use aho_corasick::AhoCorasickKind;
use std::error::Error;
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Instant;

mod number;
mod dfa;
mod index;
mod vocabulary;

use crate::dfa::fasthashdfa::FastHashDFA;
use crate::index::lattice::Lattice;
use crate::index::index::Index;
use crate::index::expression::Expression;
use crate::number::Number;
use crate::vocabulary::Vocabulary;

fn main() -> Result<(), Box<dyn Error>> {
    let now = Instant::now();
    let vocabulary = match Vocabulary::from_file_path("../vocabulary.tiktoken", 1u32) {
        Some(vocab) => Arc::new(vocab),
        None => {
            return Err("Failed to create vocabulary".into());
        }
    };

    println!("Vocabulary loaded in {:?}", now.elapsed());

    let now = Instant::now();
    let ac = match Lattice::<u16, u32>::base(AhoCorasickKind::ContiguousNFA, vocabulary.clone()) {
        Some(base) => base,
        None => {
            return Err("Failed to build AhoCorasick base".into());
        }
    };

    println!("Lattice base (AhoCorasick) built in {:?}", now.elapsed());

    let now = Instant::now();
    let toktrie = match Expression::<u16, u32, FastHashDFA<u16, u32>>::base(vocabulary.clone()) {
        Some(base) => base,
        None => {
            return Err("Failed to build TokTrie base".into());
        }
    };

    println!("Expression base (TokTrie) built in {:?}", now.elapsed());

    let mut indexes: Vec<Box<dyn Index<u16, u32>>> = Vec::new();

    println!("Creating indexes...");

    let now = Instant::now();
    let input = "Why ";
    let index = Lattice::new(input, vocabulary.clone(), &ac);

    indexes.push(Box::new(index));

    println!("Lattice '{}' created in {:?}", input, now.elapsed());

    let now = Instant::now();
    let input = "monday|tuesday|wednesday|thursday|friday";
    let index: Expression<u16, u32, FastHashDFA<u16, u32>> = match Expression::new(
        input,
        vocabulary.clone(),
        &toktrie,
    ) {
        Some(re) => re,
        None => {
            return Err(format!("Failed to create Expression index with data '{}'", input).into());
        }
    };

    indexes.push(Box::new(index));
    
    println!("Expression '{}' created in {:?}", input, now.elapsed());
    
    let now = Instant::now();
    let input = "?";
    let index = Lattice::new(input, vocabulary.clone(), &ac);

    indexes.push(Box::new(index));

    println!("Lattice '{}' created in {:?}", input, now.elapsed());

    for index in &indexes {
        println!("{} memory usage: {} bytes", index.name(), index.memory_usage());
    }

    if let Err(e) = demo(&indexes, vocabulary.clone()) {
        return Err(e);
    }

    Ok(())
}

fn demo(
    indexes: &[Box<dyn Index<u16, u32>>],
    vocabulary: Arc<Vocabulary<u32>>,
) -> Result<(), Box<dyn Error>> {
    let mut current = String::new();

    for (_, index) in indexes.iter().enumerate() {
        let mut current_node = index.start();

        loop {
            let transitions = match index.transitions(current_node) {
                Some(trans) if !trans.is_empty() => trans,
                _ => {
                    break;
                }
            };

            if transitions.contains(&vocabulary.get_eos_id()) {
                break;
            }

            let routes: Vec<_> = transitions
                .iter()
                .filter_map(|&token_id| {
                    vocabulary.get_token_by_id(token_id).map(|token| (token_id, token))
                })
                .collect();

            print!("Routes: ");
            
            for (_, token_str) in &routes {
                print!("`{}` ", token_str);
            }

            println!();

            let selected_token_id = loop {
                print!("> ");

                io::stdout().flush()?;

                let mut input = String::new();

                io::stdin().read_line(&mut input)?;

                let selected_token = input.trim_matches('\n');

                if let Some(id) = vocabulary.get_id_by_token(selected_token) {
                    if transitions.contains(&id) {
                        break id;
                    } else {
                        println!("Invalid token!");
                    }
                } else {
                    println!("Non-existent token!");
                }
            };

            if let Some(token) = vocabulary.get_token_by_id(selected_token_id) {
                current.push_str(&token);
            }

            println!("Current: {}", current);

            if let Some(next_node) = index.next(current_node, selected_token_id) {
                current_node = next_node;
            } else {
                break;
            }
        }
    }

    Ok(())
}