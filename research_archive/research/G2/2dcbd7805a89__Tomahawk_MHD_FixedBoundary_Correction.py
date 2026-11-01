#!/usr/bin/env python3
"""Fixed-boundary toroidal-geometry correction for the Tomahawk MHD screen.

The earlier target profile was derived cylindrically and then solved in a
toroidal, R-dependent Grad-Shafranov operator.  This module closes that
specific gap by iterating the prescribed toroidal-current profile against the
q profile measured on the solved fixed-boundary equilibrium.

It is intentionally not a free-boundary or qualified 3-D equilibrium code:
PF/shaping coils, mgrid/MAKEGRID data, p(psi)/F(psi) closure, and nonlinear
stability are still required for promotion beyond this screen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.interpolate import RegularGridInterpolator
from scipy.sparse.linalg import splu


MU0 = 4.0e-7 * math.pi
R0_M = 7.5
A_M = 3.0
B0_T = 14.0
F_TOROIDAL = R0_M * B0_T
Q0_TARGET = 1.20
Q_EDGE_TARGET = 5.808
Q_LINEAR_TARGET = 2.0
TOROIDAL_Q_DRIFT_EDGE = 0.20
RHO_CALIBRATION = 0.96
BALLOONING_ALPHA_CRIT_COEFFICIENT = 0.60
MIN_GRADEABLE_SHEAR = 0.05
N_SURFACES = 64
N_THETA = 256
N_RADIAL_RAY = 100
N_ITERATIONS = 4


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(value), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def trapezoid(values, coordinates, axis=-1):
    method = getattr(np, "trapezoid", None)
    return method(values, coordinates, axis=axis) if method else np.trapz(
        values, coordinates, axis=axis
    )


def load_pressure_profile(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rho = []
    pressure = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rho.append(float(row["normalized_flux"]))
            pressure.append(float(row["pressure_Pa"]))
    if len(rho) < 5 or not np.all(np.diff(rho) > 0.0):
        raise ValueError(f"invalid pressure profile: {path}")
    return np.asarray(rho), np.asarray(pressure)


def make_grid(nr: int, nz: int) -> dict:
    R = np.linspace(R0_M - 1.10 * A_M, R0_M + 1.10 * A_M, int(nr))
    Z = np.linspace(-1.10 * A_M, 1.10 * A_M, int(nz))
    RR, ZZ = np.meshgrid(R, Z, indexing="xy")
    dR = float(R[1] - R[0])
    dZ = float(Z[1] - Z[0])
    rho2 = ((RR - R0_M) / A_M) ** 2 + (ZZ / A_M) ** 2
    mask = rho2 <= 1.0
    return {
        "R": R,
        "Z": Z,
        "RR": RR,
        "ZZ": ZZ,
        "dR": dR,
        "dZ": dZ,
        "rho": np.sqrt(np.maximum(rho2, 0.0)),
        "mask": mask,
    }


def build_operator(grid: dict):
    RR = grid["RR"]
    mask = grid["mask"]
    dR = grid["dR"]
    dZ = grid["dZ"]
    nz, nr = mask.shape
    index = -np.ones(mask.shape, dtype=int)
    index[mask] = np.arange(int(mask.sum()))
    ae = 1.0 / dR**2 - 1.0 / (2.0 * RR * dR)
    aw = 1.0 / dR**2 + 1.0 / (2.0 * RR * dR)
    an = 1.0 / dZ**2
    ap = -2.0 / dR**2 - 2.0 / dZ**2
    row = []
    col = []
    data = []
    for i, j in zip(*np.nonzero(mask)):
        current = int(index[i, j])
        row.append(current)
        col.append(current)
        data.append(float(ap))
        if j + 1 < nr and mask[i, j + 1]:
            row.append(current)
            col.append(int(index[i, j + 1]))
            data.append(float(ae[i, j]))
        if j - 1 >= 0 and mask[i, j - 1]:
            row.append(current)
            col.append(int(index[i, j - 1]))
            data.append(float(aw[i, j]))
        if i + 1 < nz and mask[i + 1, j]:
            row.append(current)
            col.append(int(index[i + 1, j]))
            data.append(float(an))
        if i - 1 >= 0 and mask[i - 1, j]:
            row.append(current)
            col.append(int(index[i - 1, j]))
            data.append(float(an))
    return sparse.coo_matrix(
        (data, (row, col)),
        shape=(int(mask.sum()), int(mask.sum())),
    ).tocsc()


def delta_star(psi: np.ndarray, grid: dict) -> np.ndarray:
    RR = grid["RR"]
    mask = grid["mask"]
    dR = grid["dR"]
    dZ = grid["dZ"]
    east = np.zeros_like(psi)
    west = np.zeros_like(psi)
    north = np.zeros_like(psi)
    south = np.zeros_like(psi)
    east[:, :-1] = np.where(mask[:, 1:], psi[:, 1:], 0.0)
    west[:, 1:] = np.where(mask[:, :-1], psi[:, :-1], 0.0)
    north[:-1, :] = np.where(mask[1:, :], psi[1:, :], 0.0)
    south[1:, :] = np.where(mask[:-1, :], psi[:-1, :], 0.0)
    ae = 1.0 / dR**2 - 1.0 / (2.0 * RR * dR)
    aw = 1.0 / dR**2 + 1.0 / (2.0 * RR * dR)
    ap = -2.0 / dR**2 - 2.0 / dZ**2
    return ae * east + aw * west + (north + south) / dZ**2 + ap * psi


def solve_fixed_source(grid: dict, factorization, source: np.ndarray):
    psi = np.zeros_like(source)
    psi[grid["mask"]] = factorization.solve(source[grid["mask"]])
    residual = delta_star(psi, grid) - source
    scale = max(float(np.max(np.abs(source[grid["mask"]]))), 1.0)
    relative = float(np.max(np.abs(residual[grid["mask"]])) / scale)
    return psi, relative


def stable_solved_q_target(rho: np.ndarray) -> np.ndarray:
    q4 = (Q_EDGE_TARGET - Q0_TARGET - Q_LINEAR_TARGET * RHO_CALIBRATION) / (
        RHO_CALIBRATION**4
    )
    return Q0_TARGET + Q_LINEAR_TARGET * rho + q4 * rho**4


def q_design_from_solved_target(rho: np.ndarray) -> np.ndarray:
    return stable_solved_q_target(rho) / (1.0 + TOROIDAL_Q_DRIFT_EDGE * rho**2)


def current_from_q_design(rho_dense: np.ndarray, q_design: np.ndarray):
    radius = A_M * rho_dense
    q_safe = np.maximum(q_design, 0.2)
    enclosed_current = (
        2.0 * math.pi * B0_T * radius**2 / (MU0 * R0_M * q_safe)
    )
    current_density = np.gradient(enclosed_current, radius, edge_order=2) / (
        2.0 * math.pi * radius
    )
    current_density[0] = current_density[1]
    if np.any(current_density <= 0.0) or not np.all(np.isfinite(current_density)):
        raise ValueError("q design produced a non-positive or non-finite j_phi")
    return enclosed_current, current_density


def extract_flux_surfaces(
    grid: dict,
    psi: np.ndarray,
    pressure_rho: np.ndarray,
    pressure_values: np.ndarray,
    n_surfaces: int = N_SURFACES,
    n_theta: int = N_THETA,
    n_radial: int = N_RADIAL_RAY,
) -> dict:
    """Extract flux surfaces by radial ray intersection and integrate flux."""
    R = grid["R"]
    Z = grid["Z"]
    mask = grid["mask"]
    psi_axis = float(np.max(psi[mask]))
    if not math.isfinite(psi_axis) or psi_axis <= 0.0:
        raise RuntimeError("non-positive fixed-boundary axis flux")
    axis_index = np.unravel_index(np.argmax(psi), psi.shape)
    r_axis = float(grid["RR"][axis_index])
    z_axis = float(grid["ZZ"][axis_index])
    psi_interp = RegularGridInterpolator(
        (Z, R), psi, bounds_error=False, fill_value=0.0
    )
    angles = np.linspace(0.0, 2.0 * math.pi, int(n_theta), endpoint=False)
    cos_theta = np.cos(angles)
    sin_theta = np.sin(angles)
    ray_fraction = np.linspace(0.0, 1.0, int(n_radial))[None, :]
    axis_offset_R = r_axis - R0_M
    axis_offset_Z = z_axis
    discriminant = (
        (axis_offset_R * cos_theta + axis_offset_Z * sin_theta) ** 2
        + A_M**2
        - axis_offset_R**2
        - axis_offset_Z**2
    )
    ray_boundary = -(axis_offset_R * cos_theta + axis_offset_Z * sin_theta) + np.sqrt(
        np.maximum(discriminant, 0.0)
    )
    full_ray = ray_boundary[:, None] * ray_fraction
    ray_points = np.stack(
        [
            z_axis + full_ray * sin_theta[:, None],
            r_axis + full_ray * cos_theta[:, None],
        ],
        axis=-1,
    )
    ray_values = psi_interp(ray_points.reshape(-1, 2)).reshape(
        int(n_theta), int(n_radial)
    )

    fractions = np.linspace(0.96, 0.04, int(n_surfaces))
    psi_targets = fractions * psi_axis
    areas = []
    toroidal_flux = []
    surface_pressure = []
    surface_bphi = []
    for target in psi_targets:
        above = ray_values >= target
        first_below = np.argmax(~above, axis=1)
        first_below = np.clip(first_below, 1, int(n_radial) - 1)
        ray_index = np.arange(int(n_theta))
        value_before = ray_values[ray_index, first_below - 1]
        value_after = ray_values[ray_index, first_below]
        interpolation = (target - value_before) / (
            value_after - value_before + 1.0e-30
        )
        root_fraction = (
            first_below - 1 + np.clip(interpolation, 0.0, 1.0)
        ) / (int(n_radial) - 1)
        root_radius = root_fraction * ray_boundary
        root_R = r_axis + root_radius * cos_theta
        root_Z = z_axis + root_radius * sin_theta
        areas.append(math.pi * float(np.mean(root_radius**2)))
        ray_radius = root_radius[:, None] * ray_fraction
        ray_R = r_axis + ray_radius * cos_theta[:, None]
        integrand = F_TOROIDAL * ray_radius / ray_R
        per_ray_flux = trapezoid(integrand, ray_radius, axis=1)
        toroidal_flux.append(2.0 * math.pi * float(np.mean(per_ray_flux)))
        geometric_rho = np.sqrt((root_R - R0_M) ** 2 + root_Z**2) / A_M
        surface_pressure.append(
            float(np.mean(np.interp(geometric_rho, pressure_rho, pressure_values)))
        )
        surface_bphi.append(float(F_TOROIDAL * np.mean(1.0 / root_R)))

    return {
        "psi_axis_Wb": psi_axis,
        "axis_R_m": r_axis,
        "axis_Z_m": z_axis,
        "psi_fraction": fractions,
        "psi_Wb": psi_targets,
        "r_eff_m": np.sqrt(np.asarray(areas) / math.pi),
        "toroidal_flux_Wb": np.asarray(toroidal_flux),
        "pressure_avg_Pa": np.asarray(surface_pressure),
        "bphi_avg_T": np.asarray(surface_bphi),
    }


def stability_metrics(
    grid: dict,
    psi: np.ndarray,
    source: np.ndarray,
    surfaces: dict,
    pressure_rho: np.ndarray,
    pressure_values: np.ndarray,
    residual_relative: float,
) -> tuple[dict, dict, dict]:
    r = np.asarray(surfaces["r_eff_m"])
    q = np.abs(
        np.gradient(
            np.asarray(surfaces["toroidal_flux_Wb"]),
            np.asarray(surfaces["psi_Wb"]),
            edge_order=2,
        )
    ) / (2.0 * math.pi)
    bphi = np.asarray(surfaces["bphi_avg_T"])
    pressure = np.asarray(surfaces["pressure_avg_Pa"])
    order = np.argsort(r)
    r = r[order]
    q = q[order]
    bphi = bphi[order]
    pressure = pressure[order]
    target_q = stable_solved_q_target(np.clip(r / A_M, 0.0, 1.0))
    q_ratio = q / np.maximum(target_q, 1.0e-12)
    q_at_calibration = float(np.interp(RHO_CALIBRATION, r / A_M, q))
    q_target_at_calibration = float(
        stable_solved_q_target(np.asarray([RHO_CALIBRATION]))[0]
    )
    dq_dr = np.gradient(q, r, edge_order=2)
    dp_dr = np.gradient(pressure, r, edge_order=2)
    shear = r / np.maximum(q, 1.0e-12) * dq_dr
    dlnq_dr = dq_dr / np.maximum(q, 1.0e-12)
    suydam = r * bphi**2 / 4.0 * dlnq_dr**2 + MU0 * dp_dr
    alpha = -(2.0 * MU0 * R0_M * q**2 / B0_T**2) * dp_dr
    alpha_crit = BALLOONING_ALPHA_CRIT_COEFFICIENT * np.abs(shear)
    gradeable = np.abs(shear) >= MIN_GRADEABLE_SHEAR
    ratio = alpha / np.maximum(alpha_crit, 1.0e-12)

    RR = grid["RR"]
    mask = grid["mask"]
    dR = grid["dR"]
    dZ = grid["dZ"]
    dpsi_dz, dpsi_dr = np.gradient(psi, dZ, dR, edge_order=2)
    br = np.where(mask, -dpsi_dz / RR, 0.0)
    bz = np.where(mask, dpsi_dr / RR, 0.0)
    divb = np.gradient(RR * br, dR, axis=1, edge_order=2) / RR + np.gradient(
        bz, dZ, axis=0, edge_order=2
    )
    core = mask & (grid["rho"] <= 0.90)
    field_scale = max(
        float(np.max(np.abs(br[core]))),
        float(np.max(np.abs(bz[core]))),
        1.0,
    ) / A_M
    divb_relative = float(np.max(np.abs(divb[core])) / field_scale)

    metrics = {
        "status": "FIXED_BOUNDARY_SOLVED_EQUILIBRIUM_SCREEN",
        "solver_equation": "Delta_star(psi) = -mu0 * R * j_phi",
        "solver_grid": [int(len(grid["R"])), int(len(grid["Z"]))],
        "gs_residual_relative": residual_relative,
        "divB_relative": divb_relative,
        "axis_R_m": surfaces["axis_R_m"],
        "axis_Z_m": surfaces["axis_Z_m"],
        "psi_axis_Wb": surfaces["psi_axis_Wb"],
        "I_p_solved_MA": float(np.sum(source[mask] / (-MU0 * RR[mask])) * dR * dZ / 1.0e6),
        "q_min": float(np.min(q)),
        "q_max": float(np.max(q)),
        "q_at_rho_0_96": q_at_calibration,
        "q_target_at_rho_0_96": q_target_at_calibration,
        "q_ratio_at_rho_0_96": q_at_calibration / q_target_at_calibration,
        "max_abs_q_target_relative_error": float(np.max(np.abs(q_ratio - 1.0))),
        "q_monotonic_pass": bool(np.all(np.diff(q) >= -1.0e-8)),
        "min_suydam_D": float(np.min(suydam)),
        "min_suydam_D_at_rho": float(r[np.argmin(suydam)] / A_M),
        "max_ballooning_alpha_over_alpha_crit": float(
            np.max(ratio[gradeable]) if np.any(gradeable) else math.inf
        ),
        "max_ballooning_at_rho": float(
            r[gradeable][np.argmax(ratio[gradeable])] / A_M
            if np.any(gradeable)
            else math.nan
        ),
        "min_shear": float(np.min(shear)),
        "n_gradeable_surfaces": int(np.count_nonzero(gradeable)),
        "n_surfaces": int(len(r)),
        "suydam_proxy_method": (
            "Suydam D = r Bphi^2/4 (d ln q/dr)^2 + mu0 dp/dr"
        ),
        "ballooning_proxy_method": (
            "alpha = -2 mu0 R0 q^2 dp/dr / B0^2; alpha_crit = 0.6 |s|"
        ),
        "pressure_label": "supplied pressure profile interpolated by geometric rho",
        "limitations": [
            "fixed circular boundary; no PF/shaping coil fit",
            "prescribed geometric-rho j_phi and pressure, not a full p(psi), F(psi) closure",
            "local large-aspect-ratio Suydam and s-alpha proxies, not eigenvalue stability",
            "no 3-D free-boundary equilibrium or nonlinear MHD",
        ],
    }
    gates = {
        "GS_residual_pass": bool(residual_relative <= 1.0e-10),
        "divB_pass": bool(divb_relative <= 1.0e-8),
        "q_target_fit_pass": bool(metrics["max_abs_q_target_relative_error"] <= 0.10),
        "q_monotonic_pass": metrics["q_monotonic_pass"],
        "suydam_interchange_proxy_pass": bool(np.all(suydam >= 0.0)),
        "ballooning_s_alpha_proxy_pass": bool(
            np.any(gradeable) and np.all(ratio[gradeable] <= 1.0)
        ),
    }
    gates["fixed_boundary_correction_screen_pass"] = bool(
        all(
            gates[name]
            for name in (
                "GS_residual_pass",
                "divB_pass",
                "q_target_fit_pass",
                "q_monotonic_pass",
                "suydam_interchange_proxy_pass",
                "ballooning_s_alpha_proxy_pass",
            )
        )
    )
    arrays = {
        "r_eff_m": r,
        "rho_eff": r / A_M,
        "q_solved": q,
        "q_target": target_q,
        "q_ratio": q_ratio,
        "pressure_avg_Pa": pressure,
        "dp_dr_Pa_per_m": dp_dr,
        "bphi_avg_T": bphi,
        "dq_dr_per_m": dq_dr,
        "magnetic_shear_s": shear,
        "suydam_D": suydam,
        "alpha_proxy": alpha,
        "alpha_crit_proxy": alpha_crit,
        "alpha_over_alpha_crit": ratio,
        "gradeable": gradeable,
        "BR": br,
        "BZ": bz,
    }
    return metrics, gates, arrays


def write_profile_csv(path: Path, rho, pressure, q_design, q_target, enclosed, jphi):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "normalized_flux",
            "r_m",
            "pressure_Pa",
            "q_design_for_toroidal_solve",
            "q_target_on_solved_surfaces",
            "I_p_enclosed_A",
            "j_phi_target_A_per_m2",
            "toroidal_q_drift_compensation",
        ])
        for row in zip(rho, pressure, q_design, q_target, enclosed, jphi):
            writer.writerow([
                f"{float(row[0]):.12g}",
                f"{float(A_M * row[0]):.12g}",
                f"{float(row[1]):.12g}",
                f"{float(row[2]):.12g}",
                f"{float(row[3]):.12g}",
                f"{float(row[4]):.12g}",
                f"{float(row[5]):.12g}",
                f"{float(1.0 + TOROIDAL_Q_DRIFT_EDGE * row[0] ** 2):.12g}",
            ])


def write_q_csv(path: Path, arrays: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rho_eff",
        "r_eff_m",
        "q_solved",
        "q_target",
        "q_ratio",
        "pressure_avg_Pa",
        "dp_dr_Pa_per_m",
        "bphi_avg_T",
        "dq_dr_per_m",
        "magnetic_shear_s",
        "suydam_D",
        "alpha_proxy",
        "alpha_crit_proxy",
        "alpha_over_alpha_crit",
        "gradeable",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i in range(len(arrays["r_eff_m"])):
            writer.writerow({
                key: (
                    str(bool(arrays[key][i])).lower()
                    if key == "gradeable"
                    else f"{float(arrays[key][i]):.12g}"
                )
                for key in fields
            })


def build_correction(input_root: Path, output_root: Path, nr: int, nz: int):
    mhd = input_root / "MHD"
    profile_path = mhd / "mhd_profile_sweep.csv"
    pressure_rho, pressure_values = load_pressure_profile(profile_path)
    grid = make_grid(nr, nz)
    factorization = splu(build_operator(grid))
    rho_dense = np.linspace(1.0e-4, 1.0, 4096)
    pressure_dense = np.interp(rho_dense, pressure_rho, pressure_values)
    q_target_dense = stable_solved_q_target(rho_dense)

    # Re-run the original cylindrical target through this same toroidal
    # fixed-boundary operator.  This records the correction baseline rather
    # than relying only on the user's reported endpoint.
    original_q_dense = Q0_TARGET + 5.0 * rho_dense**2
    _, original_j_dense = current_from_q_design(
        rho_dense, original_q_dense
    )
    original_j_grid = np.interp(
        np.clip(grid["rho"], 0.0, 1.0), rho_dense, original_j_dense
    )
    original_source = np.where(
        grid["mask"], -MU0 * grid["RR"] * original_j_grid, 0.0
    )
    original_psi, original_residual = solve_fixed_source(
        grid, factorization, original_source
    )
    original_surfaces = extract_flux_surfaces(
        grid, original_psi, pressure_rho, pressure_values
    )
    original_rho_eff = original_surfaces["r_eff_m"] / A_M
    original_q_solved = np.abs(
        np.gradient(
            original_surfaces["toroidal_flux_Wb"],
            original_surfaces["psi_Wb"],
            edge_order=2,
        )
    ) / (2.0 * math.pi)
    original_order = np.argsort(original_rho_eff)
    original_q_at_calibration = float(
        np.interp(
            RHO_CALIBRATION,
            original_rho_eff[original_order],
            original_q_solved[original_order],
        )
    )
    original_q_target_at_calibration = float(
        Q0_TARGET + 5.0 * RHO_CALIBRATION**2
    )

    q_design = q_design_from_solved_target(rho_dense)
    history = []
    final = None

    for iteration in range(N_ITERATIONS):
        enclosed_current, current_density = current_from_q_design(
            rho_dense, q_design
        )
        j_grid = np.interp(np.clip(grid["rho"], 0.0, 1.0), rho_dense, current_density)
        source = np.where(grid["mask"], -MU0 * grid["RR"] * j_grid, 0.0)
        psi, residual_relative = solve_fixed_source(grid, factorization, source)
        surfaces = extract_flux_surfaces(
            grid,
            psi,
            pressure_rho,
            pressure_values,
        )
        metrics, gates, arrays = stability_metrics(
            grid,
            psi,
            source,
            surfaces,
            pressure_rho,
            pressure_values,
            residual_relative,
        )
        metrics["iteration"] = iteration + 1
        history.append({
            "iteration": iteration + 1,
            "q_at_rho_0_96": metrics["q_at_rho_0_96"],
            "q_ratio_at_rho_0_96": metrics["q_ratio_at_rho_0_96"],
            "max_abs_q_target_relative_error": metrics[
                "max_abs_q_target_relative_error"
            ],
            "min_suydam_D": metrics["min_suydam_D"],
            "max_ballooning_alpha_over_alpha_crit": metrics[
                "max_ballooning_alpha_over_alpha_crit"
            ],
            "gates": gates,
        })
        final = {
            "metrics": metrics,
            "gates": gates,
            "arrays": arrays,
            "psi": psi,
            "source": source,
            "j_grid": j_grid,
            "enclosed_current": enclosed_current,
            "current_density": current_density,
            "q_design": q_design.copy(),
        }
        if gates["fixed_boundary_correction_screen_pass"]:
            break
        solved_rho = arrays["rho_eff"]
        solved_ratio = arrays["q_ratio"]
        correction_ratio = np.interp(
            rho_dense,
            solved_rho,
            solved_ratio,
            left=float(solved_ratio[0]),
            right=float(solved_ratio[-1]),
        )
        q_design = q_design * np.clip(1.0 / correction_ratio, 0.85, 1.15)
        q_design = np.maximum(q_design, 0.2)

    out_mhd = output_root / "MHD"
    q_input_path = out_mhd / "mhd_shear_target_toroidal_corrected.csv"
    write_profile_csv(
        q_input_path,
        rho_dense,
        pressure_dense,
        final["q_design"],
        q_target_dense,
        final["enclosed_current"],
        final["current_density"],
    )
    q_profile_path = out_mhd / "fixed_boundary_q_profile.csv"
    write_q_csv(q_profile_path, final["arrays"])
    field_path = out_mhd / "fixed_boundary_equilibrium_fields.npz"
    np.savez_compressed(
        field_path,
        R=grid["R"],
        Z=grid["Z"],
        RR=grid["RR"],
        ZZ=grid["ZZ"],
        rho=grid["rho"],
        mask=grid["mask"],
        psi=final["psi"],
        source=final["source"],
        j_phi=final["j_grid"],
        pressure=np.where(grid["mask"], np.interp(grid["rho"], pressure_rho, pressure_values), 0.0),
    )
    ripple_context = None
    ripple_report_path = input_root / "magnetic_correction_report.json"
    if ripple_report_path.is_file():
        ripple_report = json.loads(ripple_report_path.read_text(encoding="utf-8"))
        ripple_context = {
            "baseline_16_coil_edge_ripple_percent": ripple_report[
                "baseline_16_coil"
            ]["plasma_edge"]["ripple_percent"],
            "correction_48_coil_edge_ripple_percent": ripple_report[
                "correction_48_coil"
            ]["plasma_edge"]["ripple_percent"],
            "correction_48_coil_current_A": ripple_report["correction_48_coil"][
                "current_A"
            ],
            "correction_48_coil_current_limit_A": ripple_report["correction_48_coil"][
                "current_limit_A"
            ],
            "source_report": "magnetic_correction_report.json",
            "scope": "exact finite-segment Biot-Savart TF-ripple screen; analytic interleaved screening topology",
        }
    report = {
        "schema_version": "TOMAHAWK-FIXED-BOUNDARY-CORRECTION-1.0",
        "status": (
            "FIXED_BOUNDARY_STABILITY_SCREEN_PASS_WITH_3D_BLOCKER"
            if final["gates"]["fixed_boundary_correction_screen_pass"]
            else "FIXED_BOUNDARY_CORRECTION_DID_NOT_CLOSE"
        ),
        "baseline_user_reported_failure": {
            "q_target_at_rho_0_96": 5.808,
            "q_solved_at_rho_0_96": 6.98,
            "q_ratio_at_rho_0_96": 6.98 / 5.808,
            "min_suydam_D": -0.146,
            "max_ballooning_alpha_over_alpha_crit": 3.28,
            "provenance": "user-provided fixed-boundary run result in current task",
        },
        "method": {
            "equation": "Delta_star(psi) = -mu0 * R * j_phi",
            "operator": "same finite-difference Delta-star operator as the existing fixed-boundary screen",
            "flux_surface_q": "toroidal-flux derivative from solved psi surfaces using radial ray intersections",
            "inverse_update": "q_design <- q_design / (q_solved / q_target), clipped to 15 percent per iteration",
            "toroidal_precompensation": f"1 + {TOROIDAL_Q_DRIFT_EDGE:.2f} rho^2, inferred from reported 1.0-to-1.2 q drift",
            "diagnostic_caution": "Suydam and s-alpha values are local proxy diagnostics from this module's continuous radial-ray surfaces; cross-check against the project's exact independent diagnostic before promotion.",
        },
        "baseline_same_operator_q_drift": {
            "target_profile": "q(rho) = 1.20 + 5.00 rho^2",
            "q_target_at_rho_0_96": original_q_target_at_calibration,
            "q_solved_at_rho_0_96": original_q_at_calibration,
            "q_ratio_at_rho_0_96": original_q_at_calibration / original_q_target_at_calibration,
            "gs_residual_relative": original_residual,
            "provenance": "recomputed with this correction module's toroidal fixed-boundary operator",
        },
        "correction_profile": {
            "solved_q_target": "q(rho) = 1.20 + 2.00 rho + 3.16478587963 rho^4",
            "q_at_rho_0_96_target": Q_EDGE_TARGET,
            "current_profile_derivation": "j_phi from d/dr [2 pi B0 r^2 / (mu0 R0 q_design)]",
            "iterations_completed": len(history),
            "iteration_history": history,
        },
        "tf_ripple_screen": ripple_context,
        "fixed_boundary_candidate": final["metrics"],
        "mesh_convergence": (
            json.loads((out_mhd / "fixed_boundary_mesh_convergence.json").read_text(encoding="utf-8"))
            if (out_mhd / "fixed_boundary_mesh_convergence.json").is_file()
            else None
        ),
        "gates": {
            **final["gates"],
            "free_boundary_3D_MHD_pass": False,
            "qualified_design_pass": False,
        },
        "remaining_blockers": [
            "PF/shaping coil geometry, currents, and engineering limits",
            "free-boundary 3-D equilibrium and mgrid/MAKEGRID input",
            "self-consistent p(psi), F(psi), and plasma-current/current-drive closure",
            "nonlinear MHD stability spectrum",
            "orbit-resolved alpha transport",
            "qualified neutronics, CFD/CHT, and CHF",
        ],
    }
    report_path = output_root / "fixed_boundary_correction_report.json"
    write_json(report_path, report)
    input_contract = {
        "schema_version": "TOMAHAWK-FIXED-BOUNDARY-CORRECTION-INPUT-1.0",
        "status": "MODEL_DERIVED_FIXED_BOUNDARY_INPUT_NOT_QUALIFIED",
        "geometry": {
            "R0_m": R0_M,
            "a_m": A_M,
            "boundary": "fixed circular boundary",
            "tf_branch": "CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION",
        },
        "pressure_profile": "MHD/mhd_profile_sweep.csv",
        "corrected_current_profile": "MHD/mhd_shear_target_toroidal_corrected.csv",
        "solved_q_profile": "MHD/fixed_boundary_q_profile.csv",
        "field_archive": "MHD/fixed_boundary_equilibrium_fields.npz",
        "mesh_convergence": "MHD/fixed_boundary_mesh_convergence.json",
        "tf_ripple_screen": "magnetic_correction_report.json",
        "target_q": "q(rho) = 1.20 + 2.00 rho + 3.16478587963 rho^4",
        "solver": {
            "grid_nr": nr,
            "grid_nz": nz,
            "equation": "Delta_star(psi) = -mu0 * R * j_phi",
            "gs_residual_tolerance": 1.0e-10,
            "q_fit_tolerance_relative": 0.10,
        },
        "qualification": {
            "fixed_boundary_stability_screen": final["gates"][
                "fixed_boundary_correction_screen_pass"
            ],
            "free_boundary_3D_MHD": "BLOCKED_NO_PF_OR_MGRID_INPUT",
            "qualified_design": False,
        },
    }
    write_json(out_mhd / "mhd_input_fixed_boundary_correction.json", input_contract)
    manifest = {
        "schema_version": "TOMAHAWK-FIXED-BOUNDARY-CORRECTION-MANIFEST-1.0",
        "status": report["status"],
        "files": {},
    }
    for path in sorted(output_root.rglob("*")):
        if (
            path.is_file()
            and path.name not in {
                "fixed_boundary_correction_manifest.json",
                "fixed_boundary_correction_manifest_v2.json",
            }
            and "__pycache__" not in path.parts
        ):
            manifest["files"][path.relative_to(output_root).as_posix()] = sha256(path)
    write_json(output_root / "fixed_boundary_correction_manifest.json", manifest)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--nr", type=int, default=161)
    parser.add_argument("--nz", type=int, default=161)
    args = parser.parse_args()
    report = build_correction(args.input_root, args.output_root, args.nr, args.nz)
    print(json.dumps({
        "status": report["status"],
        "q_at_rho_0_96": report["fixed_boundary_candidate"]["q_at_rho_0_96"],
        "q_ratio_at_rho_0_96": report["fixed_boundary_candidate"]["q_ratio_at_rho_0_96"],
        "min_suydam_D": report["fixed_boundary_candidate"]["min_suydam_D"],
        "max_ballooning_alpha_over_alpha_crit": report["fixed_boundary_candidate"][
            "max_ballooning_alpha_over_alpha_crit"
        ],
        "fixed_boundary_correction_screen_pass": report["gates"][
            "fixed_boundary_correction_screen_pass"
        ],
        "qualified_design_pass": report["gates"]["qualified_design_pass"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
