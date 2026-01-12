use crate::number::Number;
use crate::dfa::DFA;

#[derive(Debug, Clone, Copy)]
struct Edge<N, T> {
    token: T,
    target: N,
}

pub struct FlatDFA<N, T, O> {
    offsets: Vec<O>,
    edges: Vec<Edge<N, T>>,
}

impl<N, T, O> FlatDFA<N, T, O>
where N: Number, T: Number, O: Number {
    pub fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
        let mut transitions: Vec<(N, T, N)> = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));

        let mut offsets = vec![O::from_usize(0); nodes_count + 2];
        let mut edges = Vec::with_capacity(transitions.len());

        let mut c = 0; // Current node
        let mut idx = O::from_usize(0);

        for (src, token, target) in &transitions {
            let src = src.to_usize();

            while c < src {
                c += 1;
                offsets[c] = idx;
            }

            let edge = Edge { token: *token, target: *target };

            edges.push(edge);

            idx += O::from_usize(1);
        }

        while c < nodes_count as usize {
            c += 1;
            offsets[c] = idx;
        }

        Self { offsets, edges }
    }
}

impl<N, T, O> DFA<N, T> for FlatDFA<N, T, O>
where N: Number, T: Number, O: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        let node = src.to_usize();

        if node + 1 >= self.offsets.len() {
            return None;
        }

        let start = self.offsets[node];
        let start = start.to_usize();

        let end = self.offsets[node + 1];
        let end = end.to_usize();

        if start == end {
            return None;
        }

        let slice = &self.edges[start..end];

        slice.binary_search_by_key(&token, |e| e.token)
            .ok()
            .map(|i| slice[i].target)
    }

    fn transitions(&self, node: N) -> Option<Vec<T>> {
        let node = node.to_usize();

        if node + 1 >= self.offsets.len() {
            return None
        }

        let start = self.offsets[node];
        let start = start.to_usize();
        
        let end = self.offsets[node + 1];
        let end = end.to_usize();

        let count = end - start;
        let mut result = Vec::with_capacity(count);

        for edge in &self.edges[start..end] {
            result.push(edge.token);
        }

        Some(result)
    }

    fn name(&self) -> &str {
        "FlatDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.edges.capacity() * std::mem::size_of::<Edge<N, T>>();
        mem += self.offsets.capacity() * std::mem::size_of::<O>();

        mem
    }
}