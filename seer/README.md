# seer

## Setup

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation)
and Python 3.14, and nothing else. `make build` creates `.venv`, builds `kernel`
against that interpreter and installs the wheel into it.

```bash
make build       # venv + kernel + runtime dependencies
make test        # tests/main.py over tests/cases.yaml
make test-model  # the algebra and the graph against a brute force reference
make test-all    # both
make benchmark   # the modelling layer, timed
make run         # interactive, user driven
make live        # live, model driven
```

**SageMath is no longer involved.** The modelling seer does - a boolean algebra
over table variables and a multigraph over foreign keys - was its
`BooleanPolynomialRing` and its `Graph`, which meant hunting for a system-wide
interpreter that could see it and gave the browser nothing at all. Both are
ports in `kernel` now: the algebra holds the polynomial as a zero-suppressed
decision diagram, which is what PolyBoRi gives `BooleanPolynomialRing`
underneath SageMath, and the graph is built for the single mutation join
resolution performs. seer already needed `kernel` for its indexes, so the
modelling costs it no dependency it did not have.

### User driven interactive mode

Needs only the vocabulary file. One vocabulary token per line, so a word may
take several turns.

```bash
source .venv/bin/activate
python main.py
python main.py --threads 8
python main.py --schema my.sql
python main.py --no-debug 
```

### Model driven live mode

Additionally requires `llama-cpp-python` and the
[gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF)
model at `../models/`.

It serialises the model's vocabulary, **overwriting `../vocabulary.tiktoken`**,
builds the engine over it and masks the logits at every step, so the model can
only sample tokens the syntax graph allows.

```bash
make model
python main.py --live --threads 8
python main.py --live --no-debug
python main.py --live --model ../models/model.gguf --prompt "List every post title!"
```