"""Cases shared by both sides of the parity check."""

import random

SCHEMAS = [
    {"users": ["id", "first_name", "last_name", "email"],
     "posts": ["id", "user_id", "title", "body"],
     "comments": ["id", "user_id", "post_id", "title", "body"]},
    {"a": ["id", "x"], "b": ["id", "x", "y"], "c": ["id", "y", "z"], "d": ["z", "w"]},
    {"t1": ["k"], "t2": ["k"], "t3": ["k"], "t4": ["k", "m"]},
    {"solo": ["only"]},
    {"p": ["id", "q_id", "v"], "q": ["id", "r_id", "v"], "r": ["id", "v"],
     "s": ["id", "v", "w"], "u": ["w"]},
]

def _generate(seed: int = 0, count: int = 260):
    rnd = random.Random(seed)
    cases = []

    for _ in range(count):
        schema = rnd.choice(SCHEMAS)
        fields = sorted({f for columns in schema.values() for f in columns})
        tables = sorted(schema)
        ops = []

        for _ in range(rnd.randint(1, 6)):
            if rnd.random() < 0.65:
                ops.append(("field", rnd.choice(fields)))
            else:
                ops.append(("table", rnd.choice(tables)))

        cases.append((schema, ops))

    return cases

ROOT_CASES = _generate()

JOIN_SCHEMA = """
    CREATE TABLE users (
        id BIGINT PRIMARY KEY,
        email VARCHAR(255)
    );
    CREATE TABLE posts (
        id BIGINT PRIMARY KEY,
        user_id BIGINT REFERENCES users(id),
        editor_id BIGINT REFERENCES users(id),
        title VARCHAR(255)
    );
    CREATE TABLE comments (
        id BIGINT PRIMARY KEY,
        user_id BIGINT REFERENCES users(id),
        post_id BIGINT REFERENCES posts(id),
        body TEXT
    );
    CREATE TABLE tags (
        id BIGINT PRIMARY KEY,
        post_id BIGINT REFERENCES posts(id)
    );
"""

REQUIRED = [
    {"users", "posts", "comments"},
    {"users", "posts", "comments c"},
    {"users u", "posts p", "comments"},
    {"users", "tags"},
    {"posts", "tags", "comments", "users u"},
]

WALKS = [
    (0, "users", ["posts", "comments"]),
    (0, "comments", ["users", "posts"]),
    (1, "users", ["posts", "comments c"]),
    (1, "comments c", ["posts", "users"]),
    (2, "users u", ["posts p", "comments"]),
    (3, "users", ["posts", "tags"]),
    (4, "tags", ["posts", "comments", "users u"]),
    (4, "users u", ["comments", "posts", "tags"]),
]
