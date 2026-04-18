import platform
import sys
from ctypes import *
from os import path
from .data import Parameters, QRParameters, create_string, create_default_QRParameters

ilp_methods = {
    "LEASTSQUARES": 1,
    "ABS": 2,
}

flow_config_files = {
    "SIMPLE": "config/main_config/flow_virtual_simple.json",
    "HALF": "config/main_config/flow_virtual_half.json",
}

satsuma_config_files = {
    "DEFAULT": "config/satsuma/default.json",
    "MST": "config/satsuma/approx-mst.json",
    "ROUND2EVEN": "config/satsuma/approx-round2even.json",
    "SYMMDC": "config/satsuma/approx-symmdc.json",
    "EDGETHRU": "config/satsuma/edgethru.json",
    "LEMON": "config/satsuma/lemon.json",
    "NODETHRU": "config/satsuma/nodethru.json",
}

# Module-level library cache — loaded once, reused across operator calls
_quadwild_lib = None
_quadpatches_lib = None


class QWException(Exception):
    """Custom exception for QuadWild library errors during remeshing operations."""


def _get_native_libraries():
    """Load and cache native QuadWild libraries.

    Libraries are loaded once and cached at module level to avoid
    repeated LoadLibrary calls on every operator execution.

    Returns:
        Tuple of (quadwild_lib, quadpatches_lib) ctypes library handles.

    Raises:
        QWException: If libraries fail to load or Python version is unsupported.
    """
    global _quadwild_lib, _quadpatches_lib

    if _quadwild_lib is not None and _quadpatches_lib is not None:
        return _quadwild_lib, _quadpatches_lib

    python_version = sys.version_info
    if python_version < (3, 10):
        raise QWException(
            f"Python {python_version.major}.{python_version.minor} not supported. Requires Python 3.10+"
        )

    system = platform.system()
    if system == "Windows":
        quadwild_lib_filename = "lib_quadwild.dll"
        quadpatches_lib_filename = "lib_quadpatches.dll"
    elif system == "Darwin":
        quadwild_lib_filename = "liblib_quadwild.dylib"
        quadpatches_lib_filename = "liblib_quadpatches.dylib"
    else:
        quadwild_lib_filename = "liblib_quadwild.so"
        quadpatches_lib_filename = "liblib_quadpatches.so"

    lib_dir = path.dirname(path.abspath(__file__))
    quadwild_lib_path = path.join(lib_dir, quadwild_lib_filename)
    quadpatches_lib_path = path.join(lib_dir, quadpatches_lib_filename)

    try:
        _quadwild_lib = cdll.LoadLibrary(quadwild_lib_path)
    except Exception as e:
        raise QWException(
            f"Failed to load {quadwild_lib_filename}: {e}. "
            f"Ensure the library is compatible with Python {python_version.major}.{python_version.minor}"
        ) from e

    try:
        _quadpatches_lib = cdll.LoadLibrary(quadpatches_lib_path)
    except Exception as e:
        raise QWException(
            f"Failed to load {quadpatches_lib_filename}: {e}. "
            f"Ensure the library is compatible with Python {python_version.major}.{python_version.minor}"
        ) from e

    # Set up function signatures
    _quadwild_lib.remeshAndField2.argtypes = [
        POINTER(Parameters),
        c_char_p,
        c_char_p,
        c_char_p,
    ]
    _quadwild_lib.remeshAndField2.restype = None

    _quadwild_lib.trace2.argtypes = [c_char_p]
    _quadwild_lib.trace2.restype = c_bool

    _quadpatches_lib.quadPatches.argtypes = [
        c_char_p,
        POINTER(QRParameters),
        c_float,
        c_int,
        c_bool,
    ]
    _quadpatches_lib.quadPatches.restype = c_int

    return _quadwild_lib, _quadpatches_lib


