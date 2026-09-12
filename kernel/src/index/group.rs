use std::sync::Arc;

use crate::dfa::dfa::DFA;
use crate::index::unit::Unit;
use crate::number::Number;

/// A language subtraction: one inclusion minus any number of exclusions.
///
/// From the outside a group is just another index -- it is fed the same tokens
/// and asked the same questions -- but it accepts a word only when the
/// inclusion accepts it and no exclusion does. That is what alias resolution
/// needs: an identifier is a legal alias unless it happens to spell a reserved
/// word, a table name or a field name.
///
/// The members are `Unit`s rather than flat indexes, so an inclusion or an
/// exclusion may itself be a group.
///
/// A group carries no position of its own: the walk over its members lives in
/// `Memory`, which is what lets one immutable group back any number of heads.
pub struct Group<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    include: Arc<Unit<N, T, D>>,
    excludes: Vec<Arc<Unit<N, T, D>>>,
    eos_id: T,
}

impl<N, T, D> Group<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    pub fn new(include: Arc<Unit<N, T, D>>, excludes: Vec<Arc<Unit<N, T, D>>>, eos_id: T) -> Self {
        Self {
            include,
            excludes,
            eos_id,
        }
    }

    #[inline(always)]
    pub fn include(&self) -> &Arc<Unit<N, T, D>> {
        &self.include
    }

    #[inline(always)]
    pub fn excludes(&self) -> &[Arc<Unit<N, T, D>>] {
        &self.excludes
    }

    /// The terminating token id, needed to keep a blocked group from ending.
    #[inline(always)]
    pub fn eos_id(&self) -> T {
        self.eos_id
    }

    pub fn node_count(&self) -> N {
        self.include.node_count()
    }

    /// An upper bound: members are shared, so a member counted here may well be
    /// counted again by another group.
    pub fn memory_usage(&self) -> usize {
        let mut mem = std::mem::size_of::<Self>();

        mem += self.excludes.capacity() * std::mem::size_of::<Arc<Unit<N, T, D>>>();
        mem += self.include.memory_usage();

        for exclude in &self.excludes {
            mem += exclude.memory_usage();
        }

        mem
    }
}
