use rustc_hash::{FxHashMap as HashMap};
use std::borrow::Cow;

use crate::Number;
use crate::dfa::dfa::DFA;

#[derive(Copy, Clone)]
enum SectionUnit {
    U8,
    U16,
    U32,
    U64,
}

impl SectionUnit {
    fn from_section_size(section_size: usize) -> Self {
        if section_size < u8::MAX as usize {
            Self::U8
        } else if section_size < u16::MAX as usize {
            Self::U16
        } else if section_size < u32::MAX as usize {
            Self::U32
        } else if section_size < u64::MAX as usize {
            Self::U64
        } else {
            unreachable!()
        }
    }

    fn byte_size(&self) -> usize {
        match self {
            Self::U8 => 1,
            Self::U16 => 2,
            Self::U32 => 4,
            Self::U64 => 8,
        }
    }

    #[inline(always)]
    fn _get<S: Number, N: Number, T: Number>(
        index_ptr: *const u64,
        index_offset: usize,
        data_offset: usize,
        section_mask: T,
        token: T,
        tokens: &[T],
        targets: &[N]
    ) -> Option<N> {
        let mut h = hash(token, section_mask);
        let index_base_ptr = unsafe { index_ptr.add(index_offset) as *const S };

        loop {
            let p = h.to_usize();
            let v = unsafe { *index_base_ptr.add(p) };

            if v == S::max_value() {
                return None;
            }

            let idx = data_offset + v.to_usize();
            let candidate = unsafe { *tokens.get_unchecked(idx) };

            if candidate == token {
                return Some(unsafe { *targets.get_unchecked(idx) });
            }

            h = (h + T::from_usize(1)) & section_mask;
        }
    }

    fn _set<S: Number, N: Number, T: Number>(
        transitions: &[(N, T, N)],
        index: &mut [u64],
        index_offset: usize,
        data_start: usize,
        data_count: usize,
        section_mask: usize
    ) {
        let base_ptr = unsafe { (index.as_mut_ptr() as *mut u64).add(index_offset) as *mut S };
        let mask = T::from_usize(section_mask);

        for i in 0..data_count {
            let idx = data_start + i;
            let (_, token, _) = transitions[idx];

            let v = S::from_usize(i);
            let mut h = hash(token, mask);

            loop {
                let p = h.to_usize();

                unsafe {
                    if *base_ptr.add(p) == S::max_value() {
                        *base_ptr.add(p) = v;

                        break;
                    }
                }

                h = (h + T::from_usize(1)) & mask;
            }
        }
    }

    #[inline(always)]
    fn get<N: Number, T: Number>(
        &self,
        index_ptr: *const u64,
        index_offset: usize,
        data_offset: usize,
        section_mask: T,
        token: T,
        tokens: &[T],
        targets: &[N]
    ) -> Option<N> {
        match self {
            Self::U8  => Self::_get::<u8, N, T>(index_ptr, index_offset, data_offset, section_mask, token, tokens, targets),
            Self::U16 => Self::_get::<u16, N, T>(index_ptr, index_offset, data_offset, section_mask, token, tokens, targets),
            Self::U32 => Self::_get::<u32, N, T>(index_ptr, index_offset, data_offset, section_mask, token, tokens, targets),
            Self::U64 => Self::_get::<u64, N, T>(index_ptr, index_offset, data_offset, section_mask, token, tokens, targets),
        }
    }

    fn set<N: Number, T: Number>(
        &self,
        transitions: &[(N, T, N)],
        index: &mut [u64],
        index_offset: usize,
        data_start: usize,
        data_count: usize,
        section_mask: usize
    ) {
        match self {
            Self::U8  => Self::_set::<u8, N, T>(transitions, index, index_offset, data_start, data_count, section_mask),
            Self::U16 => Self::_set::<u16, N, T>(transitions, index, index_offset, data_start, data_count, section_mask),
            Self::U32 => Self::_set::<u32, N, T>(transitions, index, index_offset, data_start, data_count, section_mask),
            Self::U64 => Self::_set::<u64, N, T>(transitions, index, index_offset, data_start, data_count, section_mask),
        }
    }
}

#[derive(Copy, Clone)]
struct Header<O, T> {
    data_offset: O,
    index_offset: O,
    section_mask: T,
    unit: Option<SectionUnit>,
}

enum Headers<T> {
    U8(Vec<Header<u8, T>>),
    U16(Vec<Header<u16, T>>),
    U32(Vec<Header<u32, T>>),
    U64(Vec<Header<u64, T>>),
}

