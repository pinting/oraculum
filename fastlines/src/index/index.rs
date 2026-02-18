use std::borrow::Cow;
use crate::number::Number;

pub trait Index<N: Number, T: Number> {
    fn node_count(&self) -> N;
    fn next(&self, node_id: N, token_id: T) -> Option<N>;
    fn transitions<'a>(&'a self, node_id: N) -> Option<Cow<'a, [T]>>;
    fn name(&self) -> &str;
    fn memory_usage(&self) -> usize;
}
