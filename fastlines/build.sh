#!/bin/bash

source .venv/bin/activate

uv pip install -r requirements.txt

rm -rf target/
rm -rf *.so

maturin develop --features pyo3