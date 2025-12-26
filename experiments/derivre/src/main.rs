use derivre::RegexBuilder;
use std::io::{self, Write};

fn get_routes(rx: &mut derivre::Regex, state: derivre::StateID, vocabulary: &Vec<&str>) -> Vec<String> {
    vocabulary
        .iter()
        .filter(|&&token| {
            let next = rx.transition_bytes(state, token.as_bytes());
            
            !next.is_dead()
        })
        .map(|&s| s.to_string())
        .collect()
}

fn main() {
    let mut builder = RegexBuilder::new();
    let expr = builder.mk_regex("monday|tuesday|wednesday|thursday|friday").unwrap();
    let mut rx = builder.into_regex(expr);
    
    let vocabulary: Vec<String> = ('a'..='z').map(|c| c.to_string()).collect();
    let vocabulary: Vec<&str> = vocabulary.iter().map(|s| s.as_str()).collect();
    
    let mut state = rx.initial_state();
    let mut input = String::new();
    
    loop {
        println!("Current: `{}`", input);

        let routes = get_routes(&mut rx, state, &vocabulary);

        println!("Possible next tokens: {:?}", routes);
        
        if routes.is_empty() {
            println!("No valid continuations, resetting");

            state = rx.initial_state();

            input.clear();

            continue;
        }
        
        print!("Enter a letter: ");

        io::stdout().flush().unwrap();
        
        let mut buffer = String::new();

        io::stdin().read_line(&mut buffer).unwrap();
        
        let c = buffer.trim();
        
        if c.len() != 1 {
            continue;
        }
        
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