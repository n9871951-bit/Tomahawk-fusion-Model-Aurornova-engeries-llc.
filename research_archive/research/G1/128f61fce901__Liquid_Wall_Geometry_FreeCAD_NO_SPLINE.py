"""
Tomahawk liquid-wall screening geometry builder for FreeCAD 0.21 / 1.x.

This version is intended to run inside FreeCAD, create a visible document,
save an FCStd model, and export STEP geometry plus a JSON manifest.

IMPORTANT ENGINEERING STATUS
----------------------------
The EV007 formula is used as the plasma-boundary reference. EV007 is not a
first wall. Standoff, liquid thickness, backing thickness, flow topology,
and material names below are screening assumptions, not validated design
values. This macro does not perform MHD, heat transfer, neutronics, stress,
fatigue, creep, or DPA calculations.

Default output directory:
    Windows: C:\\Users\\<you>\\Documents\\Tomahawk_Liquid_Wall_FreeCAD
    Linux:   /home/<you>/Documents/Tomahawk_Liquid_Wall_FreeCAD

Run from FreeCAD's View -> Panels -> Python console:

    import runpy
    runpy.run_path(r"C:\\full\\path\\Liquid_Wall_Geometry_FreeCAD_FIXED.py",
                   run_name="__main__")

Or headlessly:

    FreeCADCmd Liquid_Wall_Geometry_FreeCAD_FIXED.py --out OUTPUT_FOLDER

Ordinary Python can run the analytic checks only:

    python Liquid_Wall_Geometry_FreeCAD_FIXED.py --preflight
"""

import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path


# ---------------------------------------------------------------------------
# SCREENING ASSUMPTIONS. Review these before using exported geometry.
# FreeCAD stores geometry in millimetres; these source values remain in metres
# and are converted exactly once when App.Vector objects are created.
# ---------------------------------------------------------------------------
SETTINGS = {
    "liquid_metal_name": "PbLi_SCREENING_ASSUMPTION",
    "solid_backing_alloy": "ODS_FeCrAl_SCREENING_ASSUMPTION",
    "standoff_m": 0.05,
    "liquid_thickness_m": 0.02,
    "backing_thickness_m": 0.05,
    "flow_topology": "gravity_fed_poloidal_SCREENING_ASSUMPTION",
    "inlet_theta_deg_range": [80.0, 100.0],
    "outlet_theta_deg_range": [260.0, 280.0],
    "laser_footprint_theta_deg_range": [-15.0, 15.0],
    "support_face_assumption": "outer_coolant_interface",
    # Forced for compatibility with FreeCAD installations that raise
    # Part.OCCError("not enough points given") during B-spline interpolation.
    "construction_mode": "faceted_robust_no_spline",
    "build_quality": "standard",
    "export_step": True,
}


# Use "preview" first on a slow computer. "solver" is only a denser CAD
# approximation; it does not make the geometry solver-qualified by itself.
QUALITY_LEVELS = {
    "preview": {"n_theta": 24, "n_phi": 64},
    "standard": {"n_theta": 48, "n_phi": 128},
    "solver": {"n_theta": 64, "n_phi": 256},
}


# Analytic EV007 parameters supplied in the earlier repair/verification data.
R0_M = 7.499999999999888
A_M = 2.999999999999756
B_M = 2.138969432449380
EPSILON_M = 0.009999999999999069
PERIODS = 16
M_TO_MM = 1000.0
DOCUMENT_BASENAME = "Tomahawk_Liquid_Wall"
OUTPUT_FOLDER_NAME = "Tomahawk_Liquid_Wall_FreeCAD"
BUILD_EVENTS = []


def ev007_point_m(theta, phi):
    """Return one EV007 point in metres."""
    radius = (
        R0_M
        + A_M * math.cos(theta)
        + EPSILON_M * math.cos(theta - PERIODS * phi)
    )
    z_value = B_M * math.sin(theta) + EPSILON_M * math.sin(
        theta - PERIODS * phi
    )
    return (
        radius * math.cos(phi),
        radius * math.sin(phi),
        z_value,
    )


