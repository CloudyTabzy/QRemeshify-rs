//! QRemeshify Rust Extension
//!
//! High-performance mesh processing module providing:
//! - Fast OBJ file I/O (10-50x faster than Python)
//! - Parallel sharp edge detection using Rayon
//! - Mesh validation algorithms
//!
//! # Architecture
//!
//! This crate is designed to work alongside the Python addon (QRemeshify) and
//! the C++ native libraries (lib_quadwild, lib_quadpatches).
//!
//! Data flow: Python BMesh → Rust (fast I/O) → C++ QuadWild → Rust → Python BMesh

pub mod obj_io;
pub mod sharp_detection;
pub mod validation;

use pyo3::prelude::*;

/// QRemeshify Rust Extension Module
///
/// This module provides high-performance mesh processing functions:
/// - `export_mesh_rs`: Fast OBJ mesh export
/// - `import_mesh_rs`: Fast OBJ mesh import  
/// - `detect_sharp_edges_rs`: Parallel sharp edge detection
/// - `validate_mesh_rs`: Mesh validation
#[pymodule]
fn qremeshify_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Add submodule functions to the main module
    m.add_function(wrap_pyfunction!(obj_io::export_mesh_rs, m)?)?;
    m.add_function(wrap_pyfunction!(obj_io::export_mesh_rs_full, m)?)?;
    m.add_function(wrap_pyfunction!(obj_io::import_mesh_rs, m)?)?;
    m.add_function(wrap_pyfunction!(obj_io::import_mesh_rs_simple, m)?)?;
    m.add_function(wrap_pyfunction!(obj_io::export_sharp_features_rs, m)?)?;
    m.add_function(wrap_pyfunction!(sharp_detection::detect_sharp_edges_rs, m)?)?;
    m.add_function(wrap_pyfunction!(validation::validate_mesh_rs, m)?)?;
    
    // Add version info
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    
    Ok(())
}
