VENV := .venv
PYTHON := $(VENV)/bin/python

# Captured before the venv is put on PATH, so the SageMath check below can tell
# "not installed system-wide" apart from "this venv cannot see it".
SYSTEM_PATH := $(PATH)

export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)
export VIRTUAL_ENV := $(CURDIR)/$(VENV)

# PyO3 0.22 refuses to build against Python 3.14 without this; the generated
# extension works, the version check is simply ahead of the release.
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY := 1

KERNEL_WHEELS := $(CURDIR)/../kernel/target/wheels

.ONESHELL:
.PHONY: prerequisites kernel build model test benchmark run live clean distclean

# SageMath only ships system-wide, so the venv has to see the system packages.
# `sage` is imported by src/root.py and src/relationships.py.
prerequisites:
	@command -v uv > /dev/null || (echo "Error: uv is not installed!" && exit 1)
	@VERSION=$$(python3 -c \
		"import tomllib; \
		print(tomllib.load(open('pyproject.toml','rb'))['project']['requires-python'].lstrip('>= '))")

	# SageMath installs into the system interpreter's site-packages, so look
	# there directly. PATH may well start with an unrelated virtualenv.
	SYSTEM_PYTHON=""

	for CANDIDATE in /usr/bin/python$$VERSION /usr/local/bin/python$$VERSION \
		$$(PATH="$(SYSTEM_PATH)" command -v python$$VERSION); do
		if [ -x "$$CANDIDATE" ] && $$CANDIDATE -c "import sage" > /dev/null 2>&1; then
			SYSTEM_PYTHON=$$CANDIDATE

			break
		fi
	done

	if [ -z "$$SYSTEM_PYTHON" ]; then
		echo "Error: no Python $$VERSION with SageMath found!"
		echo "SageMath only installs system-wide, e.g. 'sudo pacman -S sagemath'."
		exit 1
	fi

	if [ ! -d "$(VENV)" ]; then
		echo "Creating venv with Python $$VERSION and system site packages..."
		uv venv "$(VENV)" --python "$$SYSTEM_PYTHON" --system-site-packages
	else
		ACTUAL_VERSION=$$($(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

		if [ "$$ACTUAL_VERSION" != "$$VERSION" ]; then
			echo "Error: .venv Python version mismatch"
			exit 1
		fi

		if ! $(PYTHON) -c "import sage" > /dev/null 2>&1; then
			echo "Error: .venv cannot see SageMath."
			echo "It was created without --system-site-packages; run 'make distclean build'."
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

test:
	$(PYTHON) -m pytest tests/ -q

# Interactive entry point.
run:
	$(PYTHON) main.py

# Model driven entry point.
live:
	$(PYTHON) main.py --live

clean:
	rm -rf __pycache__/ src/__pycache__/ tests/__pycache__/ tests/parity/__pycache__/ .pytest_cache/

distclean: clean
	rm -rf $(VENV)
