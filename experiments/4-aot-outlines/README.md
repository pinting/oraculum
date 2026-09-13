# 4th - Ahead-of-time lattice building for regular expressions using `dottxt-ai/outlines-core`

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

Prebuilt-based regex matching with precomputed token patterns. The obvious weakness are the increased memory usage for storing the index and the higher upfront cost: 211.950862 ms vocabulary rebuild (one time) and 1.190878411 s index build for the example regular expression. Its strength is its exceptional runtime efficiency, 6-18 µs per step.

## Output

```
Loaded vocabulary in 804.465193ms
Built outlines vocabulary in 211.950862ms
Enter regex pattern (press Enter for default): 
Using pattern: (monday|tuesday|wednesday|thursday|friday)+
Built index in 1.190878411s
Current: ``
Time to get routes: 17.55µs
Possible next tokens: ["thu", "wed", "fri", "t", "fr", "mond", "thur", "frid", "tu", "th", "w", "m", "mo", "f", "mon", "friday", "we", "monday"]
Input: we
Current: `we`
Time to get routes: 6.71µs
Possible next tokens: ["dn", "d"]
Input: d
Current: `wed`
Time to get routes: 8.19µs
Possible next tokens: ["nes", "ne", "nesday", "n"]
Input: ne
Current: `wedne`
Time to get routes: 7.13µs
Possible next tokens: ["s", "sda", "sd"]
Input: s
Current: `wednes`
Time to get routes: 6.93µs
Possible next tokens: ["day", "d", "da"]
Input: day
Current: `wednesday`
Time to get routes: 15.06µs
Possible next tokens: ["monday", "wed", "fri", "fr", "mond", "frid", "thur", "tu", "th", "mo", "mon", "EOS", "friday", "we", "thu"]
```
