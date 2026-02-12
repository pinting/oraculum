use aho_corasick::{AhoCorasick, AhoCorasickKind};
use std::{collections::HashMap, io::{self, Write}, rc::Rc, time::Instant};
use base64::{Engine, engine::general_purpose::STANDARD};
use std::fs;

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

type TokenId = u32;
type TextPosition = usize;
type EdgeIdx = u32;

#[derive(Debug, Clone, Copy)]
struct TokenEdge {
    token_id: TokenId,
    target: TextPosition,
    next: EdgeIdx,
}

struct TokenLattice {
    heads: Vec<EdgeIdx>,
    edges: Vec<TokenEdge>,
}

impl TokenLattice {
    fn new(input: &str, vocabulary: &Vocabulary, ac: &AhoCorasick) -> Self {
        let length = input.len();
        let mut lattice = Self {
            heads: vec![u32::MAX; length + 1],
            edges: Vec::with_capacity(length * 2),
        };

        for m in ac.find_overlapping_iter(input) {
            let idx = m.pattern().as_usize();
            let Some(id) = vocabulary.idx_to_id.get(&idx) else { continue };

            let start = m.start();
            let end = m.end();

            lattice.add(start, end, id);
        }

        lattice
    }

    fn add(&mut self, start: usize, end: usize, token_id: &u32) {
        let next_edge_idx = self.heads[start];
        
        let edge = TokenEdge {
            token_id: *token_id,
            target: end as TextPosition,
            next: next_edge_idx,
        };

        let i = self.edges.len() as u32;

        self.edges.push(edge);

        self.heads[start] = i;
    }

    fn get_routes(&self, position: TextPosition, vocabulary: &Vocabulary) -> Vec<(Rc<str>, TokenId, TextPosition)> {
        let mut routes = Vec::new();
        let mut i = self.heads[position];

        while i != u32::MAX {
            let edge = &self.edges[i as usize];

            if let Some(token) = vocabulary.id_to_token.get(&edge.token_id) {
                routes.push((token.clone(), edge.token_id, edge.target));
            }

            i = edge.next;
        }

        routes
    }
}

fn main() {
    let start = Instant::now();
    let result = fs::read("../../vocabulary.tiktoken");

    let Ok(data) = result else {
        println!("Failed to read vocabulary");
        return;
    };

    let mut vocabulary = Vocabulary::new();
    let result = vocabulary.load(&data);

    if result.is_err() {
        println!("Failed to load vocabulary");
        return;
    }

    let tokens: Vec<&str> = vocabulary.tokens.iter().map(|v| v.as_ref()).collect();
    let tokens = &tokens;

    println!("Loaded vocabulary in {:?}", start.elapsed());
    println!("Vocabulary size: {} tokens", tokens.len());
    println!("Define constant: ");

    let mut input = String::new();

    io::stdin()
        .read_line(&mut input)
        .expect("Failed to read line");

    let input = input.trim_matches('\n');

    println!("NonContiguousNFA");

    let (build_time, memory_usage, nfa_ac) = {
        let start = Instant::now();
        let ac = AhoCorasick::builder()
            .kind(Some(AhoCorasickKind::NoncontiguousNFA))
            .build(tokens)
            .unwrap();
        (start.elapsed(), ac.memory_usage(), ac)
    };

    println!("\tBuild time: {:?}", build_time);
    println!("\tMemory usage: {:.2} MB", memory_usage as f64 / (1024.0 * 1024.0));

    let start = Instant::now();
    
    TokenLattice::new(input, &vocabulary, &nfa_ac);

    println!("\tLattice construction time: {:?}", start.elapsed());

    println!("ContiguousNFA");

    let (build_time, memory_usage, contiguous_nfa_ac) = {
        let start = Instant::now();
        let ac = AhoCorasick::builder()
            .kind(Some(AhoCorasickKind::ContiguousNFA))
            .build(tokens)
            .unwrap();

        (start.elapsed(), ac.memory_usage(), ac)
    };
    
    println!("\tBuild time: {:?}", build_time);
    println!("\tMemory usage: {:.2} MB", memory_usage as f64 / (1024.0 * 1024.0));

    let start = Instant::now();

    TokenLattice::new(input, &vocabulary, &contiguous_nfa_ac);

    println!("\tLattice construction time: {:?}", start.elapsed());

    println!("DFA");

    let (build_time, memory_usage, dfa_ac) = {
        let start = Instant::now();
        let ac = AhoCorasick::builder()
            .kind(Some(AhoCorasickKind::DFA))
            .build(tokens)
            .unwrap();
        (start.elapsed(), ac.memory_usage(), ac)
    };

    println!("\tBuild time: {:?}", build_time);
    println!("\tMemory usage: {:.2} MB", memory_usage as f64 / (1024.0 * 1024.0));

    let start = Instant::now();
    let lattice = TokenLattice::new(input, &vocabulary, &dfa_ac);

    println!("\tLattice construction time: {:?}", start.elapsed());

    let mut position: TextPosition = 0;
    let mut selected = String::new();

    loop {
        println!("Current: `{}`", selected);

        let start = Instant::now();
        let routes = lattice.get_routes(position, &vocabulary);

        println!("Time taken: {:?}", start.elapsed());
        println!("Number of possible transitions: {}", routes.len());

        let tokens: Vec<&str> = routes.iter().map(|(t, _, _)| t.as_ref()).collect();

        println!("Possible next tokens: {:?}", tokens);

        if routes.is_empty() {
            println!("No routes, exiting");

            return;
        }

        print!("Input: ");

        io::stdout().flush().unwrap();

        let mut buffer = String::new();

        io::stdin().read_line(&mut buffer).unwrap();

        let buffer = buffer.trim_matches('\n');
        
        let route = routes
            .iter()
            .find(|(token, _, _)| token.as_ref() == buffer);

        let Some((token, _, target)) = route else {
            println!("Invalid token / route");
            continue;
        };

        selected.push_str(token.as_ref());

        position = *target;
    }
}