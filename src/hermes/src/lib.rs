/*
 * Copyright (C) 2024. Lovania
 */

use pyo3::prelude::*;

pub use self::serialize::{encode, encode_slice, Decoder};
pub use self::value::Value;

mod serialize;
mod value;

/// A Python module implemented in Rust.
#[pymodule]
fn hermes(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_slice, m)?).unwrap();
    Ok(())
}
