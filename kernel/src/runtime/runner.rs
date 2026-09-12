//! The pool of active indexes, and the worker pool that drives them.
//!
//! A feed is three stages, and only the middle one is the caller's:
//!
//! 1. **advance** -- every head consumes the token. Heads are independent, so
//!    this fans out over the workers; the ones that reject the token die.
//! 2. **notify** -- every head that reached an accepting state is reported to
//!    the resolver, which answers with the drafts that may follow. This is the
//!    caller's modelling and runs on the runner's own thread.
//! 3. **build** -- the drafts come back as real indexes from the factory, which
//!    spreads the batch over the same workers, and each becomes a new head.
//!
//! Stages 2 and 3 repeat until nothing new appears, because an index may accept
//! the empty word and so be ready to expand the moment it is created.
//!
//! The runner never inspects a payload and never builds a graph. It knows
//! nothing about what the indexes spell.

use rayon::prelude::*;
use rayon::{ThreadPool, ThreadPoolBuilder};
use rustc_hash::FxHashSet as HashSet;
use std::sync::Arc;

use crate::dfa::dfa::DFA;
use crate::index::index::Accepting;
use crate::index::unit::Unit;
use crate::number::Number;
use crate::runtime::factory::{Draft, Factory, IndexId};
use crate::runtime::head::{Head, HeadId};
use crate::runtime::resolver::{Expansion, Report, Request, Resolver, Source};

/// Number of heads below which a stage runs on the calling thread. Advancing
/// one head is a single DFA lookup, so a dispatch per head only pays once there
/// are several of them.
pub const PARALLEL_THRESHOLD: usize = 2;

pub struct Runner<N, T, D, P>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
    P: Send + Sync,
{
    factory: Arc<Factory<N, T, D>>,
    pool: Arc<ThreadPool>,
    heads: Vec<Head<N, T, D, P>>,
    tokens: Vec<T>,
    next_id: HeadId,
    completed: bool,

    rounds: usize,
    notified: usize,
    spawned: usize,
}

