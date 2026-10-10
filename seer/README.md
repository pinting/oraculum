# seer

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation)
and Python 3.14, and nothing else. `make build` creates `.venv`, builds `kernel`
against that interpreter and installs the wheel into it.

```bash
make build       # venv + kernel + runtime dependencies
make wasm        # the same kernel, cross compiled to WebAssembly
make test        # python -m test: test/cases.yaml, fed and run in SQLite
make fuzz        # python -m tools.fuzz: random walks over three schemas
make postgres    # the corpus and the walks, run in PostgreSQL
make run         # interactive, user driven
make live        # live, model driven
```

### User driven - interactive mode

```bash
source .venv/bin/activate
python main.py
```

### Model driven - live mode

`make live` installs `llama-cpp-python` at the pinned version and starts it. It
also needs the
[gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF)
model at `../models/`.

```bash
make live
python main.py --live
```

### Tests

```bash
python -m test                  # the whole corpus
python -m test --verbose        # every record, not only the failures
python -m test --no-database    # feed only, skip SQLite
```

The suite lives in `test/`. Every query of `test/cases.yaml` is fed into the
engine one character at a time and has to end the way its group declares -
`completed` or `stuck`. Every legal query that completes is then run in an
in-memory SQLite database built from `test/schema.sql` and filled from
`test/data.sql`, and has to run there too. `test/schema.sql` is the schema the
engine generates over in the suite, so the engine and the database always
agree on what exists; it is a copy of `schema.sql`, which the drivers use.
SQLite 3.39 or later is needed, for RIGHT and FULL JOIN.

### Tools

The corpus checks the statements someone thought of; `tools/` looks for the
ones nobody did.

```bash
python -m tools.fuzz                                     # 500 walks over test/schema.sql
python -m tools.fuzz --schema tools/schemas/harsh.sql    # the same, over a harder schema
python -m tools.probe "SELECT email FROM users WHERE "   # what is offered after a prefix
```

A walk types one character at a time, each picked from what the engine
offers, until the statement completes or the step budget runs out. It fails
when an offered character is refused, when nothing is offered before the
statement is complete, when only whitespace can ever follow, or when SQLite
will not run the statement it completed. Completed statements land in
`out/fuzz/<schema>.jsonl`.

`make postgres` runs the legal records of the corpus and those statements in
a throwaway PostgreSQL 16, which is stricter than SQLite about grouping and
types. The server comes from `pgserver`, which has no wheel for Python 3.14,
so the target builds a Python 3.12 interpreter for it in `.postgres`. Literal
values seer does not check (`'2024-99-99'`) and the known limits of its type
classes are reported apart from real refusals; only the latter fail the run.
