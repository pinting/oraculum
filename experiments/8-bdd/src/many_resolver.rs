use std::collections::{HashMap, HashSet};
use std::fmt::Debug;
use std::hash::Hash;
use boolean_expression::{BDDFunc, BDD, BDD_ONE, BDD_ZERO};

#[derive(Clone)]
pub struct ManyResolver<T: Eq + Hash + Ord + Clone + Debug, F: Eq + Hash + Clone + Debug> {
    bdd: BDD<T>,
    constraints: HashMap<F, BDDFunc>,
    current: BDDFunc,
    fields: Vec<F>,
}

impl<T: Eq + Hash + Ord + Clone + Debug, F: Eq + Hash + Clone + Debug> ManyResolver<T, F> {
    pub fn new(tables: HashMap<T, Vec<F>>) -> Self {
        let mut bdd = BDD::new();
        let mut tables_by_field: HashMap<F, HashSet<T>> = HashMap::new();
        let mut constraints = HashMap::new();

        for (t, fields) in &tables {
            for field in fields {
                tables_by_field
                    .entry(field.clone())
                    .or_default()
                    .insert(t.clone());
            }
        }

        for (field, tables) in &tables_by_field {
            let terminals: Vec<BDDFunc> = tables.iter().map(|t| bdd.terminal(t.clone())).collect();

            let mut zero_true = BDD_ONE;
            let mut one_true = BDD_ZERO;

            for &t in &terminals {
                let not_t = bdd.not(t);

                let keep_one = bdd.and(one_true, not_t);
                let make_one = bdd.and(zero_true, t);

                one_true = bdd.or(keep_one, make_one);
                zero_true = bdd.and(zero_true, not_t);
            }

            constraints.insert(field.clone(), one_true);
        }

        let mut resolver = Self {
            bdd,
            constraints,
            current: BDD_ONE,
            fields: Vec::new(),
        };

        resolver.refresh();

        resolver
    }

    fn refresh(&mut self) {
        let fields = self.constraints.iter()
            .filter(|&(_, &constrain)| {
                let combined = self.bdd.and(self.current, constrain);

                self.bdd.sat(combined)
            })
            .map(|(field, _)| field.clone())
            .collect();

        self.fields = fields;
    }

    pub fn use_table(&mut self, table: &T) -> Option<()> {
        if !self.bdd.labels().contains(table) {
            return None;
        }

        let mut bdd: BDD<T> = self.bdd.clone();
        let next = bdd.restrict(self.current, table.clone(), true);

        if next == BDD_ZERO {
            return None;
        }

        self.bdd = bdd;
        self.current = next;

        Some(())
    }

    pub fn get_fields(&self) -> &[F] {
        &self.fields
    }

    pub fn use_field(&mut self, field: F) -> Option<bool> {
        let constrain = *self.constraints.get(&field)?;
        let next = self.bdd.and(self.current, constrain);

        if !self.bdd.sat(next) {
            return Some(false);
        }

        self.current = next;

        self.refresh();

        Some(true)
    }

    pub fn get_required_tables(&self) -> Vec<T> {
        if self.is_satisfied() {
            return vec![];
        }

        let mut bdd: BDD<T> = self.bdd.clone();

        bdd.labels().into_iter().filter(|label| {
            let pos = bdd.restrict(self.current, label.clone(), true);
            let neg = bdd.restrict(self.current, label.clone(), false);

            pos != neg && pos != BDD_ZERO
        }).collect()
    }

    pub fn is_satisfied(&self) -> bool {
        let unsatified_tables = self.bdd.labels();
        let mut values = HashMap::with_capacity(unsatified_tables.len());

        for l in unsatified_tables {
            values.insert(l, false);
        }

        self.bdd.evaluate(self.current, &values)
    }
}