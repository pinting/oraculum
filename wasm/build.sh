#!/usr/bin/env bash
#
# Build the browser bundle: the kernel as a Pyodide wheel, the seer sources as
# a zip, and the vocabulary alongside them.
#
# Everything the build needs that is not in the repo goes into .build/, which
# is gitignored: a Python 3.14 venv with pyodide-build, the Pyodide cross build
# environment, and an emsdk pinned to the emscripten the environment wants.
# First run downloads about 700MB and takes a while; later runs reuse it.
#
#     ./build.sh && ./serve.py
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="$HERE/.build"
DIST="$HERE/dist"

# The Pyodide cross build environment, and with it the Python and emscripten
# the wheel is built against. `pyodide xbuildenv search --all` lists them.
XBUILDENV="${XBUILDENV:-314.0.6}"
EMSCRIPTEN="${EMSCRIPTEN:-5.0.3}"

mkdir -p "$BUILD" "$DIST"

# -- the cross build toolchain ------------------------------------------------

if [ ! -d "$BUILD/venv" ]; then
    echo ">> creating the build venv"
    uv venv "$BUILD/venv" --python 3.14 -q
    uv pip install --python "$BUILD/venv/bin/python" -q pyodide-build
fi

export PATH="$BUILD/venv/bin:$PATH"

if ! pyodide xbuildenv search 2>/dev/null | grep -q "^│ $XBUILDENV .*Yes"; then
    true  # `search` lists what is installable, not what is installed
fi

echo ">> installing the Pyodide cross build environment $XBUILDENV"
pyodide xbuildenv install "$XBUILDENV" 2>&1 | tail -1

if [ ! -d "$BUILD/emsdk" ]; then
    echo ">> fetching emsdk"
    git clone --depth 1 https://github.com/emscripten-core/emsdk.git "$BUILD/emsdk"
fi

if [ ! -d "$BUILD/emsdk/upstream/emscripten" ]; then
    echo ">> installing emscripten $EMSCRIPTEN (this is the slow part)"
    "$BUILD/emsdk/emsdk" install "$EMSCRIPTEN"
fi

"$BUILD/emsdk/emsdk" activate "$EMSCRIPTEN" > /dev/null
# shellcheck disable=SC1091
source "$BUILD/emsdk/emsdk_env.sh" 2> /dev/null

# -- the kernel ---------------------------------------------------------------

# `parallel` off: Pyodide has no pthreads and rayon's pool cannot be built
# there.
export MATURIN_PEP517_ARGS="--no-default-features --features pyo3"

echo ">> building the kernel wheel"
rm -rf "$ROOT/kernel/dist"
(cd "$ROOT/kernel" && pyodide build 2>&1 | tail -2)

WHEEL="$(ls "$ROOT"/kernel/dist/*pyemscripten*.whl "$ROOT"/kernel/dist/*emscripten*.whl 2>/dev/null | head -1)"

if [ -z "$WHEEL" ]; then
    echo "no wheel was produced" >&2
    exit 1
fi

rm -f "$DIST"/*.whl
cp "$WHEEL" "$DIST/"

# -- seer, and the vocabulary -------------------------------------------------

# The page holds its Python inside JS template literals, so a backtick or a
# ${ in there silently truncates the script and the page dies on load. Cheap to
# check, and invisible if you only read the file.
echo ">> checking index.html"
python3 - "$HERE/index.html" <<'CHECK'
import re
import sys

page = open(sys.argv[1], encoding="utf-8").read()
blocks = re.findall(r"runPython\(`(.*?)`\)", page, re.S)

if not blocks:
    sys.exit("no embedded python found - has the page been restructured?")

for i, block in enumerate(blocks, 1):
    for needle in ("`", "${"):
        if needle in block:
            sys.exit(f"embedded python block {i} contains {needle!r}, "
                     "which ends the JavaScript template literal holding it")

print(f"   {len(blocks)} embedded python blocks, no template literal escapes")
CHECK

echo ">> packing the seer sources"
rm -f "$DIST/seer.zip"
# tests/ rides along so the corpus can be run inside the browser too, which
# is how the modelling is checked against the WebAssembly kernel.
(cd "$ROOT" && zip -q -r "$DIST/seer.zip" \
    seer/src seer/core.py seer/main.py seer/schema.sql seer/tests \
    -x '*__pycache__*' '*.pyc')

echo ">> copying the vocabulary"
cp "$ROOT/vocabulary.tiktoken" "$DIST/"

cat > "$DIST/manifest.json" <<JSON
{
  "wheel": "$(basename "$WHEEL")",
  "xbuildenv": "$XBUILDENV",
  "emscripten": "$EMSCRIPTEN",
  "pyodide": "v$XBUILDENV"
}
JSON

echo
echo "built into $DIST:"
ls -la "$DIST" | tail -n +2 | awk '{printf "  %-60s %10s\n", $NF, $5}'
echo
echo "now run ./serve.py and open http://127.0.0.1:8000/ in Firefox"
