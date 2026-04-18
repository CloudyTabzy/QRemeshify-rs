import bmesh

# Constants
BISECT_DISTANCE_THRESHOLD = 0.0001

# Axis definitions: (plane_normal, label)
_AXES = {
    "x": (1, 0, 0),
    "y": (0, 1, 0),
    "z": (0, 0, 1),
}


def bisect_on_axes(
    bm: bmesh.types.BMesh, xaxis: bool, yaxis: bool, zaxis: bool
) -> None:
    """Bisect mesh along specified axes to prepare for symmetry processing.

    Removes geometry on the negative side of each bisect plane.

    Args:
        bm: BMesh object to bisect.
        xaxis: Whether to bisect along X axis.
        yaxis: Whether to bisect along Y axis.
        zaxis: Whether to bisect along Z axis.
    """
    axis_flags = [("x", xaxis), ("y", yaxis), ("z", zaxis)]

    for axis_name, enabled in axis_flags:
        if not enabled:
            continue

        plane_no = _AXES[axis_name]
        bmesh.ops.bisect_plane(
            bm,
            geom=[v for v in bm.verts] + [e for e in bm.edges] + [f for f in bm.faces],
            dist=BISECT_DISTANCE_THRESHOLD,
            plane_co=(0, 0, 0),
            plane_no=plane_no,
            use_snap_center=False,
            clear_outer=False,
            clear_inner=True,
        )
