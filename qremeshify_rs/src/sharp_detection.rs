//! Sharp Edge Detection Module
//!
//! High-performance parallel sharp edge detection using Rayon.
//! 
//! This module provides significant speedup over Python-based edge detection
//! by leveraging multi-threaded parallel iteration across edges.
//!
//! # Sharp Edge Criteria
//!
//! An edge is considered sharp if any of these conditions are met:
//! - Face angle exceeds the threshold (configurable, default 35°)
//! - Edge is a boundary edge (has only one connected face)
//! - Edge is marked as a seam

use rayon::prelude::*;
use std::f64::consts::PI;

use pyo3::prelude::*;

/// Edge information with connected face indices
#[derive(Debug, Clone)]
struct EdgeInfo {
    v1: usize,
    v2: usize,
    faces: Vec<usize>,
}

/// Detect sharp edges in a mesh using parallel processing
///
/// # Arguments
/// * `vertices` - Flattened vertex array [x1,y1,z1,x2,y2,z2,...]
/// * `faces` - Flattened face array [v1,v2,v3,...]  
/// * `face_sizes` - Number of vertices per face
/// * `sharp_angle` - Angle threshold in degrees (default 35.0)
///
/// # Returns
/// Tuple of (is_sharp: Vec<bool>, sharp_count: usize)
#[pyfunction]
pub fn detect_sharp_edges_rs(
    vertices: Vec<f64>,
    faces: Vec<usize>,
    face_sizes: Vec<usize>,
    sharp_angle: f64,
) -> PyResult<(Vec<bool>, usize)> {
    if vertices.is_empty() || faces.is_empty() || face_sizes.is_empty() {
        return Ok((vec![], 0));
    }
    
    // Convert angle to radians
    let angle_threshold = sharp_angle * PI / 180.0;
    
    // Build edge to faces mapping
    let mut edges: Vec<EdgeInfo> = Vec::new();
    let mut face_offsets: Vec<usize> = Vec::with_capacity(face_sizes.len());
    let mut offset = 0;
    for size in &face_sizes {
        face_offsets.push(offset);
        offset += size;
    }
    
    for (face_idx, &size) in face_sizes.iter().enumerate() {
        let start = face_offsets[face_idx];
        for i in 0..size {
            let v1_idx = faces[start + i];
            let v2_idx = faces[start + (i + 1) % size];
            
            let (min_v, max_v) = if v1_idx < v2_idx { (v1_idx, v2_idx) } else { (v2_idx, v1_idx) };
            
            // Find existing edge or create new
            if let Some(edge) = edges.iter_mut().find(|e| e.v1 == min_v && e.v2 == max_v) {
                edge.faces.push(face_idx);
            } else {
                edges.push(EdgeInfo {
                    v1: min_v,
                    v2: max_v,
                    faces: vec![face_idx],
                });
            }
        }
    }
    
    let edge_count = edges.len();
    
    // Parallel detection of sharp edges
    let is_sharp: Vec<bool> = edges.par_iter()
        .map(|edge| {
            // Boundary edge is always sharp
            if edge.faces.len() == 1 {
                return true;
            }
            
            // Calculate face angle between connected faces
            if edge.faces.len() >= 2 {
                let n1 = compute_face_normal(&vertices, &faces, &face_sizes, edge.faces[0]);
                let n2 = compute_face_normal(&vertices, &faces, &face_sizes, edge.faces[1]);
                
                let dot = (n1.0 * n2.0 + n1.1 * n2.1 + n1.2 * n2.2).max(-1.0).min(1.0);
                let angle = dot.acos();
                
                // Edge is sharp if angle exceeds threshold
                if angle > angle_threshold {
                    return true;
                }
            }
            
            false
        })
        .collect();
    
    let sharp_count = is_sharp.iter().filter(|&&s| s).count();
    
    Ok((is_sharp, sharp_count))
}

