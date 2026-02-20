use std::collections::HashSet;

use crate::graph::{Column, Table};

const SKIP_PREFIXES: &[&str] = &[
    "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT",
];

pub fn parse_schema(input: &str) -> Option<(HashSet<Column>, HashSet<Table>)> {
    let mut columns = HashSet::new();
    let mut tables = HashSet::new();

    let upper = input.to_uppercase();
    let mut pos = 0;

    while let Some(start) = upper[pos..].find("CREATE TABLE") {
        let start = pos + start + "CREATE TABLE".len();

        let name_start = upper[start..].find(|c: char| !c.is_whitespace())? + start;
        let name_end = upper[name_start..].find(|c: char| c.is_whitespace() || c == '(')? + name_start;
        let table_name = input[name_start..name_end].to_string();

        let paren_open = input[name_end..].find('(')? + name_end;
        let paren_close = input[paren_open..].find(')')? + paren_open;
        let body = &input[paren_open + 1..paren_close];

        tables.insert(Table { name: table_name.clone() });

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

            let col_name = first_word.to_string();

            columns.insert(Column {
                name: col_name,
                table_name: table_name.clone(),
            });
        }

        pos = paren_close + 1;
    }

    if tables.is_empty() {
        return None;
    }

    Some((columns, tables))
}
