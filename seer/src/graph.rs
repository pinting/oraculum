use std::collections::HashSet;
use std::sync::Arc;

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum State {
    Literal(String),
    Regex(String),
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Column {
    pub name: String,
    pub table_name: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Table {
    pub name: String,
}

#[derive(Clone, Debug)]
pub struct Context {
    pub available_columns: HashSet<Column>,
    pub available_tables: HashSet<Table>,
    pub required_tables: HashSet<String>,
}

impl Context {
    pub fn new(columns: HashSet<Column>, tables: HashSet<Table>) -> Self {
        Self {
            available_columns: columns,
            available_tables: tables,
            required_tables: HashSet::new(),
        }
    }

    pub fn use_column(&self, col: &Column) -> Self {
        let mut next = self.clone();

        next.available_columns.retain(|c| c.name != col.name);
        next.required_tables.insert(col.table_name.clone());

        next
    }

    pub fn use_table(&self, tbl: &Table) -> Self {
        let mut next = self.clone();

        next.available_tables.remove(tbl);
        next.required_tables.remove(&tbl.name);

        next
    }

    pub fn has_fulfilled_dependencies(&self) -> bool {
        self.required_tables.is_empty()
    }
}

pub type Thunk = Arc<dyn Fn(Context) -> Vec<Node> + Send + Sync>;

type SelectorFn = Arc<dyn Fn(&Context) -> Vec<(String, Context)> + Send + Sync>;
type CompleteFn = Arc<dyn Fn(&Context) -> bool + Send + Sync>;

#[derive(Clone)]
struct Selector {
    select: SelectorFn,
    is_complete: CompleteFn,
}

pub struct Node {
    pub state: State,
    pub next_ctx: Context,
    pub thunk: Thunk,
}

pub fn terminal() -> Thunk {
    Arc::new(|_ctx: Context| vec![])
}

pub fn branch(thunks: Vec<Thunk>) -> Thunk {
    Arc::new(move |ctx: Context| {
        thunks.iter().flat_map(|t| t(ctx.clone())).collect()
    })
}

pub fn lit(word: &str, next: Thunk) -> Thunk {
    let word = word.to_string();

    Arc::new(move |ctx: Context| {
        vec![Node {
            state: State::Literal(word.clone()),
            next_ctx: ctx.clone(),
            thunk: next.clone(),
        }]
    })
}

pub fn exp(pattern: &str, next: Thunk) -> Thunk {
    let pattern = pattern.to_string();

    Arc::new(move |ctx: Context| {
        vec![Node {
            state: State::Regex(pattern.clone()),
            next_ctx: ctx.clone(),
            thunk: next.clone(),
        }]
    })
}

pub fn ws(next: Thunk) -> Thunk {
    exp("[ \n\t]+", next)
}

pub fn comma(next: Thunk) -> Thunk {
    exp("[ \n\t]*,[ \n\t]*", next)
}

fn any(select: SelectorFn, next: Thunk) -> Thunk {
    Arc::new(move |ctx: Context| {
        select(&ctx).into_iter().map(|(name, next_ctx)| {
            let select = select.clone();
            let next = next.clone();

            let thunk: Thunk = Arc::new(move |c: Context| {
                let mut thunks = vec![next.clone()];

                if !select(&c).is_empty() {
                    thunks.push(comma(any(select.clone(), next.clone())));
                }

                branch(thunks)(c)
            });

            Node {
                state: State::Literal(name),
                next_ctx,
                thunk,
            }
        }).collect()
    })
}

fn all(selector: Selector, next_phase: Thunk) -> Thunk {
    Arc::new(move |ctx: Context| {
        (selector.select)(&ctx).into_iter().map(|(name, next_ctx)| {
            let selector = selector.clone();
            let next_phase = next_phase.clone();

            let thunk: Thunk = Arc::new(move |c: Context| {
                let mut thunks: Vec<Thunk> = Vec::new();

                // Is selection completed, can we move on?
                if (selector.is_complete)(&c) {
                    thunks.push(next_phase.clone());
                }

                // Are there any leftovers here?
                if !(selector.select)(&c).is_empty() {
                    thunks.push(comma(all(selector.clone(), next_phase.clone())));
                }

                branch(thunks)(c)
            });

            Node {
                state: State::Literal(name),
                next_ctx,
                thunk,
            }
        }).collect()
    })
}

pub fn columns(next_phase: Thunk) -> Thunk {
    let select: SelectorFn = Arc::new(|ctx: &Context| {
        ctx.available_columns.iter().map(|col| {
            (col.name.clone(), ctx.use_column(col))
        }).collect()
    });

    any(select, next_phase)
}

pub fn tables(next_phase: Thunk) -> Thunk {
    let selector = Selector {
        select: Arc::new(|ctx: &Context| {
            ctx.available_tables.iter().map(|tbl| {
                (tbl.name.clone(), ctx.use_table(tbl))
            }).collect()
        }),
        is_complete: Arc::new(|ctx: &Context| ctx.has_fulfilled_dependencies()),
    };

    all(selector, next_phase)
}

pub fn root() -> Thunk {
    let end_query = lit(";", terminal());
    let select_tables = tables(end_query);
    let from_clause = lit("FROM", ws(select_tables));
    let select_columns = columns(ws(from_clause));

    lit("SELECT", ws(select_columns))
}
