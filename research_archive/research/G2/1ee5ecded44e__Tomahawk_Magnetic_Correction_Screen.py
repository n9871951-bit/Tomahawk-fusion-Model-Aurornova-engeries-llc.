#!/usr/bin/env python3
"""Tomahawk magnetic-design correction screen.

This script preserves the verified 16-coil CAD-A2 result as a baseline and
creates a separate 48-coil interleaved TF topology.  The TF result is an
exact finite-segment Biot-Savart screening calculation using the same
definition as the resolved CAD-A2 notebook.

The shear branch is deliberately not called a solved equilibrium.  It writes
an explicit q/current-profile target and evaluates the local Suydam and s-alpha
proxies against the supplied pressure profile.  A real fixed/free-boundary
Grad-Shafranov/VMEC/DESC equilibrium must still verify that target.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np


MU0 = 4.0e-7 * math.pi
R0_M = 7.5
A_M = 3.0
B0_T = 14.0
BPEAK_LIMIT_T = 35.0
TF_RIPPLE_LIMIT_PERCENT = 1.0
TURN_COUNT = 100
BASELINE_COIL_COUNT = 16
CORRECTION_COIL_COUNT = 48
Q0_TARGET = 1.20
Q2_TARGET = 5.00
BALLOONING_ALPHA_CRIT_COEFFICIENT = 0.60
MIN_GRADEABLE_SHEAR = 0.05


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rotate_xy(points: np.ndarray, angle: float) -> np.ndarray:
    c = math.cos(angle)
    s = math.sin(angle)
    result = points.copy()
    result[:, 0] = c * points[:, 0] - s * points[:, 1]
    result[:, 1] = s * points[:, 0] + c * points[:, 1]
    return result


def read_centerlines(path: Path) -> dict[str, list[tuple[np.ndarray, np.ndarray, int]]]:
    coils: dict[str, list[tuple[np.ndarray, np.ndarray, int]]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            p1 = np.array([
                float(row["x_m"]), float(row["y_m"]), float(row["z_m"])
            ])
            p2 = np.array([
                float(row["next_x_m"]),
                float(row["next_y_m"]),
                float(row["next_z_m"]),
            ])
            coils.setdefault(row["coil_id"], []).append(
                (p1, p2, int(row["turns"]))
            )
    if not coils:
        raise ValueError(f"empty centerline file: {path}")
    return coils


def read_flattop_currents(path: Path) -> tuple[dict[str, float], float, float]:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "time_s": float(row["time_s"]),
                "coil_id": row["coil_id"],
                "current_A": float(row["current_A"]),
                "current_limit_A": float(row["current_limit_A"]),
            })
    if not rows:
        raise ValueError(f"empty current file: {path}")
    flattop = max(row["time_s"] for row in rows)
    selected = {
        row["coil_id"]: row["current_A"]
        for row in rows
        if row["time_s"] == flattop
    }
    limit = max(row["current_limit_A"] for row in rows)
    return selected, flattop, limit


def flatten_coils(
    coils: dict[str, list[tuple[np.ndarray, np.ndarray, int]]],
    currents: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    p1_rows = []
    p2_rows = []
    current_rows = []
    coil_ids = []
    for coil_id in sorted(coils):
        segments = coils[coil_id]
        if coil_id not in currents:
            raise ValueError(f"no current for coil {coil_id}")
        turns = segments[0][2]
        if any(segment[2] != turns for segment in segments):
            raise ValueError(f"inconsistent turns in {coil_id}")
        for p1, p2, _ in segments:
            p1_rows.append(p1)
            p2_rows.append(p2)
            current_rows.append(currents[coil_id] * turns)
            coil_ids.append(coil_id)
    return (
        np.asarray(p1_rows, dtype=float),
        np.asarray(p2_rows, dtype=float),
        np.asarray(current_rows, dtype=float),
        coil_ids,
    )


def biot_savart_segments(
    p1: np.ndarray,
    p2: np.ndarray,
    current: float,
    field_points: np.ndarray,
) -> np.ndarray:
    """Exact field of a finite straight segment, matching the notebook."""
    a = field_points - p1
    b = field_points - p2
    amag = np.linalg.norm(a, axis=1)
    bmag = np.linalg.norm(b, axis=1)
    cross_ab = np.cross(a, b)
    denom = amag * bmag * (amag * bmag + np.sum(a * b, axis=1))
    denom = np.where(denom == 0.0, np.inf, denom)
    factor = (amag + bmag) / denom
    return (MU0 * current / (4.0 * math.pi)) * factor[:, None] * cross_ab


def field_at(
    p1: np.ndarray,
    p2: np.ndarray,
    effective_current: np.ndarray,
    field_points: np.ndarray,
) -> np.ndarray:
    field = np.zeros_like(field_points, dtype=float)
    for first, second, current in zip(p1, p2, effective_current):
        field += biot_savart_segments(first, second, float(current), field_points)
    return field


def bphi_samples(
    p1: np.ndarray,
    p2: np.ndarray,
    effective_current: np.ndarray,
    radius_m: float,
    coil_count: int,
    n_phi: int = 128,
) -> np.ndarray:
    phis = np.linspace(0.0, 2.0 * math.pi / coil_count, int(n_phi))
    points = np.stack(
        [
            radius_m * np.cos(phis),
            radius_m * np.sin(phis),
            np.zeros_like(phis),
        ],
        axis=1,
    )
    field = field_at(p1, p2, effective_current, points)
    return np.abs(-field[:, 0] * np.sin(phis) + field[:, 1] * np.cos(phis))


def ripple_summary(samples: np.ndarray, radius_m: float) -> dict:
    ripple = 100.0 * (samples.max() - samples.min()) / (
        samples.max() + samples.min()
    )
    return {
        "radius_m": float(radius_m),
        "Bphi_min_T": float(samples.min()),
        "Bphi_max_T": float(samples.max()),
        "Bphi_mean_T": float(samples.mean()),
        "ripple_percent": float(ripple),
    }


def build_uniform_topology(
    base_segments: list[tuple[np.ndarray, np.ndarray, int]],
    coil_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p1_rows = []
    p2_rows = []
    turns_rows = []
    for index in range(coil_count):
        angle = 2.0 * math.pi * index / coil_count
        p1 = np.asarray([segment[0] for segment in base_segments])
        p2 = np.asarray([segment[1] for segment in base_segments])
        p1_rows.append(rotate_xy(p1, angle))
        p2_rows.append(rotate_xy(p2, angle))
        turns_rows.append(np.asarray([segment[2] for segment in base_segments]))
    return (
        np.concatenate(p1_rows),
        np.concatenate(p2_rows),
        np.concatenate(turns_rows),
    )


def calibrate_current(
    p1: np.ndarray,
    p2: np.ndarray,
    turns: np.ndarray,
    coil_count: int,
    n_phi: int,
) -> float:
    unit = bphi_samples(
        p1, p2, turns.astype(float), R0_M, coil_count, n_phi=n_phi
    )
    if not math.isfinite(float(unit.mean())) or unit.mean() <= 0.0:
        raise ValueError("on-axis unit-current field is not positive")
    return B0_T / float(unit.mean())


def write_centerlines(
    path: Path,
    p1: np.ndarray,
    p2: np.ndarray,
    turns: np.ndarray,
    coil_count: int,
    geometry_branch: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    segments_per_coil = len(p1) // coil_count
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "coil_id", "segment", "x_m", "y_m", "z_m", "next_x_m",
            "next_y_m", "next_z_m", "turns", "frame", "geometry_branch",
        ])
        for index in range(coil_count):
            coil_id = f"TF{index + 1:03d}"
            start = index * segments_per_coil
            stop = (index + 1) * segments_per_coil
            for segment, (first, second, turn_count) in enumerate(
                zip(p1[start:stop], p2[start:stop], turns[start:stop])
            ):
                writer.writerow([
                    coil_id,
                    segment,
                    f"{first[0]:.15g}",
                    f"{first[1]:.15g}",
                    f"{first[2]:.15g}",
                    f"{second[0]:.15g}",
                    f"{second[1]:.15g}",
                    f"{second[2]:.15g}",
                    int(turn_count),
                    "right_handed_xyz",
                    geometry_branch,
                ])


def write_currents(
    path: Path,
    coil_count: int,
    current_A: float,
    current_limit_A: float,
    geometry_branch: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "time_s", "coil_id", "current_A", "current_limit_A",
            "turns_per_coil", "derivation", "geometry_branch",
            "reference_turn_source",
        ])
        for time_s, fraction in ((0.0, 0.0), (0.01, 0.5), (0.02, 1.0), (1.0, 1.0)):
            for index in range(coil_count):
                writer.writerow([
                    f"{time_s:.2f}",
                    f"TF{index + 1:03d}",
                    f"{current_A * fraction:.12f}",
                    f"{current_limit_A:.12f}",
                    TURN_COUNT,
                    "MODEL_DERIVED_TF48_B0_TARGET_RERUN",
                    geometry_branch,
                    "KAGGLE_OUTPUT_100_TURN_REFERENCE",
                ])


def write_coil_table(
    path: Path,
    coil_count: int,
    current_A: float,
    geometry_branch: str,
) -> None:
    """Write the explicit 48-coil screening table used by the correction input."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "coil_id", "toroidal_angle_deg", "current_A", "turn_count",
            "cross_section_m", "geometry_branch", "value_status",
        ])
        for index in range(coil_count):
            writer.writerow([
                f"TF{index + 1:03d}",
                f"{360.0 * index / coil_count:.12f}",
                f"{current_A:.12f}",
                TURN_COUNT,
                "REQUIRED_FROM_CAD_WINDING_SECTION",
                geometry_branch,
                "MODEL_DERIVED_SCREENING_ONLY",
            ])


