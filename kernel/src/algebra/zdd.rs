//! Zero-suppressed decision diagrams, and the GF(2) algebra over them.
//!
//! This is the data structure PolyBoRi keeps a boolean polynomial in, rebuilt
//! here without CUDD underneath it. A polynomial over `GF(2)[x1..xn]/(xi^2-xi)`
//! is a sum of squarefree monomials and nothing else, so it is exactly a *set
//! of subsets* of the variables - and a ZDD is the canonical way to hold one.
//!
//! A node is `(var, hi, lo)` and stands for the family
//!
//!     { {var} U S : S in hi }  U  { S : S in lo }
//!
//! with two terminals: `ZERO`, the empty family, which is the polynomial `0`,
//! and `ONE`, the family whose only member is the empty monomial, which is the
//! polynomial `1`. Two reductions make the representation canonical:
//!
//! * **zero suppression** - a node whose `hi` is `ZERO` says nothing, so it is
//!   replaced by its `lo`. This is what makes the diagram small on sparse
//!   families, and it is the whole reason PolyBoRi is a ZDD library rather
//!   than a BDD one;
//! * **hash consing** - `unique` maps a node triple to its id, so structurally
//!   equal diagrams *are* the same id. Equality is then a `u32` comparison,
//!   and so is "is this polynomial zero".
//!
//! Variables are ordered by index, smallest at the top, which is PolyBoRi's
//! lexicographic default. Every node sits strictly above its children.
//!
//! The operations are the recursive ones over that decomposition, each with a
//! memo table that survives between calls. `mul` in particular follows
//! PolyBoRi's `dd_multiply` (`routines/pbori_routines_misc.h`) including its
//! two-call rearrangement of the three cross terms - see the comment there.
//!
//! Nodes are never freed. CUDD reference counts and garbage collects because it
//! is a general purpose library; here the reachable set is the closure of a
//! fixed handful of constraints under multiplication, which is small and does
//! not grow once a schema has been walked a few times. `node_count` is there to
//! confirm that rather than to be acted on.

use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};

/// A polynomial: the id of the diagram node that is its root.
pub type NodeId = u32;

/// A variable, by position in the ring's variable order.
pub type VarId = u32;

/// The empty family - no monomial at all, which is the polynomial `0`.
pub const ZERO: NodeId = 0;

/// The family holding only the empty monomial, which is the polynomial `1`.
pub const ONE: NodeId = 1;

/// The level a terminal is treated as sitting at. Below every real variable, so
/// `min` over a pair always picks out a variable when either side has one.
const TERMINAL: VarId = VarId::MAX;

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct Node {
    var: VarId,
    hi: NodeId,
    lo: NodeId,
}

/// The shared diagram store: every polynomial built through it is a node in
/// here, and two equal polynomials are the same node.
pub struct Zdd {
    nodes: Vec<Node>,
    unique: HashMap<Node, NodeId>,
    xor_cache: HashMap<(NodeId, NodeId), NodeId>,
    mul_cache: HashMap<(NodeId, NodeId), NodeId>,
    subs_cache: HashMap<(NodeId, VarId, bool), NodeId>,
}

impl Zdd {
    pub fn new() -> Self {
        // The terminals occupy ids 0 and 1 so that `ZERO` and `ONE` are
        // constants; their node records are never read.
        let placeholder = Node {
            var: TERMINAL,
            hi: ZERO,
            lo: ZERO,
        };

        Self {
            nodes: vec![placeholder, placeholder],
            unique: HashMap::default(),
            xor_cache: HashMap::default(),
            mul_cache: HashMap::default(),
            subs_cache: HashMap::default(),
        }
    }

    #[inline(always)]
    pub fn is_terminal(&self, f: NodeId) -> bool {
        f <= ONE
    }

    /// The variable `f` branches on, or `TERMINAL` when it branches on nothing.
    #[inline(always)]
    pub fn var(&self, f: NodeId) -> VarId {
        if self.is_terminal(f) {
            TERMINAL
        } else {
            self.nodes[f as usize].var
        }
    }

    #[inline(always)]
    fn hi(&self, f: NodeId) -> NodeId {
        self.nodes[f as usize].hi
    }

