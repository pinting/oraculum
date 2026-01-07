use std::collections::BTreeMap;
use rustc_hash::{FxHashMap as HashMap};
use std::time::{Duration, Instant};
use rand::Rng;
use rand::rngs::ThreadRng;
use rand::seq::SliceRandom;

type TokenId = u32;
type NodeId = u32;

trait DFA {
    fn lookup(&self, src: NodeId, token: TokenId) -> Option<NodeId>;
    fn transitions(&self, node: NodeId) -> u128;
    fn name(&self) -> &str;
}

struct HashBTreeDFA {
    map: HashMap<NodeId, BTreeMap<TokenId, NodeId>>,
}

impl HashBTreeDFA {
    fn new(transitions: &[(NodeId, TokenId, NodeId)]) -> Self {
        let mut map: HashMap<NodeId, BTreeMap<TokenId, NodeId>> = HashMap::default();

        for &(src, token, target) in transitions {
            map.entry(src).or_default().insert(token, target);
        }

        Self { map }
    }
}

impl DFA for HashBTreeDFA {
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
        "HashBTreeDFA"
    }
}

struct DoubleBTreeDFA {
    map: BTreeMap<NodeId, BTreeMap<TokenId, NodeId>>,
}

impl DoubleBTreeDFA {
    fn new(transitions: &[(NodeId, TokenId, NodeId)]) -> Self {
        let mut map: BTreeMap<NodeId, BTreeMap<TokenId, NodeId>> = BTreeMap::new();

        for &(src, token, target) in transitions {
            map.entry(src).or_default().insert(token, target);
        }

        Self { map }
    }
}

impl DFA for DoubleBTreeDFA {
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
        "DoubleBTreeDFA"
    }
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
}

#[derive(Debug, Clone, Copy)]
struct FlatEdge {
    token: TokenId,
    target: NodeId,
}

struct FlatDFA {
    offsets: Vec<u32>,
    edges: Vec<FlatEdge>,
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

            let edge = FlatEdge { token: *token, target: *target };

            edges.push(edge);

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

        slice.binary_search_by_key(&token, |e| e.token)
            .ok()
            .map(|i| slice[i].target)
    }

    fn transitions(&self, node: NodeId) -> u128 {
        let idx = node as usize;
        let mut sum = 0;

        if idx + 1 < self.offsets.len() {
            let start = self.offsets[idx] as usize;
            let end = self.offsets[idx + 1] as usize;

            for edge in &self.edges[start..end] {
                sum += edge.token as u128;
            }
        }
        sum
    }

    fn name(&self) -> &str {
        "FlatDFA"
    }
}

fn benchmark_dfa(
    dfa: &dyn DFA,
    transitions: &[(NodeId, TokenId, NodeId)], 
    nodes_count: u32, 
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
        for node in 0..nodes_count {
            checksum += dfa.transitions(node);

            if i == 0 {
                break 'outer
            }

            i -= 1
        }
    }

    let scan_duration = start.elapsed();
    
    (lookup_duration, scan_duration, checksum)
}

fn benchmark(nodes_count: u32, min_links: u32, max_links: u32, vocabulary_size: u32, lookup_count: u32, scan_count: usize) {
    println!("Benchmarking with nodes_count = {}, min_links = {}, max_links = {}, vocabulary_size = {}, lookup_count = {}, scan_count = {}", 
        nodes_count, min_links, max_links, vocabulary_size, lookup_count, scan_count);
    
    println!("Generating...");

    let mut rng = ThreadRng::default();
    let mut tokens: Vec<TokenId> = (0..vocabulary_size).collect();
    let mut transitions: Vec<(NodeId, TokenId, NodeId)> = Vec::new();

    for src in 0..nodes_count {
        let links_count = rng.random_range(min_links..=max_links);

        tokens.shuffle(&mut rng);

        let selected_tokens = &tokens[0..(links_count as usize)];

        for &token in selected_tokens {
            let target = rng.random_range(0..nodes_count);

            transitions.push((src, token, target));
        }
    }

    let mut test_transitions = transitions.clone();

    test_transitions.shuffle(&mut rng);

    println!("Generated {} edges", transitions.len());

    let nested_btree_dfa = HashBTreeDFA::new(&transitions);
    let double_btree_dfa = DoubleBTreeDFA::new(&transitions);
    let nested_dfa = DoubleHashDFA::new(&transitions);
    let flat_dfa = FlatDFA::new(&transitions, nodes_count);

    let dfas: Vec<&dyn DFA> = vec![&nested_btree_dfa, &double_btree_dfa, &nested_dfa, &flat_dfa];

    let mut prev_checksum: Option<u128> = None;
    let mut results = Vec::new();

    for dfa in dfas {
        let (lookup_duration, scan_duration, checksum) = 
            benchmark_dfa(dfa, &test_transitions, nodes_count, lookup_count as usize, scan_count);
        
        if let Some(prev_checksum) = prev_checksum {
            if prev_checksum != checksum {
                println!("Checksum MISMATCH!");
            }
        }

        prev_checksum = Some(checksum);
        results.push((dfa.name(), lookup_duration, scan_duration));
    }

    let mut lookup_results = results.clone();

    lookup_results.sort_by_key(|r| r.1);

    println!("Lookup placements:");

    for (name, duration, _) in lookup_results {
        println!("\t{} - {:?}", name, duration);
    }

    let mut scan_results = results;

    scan_results.sort_by_key(|r| r.2);

    println!("Scan placements:");

    for (name, _, duration) in scan_results {
        println!("\t{} - {:?}", name, duration);
    }
}

fn main() {
    let vocabulary_size = 256_000;

    let lookup_count = 2_500;
    let scan_count = 2_500;

    let nodes_count = 200;
    let min_links = 50;
    let max_links = 100;

    benchmark(nodes_count, min_links, max_links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let min_links = 500;
    let max_links = 1_000;

    benchmark(nodes_count, min_links, max_links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let min_links = 5_000;
    let max_links = 10_000;

    benchmark(nodes_count, min_links, max_links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 2_000;
    let min_links = 50_000;
    let max_links = 100_000;

    benchmark(nodes_count, min_links, max_links, vocabulary_size, lookup_count, scan_count);

    let nodes_count = 5_000;
    let min_links = 200_000;
    let max_links = 250_000;

    benchmark(nodes_count, min_links, max_links, vocabulary_size, lookup_count, scan_count);
}