def ev007_normal(theta, phi, delta=1.0e-6):
    """Return an outward unit normal estimated from analytic-surface tangents."""
    p0 = ev007_point_m(theta, phi)
    p_theta = ev007_point_m(theta + delta, phi)
    p_phi = ev007_point_m(theta, phi + delta)

    tangent_theta = tuple((p_theta[i] - p0[i]) / delta for i in range(3))
    tangent_phi = tuple((p_phi[i] - p0[i]) / delta for i in range(3))

    nx = tangent_theta[1] * tangent_phi[2] - tangent_theta[2] * tangent_phi[1]
    ny = tangent_theta[2] * tangent_phi[0] - tangent_theta[0] * tangent_phi[2]
    nz = tangent_theta[0] * tangent_phi[1] - tangent_theta[1] * tangent_phi[0]
    magnitude = math.sqrt(nx * nx + ny * ny + nz * nz)
    if magnitude < 1.0e-12:
        raise RuntimeError("Degenerate EV007 normal at theta/phi sample")

    # Orient relative to the local toroidal centerline, not the global axis.
    local_center = (
        R0_M * math.cos(phi),
        R0_M * math.sin(phi),
        0.0,
    )
    from_center = tuple(p0[i] - local_center[i] for i in range(3))
    if nx * from_center[0] + ny * from_center[1] + nz * from_center[2] < 0.0:
        nx, ny, nz = -nx, -ny, -nz

    return nx / magnitude, ny / magnitude, nz / magnitude


def offset_point_m(theta, phi, distance_m):
    point = ev007_point_m(theta, phi)
    normal = ev007_normal(theta, phi)
    return tuple(point[i] + normal[i] * distance_m for i in range(3))


def offset_vector_mm(App, theta, phi, distance_m):
    x_value, y_value, z_value = offset_point_m(theta, phi, distance_m)
    return App.Vector(
        x_value * M_TO_MM,
        y_value * M_TO_MM,
        z_value * M_TO_MM,
    )


def validate_settings(quality):
    for key in ("standoff_m", "liquid_thickness_m", "backing_thickness_m"):
        value = SETTINGS[key]
        if not isinstance(value, (int, float)) or value <= 0.0:
            raise ValueError("SETTINGS[%r] must be a positive number" % key)

    if quality not in QUALITY_LEVELS:
        raise ValueError("Unknown quality %r" % quality)

    resolution = QUALITY_LEVELS[quality]
    if resolution["n_phi"] % PERIODS != 0:
        raise ValueError("n_phi must be an integer multiple of EV007 PERIODS")

    for key in (
        "inlet_theta_deg_range",
        "outlet_theta_deg_range",
        "laser_footprint_theta_deg_range",
    ):
        values = SETTINGS[key]
        if len(values) != 2 or values[1] <= values[0]:
            raise ValueError("SETTINGS[%r] must be [minimum, maximum]" % key)


def default_output_directory():
    documents = Path.home() / "Documents"
    base_directory = documents if documents.exists() else Path.home()
    return base_directory / OUTPUT_FOLDER_NAME


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Build Tomahawk liquid-wall screening geometry in FreeCAD"
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run analytic checks only; FreeCAD is not required",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: Documents/%s)" % OUTPUT_FOLDER_NAME,
    )
    parser.add_argument(
        "--quality",
        choices=sorted(QUALITY_LEVELS),
        default=SETTINGS["build_quality"],
        help="CAD sampling density",
    )
    parser.add_argument(
        "--no-step",
        action="store_true",
        help="Create and save FCStd only; skip STEP exports",
    )

    # FreeCAD GUI and FreeCADCmd may place their own flags in sys.argv.
    # Ignoring unknown flags prevents the macro from exiting before it builds.
    args, _unknown = parser.parse_known_args()
    return args


def run_preflight(quality):
    validate_settings(quality)
    resolution = QUALITY_LEVELS[quality]
    print("Tomahawk liquid-wall analytic preflight")
    print("Quality: %s (%d theta x %d phi samples)" % (
        quality,
        resolution["n_theta"],
        resolution["n_phi"],
    ))
    print("FreeCAD conversion: 1 metre = 1000 millimetres")

    for theta_deg in range(0, 360, 45):
        theta = math.radians(theta_deg)
        point = ev007_point_m(theta, 0.0)
        normal = ev007_normal(theta, 0.0)
        print(
            "theta=%3d deg point_m=%s normal=%s"
            % (
                theta_deg,
                tuple(round(value, 6) for value in point),
                tuple(round(value, 6) for value in normal),
            )
        )

    d_free = SETTINGS["standoff_m"]
    d_interface = d_free + SETTINGS["liquid_thickness_m"]
    d_outer = d_interface + SETTINGS["backing_thickness_m"]
    print("Offsets from EV007: %.6f m, %.6f m, %.6f m" % (
        d_free,
        d_interface,
        d_outer,
    ))
    print("Preflight passed")


