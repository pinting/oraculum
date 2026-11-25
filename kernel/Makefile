include ../versions.mk

VENV   := .venv
PYTHON := $(VENV)/bin/python

.PHONY: build benchmark clean

build:
	@command -v $(UV) > /dev/null || { echo "Error: $(UV) is not installed"; exit 1; }
	@if [ ! -d "$(VENV)" ]; then $(UV) venv "$(VENV)" --python $(PYTHON_VERSION) -q; fi
	@$(UV) pip install --python $(PYTHON) -q maturin==$(MATURIN_VERSION) numpy==$(NUMPY_VERSION)
	@VIRTUAL_ENV="$(CURDIR)/$(VENV)" $(VENV)/bin/maturin develop --features pyo3 --locked

benchmark:
	@cargo run --release --bin benchmark --locked

clean:
	@cargo clean
	rm -rf $(VENV) *.so *.egg-info/ dist/ build/ .pyodide_build/
