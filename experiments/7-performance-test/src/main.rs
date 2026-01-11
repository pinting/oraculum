use rustc_hash::{FxHashMap as HashMap};
use std::time::{Duration, Instant};
use rand::Rng;
use rand::rngs::ThreadRng;
use rand::seq::SliceRandom;

type TokenId = u32;
type NodeId = u16;

trait DFA {
    fn lookup(&self, src: NodeId, token: TokenId) -> Option<NodeId>;
    fn transitions(&self, node: NodeId) -> u128;
    fn name(&self) -> &str;
    fn memory_usage(&self) -> usize;
}

struct DoubleHashDFA {
    map: HashMap<NodeId, HashMap<TokenId, NodeId>>,
}

impl DoubleHashDFA {
    fn new(transitions: &[(NodeId, TokenId, NodeId)]) -> Self {
        let mut map: HashMap<NodeId, HashMap<TokenId, NodeId>> = HashMap::default();

        for &(src, token, target) in transitions {
            map.entry(src).or_default().insert(token, target);
        }

        Self { map }
    }
}

impl DFA for DoubleHashDFA {
    #[inline(always)]
    fn lookup(&self, src: NodeId, token: TokenId) -> Option<NodeId> {
        self.map.get(&src).and_then(|m| m.get(&token)).copied()
    }

    fn transitions(&self, node: NodeId) -> u128 {
        let mut sum = 0;

        if let Some(inner) = self.map.get(&node) {
            for &token in inner.keys() {
                sum += token as u128;
            }
        }
        
        sum
    }

    fn name(&self) -> &str {
        "DoubleHashDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();
        mem += self.map.capacity() * (std::mem::size_of::<NodeId>() + std::mem::size_of::<HashMap<TokenId, NodeId>>() + 1);

        for inner in self.map.values() {
            mem += inner.capacity() * (std::mem::size_of::<TokenId>() + std::mem::size_of::<NodeId>() + 1);
        }
        mem
    }
}

struct HybridDFA {
    offsets: Vec<u32>,
    tokens: Vec<TokenId>,
    targets: Vec<HashMap<TokenId, NodeId>>,
}

impl HybridDFA {
    fn new(transitions: &[(NodeId, TokenId, NodeId)], nodes_count: u32) -> Self {
        let mut targets = vec![HashMap::default(); nodes_count as usize];

        let mut transitions = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut offsets = vec![0; (nodes_count + 2) as usize];
        let mut tokens = Vec::with_capacity(transitions.len());

        let mut c = 0;
        let mut idx = 0;

        for (src, token, target) in transitions {
            if let Some(map) = targets.get_mut(src as usize) {
                map.insert(token, target);
            }

            while c < (src as usize) {
                c += 1;
                offsets[c] = idx;
            }

            tokens.push(token);
            idx += 1;
        }

        while c < nodes_count as usize {
            c += 1;
            offsets[c] = idx;
        }

        Self { targets, offsets, tokens }
    }
}

impl DFA for HybridDFA {
    #[inline(always)]
    fn lookup(&self, src: NodeId, token: TokenId) -> Option<NodeId> {
        self.targets.get(src as usize)
            .and_then(|m| m.get(&token))
            .copied()
    }

    fn transitions(&self, node: NodeId) -> u128 {
        let idx = node as usize;
        let mut sum = 0;

        if idx + 1 < self.offsets.len() {
            let start = self.offsets[idx] as usize;
            let end = self.offsets[idx + 1] as usize;

            for &token in &self.tokens[start..end] {
                sum += token as u128;
            }
        }
        sum
    }

    fn name(&self) -> &str {
        "HybridDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.targets.capacity() * std::mem::size_of::<HashMap<TokenId, NodeId>>();
        for map in &self.targets {
            mem += map.capacity() * (std::mem::size_of::<TokenId>() + std::mem::size_of::<NodeId>() + 1);
        }

        mem += self.offsets.capacity() * std::mem::size_of::<NodeId>();
        mem += self.tokens.capacity() * std::mem::size_of::<TokenId>();

        mem
    }
}

