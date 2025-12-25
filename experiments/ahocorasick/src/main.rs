use aho_corasick::AhoCorasick;

fn find_all_routes(
    current_idx: usize,
    target_len: usize,
    matches: &[(usize, usize, &str)],
    current_path: &mut Vec<String>,
) {
    if current_idx == target_len {
        println!("{}", current_path.join(" -> "));

        return;
    }

    for (start, end, pattern) in matches {
        if *start == current_idx {
            current_path.push(pattern.to_string());
            find_all_routes(*end, target_len, matches, current_path);
            current_path.pop(); // Backtrack
        }
    }
}

fn main() {
    let patterns = vec!["a", "aa", "aaa"];
    let haystack = "aaaaaa";
    let target_len = haystack.len();

    let ac = AhoCorasick::new(&patterns).unwrap();

    let mut all_matches = Vec::new();

    for mat in ac.find_overlapping_iter(haystack) {
        let pattern_text = patterns[mat.pattern()];

        all_matches.push((mat.start(), mat.end(), pattern_text));
    }

    println!("All possible routes for '{}':", haystack);
    println!("{:-<30}", "");

    let mut current_path = Vec::new();
    
    find_all_routes(0, target_len, &all_matches, &mut current_path);
}