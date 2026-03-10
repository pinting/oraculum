use std::sync::Arc;
use std::time::Instant;

use rand::SeedableRng;
use rand::RngExt;
use rand::rngs::SmallRng;

use fastlines::{FastHashDFA, DoubleHashDFA, FlatDFA, Expression, Number, Vocabulary, DFA, BaseIndex};

const NUM_ROUNDS: usize = 100;
const NUM_SCAN_ITERS: usize = 50;
const NUM_LOOKUP_ITERS: usize = 200;

const PATTERNS: &[&str] = &[
    "hi", "ok", "no", "yes", "cat", "dog", "red", "sun", "moon", "tree",
    "hello", "world", "apple", "house", "river",
    "a|b|c", "x|y|z", "go|no", "up|down", "left|right",
    "[a-z]", "[0-9]", "[A-Z]+", "[a-z]{2}", "[0-9]{3}",
    "foo|bar|baz", "one|two|three", "red|green|blue", "cat|dog|bird|fish", "mon|tue|wed|thu|fri",
    "ab+c", "a*b+", "x+y+z+", "go+d", "ba+na+na",
    "colou?r", "behaviou?r", "favou?rite", "grey|gray", "analyse|analyze",
    "[aeiou]{2}", "[bcdfg]{3}", "[a-f0-9]{4}", "[a-z][0-9]", "[A-Z][a-z]+",
    "the|a|an", "is|am|are|was|were", "I|you|he|she|it|we|they", "in|on|at|by|to|for", "and|but|or|nor|yet|so",
    "(ab)+", "(xy)+z", "a(bc)*d", "(ha){2,4}", "(la){3}",
    "[a-z]{1,5}", "[0-9]{2,4}", "[a-z]{3,6}", "[A-Za-z]{2,8}", "[a-z0-9]{4,8}",
    "https?://[a-z]+", "www\\.[a-z]+", "[a-z]+@[a-z]+", "[0-9]+\\.[0-9]+", "[a-z]+\\.[a-z]{2,4}",
    "(foo|bar)(baz|qux)", "(ab|cd)(ef|gh)(ij|kl)", "(red|blue)(car|bus)", "(big|small)(cat|dog|rat)", "(hot|cold)(day|night)",
    "a{1,3}b{1,3}c{1,3}", "x{2,5}y{2,5}", "[abc]{2}[def]{2}[ghi]{2}", "[a-c]{3}[d-f]{3}", "[0-3]{2}[4-7]{2}[8-9]{2}",
    "monday|tuesday|wednesday|thursday|friday|saturday|sunday",
    "january|february|march|april|may|june|july|august|september|october|november|december",
    "alpha|beta|gamma|delta|epsilon|zeta|eta|theta",
    "mercury|venus|earth|mars|jupiter|saturn|uranus|neptune",
    "spring|summer|autumn|winter|monsoon|drought",
    "(north|south)(east|west)?",
    "(pre|post|un|re)[a-z]{3,6}",
    "(auto|semi|anti)[a-z]{4,8}",
    "(over|under)(flow|line|pass|take)",
    "(black|white|grey)(bird|fish|wolf|bear)",
    "[a-z]{2,4}(ing|tion|ment|ness|able)",
    "[a-z]{3,5}(ed|er|est|ly|ful)",
    "[bcdfghjklmnpqrstvwxyz][aeiou][bcdfghjklmnpqrstvwxyz]{1,3}",
    "[aeiou][bcdfghjklmnpqrstvwxyz]{2}[aeiou]",
    "[a-z]{2}[0-9]{2}[a-z]{2}[0-9]{2}",
    "(do|re|mi|fa|sol|la|si){2,4}",
    "(ab|cd|ef|gh|ij|kl|mn|op){2,3}",
    "(foo|bar|baz|qux|quux|corge|grault|garply){1,3}",
    "(alpha|beta|gamma)(one|two|three)(red|blue|green)",
    "(north|south|east|west)(ern)?(most)?",
    "(un|re|dis|mis|pre|post)(connect|appear|cover|place|view|build)",
    "(over|under|out|up)(run|grow|come|turn|look|stand|play|line)",
    "[A-Z][a-z]{2,6}(son|ton|berg|stein|ville|burg|ford|wood|land|field)",
    "[a-z]{3,8}(ation|ition|ution|ision|usion|ption|ntion|stion|ction)",
    "(inter|intra|extra|ultra|super|hyper)(nation|state|galactic|sonic|natural|active)",
];

struct Record {
    name: String,
    build_times_ms: Vec<f64>,
    scan_times_us: Vec<f64>,
    lookup_times_us: Vec<f64>,
    memory_usages: Vec<usize>,
}

impl Record {
    fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            build_times_ms: Vec::new(),
            scan_times_us: Vec::new(),
            lookup_times_us: Vec::new(),
            memory_usages: Vec::new(),
        }
    }
}

