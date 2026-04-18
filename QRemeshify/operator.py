import os
import math
import time

import bpy
import bmesh
import mathutils

from .lib import Quadwild, QWException
from .util import bisect, exporter, importer

# Constants
MIRROR_MERGE_THRESHOLD = 0.001
BISECT_DISTANCE_THRESHOLD = 0.0001
MAX_FACE_COUNT_WARNING = 100000


def _report_debug(report_func, props, message):
    """Helper to report debug messages only when verbose_logging is enabled."""
    if props.verbose_logging:
        report_func({"DEBUG"}, message)


def _validate_mesh(obj: bpy.types.Object) -> str | None:
    """Validate that the object is suitable for remeshing.

    Returns an error message string if validation fails, or None if valid.
    """
    if obj is None or obj.type != "MESH":
        return "Object is not a mesh"
    if len(obj.data.polygons) == 0:
        return "Mesh has 0 faces"
    return None


def _apply_rotation_scale(bm: bmesh.types.BMesh, obj: bpy.types.Object) -> None:
    """Apply rotation and scale from an object to a BMesh via transform.

    Args:
        bm: BMesh to transform.
        obj: Object whose rotation and scale to apply.
    """
    if obj.rotation_mode == "QUATERNION":
        matrix = mathutils.Matrix.LocRotScale(
            None, obj.rotation_quaternion, obj.scale
        )
    else:
        matrix = mathutils.Matrix.LocRotScale(
            None, obj.rotation_euler, obj.scale
        )
    bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)


def _detect_sharp_edges(bm: bmesh.types.BMesh, sharp_angle: float) -> None:
    """Mark edges as sharp based on angle threshold, boundaries, seams,
    material boundaries, and face set boundaries.

    Args:
        bm: BMesh to detect sharp edges on.
        sharp_angle: Angle threshold in degrees.
    """
    face_set_data_layer = bm.faces.layers.int.get(".sculpt_face_set")
    bm.edges.ensure_lookup_table()

    for edge in bm.edges:
        is_sharp = math.degrees(edge.calc_face_angle(0)) > sharp_angle
        is_material_boundary = (
            len(edge.link_faces) > 1
            and edge.link_faces[0].material_index != edge.link_faces[1].material_index
        )
        is_face_set_boundary = (
            face_set_data_layer is not None
            and len(edge.link_faces) > 1
            and edge.link_faces[0][face_set_data_layer]
            != edge.link_faces[1][face_set_data_layer]
        )

        if (
            is_sharp
            or edge.is_boundary
            or edge.seam
            or is_material_boundary
            or is_face_set_boundary
        ):
            edge.smooth = False


