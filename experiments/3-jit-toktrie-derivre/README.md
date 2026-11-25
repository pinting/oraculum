# 3rd - Just-in-time lattice generation using `microsoft/toktrie` and `guidance-ai/derivre`

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

This experiment combines `derivre` with `toktrie`. Building the trie for a vocabulary takes 403 ms once. Compiling the example regular expression takes 330 µs. Trie pruning reduces the search space so step times drop to 200 to 500 µs, though it still evaluates more transitions per step than ahead-of-time methods.

## Output

```
Loaded vocabulary in 1.004035966s
Enter regex pattern (press Enter for default): 
Using pattern: (monday|tuesday|wednesday|thursday|friday)+
Built regex in 330.061µs
Built trie in 403.681127ms
Current: ``
Time taken: 486.001µs
Possible next tokens: ["f", "m", "t", "w", "th", "we", "fr", "mo", "mon", "tu", "mond", "thur", "wed", "fri", "thu", "frid", "friday", "monday", "t", "m", "f", "w"]
Input: we
Current: `we`
Time taken: 280.791µs
Possible next tokens: ["d", "dn", "d"]
Input: d
Current: `wed`
Time taken: 207.9µs
Possible next tokens: ["n", "ne", "nes", "nesday", "n"]
Input: ne
Current: `wedne`
Time taken: 260.24µs
Possible next tokens: ["s", "sd", "sda", "s"]
Input: s
Current: `wednes`
Time taken: 275.5µs
Possible next tokens: ["d", "day", "da", "d"]
Input: day
Current: `wednesday`
Time taken: 248.881µs
Possible next tokens: ["f", "m", "t", "w", "th", "we", "fr", "mo", "mon", "tu", "mond", "thur", "wed", "fri", "thu", "frid", "friday", "monday", "t", "m", "f", "w"]
```

## Architecture

### Two separate data structures

llguidance uses two independent data structures that work together:

| Structure            | Library   | Purpose                                  |
|----------------------|-----------|------------------------------------------|
| Regex AST / Lazy DFA | `derivre` | Validates byte sequences against pattern |
| Token Trie           | `toktrie` | Organizes vocabulary by shared prefixes  |

The regex AST (`derivre`) validates individual byte sequences, and the token trie (`toktrie`) organizes the vocabulary for sublinear filtering.

### Sublinear vocabulary filtering with the token trie

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

When filtering with the regex `friday|saturday`:

1. Test byte `f` against the regex: valid state, continue down the subtree.
2. Test byte `m` against the regex: dead state.
3. Skip the entire `m` subtree (`mon`, `monday`, `month`, `monkey`) with one pointer increment.
4. Test byte `t`: dead state.
5. Skip the entire `t` subtree (`tuesday`, etc.).

When a prefix fails validation, every token sharing that prefix is invalid and is skipped in O(1) without testing each token individually.

### O(1) subtree skipping with `subtree_size`

Each trie node is packed into 8 bytes:

```rust
struct TrieNode {
    byte: u8,           // 8 bits - the byte at this node
    num_parents: u8,    // 8 bits - depth for backtracking
    token_id: u24,      // 24 bits - token ID if this is a complete token
    subtree_size: u24,  // 24 bits - THIS IS THE KEY
}
```

The `subtree_size` field stores how many nodes exist in this node's subtree, enabling O(1) subtree skipping:

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

### Lazy DFA construction with Brzozowski derivatives

`derivre` implements Brzozowski derivatives, where the derivative of regex `R` with respect to character `c` produces a new regex matching suffixes: `D_c(R) = {w : cw ∈ L(R)}`. Derivative rules include:

```
D_c(c) = ε (consuming the expected character succeeds)
D_c(R₁R₂) = D_c(R₁)R₂ | ν(R₁)D_c(R₂) (nullable check for sequences)
D_c(R*) = D_c(R)R* (Kleene star recursion)
D_c(R₁&R₂) = D_c(R₁) & D_c(R₂) (intersection support)
```

Unlike traditional regex engines that convert to NFA and then DFA upfront, `derivre` constructs DFA states lazily on demand. Avoiding upfront construction removes startup cost when constraints change per request.

### O(1) state equality via hash-consing

Each computed derivative becomes an `ExprRef` (also called `StateID`), a compact reference into a hash-consed expression store. Identical regex subtrees share storage and can be compared in O(1) via pointer equality. The memoization architecture has three layers:

| Layer                   | Purpose                                            |
|-------------------------|----------------------------------------------------|
| Expression hash-consing | Deduplicate identical regex ASTs                   |
| Transition memoization  | Cache (state, byte) -> next_state                  |
| Byte compression        | Group equivalent bytes to shrink transition tables |

When walking the token trie, each `try_push(byte)` fetches the lexer state from the stack (1 read), performs an optional alphabet compression lookup (1 read), checks the transition table (1 read), and pushes the new state (1 write), totaling 5 reads and 2 writes per node on the fast path.

### Splitting the lexer and parser

llguidance uses a two-stage architecture: a `derivre`-based lexer for regular patterns and an Earley parser for context-free grammars. The parser is consulted in only 0.1% to 1% of token checks, at lexeme boundaries where grammar transitions occur.

The Earley parser stores grammar rules in flat arrays, represents items as 32-bit integer pairs, and reuses parser rows during trie backtracking instead of recomputing them.

### Dense masks and the slicer optimization

For masks allowing many tokens (inside JSON strings, comments, etc.), trie traversal becomes expensive because few subtrees can be pruned. The slicer addresses this by segmenting the vocabulary into regex-defined slices with precomputed masks:

```
[^"\\\\\\x00-\\x1F\\x7F]{1,10}   # Short safe JSON string chars
[^"\\\\\\x00-\\x1F\\x7F]{1,30}   # Medium length
[^"\\\\\\x00-\\x1F\\x7F]+        # Any remaining
```

During mask computation, if a slice's defining regex is contained in the allowed lexemes (checked via symbolic derivative intersection: `R & ~S = ∅`), the entire precomputed slice mask is OR'd in without traversal.

### Fast-forwarding with `NextByte`

`derivre`'s `NextByte` enum describes valid continuations from any state:

```rust
pub enum NextByte {
    ForcedByte(u8),
    ForcedEOI,
    SomeBytes0,
    Dead,
}
```

When `NextByte` returns `ForcedByte`, llguidance inserts the forced tokens directly without running an LLM forward pass.
