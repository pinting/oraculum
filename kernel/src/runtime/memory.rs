//! The mutable layer over an immutable index.
//!
//! Indexes carry no position: a `Lattice` is a table of token edges per byte
//! offset and an `Expression` is a DFA, and both are immutable once built,
//! which is what lets the factory share one of them between every head that
//! needs it. The walk over an index - where it currently stands and which
//! tokens it has consumed - is the memory, and there is one per head.
//!
//! For a flat index the memory is a single node id. For a group it is one
//! sub-memory per member, because a group decides whether it accepts by asking
//! each member where *it* stands. That recursion is the whole reason this layer
//! exists, and it nests: a member may itself be a group.
//!
//! Feeding a group walks its members here, on the calling thread. It used to
//! fan them out over the worker pool, which never paid: one member step is a
//! handful of comparisons, and `prune` drops nearly every exclusion on the
//! first token, so the fan-out was dispatching a task per member for work that
//! had already evaporated. Measured on 16 workers it cost between 1.07x at 16
//! exclusions and 1.72x at 1024, against simply walking them.

use std::borrow::Cow;
use std::sync::Arc;

use crate::dfa::dfa::DFA;
use crate::index::index::Accepting;
use crate::index::unit::Unit;
use crate::number::Number;

pub struct Memory<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    unit: Arc<Unit<N, T, D>>,
    node: N,
    dead: bool,

    /// Empty for a flat index. For a group: the inclusion first, then one entry
    /// per exclusion, in the order the group declares them.
    parts: Vec<Memory<N, T, D>>,
}

impl<N, T, D> Memory<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    pub fn new(unit: Arc<Unit<N, T, D>>) -> Self {
        let parts: Vec<Memory<N, T, D>> = match &*unit {
            Unit::Index(_) => Vec::new(),
            Unit::Group(group) => {
                let mut parts: Vec<Memory<N, T, D>> =
                    Vec::with_capacity(1 + group.excludes().len());

                parts.push(Memory::new(group.include().clone()));

                for exclude in group.excludes() {
                    parts.push(Memory::new(exclude.clone()));
                }

                parts
            }
        };

        Self {
            unit,
            node: N::from_usize(0),
            dead: false,
            parts,
        }
    }

    pub fn unit(&self) -> &Arc<Unit<N, T, D>> {
        &self.unit
    }

    /// Where the walk stands. For a group this is the inclusion's node, which
    /// is the only position an outside caller can make sense of.
    pub fn node(&self) -> N {
        match self.parts.first() {
            Some(include) => include.node(),
            None => self.node,
        }
    }

    pub fn is_dead(&self) -> bool {
        self.dead
    }

    /// Consume one token. Returns whether it was accepted; a rejected token
    /// kills the memory, and a dead memory never revives.
    pub fn feed(&mut self, token_id: T) -> bool {
        if self.dead {
            return false;
        }

        match &*self.unit {
            Unit::Index(index) => match index.next(self.node, token_id) {
                Some(next) => {
                    self.node = next;

                    true
                }
                None => {
                    self.dead = true;

                    false
                }
            },
            Unit::Group(_) => self.feed_group(token_id),
        }
    }

    fn feed_group(&mut self, token_id: T) -> bool {
        let (include, excludes) = self.parts.split_at_mut(1);

        // An exclusion that rejects the token is out of the running for good:
        // it is anchored at the start of the word, so it can never match again.
        // Its `feed` returning false is therefore not a failure of the group,
        // which is why only the inclusion's answer is propagated.
        let accepted: bool = include[0].feed(token_id);

        for exclude in excludes.iter_mut() {
            exclude.feed(token_id);
        }

        if !accepted {
            self.dead = true;
        } else {
            self.prune();
        }

        accepted
    }

    /// Drop the exclusions that rejected the token.
    ///
    /// An exclusion is anchored at the start of the word, so once it has
    /// rejected a token it can never match again and there is nothing left to
    /// ask it. Dropping it matters because the groups this was built for are
    /// wide - one exclusion per reserved word, table and field - and nearly
    /// all of them die on the first token, leaving a handful to walk for the
    /// rest of the head's life.
    fn prune(&mut self) {
        let mut i: usize = 1;

        while i < self.parts.len() {
            if self.parts[i].dead {
                // Order carries no meaning among exclusions, and the element
                // swapped in is never the inclusion at index 0.
                self.parts.swap_remove(i);
            } else {
                i += 1;
            }
        }
    }

    /// Whether an exclusion currently spells the word the inclusion has
    /// matched, which is what keeps the group from ending here.
    pub fn blocked(&self) -> bool {
        self.parts
            .iter()
            .skip(1)
            .any(|exclude| !exclude.dead && matches!(exclude.accepting(), Accepting::Yes(_)))
    }

    /// Exclusions still in the running. Falls as the word grows past them.
    pub fn live_excludes(&self) -> usize {
        self.parts.len().saturating_sub(1)
    }

    pub fn transitions(&self) -> Option<Cow<'_, [T]>> {
        if self.dead {
            return None;
        }

        match &*self.unit {
            Unit::Index(index) => index.transitions(self.node),
            Unit::Group(group) => {
                let transitions: Cow<'_, [T]> = self.parts.first()?.transitions()?;

                if !self.blocked() {
                    return Some(transitions);
                }

                // An accepting `Expression` node offers the terminating token
                // as a self loop. While an exclusion still matches, that is the
                // one token the group must not offer: generation has to go on
                // until the exclusion is left behind.
                let eos_id: T = group.eos_id();

                Some(Cow::Owned(
                    transitions
                        .iter()
                        .copied()
                        .filter(|&token_id| token_id != eos_id)
                        .collect(),
                ))
            }
        }
    }

    pub fn accepting(&self) -> Accepting {
        if self.dead {
            return Accepting::No;
        }

        match &*self.unit {
            Unit::Index(index) => index.accepting(self.node),
            Unit::Group(_) => {
                let Some(include) = self.parts.first() else {
                    return Accepting::No;
                };

                match include.accepting() {
                    Accepting::No => Accepting::No,
                    Accepting::Yes(is_more) => {
                        if self.blocked() {
                            Accepting::No
                        } else {
                            Accepting::Yes(is_more)
                        }
                    }
                }
            }
        }
    }

    /// Rewind to the start, keeping the index.
    ///
    /// A group is rebuilt rather than rewound, because `prune` has thrown its
    /// dead exclusions away and they have to come back.
    pub fn reset(&mut self) {
        *self = Memory::new(self.unit.clone());
    }
}
