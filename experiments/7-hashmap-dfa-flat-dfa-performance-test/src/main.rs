use std::collections::HashMap;
use std::time::Instant;
use rand::Rng;
use rand::rngs::ThreadRng; 
use rand::seq::SliceRandom;

type TokenId = u32;
type NodeId = u32;

// 1. HashMap based DFA approach

type HashDFA = HashMap<(NodeId, TokenId), NodeId>;

// 2. Flat array based DFA approach

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
    #[inline(always)]
    fn next_state(&self, current: NodeId, token: TokenId) -> Option<NodeId> {
        let idx = current as usize;

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
}

fn main() {
    let nodes_count = 200;
    let min_links = 50;
    let max_links = 100;
    let vocabulary_size = 256_000;

    println!("Generating...");

    let mut rng = ThreadRng::default();
    let mut tokens: Vec<TokenId> = (0..vocabulary_size).collect();
    let mut transitions: Vec<(NodeId, TokenId, NodeId)> = Vec::new();

    for src in 0..nodes_count {
        let links_count = rng.random_range(min_links..=max_links);

        tokens.shuffle(&mut rng);

        let selected_tokens = &tokens[0..links_count];

        for &token in selected_tokens {
            let target = rng.random_range(0..nodes_count);

            transitions.push((src, token, target));
        }
    }

    let mut checksum: u128 = 0;
    let mut test_transitions = transitions.clone();

    test_transitions.shuffle(&mut rng);

    println!("Number of generated edges: {}", transitions.len());

    // 1. HashMap based DFA approach

    let mut hash_dfa: HashDFA = HashMap::new();
    
    for &(src, token, target) in &transitions {
        hash_dfa.insert((src, token), target);
    }

    println!("1. Hash based DFA");

    let start = Instant::now();
    let iterations = 10_000_000;
    
    for i in 0..iterations {
        let (src, token, _) = test_transitions[i % test_transitions.len()];
        
        if let Some(target) = hash_dfa.get(&(src, token)) {
            checksum += *target as u128;
        }
    }

    let duration = start.elapsed();

    println!("Time for 10 million lookups: {:?}", duration);
    println!("ns per lookup: {:.2} ns", (duration.as_nanos() as f64) / (iterations as f64));

    // 2. Flat Vector DFA
    
    transitions.sort_unstable_by(|a, b| {
        a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1))
    });

    let mut offsets: Vec<NodeId> = vec![0; (nodes_count + 2) as usize];
    let mut edges: Vec<FlatEdge> = Vec::with_capacity(transitions.len());
    
    let mut i = 0;
    let mut c = 0;

    for (src, token, target) in &transitions {
        while i < (*src as usize) {
            i += 1;
            offsets[i] = c;
        }

        let edge = FlatEdge { token: *token, target: *target };

        edges.push(edge);

        c += 1;
    }
    
    while i < nodes_count as usize {
        i += 1;
        offsets[i] = c;
    }

    let flat_dfa = FlatDFA { offsets, edges };

    println!("2. Flat Vector DFA");

    let start = Instant::now();
    
    for i in 0..iterations {
        let (src, token, _) = test_transitions[i % test_transitions.len()];
        
        if let Some(target) = flat_dfa.next_state(src, token) {
            checksum -= target as u128;
        }
    }

    let duration = start.elapsed();

    println!("Time for 10M lookups: {:?}", duration);
    println!("ns per lookup: {:.2} ns", (duration.as_nanos() as f64) / (iterations as f64));
    println!("Checksum: {}", checksum);
}