def freecad_log(App, message):
    text = str(message)
    try:
        App.Console.PrintMessage(text + "\n")
    except Exception:
        print(text)


def freecad_warning(App, message):
    text = "WARNING: " + str(message)
    try:
        App.Console.PrintWarning(text + "\n")
    except Exception:
        print(text)


def interpolate_wire(App, Part, points, periodic):
    """Create a one-edge B-spline wire with old/new FreeCAD API fallbacks."""
    if periodic and len(points) < 4:
        raise ValueError("A periodic section requires at least four points")
    if not periodic and len(points) < 2:
        raise ValueError("An open section requires at least two points")

    curve = Part.BSplineCurve()
    try:
        curve.interpolate(Points=points, PeriodicFlag=periodic)
    except TypeError:
        curve.interpolate(points, periodic)
    return Part.Wire(curve.toShape())


def make_closed_section_wire(App, Part, distance_m, phi, n_theta):
    points = [
        offset_vector_mm(
            App,
            2.0 * math.pi * index / n_theta,
            phi,
            distance_m,
        )
        for index in range(n_theta)
    ]
    return interpolate_wire(App, Part, points, periodic=True)


def make_open_section_wire(
    App,
    Part,
    distance_m,
    phi,
    theta_min,
    theta_max,
    point_count,
):
    points = []
    for index in range(point_count):
        fraction = index / float(point_count - 1)
        theta = theta_min + (theta_max - theta_min) * fraction
        points.append(offset_vector_mm(App, theta, phi, distance_m))
    return interpolate_wire(App, Part, points, periodic=False)


def make_loft(Part, sections, solid, closed):
    """Call Part.makeLoft across FreeCAD versions."""
    try:
        return Part.makeLoft(sections, solid, False, closed, 5)
    except TypeError:
        return Part.makeLoft(sections, solid, False, closed)


def make_triangle_face(Part, point_a, point_b, point_c):
    """Create one planar triangular face using broadly compatible Part APIs."""
    wire = Part.makePolygon([point_a, point_b, point_c, point_a])
    return Part.Face(wire)


def make_shell_compat(Part, faces):
    try:
        return Part.makeShell(faces)
    except (AttributeError, TypeError):
        return Part.Shell(faces)


def make_solid_compat(Part, shell):
    try:
        return Part.makeSolid(shell)
    except (AttributeError, TypeError):
        return Part.Solid(shell)


def build_faceted_enclosed_offset_solid(
    App,
    Part,
    distance_m,
    n_theta,
    n_phi,
    label,
):
    """Robust full-period fallback made from periodic triangular faces.

    This preserves every sampled EV007 offset point and closes both angular
    seams explicitly. It is less smooth than the B-spline loft, but avoids the
    periodic-loft incompatibilities present in some FreeCAD/OpenCascade builds.
    """
    grid = []
    for theta_index in range(n_theta):
        theta = 2.0 * math.pi * theta_index / n_theta
        row = []
        for phi_index in range(n_phi):
            phi = 2.0 * math.pi * phi_index / n_phi
            row.append(offset_vector_mm(App, theta, phi, distance_m))
        grid.append(row)

    faces = []
    for theta_index in range(n_theta):
        next_theta = (theta_index + 1) % n_theta
        for phi_index in range(n_phi):
            next_phi = (phi_index + 1) % n_phi
            point_00 = grid[theta_index][phi_index]
            point_10 = grid[next_theta][phi_index]
            point_01 = grid[theta_index][next_phi]
            point_11 = grid[next_theta][next_phi]

            # Vertex order gives outward-facing normals for the EV007
            # theta/phi parameterization used by this script.
            faces.append(make_triangle_face(Part, point_00, point_01, point_11))
            faces.append(make_triangle_face(Part, point_00, point_11, point_10))

    shell = make_shell_compat(Part, faces)
    solid = make_solid_compat(Part, shell)
    return extract_single_solid(Part, solid, label + " faceted fallback")


