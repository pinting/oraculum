use rustc_hash::{FxHashMap as HashMap};
use std::borrow::Cow;

use crate::Number;
use crate::dfa::dfa::DFA;

pub struct DoubleHashDFA<N, T> {
    m: HashMap<N, HashMap<T, N>>,
}

impl<N, T> DFA<N, T> for DoubleHashDFA<N, T>
where N: Number, T: Number {
    fn new(m: HashMap<N, HashMap<T, N>>, _nodes_count: usize) -> Self {
        Self { m }
    }

    #[inline(always)]
    fn next(&self, src: N, token: T) -> Option<N> {
        self.m.get(&src).and_then(|m| m.get(&token)).copied()
    }
    
    fn transitions<'a>(&'a self, src: N) -> Option<Cow<'a, [T]>> {
        let inner = self.m.get(&src)?;
        let mut result = Vec::new();

        for &token in inner.keys() {
            result.push(token);
        }
        
        Some(Cow::Owned(result))
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.m.capacity() * (std::mem::size_of::<N>() + std::mem::size_of::<HashMap<T, N>>() + 1);

        for inner in self.m.values() {
            mem += inner.capacity() * (std::mem::size_of::<T>() + std::mem::size_of::<N>() + 1);
        }

        mem
    }
}