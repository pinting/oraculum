# seer

## Setup

### Interactive mode

Only requires [Rust](https://rustup.rs).

```bash
cargo run
```

### Constraining a llama.cpp model

Requires [Rust](https://rustup.rs), [UV](https://docs.astral.sh/uv/getting-started/installation) and [gemma-3-4b-it-Q8_0](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF) model.

```bash
# Model at path ../models/gemma-3-4b-it-Q8_0.gguf
make build
source .venv/bin/activate
python main.py
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](../LICENSE).
