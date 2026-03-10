use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{self, Write};
use std::sync::Arc;
use fastlines::{FlatDFA, Vocabulary};

mod context;
mod engine;
mod factory;
mod graph;
mod many_resolver;
mod one_resolver;
mod schema;

use engine::Engine;
use schema::parse_schema;

use crate::graph::root;

type TargetEngine = Engine<u32, u32, FlatDFA<u32, u32>>;

const VOCABULARY_PATH: &str = "../vocabulary.tiktoken";
const EOS_ID: u32 = 1;

const SCHEMA: &str = r#"
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);
"#;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let raw_vocabulary = fs::read(VOCABULARY_PATH)?;
    let vocabulary = Vocabulary::new(&raw_vocabulary, EOS_ID)
        .ok_or("Failed to load vocabulary")?;

    let tables = parse_schema(SCHEMA)
        .ok_or("Failed to parse schema")?;

    let thunk = root();

    let mut engine = TargetEngine::new(Arc::new(vocabulary), tables, thunk)
        .ok_or("Failed to initialize engine")?;

    let mut current = String::new();

    'outer: loop {
        let route_ids = engine.routes();

        if route_ids.is_empty() {
            break;
        }

        let mut switch: HashMap<String, u32> = HashMap::new();
        let mut routes: Vec<String> = Vec::new();

        for &id in &route_ids {
            if let Some(token) = engine.get_token(id) {
                switch.insert(token.to_string(), id);
                routes.push(token.to_string());
            }
        }

        routes.retain(|r| {
            (r.len() == 1 || !r.chars().all(|c| c.is_whitespace()))
                && !r.chars().any(|c| c.is_control())
        });

        routes.sort_unstable();
        routes.truncate(100);

        let routes: Vec<String> = routes.iter().map(|r| format!("`{}`", r)).collect();

        println!("Routes: {}{}", 
            routes.join(", "),
            if switch.len() > routes.len() { ", ..." } else { " " }
        );

        let stdin = io::stdin();
        let mut stdout = io::stdout();

        loop {
            print!("> ");

            if stdout.flush().is_err() {
                break 'outer;
            }

            let mut input = String::new();

            if stdin.read_line(&mut input).is_err() || input.is_empty() {
                break 'outer;
            }

            let input = input.trim_matches('\n');

            if input.is_empty() {
                continue;
            }

            if let Some(id) = switch.get(input) {
                engine.feed(*id);
                current.push_str(input);

                break;
            } else {
                println!("Non-existent token!");
            }
        }

        println!("Matched: `{}`", engine.matched());

        if engine.is_completed() {
            break;
        }
    }

    Ok(())
}
