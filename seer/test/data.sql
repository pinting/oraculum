-- Dummy rows for `schema.sql`, which the test suite runs every legal query
-- of the corpus against.
--
-- The data is small but not uniform, so the queries have something to say:
--
--   * some users have no posts (4, 7, 9, 11) and some posts no comments
--     (3, 11), so an outer join really pads with NULLs;
--   * every nullable column holds NULLs somewhere - `verified`, `created_at`,
--     `published_at` - so IS NULL selects rows;
--   * a few emails and first names start with `a`, a few titles share words,
--     and the timestamps straddle 2024, so LIKE, BETWEEN and the date literals
--     the corpus writes match some rows and not others;
--   * users have posted and commented unevenly, so GROUP BY ... HAVING and
--     the rankings have ties and gaps.
--
-- Every foreign key holds, and the suite loads this with them enforced.

INSERT INTO users (id, first_name, last_name, email, verified, created_at) VALUES
    (1, 'Alice', 'Anderson', 'alice@example.com', TRUE, '2023-11-02 09:15:00'),
    (2, 'Bob', 'Brown', 'bob@example.com', FALSE, '2024-01-10 14:30:00'),
    (3, 'Carol', 'Clark', 'carol@example.com', NULL, '2024-02-21 08:00:00'),
    (4, 'Dave', 'Davis', 'dave@example.org', TRUE, NULL),
    (5, 'Eve', 'Evans', 'eve@example.net', TRUE, '2024-03-05 19:45:00'),
    (6, 'Frank', 'Fischer', 'frank@example.com', NULL, '2024-05-17 11:20:00'),
    (7, 'Grace', 'Green', 'grace@example.com', FALSE, '2024-06-30 23:59:59'),
    (8, 'Heidi', 'Hall', 'heidi@example.org', TRUE, '2024-08-08 08:08:08'),
    (9, 'Ivan', 'Ivanov', 'ivan@example.com', NULL, NULL),
    (10, 'Judy', 'Jones', 'judy@example.com', TRUE, '2024-12-31 12:00:00'),
    (11, 'Mallory', 'Moore', 'mallory@example.net', FALSE, '2025-01-15 10:10:10'),
    (12, 'Ann', 'Adams', 'ann@example.com', TRUE, '2024-04-01 00:00:00');

INSERT INTO posts (id, user_id, title, body, published_at) VALUES
    (1, 1, 'Hello world', 'My first post.', '2024-01-01 10:00:00'),
    (2, 1, 'On SQL', 'Joins are graphs, and graphs are everywhere.', '2024-02-14 12:30:00'),
    (3, 1, 'Drafts', 'Not yet.', NULL),
    (4, 2, 'Bob writes', 'Short.', '2024-03-03 09:00:00'),
    (5, 3, 'Recipes', 'Bread, butter and patience.', '2024-05-20 18:45:00'),
    (6, 3, 'More recipes', 'Soup.', '2024-06-01 07:30:00'),
    (7, 5, 'Security', 'Rotate your keys.', '2024-07-04 16:00:00'),
    (8, 5, 'Privacy', 'Encrypt everything.', '2023-12-12 12:12:12'),
    (9, 6, 'Travel', 'Lisbon in spring.', '2024-04-18 13:00:00'),
    (10, 8, 'Gardening', 'Tomatoes need sun.', '2024-09-09 09:09:09'),
    (11, 8, 'Composting', 'Patience.', NULL),
    (12, 10, 'Year in review', 'It was a year.', '2024-12-31 23:00:00'),
    (13, 12, 'Ann on art', 'Colour and form.', '2024-04-02 10:00:00'),
    (14, 2, 'Bob again', 'Longer this time, with a great many more words.', '2024-10-10 10:10:10');

INSERT INTO comments (id, user_id, post_id, body) VALUES
    (1, 2, 1, 'Welcome!'),
    (2, 3, 1, 'Nice start.'),
    (3, 1, 2, 'Thanks for reading.'),
    (4, 5, 2, 'Graphs everywhere.'),
    (5, 4, 4, 'Short indeed.'),
    (6, 1, 5, 'Tasty.'),
    (7, 7, 5, 'Recipe please?'),
    (8, 3, 5, 'Coming soon.'),
    (9, 9, 7, 'Done.'),
    (10, 5, 7, 'Good advice.'),
    (11, 2, 9, 'Lisbon is lovely.'),
    (12, 6, 9, 'It is.'),
    (13, 8, 10, 'Mine too.'),
    (14, 10, 12, 'Happy new year.'),
    (15, 12, 13, 'Thanks!'),
    (16, 1, 13, 'Lovely colours.'),
    (17, 11, 14, 'Too long.'),
    (18, 2, 14, 'Fair.'),
    (19, 5, 8, 'Agreed.'),
    (20, 4, 6, 'Soup!');
