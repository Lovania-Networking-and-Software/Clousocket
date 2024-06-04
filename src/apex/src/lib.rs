use pyo3::prelude::*;
use cached::{Cached, SizedCache};

#[pyclass]
struct ACache {
    cache: SizedCache<String, String>
}

#[pymethods]
impl ACache {
    #[new]
    fn new(size: usize) -> ACache {
        ACache{cache: SizedCache::with_size(size)}
    }

    fn add(&mut self, key: String, value: String) -> Option<String>{
        self.cache.cache_set(key, value)
    }

    fn get(&mut self, key: String) -> Option<&String>{
        self.cache.cache_get(&key)
    }

    fn delete(&mut self, key: String) -> Option<String>{
        self.cache.cache_remove(&key)
    }
}

/// A Python module implemented in Rust.
#[pymodule]
fn apex(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<ACache>()?;
    Ok(())
}
