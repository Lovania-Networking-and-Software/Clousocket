use std::any::Any;
use pyo3::prelude::*;
use pyo3::types::PyTuple;
pub use self::value::Value;
pub use self::serialize::{encode, encode_slice, Decoder};

mod value;
mod serialize;

/// Formats the sum of two numbers as string.
#[pyfunction]
#[pyo3(signature = (*kwds))]
fn num_kwds(kwds: Bound<'_, PyTuple>) -> PyResult<Bound<'_, PyTuple>>{
    Ok(kwds)
}

/// A Python module implemented in Rust.
#[pymodule]
fn hermes(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_slice, m)?).unwrap();
    Ok(())
}
