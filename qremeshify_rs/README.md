# QRemeshify Rust Extension

High-performance mesh processing extension for [QRemeshify](https://github.com/QRemeshify/QRemeshify), a Blender addon for quad-based remeshing.

## Overview

This crate provides Rust implementations of performance-critical mesh operations:

- **OBJ I/O** — 10-50x faster file parsing and serialization
- **Sharp Edge Detection** — Parallel processing with Rayon
- **Mesh Validation** — Comprehensive mesh integrity checks

## Requirements

- Rust 1.75+
- Python 3.8+
- maturin (for building)

## Building

```bash
# Install maturin
pip install maturin

# Build for development
maturin develop

# Build release wheels
maturin build --release
```

## Usage

```python
import qremeshify_rs

# Fast OBJ import
vertices, faces, face_sizes, normals = qremeshify_rs.import_mesh_rs("mesh.obj")

# Fast OBJ export
qremeshify_rs.export_mesh_rs(vertices, faces, face_sizes, normals, "output.obj")

# Parallel sharp edge detection
is_sharp, sharp_count = qremeshify_rs.detect_sharp_edges_rs(
    vertices, faces, face_sizes, sharp_angle=35.0
)

# Mesh validation
is_valid, errors, warnings, issues = qremeshify_rs.validate_mesh_rs(
    vertices, faces, face_sizes
)
```

## Architecture

This extension is part of a polyglot architecture:

```
┌─────────────────────────────────────────┐
│   Python (Blender API, Orchestration)   │
└────────────────┬────────────────────────┘
                 │ PyO3
┌────────────────▼────────────────────────┐
│   Rust (OBJ I/O, Parallel Compute)      │
└────────────────┬────────────────────────┘
                 │ ctypes / file I/O
┌────────────────▼────────────────────────┐
│   C++ (QuadWild Libraries)              │
└─────────────────────────────────────────┘
```

## License

GPL-3.0-or-later
