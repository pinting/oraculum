//! The pool of active indexes, and the worker pool that drives them.
//!
//! A feed is three stages, and only the middle one is the caller's:
//!
//! 1. **advance** - every head consumes the token. Heads are independent, so
//!    this fans out over the workers; the ones that reject the token die.
//! 2. **notify** - every head that reached an accepting state is reported to
//!    the resolver, which answers with the drafts that may follow. This is the
//!    caller's modelling and runs on the runner's own thread.
//! 3. **build** - the drafts come back as real indexes from the factory, which
//!    spreads the batch over the same workers, and each becomes a new head.
//!
//! Stages 2 and 3 repeat until nothing new appears, because an index may accept
//! the empty word and so be ready to expand the moment it is created.
//!
//! The runner never inspects a payload and never builds a graph. It knows
//! nothing about what the indexes spell.

#[cfg(feature = "parallel")]
use rayon::prelude::*;

use crate::runtime::pool::{self, Pool};
use std::sync::Arc;

use crate::dfa::dfa::DFA;
use crate::index::index::Accepting;
use crate::index::unit::Unit;
use crate::number::Number;
use crate::runtime::factory::{Draft, Factory, IndexId};
use crate::runtime::head::{Head, HeadId};
use crate::runtime::resolver::{Expansion, Report, Request, Resolver, Source};
use crate::vocabulary::Vocabulary;

/// Bits per word of the route bitset.
const BITS: usize = u64::BITS as usize;

/// Number of heads below which `routes` runs on the calling thread.
///
/// Each worker the union is spread over needs a bitset of its own, which is one
/// zeroed word per 64 token ids - 31KB against this vocabulary - so a handful
/// of heads is answered here rather than paying for that twice over. Measured
/// on the seer corpus, whose head count peaks at 15: raising this from 2 to 32
/// took a 16 worker run from 2.75s to 1.93s, while the batches that make the
/// fan-out worth having - 64 heads and up - are untouched, and still 23x on 16
/// workers.
pub const PARALLEL_THRESHOLD: usize = 32;

/// Number of heads below which `advance` runs on the calling thread.
///
/// Feeding one head is a single DFA lookup, about 230ns, so a task per head
/// costs more than the work until there are thousands of them. Measured on a
/// 16 core machine: fanning out at 512 heads is twice as slow as not.
pub const ADVANCE_PARALLEL_THRESHOLD: usize = 2048;

