use crate::number::Number;

pub trait DFA<N: Number, T: Number> {
    fn lookup(&self, src: N, token: T) -> Option<N>;
    fn transitions(&self, node: N) -> Option<Vec<T>>;
    fn name(&self) -> &str;
    fn memory_usage(&self) -> usize;
}