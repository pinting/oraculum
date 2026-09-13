//! Walking indexes: what turns a pile of them into a generation.
//!
//! `memory` is one walk over one index, `head` pairs a walk with the caller's
//! payload, `factory` builds the indexes and shares them out, `runner` advances
//! every head over each token, and `resolver` is the single question it asks
//! the caller: what may follow this.
//!
//! `pool` is where the parallelism lives, and the only place that knows whether
//! there is any - without the `parallel` feature the whole runtime is serial,
//! which is what a WebAssembly build needs.

pub mod factory;
pub mod head;
pub mod memory;
pub mod pool;
pub mod resolver;
pub mod runner;
