# 5th - Ahead-of-time lattice building for regular expressions using `regex-automata` directly

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

This experiment calls `regex-automata` directly without `outlines-core`. In `outlines-core`, `Index::new` builds a token DFA over a byte DFA with linear scans, adding wrapper overhead. By calling `regex-automata` directly and reusing the existing vocabulary structure without extra copies, index construction for the example pattern drops to 583 ms, while step times remain 6 to 18 µs.

## Output

```
Loaded vocabulary in 974.46456ms
Enter regex pattern (press Enter for default): 
Using pattern: (monday|tuesday|wednesday|thursday|friday)+
Built index in 583.171892ms
Current: ``
Time to get routes: 14.42µs
Possible next tokens: ["tu", "m", "mon", "friday", "thur", "wed", "frid", "fr", "fri", "we", "w", "thu", "f", "mond", "th", "mo", "t", "monday"]
Input: we
Current: `we`
Time to get routes: 6.83µs
Possible next tokens: ["d", "dn"]
Input: d
Current: `wed`
Time to get routes: 6.44µs
Possible next tokens: ["nesday", "ne", "n", "nes"]
Input: ne
Current: `wedne`
Time to get routes: 5.63µs
Possible next tokens: ["sd", "s", "sda"]
Input: s
Current: `wednes`
Time to get routes: 6.011µs
Possible next tokens: ["da", "d", "day"]
Input: day
Current: `wednesday`
Time to get routes: 14.231µs
Possible next tokens: ["thur", "th", "mond", "monday", "mon", "we", "tu", "thu", "fr", "frid", "fri", "mo", "friday", "wed", "EOS"]
```
