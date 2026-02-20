use std::borrow::Cow;
use std::collections::HashSet;
use std::sync::Arc;

use aho_corasick::AhoCorasick;
use aho_corasick::AhoCorasickKind;
use fastlines::{Expression, FlatDFA, Index, Lattice, Vocabulary};
use toktrie::TokTrie;

use crate::graph::{Column, Context, Node, State, Table, Thunk, root};


enum CursorIndex {
    Lattice(Lattice<u32, u32>),
    Expression(Expression<u32, u32, FlatDFA<u32, u32>>),
}

impl CursorIndex {
    fn from_state(
        state: &State,
        vocabulary: Arc<Vocabulary<u32>>,
        ac_base: &AhoCorasick,
        trie_base: &TokTrie,
    ) -> Option<Self> {
        match state {
            State::Literal(s) => Some(Self::Lattice(Lattice::new(s, vocabulary, ac_base))),
            State::Regex(pattern) => Expression::new(pattern, vocabulary, trie_base).map(Self::Expression),
        }
    }

    fn transitions(&self, node_id: u32) -> Option<Cow<'_, [u32]>> {
        match self {
            Self::Lattice(idx) => idx.transitions(node_id),
            Self::Expression(idx) => idx.transitions(node_id),
        }
    }

    fn next(&self, node_id: u32, token_id: u32) -> Option<u32> {
        match self {
            Self::Lattice(idx) => idx.next(node_id, token_id),
            Self::Expression(idx) => idx.next(node_id, token_id),
        }
    }

    fn is_accepting(&self, node_id: u32, eos_id: u32) -> bool {
        match self {
            Self::Lattice(idx) => idx.transitions(node_id).is_none(),
            Self::Expression(idx) => {
                idx.transitions(node_id)
                    .map_or(false, |ts| ts.iter().any(|&t| t == eos_id))
            }
        }
    }

    fn has_non_eos_transitions(&self, node_id: u32, eos_id: u32) -> bool {
        match self {
            Self::Lattice(idx) => idx.transitions(node_id).is_some(),
            Self::Expression(idx) => {
                idx.transitions(node_id)
                    .map_or(false, |ts| ts.iter().any(|&t| t != eos_id))
            }
        }
    }
}

// An active position inside the generation graph
struct Cursor {
    index: CursorIndex,
    node_id: u32,
    thunk: Thunk,
    context: Context,
}

pub struct Engine {
    vocabulary: Arc<Vocabulary<u32>>,

    // Pre-built Aho-Corasick automaton shared as a base for Lattice indexes
    ac_base: AhoCorasick,
    
    // Pre-built token-trie shared as a base for Expression indexes
    trie_base: TokTrie,

    cursors: Vec<Cursor>,
    eos_id: u32,
    completed: bool,
}

impl Engine {
    pub fn new(
        vocabulary: Arc<Vocabulary<u32>>,
        eos_id: u32,
        columns: HashSet<Column>,
        tables: HashSet<Table>,
    ) -> Option<Self> {
        let ac_base = Lattice::<u32, u32>::base(AhoCorasickKind::ContiguousNFA, vocabulary.clone())?;
        let trie_base = Expression::<u32, u32, FlatDFA<u32, u32>>::base(vocabulary.clone())?;

        let context = Context::new(columns, tables);
        let root_thunk = root();
        let nodes = root_thunk(context);

        let mut engine = Self {
            vocabulary,
            ac_base,
            trie_base,
            cursors: Vec::new(),
            eos_id,
            completed: false,
        };

        engine.cursors = engine.new_cursors(nodes);

        Some(engine)
    }

    pub fn get_token(&self, token_id: u32) -> Option<&str> {
        self.vocabulary.get_token_by_id(token_id)
    }

    pub fn get_token_id(&self, token: &str) -> Option<u32> {
        self.vocabulary.get_id_by_token(token)
    }

    pub fn routes(&self) -> Vec<u32> {
        if self.completed {
            return vec![self.eos_id];
        }

        let mut result = HashSet::new();

        for cursor in &self.cursors {
            if let Some(tokens) = cursor.index.transitions(cursor.node_id) {
                for &token_id in tokens.as_ref() {
                    result.insert(token_id);
                }
            }
        }

        result.into_iter().collect()
    }

    pub fn is_completed(&self) -> bool {
        self.completed
    }

    pub fn feed(&mut self, token_id: u32) {
        let eos_id = self.eos_id;

        self.cursors = self.cursors.drain(..).filter_map(|mut cursor| {
            let has_token = cursor.index.transitions(cursor.node_id)
                .map_or(false, |ts| ts.iter().any(|&t| t == token_id && t != eos_id));

            if !has_token {
                return None;
            }

            let next_id = cursor.index.next(cursor.node_id, token_id)?;
            cursor.node_id = next_id;

            Some(cursor)
        }).collect();

        self.expand();
    }

    fn new_cursors(&self, nodes: Vec<Node>) -> Vec<Cursor> {
        nodes.into_iter().filter_map(|node| {
            let index = CursorIndex::from_state(
                &node.state,
                self.vocabulary.clone(),
                &self.ac_base,
                &self.trie_base,
            )?;

            Some(Cursor {
                index,
                node_id: 0,
                thunk: node.thunk,
                context: node.next_ctx,
            })
        }).collect()
    }

    fn expand(&mut self) {
        let eos_id = self.eos_id;

        let mut queue: Vec<Cursor> = self.cursors.drain(..).collect();
        let mut cursors: Vec<Cursor> = Vec::new();

        loop {
            let mut new_nodes = Vec::new();

            for cursor in queue.drain(..) {
                // Cursors not in an accepting state
                if !cursor.index.is_accepting(cursor.node_id, eos_id) {
                    cursors.push(cursor);

                    continue;
                }

                // Otherwise collect new nodes
                let nodes = (cursor.thunk)(cursor.context.clone());

                if nodes.is_empty() {
                    self.completed = true;
                } else {
                    new_nodes.extend(nodes);
                }

                // If current cursor still accept non-EOS transitions, keep it
                if cursor.index.has_non_eos_transitions(cursor.node_id, eos_id) {
                    cursors.push(cursor);
                }
            }

            if new_nodes.is_empty() {
                break;
            }

            queue = self.new_cursors(new_nodes);
        }

        self.cursors = cursors;
    }
}
