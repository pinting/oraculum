//! What a transition table has to answer.
//!
//! `new` takes the nested map the `Expression` builder produces and may store
//! it however it likes, because the table is only ever read afterwards.
//!
//! `transitions` hands back a `Cow` so that a layout already holding a node's
//! tokens contiguously can lend them out instead of collecting a fresh `Vec`.
//! That is the hot path rather than a detail: the route set offered after every
//! token is built by asking each live head exactly this.

use std::borrow::Cow;
use rustc_hash::{FxHashMap as HashMap};

use crate::Number;

pub trait DFA<N: Number, T: Number> {
    fn new(transitions: HashMap<N, HashMap<T, N>>, num_nodes: usize) -> Self;
    fn next(&self, src: N, transition: T) -> Option<N>;
    fn transitions<'a>(&'a self, src: N) -> Option<Cow<'a, [T]>>;
    fn memory_usage(&self) -> usize;
}