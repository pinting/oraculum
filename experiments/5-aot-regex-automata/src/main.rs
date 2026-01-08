use base64::{engine::general_purpose::STANDARD, Engine};
use regex_automata::dfa::dense::DFA;
use regex_automata::dfa::Automaton;
use regex_automata::util::primitives::StateID as AutomataStateId;
use regex_automata::Anchored;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{self, Write};
use std::rc::Rc;
use std::str;
use std::time::Instant;

#[derive(Debug)]
enum Error {
    NoStartState,
    BadVocabulary(String),
    RegExpError(Box<dyn std::error::Error>),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::NoStartState => write!(f, "DFA has no start state"),
            Error::BadVocabulary(exp) => write!(f, "Bad vocabulary for RegExp {}", exp),
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
            token_to_id: HashMap::new(),
            id_to_token: HashMap::new(),
            idx_to_id: HashMap::new(),
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

type TokenId = u32;
type StateId = u32;

#[derive(Clone, Debug)]
struct Index {
    initial_state: StateId,
    transitions: HashMap<StateId, HashMap<TokenId, StateId>>,
    eos_token_id: TokenId,
}

// Ported from outlines-core
impl Index {
    fn new(exp: &str, vocabulary: &Vocabulary) -> Result<Self, Error> {
        let eos_token_id = vocabulary.eos_token_id;

        let dfa = DFA::new(exp).map_err(|e| Error::RegExpError(Box::new(e)))?;
        
        let start_state = match dfa.universal_start_state(Anchored::Yes) {
            Some(s) => s,
            None => return Err(Error::NoStartState),
        };

        let mut transitions: HashMap<StateId, HashMap<TokenId, StateId>> = HashMap::new();
        let mut final_states: HashSet<StateId> = HashSet::new();

        let mut seen: HashSet<AutomataStateId> = HashSet::from_iter([start_state]);
        let mut next_states: Vec<AutomataStateId> = vec![start_state];

        while let Some(current_state) = next_states.pop() {
            let mut has_valid_transitions = false;

            if dfa.is_match_state(dfa.next_eoi_state(current_state)) {
                final_states.insert(current_state.as_u32());
                
                has_valid_transitions = true;
            }

            'token_loop: for (token, &id) in vocabulary.token_to_id.iter() {
                if eos_token_id == id{
                    continue;
                }

                let mut next_state = current_state;

                for &transition_byte in token.as_bytes() {
                    next_state = dfa.next_state(next_state, transition_byte);

                    if dfa.is_dead_state(next_state) || dfa.is_quit_state(next_state) {
                        continue 'token_loop;
                    }
                }

                let is_intermediate_state = !dfa.is_match_state(next_state);
                let is_full_match_state = dfa.is_match_state(dfa.next_eoi_state(next_state));
                
                if is_intermediate_state || is_full_match_state {
                    has_valid_transitions = true;

                    transitions
                        .entry(current_state.as_u32())
                        .or_default()
                        .insert(id, next_state.as_u32());
                }
                
                if !seen.contains(&next_state) {
                    seen.insert(next_state);
                    next_states.push(next_state);
                }
            }

            if !has_valid_transitions && !dfa.is_match_state(current_state) {
                return Err(Error::BadVocabulary(exp.to_string()));
            }
        }

        for &final_state in &final_states {
            transitions
                .entry(final_state)
                .or_default()
                .insert(eos_token_id, final_state);
        }

        Ok(Self {
            initial_state: start_state.as_u32(),
            transitions,
            eos_token_id,
        })
    }

    fn initial_state(&self) -> StateId {
        self.initial_state
    }

    fn allowed_tokens(&self, state: &StateId) -> Option<Vec<TokenId>> {
        self.transitions
            .get(state)
            .map(|res| res.keys().cloned().collect())
    }

    fn next_state(&self, state: &StateId, token_id: &TokenId) -> Option<StateId> {
        if token_id == &self.eos_token_id {
            return None;
        }

        Some(*self.transitions.get(state)?.get(token_id)?)
    }
}

fn get_routes(index: &Index, state: &u32, vocabulary: &Vocabulary) -> Vec<Rc<str>> {
    let Some(ids) = index.allowed_tokens(state) else {
        return Vec::new();
    };

    ids
        .iter()
        .filter_map(|&id| {
            vocabulary.id_to_token.get(&id).cloned()
        })
        .collect()
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

    let default_pattern = "(monday|tuesday|wednesday|thursday|friday)+";

    print!("Enter regex pattern (press Enter for default): ");
    
    io::stdout().flush().unwrap();

    let mut pattern_input = String::new();

    io::stdin().read_line(&mut pattern_input).unwrap();

    let pattern = pattern_input.trim_matches('\n');
    let pattern = if pattern.is_empty() { default_pattern } else { pattern };

    let start = Instant::now();
    let index_result = Index::new(pattern, &vocabulary);

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
            Index::new(default_pattern, &vocabulary).unwrap()
        }
    };

    println!("Built index in {:?}", start.elapsed());

    let mut state = index.initial_state();
    let mut input = String::new();

    loop {
        println!("Current: `{}`", input);

        let start_routes = Instant::now();
        let routes = get_routes(&index, &state, &vocabulary);

        println!("Time to get routes: {:?}", start_routes.elapsed());
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