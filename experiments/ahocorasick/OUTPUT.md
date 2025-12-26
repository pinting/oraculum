# Output of the Aho-Corasick experiment

```
Loaded vocabulary in 970.950215ms
Built graph in 2.230516805s
Define constant: 
I love elephants!
Constructed the token lattice in 102.27µs
Current: ``
Number of possible transitions: 2
Possible next tokens: ["I", "I"]
Input: I
Current: `I`
Number of possible transitions: 6
Possible next tokens: [" love", " lov", " lo", " l", " ", " "]
Input:  love
Current: `I love`
Number of possible transitions: 7
Possible next tokens: [" elephants", " elephant", " ele", " el", " e", " ", " "]
Input:  
Current: `I love `
Number of possible transitions: 5
Possible next tokens: ["elephant", "ele", "el", "e", "e"]
Input: ele     
Current: `I love ele`
Number of possible transitions: 7
Possible next tokens: ["phants", "phant", "phan", "pha", "ph", "p", "p"]
Input: phants
Current: `I love elephants`
Number of possible transitions: 2
Possible next tokens: ["!", "!"]
Input: !
Current: `I love elephants!`
```