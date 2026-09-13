include ../versions.mk

SHELL       := $(BASH)
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:

VENV   := .venv
PYTHON := $(VENV)/bin/python

OUT    := out
NATIVE := $(OUT)/native
WASM   := $(OUT)/wasm

# The cross build toolchain and the Emscripten it installs - about 1.7GB
# between them, and both gitignored.
TOOLCHAIN := .toolchain

KERNEL := $(CURDIR)/../kernel

export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)
export VIRTUAL_ENV := $(CURDIR)/$(VENV)

REQUIREMENTS := \
	numpy==$(NUMPY_VERSION) \
	sqlglot==$(SQLGLOT_VERSION) \
	pyyaml==$(PYYAML_VERSION)

.PHONY: prerequisites kernel build wasm test run live clean distclean

prerequisites:
	@command -v $(UV) > /dev/null || { echo "Error: $(UV) is not installed"; exit 1; }

	mkdir -p $(OUT)

	if [ -d "$(VENV)" ]; then
		ACTUAL=$$($(PYTHON) -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")

		if [ "$$ACTUAL" != "$(PYTHON_VERSION)" ]; then
			echo "Error: $(VENV) is Python $$ACTUAL, expected $(PYTHON_VERSION)."
			echo "       Run 'make distclean' to rebuild it, or set PYTHON_VERSION=$$ACTUAL."
			exit 1
		fi
	else
		echo ">> creating $(VENV) with Python $(PYTHON_VERSION)"
		$(UV) venv "$(VENV)" --python $(PYTHON_VERSION) -q
	fi

	if command -v rustc > /dev/null; then
		ACTUAL=$$(rustc --version | cut -d' ' -f2)

		if [ "$$ACTUAL" != "$(RUST_VERSION)" ]; then
			echo "Warning: rustc is $$ACTUAL, this tree pins $(RUST_VERSION)."
			echo "         Cargo.lock still pins every crate, so this usually builds anyway."
		fi
	else
		echo "Error: cargo/rustc not found - https://rustup.rs"
		exit 1
	fi

# `--locked` is what makes the Rust half reproducible: Cargo.lock names an
# exact revision for every crate, including the one that is a git dependency.
kernel: prerequisites
	@mkdir -p $(NATIVE)

	echo ">> building the native kernel wheel"

	$(UV) pip install -q maturin==$(MATURIN_VERSION)

	$(VENV)/bin/maturin build --release \
		--manifest-path $(KERNEL)/Cargo.toml \
		--interpreter $(CURDIR)/$(PYTHON) \
		--out $(CURDIR)/$(NATIVE) \
		--locked

	$(UV) pip install -q --force-reinstall --no-deps $$(ls -t $(NATIVE)/*.whl | head -1)

build: kernel
	@echo ">> installing the pinned runtime dependencies"
	$(UV) pip install -q $(REQUIREMENTS)

	echo
	echo "built into $(OUT)/:"
	ls -la $(NATIVE)/*.whl | awk '{printf "  %-58s %10s\n", $$NF, $$5}'

# pyodide-build owns the whole toolchain: it downloads the cross-build
# environment, clones emsdk and installs Emscripten into it with Pyodide's own
# patches, and sources the emsdk environment itself when `pyodide build` runs.
#
# `parallel` is off because Pyodide has no pthreads and rayon's pool cannot be
# built there at all - see kernel/src/runtime/pool.rs.
wasm: prerequisites
	@mkdir -p $(WASM) $(TOOLCHAIN) "$(PYODIDE_XBUILDENV_PATH)"

	if [ ! -x "$(TOOLCHAIN)/venv/bin/pyodide" ]; then
		echo ">> creating the cross build venv with pyodide-build $(PYODIDE_BUILD_VERSION)"
		$(UV) venv "$(TOOLCHAIN)/venv" --python $(PYTHON_VERSION) -q
		$(UV) pip install -q --python "$(TOOLCHAIN)/venv/bin/python" \
			pyodide-build==$(PYODIDE_BUILD_VERSION)
	fi

	export PATH="$(CURDIR)/$(TOOLCHAIN)/venv/bin:$$PATH"
	export PYODIDE_XBUILDENV_PATH="$(PYODIDE_XBUILDENV_PATH)"

	echo ">> cross build environment $(XBUILDENV_VERSION)"
	pyodide xbuildenv install $(XBUILDENV_VERSION) 2>&1 | tail -1

	echo ">> emscripten $(EMSCRIPTEN_VERSION) (the slow part, the first time)"
	pyodide xbuildenv install-emscripten --version $(EMSCRIPTEN_VERSION) 2>&1 | tail -2

	echo ">> building the kernel wheel for wasm32"

	rm -f $(WASM)/*.whl
	export MATURIN_PEP517_ARGS="--no-default-features --features pyo3 --locked"
	cd $(KERNEL) && pyodide build --outdir $(CURDIR)/$(WASM) 2>&1 | tail -2
	cd $(CURDIR)

	# pyodide-build leaves a second copy beside the crate whatever --outdir says.
	rm -rf $(KERNEL)/dist

	echo
	echo "built into $(OUT)/:"
	ls -la $(WASM)/*.whl | awk '{printf "  %-58s %10s\n", $$NF, $$5}'

test:
	$(PYTHON) test.py

run:
	$(PYTHON) main.py

live:
	$(UV) pip install -q llama-cpp-python==$(LLAMA_CPP_PYTHON_VERSION)
	$(PYTHON) main.py --live

clean:
	@rm -rf __pycache__/ src/__pycache__/ .pytest_cache/
	rm -rf $(NATIVE) $(WASM)/*.whl

distclean: clean
	@rm -rf $(VENV) $(TOOLCHAIN)

	case "$(PYODIDE_XBUILDENV_PATH)" in
		$(CURDIR)/*) rm -rf "$(PYODIDE_XBUILDENV_PATH)" ;;
		*) echo "leaving $(PYODIDE_XBUILDENV_PATH) alone - it is outside this tree" ;;
	esac
