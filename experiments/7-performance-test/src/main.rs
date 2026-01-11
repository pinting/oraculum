use rustc_hash::{FxHashMap as HashMap};
use std::ops::{Add, BitAnd, Div, Mul, Sub};
use std::time::{Duration, Instant};
use rand::Rng;
use rand::rngs::ThreadRng;
use rand::seq::SliceRandom;
use std::fmt::Debug;
use std::hash::Hash;

trait Number: Copy + Clone + Debug + Hash + Eq + Ord + Sized 
    + Add<Output = Self> 
    + Sub<Output = Self> 
    + Mul<Output = Self> 
    + Div<Output = Self> 
    + BitAnd<Output = Self>
    + 'static 
{
    const GOLDEN_RATIO: Self;

    fn max_value() -> Self;
    fn from_usize(v: usize) -> Self;
    fn to_usize(self) -> usize;
    fn to_u128(self) -> u128;
    fn wrapping_mul(self, rhs: Self) -> Self;
}

/*
 * How fast_hash() operates?
 * 
 * Why the golden ratio is represented as a hexadecimal number?
 *
 * It all comes down to scaling it into the integer space.
 *
 * `ϕ = 1.618033988749...`
 *
 * Scaling this down into 32-bit integer space:
 *
 * `2^32 / ϕ = 2654435769.498698323...`
 *
 * Cut off the fractions and the result is `0x9E3779B9` in hexadecimal (for u32).
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
fn fast_hash<T: Number>(token: T, mask: T) -> T {
    return token.wrapping_mul(T::GOLDEN_RATIO) & mask
}

impl Number for u16 {
    const GOLDEN_RATIO: Self = 0x9E37;

    #[inline(always)] fn max_value() -> Self { u16::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn to_u128(self) -> u128 { self as u128 }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

impl Number for u32 {
    const GOLDEN_RATIO: Self = 0x9E3779B9;

    #[inline(always)] fn max_value() -> Self { u32::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn to_u128(self) -> u128 { self as u128 }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

impl Number for u64 {
    const GOLDEN_RATIO: Self = 0x9E3779B97F4A7C15;

    #[inline(always)] fn max_value() -> Self { u64::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn to_u128(self) -> u128 { self as u128 }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

trait DFA<N: Number, T: Number> {
    fn lookup(&self, src: N, token: T) -> Option<N>;
    fn transitions(&self, node: N) -> Option<Vec<T>>;
    fn name(&self) -> &str;
    fn memory_usage(&self) -> usize;
}

struct DoubleHashDFA<N, T> {
    map: HashMap<N, HashMap<T, N>>,
}

impl<N, T> DoubleHashDFA<N, T>
where N: Number, T: Number {
    fn new(transitions: &[(N, T, N)]) -> Self {
        let mut map: HashMap<N, HashMap<T, N>> = HashMap::default();

        for &(src, token, target) in transitions {
            map.entry(src).or_default().insert(token, target);
        }

        Self { map }
    }
}

impl<N, T> DFA<N, T> for DoubleHashDFA<N, T>
where N: Number, T: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        self.map.get(&src).and_then(|m| m.get(&token)).copied()
    }

    fn transitions(&self, node: N) -> Option<Vec<T>> {
        let inner = self.map.get(&node)?;

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

        mem += self.map.capacity() * (std::mem::size_of::<N>() + std::mem::size_of::<HashMap<T, N>>() + 1);

        for inner in self.map.values() {
            mem += inner.capacity() * (std::mem::size_of::<T>() + std::mem::size_of::<N>() + 1);
        }

        mem
    }
}

struct HybridDFA<N, T> {
    offsets: Vec<u32>,
    tokens: Vec<T>,
    targets: Vec<HashMap<T, N>>,
}

impl<N, T> HybridDFA<N, T>
where N: Number, T: Number {
    fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
        let mut targets = vec![HashMap::default(); nodes_count];

        let mut transitions = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut offsets = vec![0; nodes_count + 2];
        let mut tokens = Vec::with_capacity(transitions.len());

        let mut c = 0;
        let mut idx = 0;

        for (src, token, target) in transitions {
            if let Some(map) = targets.get_mut(src.to_usize()) {
                map.insert(token, target);
            }

            while c < src.to_usize() {
                c += 1;
                offsets[c] = idx;
            }

            tokens.push(token);
            idx += 1;
        }

        while c < nodes_count {
            c += 1;
            offsets[c] = idx;
        }

        Self { targets, offsets, tokens }
    }
}

impl<N, T> DFA<N, T> for HybridDFA<N, T>
where N: Number, T: Number {
    #[inline(always)]
    fn lookup(&self, src: N, token: T) -> Option<N> {
        self.targets.get(src.to_usize())
            .and_then(|m| m.get(&token))
            .copied()
    }

    fn transitions(&self, node: N) -> Option<Vec<T>> {
        let node = node.to_usize();

        if node + 1 >= self.offsets.len() {
            return None
        }

        let start = self.offsets[node] as usize;
        let end = self.offsets[node + 1] as usize;

        let mut result = Vec::new();

        for &token in &self.tokens[start..end] {
            result.push(token);
        }
        
        Some(result)
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

        mem += self.offsets.capacity() * std::mem::size_of::<N>();
        mem += self.tokens.capacity() * std::mem::size_of::<T>();

        mem
    }
}

#[derive(Copy, Clone)]
struct FastHashHeader<O, T> {
    data_offset: O,
    index_offset: O,
    section_mask: T,
}

struct FastHashDFA<N, T, O, I> {
    headers: Vec<FastHashHeader<O, T>>, // N = nodes_count
    tokens: Vec<T>,
    targets: Vec<N>,
    index: Vec<I>,
}

impl<N, T, O, I> FastHashDFA<N, T, O, I>
where N: Number, T: Number, O: Number, I: Number {
    fn new(transitions: &[(N, T, N)], nodes_count: usize) -> Self {
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
                let header = FastHashHeader{
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

            let header = FastHashHeader{
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
            
            let FastHashHeader {data_offset, index_offset, section_mask } = header;

            let start_idx = data_offset.to_usize();
            let end_idx = match headers.get(node + 1) {
                Some(header) => header.data_offset.to_usize(),
                None => transitions.len(),
            };

            let count = end_idx - start_idx;

            for i in 0..count {
                let idx = (start_idx + i) as usize;
                let (_, token, _) = match transitions.get(idx) {
                    Some(&t) => t,
                    None => panic!("Transitions out of bounds!"),
                };

                let mut h = fast_hash(token, section_mask);
                
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
        let FastHashHeader { data_offset, index_offset, section_mask } = *header;

        let mut h = fast_hash(token, section_mask);

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

    fn transitions(&self, node: N) -> Option<Vec<T>> {
        let node = node.to_usize();

        let header = self.headers.get(node)?;
        let FastHashHeader { data_offset, .. } = *header;
        
        let start_idx = data_offset.to_usize();
        let end_idx = match self.headers.get(node + 1) {
            Some(header) => header.data_offset.to_usize(),
            None => self.tokens.len(),
        };

        let mut result = Vec::new();

        for &token in &self.tokens[start_idx..end_idx] {
            result.push(token);
        }

        Some(result)
    }

    fn name(&self) -> &str {
        "FastHashDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.headers.capacity() * std::mem::size_of::<FastHashHeader<O, T>>();
        mem += self.tokens.capacity() * std::mem::size_of::<T>();
        mem += self.targets.capacity() * std::mem::size_of::<N>();
        mem += self.index.capacity() * std::mem::size_of::<I>();

        mem
    }
}

fn benchmark_dfa<N: Number, T: Number>(
    dfa: &dyn DFA<N, T>,
    transitions: &[(N, T, N)], 
    nodes_count: usize, 
    lookup_count: usize,
    scan_count: usize,
) -> (Duration, Duration, u128) {
    let mut checksum: u128 = 0;

    let start = Instant::now();
    let mut i = lookup_count;

    'outer: loop {
        for &(src, token, _) in transitions {
            let Some(target) = dfa.lookup(src, token) else {
                panic!("Unknown node was selected, this should not have happened!")
            };

            checksum += target.to_u128();

            if i == 0 {
                break 'outer;
            }

            i -= 1;
        }
    }


    let lookup_duration = start.elapsed();

    let start = Instant::now();
    let mut i = scan_count;

    'outer: loop {
        for node in 0..nodes_count {
            let Some(tokens) = dfa.transitions(N::from_usize(node)) else {
                panic!("Unknown node was selected, this should not have happened!")
            };

            for token in tokens.iter() {
                checksum += token.to_u128();
            }

            if i == 0 {
                break 'outer
            }

            i -= 1
        }
    }

    let scan_duration = start.elapsed();
    
    (lookup_duration, scan_duration, checksum)
}

fn benchmark<N: Number, T: Number>(nodes_count: usize, links_count: usize, vocabulary_size: u32, lookup_count: usize, scan_count: usize) {
    println!("Benchmarking with nodes_count = {}, links_count = {}, vocabulary_size = {}, lookup_count = {}, scan_count = {}", 
        nodes_count, links_count, vocabulary_size, lookup_count, scan_count);
    
    println!("Generating...");

    let mut rng = ThreadRng::default();
    let mut tokens: Vec<T> = (0..vocabulary_size).map(|x| T::from_usize(x as usize)).collect();
    let mut transitions: Vec<(N, T, N)> = Vec::new();

    for src in 0..nodes_count {
        let src = N::from_usize(src);

        tokens.shuffle(&mut rng);

        let selected_tokens = &tokens[0..links_count];

        for &token in selected_tokens {
            let target = N::from_usize(rng.random_range(0..nodes_count));

            transitions.push((src, token, target));
        }
    }

    let mut test_transitions = transitions.clone();

    test_transitions.shuffle(&mut rng);

    println!("Generated {} edges", transitions.len());

    let dfas: Vec<Box<dyn DFA<N, T>>> = vec![
        // Box::new(DoubleHashDFA::new(&transitions)),
        Box::new(HybridDFA::new(&transitions, nodes_count)),
        Box::new(FastHashDFA::<N, T, u32, u32>::new(&transitions, nodes_count)),
    ];

    let mut prev_checksum: Option<u128> = None;
    let mut results = Vec::new();

    for dfa in &dfas {
        let (lookup_duration, scan_duration, checksum) = 
            benchmark_dfa(dfa.as_ref(), &test_transitions, nodes_count, lookup_count, scan_count);
        
        if let Some(prev_checksum) = prev_checksum {
            if prev_checksum != checksum {
                println!("Checksum MISMATCH for {}", dfa.name());
            }
        }

        prev_checksum = Some(checksum);

        results.push((dfa.name(), lookup_duration, scan_duration, dfa.memory_usage()));
    }

    results.sort_by_key(|r| r.1);

    println!("Lookup placements:");

    for (name, duration, _, _) in &results {
        println!("\t{} - {:?}", name, duration);
    }

    results.sort_by_key(|r| r.2);

    println!("Scan placements:");

    for (name, _, duration, _) in &results {
        println!("\t{} - {:?}", name, duration);
    }

    results.sort_by_key(|r| r.3);

    println!("Memory placements:");
    
    for (name, _, _, size) in &results {
        println!("\t{} - {:.5} MB", name, (*size as f64) / (1024.0 * 1024.0));
    }
}

fn main() {
    let vocabulary_size = 256_000;

    let lookup_count = 100_000;
    let scan_count = 100_000;

    /*
    let nodes_count = 200;
    let links = 50;

    benchmark::<u16, u32>(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 200;
    let links = 100;

    benchmark::<u16, u32>(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let links = 1_000;

    benchmark::<u16, u32>(nodes_count, links, vocabulary_size, lookup_count, scan_count);
    */

    let nodes_count = 2_000;
    let links = 10_000;

    benchmark::<u16, u32>(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    /*
    let nodes_count = 2_000;
    let links = 100_000;

    benchmark::<u16, u32>(nodes_count, links, vocabulary_size, lookup_count, scan_count);
    */
}