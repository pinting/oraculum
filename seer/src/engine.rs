use std::borrow::Cow;
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, OnceLock};

use aho_corasick::AhoCorasickKind;
use fastlines::{DFA, Expression, FlatDFA, Index, Accepting, Lattice, Number, Vocabulary};
use toktrie::TokTrie;

use crate::context::Context;
use crate::factory::{IndexDraft, IndexFactory};
use crate::graph::root;

pub type Selector = Option<Arc<dyn Fn(Arc<Context>, String) -> Arc<Context> + Send + Sync>>;
pub type ThunkFn = Arc<dyn Fn(Arc<Context>) -> Vec<Node> + Send + Sync>;

#[derive(Clone)]
pub struct Thunk(ThunkState);

#[derive(Clone)]
enum ThunkState {
    Terminal,
    Ready(ThunkFn),
    Deferred(Arc<dyn Fn() -> Thunk + Send + Sync>, Arc<OnceLock<ThunkFn>>),
}

impl Thunk {
    pub fn terminal() -> Thunk {
        Thunk(ThunkState::Terminal)
    }

    pub fn new(f: impl Fn(Arc<Context>) -> Vec<Node> + Send + Sync + 'static) -> Thunk {
        Thunk(ThunkState::Ready(Arc::new(f)))
    }

    pub fn deferred(f: impl Fn() -> Thunk + Send + Sync + 'static) -> Thunk {
        Thunk(ThunkState::Deferred(Arc::new(f), Arc::new(OnceLock::new())))
    }

    pub fn call(&self, ctx: Arc<Context>) -> Option<Vec<Node>> {
        match &self.0 {
            ThunkState::Terminal => None,
            ThunkState::Ready(f) => Some(f(ctx)),
            ThunkState::Deferred(factory, cell) => {
                let f = cell.get_or_init(|| {
                    match (factory)().0 {
                        ThunkState::Ready(f) => f,
                        ThunkState::Terminal => return Arc::new(|_| vec![]),
                        ThunkState::Deferred(..) => panic!("deferred returned deferred"),
                    }
                });

                Some(f(ctx))
            }
        }
    }
}

pub struct Node {
    draft: IndexDraft,
    ctx: Arc<Context>,
    selector: Selector,
    thunk: Thunk,
}

impl Node {
    pub fn new(draft: IndexDraft, ctx: Arc<Context>, selector: Selector, thunk: Thunk) -> Node {
        return Node {
            draft,
            ctx,
            selector,
            thunk
        }
    }
}

struct Cursor<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    rule: String,
    vocabulary: Arc<Vocabulary<T>>,
    index: Index<N, T, D>,
    head: N,
    ctx: Arc<Context>,
    thunk: Thunk,
    selector: Selector,
    tokens: Vec<T>,
}

impl<N, T, D> Cursor<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    fn from_nodes(vocabulary: &Arc<Vocabulary<T>>, factory: &IndexFactory<N, T, D>, nodes: Vec<Node>) -> Vec<Cursor<N, T, D>> {
        nodes.into_iter().filter_map(|node| {
            let index = factory.create_index(&node.draft)?;
            let rule: String;

            match node.draft {
                IndexDraft::Expression(pattern) => {
                    rule = pattern;
                }

                IndexDraft::Lattice(word) => {
                    rule = word;
                }
            }

            Some(Cursor {
                rule,
                vocabulary: vocabulary.clone(),
                index,
                head: N::from_usize(0),
                ctx: node.ctx,
                thunk: node.thunk,
                selector: node.selector,
                tokens: Vec::new(),
            })
        }).collect()
    }

    fn feed(&mut self, token_id: T) -> Option<()> {
        let node_id = self.index.next(self.head, token_id)?;

        self.head = node_id;
        self.tokens.push(token_id);

        Some(())
    }

    fn matched(&self) -> String {
        self.tokens.iter()
            .filter_map(|&id| self.vocabulary.get_token_by_id(id))
            .collect()
    }

    fn expand(&self) -> Option<Vec<Node>> {
        let selector = self.selector.clone();

        let ctx = match &selector {
            Some(selector) => (selector)(self.ctx.clone(), self.matched()),
            None => self.ctx.clone(),
        };

        self.thunk.call(ctx)
    }

    fn transitions(&self) -> Option<Cow<'_, [T]>> {
        self.index.transitions(self.head)
    }

    fn accepting(&self) -> Accepting {
        self.index.accepting(self.head)
    }
}

pub struct Engine<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    vocabulary: Arc<Vocabulary<T>>,
    factory: Arc<IndexFactory<N, T, D>>,
    cursors: Vec<Cursor<N, T, D>>,
    accepting: bool,
    tokens: Vec<T>,
}

impl<N, T, D> Engine<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    pub fn new(
        vocabulary: Arc<Vocabulary<T>>,
        tables: HashMap<String, Vec<String>>,
        thunk: Thunk,
    ) -> Option<Self> {
        let ac_base = Lattice::<N, T>::base(AhoCorasickKind::ContiguousNFA, vocabulary.clone())?;
        let trie_base = Expression::<N, T, D>::base(vocabulary.clone())?;

        let factory = IndexFactory::<N, T, D>::new(vocabulary.clone(), ac_base, trie_base);
        let context = Context::new(tables);

        let factory = Arc::new(factory);
        let context = Arc::new(context);
        let nodes = thunk.call(context)?;

        let cursors = Cursor::from_nodes(&vocabulary, &factory, nodes);

        Some(Self {
            vocabulary,
            factory,
            cursors,
            accepting: false,
            tokens: Vec::new(),
        })
    }

    pub fn routes(&self) -> Vec<T> {
        let mut result = HashSet::new();

        for cursor in &self.cursors {
            if let Some(tokens) = cursor.transitions() {
                for &token_id in tokens.as_ref() {
                    result.insert(token_id);
                }
            }
        }

        result.into_iter().collect()
    }

    pub fn get_token(&self, token_id: T) -> Option<&str> {
        self.vocabulary.get_token_by_id(token_id)
    }

    pub fn get_token_id(&self, token: &str) -> Option<T> {
        self.vocabulary.get_id_by_token(token)
    }

    pub fn is_completed(&self) -> bool {
        self.accepting
    }

    pub fn feed(&mut self, token_id: T) -> Option<()> {
        let mut queue: Vec<Cursor<N, T, D>> = self.cursors
            .drain(..)
            .filter_map(|mut cursor| {
                cursor.feed(token_id)?;

                Some(cursor)
            })
            .collect();

        if queue.len() == 0 {
            return None
        }

        self.tokens.push(token_id);

        let mut new_cursors: Vec<Cursor<N, T, D>> = Vec::new();

        loop {
            let mut new_nodes = Vec::new();

            for cursor in queue.drain(..) {
                match cursor.accepting() {
                    Accepting::No => {
                        new_cursors.push(cursor);

                        continue
                    }

                    Accepting::Yes(is_more) => {
                        let nodes = cursor.expand();

                        if nodes.is_none() {
                            self.accepting = true;

                            continue;
                        }

                        let nodes = nodes.unwrap_or_default();

                        new_nodes.extend(nodes);

                        if is_more {
                            new_cursors.push(cursor);
                        }
                    }
                }
            }

            if new_nodes.is_empty() {
                break;
            }

            queue = Cursor::from_nodes(&self.vocabulary, &self.factory, new_nodes);
        }

        self.cursors = new_cursors;

        Some(())
    }

    pub fn matched(&self) -> String {
        self.tokens.iter()
            .filter_map(|&id| self.vocabulary.get_token_by_id(id))
            .collect()
    }
}