-- A schema that is hard on the resolvers, for `python -m tools.fuzz`.
--
--   * `users.manager_id` points back at `users`, so `users` and `users AS u`
--     are joined by a key of their own;
--   * `messages` points at `users` twice, which is two edges between the
--     same pair of tables;
--   * `payload` is binary and `meta` a type nobody recognises, and each is
--     the only column of its class - nothing can stand opposite either;
--   * `flags` holds booleans only, which no function takes;
--   * `tags.id` is an INT where every other key is a BIGINT.
--
-- Valid in both SQLite and PostgreSQL, so `tools/postgres.py` can run what
-- the walks write over it.

CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    manager_id BIGINT REFERENCES users(id),
    active BOOLEAN
);

CREATE TABLE messages (
    id BIGINT PRIMARY KEY,
    sender_id BIGINT NOT NULL REFERENCES users(id),
    recipient_id BIGINT REFERENCES users(id),
    body TEXT,
    sent_at TIMESTAMP,
    payload BYTEA
);

CREATE TABLE tags (
    id INT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    meta JSON
);

CREATE TABLE message_tags (
    message_id BIGINT NOT NULL REFERENCES messages(id),
    tag_id INT NOT NULL REFERENCES tags(id),
    weight DECIMAL(10, 2)
);

CREATE TABLE flags (
    a BOOLEAN,
    b BOOLEAN
);
