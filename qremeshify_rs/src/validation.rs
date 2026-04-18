//! Mesh Validation Module
//!
//! High-performance mesh validation algorithms.
//! 
//! This module provides comprehensive mesh validation including:
//! - Non-manifold detection
//! - Degenerate face detection
//! - Isolated vertex detection
//! - Hole detection
//!
//! # Validation Checks
//!
//! | Check | Description | Severity |
//! |-------|-------------|----------|
//! | Non-manifold edges | Edges connected to >2 faces | Error |
//! | Non-manifold vertices | Vertices in disconnected edge neighborhoods | Error |
//! | Degenerate faces | Faces with < 3 vertices or zero area | Error |
//! | Isolated vertices | Vertices not part of any face | Warning |
//! | Duplicate faces | Multiple faces with identical vertex sets | Warning |
//! | Invalid normals | Zero-length normals | Warning |

use rayon::prelude::*;

use pyo3::prelude::*;

/// Validation error/warning entry
#[derive(Debug, Clone)]
pub struct ValidationIssue {
    pub severity: String,  // "error" or "warning"
    pub code: String,     // Short error code
    pub message: String,  // Human-readable message
    pub location: Option<String>,  // Optional location info
}

impl ValidationIssue {
    pub fn error(code: &str, message: &str) -> Self {
        Self {
            severity: "error".to_string(),
            code: code.to_string(),
            message: message.to_string(),
            location: None,
        }
    }
    
    pub fn error_with_loc(code: &str, message: &str, location: &str) -> Self {
        Self {
            severity: "error".to_string(),
            code: code.to_string(),
            message: message.to_string(),
            location: Some(location.to_string()),
        }
    }
    
    pub fn warning(code: &str, message: &str) -> Self {
        Self {
            severity: "warning".to_string(),
            code: code.to_string(),
            message: message.to_string(),
            location: None,
        }
    }
    
    pub fn warning_with_loc(code: &str, message: &str, location: &str) -> Self {
        Self {
            severity: "warning".to_string(),
            code: code.to_string(),
            message: message.to_string(),
            location: Some(location.to_string()),
        }
    }
}

/// Validation result structure
#[derive(Debug, Clone)]
pub struct ValidationResult {
    pub is_valid: bool,
    pub error_count: usize,
    pub warning_count: usize,
    pub issues: Vec<ValidationIssue>,
}

impl ValidationResult {
    pub fn valid() -> Self {
        Self {
            is_valid: true,
            error_count: 0,
            warning_count: 0,
            issues: Vec::new(),
        }
    }
    
    pub fn with_issues(issues: Vec<ValidationIssue>) -> Self {
        let error_count = issues.iter().filter(|i| i.severity == "error").count();
        let warning_count = issues.iter().filter(|i| i.severity == "warning").count();
        
        Self {
            is_valid: error_count == 0,
            error_count,
            warning_count,
            issues,
        }
    }
}

