use crate::dfa::dfa::DFA;
use crate::index::group::Group;
use crate::index::index::Index;
use crate::number::Number;

/// Everything the factory can hand out an id for.
///
/// A `Unit` is either a flat index - a `Lattice` or an `Expression`, addressed
/// by a node id, unchanged from when they were the whole library - or a
/// `Group` built over other units. The split matters because only a flat index
/// answers `next`/`transitions`/`accepting` from a node id alone; a group has
/// to walk each of its members, which is a job for `Memory`.
pub enum Unit<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    Index(Index<N, T, D>),
    Group(Group<N, T, D>),
}

impl<N, T, D> Unit<N, T, D>
where
    N: Number,
    T: Number,
    D: DFA<N, T>,
{
    pub fn is_group(&self) -> bool {
        matches!(self, Self::Group(_))
    }

    pub fn node_count(&self) -> N {
        match self {
            Self::Index(index) => index.node_count(),
            Self::Group(group) => group.node_count(),
        }
    }

    pub fn memory_usage(&self) -> usize {
        match self {
            Self::Index(index) => index.memory_usage(),
            Self::Group(group) => group.memory_usage(),
        }
    }
}
