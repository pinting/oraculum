//! A boolean polynomial ring over `GF(2)`: `zdd.rs` is the diagram the
//! polynomial lives in, and this is the ring around it.
//!
//! Not a whole ring - there is no Groebner machinery, no monomial ordering to
//! choose and no division, because all `root.py` asks for is a running product
//! of mutual exclusion constraints and four questions about it.

use rustc_hash::FxHashMap as HashMap;

use crate::algebra::zdd::{NodeId, VarId, Zdd, ONE, ZERO};

/// A support this wide is described rather than expanded - see `render`.
const RENDER_LIMIT: usize = 24;

pub struct Ring {
    names: Vec<String>,
    index: HashMap<String, VarId>,
    zdd: Zdd,
}

impl Ring {
    /// The ring over these variables, in this order, which is the diagram's
    /// variable order, top first.
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
    /// Built from the defining formula rather than the closed form of its
    /// monomials, so the diagram demonstrably holds the polynomial the formula
    /// defines. The `k` inner products each leave out one factor, so
    /// they are taken as a prefix and a suffix meeting at `i`: the same formula
    /// with its common subexpressions shared, `O(k)` rather than `O(k^2)`.
    pub fn mutual_exclusion(&mut self, names: &[String]) -> Option<NodeId> {
        let mut variables: Vec<VarId> = Vec::with_capacity(names.len());

        for name in names {
            variables.push(self.variable(name)?);
        }

        let count: usize = variables.len();

        // `prefix[i]` is the product of `(1 + t_j)` over `j < i`, `suffix[i]`
        // the product over `j > i`.
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

    /// Conjunction: both operands are `0/1` valued, so the product is `AND`.
    pub fn product(&mut self, left: NodeId, right: NodeId) -> NodeId {
        self.zdd.mul(left, right)
    }

    pub fn sum(&mut self, left: NodeId, right: NodeId) -> NodeId {
        self.zdd.xor(left, right)
    }

    pub fn is_zero(&self, poly: NodeId) -> bool {
        poly == ZERO
    }

    /// Substitute `name = 1`. An unknown name constrains nothing.
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

    /// Which of `others` have a non-zero product with `poly`. One call for what
    /// `root.py` asks once per field name after every selection.
    pub fn nonzero(&mut self, poly: NodeId, others: &[NodeId]) -> Vec<bool> {
        others
            .iter()
            .map(|&other| self.zdd.mul(poly, other) != ZERO)
            .collect()
    }

    /// The variables that may still be asserted; any other contradicts the
    /// selection.
    pub fn viable(&mut self, poly: NodeId) -> Vec<bool> {
        (0..self.names.len() as VarId)
            .map(|variable| self.zdd.substitute(poly, variable, true) != ZERO)
            .collect()
    }

    /// Disjunctive normal form, for debug output.
    ///
    /// Shannon expansion over the support, dropping a variable on any branch
    /// that turns out not to depend on it. Worst case exponential in the
    /// support, so an implausibly wide one is described rather than expanded -
    /// this is a trace line, not a result.
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
