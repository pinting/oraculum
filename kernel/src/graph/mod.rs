//! The graph half of the modelling layer.
//!
//! One structure, `Multigraph`: undirected, parallel edges allowed, labels
//! opaque, and contraction as its only mutation. That last restriction is what
//! lets a copy cost nothing, which is the operation join resolution spends all
//! its time on.

pub mod multigraph;
