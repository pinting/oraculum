use derivre::RegexBuilder;
use std::cell::RefCell;
use std::io::{self, Write};
use std::rc::Rc;
use toktrie::{
    recognizer::{FunctionalRecognizer, StackRecognizer},
    TokRxInfo, TokTrie,
};
struct RegexRecognizer<'a> {
    rx: RefCell<&'a mut derivre::Regex>,
    start_state: derivre::StateID,
}

impl<'a> FunctionalRecognizer<derivre::StateID> for RegexRecognizer<'a> {
    fn initial(&self) -> derivre::StateID {
        self.start_state
    }

    fn try_append(&self, state: derivre::StateID, byte: u8) -> Option<derivre::StateID> {
        print!("{} ", byte as char);

        let next = self.rx.borrow_mut().transition_bytes(state, &[byte]);

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
    vocabulary: &[Rc<str>],
) -> Vec<Rc<str>> {
    println!("Calculating possible routes, trying to append...");

    let recognizer = RegexRecognizer {
        rx: RefCell::new(rx),
        start_state: state,
    };
    
    let mut stack_recognizer = StackRecognizer::from(recognizer);
    let mut allowed = trie.alloc_token_set();

    trie.add_bias(&mut stack_recognizer, &mut allowed, &[]);

    println!("");

    allowed
        .iter()
        .map(|token_id| vocabulary[token_id as usize].clone())
        .collect()
}

fn main() {
    let mut builder = RegexBuilder::new();
    let expr = builder.mk_regex("monday|tuesday|wednesday|thursday|friday").unwrap();
    let mut rx = builder.into_regex(expr);

    let vocabulary: Vec<Rc<str>> = ('a'..='z')
        .map(|c| Rc::from(c.to_string()))
        .collect();

    let words: Vec<Vec<u8>> = vocabulary.iter().map(|s| s.as_bytes().to_vec()).collect();
    let info = TokRxInfo::new(vocabulary.len() as u32, 0);
    let trie = TokTrie::from(&info, &words);

    let mut state = rx.initial_state();
    let mut input = String::new();

    loop {
        println!("Current: `{}`", input);

        let routes = get_routes(&trie, &mut rx, state, &vocabulary);

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