use rustc_hash::{FxHashMap as HashMap};
use std::borrow::Cow;

use crate::Number;
use crate::dfa::dfa::DFA;

#[derive(Copy, Clone)]
struct Header<O, T> {
    data_offset: O,
    index_offset: O,
    section_mask: T,
    unit_size: u8,
}

pub struct FastHashDFA<N, T, O> {
    headers: Vec<Header<O, T>>,
    tokens: Vec<T>,
    targets: Vec<N>,
    index: Vec<u64>,
}

impl<N, T, O> DFA<N, T> for FastHashDFA<N, T, O>
where N: Number, T: Number, O: Number {
       fn new(m: HashMap<N, HashMap<T, N>>, nodes_count: usize) -> Self {
        let mut transitions: Vec<(N, T, N)> = Vec::with_capacity(
            m.values().map(|x| x.len()).sum());
        
        for (src, targets) in m {
            for (token, target) in targets {
                transitions.push((src, token, target));
            }
        }
        
        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut headers = Vec::with_capacity(nodes_count);
        let mut tokens = Vec::with_capacity(transitions.len());
        let mut targets = Vec::with_capacity(transitions.len());
        
        let mut idx = 0;
        let mut slots_count = 0; 

        for node in 0..nodes_count {
            let node = N::from_usize(node);
            let data_offset = tokens.len();

            while idx < transitions.len() && transitions[idx].0 == node {
                let (_, token, target) = transitions[idx];

                tokens.push(token);
                targets.push(target);

                idx += 1;
            }
            
            let data_count = tokens.len() - data_offset;

            if data_count == 0 {
                headers.push(Header {
                    data_offset: O::from_usize(0),
                    index_offset: O::from_usize(0),
                    section_mask: T::from_usize(0),
                    unit_size: 0,
                });

                continue;
            }

            let section_size = (data_count * 2).next_power_of_two().max(4);
            let section_mask = section_size - 1; 

            let unit_size: u8 = if section_size < u8::MAX as usize {
                8
            } else if section_size < u16::MAX as usize {
                16
            } else if section_size < u32::MAX as usize {
                32
            } else if section_size < u64::MAX as usize {
                64
            } else {
                panic!("Section size is too large!");
            };

            let bytes = section_size * (unit_size as usize / 8);
            let slots = (bytes + 7) / 8; // Round up to nearest u64 slot
            let index_offset = slots_count;

            slots_count += slots;

            headers.push(Header {
                data_offset: O::from_usize(data_offset),
                index_offset: O::from_usize(index_offset),
                section_mask: T::from_usize(section_mask),
                unit_size,
            });
        }
        
        let mut index = vec![u64::MAX; slots_count];

        fn insert<S, N, T>(
            transitions: &[(N, T, N)], 
            index_ptr: &mut [u64], 
            index_offset: usize, 
            data_start: usize, 
            data_count: usize, 
            section_mask: usize
        ) 
        where 
            S: Number, 
            N: Number, 
            T: Number 
        {
            let base_ptr = unsafe { (index_ptr.as_mut_ptr() as *mut u64).add(index_offset) as *mut S };
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

        for node in 0..nodes_count {
            let header = match headers.get(node) {
                Some(&h) => h,
                None => panic!("Headers out of bounds!"),
            };

            if header.unit_size == 0 { continue; }

            let data_start = header.data_offset.to_usize();
            let data_next_start = match headers.get(node + 1) {
                Some(h) => h.data_offset.to_usize(),
                None => tokens.len(),
            };

            let data_count = data_next_start - data_start;
            let index_offset = header.index_offset.to_usize();
            let section_mask = header.section_mask.to_usize();

            match header.unit_size {
                8 => insert::<u8, N, T>(&transitions, &mut index, index_offset, data_start, data_count,  section_mask),
                16 => insert::<u16, N, T>(&transitions, &mut index, index_offset, data_start, data_count, section_mask),
                32 => insert::<u32, N, T>(&transitions, &mut index, index_offset, data_start, data_count, section_mask),
                64 => insert::<u64, N, T>(&transitions, &mut index, index_offset, data_start, data_count, section_mask),
                _ => unreachable!("Invalid unit size"),
            }
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
        let src = src.to_usize();
        let header = self.headers.get(src)?;
        
        if header.unit_size == 0 {
            panic!("Invalid unit size was set!")
        }

        let index_offset = header.index_offset.to_usize();
        let section_mask = header.section_mask;
        
        fn search<S, N, T>(
            index_ptr: *const u64, 
            index_offset: usize,
            data_offset: usize,
            section_mask: T,
            token: T,
            tokens: &[T],
            targets: &[N]
        ) -> Option<N>
        where 
            S: Number,
            N: Number,
            T: Number 
        {
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

        let index_ptr = self.index.as_ptr();
        let data_offset = header.data_offset.to_usize();

        match header.unit_size {
             8 => search::<u8, N, T>(index_ptr, index_offset, data_offset, section_mask, transition, &self.tokens, &self.targets),
            16 => search::<u16, N, T>(index_ptr, index_offset, data_offset, section_mask, transition, &self.tokens, &self.targets),
            32 => search::<u32, N, T>(index_ptr, index_offset, data_offset, section_mask, transition, &self.tokens, &self.targets),
            64 => search::<u64, N, T>(index_ptr, index_offset, data_offset, section_mask, transition, &self.tokens, &self.targets),
             _ => unreachable!("Invalid unit size"),
        }
    }

    fn transitions<'a>(&'a self, src: N) -> Option<Cow<'a, [T]>> {
        let node = src.to_usize();

        let header = self.headers.get(node)?;

        let start = header.data_offset.to_usize();
        let end = match self.headers.get(node + 1) {
            Some(h) => h.data_offset.to_usize(),
            None => self.tokens.len(),
        };

        if start == end {
            return None
        }

        Some(Cow::Borrowed(&self.tokens[start..end]))
    }

    fn name(&self) -> &str {
        "FastHashDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.headers.capacity() * std::mem::size_of::<Header<O, T>>();
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