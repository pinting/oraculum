use std::io::Write;
use std::sync::{Arc, Mutex};

use fastlines::Vocabulary;
use numpy::PyArray1;
use pyo3::prelude::*;

mod engine;
mod graph;
mod schema;

use engine::Engine;
use schema::parse_schema;

struct InitState {
    vocabulary: Arc<Vocabulary<u32>>,
    eos_id: u32,
}

static STATE: Mutex<Option<InitState>> = Mutex::new(None);
static ENGINE: Mutex<Option<Engine>> = Mutex::new(None);

#[pyfunction]
fn init_vocabulary(data: &[u8], eos_id: u32) -> i32 {
    let Some(vocabulary) = Vocabulary::new(data, eos_id) else {
        return 1;
    };

    println!("Loaded {} tokens", vocabulary.get_tokens().len());

    let mut state = STATE.lock().unwrap();

    *state = Some(InitState {
        vocabulary: Arc::new(vocabulary),
        eos_id,
    });

    0
}

#[pyfunction]
fn init_schema(data: &[u8]) -> i32 {
    let Ok(text) = std::str::from_utf8(data) else {
        return 1;
    };

    println!("Schema:\n{}", text);

    let Some((columns, tables)) = parse_schema(text) else {
        return 1;
    };

    println!("Columns: {:?}", columns);
    println!("Tables: {:?}", tables);

    let mut state = STATE.lock().unwrap();

    let Some(init) = state.take() else {
        return 1;
    };

    let Some(engine) = Engine::new(init.vocabulary, init.eos_id, columns, tables) else {
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
    let mut engine_lock = ENGINE.lock().unwrap();

    let Some(engine) = engine_lock.as_mut() else {
        return 1;
    };

    let token = engine.get_token(token_id);

    if let Some(token) = token {
        print!("{}", token);
        let _ = std::io::stdout().flush();
    }

    engine.feed(token_id);

    if engine.is_completed() {
        return 1;
    }

    0
}

#[pyfunction]
fn get_token(token_id: u32) -> Option<String> {
    let engine_lock = ENGINE.lock().unwrap();
    let engine = engine_lock.as_ref()?;

    engine.get_token(token_id).map(|s| s.to_string())
}

#[pyfunction]
fn get_token_id(token: &str) -> Option<u32> {
    let engine_lock = ENGINE.lock().unwrap();
    let engine = engine_lock.as_ref()?;

    engine.get_token_id(token)
}

#[pymodule]
fn seer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(init_vocabulary, m)?)?;
    m.add_function(wrap_pyfunction!(init_schema, m)?)?;
    m.add_function(wrap_pyfunction!(routes, m)?)?;
    m.add_function(wrap_pyfunction!(feed, m)?)?;
    m.add_function(wrap_pyfunction!(get_token, m)?)?;
    m.add_function(wrap_pyfunction!(get_token_id, m)?)?;

    Ok(())
}
