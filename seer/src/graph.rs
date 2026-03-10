use std::sync::Arc;

use crate::context::Context;
use crate::engine::{Node, Selector, Thunk};
use crate::factory::IndexDraft;

fn branch(thunks: Vec<Thunk>) -> Thunk {
    Thunk::new(move |ctx: Arc<Context>| {
        thunks.iter().flat_map(|t| t.call(ctx.clone()).unwrap_or_default()).collect()
    })
}

fn lat(word: &str, selector: Selector, next: Thunk) -> Thunk {
    let word = word.to_string();

    Thunk::new(move |ctx: Arc<Context>| {
        let node = Node::new(
            IndexDraft::Lattice(word.clone()),
            ctx,
            selector.clone(),
            next.clone(),
        );

        vec![node]
    })
}

fn exp(pattern: &str, selector: Selector, next: Thunk) -> Thunk {
    let pattern = pattern.to_string();

    Thunk::new(move |ctx: Arc<Context>| {
        let node = Node::new(
            IndexDraft::Expression(pattern.clone()),
            ctx,
            selector.clone(),
            next.clone(),
        );

        vec![node]
    })
}

fn ws(next: Thunk) -> Thunk {
    exp(r"[ \n\t]+", None, next)
}

fn comma(next: Thunk) -> Thunk {
    exp(r"[ \n\t]*,[ \n\t]*", None, next)
}

fn dot(next: Thunk) -> Thunk {
    lat(".", None, next)
}

fn table(next: Thunk) -> Thunk {
    Thunk::new(move |ctx: Arc<Context>| {
        let tables = ctx.get_required_tables();

        let mut nodes = Vec::new();

        for (namespace, tables) in &tables {
            for table in tables {
                let ctx = ctx.clone();
                let next = next.clone();

                let selector: Selector = {
                    let namespace = namespace.clone();
                    let table = table.clone();
                    
                    Some(Arc::new(move |ctx: Arc<Context>, _: String| {
                        let mut ctx = (*ctx).clone();

                        ctx.use_table(namespace.as_str(), table.as_str());

                        Arc::new(ctx)
                    }))
                };

                if namespace.is_empty() {
                    let node = Node::new(
                        IndexDraft::Lattice(table.clone()),
                        ctx.clone(),
                        selector,
                        next,
                    );

                    nodes.push(node);

                    continue;

                }

                let next = lat(namespace, selector, next);
                let next = ws(next);
                let next = lat("AS", None, next);
                let next = ws(next);

                let node = Node::new(
                    IndexDraft::Lattice(table.clone()),
                    ctx.clone(),
                    None,
                    next,
                );

                nodes.push(node);
            }
        }

        nodes
    })
}

fn tables(next: Thunk) -> Thunk {
    let fork = Thunk::deferred(move || {
        let next = next.clone();

        Thunk::new(move |ctx| {
            if ctx.is_satisfied() {
                return next.call(ctx).unwrap_or_default();
            }

            let next = next.clone();

            comma(tables(next)).call(ctx).unwrap_or_default()
        })
    });

    table(fork)
}

fn field(next: Thunk) -> Thunk {
    Thunk::new(move |ctx: Arc<Context>| {
        let fields = ctx.get_fields();

        fields.into_iter().map(|field| {
            let selector: Selector = Some(Arc::new(move |ctx: Arc<Context>, field: String| {
                let mut ctx = (*ctx).clone();

                ctx.use_field(field.as_str());

                Arc::new(ctx)
            }));

            let thunk = next.clone();

            Node::new(
                IndexDraft::Lattice(field),
                ctx.clone(),
                selector,
                thunk,
            )
        }).collect()
    })
}

fn namespace_field(next: Thunk) -> Thunk {
    let selector: Selector = Some(Arc::new(move |ctx: Arc<Context>, namespace: String| {
        let mut ctx = (*ctx).clone();

        ctx.set_current_namespace(namespace.as_str());

        Arc::new(ctx)
    }));
    
    exp(r"[a-zA-Z_][a-zA-Z0-9_]*", selector, dot(field(next)))
}

fn fields(next: Thunk) -> Thunk {
    let fork: Thunk = branch(vec![
        next.clone(),
        Thunk::deferred(move || comma(fields(next.clone()))),
    ]);

    branch(vec![
        namespace_field(fork.clone()),
        field(fork),
    ])
}

pub fn root() -> Thunk {
    let next = Thunk::terminal();
    let next = lat(";", None, next);
    let next = tables(next);
    let next = ws(next);
    let next = lat("FROM", None, next);
    let next = fields(ws(next));
    let next = ws(next);

    lat("SELECT", None, next)
}
