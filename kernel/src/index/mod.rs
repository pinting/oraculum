//! The languages an index can be, and the composition over them.
//!
//! `Lattice` and `Expression` are the flat indexes, addressed by a node id and
//! reached through `BaseIndex`; `Group` is the subtraction built over them.
//! `Unit` is the sum of the two, and is what the factory hands out ids for.

pub mod lattice;
pub mod expression;
pub mod index;
pub mod group;
pub mod unit;

#[cfg(feature = "pyo3")]
pub mod pylattice;

#[cfg(feature = "pyo3")]
pub mod pyexpression;