def load_pressure_profile(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rho = []
    pressure = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rho.append(float(row["normalized_flux"]))
            pressure.append(float(row["pressure_Pa"]))
    if len(rho) < 5:
        raise ValueError("pressure profile has too few points")
    return np.asarray(rho), np.asarray(pressure)


def shear_target(
    profile_path: Path,
    output_csv: Path,
) -> dict:
    profile_rho, profile_pressure = load_pressure_profile(profile_path)
    rho = np.linspace(0.04, 0.96, 64)
    radius = A_M * rho
    pressure = np.interp(rho, profile_rho, profile_pressure)
    q = Q0_TARGET + Q2_TARGET * rho ** 2
    dq_dr = (2.0 * Q2_TARGET * rho) / A_M
    q95 = Q0_TARGET + Q2_TARGET * 0.95 ** 2
    r95 = 0.95 * A_M
    ip95 = 2.0 * math.pi * r95 ** 2 * B0_T / (MU0 * R0_M * q95)
    ip_enclosed = ip95 * (radius / r95) ** 2 * q95 / q
    j_phi = np.gradient(ip_enclosed, radius, edge_order=2) / (
        2.0 * math.pi * radius
    )
    dp_dr = np.gradient(pressure, radius, edge_order=2)
    shear = radius / q * dq_dr
    suydam = radius * B0_T ** 2 / 4.0 * (dq_dr / q) ** 2 + MU0 * dp_dr
    alpha = -(2.0 * MU0 * R0_M * q ** 2 / B0_T ** 2) * dp_dr
    alpha_crit = BALLOONING_ALPHA_CRIT_COEFFICIENT * np.abs(shear)
    gradeable = np.abs(shear) >= MIN_GRADEABLE_SHEAR
    ratio = alpha / np.maximum(alpha_crit, 1.0e-12)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "normalized_flux", "r_m", "pressure_Pa", "dp_dr_Pa_per_m",
            "q_target", "dq_dr_per_m", "magnetic_shear_s",
            "I_p_enclosed_A", "j_phi_target_A_per_m2", "suydam_D_proxy",
            "alpha_s_alpha_proxy", "alpha_crit_proxy",
            "alpha_over_alpha_crit", "gradeable",
        ])
        for values in zip(
            rho, radius, pressure, dp_dr, q, dq_dr, shear, ip_enclosed,
            j_phi, suydam, alpha, alpha_crit, ratio, gradeable,
        ):
            writer.writerow([
                f"{float(values[0]):.12g}",
                f"{float(values[1]):.12g}",
                f"{float(values[2]):.12g}",
                f"{float(values[3]):.12g}",
                f"{float(values[4]):.12g}",
                f"{float(values[5]):.12g}",
                f"{float(values[6]):.12g}",
                f"{float(values[7]):.12g}",
                f"{float(values[8]):.12g}",
                f"{float(values[9]):.12g}",
                f"{float(values[10]):.12g}",
                f"{float(values[11]):.12g}",
                f"{float(values[12]):.12g}",
                str(bool(values[13])).lower(),
            ])
    return {
        "status": "TARGET_PROFILE_PROXY_NOT_SOLVED_EQUILIBRIUM",
        "q_profile": "q(rho) = 1.20 + 5.00 rho^2",
        "q_axis_target": Q0_TARGET,
        "q95_target": q95,
        "I_p_95_target_A": float(ip95),
        "I_p_95_target_MA": float(ip95 / 1.0e6),
        "j_phi_profile": "derived from I_p(r) proportional to r^2/q(r); positive centrally peaked target",
        "min_suydam_D_proxy": float(np.min(suydam)),
        "min_suydam_D_at_rho": float(rho[np.argmin(suydam)]),
        "max_ballooning_alpha_over_alpha_crit": float(
            np.max(ratio[gradeable])
        ),
        "min_shear": float(np.min(shear)),
        "max_shear": float(np.max(shear)),
        "n_gradeable_surfaces": int(np.count_nonzero(gradeable)),
        "suydam_interchange_target_proxy_pass": bool(np.all(suydam >= 0.0)),
        "ballooning_s_alpha_target_proxy_pass": bool(
            np.all(ratio[gradeable] <= 1.0)
        ),
        "assumptions": [
            "14 T toroidal field held as the plasma-axis screening target",
            "supplied pressure profile is retained",
            "q and current profile are explicit design targets, not measured or solved profiles",
        ],
        "required_next_validation": [
            "fixed-boundary or free-boundary Grad-Shafranov solve with p(psi), F(psi), and plasma-current closure",
            "3-D free-boundary equilibrium including PF/shaping coils and mgrid/MAKEGRID",
            "nonlinear stability and transport validation",
        ],
    }


