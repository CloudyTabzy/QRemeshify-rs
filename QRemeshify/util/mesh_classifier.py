# util/mesh_classifier.py
# Smart mesh-size detection for adaptive optimization

"""
Mesh Size Classification Module

Provides automatic detection of mesh complexity to route processing
to appropriate optimization strategies.

Categories:
    TINY:   < 500 vertices     - Minimal overhead, skip validation
    SMALL:  500 - 2K vertices  - Standard Python path
    MEDIUM: 2K - 20K vertices  - Rust OBJ I/O enabled
    LARGE:  20K - 100K vertices - Rust + parallel sharp detection
    HUGE:   > 100K vertices    - All optimizations + memmap

Usage:
    from .util.mesh_classifier import detect_mesh_category, MeshCategory
    
    category = detect_mesh_category(bm)
    if category == MeshCategory.LARGE:
        # Use Rust + parallel processing
        ...
"""

import bmesh
from enum import Enum
from typing import Tuple


class MeshCategory(Enum):
    """Mesh size categories for optimization routing."""
    TINY = "tiny"      # < 500 vertices
    SMALL = "small"    # 500 - 2K vertices
    MEDIUM = "medium"  # 2K - 20K vertices
    LARGE = "large"    # 20K - 100K vertices
    HUGE = "huge"      # > 100K vertices


# Threshold constants
TINY_THRESHOLD = 500
SMALL_THRESHOLD = 2000
MEDIUM_THRESHOLD = 20000
LARGE_THRESHOLD = 100000


def detect_mesh_category(bm: bmesh.types.BMesh) -> MeshCategory:
    """
    Auto-detect mesh size category for optimization selection.
    
    Analyzes the BMesh and returns the appropriate category based
    on vertex count and complexity.
    
    Args:
        bm: BMesh object to classify
    
    Returns:
        MeshCategory enum value indicating the mesh size class
    """
    vert_count = len(bm.verts)
    
    if vert_count < TINY_THRESHOLD:
        return MeshCategory.TINY
    elif vert_count < SMALL_THRESHOLD:
        return MeshCategory.SMALL
    elif vert_count < MEDIUM_THRESHOLD:
        return MeshCategory.MEDIUM
    elif vert_count < LARGE_THRESHOLD:
        return MeshCategory.LARGE
    else:
        return MeshCategory.HUGE


def detect_mesh_stats(bm: bmesh.types.BMesh) -> dict:
    """
    Get detailed mesh statistics for optimization decisions.
    
    Args:
        bm: BMesh object to analyze
    
    Returns:
        Dict with vertex_count, face_count, edge_count, and complexity_score
    """
    vert_count = len(bm.verts)
    face_count = len(bm.faces)
    edge_count = len(bm.edges)
    
    # Calculate complexity score
    # Higher score = more complex mesh = more benefit from Rust optimizations
    if face_count > 0:
        complexity = vert_count * (edge_count / face_count)
    else:
        complexity = vert_count
    
    return {
        "vertex_count": vert_count,
        "face_count": face_count,
        "edge_count": edge_count,
        "complexity_score": complexity,
        "category": detect_mesh_category(bm).value
    }


def get_optimization_hints(category: MeshCategory) -> dict:
    """
    Get optimization hints for a mesh category.
    
    Args:
        category: MeshCategory enum value
    
    Returns:
        Dict with optimization recommendations
    """
    hints = {
        MeshCategory.TINY: {
            "use_rust_io": False,
            "use_validation": False,
            "use_parallel_sharp": False,
            "use_memmap": False,
            "description": "Tiny mesh - use minimal overhead Python path"
        },
        MeshCategory.SMALL: {
            "use_rust_io": False,
            "use_validation": True,
            "use_parallel_sharp": False,
            "use_memmap": False,
            "description": "Small mesh - standard Python path with validation"
        },
        MeshCategory.MEDIUM: {
            "use_rust_io": True,
            "use_validation": True,
            "use_parallel_sharp": False,
            "use_memmap": False,
            "description": "Medium mesh - Rust OBJ I/O enabled"
        },
        MeshCategory.LARGE: {
            "use_rust_io": True,
            "use_validation": True,
            "use_parallel_sharp": True,
            "use_memmap": False,
            "description": "Large mesh - Rust + parallel sharp detection"
        },
        MeshCategory.HUGE: {
            "use_rust_io": True,
            "use_validation": True,
            "use_parallel_sharp": True,
            "use_memmap": True,
            "description": "Huge mesh - all optimizations + memory-mapped I/O"
        }
    }
    
    return hints.get(category, hints[MeshCategory.MEDIUM])


def should_use_rust_io(category: MeshCategory) -> bool:
    """Check if Rust I/O should be used for this category."""
    return category in (MeshCategory.MEDIUM, MeshCategory.LARGE, MeshCategory.HUGE)


def should_use_parallel_sharp(category: MeshCategory) -> bool:
    """Check if parallel sharp edge detection should be used."""
    return category in (MeshCategory.LARGE, MeshCategory.HUGE)


def should_use_memmap(category: MeshCategory) -> bool:
    """Check if memory-mapped I/O should be used."""
    return category == MeshCategory.HUGE


# Convenience function for exporter/importer routing
def get_io_strategy(bm: bmesh.types.BMesh) -> Tuple[str, dict]:
    """
    Get the recommended I/O strategy for a BMesh.
    
    Returns:
        Tuple of (strategy_name, hints_dict)
        strategy_name is one of: "python", "rust", "memmap"
    """
    category = detect_mesh_category(bm)
    hints = get_optimization_hints(category)
    
    if hints["use_memmap"]:
        return "memmap", hints
    elif hints["use_rust_io"]:
        return "rust", hints
    else:
        return "python", hints