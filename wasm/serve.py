#!/usr/bin/env python3
"""Static server for the browser demo.

`python3 -m http.server` very nearly does, but it guesses `.wasm` wrong on some
systems and the browser refuses a WebAssembly module that did not arrive as
`application/wasm`.

The other thing it does is substitute `seer/schema.sql` into the page on the
way out, so the schema box is filled on first paint rather than a dozen seconds
later when Pyodide has finished booting and `core.SCHEMA` can be read. The file
is the one the native build uses, so there is no second copy to drift.
"""

from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
SCHEMA_PATH: Path = HERE.parent / "seer" / "schema.sql"

# What `index.html` carries where the schema goes.
PLACEHOLDER: bytes = b"<!--SCHEMA-->"

def page() -> bytes:
    """`index.html` with the schema substituted into the textarea."""

    html: bytes = (HERE / "index.html").read_bytes()

    try:
        schema: str = SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError:
        schema = f"-- {SCHEMA_PATH} could not be read"

    # It lands inside a <textarea>, so only these three can end it early.
    escaped: str = (
        schema.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )

    return html.replace(PLACEHOLDER, escaped.encode("utf-8"))

class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".whl": "application/octet-stream",
        ".tiktoken": "text/plain",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(HERE), **kwargs)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            body: bytes = page()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

            return

        super().do_GET()

    def end_headers(self) -> None:
        # Nothing here needs cross-origin isolation - the build is single
        # threaded, so there is no SharedArrayBuffer to unlock - but the
        # vocabulary is 4.8MB and revalidating it on every reload is tedious.
        self.send_header("Cache-Control", "no-cache")

        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        if "GET" in fmt % args and " 200 " not in fmt % args:
            super().log_message(fmt, *args)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--port", type=int, default=8000)

    port: int = parser.parse_args().port

    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        print(f"Serving {HERE} at http://127.0.0.1:{port}/")
        print("Open that in Firefox. Ctrl-C to stop.")

        httpd.serve_forever()

if __name__ == "__main__":
    main()
