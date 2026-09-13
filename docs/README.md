# oraculum in the browser

The whole thing - the Rust kernel and seer on top of it - cross compiled to
WebAssembly and running in a tab. No server does any of the work; the page
fetches a wheel and a 4.8MB vocabulary and everything after that is local.

```sh
make docs                               # at the root; first run downloads ~1.7GB
python3 -m http.server --directory docs # then open http://127.0.0.1:8000/
```

Any static server will do. The page fetches Pyodide from a CDN and everything
else from its own directory as bytes, so there is no media type here that a
server has to get right.

`make docs` is two halves. seer's Makefile cross compiles the kernel, because
that is the same build it does natively with a different toolchain; the
Makefile at the root does the bundling, because a page made of the kernel *and*
seer *and* the vocabulary belongs to neither of them - and bundling it is the
only thing that Makefile does. What comes out is `docs/`, which GitHub Pages
serves as the site when the repository publishes from the `/docs` folder, so
committing it is publishing it.

## What had to change

**The modelling had to move into the kernel.** seer's two modelling primitives
- a boolean algebra over table variables and a multigraph over foreign keys -
were Python libraries that do not compile to WebAssembly, so the browser could
have the indexes but not the model that drives them.

Both are in the kernel now, which was already being cross compiled: the algebra
holds the polynomial as a zero-suppressed decision diagram, the way PolyBoRi
does, and the graph is built around contraction being the only mutation a join
performs. The browser and the desktop run the same code.

**The kernel had to lose its threads.** rayon was unconditional and
`Runner::new` built a pool even for a single worker, which fails outright under
Pyodide - there are no pthreads to build it from. The `parallel` feature is off
for this build and `kernel/src/runtime/pool.rs` supplies serial stand-ins.

**PyO3 had to be upgraded.** 0.22 tops out at Python 3.13 and was being built
against 3.14 anyway, via `PYO3_USE_ABI3_FORWARD_COMPATIBILITY`. On x86_64 that
got away with it. On wasm32 it does not - `pyo3-ffi` reads a `PyObject` field
at the 3.13 offset, and where a 64-bit pointer landed on something harmless a
32-bit one lands on `0xffffffff`:

    panicked at pyo3-ffi-0.22.6/src/object.rs:111:
    misaligned pointer dereference: address must be a multiple of 0x4
    but is 0xffffffff

0.29 supports 3.14 properly and the flag is gone from both build paths.

None of the three costs the native build anything: `parallel` is on by default,
and the native wheel is now a real cp314 one rather than abi3.

## The toolchain, and why every version is written down

Pyodide pins an exact Emscripten per release and a wheel built against the
wrong one will not load. Neither is a thing to leave to whatever is on PATH, so
`pyodide-build` installs both at named versions - and it is itself installed at
a named version, into a venv of a named Python, by a Makefile that names them
all.

| piece | version | why that one |
| --- | --- | --- |
| Pyodide, and its cross build env | 314.0.6 | the Python 3.14 line, which is what seer's `requires-python` wants |
| emscripten | 5.0.3 | what that cross build environment was built with |
| pyodide-build | 0.39.0 | the one that drives them; `install-emscripten` is its command |
| PyO3 | 0.29 | the first line that supports Python 3.14 outright |
| sqlglot | 30.18.0 | vendored as a wheel beside the page, not resolved in the browser |

They live in `../versions.mk` with everything else this repository pins, and
every one of them is `?=`, so the environment wins:

```sh
PYODIDE_VERSION=315.0.0 EMSCRIPTEN_VERSION=5.1.0 make docs
```

`pyodide xbuildenv search --all` lists which combinations exist.

The one thing left unpinned is emsdk itself, which pyodide-build clones at its
tip - but it clones it only to install the pinned Emscripten, which
is the part that ends up in the wheel. Doing it through pyodide-build rather
than by hand also gets Pyodide's own patches applied, which the script this
replaced did not.

The built page names no version of its own. It reads `dist/manifest.json`,
which the bundler writes out of the same variables, and installs the two wheels
sitting beside it - so what the browser runs is what the build pinned, and
nothing is resolved against PyPI at load time.

## Layout

This directory is both the front end's source and the published site. GitHub
Pages serves it as the site root; `make docs` at the repository root writes the
built half of it.

Tracked, and edited by hand:

    index.template.html  the demo - the markup, the CSS and the JavaScript
    runtime.py           the Python the page runs inside Pyodide
    render.py            injects runtime.py and seer/schema.sql into the
                         template, and refuses anything that would truncate
                         the literal the Python lands in
    README.md            this

Tracked, and written by `make docs`:

    index.html           the template, with runtime.py and the schema in it
    .nojekyll            so publishing does not run Jekyll over it
    dist/
      kernel-*.whl       the kernel, cross compiled
      sqlglot-*.whl      vendored, so the browser resolves nothing
      seer.zip           the seer sources, unpacked into the emscripten FS
      vocabulary.tiktoken
      manifest.json      every version the build pinned, and the two wheel names

The four source files are served alongside the site, which is harmless - they
are in a public repository either way, and `index.html` is what a visitor
lands on.

## Is it actually right?

`seer/cases.yaml` ships inside `seer.zip`, so the corpus that guards the
native build can be run against the WebAssembly one. All 342 records behave
there exactly as they do natively.

## The schema

`render.py` substitutes `seer/schema.sql` into the page's textarea at build
time, template to page - a static host has no server to do it on the way out, so the schema is there on first paint rather than a dozen seconds later
when Pyodide has booted far enough to read `core.SCHEMA`. It reads the same
file the native build uses, so there is no second copy to keep in step, and
editing that file shows up on the next reload without rebuilding anything.

Editing the box and pressing Reset rebuilds the engine over whatever is in it,
which does not touch the file.

## Notes

The page loads Pyodide itself from the jsDelivr CDN, so a first load needs the
network even though nothing after it does. The vocabulary is the slow part of
startup - 4.8MB parsed into three lookups - and the engine build after it takes
a moment more; the log in the page reports both.
