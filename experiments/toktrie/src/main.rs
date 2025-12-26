use derivre::RegexBuilder;
use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::fs;
use std::io::{self, Write};
use std::rc::Rc;
use std::time::Instant;
use base64::{Engine, engine::general_purpose::STANDARD};
use toktrie::{
    recognizer::{FunctionalRecognizer, StackRecognizer},
    TokRxInfo, TokTrie,
};

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

struct RegexRecognizer<'a> {
    rx: RefCell<&'a mut derivre::Regex>,
    start_state: derivre::StateID,
    n: &'a Cell<usize>,
}

impl<'a> FunctionalRecognizer<derivre::StateID> for RegexRecognizer<'a> {
    fn initial(&self) -> derivre::StateID {
        self.start_state
    }

    fn try_append(&self, state: derivre::StateID, byte: u8) -> Option<derivre::StateID> {
        let next = self.rx.borrow_mut().transition_bytes(state, &[byte]);

        self.n.set(self.n.get() + 1);

        if next.is_dead() {
            None
        } else {
            Some(next)
        }
    }
}

fn get_routes(
    trie: &TokTrie,
    rx: &mut derivre::Regex,
    state: derivre::StateID,
    tokens: &[Rc<str>],
) -> Vec<Rc<str>> {
    let n = Cell::new(0);
    let recognizer = RegexRecognizer {
        rx: RefCell::new(rx),
        start_state: state,
        n: &n,
    };
    
    let mut stack_recognizer = StackRecognizer::from(recognizer);
    let mut result = trie.alloc_token_set();

    trie.add_bias(&mut stack_recognizer, &mut result, &[]);

    println!("Number of transition attempts: {}", n.get());

    result
        .iter()
        .map(|token_id| tokens[token_id as usize].clone())
        .collect()
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

    let start = Instant::now();
    let mut builder = RegexBuilder::new();
    let expr = builder.mk_regex("monday|tuesday|wednesday|thursday|friday").unwrap();
    let mut rx = builder.into_regex(expr);

    println!("Built regex in {:?}", start.elapsed());

    let start = Instant::now();
    let words: Vec<Vec<u8>> = tokens.iter().map(|s| s.as_bytes().to_vec()).collect();
    let info = TokRxInfo::new(tokens.len() as u32, 0);
    let trie = TokTrie::from(&info, &words);

    println!("Built trie in {:?}", start.elapsed());

    let mut state = rx.initial_state();
    let mut input = String::new();

    loop {
        println!("Current: `{}`", input);

        let routes = get_routes(&trie, &mut rx, state, &tokens);

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