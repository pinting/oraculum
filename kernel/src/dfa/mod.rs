//! Transition table layouts for `Expression`.
//!
//! Each of these answers the same two questions -- where does this token lead
//! from this node, and which tokens lead anywhere -- and differs only in how
//! the table is stored. `FlatDFA` is what the crate is built with;
//! `src/bin/benchmark.rs` is what decided that.

pub mod dfa;
pub mod doublehashdfa;
pub mod flatdfa;
pub mod fasthashdfa;
