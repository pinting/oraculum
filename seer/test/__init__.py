"""The test suite: every query of the corpus, fed into the engine and run in a database.

The engine is a generator, not a parser, so there is nothing to call on a
finished string - the only question it answers is which tokens may come next.
Feeding a query character by character turns that into a yes/no test, because a
single character is either among the routes the graph is offering or it is not:

* if it is, the engine takes it and the next character is asked about;
* if it is not, the feed is **stuck** - the graph never offered that character,
  so the text is outside the subset of SQL seer implements.

So a feed has exactly two outcomes, and a record declares which one it wants.
`expect: completed` means the feed has to walk the whole string and find the
statement completed at EOF; `expect: stuck` means it has to stop somewhere
before that. Reaching EOF with the statement unfinished counts as stuck too -
the graph is still waiting for more, so the string was not a statement.

That the engine completes a query says it is in the subset; it does not say
the query is SQL. So every query that completes as declared is then run in a
real database - SQLite, in memory, built from `schema.sql` and filled from
`data.sql` - and a statement the database refuses fails the record as surely
as a feed that went the wrong way.

    cases.yaml     the corpus: groups of queries, each with the outcome it expects
    schema.sql     the schema the engine generates over and the database is built from
    data.sql       the rows the database is filled with

    corpus.py      reading the corpus into records
    feeder.py      feeding one query into a fresh engine
    database.py    running one query in SQLite
    report.py      the progress bar
    __main__.py    the run, end to end

    python -m test
    python -m test --verbose
    python -m test --queries other.yaml --schema other.sql --data other.sql
    python -m test --no-database
"""
