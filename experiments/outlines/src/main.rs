use outlines_core::*;
use outlines_core::prelude::{Index};
use std::io::{self, Write};
use std::collections::HashMap;
use base64::{Engine, engine::general_purpose::STANDARD};
use std::rc::Rc;
use std::fs;

struct Vocabulary {
    token_to_id: HashMap<Rc<str>, u32>,
    id_to_token: HashMap<u32, Rc<str>>,
}

impl Vocabulary {
    fn new() -> Self {
        Self {
            token_to_id: HashMap::new(),
            id_to_token: HashMap::new(),
        }
    }

    fn load(&mut self, data: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
        let text = str::from_utf8(data)?;

        for line in text.lines() {
            let parts: Vec<&str> = line.split_whitespace().collect();

            if parts.len() != 2 {
                continue;
            }

            let (token, id) = (parts[0], parts[1]);

            let Ok(token) = STANDARD.decode(token) else { continue };
            let Ok(token) = String::from_utf8(token) else { continue };
            let Ok(id) = id.parse::<u32>() else { continue };

            let token: Rc<str> = Rc::from(token);

            self.token_to_id.insert(token.clone(), id);
            self.id_to_token.insert(id, token);
        }

        Ok(())
    }
}

fn get_routes(index: &Index, state: &u32, vocabulary: &Vocabulary) -> (Vec<Rc<str>>, usize) {
    let Some(ids) = index.allowed_tokens(state) else {
        return (Vec::new(), 0);
    };

    let mut count = 0;

    let routes = ids
        .iter()
        .filter_map(|&id| {
            count += 1;

            vocabulary.id_to_token.get(&id).cloned()
        })
        .collect();

    (routes, count)
}

fn main() {
    let result = fs::read("../../vocabulary.tiktoken");

    let Ok(data) = result else {
        println!("Failed to read vocabulary");

        return
    };

    let mut vocabulary = Vocabulary::new();
    let result = vocabulary.load(&data);

    if result.is_err() {
        println!("Failed to load vocabulary");

        return
    }

    let eos_token_id = 26;

    let mut v = prelude::Vocabulary::new(eos_token_id);

    for (token, &id) in &vocabulary.token_to_id {
        v.try_insert(token.as_ref(), id).unwrap();
    }

    let index = Index::new("monday|tuesday|wednesday|thursday|friday", &v).unwrap();

    let mut state = index.initial_state();
    let mut input = String::new();

    loop {
        println!("Current: `{}`", input);

        let (routes, n) = get_routes(&index, &state, &vocabulary);

        println!("Number of transition attempts: {}", n);
        println!("Possible next tokens: {:?}", routes);

        if routes.is_empty() {
            println!("No valid continuations, resetting");

            state = index.initial_state();

            input.clear();

            continue;
        }

        print!("Input: ");

        io::stdout().flush().unwrap();

        let mut buffer = String::new();

        io::stdin().read_line(&mut buffer).unwrap();

        let c = buffer..trim_matches('\n');
        let token_id = vocabulary.token_to_id.get(c);

        if let Some(&id) = token_id {
            if let Some(next_state) = index.next_state(&state, &id) {
                state = next_state;

                input.push_str(c);
            } else {
                println!("Invalid state, resetting");

                state = index.initial_state();

                input.clear();
            }
        } else {
            println!("Invalid token, resetting");

            state = index.initial_state();

            input.clear();
        }
    }
}
