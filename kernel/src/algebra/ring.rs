//! A boolean polynomial ring, in the shape SageMath's `BooleanPolynomialRing`
//! has it.
//!
//! SageMath's ring is a wrapper over PolyBoRi, which holds each polynomial as a
//! ZDD over the monomials; `zdd.rs` is that diagram and this is the ring around
//! it - the variable names, the constructions and the queries. The port is not
//! of the whole ring: there is no Groebner machinery, no monomial ordering to
//! choose and no division, because the only thing asked of the algebra here is
//! the one asked of it in `root.py`:
//!
//! > a running product of mutual exclusion constraints, and four questions
//! > about it - is it zero, does the all-zero assignment satisfy it, which
//! > variables does it still depend on, and what happens if this one is one.
//!
//! **Why a ZDD rather than a list of monomials.** The constraint a field name
//! contributes is "exactly one of the `k` tables it lives in":
//!
//!     SUM_i t_i * PRODUCT_(j != i) (1 + t_j)
//!
//! Expanded, a monomial over a subset `S` of those variables appears once per
//! element of `S`, so over GF(2) it survives exactly when `|S|` is odd: the
//! normal form has `2^(k-1)` monomials. A column called `id` lives in every
//! table there is, so `k` is the table count and that number is the whole
//! problem. The ZDD for "every odd subset" is two nodes per level - it is
//! linear in `k` - which is what makes holding the polynomial itself, rather
//! than a hand-rolled stand-in for it, affordable.
//!
//! **What is not ported.** `render` is DNF over the satisfying assignments,
//! which SageMath reaches by handing the polynomial's string form to sympy.
//! Nothing here needs sympy: the DNF is a Shannon expansion over the diagram's
//! own support, which `substitute` already provides. It is debug output, and
//! the only place the three backends are allowed to differ in spelling.

use rustc_hash::FxHashMap as HashMap;

use crate::algebra::zdd::{NodeId, VarId, Zdd, ONE, ZERO};

/// A support this wide is not rendered term by term - see `render`.
const RENDER_LIMIT: usize = 24;

pub struct Ring {
    names: Vec<String>,
    index: HashMap<String, VarId>,
    zdd: Zdd,
}

impl Ring {
    /// The ring over these variables, in this order.
    ///
    /// The order is the diagram's variable order, top first. Callers hand the
    /// table names in sorted order, which keeps a ring reproducible across runs
    /// and so keeps the node ids reproducible too.
    pub fn new<I, S>(names: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        let names: Vec<String> = names.into_iter().map(Into::into).collect();
        let mut index: HashMap<String, VarId> = HashMap::default();

        for (position, name) in names.iter().enumerate() {
            index.entry(name.clone()).or_insert(position as VarId);
        }

        Self {
            names,
            index,
            zdd: Zdd::new(),
        }
    }

    pub fn variables(&self) -> &[String] {
        &self.names
    }

    pub fn variable(&self, name: &str) -> Option<VarId> {
        self.index.get(name).copied()
    }

    pub fn one(&self) -> NodeId {
        ONE
    }

    pub fn zero(&self) -> NodeId {
        ZERO
    }

    /// `SUM_i t_i * PRODUCT_(j != i) (1 + t_j)` - exactly one of `names` is on.
    ///
    /// Built from the defining formula rather than from the closed form of its
    /// monomials, so what the diagram holds is demonstrably the polynomial
    /// SageMath would have built.
    ///
    /// The `k` inner products overlap almost entirely - each leaves out one
    /// factor - so they are taken as a prefix and a suffix meeting at `i`,
    /// which is the same formula with its common subexpressions shared and
    /// `O(k)` multiplications rather than `O(k^2)`.
    ///
    /// `None` when a name is not a variable of the ring.
    pub fn mutual_exclusion(&mut self, names: &[String]) -> Option<NodeId> {
        let mut variables: Vec<VarId> = Vec::with_capacity(names.len());

        for name in names {
            variables.push(self.variable(name)?);
        }

        let count: usize = variables.len();

        // `prefix[i]` is the product of `(1 + t_j)` for every `j < i`, and
        // `suffix[i]` the product for every `j > i`.
        let mut prefix: Vec<NodeId> = vec![ONE; count + 1];
        let mut suffix: Vec<NodeId> = vec![ONE; count + 1];

        for (i, &off) in variables.iter().enumerate() {
            let negated: NodeId = self.zdd.negate(off);

            prefix[i + 1] = self.zdd.mul(prefix[i], negated);
        }

        for (i, &off) in variables.iter().enumerate().rev() {
            let negated: NodeId = self.zdd.negate(off);

            suffix[i] = self.zdd.mul(suffix[i + 1], negated);
        }

        let mut constraint: NodeId = ZERO;

        for (i, &on) in variables.iter().enumerate() {
            let single: NodeId = self.zdd.single(on);
            let others: NodeId = self.zdd.mul(prefix[i], suffix[i + 1]);
            let term: NodeId = self.zdd.mul(single, others);

            constraint = self.zdd.xor(constraint, term);
        }

        Some(constraint)
    }

