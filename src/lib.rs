use std::collections::HashMap;
use std::io::Write;
use std::sync::OnceLock;

use base64::{Engine, engine::general_purpose::STANDARD};
use numpy::PyArray1;
use pyo3::prelude::*;

struct Vocabulary {
    token_to_id: HashMap<&'static str, u32>,
    id_to_token: HashMap<u32, &'static str>,
    idx_to_id: HashMap<usize, u32>,
    tokens: Vec<&'static str>,
    token_ids: Vec<u32>,
}

impl Vocabulary {
    fn new() -> Self {
        Self {
            token_to_id: HashMap::new(),
            id_to_token: HashMap::new(),
            idx_to_id: HashMap::new(),
            tokens: Vec::new(),
            token_ids: Vec::new(),
        }
    }

    fn load(&mut self, data: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
        let text = std::str::from_utf8(data)?;

        for line in text.lines() {
            let parts: Vec<&str> = line.split_whitespace().collect();

            if parts.len() != 2 {
                continue;
            }

            let (token, id) = (parts[0], parts[1]);

            let Ok(token) = STANDARD.decode(token) else { continue };
            let Ok(token) = String::from_utf8(token) else { continue };
            let Ok(id) = id.parse::<u32>() else { continue };

            let token: &'static str = Box::leak(token.into_boxed_str());
            let idx = self.tokens.len();

            self.token_to_id.insert(token, id);
            self.id_to_token.insert(id, token);
            self.idx_to_id.insert(idx, id);
            self.tokens.push(token);
            self.token_ids.push(id);
        }

        Ok(())
    }
}

static ENGINE: OnceLock<Vocabulary> = OnceLock::new();

#[pyfunction]
fn init_vocabulary(data: &[u8]) -> i32 {
    if ENGINE.get().is_some() {
        return 1;
    }

    let mut vocabulary = Vocabulary::new();

    if vocabulary.load(data).is_err() {
        return 1;
    }

    println!("Loaded {} tokens", vocabulary.tokens.len());

    if ENGINE.set(vocabulary).is_err() {
        return 1;
    }

    0
}

#[pyfunction]
fn init_schema(data: &[u8]) -> i32 {
    let Ok(text) = std::str::from_utf8(data) else {
        return 1;
    };

    println!("Schema:\n{}", text);

    0
}

#[pyfunction]
fn routes<'py>(py: Python<'py>) -> Bound<'py, PyArray1<u32>> {
    let Some(vocab) = ENGINE.get() else {
        return PyArray1::from_slice_bound(py, &[]);
    };

    PyArray1::from_slice_bound(py, &vocab.token_ids)
}

#[pyfunction]
fn feed(token_id: u32) -> i32 {
    let Some(vocabulary) = ENGINE.get() else {
        return 1;
    };

    let Some(token) = vocabulary.id_to_token.get(&token_id) else {
        return 1;
    };

    print!("{}", token);

    let _ = std::io::stdout().flush();

    0
}

#[pymodule]
fn oraculum(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(init_vocabulary, m)?)?;
    m.add_function(wrap_pyfunction!(init_schema, m)?)?;
    m.add_function(wrap_pyfunction!(routes, m)?)?;
    m.add_function(wrap_pyfunction!(feed, m)?)?;

    Ok(())
}
