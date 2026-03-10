VENV := .venv
PYTHON := $(VENV)/bin/python

export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)
export VIRTUAL_ENV := $(CURDIR)/$(VENV)

.ONESHELL:
.PHONY: prerequisites build clean

prerequisites:
	@command -v uv > /dev/null || (echo "Error: uv is not installed!" && exit 1)
	@VERSION=$$(python3 -c \
		"import tomllib; \
		print(tomllib.load(open('pyproject.toml','rb'))['project']['requires-python'].lstrip('>= '))")

	if [ ! -d "$(VENV)" ]; then
		echo "Creating venv with Python $$VERSION..."
		uv venv "$(VENV)" --python "$$VERSION"
	else
		ACTUAL_VERSION=$$($(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

		if [ "$$ACTUAL_VERSION" != "$$VERSION" ]; then
			echo "Error: .venv Python version mismatch"
			exit 1
		fi
	fi

build: prerequisites
	uv pip install -r requirements.txt
	maturin develop --features pyo3

clean:
	cargo clean
	rm -rf *.so *.egg-info/ dist/ build/
