//! What the runner asks when a head reaches the end of its index.
//!
//! The kernel builds no graph of its own. When a head accepts, it notifies the
//! caller through a `Resolver` and gets back either the drafts of the indexes
//! that may follow - each carrying the payload for the head it will become -
//! or `Terminal`, meaning nothing follows and the generation is complete.
//!
//! The library on the other side owns the modelling: it takes the payload,
//! finds the context it belongs to, applies whatever the head matched, and
//! produces the next drafts. The kernel only has to build them and keep
//! walking.

use crate::runtime::factory::{Draft, IndexId};
use crate::runtime::head::HeadId;

/// What a resolver is told about the head that reached an accepting state.
pub struct Report<'a, P> {
    pub id: HeadId,
    pub index_id: u64,
    pub matched: String,
    pub payload: &'a P,
}

/// Where the index for a new head comes from: one that already exists, or a
/// description of one to build.
pub enum Source {
    Id(IndexId),
    Draft(Draft),
}

/// One index the caller wants walked next.
pub struct Request<P> {
    pub source: Source,
    pub payload: P,
}

impl<P> Request<P> {
    pub fn new(draft: Draft, payload: P) -> Self {
        Self {
            source: Source::Draft(draft),
            payload,
        }
    }

    pub fn existing(index_id: IndexId, payload: P) -> Self {
        Self {
            source: Source::Id(index_id),
            payload,
        }
    }
}

pub enum Expansion<P> {
    /// Nothing follows: this branch has generated everything it can.
    Terminal,

    /// The indexes that may follow. An empty list is a dead end rather than a
    /// completion - the head simply has no children.
    Children(Vec<Request<P>>),
}

pub trait Resolver<P> {
    fn resolve(&self, report: &Report<'_, P>) -> Expansion<P>;

    /// Whether resolution has failed and the runner should stop asking. The
    /// Python binding uses it to abandon a feed once a callback has raised.
    fn aborted(&self) -> bool {
        false
    }
}

/// A resolver that ends every branch, so a runner can be driven without one.
pub struct Terminal;

impl<P> Resolver<P> for Terminal {
    fn resolve(&self, _report: &Report<'_, P>) -> Expansion<P> {
        Expansion::Terminal
    }
}
