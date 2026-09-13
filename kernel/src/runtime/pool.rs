//! The worker pool, or the lack of one.
//!
//! Every parallel construct the runtime uses goes through here, so that a
//! build without the `parallel` feature is single threaded from top to bottom
//! and needs no threads at all. That is what a WebAssembly target requires:
//! Pyodide loads an extension module into a runtime with no pthreads, and
//! rayon's pool cannot be built there - `ThreadPoolBuilder::build` fails rather
//! than degrading, even when asked for a single worker.
//!
//! With the feature on this is rayon, unchanged. With it off `install` calls
//! the closure where it stands and `join` runs the two in order; the iterator
//! sites are `cfg`'d individually, because a serial `par_iter` cannot be
//! written as a shim - the trait it comes from is the parallelism.

#[cfg(feature = "parallel")]
pub use rayon::join;

#[cfg(feature = "parallel")]
pub type Pool = rayon::ThreadPool;

/// Build a pool of `workers` threads, or `None` if the platform has no threads.
#[cfg(feature = "parallel")]
pub fn build(workers: usize) -> Option<Pool> {
    rayon::ThreadPoolBuilder::new()
        .num_threads(workers.max(1))
        .thread_name(|i| format!("kernel-worker-{i}"))
        .build()
        .ok()
}

/// The serial stand-in: one "worker", which is whoever called.
#[cfg(not(feature = "parallel"))]
pub struct Pool;

#[cfg(not(feature = "parallel"))]
impl Pool {
    /// Rayon's `install` runs the closure inside the pool; here there is no
    /// elsewhere to run it, so it runs here.
    pub fn install<R, F: FnOnce() -> R>(&self, op: F) -> R {
        op()
    }

    pub fn current_num_threads(&self) -> usize {
        1
    }
}

#[cfg(not(feature = "parallel"))]
pub fn build(_workers: usize) -> Option<Pool> {
    Some(Pool)
}

#[cfg(not(feature = "parallel"))]
pub fn join<A, B, RA, RB>(a: A, b: B) -> (RA, RB)
where
    A: FnOnce() -> RA,
    B: FnOnce() -> RB,
{
    (a(), b())
}
