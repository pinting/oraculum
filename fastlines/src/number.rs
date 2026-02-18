use std::ops::{Add, AddAssign, BitAnd, Div, Mul, Sub};
use std::fmt::Debug;
use std::hash::Hash;

pub trait Number: Copy + Clone + Debug + Hash + Eq + Ord + Sized 
    + Add<Output = Self> 
    + Sub<Output = Self> 
    + Mul<Output = Self> 
    + Div<Output = Self> 
    + AddAssign
    + BitAnd<Output = Self>
    + 'static 
{
    const GOLDEN_RATIO: Self;

    fn max_value() -> Self;
    fn from_usize(v: usize) -> Self;
    fn to_usize(self) -> usize;
    fn wrapping_mul(self, rhs: Self) -> Self;
}

impl Number for u8 {
    const GOLDEN_RATIO: Self = 0x9E;

    #[inline(always)] fn max_value() -> Self { u8::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

impl Number for u16 {
    const GOLDEN_RATIO: Self = 0x9E37;

    #[inline(always)] fn max_value() -> Self { u16::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

impl Number for u32 {
    const GOLDEN_RATIO: Self = 0x9E3779B9;

    #[inline(always)] fn max_value() -> Self { u32::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

impl Number for u64 {
    const GOLDEN_RATIO: Self = 0x9E3779B97F4A7C15;

    #[inline(always)] fn max_value() -> Self { u64::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}

impl Number for u128 {
    const GOLDEN_RATIO: Self = 0x9E3779B97F4A7C15F39CC0605CEDC835;

    #[inline(always)] fn max_value() -> Self { u128::MAX }
    #[inline(always)] fn from_usize(v: usize) -> Self { v as Self }
    #[inline(always)] fn to_usize(self) -> usize { self as usize }
    #[inline(always)] fn wrapping_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
}