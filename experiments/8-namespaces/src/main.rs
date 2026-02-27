mod context;
mod many_resolver;
mod one_resolver;

use std::collections::HashMap;

use context::Context;

fn read_line() -> Option<String> {
    let mut line = String::new();
    let n = std::io::stdin().read_line(&mut line).unwrap();

    if n == 0 {
        return None;
    }

    Some(line.trim().to_string())
}

fn make_tables() -> HashMap<String, Vec<String>> {
    HashMap::from([
        ("top".into(), vec!["tl_key".into(), "tr_key".into(), "top_val".into()]),
        ("left".into(), vec!["tl_key".into(), "lb_key".into(), "left_val".into()]),
        ("right".into(), vec!["tr_key".into(), "rb_key".into(), "right_val".into()]),
        ("bottom".into(), vec!["lb_key".into(), "rb_key".into(), "bottom_val".into()]),
    ])
}

fn main() {
    let mut ctx = Context::new(make_tables());

    loop {
        println!("Namespace (empty = global):");

        let namespace = match read_line() {
            Some(ns) => ns,
            None => break,
        };

        let fields = ctx.get_fields(&namespace);

        if fields.is_empty() {
            println!("No fields available");

            continue;
        }

        println!("Fields: {}", fields.join(", "));
        println!("Select field (empty = done):");

        let field = match read_line() {
            Some(f) if !f.is_empty() => f,
            _ => break,
        };

        match ctx.use_field(&namespace, field) {
            None => println!("Unknown field"),
            Some(false) => println!("Unsatisfiable"),
            Some(true) => {}
        }
    }

    loop {
        let required = ctx.get_required_tables();

        if required.is_empty() {
            break;
        }

        for (namespace, tables) in &required {
            let label = if namespace.is_empty() { "global" } else { namespace.as_str() };

            println!("{}: {}", label, tables.join(", "));
        }

        println!("Namespace (empty = global):");

        let namespace = match read_line() {
            Some(ns) => ns,
            None => break,
        };

        println!("Select table:");

        let table = match read_line() {
            Some(t) if !t.is_empty() => t,
            _ => break,
        };

        match ctx.use_table(&namespace, &table) {
            None => println!("Invalid table"),
            Some(_) => {}
        }
    }

    if ctx.is_satisfied() {
        println!("Satisfied!");
    } else {
        println!("Not satisfied.");
    }
}
