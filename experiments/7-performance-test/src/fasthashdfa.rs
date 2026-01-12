use std::borrow::Cow;

use crate::number::Number;
use crate::dfa::DFA;

#[derive(Copy, Clone)]
struct Header<O, T> {
    data_offset: O,
    index_offset: O,
    section_mask: T,
}

pub struct FastHashDFA<N, T, O, I> {
    headers: Vec<Header<O, T>>, // N = nodes_count
    tokens: Vec<T>,
    targets: Vec<N>,
    index: Vec<I>,
}

impl<N, T, O, I> FastHashDFA<N, T, O, I>
where N: Number, T: Number, O: Number, I: Number {
    pub fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
        let mut transitions = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut headers = Vec::with_capacity(nodes_count);
        let mut tokens = Vec::with_capacity(transitions.len());
        let mut targets = Vec::with_capacity(transitions.len());
        
        let mut idx = 0;
        let mut index_size = 0;

        // Iterate over the nodes to fill up headers, tokens and targets
        // and calculate the size of the index.
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
                let header = Header{
                    data_offset: O::from_usize(0),
                    index_offset: O::from_usize(0),
                    section_mask: T::from_usize(0),
                };

                headers.push(header);

                continue
            }

            // While data count equals with the actual length of the data section,
            // the index section needs room to reduce the number of hash collisions.
            // Keeping the size 2^N is required to replace the expensive modulo
            // operation with bit masking.
            let section_size = (data_count * 2).next_power_of_two().max(4);

            // The section size is a single 1 bit at position N.
            // So the subtraction of 1 = 0001b will result in flipping the bits 
            // between [0, N], creating a mask where the first 0 bit is at N.
            let section_mask = section_size - 1; 

            let index_offset = index_size;
            
            index_size += section_size;

            let header = Header{
                data_offset: O::from_usize(data_offset),
                index_offset: O::from_usize(index_offset),
                section_mask: T::from_usize(section_mask),
            };

            headers.push(header);
        }
        
        // Create the index
        let mut index = vec![I::max_value(); index_size];

        // Iterate over the nodes once again to fill the index
        for node in 0..nodes_count {
            let node = node as usize;

            let header = match headers.get(node) {
                Some(&header) => header,
                None => panic!("Headers out of bounds!"),
            };
            
            let Header {data_offset, index_offset, section_mask } = header;

            let start = data_offset.to_usize();
            let end = match headers.get(node + 1) {
                Some(header) => header.data_offset.to_usize(),
                None => transitions.len(),
            };

            let count = end - start;

            for i in 0..count {
                let idx = (start + i) as usize;
                let (_, token, _) = match transitions.get(idx) {
                    Some(&t) => t,
                    None => panic!("Transitions out of bounds!"),
                };

                let mut h = hash(token, section_mask);
                
                loop {
                    let p = index_offset.to_usize() + h.to_usize();

                    if index[p] == I::max_value() {
                        index[p] = I::from_usize(i);

                        break;
                    }

                    h = (h + T::from_usize(1)) & section_mask;
                }
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

impl<N, T, O, I> DFA<N, T> for FastHashDFA<N, T, O, I>
where N: Number, T: Number, O: Number, I: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        let src = src.to_usize();
        
        let header = self.headers.get(src)?;
        let Header { data_offset, index_offset, section_mask } = *header;

        let mut h = hash(token, section_mask);

        loop {
            // Unsafe access is used here for maximum performance.
            // Bounds checks are omitted because `h` is masked by `section_mask` 
            // which guarantees it falls within the allocated section size for this node.
            let p = index_offset.to_usize() + h.to_usize();
            let i = unsafe { *self.index.get_unchecked(p) };

            if i == I::max_value() {
                return None;
            }

            let idx = data_offset.to_usize() + i.to_usize();
            let candidate = unsafe { *self.tokens.get_unchecked(idx) };

            if candidate == token {
                return Some(unsafe { *self.targets.get_unchecked(idx) });
            }

            h = (h + T::from_usize(1)) & section_mask;
        }
    }

    fn transitions<'a>(&'a self, node: N) -> Option<Cow<'a, [T]>> {
        let node = node.to_usize();

        let header = self.headers.get(node)?;
        let Header { data_offset, .. } = *header;
        
        let start = data_offset.to_usize();
        let end = match self.headers.get(node + 1) {
            Some(header) => header.data_offset.to_usize(),
            None => self.tokens.len(),
        };

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
        mem += self.index.capacity() * std::mem::size_of::<I>();

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