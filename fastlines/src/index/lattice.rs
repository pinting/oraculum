use aho_corasick::{AhoCorasick, AhoCorasickKind};
use std::{borrow::Cow, sync::Arc};

use crate::{index::index::Index, number::Number, vocabulary::Vocabulary};

pub struct Lattice<N, T> {
    offsets: Vec<N>,
    targets: Vec<T>,
    vocabulary: Arc<Vocabulary<T>>,
    length: usize,
}

impl<N, T> Lattice<N, T>
where N: Number, T: Number {
    pub fn base(kind: AhoCorasickKind, vocabulary: Arc<Vocabulary<T>>) -> Option<AhoCorasick> {
        let tokens = vocabulary.get_tokens();
        let patterns: Vec<&str> = tokens.iter().map(|token| token.as_ref()).collect();
        
        AhoCorasick::builder()
            .kind(Some(kind))
            .build(patterns)
            .ok()
    }

    pub fn new(constant: &str, vocabulary: Arc<Vocabulary<T>>, ac: &AhoCorasick) -> Self {
        let length = constant.len();

        let mut heads = vec![N::max_value(); length + 1];
        let mut edges = Vec::<(T, N)>::with_capacity(length * 2);

        fn insert<N, T>(heads: &mut Vec<N>, edges: &mut Vec<(T, N)>, start: usize, token_id: T) 
        where N: Number, T: Number {
            let next = heads[start];
            let current = N::from_usize(edges.len());
            let edge = (token_id, next);

            edges.push(edge);

            heads[start] = current;
        }

        for m in ac.find_overlapping_iter(constant) {
            let idx = m.pattern().as_usize();
            let Some(id) = vocabulary.get_id_by_idx(idx) else { continue };

            let start = m.start();

            insert(&mut heads, &mut edges, start, id);
        }

        let mut offsets = Vec::with_capacity(heads.len());
        let mut targets = Vec::with_capacity(edges.len());

        for head in heads {
            offsets.push(N::from_usize(targets.len()));

            let mut current = head;

            while current != N::max_value() {
                let (target, next) = edges[current.to_usize()];

                targets.push(target);

                current = next;
            }
        }
        
        Self {
            offsets,
            targets,
            vocabulary: vocabulary.clone(),
            length: constant.len()
        }
    }
}


impl<N, T> Index<N, T> for Lattice<N, T>
where N: Number, T: Number {
    fn start(&self) -> N {
        N::from_usize(0)
    }

    fn next(&self, node_id: N, token_id: T) -> Option<N> {
        self.vocabulary
            .get_token_by_id(token_id)
            .map(|t| node_id.to_usize() + t.len())
            .filter(|&next| next <= self.length)
            .map(N::from_usize)
    }

    fn transitions<'a>(&'a self, node_id: N) -> Option<std::borrow::Cow<'a, [T]>> {
        let i = node_id.to_usize();

        if i >= self.length {
            return None;
        }

        let start = self.offsets.get(i)?.to_usize();
        let end = self.offsets.get(i + 1)
            .map_or(self.targets.len(), |n| n.to_usize());

        self.targets.get(start..end).map(Cow::Borrowed)
    }

    fn name(&self) -> &str {
        "Lattice"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.offsets.capacity() * std::mem::size_of::<N>();
        mem += self.targets.capacity() * std::mem::size_of::<T>();

        mem
    }
}