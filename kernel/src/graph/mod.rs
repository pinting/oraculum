//! The graph half of the modelling layer.
//!
//! One structure: undirected, parallel edges allowed, labels opaque, and
//! contraction as its only mutation - which is what lets a copy cost nothing.

pub mod multigraph;
