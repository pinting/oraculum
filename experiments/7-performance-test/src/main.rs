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

struct FlatDFA {
    offsets: Vec<u32>,
    edges: Vec<(TokenId, NodeId)>,
}

impl FlatDFA {
    fn new(transitions: &[(NodeId, TokenId, NodeId)], nodes_count: u32) -> Self {
        let mut transitions: Vec<(NodeId, TokenId, NodeId)> = transitions.to_vec();

        transitions.sort_unstable_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));

        let mut offsets = vec![0; (nodes_count + 2) as usize];
        let mut edges = Vec::with_capacity(transitions.len());

        let mut c = 0; 
        let mut idx = 0;

        for (src, token, target) in &transitions {
            while c < (*src as usize) {
                c += 1;
                offsets[c] = idx;
            }

            edges.push((*token, *target));

            idx += 1;
        }

        while c < nodes_count as usize {
            c += 1;
            offsets[c] = idx;
        }

        Self { offsets, edges }
    }
}

impl DFA for FlatDFA {
    #[inline(always)]
    fn lookup(&self, src: NodeId, token: TokenId) -> Option<NodeId> {
        let idx = src as usize;

        if idx + 1 >= self.offsets.len() {
            return None;
        }

        let start = self.offsets[idx] as usize;
        let end = self.offsets[idx + 1] as usize;

        if start == end {
            return None;
        }

        let slice = &self.edges[start..end];

        slice.binary_search_by_key(&token, |e| e.0)
            .ok()
            .map(|i| slice[i].1)
    }

    fn transitions(&self, node: NodeId) -> u128 {
        let idx = node as usize;
        let mut sum = 0;

        if idx + 1 < self.offsets.len() {
            let start = self.offsets[idx] as usize;
            let end = self.offsets[idx + 1] as usize;

            for edge in &self.edges[start..end] {
                sum += edge.0 as u128;
            }
        }
        sum
    }

    fn name(&self) -> &str {
        "FlatDFA"
    }

    fn memory_usage(&self) -> usize {
        std::mem::size_of::<Self>()
            + self.offsets.capacity() * std::mem::size_of::<NodeId>()
            + self.edges.capacity() * std::mem::size_of::<(TokenId, NodeId)>()
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
        Box::new(FlatDFA::new(&transitions, nodes_count as u32)),
        Box::new(HybridDFA::new(&transitions, nodes_count as u32)),
    ];

    let mut prev_checksum: Option<u128> = None;
    let mut results = Vec::new();

    for dfa in &dfas {
        let (lookup_duration, scan_duration, checksum) = 
            benchmark_dfa(dfa.as_ref(), &test_transitions, nodes_count, lookup_count, scan_count);
        
        if let Some(prev_checksum) = prev_checksum {
            if prev_checksum != checksum {
                println!("Checksum MISMATCH!");
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

    let nodes_count = 5_000;
    let links = 250_000;

    benchmark(nodes_count, links, vocabulary_size, lookup_count, scan_count);
}