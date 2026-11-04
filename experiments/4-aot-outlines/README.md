# 4th - Ahead-of-time lattice building for regular expressions using `dottxt-ai/outlines-core`

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

This experiment precomputes token patterns for regex matching using `outlines-core`. Upfront cost is higher: preparing the vocabulary takes 212 ms once, and compiling the index for the example pattern takes 1.19 s, using additional memory. In exchange, step time drops to 6 to 18 µs.

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
