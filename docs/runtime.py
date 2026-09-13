"""The Python the page runs, inside Pyodide."""

import sys

sys.path.insert(0, "/pkg/seer")

import core
import main as driver

with open("/vocabulary.tiktoken", "rb") as handle:
    VOCABULARY = handle.read()

ENGINE = None

# The routes the engine stands at, as token -> token id, printable only. It is
# kept rather than recomputed because the search box asks for it on every
# keystroke, and walking a 262k route set per keystroke is not a search box.
ROUTES = {}

def refresh():
    """Read the route set the engine is offering into ROUTES."""

    global ROUTES

    ROUTES = {}

    for token_id in ENGINE.routes().tolist():
        token = ENGINE.get_token(token_id)

        if token is not None and driver.printable(token):
            ROUTES[token] = token_id

def build(schema_text):
    """Build an engine over this schema, reusing the parsed vocabulary.

    core.init_engine would parse those 4.8MB again every time, which is most of
    a second for nothing - the vocabulary does not depend on the schema.
    """

    global ENGINE

    core.shutdown()
    core.set_schema(schema_text)

    if core.get_vocabulary() is None and core.init_vocabulary(VOCABULARY, core.EOS_ID) != 0:
        raise RuntimeError("Failed to initialize vocabulary")

    if core.init_schema(schema_text.encode("utf-8"), 1) != 0:
        raise RuntimeError("Failed to initialize schema")

    ENGINE = core.get_engine()

    refresh()

def view(prefix, limit):
    """Everything the page draws, in one crossing of the JS boundary.

    There is one list, and the filter is what is typed into it.

    With nothing typed it is the route set main.py's interactive loop offers,
    narrowed the way that loop narrows it: after SELECT the projection is an
    expression head offering most of the vocabulary, so an unfiltered list
    buries the field names under every token starting with a lowercase letter.

    With something typed the narrowing is dropped, because reaching what it hid
    is the whole reason for typing. Shorter tokens come first, so a single
    letter offers the one character token before the twelve character word that
    happens to start with it.
    """

    prefix = str(prefix)
    limit = int(limit)

    if prefix:
        tokens = sorted(ROUTES, key=lambda token: (len(token), token))
        tokens = [token for token in tokens if token.startswith(prefix)]
        narrowed = False
    else:
        tokens = sorted(ROUTES)
        narrowed = False

        if len(tokens) > driver.ROUTE_LIMIT:
            tokens, narrowed = driver.narrow(ENGINE, tokens)

    shown = tokens[:limit]

    # With a prefix the tokens that do not match are excluded rather than
    # hidden; with none, what narrowing dropped is hidden and worth counting.
    pool = len(tokens) if prefix else len(ROUTES)

    return {
        "routes": [(ROUTES[token], token) for token in shown],
        "more": narrowed or pool > len(shown),
        "hidden": pool - len(shown),
        "matching": len(tokens),
        "total": len(ROUTES),
        "exact": ROUTES.get(prefix, -1),
        "matched": ENGINE.matched(),
        "completed": bool(ENGINE.is_completed()),
    }

def feed(token_id):
    """Take the token and move the engine on to what follows it."""

    ENGINE.feed(int(token_id))

    refresh()