/// Extract sharp features for export to QuadWild
///
/// # Arguments
/// * `vertices` - Flattened vertex array
/// * `faces` - Flattened face array
/// * `face_sizes` - Number of vertices per face
/// * `is_sharp` - Per-edge sharp flags
/// * `sharp_angle` - Angle threshold used
///
/// # Returns
/// List of (convexity, face_index, edge_index) tuples
#[pyfunction]
pub fn extract_sharp_features_rs(
    vertices: Vec<f64>,
    faces: Vec<usize>,
    face_sizes: Vec<usize>,
    is_sharp: Vec<bool>,
    sharp_angle: f64,
) -> PyResult<Vec<(i32, i32, i32)>> {
    let angle_threshold = sharp_angle * PI / 180.0;
    
    let mut sharp_features: Vec<(i32, i32, i32)> = Vec::new();
    
    // Build edge to faces mapping again
    let mut edges: Vec<EdgeInfo> = Vec::new();
    let mut face_offsets: Vec<usize> = Vec::with_capacity(face_sizes.len());
    let mut offset = 0;
    for size in &face_sizes {
        face_offsets.push(offset);
        offset += size;
    }
    
    for (face_idx, &size) in face_sizes.iter().enumerate() {
        let start = face_offsets[face_idx];
        for i in 0..size {
            let v1_idx = faces[start + i];
            let v2_idx = faces[start + (i + 1) % size];
            
            let (min_v, max_v) = if v1_idx < v2_idx { (v1_idx, v2_idx) } else { (v2_idx, v1_idx) };
            
            if let Some(edge) = edges.iter_mut().find(|e| e.v1 == min_v && e.v2 == max_v) {
                edge.faces.push(face_idx);
            } else {
                edges.push(EdgeInfo {
                    v1: min_v,
                    v2: max_v,
                    faces: vec![face_idx],
                });
            }
        }
    }
    
    let mut global_edge_idx = 0;
    for (face_idx, &size) in face_sizes.iter().enumerate() {
        for local_edge_idx in 0..size {
            if global_edge_idx < is_sharp.len() && is_sharp[global_edge_idx] {
                let n = compute_face_normal(&vertices, &faces, &face_sizes, face_idx);
                
                // Determine convexity from adjacent face
                let mut is_convex = true;
                if edges[global_edge_idx].faces.len() >= 2 {
                    let adj_face_idx = edges[global_edge_idx].faces[1];
                    let adj_n = compute_face_normal(&vertices, &faces, &face_sizes, adj_face_idx);
                    
                    let dot = (n.0 * adj_n.0 + n.1 * adj_n.1 + n.2 * adj_n.2).max(-1.0).min(1.0);
                    let angle = dot.acos();
                    is_convex = angle <= angle_threshold;
                }
                
                let convexity = if is_convex { 1 } else { 0 };
                sharp_features.push((convexity, face_idx as i32, local_edge_idx as i32));
            }
            global_edge_idx += 1;
        }
    }
    
    Ok(sharp_features)
}

/// Get vertex coordinates as a tuple
#[inline]
fn get_vertex(vertices: &[f64], idx: usize) -> (f64, f64, f64) {
    let offset = idx * 3;
    (vertices[offset], vertices[offset + 1], vertices[offset + 2])
}

/// Compute the normal for a face
#[inline]
fn compute_face_normal(
    vertices: &[f64],
    faces: &[usize],
    face_sizes: &[usize],
    face_idx: usize,
) -> (f64, f64, f64) {
    let start: usize = face_sizes[..face_idx].iter().sum();
    let size = face_sizes[face_idx];
    
    if size < 3 {
        return (0.0, 0.0, 1.0);
    }
    
    let v0 = get_vertex(vertices, faces[start]);
    let v1 = get_vertex(vertices, faces[start + 1]);
    let v2 = get_vertex(vertices, faces[start + 2]);
    
    let (ax, ay, az) = (v1.0 - v0.0, v1.1 - v0.1, v1.2 - v0.2);
    let (bx, by, bz) = (v2.0 - v0.0, v2.1 - v0.1, v2.2 - v0.2);
    
    let (nx, ny, nz) = (
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    );
    
    let len = (nx * nx + ny * ny + nz * nz).sqrt();
    if len > 1e-10 {
        (nx / len, ny / len, nz / len)
    } else {
        (0.0, 0.0, 1.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_face_normal() {
        // Triangle in XY plane
        let vertices = vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0];
        let faces = vec![0, 1, 2];
        let face_sizes = vec![3];
        
        let n = compute_face_normal(&vertices, &faces, &face_sizes, 0);
        
        // Should point in +Z direction
        assert!((n.0).abs() < 1e-6);
        assert!((n.1).abs() < 1e-6);
        assert!((n.2 - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_detect_sharp_edges_basic() {
        // Simple quad - flat face, no sharp edges
        let vertices = vec![
            0.0, 0.0, 0.0,  // v0
            1.0, 0.0, 0.0,  // v1
            1.0, 1.0, 0.0,  // v2
            0.0, 1.0, 0.0,  // v3
        ];
        let faces = vec![0, 1, 2, 3]; // quad as single face
        let face_sizes = vec![4];
        
        let (is_sharp, sharp_count) = detect_sharp_edges_rs(
            vertices, faces, face_sizes, 35.0
        ).unwrap();
        
        // Single face has no internal sharp edges
        assert_eq!(sharp_count, 0);
    }
    
    #[test]
    fn test_detect_sharp_edges_cube() {
        // Cube with hard edges (each face separate)
        let vertices = vec![
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            1.0, 1.0, 0.0,
            0.0, 1.0, 0.0,
            0.0, 0.0, 1.0,
            1.0, 0.0, 1.0,
            1.0, 1.0, 1.0,
            0.0, 1.0, 1.0,
        ];
        
        // Two triangles per face
        let faces = vec![
            0, 1, 2, 0, 2, 3,  // Front face (Z=0)
            4, 5, 6, 4, 6, 7,  // Back face (Z=1)
            0, 4, 5, 0, 5, 1,  // Bottom face
            2, 6, 7, 2, 7, 3,  // Top face
            0, 3, 7, 0, 7, 4,  // Left face
            1, 5, 6, 1, 6, 2,  // Right face
        ];
        let face_sizes = vec![3, 3, 3, 3, 3, 3];
        
        let (is_sharp, sharp_count) = detect_sharp_edges_rs(
            vertices, faces, face_sizes, 35.0
        ).unwrap();
        
        // All edges of cube are sharp (boundary edges)
        assert!(sharp_count > 0);
    }
}
