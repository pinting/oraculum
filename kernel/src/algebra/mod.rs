//! Boolean polynomials over `GF(2)`, held as zero-suppressed decision diagrams.
//!
//! `zdd` is the diagram and the algebra over it - the representation PolyBoRi
//! uses, without CUDD underneath. `ring` is the ring around it.

pub mod ring;
pub mod zdd;
