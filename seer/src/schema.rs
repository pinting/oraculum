use std::collections::HashMap;

const SKIP_PREFIXES: &[&str] = &[
    "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT",
];

fn find_matching_paren(input: &str, open: usize) -> Option<usize> {
    let mut depth = 0;

    for (i, c) in input[open..].char_indices() {
        match c {
            '(' => depth += 1,
            ')' => {
                depth -= 1;

                if depth == 0 {
                    return Some(open + i);
                }
            }
            _ => {}
        }
    }

    None
}

pub fn parse_schema(input: &str) -> Option<HashMap<String, Vec<String>>> {
    let mut tables = HashMap::new();

    let upper = input.to_uppercase();
    let mut pos = 0;

    while let Some(start) = upper[pos..].find("CREATE TABLE") {
        let start = pos + start + "CREATE TABLE".len();

        let name_start = upper[start..].find(|c: char| !c.is_whitespace())? + start;
        let name_end = upper[name_start..].find(|c: char| c.is_whitespace() || c == '(')? + name_start;
        let table_name = input[name_start..name_end].to_string();

        let paren_open = input[name_end..].find('(')? + name_end;
        let paren_close = find_matching_paren(input, paren_open)?;
        let body = &input[paren_open + 1..paren_close];

        let mut columns = Vec::new();

        for line in body.lines() {
            let trimmed = line.trim();

            if trimmed.is_empty() {
                continue;
            }

            let first_word = trimmed.split_whitespace().next().unwrap_or("");
            let first_upper = first_word.to_uppercase();

            if SKIP_PREFIXES.iter().any(|p| first_upper.starts_with(p)) {
                continue;
            }

            columns.push(first_word.to_string());
        }

        tables.insert(table_name, columns);

        pos = paren_close + 1;
    }

    if tables.is_empty() {
        return None;
    }

    Some(tables)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_simple_schema() {
        let schema = "
CREATE TABLE users (
    id INTEGER,
    email TEXT
);";

        let tables = parse_schema(schema).unwrap();

        assert_eq!(tables.len(), 1);
        assert_eq!(tables["users"], vec!["id", "email"]);
    }

    #[test]
    fn parse_nested_parens() {
        let schema = "
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);";

        let tables = parse_schema(schema).unwrap();
        let cols = &tables["orders"];

        assert_eq!(cols, &vec!["id", "user_id", "total", "status"]);
    }

    #[test]
    fn parse_multiple_tables_with_nested_parens() {
        let schema = "
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total DECIMAL(10, 2),
    status TEXT DEFAULT 'pending'
);";

        let tables = parse_schema(schema).unwrap();

        assert_eq!(tables.len(), 2);
        assert_eq!(tables["users"], vec!["id", "name", "email"]);
        assert_eq!(tables["orders"], vec!["id", "user_id", "total", "status"]);
    }
}