def build_faceted_periodic_band_surface(
    App,
    Part,
    distance_m,
    theta_min,
    theta_max,
    point_count,
    n_phi,
    label,
):
    """Robust triangular fallback for an open-theta, periodic-phi face band."""
    grid = []
    for theta_index in range(point_count):
        fraction = theta_index / float(point_count - 1)
        theta = theta_min + (theta_max - theta_min) * fraction
        row = []
        for phi_index in range(n_phi):
            phi = 2.0 * math.pi * phi_index / n_phi
            row.append(offset_vector_mm(App, theta, phi, distance_m))
        grid.append(row)

    faces = []
    for theta_index in range(point_count - 1):
        for phi_index in range(n_phi):
            next_phi = (phi_index + 1) % n_phi
            point_00 = grid[theta_index][phi_index]
            point_10 = grid[theta_index + 1][phi_index]
            point_01 = grid[theta_index][next_phi]
            point_11 = grid[theta_index + 1][next_phi]
            faces.append(make_triangle_face(Part, point_00, point_01, point_11))
            faces.append(make_triangle_face(Part, point_00, point_11, point_10))

    shell = make_shell_compat(Part, faces)
    if shell.isNull() or not shell.isValid() or shell.Area <= 0.0:
        raise RuntimeError("%s faceted fallback is invalid or zero-area" % label)
    return shell


def extract_single_solid(Part, shape, label):
    solids = list(shape.Solids)
    if len(solids) == 1:
        solid = solids[0]
    elif shape.ShapeType == "Shell" and shape.isClosed():
        solid = Part.Solid(shape)
    else:
        raise RuntimeError(
            "%s did not produce exactly one solid (found %d)"
            % (label, len(solids))
        )

    if solid.isNull() or not solid.isValid() or solid.Volume <= 0.0:
        raise RuntimeError("%s produced an invalid or zero-volume solid" % label)
    return solid


def build_enclosed_offset_solid(App, Part, distance_m, n_theta, n_phi, label):
    """Build a full-period faceted solid without any spline interpolation."""
    event = "%s: forced faceted construction; B-spline path disabled" % label
    BUILD_EVENTS.append(event)
    freecad_log(App, event)
    return build_faceted_enclosed_offset_solid(
        App,
        Part,
        distance_m,
        n_theta,
        n_phi,
        label,
    )


def build_enclosed_offset_solid_spline_unused(
    App,
    Part,
    distance_m,
    n_theta,
    n_phi,
    label,
):
    """Retained only as an inactive diagnostic path; never called in this file."""
    sections = [
        make_closed_section_wire(
            App,
            Part,
            distance_m,
            2.0 * math.pi * index / n_phi,
            n_theta,
        )
        for index in range(n_phi)
    ]

    first_error = None
    try:
        shape = make_loft(Part, sections, solid=True, closed=True)
        return extract_single_solid(Part, shape, label)
    except Exception as error:
        first_error = error

    # Reuse the exact first TopoShape. Recomputing at 2*pi can introduce a
    # floating-point seam mismatch that makes an otherwise correct solid fail
    # OpenCascade validity checks or split into multiple solids after Boolean
    # subtraction.
    closing_section = sections[0]
    try:
        shape = make_loft(
            Part,
            sections + [closing_section],
            solid=True,
            closed=False,
        )
        return extract_single_solid(Part, shape, label)
    except Exception as second_error:
        event = (
            "%s: periodic B-spline lofts failed; used closed triangular "
            "EV007 fallback. closed-loft error=%s; repeated-section error=%s"
            % (label, first_error, second_error)
        )
        BUILD_EVENTS.append(event)
        freecad_warning(App, event)
        return build_faceted_enclosed_offset_solid(
            App,
            Part,
            distance_m,
            n_theta,
            n_phi,
            label,
        )


def outer_shell(solid, label):
    shells = list(solid.Shells)
    if not shells:
        raise RuntimeError("%s has no boundary shell" % label)
    shell = max(shells, key=lambda item: item.Area)
    if shell.isNull() or not shell.isValid() or shell.Area <= 0.0:
        raise RuntimeError("%s has an invalid boundary shell" % label)
    return shell


