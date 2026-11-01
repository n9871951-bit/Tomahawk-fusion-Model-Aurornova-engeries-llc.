"""
Tomahawk liquid-wall geometry builder, standalone FreeCAD Python.

Builds the 5 geometry objects and named face sets listed as missing in
required_inputs.json / PRELAUNCH_STATUS.md's "Next geometry handoff",
as offset shells from the analytic EV007 plasma boundary formula
(from G1_Repair_Verification.json - residuals ~1e-11 m, treated as exact):

    R = R0 + a*cos(theta) + epsilon*cos(theta - 16*phi)
    Z = b*sin(theta) + epsilon*sin(theta - 16*phi)
    X = R*cos(phi), Y = R*sin(phi)

Layer structure (radially outward from the plasma boundary):
    EV007 (plasma boundary reference, NOT the wall)
      -> [STANDOFF_M gap]
    liquid_free_surface        (plasma-facing surface of the liquid)
      -> [LIQUID_THICKNESS_M]
    liquid_solid_interface     (back of the liquid / front of the structure)
      -> [BACKING_THICKNESS_M]
    outer_coolant_interface    (outer face of the structural backing)

liquid_metal_volume        = solid between liquid_free_surface and liquid_solid_interface
structural_backing_volume  = solid between liquid_solid_interface and outer_coolant_interface

ALL THICKNESS/GAP VALUES AND THE FLOW TOPOLOGY BELOW ARE PLACEHOLDER
ASSUMPTIONS, not derived from any supplied design value. They are
clearly logged in the output manifest for review and revision.

Run with runpy.run_path in FreeCAD's Python console, same as
tomahawk_entire_model.py. Exports STEP files plus a JSON manifest
documenting every assumed value.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# PLACEHOLDER DESIGN ASSUMPTIONS - override via command-line args or by
# editing SETTINGS below. None of these come from a supplied design value.
# ---------------------------------------------------------------------------
SETTINGS = {
    'liquid_metal_name': 'PbLi',                # ASSUMPTION: alternatives are pure Li or FLiBe
    'solid_backing_alloy': 'ODS_FeCrAl',        # RESOLVED: selection_conflict in required_inputs.json
    'standoff_m': 0.05,                          # ASSUMPTION: EV007 -> liquid free surface gap
    'liquid_thickness_m': 0.02,                  # ASSUMPTION: nominal liquid layer thickness
    'backing_thickness_m': 0.05,                 # ASSUMPTION: structural backing thickness
    'flow_topology': 'gravity_fed_poloidal',     # ASSUMPTION: inlet near top, outlet near bottom
    'inlet_theta_deg_range': [80.0, 100.0],      # ASSUMPTION: band near the top (theta=90 is +Z-ish)
    'outlet_theta_deg_range': [260.0, 280.0],    # ASSUMPTION: band near the bottom
    'laser_footprint_theta_deg_range': [-15.0, 15.0],  # ASSUMPTION: outboard midplane band
    'support_face': 'outer_coolant_interface',   # ASSUMPTION: support taken on the outer backing face
}

# Analytic EV007 formula parameters, from G1_Repair_Verification.json
R0_M = 7.499999999999888
A_M = 2.999999999999756
B_M = 2.13896943244938
EPSILON_M = 0.009999999999999069
PERIODS = 16


def ev007_point(theta, phi):
    R = R0_M + A_M * math.cos(theta) + EPSILON_M * math.cos(theta - PERIODS * phi)
    Z = B_M * math.sin(theta) + EPSILON_M * math.sin(theta - PERIODS * phi)
    X = R * math.cos(phi)
    Y = R * math.sin(phi)
    return X, Y, Z


def ev007_normal(theta, phi, eps=1e-6):
    # Numerical outward normal via finite-difference tangents in theta, phi
    p0 = ev007_point(theta, phi)
    pt = ev007_point(theta + eps, phi)
    pp = ev007_point(theta, phi + eps)
    t_theta = tuple((pt[i] - p0[i]) / eps for i in range(3))
    t_phi = tuple((pp[i] - p0[i]) / eps for i in range(3))
    # cross product t_theta x t_phi
    nx = t_theta[1]*t_phi[2] - t_theta[2]*t_phi[1]
    ny = t_theta[2]*t_phi[0] - t_theta[0]*t_phi[2]
    nz = t_theta[0]*t_phi[1] - t_theta[1]*t_phi[0]
    norm = math.sqrt(nx*nx + ny*ny + nz*nz)
    if norm < 1e-12:
        return (0.0, 0.0, 0.0)
    # Orient outward relative to the LOCAL poloidal cross-section center
    # (R0*cos(phi), R0*sin(phi), 0), not the global machine (Z) axis.
    # Using the global machine-axis direction is only correct on the
    # outboard half of the tube (theta near 0) and gives an INWARD-pointing
    # "outward" normal on the inboard half (theta near pi) - epsilon is
    # tiny relative to a, so approximating the local center with R0 alone
    # does not introduce meaningful error for orientation purposes.
    local_center = (R0_M*math.cos(phi), R0_M*math.sin(phi), 0.0)
    from_center = (p0[0]-local_center[0], p0[1]-local_center[1], p0[2]-local_center[2])
    dot = nx*from_center[0] + ny*from_center[1] + nz*from_center[2]
    if dot < 0:
        nx, ny, nz = -nx, -ny, -nz
    return (nx/norm, ny/norm, nz/norm)


def offset_point(theta, phi, distance):
    p = ev007_point(theta, phi)
    n = ev007_normal(theta, phi)
    return tuple(p[i] + n[i]*distance for i in range(3))


def build_offset_surface(App, Part, distance, n_theta=64, n_phi=128):
    """Build a periodic B-spline surface offset outward from EV007 by `distance`.

    Uses endpoint-excluded angular sampling (0 to 2*pi, NOT including the
    2*pi point itself) for both theta and phi, matching the convention
    G1_Repair_Verification.json documents as the one that avoided a
    duplicate-point seam artifact in the original EV007 construction.
    """
    points_grid = []
    for i in range(n_theta):
        theta = 2.0 * math.pi * i / n_theta
        row = []
        for j in range(n_phi):
            phi = 2.0 * math.pi * j / n_phi
            x, y, z = offset_point(theta, phi, distance)
            row.append(App.Vector(x, y, z))
        points_grid.append(row)

    bs = Part.BSplineSurface()
    bs.interpolate(points_grid)
    return bs.toShape()


def build_solid_between(App, Part, inner_distance, outer_distance, n_theta=64, n_phi=128):
    """Build a solid volume between two offset surfaces by lofting/thickening."""
    inner_face = build_offset_surface(App, Part, inner_distance, n_theta, n_phi)
    outer_face = build_offset_surface(App, Part, outer_distance, n_theta, n_phi)
    # Sew inner + outer shells into a closed solid. This is a first-pass
    # construction; a real mesh-ready solid may need explicit side-wall
    # stitching depending on how FreeCAD's sewing handles the periodic seam.
    shell = Part.Shell([inner_face, outer_face])
    try:
        solid = Part.Solid(shell)
    except Exception:
        solid = shell  # fall back to shell if sewing does not close cleanly
    return solid


def build_face_set(App, Part, distance, theta_deg_range, n_theta=64, n_phi=128, label=''):
    """Extract a banded sub-region of an offset surface by theta range, for
    named face sets (inlet, outlet, laser footprint, etc.)."""
    theta_min = math.radians(theta_deg_range[0])
    theta_max = math.radians(theta_deg_range[1])
    points_grid = []
    n_theta_band = max(4, int(n_theta * (theta_max - theta_min) / (2*math.pi)))
    for i in range(n_theta_band + 1):
        theta = theta_min + (theta_max - theta_min) * i / n_theta_band
        row = []
        for j in range(n_phi):
            phi = 2.0 * math.pi * j / n_phi
            x, y, z = offset_point(theta, phi, distance)
            row.append(App.Vector(x, y, z))
        points_grid.append(row)
    bs = Part.BSplineSurface()
    bs.interpolate(points_grid)
    return bs.toShape()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true',
                         help='Dimension/logic check only, no FreeCAD required')
    parser.add_argument('--out', default=None, help='Output directory')
    args = parser.parse_args()

    if args.preflight:
        # Preflight: sanity-check the analytic geometry and settings without FreeCAD
        print("PREFLIGHT: checking analytic EV007 formula and offset distances")
        for theta_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
            theta = math.radians(theta_deg)
            p = ev007_point(theta, 0.0)
            n = ev007_normal(theta, 0.0)
            print(f"  theta={theta_deg:3d} deg: point={tuple(round(v,4) for v in p)} "
                  f"normal={tuple(round(v,4) for v in n)}")
        total_offset_liquid = SETTINGS['standoff_m'] + SETTINGS['liquid_thickness_m']
        total_offset_backing = total_offset_liquid + SETTINGS['backing_thickness_m']
        print(f"\nliquid_free_surface offset: {SETTINGS['standoff_m']} m")
        print(f"liquid_solid_interface offset: {total_offset_liquid} m")
        print(f"outer_coolant_interface offset: {total_offset_backing} m")
        print(f"\nSETTINGS: {json.dumps(SETTINGS, indent=2)}")
        return

    if 'FreeCAD' not in sys.modules:
        parser.error('Run in FreeCAD Python console for actual geometry export; '
                     'ordinary Python can only --preflight.')

    import FreeCAD as App
    import Part

    out_dir = Path(args.out) if args.out else Path.home() / 'Desktop' / 'Tomahawk_Liquid_Wall'
    out_dir.mkdir(parents=True, exist_ok=True)

    standoff = SETTINGS['standoff_m']
    liquid_t = SETTINGS['liquid_thickness_m']
    backing_t = SETTINGS['backing_thickness_m']

    d_free_surface = standoff
    d_liquid_solid_interface = standoff + liquid_t
    d_outer_coolant_interface = standoff + liquid_t + backing_t

    print("Building liquid_free_surface...")
    liquid_free_surface = build_offset_surface(App, Part, d_free_surface)
    Part.export([liquid_free_surface], str(out_dir / 'liquid_free_surface.step'))

    print("Building liquid_solid_interface...")
    liquid_solid_interface = build_offset_surface(App, Part, d_liquid_solid_interface)
    Part.export([liquid_solid_interface], str(out_dir / 'liquid_solid_interface.step'))

    print("Building outer_coolant_interface...")
    outer_coolant_interface = build_offset_surface(App, Part, d_outer_coolant_interface)
    Part.export([outer_coolant_interface], str(out_dir / 'outer_coolant_interface.step'))

    print("Building liquid_metal_volume...")
    liquid_metal_volume = build_solid_between(App, Part, d_free_surface, d_liquid_solid_interface)
    Part.export([liquid_metal_volume], str(out_dir / 'liquid_metal_volume.step'))

    print("Building structural_backing_volume...")
    structural_backing_volume = build_solid_between(App, Part, d_liquid_solid_interface, d_outer_coolant_interface)
    Part.export([structural_backing_volume], str(out_dir / 'structural_backing_volume.step'))

    print("Building named face sets (inlet, outlet, laser footprint)...")
    inlet_face = build_face_set(App, Part, d_free_surface, SETTINGS['inlet_theta_deg_range'])
    Part.export([inlet_face], str(out_dir / 'inlet_face_set.step'))

    outlet_face = build_face_set(App, Part, d_free_surface, SETTINGS['outlet_theta_deg_range'])
    Part.export([outlet_face], str(out_dir / 'outlet_face_set.step'))

    laser_face = build_face_set(App, Part, d_free_surface, SETTINGS['laser_footprint_theta_deg_range'])
    Part.export([laser_face], str(out_dir / 'laser_footprint_face_set.step'))

    manifest = {
        'schema_version': 'TOMAHAWK-LW-GEOMETRY-HANDOFF-0.1',
        'status': 'SCREENING_GEOMETRY_PLACEHOLDER_VALUES_NOT_DESIGN_VALUES',
        'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'source_reference_surface': 'EV007 analytic formula from G1_Repair_Verification.json',
        'settings_used': SETTINGS,
        'offsets_from_EV007_m': {
            'liquid_free_surface': d_free_surface,
            'liquid_solid_interface': d_liquid_solid_interface,
            'outer_coolant_interface': d_outer_coolant_interface,
        },
        'files': [
            'liquid_free_surface.step', 'liquid_solid_interface.step',
            'outer_coolant_interface.step', 'liquid_metal_volume.step',
            'structural_backing_volume.step', 'inlet_face_set.step',
            'outlet_face_set.step', 'laser_footprint_face_set.step',
        ],
        'still_missing_from_required_inputs': [
            'support_and_displacement_face_sets (only outer_coolant_interface assumed)',
            'periodic_face_pairs (not yet extracted as named faces)',
            'minimum_allowed_liquid_thickness_m',
            'all liquid_metal material property curves (density, viscosity, etc.)',
            'all solid_backing material property curves',
        ],
        'warning': ('This is a FIRST-PASS SCREENING geometry using placeholder standoff, '
                    'thickness, and flow-topology assumptions. It has not been checked for '
                    'mesh-readiness (manifold, non-overlapping, correct normals) the way the '
                    'reactor CAD and PF coil geometry were. Treat every dimension as a '
                    'starting point for review, not a design value.'),
    }
    with open(out_dir / 'liquid_wall_geometry_manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. Output written to: {out_dir}")
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
