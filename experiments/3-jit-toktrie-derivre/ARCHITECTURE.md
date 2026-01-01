# toktrie and derivre

## Two Separate Data Structures

A critical architectural distinction: llguidance uses two independent data structures that work together:

| Structure            | Library   | Purpose                                  |
|----------------------|-----------|------------------------------------------|
| Regex AST / Lazy DFA | `derivre` | Validates byte sequences against pattern |
| Token Trie           | `toktrie` | Organizes vocabulary by shared prefixes  |

The regex AST (derivre) handles efficient validation of individual byte sequences. The token trie (toktrie) organizes the vocabulary to enable sublinear filtering. Neither alone solves the problem - their combination is the key insight.

## The Token Trie Enables Sublinear Vocabulary Filtering

The vocabulary is pre-organized into a prefix trie at initialization time:

```
Root
├─ f
│  └─ r
│     └─ i
│        └─ d
│           └─ a
│              └─ y [TOKEN: "friday"]
├─ m
│  └─ o
│     └─ n
│        ├─ [TOKEN: "mon"]
│        ├─ d
│        │  └─ a
│        │     └─ y [TOKEN: "monday"]
│        ├─ t
│        │  └─ h [TOKEN: "month"]
│        └─ k
│           └─ e
│              └─ y [TOKEN: "monkey"]
├─ t
│  └─ u
│     └─ e
│        └─ s
│           └─ d
│              └─ a
│                 └─ y [TOKEN: "tuesday"]
...
```

When filtering with regex `friday|saturday`:

1. Test byte `f` against regex → **valid state** → continue down subtree
2. Test byte `m` against regex → **dead state**
3. Skip entire `m` subtree (mon, monday, month, monkey) with one pointer increment
4. Test byte `t` → **dead state**
5. Skip entire `t` subtree (tuesday, etc.)

The key insight: when a prefix fails validation, **all tokens sharing that prefix** are invalid. Instead of testing each token individually, we skip them in O(1).

## The subtree_size Field Enables O(1) Skipping

Each trie node is packed into exactly 8 bytes:

```rust
struct TrieNode {
    byte: u8,           // 8 bits - the byte at this node
    num_parents: u8,    // 8 bits - depth for backtracking
    token_id: u24,      // 24 bits - token ID if this is a complete token
    subtree_size: u24,  // 24 bits - THIS IS THE KEY
}
```

The `subtree_size` field stores how many nodes exist in this node's subtree. This enables O(1) subtree skipping:

```rust
fn compute_mask(trie: &[TrieNode], regex: &mut Regex) -> BitVec {
    let mut mask = BitVec::new();
    let mut p = 1;
    
    while p < trie.len() {
        let node = &trie[p];
        
        if regex.try_push(node.byte) {
            if node.token_id != INVALID {
                mask.set(node.token_id, true);
            }

            p += 1;
        } else {
            p += node.subtree_size;

            regex.pop_bytes(node.num_parents - 1);
        }
    }
    mask
}
```

The DFS ordering ensures all descendants are contiguous in memory, so `p += subtree_size` is pure pointer arithmetic.

## derivre's Lazy DFA via Brzozowski Derivatives

The derivre library implements Brzozowski derivatives - where the derivative of regex R with respect to character c produces a new regex matching suffixes: D_c(R) = {w : cw ∈ L(R)}. Key derivative rules:

```
D_c(c) = ε (consuming the expected character succeeds)
D_c(R₁R₂) = D_c(R₁)R₂ | ν(R₁)D_c(R₂) (nullable check for sequences)
D_c(R*) = D_c(R)R* (Kleene star recursion)
D_c(R₁&R₂) = D_c(R₁) & D_c(R₂) (intersection support)
```

Unlike traditional regex engines that convert to NFA then DFA upfront, derivre constructs DFA states lazily on demand. This eliminates startup cost entirely - critical when constraints change per-request.

## StateID via Hash-Consing Enables O(1) State Equality

Each computed derivative becomes an **ExprRef** (equivalent to StateID) - a compact reference into a hash-consed expression store. Identical regex subtrees share storage and can be compared in O(1) via pointer equality. The memoization architecture has three layers:

| Layer                   | Purpose                                            |
|-------------------------|----------------------------------------------------|
| Expression hash-consing | Deduplicate identical regex ASTs                   |
| Transition memoization  | Cache (state, byte) → next_state                   |
| Byte compression        | Group equivalent bytes to shrink transition tables |

When walking the token trie, each `try_push(byte)` involves: fetching lexer state from stack (1 read), optional alphabet compression lookup (1 read), transition table lookup (1 read), and pushing new state (1 write) - just **5 reads and 2 writes per node** in the fast path.

## The Lexer/Parser Split Minimizes Grammar Involvement

LLGuidance uses a two-stage architecture: a **derivre-based lexer** handling regular patterns and an **Earley parser** for context-free grammars. The critical insight is that the parser is consulted in only **0.1-1% of token checks** - lexeme boundaries where grammar transitions occur.

The Earley parser itself is heavily optimized: grammar rules stored in flat arrays, items represented as 32-bit integer pairs, and parser rows reused during trie backtracking rather than recomputed.

## Slicer Optimization Handles Dense Masks Efficiently

For masks allowing many tokens (inside JSON strings, comments, etc.), trie traversal becomes expensive because few subtrees can be pruned. The **slicer** addresses this by segmenting the vocabulary into regex-defined slices with precomputed masks:

```
[^"\\\\\\x00-\\x1F\\x7F]{1,10}   # Short safe JSON string chars
[^"\\\\\\x00-\\x1F\\x7F]{1,30}   # Medium length
[^"\\\\\\x00-\\x1F\\x7F]+        # Any remaining
```

During mask computation, if a slice's defining regex is **contained** in the allowed lexemes (checked via symbolic derivative intersection: R & ~S = ∅), the entire precomputed slice mask is OR'd in without traversal.

## The NextByte Optimization Enables Fast-Forwarding

derivre's `NextByte` enum describes valid continuations from any state:

```rust
pub enum NextByte {
    ForcedByte(u8),
    ForcedEOI,
    SomeBytes0,
    Dead,
}
```

When `ForcedByte` is returned, llguidance can insert tokens without invoking the LLM forward pass at all - guidance acceleration.