def build_layer_volume(outer_solid, inner_solid, label):
    result = outer_solid.cut(inner_solid)
    try:
        result = result.removeSplitter()
    except Exception:
        pass

    solids = list(result.Solids)
    if len(solids) != 1:
        raise RuntimeError(
            "%s Boolean cut did not produce exactly one solid (found %d)"
            % (label, len(solids))
        )
    solid = solids[0]
    if solid.isNull() or not solid.isValid() or solid.Volume <= 0.0:
        raise RuntimeError("%s Boolean result is invalid or zero-volume" % label)
    return solid


def build_periodic_band_surface(
    App,
    Part,
    distance_m,
    theta_deg_range,
    n_theta,
    n_phi,
    label,
):
    theta_min = math.radians(theta_deg_range[0])
    theta_max = math.radians(theta_deg_range[1])
    span_fraction = (theta_max - theta_min) / (2.0 * math.pi)
    point_count = max(6, int(round(n_theta * span_fraction)) + 1)

    event = "%s: forced faceted construction; B-spline path disabled" % label
    BUILD_EVENTS.append(event)
    freecad_log(App, event)
    return build_faceted_periodic_band_surface(
        App,
        Part,
        distance_m,
        theta_min,
        theta_max,
        point_count,
        n_phi,
        label,
    )


def build_periodic_band_surface_spline_unused(
    App,
    Part,
    distance_m,
    theta_deg_range,
    n_theta,
    n_phi,
    label,
):
    """Retained only as an inactive diagnostic path; never called in this file."""
    theta_min = math.radians(theta_deg_range[0])
    theta_max = math.radians(theta_deg_range[1])
    span_fraction = (theta_max - theta_min) / (2.0 * math.pi)
    point_count = max(6, int(round(n_theta * span_fraction)) + 1)

    sections = [
        make_open_section_wire(
            App,
            Part,
            distance_m,
            2.0 * math.pi * index / n_phi,
            theta_min,
            theta_max,
            point_count,
        )
        for index in range(n_phi)
    ]

    first_error = None
    try:
        band = make_loft(Part, sections, solid=False, closed=True)
    except Exception as error:
        first_error = error
        # Use the identical first wire to avoid a numerical 0/2*pi seam gap.
        closing_section = sections[0]
        try:
            band = make_loft(
                Part,
                sections + [closing_section],
                solid=False,
                closed=False,
            )
        except Exception as second_error:
            event = (
                "%s: periodic B-spline surface lofts failed; used triangular "
                "band fallback. closed-loft error=%s; repeated-section error=%s"
                % (label, first_error, second_error)
            )
            BUILD_EVENTS.append(event)
            freecad_warning(App, event)
            return build_faceted_periodic_band_surface(
                App,
                Part,
                distance_m,
                theta_min,
                theta_max,
                point_count,
                n_phi,
                label,
            )

    if band.isNull() or not band.isValid() or band.Area <= 0.0:
        raise RuntimeError("%s produced an invalid or zero-area surface" % label)
    return band


def unique_document_name(App, base_name):
    existing = set(App.listDocuments().keys())
    if base_name not in existing:
        return base_name
    index = 2
    while "%s_%d" % (base_name, index) in existing:
        index += 1
    return "%s_%d" % (base_name, index)


def add_shape_object(
    doc,
    group,
    name,
    label,
    shape,
    boundary_role,
    color,
    transparency,
    gui_up,
):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "BoundaryRole", "Tomahawk")
    obj.BoundaryRole = boundary_role
    obj.addProperty("App::PropertyString", "EngineeringStatus", "Tomahawk")
    obj.EngineeringStatus = "SCREENING_GEOMETRY_NOT_SOLVER_QUALIFIED"
    group.addObject(obj)

    if gui_up:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.LineColor = (0.15, 0.15, 0.15)
        obj.ViewObject.Transparency = transparency
        try:
            obj.ViewObject.DisplayMode = "Flat Lines"
        except Exception:
            pass
    return obj


def shape_statistics(shape):
    bounds = shape.BoundBox
    return {
        "shape_type": shape.ShapeType,
        "valid": bool(shape.isValid()),
        "closed": bool(shape.isClosed()),
        "solid_count": len(shape.Solids),
        "shell_count": len(shape.Shells),
        "face_count": len(shape.Faces),
        "area_mm2": float(shape.Area),
        "volume_mm3": float(shape.Volume),
        "bounds_mm": {
            "x_min": float(bounds.XMin),
            "x_max": float(bounds.XMax),
            "y_min": float(bounds.YMin),
            "y_max": float(bounds.YMax),
            "z_min": float(bounds.ZMin),
            "z_max": float(bounds.ZMax),
        },
    }


