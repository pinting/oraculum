package main

import (
	"fmt"
)

type RegExp interface {
	Nullable() bool
	Derive(c rune) RegExp
	Simplify() RegExp
	String() string
}

/*
 * Empty ∅
 */

type Empty struct{}

func NewEmpty() RegExp { return &Empty{} }

func (e *Empty) Nullable() bool { return false }

func (e *Empty) Derive(c rune) RegExp { return NewEmpty() }

func (e *Empty) Simplify() RegExp { return e }

func (e *Empty) String() string { return "∅" }

/*
 * Null ε
 */

type Null struct{}

func NewNull() RegExp { return &Null{} }

func (n *Null) Nullable() bool { return true }

func (n *Null) Derive(c rune) RegExp { return NewEmpty() }

func (n *Null) Simplify() RegExp { return n }

func (n *Null) String() string { return "ε" }

/*
 * Literal 'a'
 */

type Literal struct {
	R rune
}

func NewLiteral(c rune) RegExp { return &Literal{R: c} }

func (l *Literal) Nullable() bool { return false }

func (l *Literal) Derive(c rune) RegExp {
	if l.R == c {
		return NewNull()
	}
	return NewEmpty()
}

func (l *Literal) Simplify() RegExp { return l }

func (l *Literal) String() string { return string(l.R) }

/*
 * Union R | S
 */

type Union struct {
	Left, Right RegExp
}

func NewUnion(r1, r2 RegExp) RegExp { return &Union{Left: r1, Right: r2} }

func (u *Union) Nullable() bool { return u.Left.Nullable() || u.Right.Nullable() }

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
 * Concat R . S
 */

func NewConcat(r1, r2 RegExp) RegExp { return &Concat{Left: r1, Right: r2} }

type Concat struct {
	Left, Right RegExp
}

func (c *Concat) Nullable() bool {
	return c.Left.Nullable() && c.Right.Nullable()
}

// D_r(RS) = D_r(R)S | ν(R)D_r(S)
func (c *Concat) Derive(r rune) RegExp {
	d1r2 := NewConcat(c.Left.Derive(r), c.Right)

	if c.Left.Nullable() {
		d2 := c.Right.Derive(r)

		return NewUnion(d1r2, d2).Simplify()
	}

	return d1r2.Simplify()
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
	if _, ok := s1.(*Null); ok {
		return s2
	}

	// R . ε = R
	if _, ok := s2.(*Null); ok {
		return s1
	}

	return NewConcat(s1, s2)
}

func (c *Concat) String() string {
	return fmt.Sprintf("%s%s", c.Left.String(), c.Right.String())
}

/*
 * Star R*
 */

type Star struct {
	Operand RegExp
}

func NewStar(r RegExp) RegExp { return &Star{Operand: r} }

func (s *Star) Nullable() bool {
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
		return NewNull()
	}

	// ε* = ε
	if _, ok := op.(*Null); ok {
		return NewNull()
	}

	return NewStar(op)
}

func (s *Star) String() string {
	return fmt.Sprintf("%s*", s.Operand.String())
}

func Matches(r RegExp, text string) bool {
	current := r

	for _, r := range text {
		current = current.Derive(r)

		if _, ok := current.(*Empty); ok {
			return false
		}
	}

	return current.Nullable()
}

func main() {
	// (a|b)*cd
	pattern := NewConcat(
		NewStar(NewUnion(NewLiteral('a'), NewLiteral('b'))),
		NewConcat(NewLiteral('c'), NewLiteral('d')),
	)

	r := pattern

	fmt.Printf("Start:  %s\n", r)

	r = r.Derive('a')

	fmt.Printf("Derive 'a' -> %s\n", r)

	r = r.Derive('b')

	fmt.Printf("Derive 'b' -> %s\n", r)

	r = r.Derive('c')

	fmt.Printf("Derive 'c' -> %s\n", r)

	r = r.Derive('d')

	fmt.Printf("Derive 'd' -> %s\n", r)
	fmt.Printf("Nullable? %v\n", r.Nullable())
}