struct FastHashDFA {
    headers: Vec<(/* data_offset: */ u32, /* index_offset: */ u32, /* section_mask: */ u32)>, // N = nodes_count
    tokens: Vec<TokenId>,
    targets: Vec<NodeId>,
    index: Vec<u32>,
}

impl FastHashDFA {
    #[inline(always)]
    fn hash(token: u32, mask: u32) -> u32 {
        /*
        * Why `0x9E3779B9`?
        *
        * It all comes down to the golden ratio ϕ and the modulo of odd numbers.
        *
        * `ϕ = 1.618033988749...`
        *
        * Scale this down into 32-bit integer space:
        *
        * `2^32 / ϕ = 2654435769.498698323...`
        *
        * Cut off the fractions, and the result is `0x9E3779B9` in hexadecimal.
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
        * E.g., a section size is 2^3 = 8, so its mask is 7 = 0111b.
        * 
        * Let's try with `a = 2` where `GCD(2, 2) = 2`.
        *
        * ```
        * token_id => (token_id * a) & mask
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
        * Let's try with `a = 3` where `GCD(3, 2) = 1`.
        *
        * ```
        * token_id => (token_id * a) & mask
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

        return token.wrapping_mul(0x9E3779B9) & mask
    }

    fn new(transitions: &[(NodeId, TokenId, NodeId)], max_node_id: u32) -> Self {
        let mut transitions = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut headers = Vec::with_capacity(max_node_id as usize);
        let mut tokens = Vec::with_capacity(transitions.len());
        let mut targets = Vec::with_capacity(transitions.len());
        
        let mut idx = 0;
        let mut index_size = 0;

        // Iterate over the nodes to fill up headers, tokens and targets
        // and calculate the size of the index.
        for node_id in 0..max_node_id {
            let node_id = node_id as NodeId;
            let data_offset = tokens.len();

            while idx < transitions.len() && transitions[idx].0 == node_id {
                let (_, token, target) = transitions[idx];

                tokens.push(token);
                targets.push(target);

                idx += 1;
            }
            
            let data_count = tokens.len() - data_offset;

            if data_count == 0 {
                headers.push((0, 0, 0));

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

            headers.push((data_offset as u32, index_offset as u32, section_mask as u32));
        }
        
        // Create the index
        let mut index = vec![u32::MAX; index_size];

        // Iterate over the nodes once again to fill the index
        for node_id in 0..max_node_id {
            let node_id = node_id as usize;

            let (start_idx, index_offset, section_mask) = match headers.get(node_id) {
                Some(&h) => h,
                None => panic!("Headers out of bounds!"),
            };

            let end_idx = match headers.get(node_id + 1) {
                Some(&h) => h.0,
                None => transitions.len() as u32,
            };

            let count = end_idx - start_idx;

            for i in 0..count {
                let idx = (start_idx + i) as usize;
                let (_, token, _) = match transitions.get(idx) {
                    Some(&t) => t,
                    None => panic!("Transitions out of bounds!"),
                };

                let i = i as u32;
                let mut h = FastHashDFA::hash(token, section_mask);
                
                loop {
                    let p = (index_offset + h) as usize;

                    if index[p] == u32::MAX {
                        index[p] = i;

                        break;
                    }

                    h = (h + 1) & section_mask;
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

impl DFA for FastHashDFA {
    #[inline(always)]
    fn lookup(&self, src: NodeId, token: TokenId) -> Option<NodeId> {
        let src = src as usize;
        
        let (data_offset, index_offset, section_mask) = match self.headers.get(src) {
            Some(&h) => h,
            None => return None,
        };

        if section_mask == 0 { return None; }

        let mut h = FastHashDFA::hash(token, section_mask) as usize;
        let index_offset = index_offset as usize;

        loop {
            // Unsafe access is used here for maximum performance.
            // Bounds checks are omitted because `h` is masked by `section_mask` 
            // which guarantees it falls within the allocated section size for this node.
            let p = index_offset + h;
            let i = unsafe { *self.index.get_unchecked(p) };

            if i == u32::MAX {
                return None;
            }

            let idx = (data_offset as usize) + (i as usize);
            let candidate = unsafe { *self.tokens.get_unchecked(idx) };

            if candidate == token {
                return Some(unsafe { *self.targets.get_unchecked(idx) });
            }

            h = (h + 1) & section_mask as usize;
        }
    }

    fn transitions(&self, node: NodeId) -> u128 {
        let mut checksum = 0;
        let idx = node as usize;

        if let Some(&(start, _, _)) = self.headers.get(idx) {
            let end = if idx + 1 < self.headers.len() {
                self.headers[idx + 1].0
            } else {
                self.tokens.len() as u32
            };

            for &token in &self.tokens[start as usize..end as usize] {
                checksum += token as u128;
            }
        }

        checksum
    }

    fn name(&self) -> &str {
        "FastHashDFA"
    }

    fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.headers.capacity() * std::mem::size_of::<(u32, u32, u32)>();
        mem += self.tokens.capacity() * std::mem::size_of::<TokenId>();
        mem += self.targets.capacity() * std::mem::size_of::<NodeId>();
        mem += self.index.capacity() * std::mem::size_of::<u32>();

        mem
    }
}

fn benchmark_dfa(
    dfa: &dyn DFA,
    transitions: &[(NodeId, TokenId, NodeId)], 
    nodes_count: usize, 
    lookup_count: usize,
    scan_count: usize,
) -> (Duration, Duration, u128) {
    let mut checksum: u128 = 0;

    let start = Instant::now();
    let mut i = lookup_count;

    'outer: loop {
        for &(src, token, _) in transitions {
            if let Some(target) = dfa.lookup(src, token) {
                checksum += target as u128;
            }

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
        for node_id in 0..nodes_count {
            checksum += dfa.transitions(node_id as NodeId);

            if i == 0 {
                break 'outer
            }

            i -= 1
        }
    }

    let scan_duration = start.elapsed();
    
    (lookup_duration, scan_duration, checksum)
}

fn benchmark(nodes_count: usize, links_count: usize, vocabulary_size: u32, lookup_count: usize, scan_count: usize) {
    println!("Benchmarking with nodes_count = {}, links_count = {}, vocabulary_size = {}, lookup_count = {}, scan_count = {}", 
        nodes_count, links_count, vocabulary_size, lookup_count, scan_count);
    
    println!("Generating...");

    let mut rng = ThreadRng::default();
    let mut tokens: Vec<TokenId> = (0..vocabulary_size).collect();
    let mut transitions: Vec<(NodeId, TokenId, NodeId)> = Vec::new();

    for src in 0..nodes_count {
        let src = src as NodeId;

        tokens.shuffle(&mut rng);

        let selected_tokens = &tokens[0..links_count];

        for &token in selected_tokens {
            let target = rng.random_range(0..nodes_count) as NodeId;

            transitions.push((src, token, target));
        }
    }

    let mut test_transitions = transitions.clone();

    test_transitions.shuffle(&mut rng);

    println!("Generated {} edges", transitions.len());

    let dfas: Vec<Box<dyn DFA>> = vec![
        Box::new(DoubleHashDFA::new(&transitions)),
        Box::new(HybridDFA::new(&transitions, nodes_count as u32)),
        Box::new(FastHashDFA::new(&transitions, nodes_count as u32)),
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

    let nodes_count = 200;
    let links = 50;

    benchmark(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 200;
    let links = 100;

    benchmark(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let links = 1_000;

    benchmark(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let links = 10_000;

    benchmark(nodes_count, links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let links = 100_000;

    benchmark(nodes_count, links, vocabulary_size, lookup_count, scan_count);
}