    /// Conjunction. Both operands are `0/1` valued, so the product is `AND`.
    pub fn product(&mut self, left: NodeId, right: NodeId) -> NodeId {
        self.zdd.mul(left, right)
    }

    pub fn sum(&mut self, left: NodeId, right: NodeId) -> NodeId {
        self.zdd.xor(left, right)
    }

    pub fn is_zero(&self, poly: NodeId) -> bool {
        poly == ZERO
    }

    /// Substitute `name = 1`. An unknown name constrains nothing, so the
    /// polynomial comes back unchanged - which is what both other backends do.
    pub fn assume(&mut self, poly: NodeId, name: &str) -> NodeId {
        match self.variable(name) {
            Some(variable) => self.zdd.substitute(poly, variable, true),
            None => poly,
        }
    }

    /// The variables the polynomial actually depends on.
    pub fn constrained(&self, poly: NodeId) -> Vec<&str> {
        self.zdd
            .support(poly)
            .into_iter()
            .map(|variable| self.names[variable as usize].as_str())
            .collect()
    }

    pub fn holds_empty(&self, poly: NodeId) -> bool {
        self.zdd.holds_empty(poly)
    }

    /// Which of `others` have a non-zero product with `poly`.
    ///
    /// One call for what `root.py` asks once per field name after every
    /// selection. The products share a memo table, so the run costs rather less
    /// than the same number of separate multiplications, and - the point of
    /// doing it here at all - it costs one crossing of the language boundary
    /// rather than two per field.
    pub fn nonzero(&mut self, poly: NodeId, others: &[NodeId]) -> Vec<bool> {
        others
            .iter()
            .map(|&other| self.zdd.mul(poly, other) != ZERO)
            .collect()
    }

    /// The variables that may still be asserted: those `assume` leaves
    /// something behind. Asserting any other one contradicts the selection.
    pub fn viable(&mut self, poly: NodeId) -> Vec<bool> {
        (0..self.names.len() as VarId)
            .map(|variable| self.zdd.substitute(poly, variable, true) != ZERO)
            .collect()
    }

    /// Disjunctive normal form, for debug output.
    ///
    /// Shannon expansion over the support: at each variable the function splits
    /// into what it is with that variable on and what it is with it off, and a
    /// branch that turns out not to depend on the variable drops it rather than
    /// writing both polarities. Terms are sorted so two runs print alike.
    ///
    /// The expansion is worst case exponential in the support, so a polynomial
    /// with an implausibly wide one is described rather than expanded - this is
    /// a trace line, not a result.
    pub fn render(&mut self, poly: NodeId) -> String {
        if poly == ZERO {
            return "False".to_string();
        }

        if poly == ONE {
            return "True".to_string();
        }

        let support: Vec<VarId> = self.zdd.support(poly);

        if support.len() > RENDER_LIMIT {
            return format!(
                "<{} terms over {} variables>",
                self.zdd.terms(poly),
                support.len()
            );
        }

        let mut terms: Vec<String> = Vec::new();
        let mut literals: Vec<(VarId, bool)> = Vec::new();

        self.expand(poly, &support, 0, &mut literals, &mut terms);

        terms.sort_unstable();

        terms.join(" | ")
    }

    fn expand(
        &mut self,
        poly: NodeId,
        support: &[VarId],
        depth: usize,
        literals: &mut Vec<(VarId, bool)>,
        terms: &mut Vec<String>,
    ) {
        if poly == ZERO {
            return;
        }

        if poly == ONE || depth == support.len() {
            terms.push(self.term(literals));

            return;
        }

        let variable: VarId = support[depth];
        let on: NodeId = self.zdd.substitute(poly, variable, true);
        let off: NodeId = self.zdd.substitute(poly, variable, false);

        if on == off {
            // The function does not look at this variable on this branch.
            self.expand(on, support, depth + 1, literals, terms);

            return;
        }

        for (branch, value) in [(on, true), (off, false)] {
            literals.push((variable, value));
            self.expand(branch, support, depth + 1, literals, terms);
            literals.pop();
        }
    }

    fn term(&self, literals: &[(VarId, bool)]) -> String {
        if literals.is_empty() {
            return "True".to_string();
        }

        let mut written: Vec<String> = literals
            .iter()
            .map(|&(variable, value)| {
                let name: &str = &self.names[variable as usize];

                if value {
                    name.to_string()
                } else {
                    format!("~{name}")
                }
            })
            .collect();

        written.sort_unstable();

        written.join(" & ")
    }

    /// How many monomials the polynomial has - what a list of them would cost.
    pub fn terms(&self, poly: NodeId) -> u128 {
        self.zdd.terms(poly)
    }

    pub fn node_count(&self) -> usize {
        self.zdd.node_count()
    }

    pub fn memory_usage(&self) -> usize {
        let mut mem: usize = std::mem::size_of::<Self>();

        mem += self.zdd.memory_usage();
        mem += self.names.capacity() * std::mem::size_of::<String>();

        for name in &self.names {
            mem += name.capacity() * 2;
        }

        mem
    }
}
