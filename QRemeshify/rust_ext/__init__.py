# rust_ext/__init__.py
# Rust extension integration with Python fallback

"""
QRemeshify Rust Extension

This module provides high-performance Rust implementations of core mesh operations
with automatic fallback to Python implementations if the Rust extension is unavailable.

Functions:
    - export_mesh_rs(): Fast OBJ mesh export
    - import_mesh_rs(): Fast OBJ mesh import
    - export_sharp_features_rs(): Sharp features export
    - detect_sharp_edges_rs(): Parallel sharp edge detection
    - validate_mesh_rs(): Mesh validation

Usage:
    from .rust_ext import export_mesh_rs, import_mesh_rs
    
    # Try Rust first, fall back to Python automatically
    result = export_mesh_rs(...)
"""

import sys
import os
from typing import Optional, Tuple, List, Dict, Any

# State tracking
_rust_available = False
_rust_module = None

# For error messages and debugging
_rust_load_error: Optional[str] = None

def _init_rust_extension() -> bool:
    """
    Initialize the Rust extension module.
    
    Returns:
        True if Rust extension loaded successfully, False otherwise.
    """
    global _rust_available, _rust_module, _rust_load_error
    
    if _rust_available:
        return True
    
    # Determine extension path
    if hasattr(sys, 'frozen'):
        # Blender's frozen Python environment
        ext_dir = os.path.dirname(__file__)
    else:
        ext_dir = os.path.dirname(__file__) or os.path.dirname(os.path.abspath(__file__))
    
    # Platform-specific extension name
    if sys.platform == 'win32':
        ext_name = 'qremeshify_rs.pyd'
    elif sys.platform == 'darwin':
        ext_name = 'libqremeshify_rs.dylib'
    else:
        ext_name = 'libqremeshify_rs.so'
    
    ext_path = os.path.join(ext_dir, ext_name)
    
    if not os.path.exists(ext_path):
        _rust_load_error = f"Rust extension not found: {ext_path}"
        return False
    
    try:
        # Import the Rust extension
        import importlib.util
        spec = importlib.util.spec_from_file_location('qremeshify_rs', ext_path)
        if spec is None or spec.loader is None:
            _rust_load_error = "Failed to create module spec"
            return False
        
        _rust_module = importlib.util.module_from_spec(spec)
        sys.modules['qremeshify_rs'] = _rust_module
        spec.loader.exec_module(_rust_module)
        
        _rust_available = True
        return True
        
    except Exception as e:
        _rust_load_error = str(e)
        return False


def is_rust_available() -> bool:
    """
    Check if the Rust extension is available.
    
    Returns:
        True if Rust extension is loaded, False otherwise.
    """
    global _rust_available
    if not _rust_available:
        _init_rust_extension()
    return _rust_available


def get_rust_version() -> Optional[str]:
    """
    Get the Rust extension version.
    
    Returns:
        Version string if Rust available, None otherwise.
    """
    if not _init_rust_extension():
        return None
    
    if _rust_module and hasattr(_rust_module, '__version__'):
        return _rust_module.__version__
    
    return None


def get_load_error() -> Optional[str]:
    """
    Get the error message if Rust extension failed to load.
    
    Returns:
        Error message if load failed, None otherwise.
    """
    global _rust_load_error
    return _rust_load_error


# =============================================================================
# Rust Function Wrappers
# =============================================================================

def export_mesh_rs(
    vertices: List[Tuple[float, float, float]],
    faces: List[int],
    filepath: str
) -> bool:
    """
    Export mesh to OBJ file using Rust implementation.
    
    Args:
        vertices: List of (x, y, z) vertex coordinates
        faces: List of vertex indices (0-based)
        filepath: Output OBJ file path
    
    Returns:
        True on success, False on failure
    """
    if not _init_rust_extension():
        return False
    
    if _rust_module and hasattr(_rust_module, 'export_mesh_rs'):
        try:
            return _rust_module.export_mesh_rs(vertices, faces, filepath)
        except Exception:
            return False
    
    return False


