//! What a flat index has to answer, and the dispatch over the two of them.
//!
//! `BaseIndex` is the walk: which tokens lead out of a node, where one of them
//! leads, and whether a word may end here. `Accepting` says a little more than
//! a bool - `Yes(is_more)` carries whether the word could also go on - which
//! is what lets the runner retire a head that has nothing left to match rather
//! than keep it in the pool for every later token.
//!
//! `Index` is how the two are reached once the concrete type is no longer known
//! statically, which is the case from `Unit` down.

use std::borrow::Cow;
use crate::{Expression, Lattice, number::Number};
use crate::dfa::dfa::DFA;

pub enum Accepting {
    No,
    Yes(/* is_more: */ bool)
}

pub trait BaseIndex<N: Number, T: Number> {
    fn node_count(&self) -> N;
    fn next(&self, node_id: N, token_id: T) -> Option<N>;
    fn transitions<'a>(&'a self, node_id: N) -> Option<Cow<'a, [T]>>;
    fn accepting(&self, node_id: N) -> Accepting;
    fn memory_usage(&self) -> usize;
}


pub enum Index<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    Lattice(Lattice<N, T>),
    Expression(Expression<N, T, D>),
}

impl<N, T, D> Index<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    pub fn node_count(&self) -> N {
        match self {
            Self::Lattice(idx) => idx.node_count(),
            Self::Expression(idx) => idx.node_count(),
        }
    }

    pub fn next(&self, node_id: N, token_id: T) -> Option<N> {
        match self {
            Self::Lattice(idx) => idx.next(node_id, token_id),
            Self::Expression(idx) => idx.next(node_id, token_id),
        }
    }

    pub fn transitions(&self, node_id: N) -> Option<Cow<'_, [T]>> {
        match self {
            Self::Lattice(idx) => idx.transitions(node_id),
            Self::Expression(idx) => idx.transitions(node_id),
        }
    }

    pub fn accepting(&self, node_id: N) -> Accepting {
        match self {
            Self::Lattice(idx) => idx.accepting(node_id),
            Self::Expression(idx) => idx.accepting(node_id),
        }
    }

    pub fn memory_usage(&self) -> usize {
        match self {
            Self::Lattice(idx) => idx.memory_usage(),
            Self::Expression(idx) => idx.memory_usage(),
        }
    }
}
