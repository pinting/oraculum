# 5th - Ahead-of-time lattice building for regular expressions using `regex-automata` directly

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

Same as `outlines-core`. The `Index::new` function of Outlines is using linear search to build a token DFA on top of the regular expression byte DFA of `regex-automata`. This strategy is slow, could be improved - and it makes no sense to depend on a library which wraps another library in a couple of hundreds of lines. 583.171892 ms index build time for the example regular expression, 6-18 µs per step. The unanswered question, why build time decreased so much when using the same regular expression engine behind the scenes - perhaps it is due to no memory copy has to be initiated, the same vocabulary data structure is used as it is.

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
