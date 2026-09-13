# 2nd - Just-in-time lattice generation using only `guidance-ai/derivre`

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

Pure regex-based matching with derivative automata. 257 µs build time for the example regular expression. Slow next token filtering because of the exhaustive token matching, around 39 ms per step.

## Output

```
Loaded vocabulary in 1.006405324s
Enter regex pattern (press Enter for default): 
Using pattern: (monday|tuesday|wednesday|thursday|friday)+
Built regex in 257.41µs
Current: ``
Time taken: 39.245095ms
Possible next tokens: ["f", "m", "t", "w", "th", "we", "fr", "mo", "mon", "tu", "mond", "thur", "wed", "fri", "thu", "frid", "friday", "monday", "t", "m", "f", "w"]
Input: we
Current: `we`
Time taken: 39.012464ms
Possible next tokens: ["d", "dn", "d"]
Input: d
Current: `wed`
Time taken: 38.910822ms
Possible next tokens: ["n", "ne", "nes", "nesday", "n"]
Input: ne
Current: `wedne`
Time taken: 38.987573ms
Possible next tokens: ["s", "sd", "sda", "s"]
Input: s
Current: `wednes`
Time taken: 39.262623ms
Possible next tokens: ["d", "day", "da", "d"]
Input: day
Current: `wednesday`
Time taken: 39.482404ms
Possible next tokens: ["f", "m", "t", "w", "th", "we", "fr", "mo", "mon", "tu", "mond", "thur", "wed", "fri", "thu", "frid", "friday", "monday", "t", "m", "f", "w"]
```
