# seer

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation), and Python 3.14.

Running `make build` creates `.venv`, builds `kernel` against that interpreter, and installs it alongside runtime dependencies.

```bash
make build       # Build seer along with the kernel
make test        # Run the test suite
make run         # Run the interactive user demo
make live        # Run the live model demo
```

`make live` requires the [gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF) model placed at `../models/`.

### Tests

```bash
python -m test             # The whole corpus across all validators
python -m test --verbose   # Every record, not only the failures
```

The test suite lives in `test/`. Every query in `test/cases.yaml` is fed into the engine one character at a time and must end as its group specifies: `completed` or `stuck`. Every legal query that completes is validated against all integration validators (`SQLiteValidator` over an in-memory SQLite 3.39+ database built from `test/schema.sql` and `test/data.sql`, and `SqlglotValidator` checking PostgreSQL dialect parsing, schema qualification, type compatibility, and `GROUP BY` coverage).
