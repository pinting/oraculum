//! Boolean polynomials over `GF(2)`, held as zero-suppressed decision diagrams.
//!
//! `zdd` is the diagram and the algebra over it - a port of the representation
//! PolyBoRi gives SageMath's `BooleanPolynomialRing`, without CUDD underneath.
//! `ring` is the ring around it: the variable names and the handful of
//! constructions and queries a mutual exclusion model needs.

pub mod ring;
pub mod zdd;
