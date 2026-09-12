//! An active index.
//!
//! A head is one index the runner is currently walking: a `Memory` over a
//! shared index, the tokens it has consumed, and whatever the caller attached
//! to it. The payload is opaque to the kernel -- for the Python library it is
//! the graph node that produced the head, which is how a notification finds its
//! way back to the right context.

use std::sync::Arc;

use crate::dfa::dfa::DFA;
use crate::index::index::Accepting;
use crate::index::unit::Unit;
use crate::number::Number;
use crate::runtime::factory::IndexId;
use crate::runtime::memory::Memory;
use crate::vocabulary::Vocabulary;

pub type HeadId = u64;

pub struct Head<N, T, D, P>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    id: HeadId,
    index_id: IndexId,
    memory: Memory<N, T, D>,
    tokens: Vec<T>,
    payload: P,

    /// Whether the caller has already been notified about the state this head
    /// stands in. Cleared by every accepted token, so each position is reported
    /// once and only once.
    expanded: bool,

    /// Scratch for the parallel advance, so the runner can drop the heads that
    /// rejected the token without a second pass over the memories.
    alive: bool,
}

impl<N, T, D, P> Head<N, T, D, P>
where
    N: Number,
    T: Number,
    D: DFA<N, T> + Send + Sync,
{
    pub fn new(id: HeadId, index_id: IndexId, unit: Arc<Unit<N, T, D>>, payload: P) -> Self {
        Self {
            id,
            index_id,
            memory: Memory::new(unit),
            tokens: Vec::new(),
            payload,
            expanded: false,
            alive: true,
        }
    }

    pub fn id(&self) -> HeadId {
        self.id
    }

    pub fn index_id(&self) -> IndexId {
        self.index_id
    }

    pub fn node(&self) -> N {
        self.memory.node()
    }

    pub fn tokens(&self) -> &[T] {
        &self.tokens
    }

    pub fn payload(&self) -> &P {
        &self.payload
    }

    pub fn payload_mut(&mut self) -> &mut P {
        &mut self.payload
    }

    pub fn memory(&self) -> &Memory<N, T, D> {
        &self.memory
    }

    pub fn is_alive(&self) -> bool {
        self.alive && !self.memory.is_dead()
    }

    pub fn is_expanded(&self) -> bool {
        self.expanded
    }

    pub fn mark_expanded(&mut self) {
        self.expanded = true;
    }

    pub fn accepting(&self) -> Accepting {
        self.memory.accepting()
    }

    pub fn transitions(&self) -> Vec<T> {
        match self.memory.transitions() {
            Some(transitions) => transitions.into_owned(),
            None => Vec::new(),
        }
    }

    /// Consume one token, recording it so the caller can be told what this head
    /// matched when it is asked to expand.
    pub fn feed(&mut self, token_id: T) -> bool {
        self.alive = self.memory.feed(token_id);

        if self.alive {
            self.tokens.push(token_id);
            self.expanded = false;
        }

        self.alive
    }

    pub fn matched(&self, vocabulary: &Vocabulary<T>) -> String {
        let mut matched = String::new();

        for &token_id in &self.tokens {
            if let Some(token) = vocabulary.get_token_by_id(token_id) {
                matched.push_str(token);
            }
        }

        matched
    }
}
