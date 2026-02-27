use std::collections::{HashMap, HashSet};
use std::fmt::Debug;
use std::hash::Hash;

pub struct OneResolver<T: Eq + Hash + Ord + Clone + Debug, F: Eq + Hash + Ord + Clone + Debug> {
    tables_by_field: HashMap<F, HashSet<T>>,
    candidates: HashSet<T>,
    fields: Vec<F>,
}

impl<T: Eq + Hash + Ord + Clone + Debug, F: Eq + Hash + Ord + Clone + Debug> OneResolver<T, F> {
    pub fn new(tables: HashMap<T, Vec<F>>) -> Self {
        let mut tables_by_field: HashMap<F, HashSet<T>> = HashMap::new();
        let mut candidates = HashSet::new();

        for (t, fields) in &tables {
            candidates.insert(t.clone());

            for field in fields {
                tables_by_field
                    .entry(field.clone())
                    .or_default()
                    .insert(t.clone());
            }
        }

        let mut guesser = Self {
            tables_by_field,
            candidates,
            fields: Vec::new(),
        };

        guesser.refresh();

        guesser
    }

    fn refresh(&mut self) {
        let fields: Vec<F> = self.tables_by_field
            .iter()
            .filter(|(_, tables)| tables.iter().any(|t| self.candidates.contains(t)))
            .map(|(field, _)| field.clone())
            .collect();

        self.fields = fields;
    }

    pub fn get_fields(&self) -> &[F] {
        &self.fields
    }

    pub fn use_field(&mut self, field: F) -> Option<bool> {
        let tables = self.tables_by_field.get(&field)?;
        let next: HashSet<T> = self.candidates.intersection(tables).cloned().collect();

        if next.is_empty() {
            return Some(false);
        }

        self.candidates = next;

        self.refresh();

        Some(true)
    }

    pub fn use_table(&mut self, table: &T) -> Option<bool> {
        if !self.candidates.contains(table) {
            return None;
        }

        self.candidates.retain(|t| t == table);

        self.refresh();

        Some(self.is_satisfied())
    }

    pub fn get_required_tables(&mut self) -> Vec<T> {
        if self.is_satisfied() {
            return vec![];
        }

        self.candidates.iter().cloned().collect()
    }

    pub fn is_satisfied(&self) -> bool {
        self.candidates.len() == 1
    }
}
