use std::collections::HashMap;

use rustc_hash::FxHashMap;

use crate::many_resolver::ManyResolver;
use crate::one_resolver::OneResolver;

pub struct Context {
    global: ManyResolver<String, String>,
    namespaces: FxHashMap<String, OneResolver<String, String>>,
    tables: HashMap<String, Vec<String>>,
}

impl Context {
    pub fn new(tables: HashMap<String, Vec<String>>) -> Self {
        let resolver = ManyResolver::new(tables.clone());

        Self {
            global: resolver,
            namespaces: FxHashMap::default(),
            tables,
        }
    }

    pub fn use_field(&mut self, namespace: &str, field: String) -> Option<bool> {
        if namespace.is_empty() {
            return self.global.use_field(field);
        }

        if !self.namespaces.contains_key(namespace) {
            self.namespaces.insert(namespace.to_string(), OneResolver::new(self.tables.clone()));
        }

        self.namespaces.get_mut(namespace).unwrap().use_field(field)
    }

    pub fn get_fields(&self, namespace: &str) -> Vec<String> {
        if namespace.is_empty() {
            return self.global.get_fields().to_vec();
        }

        if let Some(guesser) = self.namespaces.get(namespace) {
            return guesser.get_fields().to_vec();
        }

        self.get_all_fields()
    }

    fn get_all_fields(&self) -> Vec<String> {
        let mut fields: Vec<String> = self.tables.values()
            .flat_map(|v| v.iter().cloned())
            .collect::<std::collections::HashSet<_>>()
            .into_iter()
            .collect();

        fields.sort();

        fields
    }

    pub fn get_required_tables(&mut self) -> HashMap<String, Vec<String>> {
        let mut result = HashMap::new();

        let global = self.global.get_required_tables();

        if !global.is_empty() {
            result.insert(String::new(), global);
        }

        for (namespace, guesser) in &mut self.namespaces {
            let tables = guesser.get_required_tables();

            if !tables.is_empty() {
                result.insert(namespace.clone(), tables);
            }
        }

        result
    }

    pub fn use_table(&mut self, namespace: &str, table: &str) -> Option<bool> {
        if namespace.is_empty() {
            return self.global.use_table(&table.to_string());
        }

        self.namespaces.get_mut(namespace)?.use_table(&table.to_string())
    }

    pub fn is_satisfied(&self) -> bool {
        self.global.is_satisfied() && self.namespaces.values().all(|g| g.is_satisfied())
    }
}
