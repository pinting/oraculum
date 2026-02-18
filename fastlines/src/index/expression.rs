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
use crate::index::index::Index;
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

        // Build the regular expression engine
        let mut rb = RegexBuilder::new();
        let exp = rb.mk_regex(expression).ok()?;
        let mut rx = rb.into_regex(exp);

        // Initialize
        let start_state = rx.initial_state();

        let mut state_to_node: HashMap<StateID, N> = HashMap::default();

        state_to_node.insert(start_state, N::from_usize(0));

        let mut queue = VecDeque::new();

        queue.push_back(start_state);

        let mut transitions: HashMap<N, HashMap<T, N>> = HashMap::default();
        let mut next_node_id = 1;

        // Explore the lazy generated graph of Derivre
        while let Some(current_state) = queue.pop_front() {
            let current_node = *state_to_node.get(&current_state).unwrap();

            if rx.is_accepting(current_state) {
                // Self-loop for EOS: this is needed so the transitions()
                // give back the terminating token ID when an accepting state
                // is reached
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

impl<N, T, D> Index<N, T> for Expression<N, T, D>
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
        if token_id == self.eos_id {
            return None;
        }

        self.dfa.next(node_id, token_id)
    }
    
    fn transitions<'a>(&'a self, node_id: N) -> Option<Cow<'a, [T]>> {
        self.dfa.transitions(node_id)
    }

    fn name(&self) -> &str {
        "Expression"
    }

    fn memory_usage(&self) -> usize {
        self.dfa.memory_usage()
    }
}
