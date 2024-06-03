pub use self::serialize::{encode, encode_slice, Decoder};
pub use self::value::Value;
use pyo3::prelude::*;
use std::any::Any;
use std::io::Read;

mod serialize;
mod value;

/// A Python module implemented in Rust.
#[pymodule]
fn hermes(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_slice, m)?).unwrap();
    m.add_class::<Decoder>()?;
    Ok(())
}
