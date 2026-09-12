//! The index registry.
//!
//! Callers never get an index back. They describe the one they want with a
//! `Draft` and receive an `IndexId`; the factory keeps the index itself and
//! hands it to whichever head needs it. Two consequences follow:
//!
//! * an index is built at most once, however many nodes of a syntax graph ask
//!   for it, and however many of them ask at the same moment;
//! * a head is cheap, because it borrows a shared index instead of owning one.
//!
//! Building is the expensive half of generation - an `Expression` over the
//! identifier pattern costs milliseconds against a real vocabulary - so
//! `create_many` fans a batch out over the worker pool, and a draft that is
//! already being built is waited on rather than built a second time.

use aho_corasick::{AhoCorasick, AhoCorasickKind};
use rayon::prelude::*;
use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use toktrie::TokTrie;

use crate::dfa::dfa::DFA;
use crate::index::expression::Expression;
use crate::index::group::Group;
use crate::index::index::Index;
use crate::index::lattice::Lattice;
use crate::index::unit::Unit;
use crate::number::Number;
use crate::vocabulary::Vocabulary;

pub const AC_KIND: AhoCorasickKind = AhoCorasickKind::ContiguousNFA;

pub type IndexId = u64;

/// A description of an index that has not been built yet.
///
/// Drafts are the cache key, so they have to say everything that distinguishes
/// one index from another and nothing else. A group is drafted from the ids of
/// its members rather than their drafts: the members are built first, which
/// keeps the key small and lets a group be composed out of indexes that already
/// exist - including other groups.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Draft {
    Lattice(String),
    Expression(String),
    Group {
        include: IndexId,
        excludes: Vec<IndexId>,
    },
}

impl Draft {
    /// A short name for the index, for diagnostics. A group borrows its
    /// inclusion's id, because that is the shape it matches.
    pub fn label(&self) -> String {
        match self {
            Self::Lattice(word) => word.clone(),
            Self::Expression(pattern) => pattern.clone(),
            Self::Group { include, .. } => format!("group({})", include),
        }
    }
}

/// The state a build has to take the lock for.
struct Registry<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    units: Vec<Arc<Unit<N, T, D>>>,
    drafts: Vec<Draft>,
    cache: HashMap<Draft, IndexId>,
    failed: HashSet<Draft>,
    pending: HashMap<Draft, Arc<Gate>>,
}

/// What a thread waits on while another builds the draft it asked for.
struct Gate {
    done: Mutex<bool>,
    signal: Condvar,
}

impl Gate {
    fn new() -> Self {
        Self {
            done: Mutex::new(false),
            signal: Condvar::new(),
        }
    }

    fn wait(&self) {
        let mut done = self.done.lock().unwrap();

        while !*done {
            done = self.signal.wait(done).unwrap();
        }
    }

    fn open(&self) {
        *self.done.lock().unwrap() = true;

        self.signal.notify_all();
    }
}

/// What `get_or_create` decided to do with a draft, taken under the lock and
/// acted on outside it.
enum Claim {
    Hit(IndexId),
    Miss,
    Build,
    Wait(Arc<Gate>),
}

pub struct Factory<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    vocabulary: Arc<Vocabulary<T>>,
    ac_base: Arc<AhoCorasick>,
    trie_base: Arc<TokTrie>,
    registry: Mutex<Registry<N, T, D>>,
    builds: AtomicUsize,
    cached: bool,
}