    #[inline(always)]
    fn lo(&self, f: NodeId) -> NodeId {
        self.nodes[f as usize].lo
    }

    /// The cofactors of `f` at level `v`, as `(hi, lo)`.
    ///
    /// A diagram that does not branch on `v` has no monomial containing it at
    /// this level, which is `hi = ZERO` - the zero suppression read backwards.
    #[inline(always)]
    fn split(&self, f: NodeId, v: VarId) -> (NodeId, NodeId) {
        if self.var(f) == v {
            (self.hi(f), self.lo(f))
        } else {
            (ZERO, f)
        }
    }

    /// The node for `(var, hi, lo)`, reduced and shared.
    pub fn make(&mut self, var: VarId, hi: NodeId, lo: NodeId) -> NodeId {
        if hi == ZERO {
            return lo;
        }

        let node = Node { var, hi, lo };

        if let Some(&existing) = self.unique.get(&node) {
            return existing;
        }

        let id: NodeId = self.nodes.len() as NodeId;

        self.nodes.push(node);
        self.unique.insert(node, id);

        id
    }

    /// The polynomial that is the single variable `v`.
    pub fn single(&mut self, v: VarId) -> NodeId {
        self.make(v, ONE, ZERO)
    }

    /// `1 + v` - negation, over GF(2).
    pub fn negate(&mut self, v: VarId) -> NodeId {
        self.make(v, ONE, ONE)
    }

    /// Addition, which over GF(2) is the symmetric difference of the monomial
    /// sets: a monomial in both cancels.
    pub fn xor(&mut self, a: NodeId, b: NodeId) -> NodeId {
        if a == b {
            return ZERO;
        }

        if a == ZERO {
            return b;
        }

        if b == ZERO {
            return a;
        }

        let key: (NodeId, NodeId) = if a < b { (a, b) } else { (b, a) };

        if let Some(&cached) = self.xor_cache.get(&key) {
            return cached;
        }

        // Neither side is a terminal here - the only terminals are `ZERO`,
        // handled above, and `ONE`, which would have made `a == b` - so `v` is
        // a real variable.
        let v: VarId = self.var(a).min(self.var(b));
        let (a1, a0) = self.split(a, v);
        let (b1, b0) = self.split(b, v);

        let hi: NodeId = self.xor(a1, b1);
        let lo: NodeId = self.xor(a0, b0);
        let result: NodeId = self.make(v, hi, lo);

        self.xor_cache.insert(key, result);

        result
    }

    /// Multiplication.
    ///
    /// Splitting both sides at the top variable `v` gives `f = v*a1 + a0` and
    /// `g = v*b1 + b0`, and since `v*v = v`,
    ///
    ///     f*g = v*(a1*b1 + a1*b0 + a0*b1) + a0*b0
    ///
    /// Three products for the `hi` branch, except that PolyBoRi's `dd_multiply`
    /// folds two of them into one by multiplying `a1` against `b0 + b1`, which
    /// is what is done here. The two shortcuts it takes on the way - `a0 == a1`
    /// collapsing the sum to `a1*b0`, and `b0 == b1` collapsing it to `a0*b1` -
    /// fall straight out of the same identity over GF(2).
    ///
    /// `f * f = f` because the cross terms pair up and cancel and every
    /// monomial is idempotent, which is the `a == b` case.
    pub fn mul(&mut self, a: NodeId, b: NodeId) -> NodeId {
        if a == ZERO || b == ZERO {
            return ZERO;
        }

        if a == ONE {
            return b;
        }

        if b == ONE {
            return a;
        }

        if a == b {
            return a;
        }

        let key: (NodeId, NodeId) = if a < b { (a, b) } else { (b, a) };

        if let Some(&cached) = self.mul_cache.get(&key) {
            return cached;
        }

        let v: VarId = self.var(a).min(self.var(b));
        let (a1, a0) = self.split(a, v);
        let (b1, b0) = self.split(b, v);

        let lo: NodeId = self.mul(a0, b0);

        let hi: NodeId = if a0 == a1 {
            self.mul(b0, a1)
        } else {
            let first: NodeId = self.mul(a0, b1);

            if b0 == b1 {
                first
            } else {
                let sum: NodeId = self.xor(b0, b1);
                let second: NodeId = self.mul(sum, a1);

                self.xor(first, second)
            }
        };

        let result: NodeId = self.make(v, hi, lo);

        self.mul_cache.insert(key, result);

        result
    }

