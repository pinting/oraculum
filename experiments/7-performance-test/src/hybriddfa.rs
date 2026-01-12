use rustc_hash::{FxHashMap as HashMap};
use std::borrow::Cow;

use crate::number::Number;
use crate::dfa::DFA;

pub struct HybridDFA<N, T, O> {
    offsets: Vec<O>,
    tokens: Vec<T>,
    targets: Vec<HashMap<T, N>>,
}

impl<N, T, O> HybridDFA<N, T, O>
where N: Number, T: Number, O: Number {
    pub fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
        let mut targets = vec![HashMap::default(); nodes_count];

        let mut transitions = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut offsets = vec![O::from_usize(0); nodes_count + 2];
        let mut tokens = Vec::with_capacity(transitions.len());

        let mut c = 0;
        let mut idx = O::from_usize(0);

        for (src, token, target) in transitions {
            if let Some(map) = targets.get_mut(src.to_usize()) {
                map.insert(token, target);
            }

            while c < src.to_usize() {
                c += 1;
                offsets[c] = idx;
            }

            tokens.push(token);
            idx += O::from_usize(1);
        }

        while c < nodes_count {
            c += 1;
            offsets[c] = idx;
        }

        Self { targets, offsets, tokens }
    }
}

impl<N, T, O> DFA<N, T> for HybridDFA<N, T, O>
where N: Number, T: Number, O: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        self.targets.get(src.to_usize())
            .and_then(|m| m.get(&token))
            .copied()
    }

    fn transitions<'a>(&'a self, node: N) -> Option<Cow<'a, [T]>> {
        let node = node.to_usize();

        if node + 1 >= self.offsets.len() {
            return None
        }

        let start = self.offsets[node];
        let start = start.to_usize();

        let end: O = self.offsets[node + 1];
        let end = end.to_usize();

        Some(Cow::Borrowed(&self.tokens[start..end]))
    }

    fn name(&self) -> &str {
        "HybridDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.targets.capacity() * std::mem::size_of::<HashMap<T, N>>();

        for map in &self.targets {
            mem += map.capacity() * (std::mem::size_of::<T>() + std::mem::size_of::<N>() + 1);
        }

        mem += self.offsets.capacity() * std::mem::size_of::<O>();
        mem += self.tokens.capacity() * std::mem::size_of::<T>();

        mem
    }
}