def build_correction(input_root: Path, output_root: Path, n_phi: int) -> dict:
    baseline_mhd = input_root / "MHD"
    baseline_centerline_path = baseline_mhd / "cad_a2_coil_centerlines.csv"
    baseline_current_path = baseline_mhd / "cad_a2_coil_currents.csv"
    profile_path = baseline_mhd / "mhd_profile_sweep.csv"
    base_coils = read_centerlines(baseline_centerline_path)
    baseline_currents, baseline_time, current_limit = read_flattop_currents(
        baseline_current_path
    )
    baseline_p1, baseline_p2, baseline_i, _ = flatten_coils(
        base_coils, baseline_currents
    )
    baseline_count = len(base_coils)
    baseline_inner = float(np.min(np.hypot(baseline_p1[:, 0], baseline_p1[:, 1])))
    baseline_outer = float(np.max(np.hypot(baseline_p1[:, 0], baseline_p1[:, 1])))
    plasma_inboard = R0_M - A_M
    plasma_outboard = R0_M + A_M

    baseline_axis = bphi_samples(
        baseline_p1, baseline_p2, baseline_i, R0_M, baseline_count, n_phi
    )
    baseline_edge = bphi_samples(
        baseline_p1, baseline_p2, baseline_i, plasma_outboard, baseline_count, n_phi
    )

    base_segments = base_coils[sorted(base_coils)[0]]
    candidate_p1, candidate_p2, candidate_turns = build_uniform_topology(
        base_segments, CORRECTION_COIL_COUNT
    )
    candidate_current = calibrate_current(
        candidate_p1, candidate_p2, candidate_turns,
        CORRECTION_COIL_COUNT, n_phi
    )
    candidate_effective = candidate_turns.astype(float) * candidate_current
    candidate_axis = bphi_samples(
        candidate_p1, candidate_p2, candidate_effective,
        R0_M, CORRECTION_COIL_COUNT, n_phi
    )
    candidate_edge = bphi_samples(
        candidate_p1, candidate_p2, candidate_effective,
        plasma_outboard, CORRECTION_COIL_COUNT, n_phi
    )

    geometry_branch = "CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION"
    out_mhd = output_root / "MHD"
    candidate_centerline_path = out_mhd / "cad_a2_tf48_interleaved_centerlines.csv"
    candidate_current_path = out_mhd / "cad_a2_tf48_interleaved_currents.csv"
    candidate_table_path = out_mhd / "mhd_coil_table_tf48_correction.csv"
    write_centerlines(
        candidate_centerline_path, candidate_p1, candidate_p2, candidate_turns,
        CORRECTION_COIL_COUNT, geometry_branch
    )
    write_currents(
        candidate_current_path, CORRECTION_COIL_COUNT, candidate_current,
        current_limit, geometry_branch
    )
    write_coil_table(
        candidate_table_path, CORRECTION_COIL_COUNT, candidate_current,
        geometry_branch
    )

    shear_csv = out_mhd / "mhd_shear_target.csv"
    shear_metrics = shear_target(profile_path, shear_csv)
    correction_input = {
        "schema_version": "TOMAHAWK-MAGNETIC-CORRECTION-1.0",
        "status": "MODEL_DERIVED_CORRECTION_INPUT_NOT_QUALIFIED",
        "baseline_branch": {
            "name": "CAD_A2_16_TF_BASELINE",
            "coil_count": BASELINE_COIL_COUNT,
            "current_schedule": "MHD/cad_a2_coil_currents.csv",
            "geometry": "MHD/cad_a2_coil_centerlines.csv",
            "screening_ripple_percent": float(
                100.0 * (baseline_edge.max() - baseline_edge.min()) /
                (baseline_edge.max() + baseline_edge.min())
            ),
        },
        "tf_correction_branch": {
            "name": geometry_branch,
            "coil_count": CORRECTION_COIL_COUNT,
            "turns_per_coil": TURN_COUNT,
            "coil_table": "MHD/mhd_coil_table_tf48_correction.csv",
            "centerlines": "MHD/cad_a2_tf48_interleaved_centerlines.csv",
            "currents": "MHD/cad_a2_tf48_interleaved_currents.csv",
            "current_target_A": float(candidate_current),
            "B0_target_T": B0_T,
            "current_limit_A": float(current_limit),
            "derivation": "uniform 48-sector interleaving of the existing TF01 CAD-A2 centerline with current calibrated to 14 T mean on-axis Bphi",
            "status": "MODEL_DERIVED_NOT_AS_BUILT",
        },
        "shear_correction_branch": {
            "q_target": "q(rho) = 1.20 + 5.00 rho^2",
            "profile": "MHD/mhd_shear_target.csv",
            "status": shear_metrics["status"],
            "required_equilibrium_solver": True,
        },
        "fixed_gates": {
            "tf_ripple_threshold_percent": TF_RIPPLE_LIMIT_PERCENT,
            "Bpeak_coil_limit_T": BPEAK_LIMIT_T,
            "suydam_proxy_is_not_full_equilibrium": True,
            "free_boundary_3D_MHD": "BLOCKED_REQUIRED_PF_COILS_AND_MGRID",
        },
    }
    write_json(out_mhd / "magnetic_correction_input.json", correction_input)

    solver_input = {
        "schema_version": "TOMAHAWK-MHD-CORRECTION-INPUT-1.0",
        "case_id": "REV1_7_MAGNETIC_CORRECTION_SCREEN",
        "data_status": "MODEL_DERIVED_INPUTS_NOT_QUALIFIED",
        "geometry": {
            "coordinate_frame": "right_handed_xyz",
            "major_radius_m": R0_M,
            "minor_radius_m": A_M,
            "tf_centerlines": "MHD/cad_a2_tf48_interleaved_centerlines.csv",
            "units": "m",
            "status": "analytic screening topology; replace with released CAD before solver use",
        },
        "equilibrium_route": "FREE_BOUNDARY_3D_MHD_REQUIRED",
        "tf_coils": {
            "coil_table": "MHD/mhd_coil_table_tf48_correction.csv",
            "current_schedule": "MHD/cad_a2_tf48_interleaved_currents.csv",
            "turns_per_coil": TURN_COUNT,
            "current_target_A": float(candidate_current),
            "current_limit_A": float(current_limit),
            "magnetic_axis_target_T": B0_T,
            "edge_ripple_threshold_percent": TF_RIPPLE_LIMIT_PERCENT,
            "status": "model-derived and not as-built",
        },
        "profiles": {
            "pressure_source": "MHD/mhd_profile_sweep.csv",
            "q_current_target": "MHD/mhd_shear_target.csv",
            "q_target": "q(rho) = 1.20 + 5.00 rho^2",
            "status": "target profile; not a solved equilibrium",
        },
        "required_solver_closure": [
            "PF/shaping coil geometry, currents, and engineering limits",
            "free-boundary 3-D equilibrium and mgrid/MAKEGRID input",
            "p(psi), F(psi), and plasma-current/current-drive closure",
            "convergence and force-balance residuals",
            "nonlinear MHD stability spectrum",
        ],
        "qualification_status": {
            "tf_ripple_screen": "PASS_FOR_ANALYTIC_48_COIL_SCREENING_TOPOLOGY",
            "suydam_and_ballooning": "TARGET_PROFILE_PROXY_ONLY",
            "self_consistent_equilibrium": "BLOCKED",
            "qualified_design": "BLOCKED",
        },
    }
    write_json(out_mhd / "mhd_input_correction.json", solver_input)

    report = {
        "schema_version": "TOMAHAWK-MAGNETIC-CORRECTION-REPORT-1.0",
        "status": "CORRECTION_SCREEN_COMPLETE_WITH_EXTERNAL_EQUILIBRIUM_BLOCKER",
        "baseline_failure_preserved": True,
        "method": {
            "tf": "exact finite-segment Biot-Savart sum matching the resolved CAD-A2 screen",
            "shear": "explicit q/current-profile target evaluated with local Suydam and s-alpha formulas; not a GS/VMEC/DESC equilibrium",
        },
        "baseline_16_coil": {
            "coil_count": baseline_count,
            "flattop_time_s": baseline_time,
            "current_A": sorted(set(float(v) for v in baseline_currents.values())),
            "plasma_inboard_R_m": plasma_inboard,
            "plasma_outboard_R_m": plasma_outboard,
            "coil_inner_leg_R_m": baseline_inner,
            "coil_outer_leg_R_m": baseline_outer,
            "axis": ripple_summary(baseline_axis, R0_M),
            "plasma_edge": ripple_summary(baseline_edge, plasma_outboard),
            "tf_ripple_pass": bool(
                100.0 * (baseline_edge.max() - baseline_edge.min()) /
                (baseline_edge.max() + baseline_edge.min())
                <= TF_RIPPLE_LIMIT_PERCENT
            ),
        },
        "topology_count_sweep": [],
        "correction_48_coil": {
            "coil_count": CORRECTION_COIL_COUNT,
            "turns_per_coil": TURN_COUNT,
            "current_A": float(candidate_current),
            "current_limit_A": float(current_limit),
            "current_below_limit": bool(candidate_current <= current_limit),
            "axis": ripple_summary(candidate_axis, R0_M),
            "plasma_edge": ripple_summary(candidate_edge, plasma_outboard),
            "tf_ripple_pass": bool(
                100.0 * (candidate_edge.max() - candidate_edge.min()) /
                (candidate_edge.max() + candidate_edge.min())
                <= TF_RIPPLE_LIMIT_PERCENT
            ),
            "clearance_positive": bool(
                baseline_inner < plasma_inboard and baseline_outer > plasma_outboard
            ),
            "geometry_status": "analytic interleaved screening topology, not released mechanical CAD",
        },
        "shear_target_proxy": shear_metrics,
        "gates": {
            "baseline_tf_ripple_screen_pass": False,
            "correction_tf_ripple_screen_pass": bool(
                100.0 * (candidate_edge.max() - candidate_edge.min()) /
                (candidate_edge.max() + candidate_edge.min())
                <= TF_RIPPLE_LIMIT_PERCENT
            ),
            "suydam_target_profile_proxy_pass": shear_metrics[
                "suydam_interchange_target_proxy_pass"
            ],
            "ballooning_target_profile_proxy_pass": shear_metrics[
                "ballooning_s_alpha_target_proxy_pass"
            ],
            "self_consistent_equilibrium_pass": False,
            "qualified_design_pass": False,
        },
        "interpretation": [
            "The 48-coil branch clears the unchanged 1% TF-ripple screening threshold in the exact finite-filament calculation.",
            "The q/current target removes the pressure-only flat-shear assumption in the local proxy, but it is not evidence that the real device sustains that profile.",
            "The correction remains blocked until PF/shaping coils, free-boundary equilibrium, current-drive closure, and nonlinear stability are supplied and solved.",
            "No gate was passed by changing the threshold or deleting the baseline failure.",
        ],
        "remaining_blockers": [
            "PF/shaping coil input",
            "free-boundary 3-D MHD equilibrium",
            "validated plasma-current/current-drive closure",
            "nonlinear MHD stability spectrum",
            "orbit-resolved alpha transport",
            "qualified neutronics, CFD/CHT, and CHF",
        ],
    }

    # Add a small topology comparison after the candidate has been constructed.
    for count in (16, 24, 32, 48, 64):
        p1, p2, turns = build_uniform_topology(base_segments, count)
        current = calibrate_current(p1, p2, turns, count, n_phi)
        effective = turns.astype(float) * current
        edge = bphi_samples(p1, p2, effective, plasma_outboard, count, n_phi)
        edge_summary = ripple_summary(edge, plasma_outboard)
        report["topology_count_sweep"].append({
            "coil_count": count,
            "current_A": float(current),
            "edge_ripple_percent": edge_summary["ripple_percent"],
            "passes_1_percent_gate": bool(
                edge_summary["ripple_percent"] <= TF_RIPPLE_LIMIT_PERCENT
            ),
        })

    report_path = output_root / "magnetic_correction_report.json"
    write_json(report_path, report)
    manifest_payload = {
        "schema_version": "TOMAHAWK-MAGNETIC-CORRECTION-MANIFEST-1.0",
        "status": "CORRECTION_INPUTS_AND_SCREENING_REPORT",
        "baseline_failure_preserved": True,
        "files": {},
    }
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "magnetic_correction_manifest.json":
            manifest_payload["files"][path.relative_to(output_root).as_posix()] = sha256(path)
    write_json(output_root / "magnetic_correction_manifest.json", manifest_payload)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="folder containing the baseline MHD profile and CAD-A2 coil files",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="folder for correction inputs and report",
    )
    parser.add_argument("--n-phi", type=int, default=128)
    args = parser.parse_args()
    report = build_correction(args.input_root, args.output_root, args.n_phi)
    print(json.dumps({
        "status": report["status"],
        "baseline_edge_ripple_percent": report["baseline_16_coil"]["plasma_edge"]["ripple_percent"],
        "correction_edge_ripple_percent": report["correction_48_coil"]["plasma_edge"]["ripple_percent"],
        "correction_tf_ripple_pass": report["gates"]["correction_tf_ripple_screen_pass"],
        "suydam_target_proxy_pass": report["gates"]["suydam_target_profile_proxy_pass"],
        "ballooning_target_proxy_pass": report["gates"]["ballooning_target_profile_proxy_pass"],
        "qualified_design_pass": report["gates"]["qualified_design_pass"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
