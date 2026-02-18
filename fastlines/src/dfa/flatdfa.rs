use std::borrow::Cow;
use rustc_hash::{FxHashMap as HashMap};

use crate::Number;
use crate::dfa::dfa::DFA;

enum Offsets {
    U8(Vec<u8>),
    U16(Vec<u16>),
    U32(Vec<u32>),
    U64(Vec<u64>),
}

pub struct FlatDFA<N, T> {
    offsets: Offsets,
    tokens: Vec<T>,
    targets: Vec<N>,
}

impl<N, T> FlatDFA<N, T>
where N: Number, T: Number {
    #[inline(always)]
    fn next_inner<O: Number>(&self, offsets: &[O], src: N, transition: T) -> Option<N> {
        let node = src.to_usize();

        if node + 1 >= offsets.len() {
            return None;
        }

        let start = offsets[node].to_usize();
        let end = offsets[node + 1].to_usize();

        if start == end {
            return None;
        }

        let slice = &self.tokens[start..end];

        slice.binary_search(&transition)
            .ok()
            .map(|i| self.targets[start + i])
    }

    fn transitions_inner<O: Number>(&self, offsets: &[O], src: N) -> Option<Cow<'_, [T]>> {
        let node = src.to_usize();

        if node + 1 >= offsets.len() {
            return None
        }

        let start = offsets[node].to_usize();
        let end = offsets[node + 1].to_usize();

        Some(Cow::Borrowed(&self.tokens[start..end]))
    }
}

impl<N, T> DFA<N, T> for FlatDFA<N, T>
where N: Number, T: Number {
    fn new(m: HashMap<N, HashMap<T, N>>, nodes_count: usize) -> Self {
        let mut transitions: Vec<(N, T, N)> = Vec::with_capacity(
            m.values().map(|x| x.len()).sum());

        for (src, targets) in m {
            for (token, target) in targets {
                transitions.push((src, token, target));
            }
        }

        transitions.sort_unstable_by(|a, b|
            a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));

        let mut raw_offsets = vec![0usize; nodes_count + 2];
        let mut tokens = Vec::with_capacity(transitions.len());
        let mut targets = Vec::with_capacity(transitions.len());
        let mut c = 0;
        let mut idx = 0usize;

        for (src, token, target) in &transitions {
            let src = src.to_usize();

            while c < src {
                c += 1;
                raw_offsets[c] = idx;
            }

            tokens.push(*token);
            targets.push(*target);

            idx += 1;
        }

        while c < nodes_count as usize {
            c += 1;
            raw_offsets[c] = idx;
        }

        let max_offset = tokens.len();

        let build_offsets = |raw: &[usize]| -> Offsets {
            fn convert<O: Number>(raw: &[usize]) -> Vec<O> {
                raw.iter().map(|&v| O::from_usize(v)).collect()
            }

            if max_offset <= u8::MAX as usize {
                Offsets::U8(convert(raw))
            } else if max_offset <= u16::MAX as usize {
                Offsets::U16(convert(raw))
            } else if max_offset <= u32::MAX as usize {
                Offsets::U32(convert(raw))
            } else if max_offset <= u64::MAX as usize {
                Offsets::U64(convert(raw))
            } else {
                unreachable!()
            }
        };

        let offsets = build_offsets(&raw_offsets);

        Self { offsets, tokens, targets }
    }

    #[inline(always)]
    fn next(&self, src: N, transition: T) -> Option<N> {
        match &self.offsets {
            Offsets::U8(o) => self.next_inner(o, src, transition),
            Offsets::U16(o) => self.next_inner(o, src, transition),
            Offsets::U32(o) => self.next_inner(o, src, transition),
            Offsets::U64(o) => self.next_inner(o, src, transition),
        }
    }

    fn transitions<'a>(&'a self, src: N) -> Option<Cow<'a, [T]>> {
        match &self.offsets {
            Offsets::U8(o) => self.transitions_inner(o, src),
            Offsets::U16(o) => self.transitions_inner(o, src),
            Offsets::U32(o) => self.transitions_inner(o, src),
            Offsets::U64(o) => self.transitions_inner(o, src),
        }
    }

    fn name(&self) -> &str {
        "FlatDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += match &self.offsets {
            Offsets::U8(o) => o.capacity() * std::mem::size_of::<u8>(),
            Offsets::U16(o) => o.capacity() * std::mem::size_of::<u16>(),
            Offsets::U32(o) => o.capacity() * std::mem::size_of::<u32>(),
            Offsets::U64(o) => o.capacity() * std::mem::size_of::<u64>(),
        };
        mem += self.tokens.capacity() * std::mem::size_of::<T>();
        mem += self.targets.capacity() * std::mem::size_of::<N>();

        mem
    }
}
