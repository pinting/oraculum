from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SCHEMA_PLACEHOLDER: str = "<!-- SCHEMA -->"
RUNTIME_PLACEHOLDER: str = "<!-- RUNTIME -->"

# The two sequences that end a JavaScript template literal early.
FORBIDDEN: tuple[str, ...] = ("`", "${")

def forbidden_in(source: str, what: str) -> None:
    """Fail if the text would truncate the literal it is about to land in."""

    for needle in FORBIDDEN:
        if needle in source:
            sys.exit(
                f"{what} contains {needle!r}, which ends the JavaScript "
                "template literal holding it"
            )

def check(page: str) -> int:
    """Fail if any embedded Python block would truncate its template literal."""

    blocks: list[str] = re.findall(r"runPython\(`(.*?)`\)", page, re.S)

    if not blocks:
        sys.exit("no embedded python found - has the page been restructured?")

    for index, block in enumerate(blocks, 1):
        forbidden_in(block, f"embedded python block {index}")

    return len(blocks)

def substitute(page: str, placeholder: str, text: str, source: Path) -> str:
    if placeholder not in page:
        sys.exit(f"the template has no {placeholder} for {source}")

    return page.replace(placeholder, text)

def main(argv: list[str]) -> int:
    if len(argv) != 5:
        sys.exit(
            f"usage: {argv[0]} <index.template.html> <schema.sql> "
            "<runtime.py> <index.html>"
        )

    template, schema_path, runtime_path, target = (Path(a) for a in argv[1:])

    runtime: str = runtime_path.read_text(encoding="utf-8")

    forbidden_in(runtime, str(runtime_path))

    page: str = template.read_text(encoding="utf-8")

    page = substitute(page, RUNTIME_PLACEHOLDER, runtime, runtime_path)

    # It lands inside a <textarea>, so only these three can end it early.
    schema: str = html.escape(schema_path.read_text(encoding="utf-8"), quote=False)

    page = substitute(page, SCHEMA_PLACEHOLDER, schema, schema_path)

    blocks: int = check(page)

    target.write_text(page, encoding="utf-8")

    print(f"   {blocks} embedded python block(s), runtime and schema substituted")

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
