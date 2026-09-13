mod context;
mod many_resolver;
mod one_resolver;
use std::collections::HashMap;

use context::Context;

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

    println!("Context: {}", ctx);
    println!("Fields: {}", ctx.get_fields().join(", "));
    println!("Selecting `` `tl_key`");

    ctx.set_current_namespace("");
    ctx.use_field("tl_key");

    println!("Context: {}", ctx);
    println!("Fields: {}", ctx.get_fields().join(", "));
    println!("Selecting `foo` `tl_key`");

    ctx.set_current_namespace("foo");
    ctx.use_field("tl_key");

    println!("Context: {}", ctx);
    println!("Table left AS foo");

    ctx.use_table("foo", "left");

    println!("Context: {}", ctx);
    println!("Table top");

    ctx.use_table("", "top");

    let ctx = ctx.clone();

    println!("Context: {}", ctx);
    println!("Satisifed: {}", ctx.is_satisfied());
}