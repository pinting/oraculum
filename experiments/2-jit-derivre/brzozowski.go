package main

import (
	"fmt"
)

type RegExp interface {
	Accepting() bool
	Derive(c rune) RegExp
	Simplify() RegExp
	String() string
}

/*
 * Empty ∅ denotes the empty set: L(∅) = {}
 */

type Empty struct{}

func NewEmpty() RegExp { return &Empty{} }

func (e *Empty) Accepting() bool { return false }

func (e *Empty) Derive(c rune) RegExp { return NewEmpty() }

func (e *Empty) Simplify() RegExp { return e }

func (e *Empty) String() string { return "∅" }

/*
 * Epsilon ε denotes the singleton set containing the empty string: L(ε) = {ε}
 */

type Epsilon struct{}

func NewEpsilon() RegExp { return &Epsilon{} }

func (n *Epsilon) Accepting() bool { return true }

func (n *Epsilon) Derive(c rune) RegExp { return NewEmpty() }

func (n *Epsilon) Simplify() RegExp { return n }

func (n *Epsilon) String() string { return "ε" }

/*
 * Literal 'a' denotes the singleton set containing the single-symbol string a: L(a) = {a}
 */

type Literal struct {
	R rune
}

func NewLiteral(c rune) RegExp { return &Literal{R: c} }

func (l *Literal) Accepting() bool { return false }

func (l *Literal) Derive(c rune) RegExp {
	if l.R == c {
		return NewEpsilon()
	}

	return NewEmpty()
}

func (l *Literal) Simplify() RegExp { return l }

func (l *Literal) String() string { return string(l.R) }

/*
 * Union R | S denotes the union of R and S: L(R ∨ S) = L(R) ∪ L(S)
 */

type Union struct {
	Left, Right RegExp
}

func NewUnion(r1, r2 RegExp) RegExp { return &Union{Left: r1, Right: r2} }

func (u *Union) Accepting() bool { return u.Left.Accepting() || u.Right.Accepting() }

func (u *Union) Derive(c rune) RegExp {
	d1 := u.Left.Derive(c)
	d2 := u.Right.Derive(c)

	return NewUnion(d1, d2).Simplify()
}

func (u *Union) Simplify() RegExp {
	s1 := u.Left.Simplify()
	s2 := u.Right.Simplify()

	// ∅ | R = R
	if _, ok := s1.(*Empty); ok {
		return s2
	}

	// R | ∅ = R
	if _, ok := s2.(*Empty); ok {
		return s1
	}

	return NewUnion(s1, s2)
}

func (u *Union) String() string {
	return fmt.Sprintf("(%s|%s)", u.Left.String(), u.Right.String())
}

/*
 * Concat R . S denotes the concatenation of R and S: L(RS) = L(R) · L(S)
 */

func NewConcat(r1, r2 RegExp) RegExp { return &Concat{Left: r1, Right: r2} }

type Concat struct {
	Left, Right RegExp
}

func (c *Concat) Accepting() bool {
	return c.Left.Accepting() && c.Right.Accepting()
}

// D_r(RS) = D_r(R)S | ν(R)D_r(S)
func (c *Concat) Derive(r rune) RegExp {
	a := NewConcat(c.Left.Derive(r), c.Right)

	if c.Left.Accepting() {
		b := c.Right.Derive(r)

		return NewUnion(a, b).Simplify()
	}

	return a.Simplify()
}

func (c *Concat) Simplify() RegExp {
	s1 := c.Left.Simplify()
	s2 := c.Right.Simplify()

	// ∅ . R = ∅
	if _, ok := s1.(*Empty); ok {
		return NewEmpty()
	}

	// R . ∅ = ∅
	if _, ok := s2.(*Empty); ok {
		return NewEmpty()
	}

	// ε . R = R
	if _, ok := s1.(*Epsilon); ok {
		return s2
	}

	// R . ε = R
	if _, ok := s2.(*Epsilon); ok {
		return s1
	}

	return NewConcat(s1, s2)
}

func (c *Concat) String() string {
	return fmt.Sprintf("%s%s", c.Left.String(), c.Right.String())
}

/*
 * Star R* denotes the Kleene closure of R: L(R*) = L(R)*
 */

type Star struct {
	Operand RegExp
}

func NewStar(r RegExp) RegExp { return &Star{Operand: r} }

func (s *Star) Accepting() bool {
	return true
}

// D_c(R*) = D_c(R)R*
func (s *Star) Derive(c rune) RegExp {
	d := s.Operand.Derive(c)

	return NewConcat(d, NewStar(s.Operand)).Simplify()
}

func (s *Star) Simplify() RegExp {
	op := s.Operand.Simplify()

	// ∅* = ε
	if _, ok := op.(*Empty); ok {
		return NewEpsilon()
	}

	// ε* = ε
	if _, ok := op.(*Epsilon); ok {
		return NewEpsilon()
	}

	return NewStar(op)
}

func (s *Star) String() string {
	op := s.Operand.Simplify()

	if _, ok := op.(*Concat); ok {
		return fmt.Sprintf("(%s)*", op.String())
	}

	return fmt.Sprintf("%s*", op.String())
}

func Matches(current RegExp, text string) {
	fmt.Printf("Start: %s", current)

	if current.Accepting() {
		fmt.Print("\nAccepting")
	}

	fmt.Print("\n")

	for _, r := range text {
		current = current.Derive(r)

		fmt.Printf("Derive '%c' -> %s", r, current)

		if current.Accepting() {
			fmt.Print("\tAccepting")
		}

		fmt.Print("\n")

		if _, ok := current.(*Empty); ok {
			return
		}
	}
}

func main() {
	fmt.Printf("Example #1 - Basic\n\n")

	start := NewConcat(
		NewStar(NewUnion(NewLiteral('a'), NewLiteral('b'))),
		NewConcat(NewLiteral('c'), NewLiteral('d')),
	)

	Matches(start, "abcd")

	fmt.Printf("\nExample #2 - (ab)* can be ignored\n\n")

	start = NewConcat(
		NewStar(NewConcat(NewLiteral('a'), NewLiteral('b'))),
		NewLiteral('c'),
	)

	Matches(start, "c")

	fmt.Printf("\nExample #3 - However once (ab)* is started, it needs to be finished\n\n")

	Matches(start, "ababc")
}
