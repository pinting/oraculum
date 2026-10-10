"""Tools for battle testing seer beyond the corpus of `test/`.

The corpus checks the statements someone thought of. These look for the ones
nobody did, and run what seer writes in a stricter database than SQLite.

    fuzz.py        random walks through the syntax graph, run in SQLite
    probe.py       what the graph offers after a prefix
    postgres.py    statements run in PostgreSQL, in an interpreter of its own
    schemas/       schemas that are hard on the resolvers

    python -m tools.fuzz
    python -m tools.probe "SELECT email FROM users WHERE "
    make fuzz postgres

`postgres.py` is the odd one out: the PostgreSQL it starts comes from
`pgserver`, which ships no wheel for Python 3.14, so it runs under the
interpreter `make postgres` builds for it and imports nothing of seer but the
corpus reader.
"""