pub struct Runner<N, T, D, P>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
    P: Send + Sync,
{
    factory: Arc<Factory<N, T, D>>,
    pool: Arc<Pool>,
    heads: Vec<Head<N, T, D, P>>,
    tokens: Vec<T>,
    next_id: HeadId,
    completed: bool,

    /// Words of the route bitset, fixed by the vocabulary - see `routes`.
    words: usize,

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
    ///
    /// Without the `parallel` feature there is no pool to build and this cannot
    /// fail - the `Option` stays because the caller's error path does.
    pub fn new(factory: Arc<Factory<N, T, D>>, workers: usize) -> Option<Self> {
        let pool: Pool = pool::build(workers)?;

        Some(Self::with_pool(factory, Arc::new(pool)))
    }

    pub fn with_pool(factory: Arc<Factory<N, T, D>>, pool: Arc<Pool>) -> Self {
        let words: usize = Self::words(&factory);

        Self {
            factory,
            pool,
            heads: Vec::new(),
            tokens: Vec::new(),
            next_id: 0,
            completed: false,
            words,
            rounds: 0,
            notified: 0,
            spawned: 0,
        }
    }

    /// Words of the route bitset: one bit per token id the vocabulary can
    /// answer with, plus the terminator, which is the one id an index offers
    /// that the table itself does not carry.
    fn words(factory: &Factory<N, T, D>) -> usize {
        let vocabulary: &Arc<Vocabulary<T>> = factory.vocabulary();

        let highest: usize = vocabulary
            .get_ids()
            .iter()
            .map(|id| id.to_usize())
            .max()
            .unwrap_or(0)
            .max(vocabulary.get_eos_id().to_usize());

        (highest + 1).div_ceil(BITS)
    }

    pub fn factory(&self) -> &Arc<Factory<N, T, D>> {
        &self.factory
    }

    pub fn pool(&self) -> &Arc<Pool> {
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

        // Entering the pool costs several microseconds, so it is worth it only
        // when the batch has real building to do - see `Factory::create_many`,
        // which makes the same call about fanning out at all.
        let built: Vec<Option<IndexId>> = if drafts.is_empty() {
            Vec::new()
        } else if factory.unbuilt(&drafts) < 2 {
            factory.create_many(&drafts)
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
    ///
    /// The union is taken as a bitset over token ids rather than by collecting
    /// each head's routes and hashing them. Both halves of that matter: a head
    /// offers tens of thousands of tokens and the index holds them contiguous,
    /// so collecting meant copying every one of them out, and the hash pass
    /// that followed was serial work behind a parallel scan - at 64 heads it
    /// was nine tenths of the call. A bitset is a word-wise OR to merge, which
    /// is what lets the whole union be reduced across the workers, and it comes
    /// out in id order, which is the order this promises.
    pub fn routes(&self) -> Vec<T> {
        if self.heads.is_empty() {
            return Vec::new();
        }

        #[cfg(feature = "parallel")]
        let bits: Vec<u64> = if self.heads.len() < PARALLEL_THRESHOLD {
            self.mark_all()
        } else {
            self.pool.install(|| {
                self.heads
                    .par_iter()
                    .fold(
                        || vec![0u64; self.words],
                        |mut bits, head| {
                            mark(&mut bits, head);

                            bits
                        },
                    )
                    .reduce(|| vec![0u64; self.words], union)
            })
        };

        #[cfg(not(feature = "parallel"))]
        let bits: Vec<u64> = self.mark_all();

        expand(&bits)
    }

    /// Every head's routes into one bitset, on the calling thread.
    fn mark_all(&self) -> Vec<u64> {
        let mut bits: Vec<u64> = vec![0u64; self.words];

        for head in &self.heads {
            mark(&mut bits, head);
        }

        bits
    }

    /// Consume one token and settle the head pool around it.
    ///
    /// Returns whether any head accepted the token. As in a plain DFA walk a
    /// rejected token leaves nothing alive.
    ///
    /// The feed itself is not entered through the pool. It used to be, so that
    /// a resolver reaching back into the factory would share these workers
    /// rather than start a pool of its own - but entering a pool costs a job
    /// submission and a wait, and that was being paid once per token to wrap
    /// stages that mostly run on this thread anyway: measured at 3.0x the cost
    /// of a feed on 16 workers, and 2.5x on one. The stages that do fan out -
    /// `advance`, `routes` and the batch build in `spawn_many` - enter the pool
    /// themselves, which is where the cost belongs. A resolver that builds
    /// indexes by calling the factory directly now has its nested parallelism
    /// run on rayon's global pool instead of this one.
    pub fn feed(&mut self, token_id: T, resolver: &(dyn Resolver<P> + Sync)) -> bool {
        self.drive(token_id, resolver)
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
        self.resolve(resolver)
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
        #[cfg(not(feature = "parallel"))]
        for head in &mut self.heads {
            head.feed(token_id);
        }

        #[cfg(feature = "parallel")]
        if self.heads.len() < ADVANCE_PARALLEL_THRESHOLD {
            for head in &mut self.heads {
                head.feed(token_id);
            }
        } else {
            let pool: Arc<Pool> = self.pool.clone();
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

/// Set a bit for every token this head would accept.
///
/// The head's routes are read where the index holds them rather than copied
/// out: a `Lattice` and an `Expression` both keep the route set of a node
/// contiguous, so this walks the index's own memory.
fn mark<N, T, D, P>(bits: &mut [u64], head: &Head<N, T, D, P>)
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    let Some(transitions) = head.memory().transitions() else {
        return;
    };

    for &token_id in transitions.iter() {
        let id: usize = token_id.to_usize();

        bits[id / BITS] |= 1u64 << (id % BITS);
    }
}

/// Merge one worker's bitset into another's.
fn union(mut left: Vec<u64>, right: Vec<u64>) -> Vec<u64> {
    for (word, other) in left.iter_mut().zip(right) {
        *word |= other;
    }

    left
}

/// The set bits as token ids, ascending.
fn expand<T: Number>(bits: &[u64]) -> Vec<T> {
    let total: usize = bits.iter().map(|word| word.count_ones() as usize).sum();
    let mut routes: Vec<T> = Vec::with_capacity(total);

    for (index, &word) in bits.iter().enumerate() {
        let mut word: u64 = word;

        while word != 0 {
            let bit: usize = word.trailing_zeros() as usize;

            routes.push(T::from_usize(index * BITS + bit));

            // Clear the lowest set bit and go again.
            word &= word - 1;
        }
    }

    routes
}
