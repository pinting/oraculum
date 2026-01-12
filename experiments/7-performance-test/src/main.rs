use std::time::{Duration, Instant};
use rand::Rng;
use rand::rngs::ThreadRng;
use rand::seq::SliceRandom;

mod number;
mod dfa;
mod flatdfa;
mod doublehashdfa;
mod hybriddfa;
mod fasthashdfa;

use crate::flatdfa::FlatDFA;
use crate::number::Number;
use crate::dfa::DFA;
use crate::doublehashdfa::DoubleHashDFA;
use crate::hybriddfa::HybridDFA;
use crate::fasthashdfa::FastHashDFA;

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
        Box::new(DoubleHashDFA::new(&transitions)),
        Box::new(FlatDFA::<N, T, u32>::new(&transitions, nodes_count)),
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