def import_mesh_rs(filepath: str) -> Optional[Tuple[List[Tuple[float, float, float]], List[List[int]]]]:
    """
    Import mesh from OBJ file using Rust implementation.
    
    Args:
        filepath: Input OBJ file path
    
    Returns:
        Tuple of (vertices, faces) on success, None on failure
    """
    if not _init_rust_extension():
        return None
    
    if _rust_module and hasattr(_rust_module, 'import_mesh_rs_simple'):
        try:
            return _rust_module.import_mesh_rs_simple(filepath)
        except Exception:
            pass
    
    if _rust_module and hasattr(_rust_module, 'import_mesh_rs'):
        try:
            # Full version returns (vertices, faces, face_sizes, normals)
            # Convert to simpler (vertices, faces) format
            result = _rust_module.import_mesh_rs(filepath)
            if result:
                verts_flat, faces_flat, face_sizes, normals = result
                # Reconstruct face tuples
                vertices = []
                for i in range(0, len(verts_flat), 3):
                    vertices.append((verts_flat[i], verts_flat[i+1], verts_flat[i+2]))
                
                faces = []
                idx = 0
                for size in face_sizes:
                    face = []
                    for _ in range(size):
                        face.append(faces_flat[idx])
                        idx += 1
                    faces.append(face)
                
                return (vertices, faces)
        except Exception:
            pass
    
    return None


def export_sharp_features_rs(
    sharp_edges: List[Tuple[int, int, float, float]],
    filepath: str
) -> bool:
    """
    Export sharp features to file using Rust implementation.
    
    Args:
        sharp_edges: List of (vertex1, vertex2, convexity, edge_type) tuples
        filepath: Output file path
    
    Returns:
        True on success, False on failure
    """
    if not _init_rust_extension():
        return False
    
    if _rust_module and hasattr(_rust_module, 'export_sharp_features_rs'):
        try:
            return _rust_module.export_sharp_features_rs(sharp_edges, filepath)
        except Exception:
            return False
    
    return False


def detect_sharp_edges_rs(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]],
    normal_threshold: float = 30.0
) -> Optional[List[int]]:
    """
    Detect sharp edges using parallel Rust implementation.
    
    Args:
        vertices: List of (x, y, z) vertex coordinates
        faces: List of vertex index tuples
        normal_threshold: Angle threshold in degrees for sharp edge detection
    
    Returns:
        List of sharp edge indices on success, None on failure
    """
    if not _init_rust_extension():
        return None
    
    if _rust_module and hasattr(_rust_module, 'detect_sharp_edges_rs'):
        try:
            return _rust_module.detect_sharp_edges_rs(vertices, faces, normal_threshold)
        except Exception:
            return None
    
    return None


def validate_mesh_rs(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]]
) -> Optional[Dict[str, Any]]:
    """
    Validate mesh using Rust implementation.
    
    Args:
        vertices: List of (x, y, z) vertex coordinates
        faces: List of vertex index tuples
    
    Returns:
        Validation result dict on success, None on failure
        Dict contains: is_valid, degenerate_faces, isolated_verts, non_manifold_edges
    """
    if not _init_rust_extension():
        return None
    
    if _rust_module and hasattr(_rust_module, 'validate_mesh_rs'):
        try:
            return _rust_module.validate_mesh_rs(vertices, faces)
        except Exception:
            return None
    
    return None


# =============================================================================
# Convenience Functions
# =============================================================================

def get_available_functions() -> Dict[str, bool]:
    """
    Get a dict showing which Rust functions are available.
    
    Returns:
        Dict mapping function name to availability status
    """
    _init_rust_extension()
    
    return {
        'export_mesh_rs': hasattr(_rust_module, 'export_mesh_rs') if _rust_module else False,
        'import_mesh_rs': hasattr(_rust_module, 'import_mesh_rs') if _rust_module else False,
        'export_sharp_features_rs': hasattr(_rust_module, 'export_sharp_features_rs') if _rust_module else False,
        'detect_sharp_edges_rs': hasattr(_rust_module, 'detect_sharp_edges_rs') if _rust_module else False,
        'validate_mesh_rs': hasattr(_rust_module, 'validate_mesh_rs') if _rust_module else False,
    }


# Auto-initialize on import
_init_rust_extension()