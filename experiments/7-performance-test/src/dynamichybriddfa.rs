use std::borrow::Cow;
use std::hash::Hash;
use rustc_hash::FxHashMap;

use crate::number::Number;
use crate::dfa::DFA;

pub enum Offset<T, O> {
    Empty,
    U8 { offset: O, map: FxHashMap<T, u8> },
    U16 { offset: O, map: FxHashMap<T, u16> },
    U32 { offset: O, map: FxHashMap<T, u32> },
    U64 { offset: O, map: FxHashMap<T, u64> },
}

pub struct DynamicHybridDFA<N, T, O> {
    offsets: Vec<Offset<T, O>>,
    tokens: Vec<T>,
    targets: Vec<N>,
}

impl<N, T, O> DynamicHybridDFA<N, T, O>
where N: Number, T: Number + Hash + Eq, O: Number {
    pub fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
        let mut transitions = transitions.to_vec();
        
        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut offsets = Vec::with_capacity(nodes_count);
        let mut tokens = Vec::with_capacity(transitions.len());
        let mut targets = Vec::with_capacity(transitions.len());
        
        let mut idx = 0;

        fn b<S, N, T>(
            start: usize,
            count: usize,
            transitions: &[(N, T, N)]
        ) -> FxHashMap<T, S>
        where S: Number, N: Number, T: Number + Hash + Eq {
            let mut map = FxHashMap::with_capacity_and_hasher(count, Default::default());
            
            for i in 0..count {
                let (_, token, _) = transitions[start + i];

                map.insert(token, S::from_usize(i));
            }

            map
        }

        for node in 0..nodes_count {
            let node = N::from_usize(node);
            let data_offset = tokens.len();
            let start_idx = idx;

            while idx < transitions.len() && transitions[idx].0 == node {
                let (_, token, target) = transitions[idx];

                tokens.push(token);
                targets.push(target);

                idx += 1;
            }
            
            let count = tokens.len() - data_offset;

            if count == 0 {
                offsets.push(Offset::Empty);
                
                continue;
            }

            let offset = O::from_usize(data_offset);

            if count < u8::MAX as usize {
                offsets.push(Offset::U8 {
                    offset,
                    map: b::<u8, N, T>(start_idx, count, &transitions),
                });
            } else if count < u16::MAX as usize {
                offsets.push(Offset::U16 {
                    offset,
                    map: b::<u16, N, T>(start_idx, count, &transitions),
                });
            } else if count < u32::MAX as usize {
                offsets.push(Offset::U32 {
                    offset,
                    map: b::<u32, N, T>(start_idx, count, &transitions),
                });
            } else if count < u64::MAX as usize {
                offsets.push(Offset::U64 {
                    offset,
                    map: b::<u64, N, T>(start_idx, count, &transitions),
                });
            } else {
                panic!("Section size is too large!");
            }
        }
        
        Self {
            offsets,
            tokens,
            targets,
        }
    }
}

impl<N, T, O> DFA<N, T> for DynamicHybridDFA<N, T, O>
where N: Number, T: Number + Hash + Eq, O: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        let src = src.to_usize();
        let offset = self.offsets.get(src)?;

        fn l<S, N, T, O>(
            offset: O,
            map: &FxHashMap<T, S>,
            token: T,
            targets: &[N]
        ) -> Option<N>
        where S: Number, N: Number, T: Number + Hash + Eq, O: Number {
            let idx = map.get(&token)?;
            let abs = offset.to_usize() + idx.to_usize();

            Some(unsafe { *targets.get_unchecked(abs) })
        }

        match offset {
            Offset::Empty => None,
            Offset::U8 { offset, map } => l::<u8, N, T, O>(*offset, map, token, &self.targets),
            Offset::U16 { offset, map } => l::<u16, N, T, O>(*offset, map, token, &self.targets),
            Offset::U32 { offset, map } => l::<u32, N, T, O>(*offset, map, token, &self.targets),
            Offset::U64 { offset, map } => l::<u64, N, T, O>(*offset, map, token, &self.targets),
        }
    }

    fn transitions<'a>(&'a self, node: N) -> Option<Cow<'a, [T]>> {
        let node = node.to_usize();
        let offset = self.offsets.get(node)?;

        fn t<'a, S, T, O>(
            offset: O,
            map: &FxHashMap<T, S>,
            tokens: &'a [T]
        ) -> Option<Cow<'a, [T]>>
        where S: Number, T: Number + Hash + Eq, O: Number {
            let start = offset.to_usize();
            let end = start + map.len();

            Some(Cow::Borrowed(&tokens[start..end]))
        }

        match offset {
            Offset::Empty => None,
            Offset::U8 { offset, map } => t::<u8, T, O>(*offset, map, &self.tokens),
            Offset::U16 { offset, map } => t::<u16, T, O>(*offset, map, &self.tokens),
            Offset::U32 { offset, map } => t::<u32, T, O>(*offset, map, &self.tokens),
            Offset::U64 { offset, map } => t::<u64, T, O>(*offset, map, &self.tokens),
        }
    }

    fn name(&self) -> &str {
        "DynamicHybridDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.offsets.capacity() * std::mem::size_of::<Offset<T, O>>();
        mem += self.tokens.capacity() * std::mem::size_of::<T>();
        mem += self.targets.capacity() * std::mem::size_of::<N>();

        fn map_mem<S, T>(map: &FxHashMap<T, S>) -> usize {
            map.capacity() * (std::mem::size_of::<T>() + std::mem::size_of::<S>())
        }

        for node in &self.offsets {
            match node {
                Offset::Empty => {},
                Offset::U8 { map, .. } => mem += map_mem(map),
                Offset::U16 { map, .. } => mem += map_mem(map),
                Offset::U32 { map, .. } => mem += map_mem(map),
                Offset::U64 { map, .. } => mem += map_mem(map),
            }
        }

        mem
    }
}