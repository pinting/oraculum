# Every version this repository pins, in one file, so that a build that works
# today works in ten years. Nothing is fetched from a network without a version
# next to it.
#
# All of them are `?=`, so the environment wins:
#
#     EMSCRIPTEN_VERSION=5.1.0 make docs
#     PYODIDE_XBUILDENV_PATH=~/.cache/pyodide-build make docs

# Where this file is, which is the top of the tree. `make -C seer` runs with
# seer as the working directory, so a relative path would resolve one level too
# deep.
REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# -- the interpreters ---------------------------------------------------------

PYTHON_VERSION            ?= 3.14.7

# Checked, not installed. Cargo.lock pins the dependency graph, which is the
# half that drifts, so a mismatched rustc gets a warning rather than a refusal.
RUST_VERSION              ?= 1.98.1

# make runs SHELL directly and will not search PATH for it.
UV                        ?= uv
BASH                      ?= $(shell command -v bash 2>/dev/null || echo /bin/bash)

# -- the native build ---------------------------------------------------------

MATURIN_VERSION           ?= 1.15.0
NUMPY_VERSION             ?= 2.5.3
SQLGLOT_VERSION           ?= 30.18.0
PYYAML_VERSION            ?= 6.0.3
LLAMA_CPP_PYTHON_VERSION  ?= 0.3.35

# -- the WebAssembly toolchain ------------------------------------------------

PYODIDE_BUILD_VERSION     ?= 0.39.0

# The Pyodide the page loads, and the cross-build environment the wheel is
# compiled against. They have to agree: a wheel built against one Pyodide's ABI
# will not import into another.
PYODIDE_VERSION           ?= 314.0.6
XBUILDENV_VERSION         ?= $(PYODIDE_VERSION)
EMSCRIPTEN_VERSION        ?= 5.0.3

# About 1.7GB. Point it at a shared cache to stop every clone paying for it
# again; the default keeps it inside the tree so `make distclean` can take it.
PYODIDE_XBUILDENV_PATH    ?= $(REPO_ROOT)/seer/.xbuildenv

# The only thing the built page fetches from anywhere but its own directory -
# the Pyodide distribution is far too large to vendor into a git repository.
PYODIDE_CDN               ?= https://cdn.jsdelivr.net/pyodide/v$(PYODIDE_VERSION)/full
PYPI                      ?= https://pypi.org
