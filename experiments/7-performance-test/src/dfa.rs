use std::borrow::Cow;

use crate::number::Number;

pub trait DFA<N: Number, T: Number> {
    fn lookup(&self, src: N, token: T) -> Option<N>;
    fn transitions<'a>(&'a self, node: N) -> Option<Cow<'a, [T]>>;
    fn name(&self) -> &str;
    fn memory_usage(&self) -> usize;
}