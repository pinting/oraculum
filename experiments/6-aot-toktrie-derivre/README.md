# 6th - Ahead-of-time lattice building for regular expressions using `microsoft/toktrie` and `guidance-ai/derivre`

Measured over the Gemma 3 vocabulary with the regular expression
`(monday|tuesday|wednesday|thursday|friday)+`, feeding the tokens
`we -> d -> ne -> s -> day`.

This experiment combines ahead-of-time index compilation with `toktrie` and `derivre`. Initial trie generation takes 400 ms once per vocabulary. Building an index for the example pattern takes only 4.33 ms, and step evaluation takes 7 to 21 µs while matching the same token count per step as Outlines.

## Output

```
Loaded vocabulary in 786.150486ms
Built trie in 399.975656ms
Enter regex pattern (press Enter for default): 
Using pattern: (monday|tuesday|wednesday|thursday|friday)+
Built index in 4.334894ms
Current: ``
Time taken: 14.55µs
Possible next tokens: ["thu", "monday", "w", "wed", "fri", "fr", "mond", "frid", "thur", "t", "tu", "m", "th", "w", "m", "mo", "f", "mon", "f", "friday", "we", "t"]
Input: we
Current: `we`
Time taken: 7.4µs
Possible next tokens: ["d", "dn", "d"]
Input: d
Current: `wed`
Time taken: 9.58µs
Possible next tokens: ["ne", "n", "nes", "nesday", "n"]
Input: ne
Current: `wedne`
Time taken: 7.61µs
Possible next tokens: ["s", "s", "sda", "sd"]
Input: s
Current: `wednes`
Time taken: 6.9µs
Possible next tokens: ["day", "d", "d", "da"]
Input: day
Current: `wednesday`
Time taken: 21.28µs
Possible next tokens: ["thu", "friday", "w", "wed", "fri", "fr", "mond", "frid", "thur", "monday", "t", "tu", "m", "th", "w", "m", "mo", "f", "mon", "EOS", "f", "we", "t"]
```
