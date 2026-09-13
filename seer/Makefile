VENV := .venv
PYTHON := $(VENV)/bin/python

export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)
export VIRTUAL_ENV := $(CURDIR)/$(VENV)

KERNEL_WHEELS := $(CURDIR)/../kernel/target/wheels

.ONESHELL:
.PHONY: prerequisites kernel build model test test-model test-all benchmark run live clean distclean

# Nothing outside this venv is needed. The modelling seer runs on - a boolean
# algebra over table variables and a foreign key multigraph - used to be
# SageMath's, which ships system-wide only and does not cross compile; it lives
# in `kernel` now, which is built here and which the browser build shares.
prerequisites:
	@command -v uv > /dev/null || (echo "Error: uv is not installed!" && exit 1)
	@VERSION=$$(python3 -c \
		"import tomllib; \
		print(tomllib.load(open('pyproject.toml','rb'))['project']['requires-python'].lstrip('>= '))")

	if [ ! -d "$(VENV)" ]; then
		uv venv "$(VENV)" --python "$$VERSION"
	else
		ACTUAL_VERSION=$$($(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

		if [ "$$ACTUAL_VERSION" != "$$VERSION" ]; then
			echo "Error: .venv Python version mismatch"
			exit 1
		fi
	fi

# Build kernel against this venv's interpreter and install the wheel into it.
kernel: prerequisites
	uv pip install maturin
	cd ../kernel && $(CURDIR)/$(VENV)/bin/maturin build --release -i $(CURDIR)/$(PYTHON)
	uv pip install --force-reinstall --no-deps $$(ls -t $(KERNEL_WHEELS)/*.whl | head -1)

build: kernel
	uv pip install -r requirements.txt

# Extra dependency of the live mode entry point.
model: build
	uv pip install llama-cpp-python

# Feeds every query of tests/cases.yaml into the engine, one character at a
# time, and fails on any that does not behave as its group declares.
test:
	$(PYTHON) tests/main.py

# The algebra and the graph against the brute force reference written in the
# test, on inputs the corpus never reaches.
test-model:
	$(PYTHON) tests/model.py

test-all: test-model test

# The modelling layer, timed. The corpus is the wrong place to look for this:
# most of a run is the kernel masking the vocabulary.
benchmark:
	$(PYTHON) tests/benchmark.py

# Interactive entry point.
run:
	$(PYTHON) main.py

# Model driven entry point.
live:
	$(PYTHON) main.py --live

clean:
	rm -rf __pycache__/ src/__pycache__/ tests/__pycache__/ .pytest_cache/

distclean: clean
	rm -rf $(VENV)
