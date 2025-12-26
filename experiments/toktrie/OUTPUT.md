# Output of the outlines experiment

```
Loaded vocabulary in 1.016819421s
Enter regex pattern (press Enter for default weekdays): 
Using pattern: monday|tuesday|wednesday|thursday|friday
Built regex in 261.561µs
Built trie in 408.583105ms
Current: ``
Number of transition attempts: 519
Possible next tokens: ["f", "m", "t", "w", "th", "we", "fr", "mo", "mon", "tu", "mond", "thur", "wed", "fri", "thu", "frid", "friday", "monday", "t", "m", "f", "w"]
Input: m     
Current: `m`
Number of transition attempts: 357
Possible next tokens: ["o", "on", "ond", "onday", "onda", "o"]
Input: on
Current: `mon`
Number of transition attempts: 355
Possible next tokens: ["d", "day", "da", "d"]
Input: d
Current: `mond`
Number of transition attempts: 334
Possible next tokens: ["a", "ay", "a"]
Input: ay
Current: `monday`
```