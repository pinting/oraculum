# seer

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation)
and Python 3.14, and nothing else. `make build` creates `.venv`, builds `kernel`
against that interpreter and installs the wheel into it.

```bash
make build       # venv + kernel + runtime dependencies
make wasm        # the same kernel, cross compiled to WebAssembly
make test        # test.py over cases.yaml
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