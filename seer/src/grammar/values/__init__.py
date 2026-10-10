"""Values: what an item of the projection is written as.

    <value>     := <term> [<arithmetic operator> <term>]*
    <term>      := <column ref> | <literal> | <call> | <aggregate> | <ranking> | <case>
    <call>      := FN "(" <value> ["," <value>]* ")" | CAST "(" <value> AS TEXT ")"
    <aggregate> := AGG "(" [DISTINCT] <value> ")" [<window>] | COUNT "(" "*" ")" [<window>]
    <ranking>   := RANK "(" ")" <window>
    <window>    := OVER "(" [PARTITION BY <column> [, <column>]*]
                            [ORDER BY <column> [ASC | DESC] [, ...]*] ")"
    <case>      := CASE [WHEN <predicate> THEN <value>]+ [ELSE <value>] END

The projection is written before the FROM clause exists, so a value is built
the way the conditions of `grammar.conditions` are: continuation passing. Every
emitter takes `then`, which is handed the `Expr` once the emitter has written
it whole and answers with what may follow it. The tree is never stored half
built - each branch of the graph carries the part it has written in the
closures of the thunks ahead of it - and the virtual table only learns of a
value when its item is complete (`projection.py`).

What the virtual table does learn of while a value is written are its columns.
Every column is demanded the moment it is taken, as a value of whatever
classes its `Position` allows, which is how `LOWER(` offers only the columns
that can be text. A column taken where its class was free may be narrowed
afterwards: an arithmetic operator after a value narrows it to numeric, and a
comparison inside a CASE to the class it compares in - see
`expression.narrowing`. The operator is only offered where the narrowing can
hold, and its selector applies it.

Two kinds of value branch on a class rather than read one off what is written:
a `CASE`, whose branches all have to agree, and `COALESCE`, whose arguments
do. Each is offered once per class with a literal, the class fixed from its
first token on.

    position.py   where a value is written, and what that allows
    leaves.py     columns and literals
    narrow.py     narrowing a value once something asks for its class
    calls.py      scalar functions, casts, aggregates, ranking functions
    windows.py    OVER (...)
    cases.py      CASE WHEN ... END, and its predicates
    values.py     a term, and the arithmetic extending it
"""

from .position import Position, Then, meet
from .values import value

__all__ = ["Position", "Then", "meet", "value"]
