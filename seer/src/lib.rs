use std::io::Write;
use std::sync::{Arc, Mutex};

use fastlines::{FlatDFA, Vocabulary};
use numpy::PyArray1;
use pyo3::prelude::*;

mod context;
mod engine;
mod factory;
mod graph;
mod many_resolver;
mod one_resolver;
mod schema;

use engine::Engine;
use schema::parse_schema;

use crate::graph::root;

static VOCABULARY: Mutex<Option<Arc<Vocabulary<u32>>>> = Mutex::new(None);
static ENGINE: Mutex<Option<Engine<u32, u32, FlatDFA<u32, u32>>>> = Mutex::new(None);

#[pyfunction]
fn init_vocabulary(data: &[u8], eos_id: u32) -> i32 {
    let Some(vocabulary) = Vocabulary::new(data, eos_id) else {
        return 1;
    };

    println!("Loaded {} tokens", vocabulary.get_tokens().len());

    let mut v = VOCABULARY.lock().unwrap();

    *v = Some(Arc::new(vocabulary));

    0
}

#[pyfunction]
fn init_schema(data: &[u8]) -> i32 {
    let Ok(text) = std::str::from_utf8(data) else {
        return 1;
    };

    println!("Schema:\n{}", text);

    let Some(tables) = parse_schema(text) else {
        return 1;
    };

    println!("Tables: {:?}", tables);

    let mut vocabulary = VOCABULARY.lock().unwrap();

    let Some(vocabulary) = vocabulary.take() else {
        return 1;
    };

    let thunk = root();
    let engine = Engine::new(vocabulary, tables, thunk);
    
    let Some(engine) = engine else {
        return 1;
    };

    let mut engine_lock = ENGINE.lock().unwrap();

    *engine_lock = Some(engine);

    0
}

#[pyfunction]
fn routes<'py>(py: Python<'py>) -> Bound<'py, PyArray1<u32>> {
    let engine_lock = ENGINE.lock().unwrap();

    let Some(engine) = engine_lock.as_ref() else {
        return PyArray1::from_slice_bound(py, &[]);
    };

    let result = engine.routes();

    PyArray1::from_slice_bound(py, &result)
}

#[pyfunction]
fn feed(token_id: u32) -> i32 {
    let mut engine = ENGINE.lock().unwrap();

    let Some(engine) = engine.as_mut() else {
        return 1;
    };

    engine.feed(token_id);

    0
}

#[pyfunction]
fn get_token_by_id(token_id: u32) -> Option<String> {
    let mut vocabulary = VOCABULARY.lock().unwrap();

    let Some(vocabulary) = vocabulary.as_mut() else {
        return None;
    };

    Some(vocabulary.get_token_by_id(token_id)?.to_string())
}

#[pyfunction]
fn get_id_by_token(token: &str) -> Option<u32> {
    let mut vocabulary = VOCABULARY.lock().unwrap();

    let Some(vocabulary) = vocabulary.as_mut() else {
        return None;
    };

    vocabulary.get_id_by_token(token)
}

#[pymodule]
fn seer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(init_vocabulary, m)?)?;
    m.add_function(wrap_pyfunction!(init_schema, m)?)?;
    m.add_function(wrap_pyfunction!(routes, m)?)?;
    m.add_function(wrap_pyfunction!(feed, m)?)?;
    m.add_function(wrap_pyfunction!(get_token_by_id, m)?)?;
    m.add_function(wrap_pyfunction!(get_id_by_token, m)?)?;

    Ok(())
}