class QREMESH_OT_Remesh(bpy.types.Operator):
    """Operator to remesh selected mesh using QuadWild algorithm for quad-based topology generation."""

    bl_idname = "qremeshify.remesh"
    bl_label = "Remesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx: bpy.types.Context) -> set[str]:
        props = ctx.scene.quadwild_props
        qr_props = ctx.scene.quadpatches_props
        selected_objs = ctx.selected_objects

        if len(selected_objs) == 0:
            self.report({"ERROR_INVALID_INPUT"}, "No selected objects")
            return {"CANCELLED"}

        if len(selected_objs) > 1:
            self.report(
                {"INFO"},
                "Multiple objects selected, will only operate on the first selected object",
            )

        obj = selected_objs[0]

        # Validate mesh
        error = _validate_mesh(obj)
        if error:
            self.report({"ERROR_INVALID_INPUT"}, error)
            return {"CANCELLED"}

        face_count = len(obj.data.polygons)
        if face_count > MAX_FACE_COUNT_WARNING:
            self.report(
                {"WARNING"},
                f"Mesh has {face_count} faces - remeshing may be slow. Consider decimating first.",
            )

        original_location = obj.location
        start_time = time.monotonic()

        mesh_filename = "".join(
            c if c not in "\/:*?<>|" else "_" for c in obj.name
        ).strip()
        mesh_filepath = f"{os.path.join(bpy.app.tempdir, mesh_filename)}.obj"
        _report_debug(self.report, props, f"Remeshing from {mesh_filepath}")

        # Load lib
        qw = Quadwild(mesh_filepath)

        # Progress tracking
        wm = ctx.window_manager
        total_steps = 4 if not props.useCache else 1
        wm.progress_begin(0, total_steps)

        try:
            if not props.useCache:
                # Get mesh after modifiers and shapekeys applied
                depsgraph = ctx.evaluated_depsgraph_get()
                evaluated_obj = obj.evaluated_get(depsgraph)
                mesh = evaluated_obj.to_mesh()

                # Create a bmesh from mesh
                bm = bmesh.new()
                bm.from_mesh(mesh)

                # Apply only rotation and scale
                _apply_rotation_scale(bm, evaluated_obj)

                # Bisect to prep for symmetry
                if props.symmetryX or props.symmetryY or props.symmetryZ:
                    bisect.bisect_on_axes(
                        bm, props.symmetryX, props.symmetryY, props.symmetryZ
                    )

                # Find edges to mark as sharp
                if props.enableSharp:
                    _detect_sharp_edges(bm, props.sharpAngle)

                # Triangulate mesh
                bmesh.ops.triangulate(
                    bm, faces=bm.faces, quad_method="SHORT_EDGE", ngon_method="BEAUTY"
                )

                # Export selected object as OBJ
                step_time = time.monotonic()
                exporter.export_mesh(bm, mesh_filepath)
                _report_debug(self.report, props, f"Mesh exported in {time.monotonic() - step_time:.2f}s")
                wm.progress_update(1)

                # Calculate sharp features
                if props.enableSharp:
                    num_sharp_features = exporter.export_sharp_features(
                        bm, qw.sharp_path, props.sharpAngle
                    )
                    _report_debug(self.report, props, f"Found {num_sharp_features} sharp edges")

                # Remesh and calculate field
                self.report({"INFO"}, "Running remeshing and field calculation...")
                step_time = time.monotonic()
                qw.remeshAndField(
                    remesh=props.enableRemesh,
                    enableSharp=props.enableSharp,
                    sharpAngle=props.sharpAngle,
                )
                _report_debug(self.report, props, f"Remesh+field completed in {time.monotonic() - step_time:.2f}s")
                wm.progress_update(2)

                if props.debug:
                    new_mesh = importer.import_mesh(qw.remeshed_path)
                    new_obj = bpy.data.objects.new(
                        f"{obj.name} remeshAndField", new_mesh
                    )
                    ctx.collection.objects.link(new_obj)
                    new_obj.hide_set(True)

                # Trace
                self.report({"INFO"}, "Tracing field lines...")
                step_time = time.monotonic()
                qw.trace()
                _report_debug(self.report, props, f"Trace completed in {time.monotonic() - step_time:.2f}s")
                wm.progress_update(3)

                if props.debug:
                    new_mesh = importer.import_mesh(qw.traced_path)
                    new_obj = bpy.data.objects.new(f"{obj.name} trace", new_mesh)
                    ctx.collection.objects.link(new_obj)
                    new_obj.hide_set(True)

                # Free bmesh resources early
                bm.free()
                del bm
                evaluated_obj.to_mesh_clear()

            # Convert to quads
            self.report({"INFO"}, "Converting to quadrangulated topology...")
            step_time = time.monotonic()
            qw.quadrangulate(
                props.enableSmoothing,
                qr_props.scaleFact,
                qr_props.fixedChartClusters,
                qr_props.alpha,
                qr_props.ilpMethod,
                qr_props.timeLimit,
                qr_props.gapLimit,
                qr_props.minimumGap,
                qr_props.isometry,
                qr_props.regularityQuadrilaterals,
                qr_props.regularityNonQuadrilaterals,
                qr_props.regularityNonQuadrilateralsWeight,
                qr_props.alignSingularities,
                qr_props.alignSingularitiesWeight,
                qr_props.repeatLosingConstraintsIterations,
                qr_props.repeatLosingConstraintsQuads,
                qr_props.repeatLosingConstraintsNonQuads,
                qr_props.repeatLosingConstraintsAlign,
                qr_props.hardParityConstraint,
                qr_props.flowConfig,
                qr_props.satsumaConfig,
                qr_props.callbackTimeLimit,
                qr_props.callbackGapLimit,
            )
            _report_debug(self.report, props, f"Quadrangulation completed in {time.monotonic() - step_time:.2f}s")
            wm.progress_update(total_steps)

            if props.debug and props.enableSmoothing:
                new_mesh = importer.import_mesh(qw.output_path)
                new_obj = bpy.data.objects.new(f"{obj.name} quadrangulate", new_mesh)
                ctx.collection.objects.link(new_obj)
                new_obj.hide_set(True)

            # Import final OBJ
            self.report({"INFO"}, "Importing remeshed mesh...")
            final_mesh_path = (
                qw.output_smoothed_path if props.enableSmoothing else qw.output_path
            )
            final_mesh = importer.import_mesh(final_mesh_path)
            final_obj = bpy.data.objects.new(f"{obj.name} Remeshed", final_mesh)
            ctx.collection.objects.link(final_obj)
            ctx.view_layer.objects.active = final_obj
            final_obj.select_set(True)

            # Set object location
            final_obj.location = original_location

            # Add Mirror modifier for symmetry
            if props.symmetryX or props.symmetryY or props.symmetryZ:
                mirror_modifier = final_obj.modifiers.new("Mirror", "MIRROR")

                mirror_modifier.use_axis[0] = props.symmetryX
                mirror_modifier.use_axis[1] = props.symmetryY
                mirror_modifier.use_axis[2] = props.symmetryZ
                mirror_modifier.use_clip = True
                mirror_modifier.merge_threshold = MIRROR_MERGE_THRESHOLD

            # Hide original
            obj.hide_set(True)

            elapsed = time.monotonic() - start_time
            self.report(
                {"INFO"},
                f"Remeshing complete! {face_count} → {len(final_mesh.polygons)} faces in {elapsed:.1f}s",
            )

        except QWException as e:
            self.report({"ERROR"}, f"Remeshing failed: {e}")
            return {"CANCELLED"}

        except FileNotFoundError as e:
            self.report({"ERROR"}, f"Output file not found: {e}")
            return {"CANCELLED"}

        finally:
            wm.progress_end()
            del qw

        return {"FINISHED"}
