/*
 * DRAFT of the Aho-Corasick algorithm for learning purposes
 */

package main

import (
	"fmt"
	"strings"
)

type Node struct {
	c byte

	children    map[byte]*Node
	patternIdxs []int

	suffix     *Node
	dictSuffix *Node
}

func NewNode(c byte) *Node {
	return &Node{
		c:        c,
		children: make(map[byte]*Node),
	}
}

func (n *Node) string(b *strings.Builder, route []byte) {
	route = append(route, n.c)

	if len(n.patternIdxs) != 0 {
		for _, c := range route {
			b.WriteByte(c)
			b.WriteByte(' ')
		}

		b.WriteByte('\n')
	}

	for _, child := range n.children {
		child.string(b, route)
	}
}

func (n *Node) String() string {
	b := strings.Builder{}

	n.string(&b, []byte{})

	return b.String()
}

type Queue []*Node

func Build(patterns []string) *Node {
	root := NewNode('#')

	// 1. Build the Trie
	for i, p := range patterns {
		node := root

		for j := 0; j < len(p); j += 1 {
			c := p[j]

			if _, exists := node.children[c]; !exists {
				node.children[c] = NewNode(c)
			}

			node = node.children[c]
		}

		node.patternIdxs = append(node.patternIdxs, i)
	}

	// 2. Build Suffix and DictSuffix Links using BFS
	root.suffix = root

	queue := Queue{}

	// Initialize depth 1 nodes: their suffix is always root
	for _, child := range root.children {
		child.suffix = root
		queue = append(queue, child)
	}

	for len(queue) > 0 {
		parent := queue[0]
		queue = queue[1:]

		for c, child := range parent.children {
			// Suffix Link (Failure Link) Construction

			// The suffix link points to the longest proper suffix of the current string
			// that is also a prefix of some pattern in the trie.

			// Start with the suffix of the parent node and traverse up until we find a node
			// that has a transition for the current character.

			s := parent.suffix

			for s != root {
				if _, exists := s.children[c]; exists {
					break
				}

				s = s.suffix
			}

			// If a valid transition exists from the failure node, the suffix link points there.
			// Otherwise, it falls back to the root.

			if match, exists := s.children[c]; exists {
				child.suffix = match
			} else {
				child.suffix = root
			}

			// Dictionary Suffix Link (Output Link) Construction

			// The dictSuffix points to the nearest node reachable via suffix links
			// that completes a pattern (i.e., has patternIdxs).

			// Optimization: Instead of traversing up the chain linearly, we check if the
			// immediate suffix node is an output node. If not, we simply inherit its
			// already-computed dictSuffix. This makes this step O(1).

			if len(child.suffix.patternIdxs) > 0 {
				child.dictSuffix = child.suffix
			} else {
				child.dictSuffix = child.suffix.dictSuffix
			}

			queue = append(queue, child)
		}
	}

	return root
}

type Result struct {
	PatternIdx int
	End        int
}

func (root *Node) Search(text string) []Result {
	results := []Result{}
	node := root

	for i := 0; i < len(text); i++ {
		c := text[i]

		for {
			if child, exists := node.children[c]; exists {
				node = child

				break
			}

			if node == root {
				break
			}

			node = node.suffix
		}

		if len(node.patternIdxs) > 0 {
			for _, patternIdx := range node.patternIdxs {
				end := i + 1
				result := Result{PatternIdx: patternIdx, End: end}
				results = append(results, result)
			}
		}

		dictNode := node.dictSuffix

		for dictNode != nil {
			for _, patternIdx := range dictNode.patternIdxs {
				end := i + 1
				result := Result{PatternIdx: patternIdx, End: end}
				results = append(results, result)
			}

			dictNode = dictNode.dictSuffix
		}
	}

	return results
}

func main() {
	patterns := []string{"a", "ab", "bab", "bc", "bca", "c", "caa"}

	fmt.Printf("Building with patterns: %v\n", patterns)

	root := Build(patterns)

	fmt.Println(root.String())

	text := "abccab"

	fmt.Printf("Searching text: %s\n", text)

	results := root.Search(text)

	for _, result := range results {
		pattern := patterns[result.PatternIdx]
		end := result.End
		start := end - len(pattern)

		fmt.Printf("%s %d:%d\n", pattern, start, end)
	}
}
