#!/usr/bin/env python3
"""Build a geometry-preserving laser-drive control input from CAD-A2.

The CAD concept file supplies port geometry only.  This module turns that
geometry into an auditable input template for a future 3-D ray-trace,
radiation-hydrodynamics, rotating-MHD, and burn calculation.

It deliberately does not invent laser energy, absorption, focal position,
arrival time, angular momentum, compression ratio, or fusion-power gain.  The
four requested control ideas are represented as explicit equations and
required unknowns.  Until those unknowns are populated by a validated solver,
the controls are not applied to the existing fusion-power screen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = Path(
    "/workspace/scratch/9740310843df/tomahawk_full_cad/preflight/"
    "CAD_A2_20260830_214318_qb5q9bp6/whole_model_definition.json"
)
DEFAULT_RIPPLE = ROOT / "phase2_20260910/power_control_preflight/POWER_CONTROL_PREFLIGHT.json"
DEFAULT_OUT = ROOT / "phase2_20260910/laser_coupling"
EXPECTED_LASERS = 16
EXPECTED_AZIMUTH_STEP_DEG = 360.0 / EXPECTED_LASERS
TARGET_REFERENCE_XYZ_M = np.zeros(3)
SPEED_OF_LIGHT_M_S = 299_792_458.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_vector(value, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite 3-vector")
    return vector


def rotate_z(point: np.ndarray, angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return point @ np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])


def resolve_model(path: Path | None) -> Path:
    candidates = []
    if path is not None:
        candidates.append(path)
    candidates.extend(
        [
            DEFAULT_MODEL,
            ROOT / "whole_model_definition.json",
            ROOT / "cad_source/whole_model_definition.json",
            ROOT.parent / "tomahawk_full_cad/preflight/CAD_A2_20260830_214318_qb5q9bp6/whole_model_definition.json",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = "\n".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"CAD whole-model definition not found. Searched:\n{searched}")


def read_ripple(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {
            "available": False,
            "status": "RIPPLE_RESULT_NOT_SUPPLIED",
            "tf_ripple_screen_pass": False,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    strict_gate = data.get("strict_tf_ripple_gate")
    if strict_gate is not None:
        return {
            "available": True,
            "source_path": str(path.resolve()),
            "source_sha256": sha256(path),
            "status": data.get("status"),
            "tf_branch": strict_gate.get(
                "controlling_screening_branch", "STRICT_PROJECT_TF_RIPPLE_PREFLIGHT"
            ),
            "tf_coil_count": strict_gate.get("controlling_screening_coil_count"),
            "edge_ripple_percent": strict_gate.get(
                "controlling_screening_edge_ripple_percent"
            ),
            "threshold_percent": strict_gate.get("limit_percent"),
            "tf_ripple_screen_pass": bool(strict_gate.get("tf_edge_ripple_screen_pass", False)),
            "authoritative_native_tf_source": bool(strict_gate.get("native_tf_mgrid_present", False)),
        }
    gates = data.get("gates", {})
    ripple = data.get("ripple", {})
    edge = ripple.get("outboard_edge", {}).get("tf_only", {})
    reported_pass = bool(
        gates.get("tf_ripple_screen_pass", ripple.get("tf_ripple_screen_pass", False))
    )
    return {
        "available": True,
        "source_path": str(path.resolve()),
        "source_sha256": sha256(path),
        "status": data.get("status"),
        "tf_branch": data.get("tf_source", {}).get("geometry_branch"),
        "tf_coil_count": data.get("tf_source", {}).get("coil_count"),
        "edge_ripple_percent": edge.get("ripple_percent"),
        "threshold_percent": ripple.get("threshold_percent"),
        "reported_tf_ripple_screen_pass": reported_pass,
        "tf_ripple_screen_pass": False,
        "authoritative_native_tf_source": False,
        "strict_gate_reason": "Only the current strict project preflight can authorize downstream changes",
    }


def extract_laser_ports(model: dict) -> list[dict]:
    ports = [port for port in model.get("ports", []) if port.get("kind") == "LASER"]
    if len(ports) != EXPECTED_LASERS:
        raise ValueError(f"Expected {EXPECTED_LASERS} LASER ports, found {len(ports)}")

    records = []
    for index, port in enumerate(sorted(ports, key=lambda item: float(item["phi_deg"]))):
        start = finite_vector(port["start"], f"LASER_{index + 1:02d}.start")
        end = finite_vector(port["end"], f"LASER_{index + 1:02d}.end")
        outward = finite_vector(port["normal"], f"LASER_{index + 1:02d}.normal")
        direction = end - start
        direction_norm = np.linalg.norm(direction)
        normal_norm = np.linalg.norm(outward)
        if direction_norm == 0.0 or normal_norm == 0.0:
            raise ValueError(f"LASER_{index + 1:02d} has a zero-length direction")
        outward = outward / normal_norm
        direction = direction / direction_norm
        # The CAD normal points from the chamber-side start toward the outer
        # end.  A laser entering the chamber propagates in the opposite sense.
        inward_k = -outward
        lever = np.cross(start - TARGET_REFERENCE_XYZ_M, inward_k)
        records.append(
            {
                "beam_id": f"LASER_{index + 1:02d}",
                "azimuth_deg": float(port["phi_deg"]),
                "poloidal_angle_deg": float(port.get("theta_deg", 0.0)),
                "start_xyz_m": start.tolist(),
                "end_xyz_m": end.tolist(),
                "outward_normal_hat": outward.tolist(),
                "inward_propagation_hat": inward_k.tolist(),
                "centerline_direction_hat": direction.tolist(),
                "length_m": float(port["length_m"]),
                "bore_radius_m": float(port["bore_m"]),
                "wall_m": float(port["wall_m"]),
                "port_origin_geometric_lever_arm_m": float(np.linalg.norm(lever)),
                "port_origin_geometric_lever_vector_m": lever.tolist(),
                "lever_arm_interpretation": (
                    "geometry-only reference about chamber origin; not the physical "
                    "laser torque lever arm until an absorption point is supplied"
                ),
            }
        )
    return records


def array_geometry_audit(model_path: Path, model: dict, beams: list[dict]) -> dict:
    azimuths = np.asarray([beam["azimuth_deg"] for beam in beams], dtype=float)
    wrapped_deltas = np.mod(np.diff(np.r_[azimuths, azimuths[0] + 360.0]), 360.0)
    normal_norm_errors = [
        abs(np.linalg.norm(beam["outward_normal_hat"]) - 1.0) for beam in beams
    ]
    return {
        "schema_version": "TOMAHAWK-LASER-GEOMETRY-AUDIT-0.1",
        "status": "CAD_LASER_GEOMETRY_EXTRACTED",
        "source": {
            "path": str(model_path),
            "sha256": sha256(model_path),
            "model_version": model.get("version"),
            "dimension_units": model.get("dimension_units"),
            "scope": model.get("scope"),
            "physics_status": model.get("physics_status"),
            "authority": model.get("authority"),
        },
        "geometry_invariant": True,
        "laser_port_count": len(beams),
        "azimuth_deg": azimuths.tolist(),
        "azimuth_spacing": {
            "expected_step_deg": EXPECTED_AZIMUTH_STEP_DEG,
            "min_step_deg": float(np.min(wrapped_deltas)),
            "max_step_deg": float(np.max(wrapped_deltas)),
            "mean_step_deg": float(np.mean(wrapped_deltas)),
            "std_step_deg": float(np.std(wrapped_deltas)),
            "max_abs_step_error_deg": float(
                np.max(np.abs(wrapped_deltas - EXPECTED_AZIMUTH_STEP_DEG))
            ),
            "uniform_azimuth_indexing_pass": bool(
                np.max(np.abs(wrapped_deltas - EXPECTED_AZIMUTH_STEP_DEG)) <= 1.0e-9
            ),
        },
        "normalization": {
            "max_normal_norm_error": float(max(normal_norm_errors)),
            "pass": bool(max(normal_norm_errors) <= 1.0e-12),
        },
        "port_geometry": beams,
        "reference_target_xyz_m": TARGET_REFERENCE_XYZ_M.tolist(),
        "reference_lever_arm_range_m": {
            "min": float(min(beam["port_origin_geometric_lever_arm_m"] for beam in beams)),
            "max": float(max(beam["port_origin_geometric_lever_arm_m"] for beam in beams)),
        },
        "interpretation": (
            "This is an exact extraction of the concept CAD port envelopes. It is "
            "not a laser optical model, absorption model, target-interaction model, "
            "or hardware qualification record."
        ),
    }


def command_template(beams: list[dict]) -> list[dict]:
    rows = []
    for beam in beams:
        rows.append(
            {
                "beam_id": beam["beam_id"],
                "azimuth_deg": beam["azimuth_deg"],
                "poloidal_angle_deg": beam["poloidal_angle_deg"],
                "baseline_power_weight": 1.0,
                "calibrated_power_weight": None,
                "baseline_timing_offset_s": 0.0,
                "calibrated_timing_offset_s": None,
                "foot_energy_J": None,
                "foot_duration_s": None,
                "main_energy_J": None,
                "main_duration_s": None,
                "foot_to_main_delay_s": None,
                "absorption_fraction": None,
                "absorption_point_x_m": None,
                "absorption_point_y_m": None,
                "absorption_point_z_m": None,
                "beam_phase_index": int(round(beam["azimuth_deg"] / EXPECTED_AZIMUTH_STEP_DEG)),
            }
        )
    return rows


def build_strategy(model_path: Path, model: dict, beams: list[dict], ripple: dict) -> dict:
    return {
        "schema_version": "TOMAHAWK-LASER-DRIVE-STRATEGY-0.1",
        "status": "LASER_COUPLING_CONTROL_LAW_DEFINED_NOT_SOLVED",
        "geometry_invariant": True,
        "applied_to_existing_power_model": False,
        "source_geometry": {
            "path": str(model_path),
            "sha256": sha256(model_path),
            "model_version": model.get("version"),
            "laser_port_count": len(beams),
            "geometry_scope": model.get("scope"),
            "qualification_status": "UNQUALIFIED_CONCEPT_DIMENSIONS_NOT_FOR_FABRICATION",
        },
        "ripple_prerequisite": ripple,
        "controls": {
            "rotational_shear": {
                "candidate_enabled": True,
                "applied_to_power_model": False,
                "phase_order": "ascending_CAD_port_azimuth",
                "beam_phase_offsets_s": None,
                "target_angular_momentum_kg_m2_s": None,
                "target_shear_rate_s^-1": None,
                "torque_equation": (
                    "tau_vec = sum_i[ eta_i * P_i(t) / c * "
                    "cross(r_abs_i - r_target, k_hat_i) ]"
                ),
                "required_inputs": [
                    "laser_power_waveform_per_beam",
                    "absorption_fraction_per_beam_and_time",
                    "absorption_point_or_surface_intersection_per_beam_and_time",
                    "plasma_corona_inertia_and_rotation_profile",
                    "rotating_MHD_or_radiation_hydrodynamics_RT_growth_model",
                ],
                "status": "BLOCKED_MISSING_ABSORPTION_AND_ROTATING_MHD_SOLVER",
            },
            "temporal_pulse_shaping": {
                "candidate_enabled": True,
                "applied_to_power_model": False,
                "waveform": {
                    "foot": {
                        "energy_J": None,
                        "duration_s": None,
                        "power_W_per_beam": None,
                    },
                    "main": {
                        "energy_J": None,
                        "duration_s": None,
                        "power_W_per_beam": None,
                    },
                    "foot_to_main_delay_s": None,
                },
                "piecewise_definition": (
                    "P_i(t)=P_foot_i for t in foot interval; "
                    "P_i(t)=P_main_i for t in main interval; zero otherwise"
                ),
                "required_inputs": [
                    "laser_energy_budget",
                    "foot_and_main_pulse_durations",
                    "inter-pulse_delay",
                    "target_trajectory_and_shock_arrival_time",
                    "laser_damage_and_bandwidth_limits",
                    "radiation_hydrodynamics_coupling_model",
                ],
                "status": "BLOCKED_MISSING_LASER_WAVEFORM_AND_RADIATION_HYDRODYNAMICS",
            },
            "asymmetry_compensation": {
                "candidate_enabled": True,
                "applied_to_power_model": False,
                "baseline_power_weight_per_beam": 1.0,
                "baseline_timing_offset_s_per_beam": 0.0,
                "solved_power_weights": None,
                "solved_timing_offsets_s": None,
                "optimization_target": (
                    "minimize target shock-arrival-time and absorbed-impulse "
                    "nonuniformity on the evolving 3-D corona"
                ),
                "required_inputs": [
                    "3D chamber_and_target_surface",
                    "beam_ray_trace_and_focus_model",
                    "time-dependent absorption_map",
                    "radiation_hydrodynamics_objective_and_constraints",
                ],
                "status": "BLOCKED_MISSING_3D_RAY_TRACE_AND_HYDRODYNAMICS",
            },
            "magnetic_insulation": {
                "candidate_enabled": True,
                "applied_to_power_model": False,
                "initial_field_reference_T": 14.0,
                "initial_field_reference_source": (
                    "DESC total-field reconciliation, TF48 branch; field target "
                    "not a finite-beta equilibrium result"
                ),
                "initial_field_change_allowed": False,
                "ideal_flux_freezing_reference_equation": (
                    "B_compressed = B_initial * (A_initial / A_compressed) "
                    "for an idealized transverse-area compression"
                ),
                "compression_area_ratio": None,
                "predicted_compressed_field_T": None,
                "transport_suppression_factor": None,
                "required_inputs": [
                    "time-dependent radiation-MHD compression tensor",
                    "finite_resistivity_and_heat_transport_model",
                    "initial_temperature_and_density_profiles",
                    "field-line topology_and_reconnection_model",
                ],
                "status": "BLOCKED_MISSING_RADIATION_MHD_FLUX_COMPRESSION_AND_TRANSPORT",
            },
        },
        "power_output": {
            "fusion_power_multiplier_applied": 1.0,
            "incremental_power_output_W": None,
            "status": "BLOCKED_NATIVE_LASER_COUPLING_RADIATION_HYDRO_BURN_SOLVER",
            "reason": (
                "No output gain is asserted until the four controls are evaluated "
                "with absorption, target dynamics, transport, and burn physics."
            ),
        },
        "beam_command_template": command_template(beams),
        "required_validation_order": [
            "verify TF edge ripple remains below the approved limit",
            "populate beam waveforms and absorption maps",
            "run 3-D laser ray trace and radiation hydrodynamics",
            "run rotating/nonlinear MHD stability and burn/deposition scoring",
            "reconcile total field, target boundary, loads, and G1 review inputs",
        ],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(audit: dict, strategy: dict) -> str:
    source = audit["source"]
    ripple = strategy["ripple_prerequisite"]
    edge_ripple = ripple.get("edge_ripple_percent")
    edge_text = "unavailable" if edge_ripple is None else f"{edge_ripple:.6f}%"
    lines = [
        "# Laser-drive strategy integration",
        "",
        "Status: `LASER_COUPLING_CONTROL_LAW_DEFINED_NOT_SOLVED`",
        "",
        "The four requested laser-drive ideas are integrated as explicit control laws and input fields. CAD geometry is unchanged, and the existing power screen receives no gain multiplier.",
        "",
        "## Exact CAD input",
        "",
        f"- Source: `{source['path']}`",
        f"- SHA-256: `{source['sha256']}`",
        f"- CAD version: `{source['model_version']}`",
        f"- Laser ports extracted: **{audit['laser_port_count']}**",
        f"- Azimuth step: **{audit['azimuth_spacing']['mean_step_deg']:.6f}°** (maximum error {audit['azimuth_spacing']['max_abs_step_error_deg']:.3e}°)",
        f"- Geometry scope: `{source['scope']}`",
        "",
        "The port origins, outward normals, bore radii, wall thicknesses, and lengths are copied into `laser_geometry_audit.json` and the per-beam command template. The port-origin lever arm is only a geometry reference; physical torque requires the time-dependent absorption point.",
        "",
        "## Four controls",
        "",
        "1. **Rotational shear:** phase ordering and the torque equation are defined. Power, absorption, interaction location, target angular momentum, and a rotating-MHD/RHD stability calculation are still required.",
        "2. **Foot/main pulse:** a piecewise foot/main waveform is defined, but energy, duration, delay, and allowable peak power remain blank until supplied by the laser system and hydro model.",
        "3. **Asymmetry compensation:** each of the 16 CAD ports has baseline weight 1 and timing offset 0; calibrated weights/offsets are intentionally blank and must come from a 3-D ray trace plus radiation-hydrodynamics objective.",
        "4. **Magnetic insulation:** the 14 T TF48 field is retained as the initial reference. The ideal flux-freezing relation is provided, but the compression-area history and transport suppression must come from radiation-MHD. Initial field/current was not increased, so the ripple and coil-load checks are not silently invalidated.",
        "",
        "## Ripple prerequisite",
        "",
        f"- TF branch: `{ripple.get('tf_branch')}`",
        f"- Edge ripple: **{edge_text}**",
        f"- Limit: **{ripple.get('threshold_percent', 'unavailable')}%**",
        f"- Gate: **{ripple.get('tf_ripple_screen_pass')}**",
        "",
        (
            "The strict project preflight does not clear the ripple prerequisite: the "
            "native TF source is absent and the 16-coil CAD-A2 branch is over the limit."
            if not ripple.get("tf_ripple_screen_pass")
            else "The strict project preflight clears the ripple prerequisite."
        ),
        "A model-derived TF branch, even if its standalone number is below the screening limit, is not treated as native/as-built evidence.",
        "",
        "## Output disposition",
        "",
        "`fusion_power_multiplier_applied = 1.0`; incremental power remains blocked pending a native laser-coupling/radiation-hydrodynamics/burn calculation. The generated files are therefore solver inputs and an audit trail, not a claim that these controls increased power.",
        "",
        "See `laser_drive_strategy_input.json` for the machine-readable control contract and `laser_beam_command_template.csv` for the 16-beam fill-in table.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-definition", type=Path, default=None)
    parser.add_argument("--ripple-result", type=Path, default=DEFAULT_RIPPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    started = time.time()
    model_path = resolve_model(args.model_definition)
    model = json.loads(model_path.read_text(encoding="utf-8"))
    beams = extract_laser_ports(model)
    audit = array_geometry_audit(model_path, model, beams)
    ripple = read_ripple(args.ripple_result)
    strategy = build_strategy(model_path, model, beams, ripple)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "laser_geometry_audit.json").write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output / "laser_drive_strategy_input.json").write_text(
        json.dumps(strategy, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    write_csv(output / "laser_beam_command_template.csv", strategy["beam_command_template"])
    (output / "LASER_DRIVE_STRATEGY.md").write_text(
        markdown_report(audit, strategy), encoding="utf-8"
    )
    run_record = {
        "schema_version": "TOMAHAWK-LASER-DRIVE-RUN-0.1",
        "status": strategy["status"],
        "wall_seconds": time.time() - started,
        "python": sys.version,
        "platform": platform.platform(),
        "source_hashes": {
            "whole_model_definition.json": sha256(model_path),
            "total_field_reconciliation.json": (
                ripple.get("source_sha256") if ripple.get("available") else None
            ),
        },
        "outputs": [
            "laser_geometry_audit.json",
            "laser_drive_strategy_input.json",
            "laser_beam_command_template.csv",
            "LASER_DRIVE_STRATEGY.md",
        ],
        "geometry_changed": False,
        "power_output_changed": False,
        "native_laser_solver_run": False,
    }
    (output / "laser_drive_run_record.json").write_text(
        json.dumps(run_record, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": strategy["status"], "output": str(output), "laser_ports": len(beams), "ripple": ripple}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
