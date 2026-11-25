include ../versions.mk

VENV   := .venv
PYTHON := $(VENV)/bin/python

OUT    := out
NATIVE := $(OUT)/native
WASM   := $(OUT)/wasm

TOOLCHAIN := .toolchain
KERNEL    := $(CURDIR)/../kernel

REQUIREMENTS := \
	numpy==$(NUMPY_VERSION) \
	sqlglot==$(SQLGLOT_VERSION) \
	pyyaml==$(PYYAML_VERSION)

.PHONY: prerequisites build wasm test run live clean

prerequisites:
	@command -v $(UV) > /dev/null || { echo "Error: $(UV) is not installed"; exit 1; }
	@command -v cargo > /dev/null || { echo "Error: cargo/rustc not found - https://rustup.rs"; exit 1; }
	@if [ ! -d "$(VENV)" ]; then $(UV) venv "$(VENV)" --python $(PYTHON_VERSION) -q; fi

build: prerequisites
	@mkdir -p $(NATIVE)
	@$(UV) pip install --python $(PYTHON) -q maturin==$(MATURIN_VERSION) $(REQUIREMENTS)
	@$(VENV)/bin/maturin build --release \
		--manifest-path $(KERNEL)/Cargo.toml \
		--interpreter $(CURDIR)/$(PYTHON) \
		--out $(CURDIR)/$(NATIVE) \
		--locked
	@$(UV) pip install --python $(PYTHON) -q --force-reinstall --no-deps $$(ls -t $(NATIVE)/*.whl | head -1)

wasm: prerequisites
	@mkdir -p $(WASM) $(TOOLCHAIN) "$(PYODIDE_XBUILDENV_PATH)"
	@if command -v rustup > /dev/null; then rustup target add wasm32-unknown-emscripten > /dev/null; fi
	@if [ ! -x "$(TOOLCHAIN)/venv/bin/pyodide" ]; then \
		$(UV) venv "$(TOOLCHAIN)/venv" --python $(PYTHON_VERSION) -q; \
		$(UV) pip install --python "$(TOOLCHAIN)/venv/bin/python" -q pyodide-build==$(PYODIDE_BUILD_VERSION); \
	fi
	@PATH="$(CURDIR)/$(TOOLCHAIN)/venv/bin:$$PATH" PYODIDE_XBUILDENV_PATH="$(PYODIDE_XBUILDENV_PATH)" \
		bash -c ' \
			set -euo pipefail; \
			pyodide xbuildenv install "$(XBUILDENV_VERSION)" 2>&1 | tail -1; \
			pyodide xbuildenv install-emscripten --version "$(EMSCRIPTEN_VERSION)" 2>&1 | tail -2; \
			rm -f "$(CURDIR)/$(WASM)"/*.whl; \
			export MATURIN_PEP517_ARGS="--no-default-features --features pyo3 --locked"; \
			(cd "$(KERNEL)" && pyodide build --outdir "$(CURDIR)/$(WASM)"); \
			rm -rf "$(KERNEL)/dist"; \
		'

test:
	$(PYTHON) -m test

run:
	$(PYTHON) main.py

live:
	$(UV) pip install --python $(PYTHON) -q llama-cpp-python==$(LLAMA_CPP_PYTHON_VERSION)
	$(PYTHON) main.py --live

clean:
	@rm -rf __pycache__/ src/__pycache__/ test/__pycache__/ test/validators/__pycache__/ .pytest_cache/
	rm -rf $(NATIVE) $(WASM)/*.whl $(VENV) $(TOOLCHAIN)
	@case "$(PYODIDE_XBUILDENV_PATH)" in \
		$(CURDIR)/*) rm -rf "$(PYODIDE_XBUILDENV_PATH)" ;; \
	esac