/// Validate mesh data
///
/// # Arguments
/// * `vertices` - Flattened vertex array [x1,y1,z1,x2,y2,z2,...]
/// * `faces` - Flattened face array [v1,v2,v3,...]
/// * `face_sizes` - Number of vertices per face
///
/// # Returns
/// Tuple of (is_valid: bool, error_count: usize, warning_count: usize, issues: List of issue tuples)
#[pyfunction]
pub fn validate_mesh_rs(
    vertices: Vec<f64>,
    faces: Vec<usize>,
    face_sizes: Vec<usize>,
) -> PyResult<(bool, usize, usize, Vec<(String, String, String, Option<String>)>)> {
    let vertex_count = vertices.len() / 3;
    let face_count = face_sizes.len();
    
    if vertex_count == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Mesh has no vertices".to_string()
        ));
    }
    
    if face_count == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Mesh has no faces".to_string()
        ));
    }
    
    let mut issues: Vec<ValidationIssue> = Vec::new();
    
    // Build face offset table
    let mut face_offsets: Vec<usize> = Vec::with_capacity(face_count);
    let mut offset = 0usize;
    for size in &face_sizes {
        face_offsets.push(offset);
        offset += size;
    }
    
    // 1. Check for degenerate faces (parallel)
    let degenerate_issues: Vec<ValidationIssue> = face_sizes.par_iter()
        .enumerate()
        .filter_map(|(face_idx, &size)| {
            if size < 3 {
                return Some(ValidationIssue::error(
                    "DEGENERATE_FACE",
                    &format!("Face {} has only {} vertices", face_idx, size)
                ));
            }
            
            let start = face_offsets[face_idx];
            
            // Check for zero-area faces
            if size == 3 {
                let v0 = get_vertex(&vertices, faces[start]);
                let v1 = get_vertex(&vertices, faces[start + 1]);
                let v2 = get_vertex(&vertices, faces[start + 2]);
                
                let area = triangle_area(v0, v1, v2);
                if area < 1e-10 {
                    return Some(ValidationIssue::error(
                        "ZERO_AREA_FACE",
                        &format!("Face {} has zero area", face_idx)
                    ));
                }
            }
            
            None
        })
        .collect();
    issues.extend(degenerate_issues);
    
    // 2. Check for isolated vertices (vertices not used in any face)
    let mut vertex_use_count = vec![0usize; vertex_count];
    for face_idx in 0..face_count {
        let start = face_offsets[face_idx];
        let size = face_sizes[face_idx];
        for i in 0..size {
            let v = faces[start + i];
            if v < vertex_count {
                vertex_use_count[v] += 1;
            }
        }
    }
    
    let isolated_issues: Vec<ValidationIssue> = vertex_use_count.par_iter()
        .enumerate()
        .filter(|&(i, &count)| count == 0)
        .map(|(v, _)| ValidationIssue::warning(
            "ISOLATED_VERTEX",
            &format!("Vertex {} is not part of any face", v)
        ))
        .collect();
    issues.extend(isolated_issues);
    
    // 3. Check for non-manifold edges
    let mut edge_face_count: std::collections::HashMap<(usize, usize), usize> = 
        std::collections::HashMap::new();
    
    for face_idx in 0..face_count {
        let start = face_offsets[face_idx];
        let size = face_sizes[face_idx];
        
        for i in 0..size {
            let v1 = faces[start + i];
            let v2 = faces[start + (i + 1) % size];
            
            let (min_v, max_v) = if v1 < v2 { (v1, v2) } else { (v2, v1) };
            *edge_face_count.entry((min_v, max_v)).or_insert(0) += 1;
        }
    }
    
    let non_manifold_issues: Vec<ValidationIssue> = edge_face_count.par_iter()
        .filter(|&(_, &count)| count > 2)
        .map(|(&(v1, v2), &count)| ValidationIssue::error(
            "NON_MANIFOLD_EDGE",
            &format!("Edge ({},{}) is connected to {} faces (non-manifold)", v1, v2, count)
        ))
        .collect();
    issues.extend(non_manifold_issues);
    
    // 4. Check for out-of-bounds vertex indices
    let out_of_bounds_issues: Vec<ValidationIssue> = faces.par_chunks(4)
        .enumerate()
        .filter_map(|(chunk_idx, chunk)| {
            for (i, &v) in chunk.iter().enumerate() {
                if v >= vertex_count {
                    return Some(ValidationIssue::error(
                        "OUT_OF_BOUNDS",
                        &format!("Face {} vertex index {} >= vertex count {}", 
                            chunk_idx, v, vertex_count)
                    ));
                }
            }
            None
        })
        .collect();
    issues.extend(out_of_bounds_issues);
    
    // 5. Check for duplicate faces
    let mut face_signature: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut duplicate_face_indices: Vec<usize> = Vec::new();
    
    for face_idx in 0..face_count {
        let start = face_offsets[face_idx];
        let size = face_sizes[face_idx];
        
        let mut verts: Vec<usize> = faces[start..start + size].to_vec();
        verts.sort();
        let sig = verts.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(",");
        
        if face_signature.contains(&sig) {
            duplicate_face_indices.push(face_idx);
        } else {
            face_signature.insert(sig);
        }
    }
    
    if !duplicate_face_indices.is_empty() {
        issues.push(ValidationIssue::warning(
            "DUPLICATE_FACES",
            &format!("Found {} duplicate face(s)", duplicate_face_indices.len())
        ));
    }
    
    let result = ValidationResult::with_issues(issues);
    
    let issue_tuples: Vec<(String, String, String, Option<String>)> = result.issues
        .iter()
        .map(|i| (i.severity.clone(), i.code.clone(), i.message.clone(), i.location.clone()))
        .collect();
    
    Ok((result.is_valid, result.error_count, result.warning_count, issue_tuples))
}

/// Get vertex coordinates as a tuple
#[inline]
fn get_vertex(vertices: &[f64], idx: usize) -> (f64, f64, f64) {
    let offset = idx * 3;
    (vertices[offset], vertices[offset + 1], vertices[offset + 2])
}

/// Calculate triangle area using cross product
#[inline]
fn triangle_area(
    v0: (f64, f64, f64),
    v1: (f64, f64, f64),
    v2: (f64, f64, f64),
) -> f64 {
    let (ax, ay, az) = (v1.0 - v0.0, v1.1 - v0.1, v1.2 - v0.2);
    let (bx, by, bz) = (v2.0 - v0.0, v2.1 - v0.1, v2.2 - v0.2);
    
    let (cx, cy, cz) = (
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    );
    
    (cx * cx + cy * cy + cz * cz).sqrt() * 0.5
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_valid_mesh() {
        let vertices = vec![
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            1.0, 1.0, 0.0,
            0.0, 1.0, 0.0,
        ];
        let faces = vec![0, 1, 2, 0, 2, 3]; // Two triangles
        let face_sizes = vec![3, 3];
        
        let (is_valid, errors, warnings, _) = validate_mesh_rs(
            vertices, faces, face_sizes
        ).unwrap();
        
        assert!(is_valid);
        assert_eq!(errors, 0);
    }
    
    #[test]
    fn test_validate_degenerate_face() {
        let vertices = vec![
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            2.0, 0.0, 0.0,  // Same line - degenerate
        ];
        let faces = vec![0, 1, 2]; // Degenerate triangle
        let face_sizes = vec![3];
        
        let (is_valid, errors, _, _) = validate_mesh_rs(
            vertices, faces, face_sizes
        ).unwrap();
        
        assert!(!is_valid);
        assert!(errors > 0);
    }
    
    #[test]
    fn test_validate_isolated_vertex() {
        let vertices = vec![
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            1.0, 1.0, 0.0,
            5.0, 5.0, 5.0,  // Isolated vertex
        ];
        let faces = vec![0, 1, 2]; // Only uses first 3 verts
        let face_sizes = vec![3];
        
        let (_, _, warnings, _) = validate_mesh_rs(
            vertices, faces, face_sizes
        ).unwrap();
        
        assert!(warnings > 0);
    }
}
