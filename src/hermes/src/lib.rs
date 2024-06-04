/*
 * Copyright (C) 2024. Lovania
 */

pub use self::serialize::{encode, encode_slice, Decoder};
pub use self::value::Value;
use pyo3::prelude::*;

mod serialize;
mod value;

/// A Python module implemented in Rust.
#[pymodule]
fn hermes(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_slice, m)?).unwrap();
    Ok(())
}
