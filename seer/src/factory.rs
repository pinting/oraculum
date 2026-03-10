use std::marker::PhantomData;
use std::sync::Arc;

use aho_corasick::AhoCorasick;
use fastlines::{DFA, Expression, FlatDFA, Index, Lattice, Number, Vocabulary};
use toktrie::TokTrie;


#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum IndexDraft {
    Lattice(String),
    Expression(String),
}

pub struct IndexFactory<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    vocabulary: Arc<Vocabulary<T>>,
    ac_base: AhoCorasick,
    trie_base: TokTrie,
    _p: PhantomData<(N, D)>,
}

impl<N, T, D> IndexFactory<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    pub fn new(
        vocabulary: Arc<Vocabulary<T>>,
        ac_base: AhoCorasick,
        trie_base: TokTrie,
    ) -> Self {
        Self {
            vocabulary,
            ac_base,
            trie_base,
            _p: PhantomData,
        }
    }

    pub fn create_lattice(&self, word: &str) -> Option<Lattice<N, T>> {
        Lattice::<N, T>::new(word, self.vocabulary.clone(), &self.ac_base)
    }

    pub fn create_expression(&self, pattern: &str) -> Option<Expression<N, T, D>> {
        Expression::<N, T, D>::new(pattern, self.vocabulary.clone(), &self.trie_base)
    }

    pub fn create_index(&self, draft: &IndexDraft) -> Option<Index<N, T, D>> {
        match draft {
            IndexDraft::Lattice(word) => self.create_lattice(word).map(Index::Lattice),
            IndexDraft::Expression(pattern) => self.create_expression(pattern).map(Index::Expression),
        }
    }

    pub fn vocabulary(&self) -> &Vocabulary<T> {
        &self.vocabulary
    }
}
