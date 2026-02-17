set -e

VENV_DIR=".venv"
REQUIREMENTS="requirements.txt"
PYTHON_VERSION="3.11"

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Install it from https://github.com/astral-sh/uv"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment with uv (Python $PYTHON_VERSION)..."
    uv venv "$VENV_DIR" --python "$PYTHON_VERSION"
fi

source "$VENV_DIR/bin/activate"

echo "Installing Python dependencies..."
uv pip install -r "$REQUIREMENTS"

echo "Cleaning previous build artifacts..."
rm -rf target/
rm -rf *.so

echo "Building Rust extension with maturin..."
maturin develop --features pyo3

echo "Setup complete. Run: source $VENV_DIR/bin/activate && python main.py"