impl<N, T, D, P> Runner<N, T, D, P>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
    P: Send + Sync,
{
    /// `workers` of 0 or 1 still builds a pool, so the code path is the same
    /// either way; the thresholds are what keep a small run off the workers.
    pub fn new(factory: Arc<Factory<N, T, D>>, workers: usize) -> Option<Self> {
        let pool: ThreadPool = ThreadPoolBuilder::new()
            .num_threads(workers.max(1))
            .thread_name(|i| format!("kernel-worker-{i}"))
            .build()
            .ok()?;

        Some(Self::with_pool(factory, Arc::new(pool)))
    }

    pub fn with_pool(factory: Arc<Factory<N, T, D>>, pool: Arc<ThreadPool>) -> Self {
        Self {
            factory,
            pool,
            heads: Vec::new(),
            tokens: Vec::new(),
            next_id: 0,
            completed: false,
            rounds: 0,
            notified: 0,
            spawned: 0,
        }
    }

    pub fn factory(&self) -> &Arc<Factory<N, T, D>> {
        &self.factory
    }

    pub fn pool(&self) -> &Arc<ThreadPool> {
        &self.pool
    }

    pub fn workers(&self) -> usize {
        self.pool.current_num_threads()
    }

    pub fn heads(&self) -> &[Head<N, T, D, P>] {
        &self.heads
    }

    pub fn len(&self) -> usize {
        self.heads.len()
    }

    pub fn is_empty(&self) -> bool {
        self.heads.is_empty()
    }

    pub fn is_completed(&self) -> bool {
        self.completed
    }

    pub fn tokens(&self) -> &[T] {
        &self.tokens
    }

    /// Rounds of the notify/build loop, heads reported, and heads created.
    pub fn stats(&self) -> (usize, usize, usize) {
        (self.rounds, self.notified, self.spawned)
    }

    pub fn matched(&self) -> String {
        let vocabulary = self.factory.vocabulary();
        let mut matched = String::new();

        for &token_id in &self.tokens {
            if let Some(token) = vocabulary.get_token_by_id(token_id) {
                matched.push_str(token);
            }
        }

        matched
    }

    pub fn head(&self, id: HeadId) -> Option<&Head<N, T, D, P>> {
        self.heads.iter().find(|head| head.id() == id)
    }

    /// Put an already built index to work. Returns the head's id, or `None`
    /// when no index carries `index_id`.
    pub fn spawn(&mut self, index_id: IndexId, payload: P) -> Option<HeadId> {
        let unit: Arc<Unit<N, T, D>> = self.factory.get(index_id)?;

        Some(self.push(index_id, unit, payload))
    }

    /// Build whatever the batch still needs on the workers and put each index
    /// to work.
    ///
    /// Requests naming an index that already exists cost nothing; the rest are
    /// built as one batch. Anything that fails to build is skipped, so the
    /// returned ids line up with the heads that exist rather than with
    /// `requests`.
    pub fn spawn_many(&mut self, requests: Vec<Request<P>>) -> Vec<HeadId> {
        if requests.is_empty() {
            return Vec::new();
        }

        let drafts: Vec<Draft> = requests
            .iter()
            .filter_map(|request| match &request.source {
                Source::Draft(draft) => Some(draft.clone()),
                Source::Id(_) => None,
            })
            .collect();

        let factory: Arc<Factory<N, T, D>> = self.factory.clone();

        let built: Vec<Option<IndexId>> = if drafts.is_empty() {
            Vec::new()
        } else {
            self.pool.install(|| factory.create_many(&drafts))
        };

        let mut built = built.into_iter();
        let mut heads: Vec<HeadId> = Vec::with_capacity(requests.len());

        for request in requests {
            let index_id: Option<IndexId> = match request.source {
                Source::Id(index_id) => Some(index_id),
                Source::Draft(_) => built.next().flatten(),
            };

            let Some(index_id) = index_id else { continue };
            let Some(unit) = self.factory.get(index_id) else {
                continue;
            };

            heads.push(self.push(index_id, unit, request.payload));
        }

        heads
    }

    pub fn kill(&mut self, id: HeadId) -> bool {
        let before: usize = self.heads.len();

        self.heads.retain(|head| head.id() != id);

        self.heads.len() != before
    }

    pub fn clear(&mut self) {
        self.heads.clear();
    }

    /// Every token at least one live head would accept.
    ///
    /// Sorted and deduplicated, so two runs over the same state answer
    /// identically however the work was spread over the pool.
    pub fn routes(&self) -> Vec<T> {
        if self.heads.is_empty() {
            return Vec::new();
        }

        let collected: Vec<Vec<T>> = if self.heads.len() < PARALLEL_THRESHOLD {
            self.heads.iter().map(|head| head.transitions()).collect()
        } else {
            self.pool
                .install(|| self.heads.par_iter().map(|head| head.transitions()).collect())
        };

        let mut seen: HashSet<T> = HashSet::default();
        let mut routes: Vec<T> = Vec::new();

        for transitions in collected {
            for token_id in transitions {
                if seen.insert(token_id) {
                    routes.push(token_id);
                }
            }
        }

        routes.sort_unstable();

        routes
    }

    /// Consume one token and settle the head pool around it.
    ///
    /// Returns whether any head accepted the token. As in a plain DFA walk a
    /// rejected token leaves nothing alive.
    ///
    /// The whole feed runs inside the worker pool, not merely the stages that
    /// fan out here. Rayon routes nested parallel work to the pool the current
    /// thread belongs to, so a resolver that reaches back into the factory --
    /// which is what building a wide group draft does -- shares these workers
    /// instead of starting a second pool of its own.
    pub fn feed(&mut self, token_id: T, resolver: &(dyn Resolver<P> + Sync)) -> bool {
        let pool: Arc<ThreadPool> = self.pool.clone();

        pool.install(|| self.drive(token_id, resolver))
    }

    fn drive(&mut self, token_id: T, resolver: &(dyn Resolver<P> + Sync)) -> bool {
        if !self.advance(token_id) {
            self.heads.clear();

            return false;
        }

        self.tokens.push(token_id);

        self.resolve(resolver);

        true
    }

    /// Run the notify/build loop without consuming a token.
    ///
    /// Needed when a head is spawned onto an index that accepts straight away,
    /// which would otherwise sit unreported until the next token.
    pub fn settle(&mut self, resolver: &(dyn Resolver<P> + Sync)) {
        let pool: Arc<ThreadPool> = self.pool.clone();

        pool.install(|| self.resolve(resolver))
    }

    fn resolve(&mut self, resolver: &(dyn Resolver<P> + Sync)) {
        loop {
            if resolver.aborted() {
                return;
            }

            self.rounds += 1;

            let pending: Vec<usize> = self
                .heads
                .iter()
                .enumerate()
                .filter(|(_, head)| {
                    !head.is_expanded() && matches!(head.accepting(), Accepting::Yes(_))
                })
                .map(|(i, _)| i)
                .collect();

            if pending.is_empty() {
                return;
            }

            let requests: Vec<Request<P>> = self.notify(&pending, resolver);

            // A head that accepted but cannot take another token has said
            // everything it had to say, so it leaves the pool once its children
            // are known.
            self.heads
                .retain(|head| !matches!(head.accepting(), Accepting::Yes(false)));

            if requests.is_empty() {
                return;
            }

            self.spawn_many(requests);
        }
    }

    fn advance(&mut self, token_id: T) -> bool {
        if self.heads.len() < PARALLEL_THRESHOLD {
            for head in &mut self.heads {
                head.feed(token_id);
            }
        } else {
            let pool: Arc<ThreadPool> = self.pool.clone();
            let heads: &mut Vec<Head<N, T, D, P>> = &mut self.heads;

            pool.install(|| {
                heads.par_iter_mut().for_each(|head| {
                    head.feed(token_id);
                })
            });
        }

        self.heads.retain(|head| head.is_alive());

        !self.heads.is_empty()
    }

    fn notify(
        &mut self,
        pending: &[usize],
        resolver: &(dyn Resolver<P> + Sync),
    ) -> Vec<Request<P>> {
        let vocabulary = self.factory.vocabulary().clone();
        let mut requests: Vec<Request<P>> = Vec::new();

        for &i in pending {
            if resolver.aborted() {
                break;
            }

            self.notified += 1;
            self.heads[i].mark_expanded();

            // Scoped, so the borrow of the head is over before the answer is
            // applied to the runner.
            let expansion: Expansion<P> = {
                let head: &Head<N, T, D, P> = &self.heads[i];

                let report: Report<'_, P> = Report {
                    id: head.id(),
                    index_id: head.index_id(),
                    matched: head.matched(&vocabulary),
                    payload: head.payload(),
                };

                resolver.resolve(&report)
            };

            match expansion {
                Expansion::Terminal => self.completed = true,
                Expansion::Children(children) => requests.extend(children),
            }
        }

        requests
    }

    fn push(&mut self, index_id: IndexId, unit: Arc<Unit<N, T, D>>, payload: P) -> HeadId {
        let id: HeadId = self.next_id;

        self.next_id += 1;
        self.spawned += 1;

        self.heads.push(Head::new(id, index_id, unit, payload));

        id
    }
}