def export_step_object(Part, obj, path):
    Part.export([obj], str(path))
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("STEP export did not create %s" % path)


def build_freecad_model(App, Part, args):
    quality = args.quality
    validate_settings(quality)
    resolution = QUALITY_LEVELS[quality]
    n_theta = resolution["n_theta"]
    n_phi = resolution["n_phi"]
    gui_up = bool(getattr(App, "GuiUp", False))

    output_directory = Path(args.out).expanduser() if args.out else default_output_directory()
    output_directory.mkdir(parents=True, exist_ok=True)

    document_name = unique_document_name(App, DOCUMENT_BASENAME)
    doc = App.newDocument(document_name)
    reference_group = doc.addObject("App::DocumentObjectGroup", "Reference_Surfaces")
    volume_group = doc.addObject("App::DocumentObjectGroup", "Physical_Volumes")
    face_group = doc.addObject("App::DocumentObjectGroup", "Boundary_Face_Sets")
    metadata_group = doc.addObject("App::DocumentObjectGroup", "Model_Metadata")

    standoff = SETTINGS["standoff_m"]
    liquid_thickness = SETTINGS["liquid_thickness_m"]
    backing_thickness = SETTINGS["backing_thickness_m"]
    d_free = standoff
    d_interface = standoff + liquid_thickness
    d_outer = d_interface + backing_thickness

    started = time.time()
    objects = {}
    freecad_log(
        App,
        "Building %s at %s quality (%d x %d sections)..."
        % (document_name, quality, n_theta, n_phi),
    )
    freecad_log(App, "All source dimensions are metres; FreeCAD geometry is millimetres.")

    try:
        freecad_log(App, "1/9  Building EV007 plasma-boundary reference...")
        ev007_core = build_enclosed_offset_solid(
            App, Part, 0.0, n_theta, n_phi, "EV007 reference"
        )
        objects["EV007_plasma_boundary"] = add_shape_object(
            doc,
            reference_group,
            "EV007_Plasma_Boundary",
            "EV007 Plasma Boundary (reference only)",
            outer_shell(ev007_core, "EV007 reference"),
            "plasma_boundary_reference_not_a_wall",
            (0.90, 0.18, 0.12),
            82,
            gui_up,
        )

        freecad_log(App, "2/9  Building liquid free surface...")
        free_surface_core = build_enclosed_offset_solid(
            App, Part, d_free, n_theta, n_phi, "Liquid free surface"
        )
        objects["liquid_free_surface"] = add_shape_object(
            doc,
            reference_group,
            "Liquid_Free_Surface",
            "Liquid Free Surface",
            outer_shell(free_surface_core, "Liquid free surface"),
            "plasma_facing_liquid_surface",
            (0.16, 0.62, 0.92),
            55,
            gui_up,
        )

        freecad_log(App, "3/9  Building liquid-solid interface...")
        interface_core = build_enclosed_offset_solid(
            App, Part, d_interface, n_theta, n_phi, "Liquid-solid interface"
        )
        objects["liquid_solid_interface"] = add_shape_object(
            doc,
            reference_group,
            "Liquid_Solid_Interface",
            "Liquid-Solid Interface",
            outer_shell(interface_core, "Liquid-solid interface"),
            "conjugate_heat_transfer_interface",
            (0.18, 0.82, 0.72),
            62,
            gui_up,
        )

        freecad_log(App, "4/9  Building outer coolant interface...")
        outer_core = build_enclosed_offset_solid(
            App, Part, d_outer, n_theta, n_phi, "Outer coolant interface"
        )
        objects["outer_coolant_interface"] = add_shape_object(
            doc,
            reference_group,
            "Outer_Coolant_Interface",
            "Outer Coolant Interface",
            outer_shell(outer_core, "Outer coolant interface"),
            "outer_backing_and_assumed_support_interface",
            (0.72, 0.76, 0.82),
            70,
            gui_up,
        )

        freecad_log(App, "5/9  Cutting liquid-metal volume...")
        liquid_volume = build_layer_volume(
            interface_core,
            free_surface_core,
            "Liquid-metal volume",
        )
        objects["liquid_metal_volume"] = add_shape_object(
            doc,
            volume_group,
            "Liquid_Metal_Volume",
            "Liquid Metal Volume (screening assumption)",
            liquid_volume,
            "mhd_fluid_domain",
            (0.10, 0.45, 0.92),
            68,
            gui_up,
        )

        freecad_log(App, "6/9  Cutting structural-backing volume...")
        backing_volume = build_layer_volume(
            outer_core,
            interface_core,
            "Structural-backing volume",
        )
        objects["structural_backing_volume"] = add_shape_object(
            doc,
            volume_group,
            "Structural_Backing_Volume",
            "Structural Backing Volume (screening assumption)",
            backing_volume,
            "thermomechanical_solid_domain",
            (0.62, 0.66, 0.72),
            76,
            gui_up,
        )

        freecad_log(App, "7/9  Building inlet face set...")
        inlet_band = build_periodic_band_surface(
            App,
            Part,
            d_free,
            SETTINGS["inlet_theta_deg_range"],
            n_theta,
            n_phi,
            "Inlet face set",
        )
        objects["inlet_face_set"] = add_shape_object(
            doc,
            face_group,
            "Inlet_Face_Set",
            "Inlet Face Set (assumed)",
            inlet_band,
            "liquid_inlet_assumption",
            (0.12, 0.88, 0.24),
            5,
            gui_up,
        )

        freecad_log(App, "8/9  Building outlet face set...")
        outlet_band = build_periodic_band_surface(
            App,
            Part,
            d_free,
            SETTINGS["outlet_theta_deg_range"],
            n_theta,
            n_phi,
            "Outlet face set",
        )
        objects["outlet_face_set"] = add_shape_object(
            doc,
            face_group,
            "Outlet_Face_Set",
            "Outlet Face Set (assumed)",
            outlet_band,
            "liquid_outlet_assumption",
            (0.98, 0.58, 0.08),
            5,
            gui_up,
        )

        freecad_log(App, "9/9  Building laser-footprint face set...")
        laser_band = build_periodic_band_surface(
            App,
            Part,
            d_free,
            SETTINGS["laser_footprint_theta_deg_range"],
            n_theta,
            n_phi,
            "Laser footprint face set",
        )
        objects["laser_footprint_face_set"] = add_shape_object(
            doc,
            face_group,
            "Laser_Footprint_Face_Set",
            "Laser Footprint Face Set (assumed)",
            laser_band,
            "transient_surface_heat_flux_assumption",
            (0.95, 0.08, 0.42),
            0,
            gui_up,
        )

        metadata = doc.addObject("App::FeaturePython", "Geometry_Assumptions")
        metadata.Label = "Geometry Assumptions — read before simulation"
        metadata.addProperty("App::PropertyString", "Status", "Tomahawk")
        metadata.Status = "SCREENING_GEOMETRY_NOT_SOLVER_QUALIFIED"
        metadata.addProperty("App::PropertyString", "SourceReference", "Tomahawk")
        metadata.SourceReference = "EV007 analytic plasma boundary"
        metadata.addProperty("App::PropertyString", "LengthUnits", "Tomahawk")
        metadata.LengthUnits = "FreeCAD geometry: mm; source dimensions: m"
        metadata.addProperty("App::PropertyString", "Quality", "Tomahawk")
        metadata.Quality = quality
        metadata.addProperty("App::PropertyString", "MaterialWarning", "Tomahawk")
        metadata.MaterialWarning = (
            "Material labels are assumptions; RAFM versus ODS-FeCrAl remains a design choice"
        )
        metadata_group.addObject(metadata)

        doc.recompute()

        fcstd_path = output_directory / "Tomahawk_Liquid_Wall.FCStd"
        doc.saveAs(str(fcstd_path))
        freecad_log(App, "Saved FreeCAD model: %s" % fcstd_path)

        exported_files = [fcstd_path.name]
        do_step_export = bool(SETTINGS["export_step"]) and not args.no_step
        if do_step_export:
            freecad_log(App, "Exporting individual STEP files...")
            for export_name, obj in objects.items():
                step_path = output_directory / (export_name + ".step")
                export_step_object(Part, obj, step_path)
                exported_files.append(step_path.name)

            combined_path = output_directory / "Tomahawk_Liquid_Wall_All.step"
            Part.export(list(objects.values()), str(combined_path))
            if not combined_path.exists() or combined_path.stat().st_size == 0:
                raise RuntimeError("Combined STEP export was not created")
            exported_files.append(combined_path.name)

        object_statistics = {
            name: shape_statistics(obj.Shape) for name, obj in objects.items()
        }
        manifest = {
            "schema_version": "TOMAHAWK-LW-FREECAD-0.2",
            "status": "SCREENING_GEOMETRY_NOT_SOLVER_QUALIFIED",
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "freecad_version": ".".join(str(value) for value in App.Version()[:3]),
            "document_name": document_name,
            "source_reference_surface": "EV007 analytic plasma-boundary formula",
            "source_length_unit": "metre",
            "freecad_and_step_length_unit": "millimetre",
            "metres_to_millimetres": M_TO_MM,
            "quality": quality,
            "resolution": resolution,
            "settings_used": SETTINGS,
            "offsets_from_EV007_m": {
                "liquid_free_surface": d_free,
                "liquid_solid_interface": d_interface,
                "outer_coolant_interface": d_outer,
            },
            "objects": object_statistics,
            "files": exported_files + ["liquid_wall_geometry_manifest.json"],
            "solver_readiness": {
                "cad_solids_created_and_checked": True,
                "named_screening_face_sets_created": True,
                "periodic_sector_face_pairs_created": False,
                "flow_manifolds_physically_modelled": False,
                "material_cards_assigned": False,
                "mhd_or_thermal_results_computed": False,
            },
            "warnings": [
                "EV007 is a plasma boundary, not a first-wall measurement.",
                "Standoff, thicknesses, flow topology, face bands, and material labels are assumptions.",
                "PF coil labels are not interpreted as liquid inlet/outlet manifolds.",
                "A valid CAD Boolean does not establish thermal, MHD, neutronic, or structural survivability.",
            ],
            "build_events": list(BUILD_EVENTS),
            "elapsed_seconds": time.time() - started,
        }
        manifest_path = output_directory / "liquid_wall_geometry_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        exported_files.append(manifest_path.name)

        if gui_up:
            try:
                import FreeCADGui as Gui

                Gui.activeDocument().activeView().viewAxonometric()
                Gui.activeDocument().activeView().fitAll()
            except Exception as error:
                freecad_warning(App, "Model built, but automatic view fitting failed: %s" % error)

        freecad_log(App, "")
        freecad_log(App, "BUILD COMPLETE")
        freecad_log(App, "Output folder: %s" % output_directory)
        freecad_log(App, "FCStd model: %s" % fcstd_path)
        freecad_log(App, "Elapsed time: %.1f seconds" % (time.time() - started))
        freecad_warning(
            App,
            "This is screening geometry with placeholder dimensions and is not yet solver-qualified.",
        )
        return doc, output_directory

    except Exception:
        # Preserve whatever was successfully created so the failure can be inspected.
        partial_path = output_directory / "Tomahawk_Liquid_Wall_PARTIAL.FCStd"
        error_log_path = output_directory / "liquid_wall_geometry_error.log"
        error_text = (
            "Tomahawk liquid-wall FreeCAD build failure\n"
            "Generated UTC: %s\n"
            "FreeCAD version: %s\n\n%s"
            % (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ".".join(str(value) for value in App.Version()[:3]),
                traceback.format_exc(),
            )
        )
        try:
            with error_log_path.open("w", encoding="utf-8") as handle:
                handle.write(error_text)
            freecad_warning(App, "Error log saved: %s" % error_log_path)
        except Exception:
            pass
        try:
            doc.recompute()
            doc.saveAs(str(partial_path))
            freecad_warning(App, "Partial model saved for inspection: %s" % partial_path)
        except Exception:
            pass
        raise


def main():
    args = parse_arguments()
    if args.preflight:
        run_preflight(args.quality)
        return

    try:
        import FreeCAD as App
        import Part
    except ImportError as error:
        raise SystemExit(
            "FreeCAD modules were not found. Open this script from FreeCAD, use "
            "FreeCADCmd, or run with --preflight only. Original error: %s" % error
        )

    try:
        build_freecad_model(App, Part, args)
    except Exception as error:
        try:
            App.Console.PrintError("LIQUID-WALL BUILD FAILED: %s\n" % error)
            App.Console.PrintError(traceback.format_exc() + "\n")
        except Exception:
            traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
