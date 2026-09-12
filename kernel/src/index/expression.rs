//! A regular expression, as a DFA over vocabulary tokens.
//!
//! Derivre gives a DFA over *bytes*, generated lazily by Brzozowski
//! derivatives. What a generator needs is a DFA over *tokens*, so this explores
//! the byte automaton breadth first and, at each state it reaches, asks a
//! TokTrie which whole tokens that state would accept. Every such token becomes
//! one edge, and every state an edge leads to becomes a node.
//!
//! That exploration is what makes building an index expensive - it is the
//! whole reachable automaton, not a lazy slice of it - which is why the result
//! is packed into a `DFA` layout that makes the lookups afterwards cheap, and
//! why the factory goes to some trouble never to build one twice.
//!
//! An accepting state gets the EOS token as a self loop, so acceptance is
//! answered by the same table as everything else.
//!
//! `base` builds the TokTrie. Like the Aho-Corasick base it depends on nothing
//! but the vocabulary, so it is built once and shared.

use derivre::{Regex, RegexBuilder, StateID};
use toktrie::TokRxInfo;
use std::cell::{RefCell};
use std::collections::{VecDeque};
use rustc_hash::{FxHashMap as HashMap};
use std::sync::Arc;
use std::borrow::Cow;
use toktrie::{
    recognizer::{FunctionalRecognizer, StackRecognizer},
    TokTrie,
};

use crate::dfa::dfa::DFA;
use crate::index::index::{BaseIndex, Accepting};
use crate::number::Number;
use crate::vocabulary::Vocabulary;

struct RegexRecognizer<'a> {
    rx: RefCell<&'a mut Regex>,
    start_state: StateID,
}

impl<'a> FunctionalRecognizer<StateID> for RegexRecognizer<'a> {
    fn initial(&self) -> StateID {
        self.start_state
    }

    fn try_append(&self, state: StateID, byte: u8) -> Option<StateID> {
        let next = self.rx.borrow_mut().transition_bytes(state, &[byte]);

        if next.is_dead() {
            None
        } else {
            Some(next)
        }
    }
}

#[derive(Clone, Debug)]
pub struct Expression<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    dfa: D,
    node_count: N,
    eos_id: T,
}

impl<N, T, D> Expression<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    pub fn base(vocabulary: Arc<Vocabulary<T>>) -> Option<TokTrie> {
        let words: Vec<Vec<u8>> = vocabulary.get_tokens()
            .iter()
            .map(|token| token.as_bytes().to_vec())
            .collect();
        
        let info = TokRxInfo::new(words.len() as u32, 0);
        
        Some(TokTrie::from(&info, &words))
    }

    pub fn new(
        expression: &str,
        vocabulary: Arc<Vocabulary<T>>,
        trie: &TokTrie,
    ) -> Option<Self> {
        let eos_id = vocabulary.get_eos_id();

        let mut rb = RegexBuilder::new();
        let exp = rb.mk_regex(expression).ok()?;
        let mut rx = rb.into_regex(exp);

        let start_state = rx.initial_state();

        let mut next_node_id = 0;
        let mut state_to_node: HashMap<StateID, N> = HashMap::default();

        state_to_node.insert(start_state, N::from_usize(next_node_id));

        next_node_id += 1;

        let mut queue = VecDeque::new();

        queue.push_back(start_state);

        let mut transitions: HashMap<N, HashMap<T, N>> = HashMap::default();

        // Derivre generates its automaton lazily, so a state only exists once
        // it has been asked for; this walk is what forces the whole of it.
        while let Some(current_state) = queue.pop_front() {
            let current_node = *state_to_node.get(&current_state).unwrap();

            if rx.is_accepting(current_state) {
                // A self loop on EOS, so that `transitions` offers the
                // terminating token at an accepting state and `accepting` can
                // be answered by the same table as everything else.
                transitions
                    .entry(current_node)
                    .or_default()
                    .insert(eos_id, current_node);
            }

            let recognizer = RegexRecognizer {
                rx: RefCell::new(&mut rx),
                start_state: current_state,
            };
            
            let mut stack_recognizer = StackRecognizer::from(recognizer);
            let mut result = trie.alloc_token_set();

            trie.add_bias(&mut stack_recognizer, &mut result, &[]);

            for token_idx in result.iter() {
                let token_idx = token_idx as usize;

                let Some(token_id) = vocabulary.get_id_by_idx(token_idx) else {
                    continue;
                };

                if token_id == eos_id {
                    continue; 
                }

                let Some(token) = vocabulary.get_token_by_idx(token_idx) else {
                    continue;
                };

                
                let next_state = rx.transition_bytes(current_state, token.as_bytes());

                if next_state.is_dead() {
                    continue;
                }

                let next_node = if let Some(&id) = state_to_node.get(&next_state) {
                    id
                } else {
                    let current_node_id = N::from_usize(next_node_id);

                    next_node_id += 1;

                    state_to_node.insert(next_state, current_node_id);
                    queue.push_back(next_state);

                    current_node_id
                };

                transitions
                    .entry(current_node)
                    .or_default()
                    .insert(token_id, next_node);
            }
        }

        let dfa = D::new(transitions.clone(), next_node_id);

        let node_count = N::from_usize(next_node_id);

        Some(Self {
            dfa,
            node_count,
            eos_id,
        })
    }
}

impl<N, T, D> BaseIndex<N, T> for Expression<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    fn node_count(&self) -> N {
        self.node_count
    }

    #[inline(always)]
    fn next(&self, node_id: N, token_id: T) -> Option<N> {
        self.dfa.next(node_id, token_id)
    }
    
    #[inline(always)]
    fn transitions<'a>(&'a self, node_id: N) -> Option<Cow<'a, [T]>> {
        self.dfa.transitions(node_id)
    }
    
    #[inline(always)]
    fn accepting(&self, node_id: N) -> Accepting {
        if self.next(node_id, self.eos_id).is_none() {
            return Accepting::No
        }

        let is_more = self.transitions(node_id).map_or(false, |t| t.len() > 1);

        Accepting::Yes(is_more)
    }

    fn memory_usage(&self) -> usize {
        self.dfa.memory_usage()
    }
}