    /// Substitute `v = 1` (`value` true) or `v = 0` (`value` false).
    ///
    /// At the level of `v` the diagram splits into the monomials that contain
    /// it and those that do not. Setting it to one merges the two halves, which
    /// is an `xor` because the shared monomials cancel; setting it to zero
    /// throws the `hi` half away, which is the `lo` branch on its own.
    pub fn substitute(&mut self, f: NodeId, v: VarId, value: bool) -> NodeId {
        let var: VarId = self.var(f);

        if var > v {
            return f;
        }

        if var == v {
            let (hi, lo) = (self.hi(f), self.lo(f));

            return if value { self.xor(hi, lo) } else { lo };
        }

        let key: (NodeId, VarId, bool) = (f, v, value);

        if let Some(&cached) = self.subs_cache.get(&key) {
            return cached;
        }

        let (hi, lo) = (self.hi(f), self.lo(f));
        let hi: NodeId = self.substitute(hi, v, value);
        let lo: NodeId = self.substitute(lo, v, value);
        let result: NodeId = self.make(var, hi, lo);

        self.subs_cache.insert(key, result);

        result
    }

    /// Whether the all-zero assignment satisfies the polynomial.
    ///
    /// Every variable at zero kills every monomial that mentions one, so what
    /// is left is the constant term - the empty monomial, which lives at the
    /// end of the `lo` chain.
    pub fn holds_empty(&self, f: NodeId) -> bool {
        let mut node: NodeId = f;

        while !self.is_terminal(node) {
            node = self.lo(node);
        }

        node == ONE
    }

    /// The variables the polynomial mentions, ascending.
    pub fn support(&self, f: NodeId) -> Vec<VarId> {
        let mut seen: HashSet<NodeId> = HashSet::default();
        let mut stack: Vec<NodeId> = vec![f];
        let mut found: HashSet<VarId> = HashSet::default();

        while let Some(node) = stack.pop() {
            if self.is_terminal(node) || !seen.insert(node) {
                continue;
            }

            found.insert(self.var(node));

            stack.push(self.hi(node));
            stack.push(self.lo(node));
        }

        let mut support: Vec<VarId> = found.into_iter().collect();

        support.sort_unstable();

        support
    }

    /// The number of monomials, which is the number of paths ending at `ONE`.
    ///
    /// Exponential in the diagram's height and linear in its size, so it says
    /// what the cube and monomial representations would have cost.
    pub fn terms(&self, f: NodeId) -> u128 {
        let mut counted: HashMap<NodeId, u128> = HashMap::default();

        self.count_terms(f, &mut counted)
    }

    fn count_terms(&self, f: NodeId, counted: &mut HashMap<NodeId, u128>) -> u128 {
        if f == ZERO {
            return 0;
        }

        if f == ONE {
            return 1;
        }

        if let Some(&cached) = counted.get(&f) {
            return cached;
        }

        let (hi, lo) = (self.hi(f), self.lo(f));
        let total: u128 = self
            .count_terms(hi, counted)
            .saturating_add(self.count_terms(lo, counted));

        counted.insert(f, total);

        total
    }

    /// Live nodes, terminals included.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn memory_usage(&self) -> usize {
        let mut mem: usize = std::mem::size_of::<Self>();

        mem += self.nodes.capacity() * std::mem::size_of::<Node>();
        mem += self.unique.capacity() * (std::mem::size_of::<Node>() + std::mem::size_of::<NodeId>());
        mem += (self.xor_cache.capacity() + self.mul_cache.capacity())
            * std::mem::size_of::<((NodeId, NodeId), NodeId)>();
        mem += self.subs_cache.capacity() * std::mem::size_of::<((NodeId, VarId, bool), NodeId)>();

        mem
    }
}

impl Default for Zdd {
    fn default() -> Self {
        Self::new()
    }
}
