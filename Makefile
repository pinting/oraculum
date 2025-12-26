.PHONY: build develop install clean run test

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

test:
	python -c "import oraculum; print('Module oraculum loaded successfully!')"
