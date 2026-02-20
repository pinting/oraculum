VENV := .venv/bin

export PATH := $(CURDIR)/$(VENV):$(PATH)
export VIRTUAL_ENV := $(CURDIR)/.venv

.PHONY: build develop install clean run interactive test fastlines

build:
	maturin build --release

develop:
	maturin develop

install:
	uv pip install -r requirements.txt
	maturin develop

clean:
	cargo clean
	rm -rf target/
	rm -rf *.egg-info/
	rm -rf dist/
	rm -rf build/

run:
	python main.py

interactive:
	python interactive.py

test:
	python -c "import seer; print('Module seer loaded successfully!')"

fastlines:
	cd ../fastlines && ./setup.sh
