# seer

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation),
Python 3.14 and **SageMath installed system-wide**, since it cannot be
installed into a virtualenv:

```bash
sudo pacman -S sagemath          # or your distribution's equivalent
```

`make build` then creates `.venv` with `--system-site-packages` so it can see
Sage, builds `kernel` against that interpreter and installs the wheel into
it. It stops with a clear message if no Python 3.14 with Sage is found, or if
an existing `.venv` was created without access to the system packages.

```bash
make build       # venv + kernel + runtime dependencies
make test        # 358 tests
make run         # main.py, interactive
make live        # main.py --live, model driven
make distclean   # also removes .venv, to recreate it
```

### Interactive mode - `main.py`

Needs only the vocabulary file. One vocabulary token per line, so a word may
take several turns.

```bash
source .venv/bin/activate
python main.py                 # one kernel worker
python main.py --threads 8     # eight
python main.py --schema my.sql
python main.py --no-debug      # without the state blocks
```

### Model driven mode - `main.py --live`

Additionally requires `llama-cpp-python` and the
[gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF)
model at `../models/`.

It serialises the model's vocabulary, **overwriting `../vocabulary.tiktoken`**,
builds the engine over it and masks the logits at every step, so the model can
only sample tokens the syntax graph allows.

```bash
make model                     # adds llama-cpp-python
python main.py --live --threads 8
python main.py --live --no-debug      # without the state blocks
python main.py --live --model ../models/other.gguf --prompt "List every post title!"
```
