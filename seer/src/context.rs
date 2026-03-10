use std::collections::HashMap;
use std::fmt;
use rustc_hash::FxHashMap;

use crate::many_resolver::ManyResolver;
use crate::one_resolver::OneResolver;

#[derive(Clone)]
pub struct Context {
    global: ManyResolver<String, String>,
    namespaces: FxHashMap<String, OneResolver<String, String>>,
    tables: HashMap<String, Vec<String>>,
    current_namespace: String,
}

impl Context {
    pub fn new(tables: HashMap<String, Vec<String>>) -> Self {
        let global = ManyResolver::new(tables.clone());

        Self {
            global,
            namespaces: FxHashMap::default(),
            tables,
            current_namespace: String::new(),
        }
    }

    pub fn set_current_namespace(&mut self, namespace: &str) {
        self.current_namespace = namespace.to_string();
    }

    pub fn use_field(&mut self, field: &str) -> Option<bool> {
        if self.current_namespace.is_empty() {
            return self.global.use_field(field.to_string());
        }

        let namespace = self.current_namespace.clone();

        self.current_namespace.clear();

        if !self.namespaces.contains_key(&namespace) {
            self.namespaces.insert(namespace.to_string(), OneResolver::new(self.tables.clone()));
        }

        self.namespaces.get_mut(&namespace).unwrap().use_field(field.to_string())
    }

    pub fn get_fields(&self) -> Vec<String> {
        if self.current_namespace.is_empty() {
            return self.global.get_fields().to_vec();
        }

        if let Some(resolver) = self.namespaces.get(&self.current_namespace) {
            return resolver.get_fields().to_vec();
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

    pub fn get_required_tables(&self) -> HashMap<String, Vec<String>> {
        let mut result = HashMap::new();

        let global = self.global.get_required_tables();

        if !global.is_empty() {
            result.insert(String::new(), global);
        }

        for (namespace, resolver) in &self.namespaces {
            let tables = resolver.get_required_tables();

            if !tables.is_empty() {
                result.insert(namespace.clone(), tables);
            }
        }

        result
    }

    pub fn use_table(&mut self, namespace: &str, table: &str) -> Option<()> {
        if namespace.is_empty() {
            return self.global.use_table(&table.to_string());
        }

        self.namespaces.get_mut(namespace)?.use_table(&table.to_string())
    }

    pub fn is_satisfied(&self) -> bool {
        self.global.is_satisfied() && self.namespaces.values().all(|g| g.is_satisfied())
    }
}

impl fmt::Display for Context {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (namespace, tables) in self.get_required_tables() {
            write!(f, "`{}`: `{}` ", namespace, tables.join(", "))?;
        }

        Ok(())
    }
}
