use base64::{engine::general_purpose::STANDARD, Engine};
use derivre::RegexBuilder;
use std::cell::{RefCell};
use std::collections::{VecDeque};
use rustc_hash::{FxHashMap as HashMap};
use std::fs;
use std::io::{self, Write};
use std::rc::Rc;
use std::str;
use std::time::Instant;
use toktrie::{
    recognizer::{FunctionalRecognizer, StackRecognizer},
    TokRxInfo, TokTrie,
};

#[derive(Debug)]
enum Error {
    RegExpError(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::RegExpError(err) => write!(f, "RegExp error: {}", err),
        }
    }
}

impl std::error::Error for Error {}

struct Vocabulary {
    token_to_id: HashMap<Rc<str>, u32>,
    id_to_token: HashMap<u32, Rc<str>>,
    idx_to_id: HashMap<usize, u32>,
    tokens: Vec<Rc<str>>,
    eos_token_id: u32,
}

impl Vocabulary {
    fn new(eos_token_id: u32) -> Self {
        Self {
            token_to_id: HashMap::default(),
            id_to_token: HashMap::default(),
            idx_to_id: HashMap::default(),
            tokens: Vec::new(),
            eos_token_id,
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

struct RegexRecognizer<'a> {
    rx: RefCell<&'a mut derivre::Regex>,
    start_state: derivre::StateID,
}

impl<'a> FunctionalRecognizer<derivre::StateID> for RegexRecognizer<'a> {
    fn initial(&self) -> derivre::StateID {
        self.start_state
    }

    fn try_append(&self, state: derivre::StateID, byte: u8) -> Option<derivre::StateID> {
        let next = self.rx.borrow_mut().transition_bytes(state, &[byte]);

        if next.is_dead() {
            None
        } else {
            Some(next)
        }
    }
}

type TokenId = u32;
type NodeId = u32;

#[derive(Clone, Debug)]
struct Index {
    initial_node: NodeId,
    transitions: HashMap<NodeId, HashMap<TokenId, NodeId>>,
    eos_token_id: TokenId,
}

impl Index {
    fn new(exp: &str, vocabulary: &Vocabulary, trie: &TokTrie) -> Result<Self, Error> {
        let eos_token_id = vocabulary.eos_token_id;

        // 1. Build Regex (derivre)
        let mut builder = RegexBuilder::new();
        let exp = builder
            .mk_regex(exp)
            .map_err(|e| Error::RegExpError(e.to_string()))?;

        let mut rx = builder.into_regex(exp);

        // 2. Initialize Traversal
        let start_state = rx.initial_state();
        let start_node: NodeId = 0;
        
        let mut state_node_map: HashMap<derivre::StateID, NodeId> = HashMap::default();

        state_node_map.insert(start_state, start_node);

        let mut queue = VecDeque::new();

        queue.push_back(start_state);

        let mut transitions: HashMap<NodeId, HashMap<TokenId, NodeId>> = HashMap::default();
        let mut next_state_id: NodeId = 1;

        // 3. Explore Graph (AOT)
        while let Some(current_state) = queue.pop_front() {
            let current_node = *state_node_map.get(&current_state).unwrap();

            // Check if this state can be terminated
            if rx.is_accepting(current_state) {
                transitions
                    .entry(current_node)
                    .or_default()
                    .insert(eos_token_id, current_node); // Self-loop for EOS
            }

            // Collect valid token indexes for this state
            let next_token_idxs: Vec<u32> = {
                let recognizer = RegexRecognizer {
                    rx: RefCell::new(&mut rx),
                    start_state: current_state,
                };
                
                let mut stack_recognizer = StackRecognizer::from(recognizer);
                let mut result = trie.alloc_token_set();

                trie.add_bias(&mut stack_recognizer, &mut result, &[]);
                
                result.iter().collect()
            };

            for token_idx in next_token_idxs {
                let token_idx = token_idx as usize;

                let Some(&token_id) = vocabulary.idx_to_id.get(&token_idx) else {
                    continue;
                };

                if token_id == eos_token_id {
                    continue; 
                }

                let token = &vocabulary.tokens[token_idx];
                
                // Transition logic: Calculate exact next state in derivre
                let next_state = rx.transition_bytes(current_state, token.as_bytes());

                if next_state.is_dead() {
                    continue;
                }

                // Resolve State ID (DFA construction)
                let next_node = if let Some(&id) = state_node_map.get(&next_state) {
                    id
                } else {
                    let id = next_state_id;

                    next_state_id += 1;

                    state_node_map.insert(next_state, id);
                    queue.push_back(next_state);

                    id
                };

                // Store Transition
                transitions
                    .entry(current_node)
                    .or_default()
                    .insert(token_id, next_node);
            }
        }

        Ok(Self {
            initial_node: start_node,
            transitions,
            eos_token_id,
        })
    }

    fn initial_state(&self) -> NodeId {
        self.initial_node
    }

    fn allowed_tokens(&self, state: &NodeId) -> Option<Vec<TokenId>> {
        self.transitions
            .get(state)
            .map(|res| res.keys().cloned().collect())
    }

    fn next_state(&self, state: &NodeId, token_id: &TokenId) -> Option<NodeId> {
        if token_id == &self.eos_token_id {
            return None;
        }

        Some(*self.transitions.get(state)?.get(token_id)?)
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
    let start = Instant::now();
    let result = fs::read("../../vocabulary.tiktoken");

    let Ok(data) = result else {
        println!("Failed to read vocabulary. Ensure ../../vocabulary.tiktoken exists.");
        return;
    };

    // Literal "EOS" 103824    
    let eos_token_id = 103824;
    
    let mut vocabulary = Vocabulary::new(eos_token_id);
    let result = vocabulary.load(&data);

    if result.is_err() {
        println!("Failed to load vocabulary");
        return;
    }

    println!("Loaded vocabulary in {:?}", start.elapsed());

    let start = Instant::now();

    let words: Vec<Vec<u8>> = vocabulary.tokens.iter().map(|s| s.as_bytes().to_vec()).collect();
    let info = TokRxInfo::new(vocabulary.tokens.len() as u32, 0);
    let trie = TokTrie::from(&info, &words);

    println!("Built trie in {:?}", start.elapsed());

    let default_pattern = "(monday|tuesday|wednesday|thursday|friday)+";

    print!("Enter regex pattern (press Enter for default): ");
    
    io::stdout().flush().unwrap();

    let mut pattern_input = String::new();

    io::stdin().read_line(&mut pattern_input).unwrap();

    let pattern = pattern_input.trim_matches('\n');
    let pattern = if pattern.is_empty() { default_pattern } else { pattern };

    let start = Instant::now();
    let index_result = Index::new(pattern, &vocabulary, &trie);

    let index = match index_result {
        Ok(idx) => {
            println!("Using pattern: {}", pattern);
            idx
        }
        
        Err(e) => {
            println!(
                "Invalid regex or incompatible vocab: {:?}. Using default pattern: {}",
                e, default_pattern
            );
            Index::new(default_pattern, &vocabulary, &trie).unwrap()
        }
    };

    println!("Built index in {:?}", start.elapsed());

    let mut state = index.initial_state();
    let mut input = String::new();

    loop {
        println!("Current: `{}`", input);

        let (routes, n) = get_routes(&index, &state, &vocabulary);

        println!("Number of transition attempts: {}", n);
        println!("Possible next tokens: {:?}", routes);

        if routes.is_empty() {
            println!("No routes, exiting");

            return;
        }

        print!("Input: ");

        io::stdout().flush().unwrap();

        let mut buffer = String::new();

        io::stdin().read_line(&mut buffer).unwrap();

        let buffer = buffer.trim_matches('\n');
        let token_id = vocabulary.token_to_id.get(buffer);

        let Some(&id) = token_id else {
            println!("Invalid token");

            continue;
        };

        let Some(next_state) = index.next_state(&state, &id) else {
            if id == eos_token_id {
                println!("EOS reached, exiting");

                return;
            }

            println!("Invalid route for token {}", id);

            continue;
        };

        state = next_state;

        input.push_str(buffer);
    }
}