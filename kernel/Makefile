include ../versions.mk

SHELL       := $(BASH)
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:

VENV   := .venv
PYTHON := $(VENV)/bin/python

export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)
export VIRTUAL_ENV := $(CURDIR)/$(VENV)

.PHONY: prerequisites build benchmark clean

# For working on the kernel alone. seer builds its own venv and installs a
# wheel into it; nothing here is needed for that.
prerequisites:
	@command -v $(UV) > /dev/null || { echo "Error: $(UV) is not installed"; exit 1; }

	if [ -d "$(VENV)" ]; then
		ACTUAL=$$($(PYTHON) -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")

		if [ "$$ACTUAL" != "$(PYTHON_VERSION)" ]; then
			echo "Error: $(VENV) is Python $$ACTUAL, expected $(PYTHON_VERSION)."
			echo "       Run 'make clean' to rebuild it, or set PYTHON_VERSION=$$ACTUAL."
			exit 1
		fi
	else
		echo ">> creating $(VENV) with Python $(PYTHON_VERSION)"
		$(UV) venv "$(VENV)" --python $(PYTHON_VERSION) -q
	fi

build: prerequisites
	@$(UV) pip install -q maturin==$(MATURIN_VERSION) numpy==$(NUMPY_VERSION)

	maturin develop --features pyo3 --locked

# Rust, because the DFA layout is a type parameter fixed when the extension is
# compiled: comparing layouts is not something the bindings can do.
benchmark:
	@cargo run --release --bin benchmark --locked

clean:
	@cargo clean
	rm -rf $(VENV) *.so *.egg-info/ dist/ build/ .pyodide_build/