fn benchmark<D>(
    expression: &str,
    vocabulary: &Arc<Vocabulary<u32>>,
    trie: &toktrie::TokTrie,
    record: &mut Record,
) where
    D: DFA<u32, u32>,
{
    let t0 = Instant::now();
    let expr = Expression::<u32, u32, D>::new(
        expression, vocabulary.clone(), trie).expect("Failed to create Expression");
    let t1 = t0.elapsed().as_secs_f64() * 1000.0;

    record.build_times_ms.push(t1);
    record.memory_usages.push(expr.memory_usage());

    let start_node: u32 = 0;

    let t0 = Instant::now();
    let mut transitions: Vec<u32> = Vec::new();

    for _ in 0..NUM_SCAN_ITERS {
        transitions = expr.transitions(start_node)
            .map(|c| c.into_owned())
            .unwrap_or_default();
    }

    let t1 = t0.elapsed().as_secs_f64() / NUM_SCAN_ITERS as f64 * 1_000_000.0;

    record.scan_times_us.push(t1);

    if transitions.is_empty() {
        record.lookup_times_us.push(0.0);

        return;
    }

    let mut rng = SmallRng::seed_from_u64(42);

    let sample_count = transitions.len().min(10);
    let sample_ids: Vec<u32> = (0..sample_count)
        .map(|_| transitions[rng.random_range(0..transitions.len())])
        .collect();

    let t0 = Instant::now();

    for _ in 0..NUM_LOOKUP_ITERS {
        for &tid in &sample_ids {
            let _ = expr.next(start_node, tid);
        }
    }

    let n = NUM_LOOKUP_ITERS * sample_ids.len();
    let t1 = t0.elapsed().as_secs_f64() / n as f64 * 1_000_000.0;

    record.lookup_times_us.push(t1);
}

fn avg(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }

    values.iter().sum::<f64>() / values.len() as f64
}

fn print_board(
    title: &str,
    results: &mut [&Record],
    f: fn(&Record) -> f64,
    unit: &str,
) {
    let nw = 20;
    let vw = 12;

    results.sort_by(|a, b| f(a).partial_cmp(&f(b)).unwrap());

    let header = format!("{:<nw$}{:>vw$}", "DFA Type", format!("Avg ({})", unit));
    let sep = "-".repeat(header.len());

    println!("{}:", title);
    println!("{}", sep);
    println!("{}", header);
    println!("{}", sep);

    for (i, r) in results.iter().enumerate() {
        println!("{:<nw$}{:>vw$.3}", format!("#{} {}", i + 1, r.name), f(r));
    }

    println!("{}", sep);
    println!();
}

fn print_boards(results: &[Record]) {
    let mut refs: Vec<&Record> = results.iter().collect();

    print_board("LOOKUP LEADERBOARD", &mut refs, |r| avg(&r.lookup_times_us), "us");

    let mut refs: Vec<&Record> = results.iter().collect();

    print_board("SCAN LEADERBOARD", &mut refs, |r| avg(&r.scan_times_us), "us");

    let mut refs: Vec<&Record> = results.iter().collect();

    print_board("BUILD LEADERBOARD", &mut refs, |r| avg(&r.build_times_ms), "ms");

    let mut refs: Vec<&Record> = results.iter().collect();

    print_board(
        "MEMORY LEADERBOARD", &mut refs,
        |r| avg(&r.memory_usages.iter().map(|&m| m as f64).collect::<Vec<_>>()) / 1024.0,
        "KB",
    );
}

fn main() {
    let vocabulary = Vocabulary::from_file_path("../vocabulary.tiktoken", 1u32)
        .map(Arc::new)
        .expect("Failed to load vocabulary.tiktoken");

    let trie = Expression::<u32, u32, FlatDFA<u32, u32>>::base(vocabulary.clone())
        .expect("Failed to build TokTrie base");

    let mut results = vec![
        Record::new("FastHashDFA"),
        Record::new("DoubleHashDFA"),
        Record::new("FlatDFA"),
    ];

    let total_cases = NUM_ROUNDS * PATTERNS.len();

    for r in 0..NUM_ROUNDS {
        for (i, pattern) in PATTERNS.iter().enumerate() {
            let idx = r * PATTERNS.len() + i + 1;
            let display: String = pattern.chars().take(50).collect();

            print!("\r[{:5}/{total_cases}] Round {}/{NUM_ROUNDS} - Pattern: {:<50}", idx, r + 1, display);

            benchmark::<FastHashDFA<u32, u32>>(pattern, &vocabulary, &trie, &mut results[0]);
            benchmark::<DoubleHashDFA<u32, u32>>(pattern, &vocabulary, &trie, &mut results[1]);
            benchmark::<FlatDFA<u32, u32>>(pattern, &vocabulary, &trie, &mut results[2]);
        }
    }

    println!();

    print_boards(&results);
}