impl<N, T, D> Factory<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    /// Build the Aho-Corasick and TokTrie bases and open an empty registry.
    ///
    /// Both bases scan the whole vocabulary and cost roughly half a second
    /// between them, which is why `fork` exists.
    pub fn new(vocabulary: Arc<Vocabulary<T>>, cached: bool) -> Option<Self> {
        let ac_base: AhoCorasick = Lattice::<N, T>::base(AC_KIND, vocabulary.clone())?;
        let trie_base: TokTrie = Expression::<N, T, D>::base(vocabulary.clone())?;

        Some(Self::with_bases(
            vocabulary,
            Arc::new(ac_base),
            Arc::new(trie_base),
            cached,
        ))
    }

    pub fn with_bases(
        vocabulary: Arc<Vocabulary<T>>,
        ac_base: Arc<AhoCorasick>,
        trie_base: Arc<TokTrie>,
        cached: bool,
    ) -> Self {
        Self {
            vocabulary,
            ac_base,
            trie_base,
            registry: Mutex::new(Registry {
                units: Vec::new(),
                drafts: Vec::new(),
                cache: HashMap::default(),
                failed: HashSet::default(),
                pending: HashMap::default(),
            }),
            builds: AtomicUsize::new(0),
            cached,
        }
    }

    /// A factory with an empty registry over the same bases.
    pub fn fork(&self, cached: bool) -> Self {
        Self::with_bases(
            self.vocabulary.clone(),
            self.ac_base.clone(),
            self.trie_base.clone(),
            cached,
        )
    }

    pub fn vocabulary(&self) -> &Arc<Vocabulary<T>> {
        &self.vocabulary
    }

    pub fn ac_base(&self) -> &Arc<AhoCorasick> {
        &self.ac_base
    }

    pub fn trie_base(&self) -> &Arc<TokTrie> {
        &self.trie_base
    }

    /// Indexes actually constructed, ignoring the ones served from cache.
    pub fn builds(&self) -> usize {
        self.builds.load(Ordering::Relaxed)
    }

    /// Indexes currently registered.
    pub fn len(&self) -> usize {
        self.registry.lock().unwrap().units.len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn is_cached(&self, draft: &Draft) -> bool {
        self.registry.lock().unwrap().cache.contains_key(draft)
    }

    pub fn get(&self, id: IndexId) -> Option<Arc<Unit<N, T, D>>> {
        self.registry
            .lock()
            .unwrap()
            .units
            .get(id as usize)
            .cloned()
    }

    pub fn draft(&self, id: IndexId) -> Option<Draft> {
        self.registry.lock().unwrap().drafts.get(id as usize).cloned()
    }

    /// A group reports its inclusion's label, because that is the shape it
    /// matches and the name a caller recognises it by.
    pub fn label(&self, id: IndexId) -> Option<String> {
        match self.draft(id)? {
            Draft::Group { include, .. } => self.label(include),
            draft => Some(draft.label()),
        }
    }

    pub fn memory_usage(&self, id: IndexId) -> Option<usize> {
        self.get(id).map(|unit| unit.memory_usage())
    }

    pub fn node_count(&self, id: IndexId) -> Option<N> {
        self.get(id).map(|unit| unit.node_count())
    }

    pub fn create_lattice(&self, word: &str) -> Option<IndexId> {
        self.create(&Draft::Lattice(word.to_string()))
    }

    pub fn create_expression(&self, pattern: &str) -> Option<IndexId> {
        self.create(&Draft::Expression(pattern.to_string()))
    }

    pub fn create_group(&self, include: IndexId, excludes: Vec<IndexId>) -> Option<IndexId> {
        self.create(&Draft::Group { include, excludes })
    }

    /// Build `draft`, or return the id of the index that already answers it.
    ///
    /// A draft is built exactly once even when several threads ask for it at
    /// the same moment: the first claims it and the rest wait on its gate.
    /// Without that, a fan-out over sibling nodes sharing a pattern would pay
    /// for the same multi-millisecond build several times over.
    pub fn create(&self, draft: &Draft) -> Option<IndexId> {
        if !self.cached {
            return self.build(draft).map(|unit| self.register(draft, unit));
        }

        loop {
            let claim: Claim = self.claim(draft);

            match claim {
                Claim::Hit(id) => return Some(id),
                Claim::Miss => return None,
                Claim::Wait(gate) => gate.wait(),
                Claim::Build => return self.build_claimed(draft),
            }
        }
    }

    /// Build a batch, spreading it over the calling thread pool.
    ///
    /// Costs differ by orders of magnitude between a `Lattice` and an
    /// `Expression`, so the batch is handed to rayon whole and left to its work
    /// stealing rather than split up front.
    pub fn create_many(&self, drafts: &[Draft]) -> Vec<Option<IndexId>> {
        if drafts.len() < 2 {
            return drafts.iter().map(|draft| self.create(draft)).collect();
        }

        drafts.par_iter().map(|draft| self.create(draft)).collect()
    }

    fn claim(&self, draft: &Draft) -> Claim {
        let mut registry = self.registry.lock().unwrap();

        if let Some(&id) = registry.cache.get(draft) {
            return Claim::Hit(id);
        }

        if registry.failed.contains(draft) {
            return Claim::Miss;
        }

        if let Some(gate) = registry.pending.get(draft) {
            return Claim::Wait(gate.clone());
        }

        registry
            .pending
            .insert(draft.clone(), Arc::new(Gate::new()));

        Claim::Build
    }

    fn build_claimed(&self, draft: &Draft) -> Option<IndexId> {
        let unit: Option<Arc<Unit<N, T, D>>> = self.build(draft);

        let mut registry = self.registry.lock().unwrap();

        let id: Option<IndexId> = match unit {
            Some(unit) => {
                let id: IndexId = registry.units.len() as IndexId;

                registry.units.push(unit);
                registry.drafts.push(draft.clone());
                registry.cache.insert(draft.clone(), id);

                Some(id)
            }
            None => {
                registry.failed.insert(draft.clone());

                None
            }
        };

        // Taken out of the map before the gate opens, so a waiter that wakes
        // and loops round sees the cache entry rather than the claim.
        if let Some(gate) = registry.pending.remove(draft) {
            drop(registry);

            gate.open();
        }

        id
    }

    fn register(&self, draft: &Draft, unit: Arc<Unit<N, T, D>>) -> IndexId {
        let mut registry = self.registry.lock().unwrap();
        let id: IndexId = registry.units.len() as IndexId;

        registry.units.push(unit);
        registry.drafts.push(draft.clone());

        id
    }

    fn build(&self, draft: &Draft) -> Option<Arc<Unit<N, T, D>>> {
        self.builds.fetch_add(1, Ordering::Relaxed);

        let unit: Unit<N, T, D> = match draft {
            Draft::Lattice(word) => Unit::Index(Index::Lattice(Lattice::new(
                word,
                self.vocabulary.clone(),
                &self.ac_base,
            )?)),
            Draft::Expression(pattern) => Unit::Index(Index::Expression(Expression::new(
                pattern,
                self.vocabulary.clone(),
                &self.trie_base,
            )?)),
            Draft::Group { include, excludes } => {
                let include: Arc<Unit<N, T, D>> = self.get(*include)?;

                let mut members: Vec<Arc<Unit<N, T, D>>> = Vec::with_capacity(excludes.len());

                for id in excludes {
                    members.push(self.get(*id)?);
                }

                Unit::Group(Group::new(include, members, self.vocabulary.get_eos_id()))
            }
        };

        Some(Arc::new(unit))
    }
}
