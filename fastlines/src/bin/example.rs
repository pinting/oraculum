use aho_corasick::AhoCorasickKind;
use std::error::Error;
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Instant;

use fastlines::{FlatDFA, Lattice, BaseIndex, Expression, Number, Vocabulary};

fn main() -> Result<(), Box<dyn Error>> {
    let now = Instant::now();
    let vocabulary = Vocabulary::from_file_path("../vocabulary.tiktoken", 1u32)
        .map(Arc::new)
        .ok_or("Failed to create vocabulary")?;

    println!("Vocabulary loaded in {:?}", now.elapsed());

    let now = Instant::now();
    let ac = Lattice::<u32, u32>::base(AhoCorasickKind::ContiguousNFA, vocabulary.clone())
        .ok_or("Failed to build AhoCorasick base")?;

    println!("Lattice base (AhoCorasick) built in {:?}", now.elapsed());

    let now = Instant::now();
    let toktrie = Expression::<u32, u32, FlatDFA<u32, u32>>::base(vocabulary.clone())
        .ok_or("Failed to build TokTrie base")?;

    println!("Expression base (TokTrie) built in {:?}", now.elapsed());

    let mut indexes: Vec<Box<dyn BaseIndex<u32, u32>>> = Vec::new();

    println!("Creating indexes...");

    let now = Instant::now();
    let input = "Why ";
    let index = Lattice::<u32, u32>::new(input, vocabulary.clone(), &ac)
        .ok_or_else(|| format!("Failed to create Lattice index with '{}'", input))?;

    indexes.push(Box::new(index));

    println!("Lattice '{}' created in {:?}", input, now.elapsed());

    let now = Instant::now();
    let input = "monday|tuesday|wednesday|thursday|friday";
    let index = Expression::<u32, u32, FlatDFA<u32, u32>>::new(input, vocabulary.clone(), &toktrie)
        .ok_or_else(|| format!("Failed to create Expression index with '{}'", input))?;

    indexes.push(Box::new(index));

    println!("Expression '{}' created in {:?}", input, now.elapsed());

    let now = Instant::now();
    let input = "?";
    let index = Lattice::<u32, u32>::new(input, vocabulary.clone(), &ac)
        .ok_or_else(|| format!("Failed to create Lattice index with '{}'", input))?;

    indexes.push(Box::new(index));

    println!("Lattice '{}' created in {:?}", input, now.elapsed());

    for index in &indexes {
        println!("Memory usage: {} bytes", index.memory_usage());
    }

    let mut current = String::new();

    for (_, index) in indexes.iter().enumerate() {
        let mut current_node = 0;

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
