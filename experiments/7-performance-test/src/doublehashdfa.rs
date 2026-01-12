use rustc_hash::{FxHashMap as HashMap};

use crate::number::Number;
use crate::dfa::DFA;

pub struct DoubleHashDFA<N, T> {
    m: HashMap<N, HashMap<T, N>>,
}

impl<N, T> DoubleHashDFA<N, T>
where N: Number, T: Number {
    pub fn new(transitions: &[(N, T, N)]) -> Self {
        let mut m: HashMap<N, HashMap<T, N>> = HashMap::default();

        for &(src, token, target) in transitions {
            m.entry(src).or_default().insert(token, target);
        }

        Self { m }
    }
}

impl<N, T> DFA<N, T> for DoubleHashDFA<N, T>
where N: Number, T: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        self.m.get(&src).and_then(|m| m.get(&token)).copied()
    }

    fn transitions(&self, node: N) -> Option<Vec<T>> {
        let inner = self.m.get(&node)?;

        let mut result = Vec::new();

        for &token in inner.keys() {
            result.push(token);
        }
        
        Some(result)
    }

    fn name(&self) -> &str {
        "DoubleHashDFA"
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