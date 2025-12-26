use derivre::RegexBuilder;
use std::fs;
use std::io::{self, Write};
use std::collections::HashMap;
use std::time::Instant;
use base64::{Engine, engine::general_purpose::STANDARD};
use std::rc::Rc;

struct Vocabulary {
    token_to_id: HashMap<Rc<str>, u32>,
    id_to_token: HashMap<u32, Rc<str>>,
    idx_to_id: HashMap<usize, u32>,
    tokens: Vec<Rc<str>>,
}

impl Vocabulary {
    fn new() -> Self {
        Self {
            token_to_id: HashMap::new(),
            id_to_token: HashMap::new(),
            idx_to_id: HashMap::new(),
            tokens: Vec::new(),
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
            let idx = self.tokens.len();

            self.token_to_id.insert(token.clone(), id);
            self.id_to_token.insert(id, token.clone());
            self.idx_to_id.insert(idx, id);
            self.tokens.push(token);
        }

        Ok(())
    }
}

fn get_routes(rx: &mut derivre::Regex, state: derivre::StateID, tokens: &[Rc<str>]) -> Vec<Rc<str>> {
    let mut n = 0;
    let result = tokens
        .iter() 
        .filter(|&token| {
            let next = rx.transition_bytes(state, token.as_bytes());
            
            n += 1;
            
            !next.is_dead()
        })
        .map(|s| s.clone())
        .collect();

    println!("Number of transition attempts: {}", n);

    result
}

fn main() {
    let start = Instant::now();
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

    let tokens: Vec<Rc<str>> = vocabulary.tokens
        .iter()
        .map(|c| Rc::from(c.to_string()))
        .collect();

    println!("Loaded vocabulary in {:?}", start.elapsed());

    let default_pattern = "monday|tuesday|wednesday|thursday|friday";

    print!("Enter regex pattern (press Enter for default weekdays): ");

    io::stdout().flush().unwrap();

    let mut pattern_input = String::new();

    io::stdin().read_line(&mut pattern_input).unwrap();

    let pattern = pattern_input.trim_matches('\n');
    let pattern = if pattern.is_empty() { default_pattern } else { pattern };

    let start = Instant::now();
    let mut builder = RegexBuilder::new();
    let expr_result = builder.mk_regex(pattern);

    let expr = match expr_result {
        Ok(e) => {
            println!("Using pattern: {}", pattern);

            e
        }
        Err(e) => {
            println!("Invalid regex: {}. Using default pattern: {}", e, default_pattern);

            builder.mk_regex(default_pattern).unwrap()
        }
    };

    let mut rx = builder.into_regex(expr);

    println!("Built regex in {:?}", start.elapsed());

    let mut state = rx.initial_state();
    let mut input = String::new();
    
    loop {
        println!("Current: `{}`", input);

        let routes = get_routes(&mut rx, state, &tokens);

        println!("Possible next tokens: {:?}", routes);
        
        if routes.is_empty() {
            println!("No valid continuations, resetting");

            state = rx.initial_state();

            input.clear();

            continue;
        }
        
        print!("Input: ");

        io::stdout().flush().unwrap();
        
        let mut buffer = String::new();

        io::stdin().read_line(&mut buffer).unwrap();
        
        let c = buffer.trim_matches('\n');
        
        let next_state = rx.transition_bytes(state, c.as_bytes());

        if next_state.is_dead() {
            println!("Invalid character, resetting");

            state = rx.initial_state();

            input.clear();
        } else {
            state = next_state;

            input.push_str(c);
        }
    }
}