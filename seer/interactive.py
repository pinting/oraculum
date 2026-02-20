import sys

import numpy as np
from numpy.typing import NDArray

import seer
from core import set_schema, schema, VOCABULARY_PATH, EOS_ID, load_vocabulary, init_engine

set_schema("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);
""")

def read_token(route_ids: NDArray[np.unsignedinteger]) -> int | None:
    while True:
        try:
            input_str: str = input("> ").rstrip("\n")
        except EOFError:
            print("\nExiting")

            return None

        if not input_str:
            print("Empty input")

            continue

        token_id: int | None = seer.get_token_id(input_str)

        if token_id is not None and token_id in route_ids:
            return token_id

        print("Invalid or non-existent token!")

def main() -> None:
    try:
        raw_vocabulary: bytes = load_vocabulary(VOCABULARY_PATH)

        init_engine(raw_vocabulary, EOS_ID, schema)

        current: str = ""

        while True:
            route_ids: NDArray[np.unsignedinteger] = seer.routes()

            if route_ids.size == 0:
                break

            seen: set[str] = set()
            routes: list[str] = []

            for tid in route_ids:
                token: str | None = seer.get_token(int(tid))

                if not token or token in seen:
                    continue

                if token.isspace() and token != " ":
                    continue

                seen.add(token)
                routes.append(f"`{token}`")

            print("\nRoutes:", " ".join(routes))

            selected_token_id: int | None = read_token(route_ids)

            if selected_token_id is None:
                return

            selected_token: str | None = seer.get_token(selected_token_id)

            if selected_token:
                current += selected_token

            print(f"Current: '{current}'")

            result: int = seer.feed(selected_token_id)

            if result != 0:
                break

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
