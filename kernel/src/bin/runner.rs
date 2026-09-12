//! The dynamic API from Rust: a factory, a head pool, and a group index.
//!
//!     cargo run --bin runner
//!
//! `example` owns its indexes and walks them by hand. This one owns nothing:
//! the factory keeps every index and answers with an id, the runner keeps the
//! heads walking them, and the graph is decided by the `Resolver` below, one
//! notification at a time.
//!
//! The language is `<greeting> <alias>`, where the alias is any identifier that
//! is not a reserved word - which is a group: the identifier pattern minus one
//! lattice per word to keep out.

use std::io::{self, Write};
use std::sync::{Arc, Mutex};

use kernel::{
    Draft, Expansion, Factory, FlatDFA, Report, Request, Resolver, Runner, Vocabulary,
};

type N = u32;
type T = u32;
type D = FlatDFA<N, T>;

const VOCABULARY_PATH: &str = "../vocabulary.tiktoken";
const EOS_ID: T = 1;

const IDENTIFIER: &str = "[a-zA-Z_][a-zA-Z0-9_]*";
const RESERVED: [&str; 4] = ["hello", "world", "monday", "friday"];

/// What a head carries: which part of the language it is matching.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Part {
    Greeting,
    Space,
    Alias,
}

/// The graph. Everything the kernel knows about the language is what this
/// answers when it is told a head has finished.
struct Grammar {
    alias: u64,
    trace: Mutex<Vec<String>>,
}

impl Resolver<Part> for Grammar {
    fn resolve(&self, report: &Report<'_, Part>) -> Expansion<Part> {
        self.trace
            .lock()
            .unwrap()
            .push(format!("head {} finished {:?} with {:?}", report.id, report.payload, report.matched));

        match report.payload {
            Part::Greeting => Expansion::Children(vec![Request::new(
                Draft::Lattice(" ".to_string()),
                Part::Space,
            )]),
            Part::Space => Expansion::Children(vec![Request::existing(self.alias, Part::Alias)]),
            // Nothing follows an alias, so the statement is complete.
            Part::Alias => Expansion::Terminal,
        }
    }
}

fn build_alias(factory: &Factory<N, T, D>) -> Option<u64> {
    let include: u64 = factory.create_expression(IDENTIFIER)?;

    let mut excludes: Vec<u64> = Vec::with_capacity(RESERVED.len());

    for word in RESERVED {
        excludes.push(factory.create_lattice(word)?);
    }

    factory.create_group(include, excludes)
}

fn main() {
    let Some(vocabulary) = Vocabulary::<T>::from_file_path(VOCABULARY_PATH, EOS_ID) else {
        eprintln!("Error: {VOCABULARY_PATH} not found or failed to load.");

        return;
    };

    println!("Vocabulary loaded ({} tokens)", vocabulary.get_tokens().len());

    let vocabulary: Arc<Vocabulary<T>> = Arc::new(vocabulary);

    let Some(factory) = Factory::<N, T, D>::new(vocabulary.clone(), true) else {
        eprintln!("Error: failed to build the index bases.");

        return;
    };

    let factory: Arc<Factory<N, T, D>> = Arc::new(factory);

    let Some(alias) = build_alias(&factory) else {
        eprintln!("Error: failed to build the alias group.");

        return;
    };

    println!("Alias group: {IDENTIFIER} minus {RESERVED:?} -> index {alias}");

    let grammar = Grammar {
        alias,
        trace: Mutex::new(Vec::new()),
    };

    let Some(mut runner) = Runner::<N, T, D, Part>::new(factory.clone(), 4) else {
        eprintln!("Error: failed to build the worker pool.");

        return;
    };

    for greeting in ["hello", "hi"] {
        if let Some(index_id) = factory.create_lattice(greeting) {
            runner.spawn(index_id, Part::Greeting);
        }
    }

    println!("\nType a token at a time: a greeting, a space, then any identifier");
    println!("except {RESERVED:?}.\n");

    while !runner.is_completed() {
        let routes: Vec<T> = runner.routes();

        if routes.is_empty() {
            println!("Nothing can follow; the statement is stuck.");

            break;
        }

        let shown: Vec<String> = routes
            .iter()
            .filter_map(|&id| vocabulary.get_token_by_id(id))
            .take(40)
            .map(|token| format!("`{token}`"))
            .collect();

        let heads: Vec<String> = runner
            .heads()
            .iter()
            .filter_map(|head| factory.label(head.index_id()))
            .collect();

        println!("Heads: {heads:?}");
        println!("Routes: {}", shown.join(" "));

        print!("> ");

        let _ = io::stdout().flush();

        let mut line = String::new();

        if io::stdin().read_line(&mut line).unwrap_or(0) == 0 {
            return;
        }

        let line = line.trim_end_matches('\n');

        let Some(token_id) = vocabulary.get_id_by_token(line) else {
            println!("Unknown token!");

            continue;
        };

        if !routes.contains(&token_id) {
            println!("Not a legal token here!");

            continue;
        }

        runner.feed(token_id, &grammar);

        println!("Matched: {:?}\n", runner.matched());
    }

    let (rounds, notified, spawned) = runner.stats();

    println!("\nDone: {:?}", runner.matched());

    for line in grammar.trace.lock().unwrap().iter() {
        println!("  {line}");
    }

    println!(
        "{rounds} resolve rounds, {notified} notifications, {spawned} heads, {} index builds",
        factory.builds()
    );
}
