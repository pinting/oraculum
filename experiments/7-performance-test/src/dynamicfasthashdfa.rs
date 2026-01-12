use std::borrow::Cow;

use crate::number::Number;
use crate::dfa::DFA;

#[derive(Copy, Clone)]
struct Header<O, T> {
    data_offset: O,
    index_offset: O,
    section_mask: T,
    unit_size: u8,
}

pub struct DynamicFastHashDFA<N, T, O> {
    headers: Vec<Header<O, T>>,
    tokens: Vec<T>,
    targets: Vec<N>,
    index: Vec<u64>,
}

impl<N, T, O> DynamicFastHashDFA<N, T, O>
where N: Number, T: Number, O: Number {
    pub fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
        let mut transitions = transitions.to_vec();
        
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
}

impl<N, T, O> DFA<N, T> for DynamicFastHashDFA<N, T, O>
where N: Number, T: Number, O: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        let src = src.to_usize();
        let header = self.headers.get(src)?;
        
        if header.unit_size == 0 {
            panic!("Invalid unit size was set!")
        }

        let index_offset = header.index_offset.to_usize();
        let section_mask = header.section_mask;
        
        fn scan<S, N, T>(
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
             8 => scan::<u8, N, T>(index_ptr, index_offset, data_offset, section_mask, token, &self.tokens, &self.targets),
            16 => scan::<u16, N, T>(index_ptr, index_offset, data_offset, section_mask, token, &self.tokens, &self.targets),
            32 => scan::<u32, N, T>(index_ptr, index_offset, data_offset, section_mask, token, &self.tokens, &self.targets),
            64 => scan::<u64, N, T>(index_ptr, index_offset, data_offset, section_mask, token, &self.tokens, &self.targets),
             _ => unreachable!("Invalid unit size"),
        }
    }

    fn transitions<'a>(&'a self, node: N) -> Option<Cow<'a, [T]>> {
        let node = node.to_usize();

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
        "DynamicFastHashDFA"
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

#[inline(always)]
fn hash<N: Number>(n: N, mask: N) -> N {
    n.wrapping_mul(N::GOLDEN_RATIO) & mask
}