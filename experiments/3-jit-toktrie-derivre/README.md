# 3rd - Just-in-time lattice generation using `microsoft/toktrie` and `guidance-ai/derivre`

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

Hybrid approach combining derivre and toktrie. 403 ms trie building (one time for a given vocabulary), 330 µs build time for the example regular expression. Moderate efficiency through trie pruning, 200-500 µs per step. Its weakness is the still relatively high transition attempts compared to AOT-based methods.

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

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the two libraries fit together.
