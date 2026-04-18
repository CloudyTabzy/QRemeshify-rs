# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-04-18

### Added
- **Rust-accelerated OBJ I/O** - High-performance mesh serialization/deserialization using PyO3
  - Automatic fallback to pure Python if Rust extension unavailable
  - Size-based routing: Rust used for meshes ≥500 vertices
- **Adaptive mesh-size optimization** - Smart detection and strategy selection
  - TINY (<500 verts): Minimal overhead path
  - SMALL (500-2K verts): Standard Python path
  - MEDIUM (2K-20K verts): Rust OBJ I/O enabled
  - LARGE (20K-100K verts): Rust + parallel processing
  - HUGE (>100K verts): All optimizations + memory-mapped I/O
- **`verbose_logging` preference** - Detailed debug output toggle (OFF by default)
- **Mesh classifier module** - `util/mesh_classifier.py` for complexity analysis

### Changed
- Better compatibility with **Blender 5.0+**
- Updated maintainer attribution to me, "Tabzy"
- Verbose logging OFF by default for cleaner user experience
- Development documentation added to `Docs/TODO.md`

### Technical
- Added `qremeshify_rs` Rust crate with PyO3 bindings
- Parallel sharp edge detection using Rayon
- Mesh validation utilities

## [1.4.0] - Initial Rust Extension Foundation

### Added
- Rust extension skeleton (`qremeshify_rs/`)
- PyO3 integration framework
- Parallel processing infrastructure

## [1.1.0 - 1.3.0] - Foundational Updates

### Added
- Initial compatibility with Blender 5.0+
- Misellaneous optimizations

## [Prior Versions]

See original [QRemeshify by ksami](https://github.com/ksami/QRemeshify) for history prior to v1.4.0.

---

## Release Assets

Each release includes:
- `QRemeshify-v*.zip` - Ready-to-install Blender addon
- Pre-built `qremeshify_rs.pyd` for Windows (Python 3.10+)

### Platform Notes

| Platform | Status | Notes |
|----------|--------|-------|
| Windows x64 | ✅ Built-in | Included in release |
| macOS | ⚠️ Build required | Requires Rust + cargo |
| Linux | ⚠️ Build required | Requires Rust + cargo |

Build instructions for other platforms are in [README.md](README.md#building-from-source).
