import io
import os

import bmesh

# Import Rust extension with fallback
try:
    from ..rust_ext import export_mesh_rs, is_rust_available
except ImportError:
    export_mesh_rs = None
    is_rust_available = lambda: False


def export_sharp_features(
    bm: bmesh.types.BMesh, sharp_filepath: str, sharp_angle: float = 35
) -> int:
    """Export edges marked sharp, boundary, and seams as sharp features.

    Output format: one line per sharp edge with ``convexity,face_index,edge_index``.
    The file starts with a count line.

    Args:
        bm: BMesh object to export sharp features from.
        sharp_filepath: Destination file path for the .sharp file.
        sharp_angle: Angle threshold in degrees (used for reference only here;
            edges are already marked non-smooth before calling this function).

    Returns:
        Number of sharp features written.
    """
    sharp_edges = []
    bm.edges.index_update()
    bm.edges.ensure_lookup_table()

    for edge in bm.edges:
        if edge.is_wire:
            continue
        if not edge.smooth:
            convexity = 1 if edge.is_convex else 0
            face = edge.link_faces[0]
            face_index = face.index
            for ei, e in enumerate(face.edges):
                if e.index == edge.index:
                    edge_index = ei
                    break
            sharp_edges.append(f"{convexity},{face_index},{edge_index}")

    num_sharp_features = len(sharp_edges)
    with open(sharp_filepath, "w") as f:
        f.write(f"{num_sharp_features}\n")
        f.write("\n".join(sharp_edges))
        if sharp_edges:
            f.write("\n")

    return num_sharp_features


def export_mesh(bm: bmesh.types.BMesh, mesh_filepath: str) -> None:
    """Export mesh as OBJ format with per-face normals.

    Vertices use 6 decimal places; normals use 4 decimal places.
    OBJ indices are 1-based.

    Uses Rust extension if available for improved performance on larger meshes.
    Falls back to pure Python implementation if Rust unavailable.

    Args:
        bm: BMesh object to export.
        mesh_filepath: Destination file path for the .obj file.
    """
    # Try Rust implementation first for medium/large meshes
    vert_count = len(bm.verts)
    if export_mesh_rs is not None and vert_count >= 500:
        try:
            # Convert BMesh to Python types for Rust
            vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
            faces = [tuple(v.index for v in face.verts) for face in bm.faces]
            
            if export_mesh_rs(vertices, faces, mesh_filepath):
                return  # Rust succeeded
        except Exception:
            pass  # Fall through to Python implementation
    
    # Python fallback - original implementation
    buf = io.StringIO()

    # Pre-allocate vertex index strings (1-based)
    vert_indices = [str(i + 1) for i in range(len(bm.verts))]

    # Write vertices
    for v in bm.verts:
        buf.write(f"v {v.co.x:.6f} {v.co.y:.6f} {v.co.z:.6f}\n")

    # Write per-face normals
    for face in bm.faces:
        buf.write(
            f"vn {face.normal.x:.4f} {face.normal.y:.4f} {face.normal.z:.4f}\n"
        )

    # Write faces (referencing vertex indices and normal indices)
    normal_index = 1  # 1-based, increments per face
    for face in bm.faces:
        parts = []
        for v in face.verts:
            parts.append(f"{vert_indices[v.index]}//{normal_index}")
        buf.write(f"f {' '.join(parts)}\n")
        normal_index += 1

    with open(mesh_filepath, "w") as f:
        f.write(buf.getvalue())
