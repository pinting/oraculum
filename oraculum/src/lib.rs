use std::io::Write;
use std::sync::OnceLock;

use fastlines::Vocabulary;
use numpy::PyArray1;
use pyo3::prelude::*;

static ENGINE: OnceLock<Vocabulary<u32>> = OnceLock::new();

#[pyfunction]
fn init_vocabulary(data: &[u8], eos_id: u32) -> i32 {
    if ENGINE.get().is_some() {
        return 1;
    }

    let Some(vocabulary) = Vocabulary::new(data, eos_id) else {
        return 1;
    };

    println!("Loaded {} tokens", vocabulary.get_tokens().len());

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

    PyArray1::from_slice_bound(py, vocab.get_ids())
}

#[pyfunction]
fn feed(token_id: u32) -> i32 {
    let Some(vocabulary) = ENGINE.get() else {
        return 1;
    };

    let Some(token) = vocabulary.get_token_by_id(token_id) else {
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