pub struct FastHashDFA<N, T> {
    headers: Headers<T>,
    tokens: Vec<T>,
    targets: Vec<N>,
    index: Vec<u64>,
}

impl<N, T> FastHashDFA<N, T>
where N: Number, T: Number {
    #[inline(always)]
    fn _next<O: Number>(&self, headers: &[Header<O, T>], src: N, transition: T) -> Option<N> {
        let src = src.to_usize();
        let header = headers.get(src)?;

        let unit = match header.unit {
            Some(u) => u,
            None => unreachable!(),
        };

        let index_offset = header.index_offset.to_usize();
        let data_offset = header.data_offset.to_usize();
        let section_mask = header.section_mask;
        let index_ptr = self.index.as_ptr();

        unit.get(index_ptr, index_offset, data_offset, section_mask, transition, &self.tokens, &self.targets)
    }

    fn _transitions<O: Number>(&self, headers: &[Header<O, T>], src: N) -> Option<Cow<'_, [T]>> {
        let node = src.to_usize();
        let header = headers.get(node)?;

        let start = header.data_offset.to_usize();
        let end = match headers.get(node + 1) {
            Some(h) => h.data_offset.to_usize(),
            None => self.tokens.len(),
        };

        if start == end {
            return None
        }

        Some(Cow::Borrowed(&self.tokens[start..end]))
    }
}

impl<N, T> DFA<N, T> for FastHashDFA<N, T>
where N: Number, T: Number {
    fn new(m: HashMap<N, HashMap<T, N>>, nodes_count: usize) -> Self {
        let mut transitions: Vec<(N, T, N)> = Vec::with_capacity(
            m.values().map(|x| x.len()).sum());

        for (src, targets) in m {
            for (token, target) in targets {
                transitions.push((src, token, target));
            }
        }

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        struct NodeMeta<T> {
            data_offset: usize,
            section_mask: T,
            unit: Option<SectionUnit>,
            index_offset: usize,
        }

        let mut tokens = Vec::with_capacity(transitions.len());
        let mut targets = Vec::with_capacity(transitions.len());
        let mut metas: Vec<NodeMeta<T>> = Vec::with_capacity(nodes_count);
        let mut idx = 0;
        let mut slots_count = 0;

        for node in 0..nodes_count {
            let node_id = N::from_usize(node);
            let data_offset = tokens.len();

            while idx < transitions.len() && transitions[idx].0 == node_id {
                let (_, token, target) = transitions[idx];

                tokens.push(token);
                targets.push(target);

                idx += 1;
            }

            let data_count = tokens.len() - data_offset;

            if data_count == 0 {
                metas.push(NodeMeta {
                    data_offset,
                    section_mask: T::from_usize(0),
                    unit: None,
                    index_offset: 0,
                });

                continue;
            }

            let section_size = (data_count * 2).next_power_of_two().max(4);
            let section_mask = section_size - 1;

            let unit = SectionUnit::from_section_size(section_size);
            let bytes = section_size * unit.byte_size();
            let slots = (bytes + 7) / 8;
            let index_offset = slots_count;

            slots_count += slots;

            metas.push(NodeMeta {
                data_offset,
                section_mask: T::from_usize(section_mask),
                unit: Some(unit),
                index_offset,
            });
        }

        let max_offset = tokens.len().max(slots_count);

        let build_headers = |metas: &[NodeMeta<T>]| -> Headers<T> {
            fn convert<O: Number, T: Copy>(metas: &[NodeMeta<T>]) -> Vec<Header<O, T>> {
                metas.iter().map(|m| Header {
                    data_offset: O::from_usize(m.data_offset),
                    index_offset: O::from_usize(m.index_offset),
                    section_mask: m.section_mask,
                    unit: m.unit,
                }).collect()
            }

            if max_offset <= u8::MAX as usize {
                Headers::U8(convert(&metas))
            } else if max_offset <= u16::MAX as usize {
                Headers::U16(convert(&metas))
            } else if max_offset <= u32::MAX as usize {
                Headers::U32(convert(&metas))
            } else if max_offset <= u64::MAX as usize {
                Headers::U64(convert(&metas))
            } else {
                unreachable!()
            }
        };

        let headers = build_headers(&metas);

        let mut index = vec![u64::MAX; slots_count];

        for node in 0..nodes_count {
            let meta = &metas[node];

            let unit = match meta.unit {
                Some(u) => u,
                None => continue,
            };

            let data_start = meta.data_offset;
            let data_next_start = match metas.get(node + 1) {
                Some(m) => m.data_offset,
                None => tokens.len(),
            };

            let data_count = data_next_start - data_start;
            let index_offset = meta.index_offset;
            let section_mask = meta.section_mask.to_usize();

            unit.set::<N, T>(&transitions, &mut index, index_offset, data_start, data_count, section_mask);
        }

        Self {
            headers,
            tokens,
            targets,
            index,
        }
    }

    #[inline(always)]
    fn next(&self, src: N, transition: T) -> Option<N> {
        match &self.headers {
            Headers::U8(h) => self._next(h, src, transition),
            Headers::U16(h) => self._next(h, src, transition),
            Headers::U32(h) => self._next(h, src, transition),
            Headers::U64(h) => self._next(h, src, transition),
        }
    }

    fn transitions<'a>(&'a self, src: N) -> Option<Cow<'a, [T]>> {
        match &self.headers {
            Headers::U8(h) => self._transitions(h, src),
            Headers::U16(h) => self._transitions(h, src),
            Headers::U32(h) => self._transitions(h, src),
            Headers::U64(h) => self._transitions(h, src),
        }
    }

    fn name(&self) -> &str {
        "FastHashDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += match &self.headers {
            Headers::U8(h) => h.capacity() * std::mem::size_of::<Header<u8, T>>(),
            Headers::U16(h) => h.capacity() * std::mem::size_of::<Header<u16, T>>(),
            Headers::U32(h) => h.capacity() * std::mem::size_of::<Header<u32, T>>(),
            Headers::U64(h) => h.capacity() * std::mem::size_of::<Header<u64, T>>(),
        };
        mem += self.tokens.capacity() * std::mem::size_of::<T>();
        mem += self.targets.capacity() * std::mem::size_of::<N>();
        mem += self.index.capacity() * std::mem::size_of::<u64>();

        mem
    }
}


