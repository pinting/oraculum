# seer

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation), and Python 3.14.

Running `make build` creates `.venv`, builds `kernel` against that interpreter, and installs the wheel into it.

```bash
make build       # Build seer along with the kernel
make test        # Run the test suite
make run         # Run the interactive user demo
make live        # Run the live model demo 
```

`make live` requires the [gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF) model placed at `../models/`.

### Tests

```bash
python -m test                  # The whole corpus
python -m test --verbose        # Every record, not only the failures
python -m test --no-database    # Feed only, skip SQLite
```

The test suite lives in `test/`. Every query in `test/cases.yaml` is fed into the engine one character at a time and must end as its group specifies: `completed` or `stuck`. Every legal query that completes is then executed in an in-memory SQLite database built from `test/schema.sql` and populated from `test/data.sql`. Because `test/schema.sql` is a copy of `schema.sql` used by the drivers, the engine and database remain synchronized. SQLite 3.39 or later is required for RIGHT and FULL JOIN support.

### Tools

While `test/cases.yaml` covers predefined test statements, `tools/` explores generated queries to find edge cases.

```bash
python -m tools.fuzz                                     # 500 walks over test/schema.sql
python -m tools.fuzz --schema tools/schemas/harsh.sql    # The same, over a harder schema
python -m tools.probe "SELECT email FROM users WHERE "   # What is offered after a prefix
```

A random walk types one character at a time from the engine's offered tokens until the statement completes or exhausts its step budget. A walk fails if an offered character is rejected, if no tokens are offered before completion, if only whitespace remains possible, or if SQLite rejects the completed query. Successful statements are saved to `out/fuzz/<schema>.jsonl`.

`make postgres` runs both the corpus queries and fuzzing outputs against an ephemeral PostgreSQL 16 instance, which enforces stricter grouping and type constraints than SQLite. The database server runs via `pgserver`, which lacks Python 3.14 wheels, so the target builds a local Python 3.12 interpreter in `.postgres`. Unchecked literal values like `'2024-99-99'` and documented type class limits are logged separately from structural syntax errors; only actual syntax rejections fail the run.
