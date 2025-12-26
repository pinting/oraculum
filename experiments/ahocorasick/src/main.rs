use aho_corasick::AhoCorasick;
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

#[derive(Debug, Clone, Copy)]
struct TokenEdge {
    token_id: u32,
    target: usize,
    next_idx: u32,
}

struct TokenLattice {
    heads: Vec<u32>,
    edges: Vec<TokenEdge>,
    cache: HashMap<(usize, u32), usize>, // (start, token_id) -> target
}

impl TokenLattice {
    fn new(length: usize) -> Self {
        Self {
            heads: vec![u32::MAX; length + 1],
            edges: Vec::with_capacity(length * 2),
            cache: HashMap::with_capacity(length * 2)
        }
    }

    fn add(&mut self, start: usize, end: usize, token_id: &u32) {
        let next_edge_idx = self.heads[start];
        
        let edge = TokenEdge {
            token_id: *token_id,
            target: end,
            next_idx: next_edge_idx,
        };

        let i = self.edges.len() as u32;

        self.edges.push(edge);

        self.heads[start] = i;
        
        self.cache.insert((start, *token_id), end);
    }
    
    fn print(&self, vocabulary: &Vocabulary, length: usize) {
        let mut current_path = Vec::new();

        fn dfs(latice: &TokenLattice, u: usize, length: usize, path: &mut Vec<u32>, vocabulary: &Vocabulary) {
            if u == length {
                let tokens: Vec<&str> = path.iter()
                    .filter_map(|id| vocabulary.id_to_token.get(id))
                    .map(|s| s.as_ref())
                    .collect();

                println!("{:?}", tokens);

                return;
            }

            let mut i = latice.heads[u];

            while i != u32::MAX {
                let edge = &latice.edges[i as usize];

                path.push(edge.token_id);
                dfs(latice, edge.target as usize, length, path, vocabulary);
                path.pop();

                i = edge.next_idx;
            }
        }

        dfs(self, 0, length, &mut current_path, vocabulary);
    }

    fn get_routes(&self, position: usize, vocabulary: &Vocabulary) -> Vec<(Rc<str>, u32, usize)> {
        let mut routes = Vec::new();
        let mut i = self.heads[position];

        while i != u32::MAX {
            let edge = &self.edges[i as usize];

            if let Some(token) = vocabulary.id_to_token.get(&edge.token_id) {
                routes.push((token.clone(), edge.token_id, edge.target));
            }

            i = edge.next_idx;
        }

        routes
    }
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

    let tokens: Vec<&str> = vocabulary.tokens.iter().map(|v|v.as_ref()).collect();
    let tokens = &tokens;

    println!("Loaded vocabulary in {:?}", start.elapsed());

    let start = Instant::now();
    let ac = AhoCorasick::builder()
        .build(tokens)
        .unwrap();

    println!("Built graph in {:?}", start.elapsed());
    println!("Define constant: ");

    let mut input = String::new();

    io::stdin()
        .read_line(&mut input)
        .expect("Failed to read line");

    let start = Instant::now();
    let input = input.trim_matches('\n');
    let mut lattice = TokenLattice::new(input.len());

    for mat in ac.find_overlapping_iter(input) {
        let idx = mat.pattern().as_usize();
        let Some(id) = vocabulary.idx_to_id.get(&idx) else { continue };

        let start = mat.start();
        let end = mat.end();

        lattice.add(start, end, id);
    }

    println!("Constructed the token lattice in {:?}", start.elapsed());

    let length = input.len();
    let mut position = 0;
    let mut selected = String::new();

    loop {
        println!("Current: `{}`", selected);

        let routes = lattice.get_routes(position, &vocabulary);

        println!("Number of possible transitions: {}", routes.len());

        let tokens: Vec<&str> = routes.iter().map(|(t, _, _)| t.as_ref()).collect();

        println!("Possible next tokens: {:?}", tokens);

        if routes.is_empty() {
            if position == length {
                println!("Reached the end of the lattice!");
            } else {
                println!("No valid continuations, resetting");
            }

            position = 0;

            selected.clear();

            continue;
        }

        print!("Input: ");

        io::stdout().flush().unwrap();

        let mut buffer = String::new();

        io::stdin().read_line(&mut buffer).unwrap();

        let c = buffer.trim_matches('\n');
        let found = routes.iter().find(|(token, _, _)| token.as_ref() == c);

        if let Some((token, _, target)) = found {
            selected.push_str(token.as_ref());

            position = *target;
        } else {
            println!("Invalid token, resetting");

            position = 0;

            selected.clear();
        }
    }
}