/*
 * How hash() works under the hood?
 *
 * What is this magical number the hash algorithm multiplies with?
 *
 * It is the golden ratio scaled into the integer space.
 *
 * `ϕ = 1.618033988749...`
 *
 * Scaling this down into 32 bit space:
 *
 * `2^32 / ϕ = 2654435769.498698323...`
 *
 * Cut off the fractions and the result is `0x9E3779B9` in hexadecimal (for 32 bit space).
 *
 * Why is this beneficial?
 *
 * 1.
 *
 * In hash algorithms, it is desirable to distribute outputs as uniformly as possible.
 * If token IDs were not scattered, they would not use the memory section evenly,
 * increasing the possibility of a collision (which is expensive).
 *
 * 2.
 *
 * Because the maximum size of a section is always `2^N`, it is important to
 * scale with a number `a` where `GCD(a, 2) = 1`; thus, `a` must be an odd number.
 *
 * Why is this important?
 *
 * E.g. a section size is 2^3 = 8, so its mask is 7 = 0111b.
 *
 * Try with `a = 2` where `GCD(2, 2) = 2`.
 *
 * ```
 * token => (token * a) & mask
 *
 * 0 =>  0 & 7 = 00000 & 00111 = 0
 * 1 =>  2 & 7 = 00010 & 00111 = 2
 * 2 =>  4 & 7 = 00100 & 00111 = 4
 * 3 =>  6 & 7 = 00110 & 00111 = 6
 * 4 =>  8 & 7 = 01000 & 00111 = 0 Collision!
 * 5 => 10 & 7 = 01010 & 00111 = 2 Collision!
 * 6 => 12 & 7 = 01100 & 00111 = 4 Collision!
 * 7 => 14 & 7 = 01110 & 00111 = 6 Collision!
 * ```
 *
 * Try with `a = 3` where `GCD(3, 2) = 1`.
 *
 * ```
 * token => (token * a) & mask
 *
 * 0 =>  0 & 7 = 00000 & 00111 = 0
 * 1 =>  3 & 7 = 00011 & 00111 = 3
 * 2 =>  6 & 7 = 00110 & 00111 = 6
 * 3 =>  9 & 7 = 01001 & 00111 = 1
 * 4 => 12 & 7 = 01100 & 00111 = 4
 * 5 => 15 & 7 = 01111 & 00111 = 7
 * 6 => 18 & 7 = 10010 & 00111 = 2
 * 7 => 21 & 7 = 10101 & 00111 = 5
 * ```
 *
 * No collisions within the section size!
 *
 * As `ax ≡ 1 (mod m)`,
 * if `x <= m` and `GCD(a, m) = 1`,
 * it reshuffles numbers between [0, m) without overlaps.
 */

#[inline(always)]
fn hash<N: Number>(n: N, mask: N) -> N {
    return n.wrapping_mul(N::GOLDEN_RATIO) & mask
}