class Quadwild:
    """Wrapper class for QuadWild native library providing remeshing and quadrangulation functionality.

    Uses cached native library instances to avoid repeated loading on each operator call.
    """

    def __init__(self, mesh_path: str) -> None:
        if mesh_path is None or len(mesh_path) == 0:
            raise QWException("mesh_path is empty")

        self.quadwild, self.quadpatches = _get_native_libraries()

        self.mesh_path = mesh_path
        self.mesh_path_without_ext, _ = path.splitext(mesh_path)
        self.sharp_path = f"{self.mesh_path_without_ext}_rem.sharp"
        self.field_path = f"{self.mesh_path_without_ext}_rem.rosy"
        self.remeshed_path = f"{self.mesh_path_without_ext}_rem.obj"
        self.traced_path = f"{self.mesh_path_without_ext}_rem_p0.obj"
        self.output_path = f"{self.mesh_path_without_ext}_rem_p0_0_quadrangulation.obj"
        self.output_smoothed_path = (
            f"{self.mesh_path_without_ext}_rem_p0_0_quadrangulation_smooth.obj"
        )

    def remeshAndField(
        self, remesh: bool, enableSharp: bool, sharpAngle: float
    ) -> None:
        """Run remeshing and field calculation.

        Args:
            remesh: Whether to run the remeshing preprocessing step.
            enableSharp: Whether sharp feature detection is enabled.
            sharpAngle: Angle threshold for sharp edges in degrees.

        Raises:
            QWException: If the native library call fails.
        """
        params = Parameters(
            remesh=remesh,
            sharpAngle=sharpAngle if enableSharp else -1,
            hasFeature=enableSharp,
            hasField=False,
            alpha=0.01,  # Unused
            scaleFact=1,  # Unused
        )
        mesh_filename_c = create_string(self.mesh_path)
        sharp_filename_c = create_string(self.sharp_path)
        field_filename_c = create_string(self.field_path)
        try:
            self.quadwild.remeshAndField2(
                byref(params), mesh_filename_c, sharp_filename_c, field_filename_c
            )
        except Exception as e:
            raise QWException("remeshAndField failed") from e

    def trace(self) -> bool:
        """Trace field lines on the remeshed geometry.

        Returns:
            True if tracing succeeded.

        Raises:
            QWException: If the native library call fails.
        """
        remeshed_path_without_ext, _ = path.splitext(self.remeshed_path)
        filename_prefix_c = create_string(remeshed_path_without_ext)
        try:
            return self.quadwild.trace2(filename_prefix_c)
        except Exception as e:
            raise QWException("trace failed") from e

    def quadrangulate(
        self,
        enableSmoothing: bool,
        scaleFact: float,
        fixedChartClusters: int,
        alpha: float,
        ilpMethod: str,
        timeLimit: int,
        gapLimit: float,
        minimumGap: float,
        isometry: bool,
        regularityQuadrilaterals: bool,
        regularityNonQuadrilaterals: bool,
        regularityNonQuadrilateralsWeight: float,
        alignSingularities: bool,
        alignSingularitiesWeight: float,
        repeatLosingConstraintsIterations: bool,
        repeatLosingConstraintsQuads: bool,
        repeatLosingConstraintsNonQuads: bool,
        repeatLosingConstraintsAlign: bool,
        hardParityConstraint: bool,
        flowConfig: str,
        satsumaConfig: str,
        callbackTimeLimit: list[float],
        callbackGapLimit: list[float],
    ) -> int:
        """Run quadrangulation optimization.

        Args:
            enableSmoothing: Whether to apply final smoothing.
            scaleFact: Scale factor for quad size (>1 for larger, <1 for more detail).
            fixedChartClusters: Number of fixed chart clusters (0 for automatic).
            alpha: Blend between isometry (alpha) and regularity (1-alpha).
            ilpMethod: ILP method name ("LEASTSQUARES" or "ABS").
            timeLimit: Optimization time limit in seconds.
            gapLimit: Optimization stops when gap reaches this value.
            minimumGap: Minimum gap value optimization must reach.
            isometry: Enable isometry constraint.
            regularityQuadrilaterals: Enable regularity for quads.
            regularityNonQuadrilaterals: Enable regularity for non-quads.
            regularityNonQuadrilateralsWeight: Weight for non-quad regularity.
            alignSingularities: Enable singularity alignment.
            alignSingularitiesWeight: Weight for singularity alignment.
            repeatLosingConstraintsIterations: Repeat losing constraints for iterations.
            repeatLosingConstraintsQuads: Repeat losing constraints for quads.
            repeatLosingConstraintsNonQuads: Repeat losing constraints for non-quads.
            repeatLosingConstraintsAlign: Repeat losing constraints for alignment.
            hardParityConstraint: Use hard parity constraint.
            flowConfig: Flow configuration name.
            satsumaConfig: Satsuma solver configuration name.
            callbackTimeLimit: Time limits for optimization callbacks.
            callbackGapLimit: Gap limits for optimization callbacks.

        Returns:
            Result code from the quadrangulation (0 = success).

        Raises:
            QWException: If the native library call fails.
        """
        params = create_default_QRParameters()

        params.alpha = alpha
        params.ilpMethod = ilp_methods[ilpMethod]
        params.timeLimit = timeLimit
        params.gapLimit = gapLimit
        params.minimumGap = minimumGap
        params.isometry = isometry
        params.regularityQuadrilaterals = regularityQuadrilaterals
        params.regularityNonQuadrilaterals = regularityNonQuadrilaterals
        params.regularityNonQuadrilateralsWeight = regularityNonQuadrilateralsWeight
        params.alignSingularities = alignSingularities
        params.alignSingularitiesWeight = alignSingularitiesWeight
        params.repeatLosingConstraintsIterations = repeatLosingConstraintsIterations
        params.repeatLosingConstraintsQuads = repeatLosingConstraintsQuads
        params.repeatLosingConstraintsNonQuads = repeatLosingConstraintsNonQuads
        params.repeatLosingConstraintsAlign = repeatLosingConstraintsAlign
        params.hardParityConstraint = hardParityConstraint

        lib_dir = path.dirname(path.abspath(__file__))
        params.flow_config_filename = path.join(
            lib_dir, flow_config_files[flowConfig]
        ).encode()
        params.satsuma_config_filename = path.join(
            lib_dir, satsuma_config_files[satsumaConfig]
        ).encode()

        params.callbackTimeLimit = (c_float * len(callbackTimeLimit))(
            *callbackTimeLimit
        )
        params.callbackGapLimit = (c_float * len(callbackGapLimit))(*callbackGapLimit)

        mesh_path_c = self.traced_path.encode()
        try:
            return self.quadpatches.quadPatches(
                mesh_path_c,
                byref(params),
                scaleFact,
                fixedChartClusters,
                enableSmoothing,
            )
        except Exception as e:
            raise QWException("quadPatches failed") from e
