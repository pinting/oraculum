use std::borrow::Cow;
use rustc_hash::{FxHashMap as HashMap};

use crate::Number;

pub trait DFA<N: Number, T: Number> {
    fn new(transitions: HashMap<N, HashMap<T, N>>, num_nodes: usize) -> Self;
    fn next(&self, src: N, transition: T) -> Option<N>;
    fn transitions<'a>(&'a self, src: N) -> Option<Cow<'a, [T]>>;
    fn memory_usage(&self) -> usize;
}