# oraculum in the browser

The whole thing - the Rust kernel and seer on top of it - cross compiled to
WebAssembly and running in a tab. No server does any of the work; the page
fetches a wheel and a 4.8MB vocabulary and everything after that is local.

```sh
./build.sh     # first run downloads ~700MB of toolchain, later runs do not
./serve.py     # then open http://127.0.0.1:8000/
```

## What had to change

**SageMath had to go.** It does not compile to WebAssembly and never will - it
is a Python distribution wrapped around PARI, Singular, Flint and friends. seer
used it for two things, a boolean algebra over table variables and a
multigraph.

Both were put behind protocols in `seer/src/backend.py` at first, with a pure
Python implementation next to the SageMath one, and the browser got the pure
one. Then both moved into the kernel, which was already being cross compiled -
the algebra as a port of what PolyBoRi gives `BooleanPolynomialRing`, the
polynomial held as a zero-suppressed decision diagram, and the graph built
around contraction being the only mutation a join performs. At that point the
two Python implementations had nothing left to do and were deleted, protocols
and all: the browser and the desktop run the same code, and
`seer/tests/model.py` checks it against a brute force reference.

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
SageMath is still selectable wherever it imports, and the native wheel is now a
real cp314 one rather than abi3.

## The toolchain

Pyodide pins an exact emscripten per release and a wheel built against the
wrong one will not load, so `build.sh` installs both rather than trusting
whatever is on PATH:

| piece | version | why that one |
| --- | --- | --- |
| Pyodide cross build env | 314.0.6 | the Python 3.14 line, which is what seer's `requires-python` wants |
| emscripten | 5.0.3 | what that cross build environment was built with |
| PyO3 | 0.29 | the first line that supports Python 3.14 outright |

To move to a different Pyodide, `pyodide xbuildenv search --all` lists the
combinations and `XBUILDENV=... EMSCRIPTEN=... ./build.sh` builds against one.

## Layout

    build.sh          builds everything into dist/
    serve.py          static server; sets the .wasm MIME type and substitutes
                      seer/schema.sql into the page
    index.html        the demo - the whole UI, deliberately in one file
    dist/             gitignored build output
      kernel-*.whl    the kernel, cross compiled
      seer.zip        the seer sources, unpacked into the emscripten FS
      vocabulary.tiktoken
      manifest.json   wheel filename and the Pyodide version to load

## Is it actually right?

`seer/tests/cases.yaml` ships inside `seer.zip`, so the corpus that guards the
native build can be run against the WebAssembly one. All 342 records behave
there exactly as they do natively.

## The schema

`serve.py` substitutes `seer/schema.sql` into the page's textarea as it serves
it, so the schema is there on first paint rather than a dozen seconds later
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
