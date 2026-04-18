import bpy
import os

# Import Rust extension with fallback
try:
    from ..rust_ext import import_mesh_rs, is_rust_available
except ImportError:
    import_mesh_rs = None
    is_rust_available = lambda: False


def import_mesh(mesh_filepath: str) -> bpy.types.Mesh:
    """Import mesh from OBJ file.

    Handles standard OBJ face formats: ``v``, ``v/vt``, ``v/vt/vn``, ``v//vn``.
    OBJ vertex indices are 1-based and converted to 0-based.

    Uses Rust extension if available for improved performance on larger meshes.
    Falls back to pure Python implementation if Rust unavailable.

    Args:
        mesh_filepath: Path to the .obj file to import.

    Returns:
        A new Blender mesh object.

    Raises:
        FileNotFoundError: If the mesh file does not exist.
    """
    if not os.path.isfile(mesh_filepath):
        raise FileNotFoundError(f"Mesh file not found: {mesh_filepath}")

    # Try Rust implementation first for medium/large files
    if import_mesh_rs is not None:
        file_size = os.path.getsize(mesh_filepath)
        if file_size >= 1024:  # Use Rust for files >= 1KB (rough indicator of mesh size)
            try:
                result = import_mesh_rs(mesh_filepath)
                if result is not None:
                    verts, faces = result
                    new_mesh = bpy.data.meshes.new("Mesh")
                    new_mesh.from_pydata(verts, [], faces)
                    new_mesh.update()
                    return new_mesh
            except Exception:
                pass  # Fall through to Python implementation

    # Python fallback - original implementation
    with open(mesh_filepath, "r") as f:
        lines = f.read().splitlines()

    verts = []
    faces = []

    for line in lines:
        if not line:
            continue
        first_char = line[0]
        if first_char == "v" and len(line) > 1 and line[1] == " ":
            tokens = line.split()
            verts.append(
                (float(tokens[1]), float(tokens[2]), float(tokens[3]))
            )
        elif first_char == "f":
            tokens = line.split()
            face_verts = []
            for token in tokens[1:]:
                # Handle all OBJ face formats: v, v/vt, v/vt/vn, v//vn
                vert_id = int(token.partition("/")[0]) - 1
                face_verts.append(vert_id)
            faces.append(tuple(face_verts))

    new_mesh = bpy.data.meshes.new("Mesh")
    new_mesh.from_pydata(verts, [], faces)
    new_mesh.update()

    return new_mesh
