# Tomahawk Rev2.2 — fast, reproducible Monte Carlo Kaggle cell
# Scope: parameter-space 0-D screening, not physical Monte Carlo transport.

import json
import math
import os
import platform
import time
import zipfile
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd

SEED = int(os.environ.get("TOMAHAWK_MC_SEED", "20260825"))
SMOKE_SAMPLES = int(os.environ.get("TOMAHAWK_MC_SMOKE", "16384"))
FULL_SAMPLES = int(os.environ.get("TOMAHAWK_MC_SAMPLES", "1000000"))
BATCH_SIZE = int(os.environ.get("TOMAHAWK_MC_BATCH", "65536"))
USE_GPU = os.environ.get("TOMAHAWK_USE_GPU", "1").lower() not in {"0", "false", "no"}

OUT_DIR = Path("/kaggle/working/tomahawk_rev22_fast_mc") if Path("/kaggle/working").exists() else Path.cwd() / "tomahawk_rev22_fast_mc"
OUT_DIR.mkdir(parents=True, exist_ok=True)

xp = np
cp = None
BACKEND = "NumPy/CPU"
GPU_NAME = "not used"
if USE_GPU:
    try:
        import cupy as cp
        if int(cp.cuda.runtime.getDeviceCount()) > 0:
            xp = cp
            BACKEND = "CuPy/GPU"
            GPU_NAME = cp.cuda.runtime.getDeviceProperties(0)["name"]
            if isinstance(GPU_NAME, bytes):
                GPU_NAME = GPU_NAME.decode(errors="replace")
    except Exception:
        xp, cp, BACKEND = np, None, "NumPy/CPU"

def cpu(value):
    return cp.asnumpy(value) if BACKEND == "CuPy/GPU" else np.asarray(value)

# R-MAPLA bookkeeping: 2.5 MJ/module at 10 Hz, distributed over 16 ports.
RMAPLA_PORTS = 16
RMAPLA_PULSE_ENERGY_J = 2.50e6
RMAPLA_REPETITION_HZ = 10.0
RMAPLA_WAVELENGTH_NM = 351.0
R0_M, A_M = 7.5, 3.0
angles = np.array([-60., -45., -30., -15., 15., 30., 45., 60.])
sequence = np.arange(RMAPLA_PORTS)
ring = sequence % 2 + 1
poloidal = angles[sequence // 2]
phi = np.deg2rad(sequence * 22.5)
theta = np.deg2rad(poloidal)
r_minor = 0.92 * A_M
position = np.column_stack([
    (R0_M + r_minor * np.cos(theta)) * np.cos(phi),
    (R0_M + r_minor * np.cos(theta)) * np.sin(phi),
    r_minor * np.sin(theta),
])
focal_z = 0.05 * np.sin(theta)
direction = np.column_stack([np.zeros(RMAPLA_PORTS), np.zeros(RMAPLA_PORTS), focal_z]) - position
direction /= np.linalg.norm(direction, axis=1)[:, None]
geometry_checks = {
    "16_ports": len(sequence) == 16,
    "2_rings": len(np.unique(ring)) == 2,
    "8_ports_each": bool(np.all(np.bincount(ring)[1:] == 8)),
    "22_5_degree_step": bool(np.allclose(np.diff(np.r_[sequence * 22.5, 360.0]), 22.5)),
    "poloidal_set": bool(np.array_equal(np.sort(np.unique(poloidal)), angles)),
    "unit_beam_directions": bool(np.allclose(np.linalg.norm(direction, axis=1), 1.0)),
}
geometry_checks["all_pass"] = all(geometry_checks.values())

per_port_energy_J = RMAPLA_PULSE_ENERGY_J / RMAPLA_PORTS
pulse_checks = {
    "energy_conservation": bool(np.isclose(per_port_energy_J * RMAPLA_PORTS, RMAPLA_PULSE_ENERGY_J)),
    "module_average_power_MW": RMAPLA_PULSE_ENERGY_J * RMAPLA_REPETITION_HZ / 1e6,
    "per_port_pulse_energy_kJ": per_port_energy_J / 1e3,
    "per_port_average_power_MW": per_port_energy_J * RMAPLA_REPETITION_HZ / 1e6,
}

# Profile quadrature.
x, w = np.polynomial.legendre.leggauss(32)
rho = 0.5 * (x + 1.0)
weights = 0.5 * w * 2.0 * rho
rho_xp = xp.asarray(rho, dtype=xp.float64)[None, :]
weights_xp = xp.asarray(weights, dtype=xp.float64)[None, :]
base_xp = xp.maximum(0.0, 1.0 - rho_xp ** 2)

MU0 = 4.0e-7 * math.pi
AMU = 1.66053906660e-27
KEV_TO_J = 1.0e3 * 1.602176634e-19
MEV_TO_J = 1.0e6 * 1.602176634e-19
M_T = 3.01604928199 * AMU
E_FUSION = 17.6 * MEV_TO_J
ALPHA_FRACTION = 3.5 / 17.6
NEUTRON_FRACTION = 14.1 / 17.6
VOLUME_M3 = 950.0
N_D0_BASE = 1.2e20
N_T0_BASE = 1.2e20
ACTIVE_MODULES = 10

PARAMETER_RANGES = OrderedDict([
    ("gamma_n", (0.50, 1.00)),
    ("density_scale", (0.85, 1.20)),
    ("fuel_fraction", (0.80, 1.00)),
    ("deuterium_fraction", (0.45, 0.55)),
    ("Ti0_keV", (15.0, 25.0)),
    ("Ti_edge_keV", (0.20, 5.00)),
    ("gamma_T", (0.50, 2.00)),
    ("Te_to_Ti", (0.80, 1.20)),
    ("B0_T", (12.0, 16.0)),
    ("tau_E_s", (0.35, 2.00)),
    ("Z_eff", (1.00, 2.00)),
    ("alpha_deposition", (0.75, 0.98)),
    ("laser_coupling", (0.60, 0.90)),
    ("repetition_rate_Hz", (8.0, 12.0)),
    ("wallplug_efficiency", (0.10, 0.20)),
    ("neutron_heat_capture", (0.90, 0.99)),
    ("alpha_heat_capture", (0.85, 0.99)),
    ("high_grade_heat_fraction", (0.70, 0.98)),
    ("eta_high_grade", (0.36, 0.45)),
    ("eta_low_grade", (0.08, 0.20)),
    ("nonlaser_aux_GWe", (0.60, 1.60)),
    ("TBR", (0.88, 1.20)),
    ("tritium_process_eff", (0.970, 0.995)),
])
PARAMETER_NAMES = list(PARAMETER_RANGES)

# A separate, explicitly labeled local robustness envelope. These ranges are
# not a claim about nature; they are the proposed tolerances for a controlled
# Rev2.2 design after the broad feasibility screen. Replace them with measured
# distributions once hardware, neutronics, and transport data exist.
LOCAL_PARAMETER_RANGES = OrderedDict([
    ("gamma_n", (0.58, 0.76)),
    ("density_scale", (1.03, 1.20)),
    ("fuel_fraction", (0.90, 1.00)),
    ("deuterium_fraction", (0.46, 0.54)),
    ("Ti0_keV", (20.0, 25.0)),
    ("Ti_edge_keV", (0.60, 2.50)),
    ("gamma_T", (0.55, 1.00)),
    ("Te_to_Ti", (0.90, 1.10)),
    ("B0_T", (12.5, 15.5)),
    ("tau_E_s", (1.20, 2.00)),
    ("Z_eff", (1.00, 1.50)),
    ("alpha_deposition", (0.85, 0.98)),
    ("laser_coupling", (0.75, 0.90)),
    ("repetition_rate_Hz", (8.5, 11.5)),
    ("wallplug_efficiency", (0.16, 0.20)),
    ("neutron_heat_capture", (0.93, 0.99)),
    ("alpha_heat_capture", (0.88, 0.99)),
    ("high_grade_heat_fraction", (0.85, 0.98)),
    ("eta_high_grade", (0.37, 0.45)),
    ("eta_low_grade", (0.09, 0.18)),
    ("nonlaser_aux_GWe", (0.70, 1.25)),
    ("TBR", (1.15, 1.20)),
    ("tritium_process_eff", (0.975, 0.995)),
])

def dt_reactivity(T):
    T = xp.clip(T, 0.2, 100.0)
    BG, mrc2 = 34.3827, 1.124656e6
    C1, C2, C3, C4 = 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3
    C5, C6, C7 = 1.35000e-2, -1.06750e-4, 1.36600e-5
    numerator = T * (C2 + T * (C4 + T * C6))
    denominator = 1.0 + T * (C3 + T * (C5 + T * C7))
    t = T / (1.0 - numerator / denominator)
    xi = (BG ** 2 / (4.0 * t)) ** (1.0 / 3.0)
    return 1.0e-6 * C1 * t * xp.sqrt(xi / (mrc2 * T ** 3)) * xp.exp(-3.0 * xi)

def evaluate(parameter_matrix):
    p = xp.asarray(parameter_matrix, dtype=xp.float64)
    c = {name: p[:, i:i + 1] for i, name in enumerate(PARAMETER_NAMES)}
    n_center = (N_D0_BASE + N_T0_BASE) * c["density_scale"]
    fuel_center = n_center * c["fuel_fraction"]
    density_shape = base_xp ** c["gamma_n"]
    temp_shape = base_xp ** c["gamma_T"]
    Ti = c["Ti_edge_keV"] + (c["Ti0_keV"] - c["Ti_edge_keV"]) * temp_shape
    Te = xp.maximum(0.2, Ti * c["Te_to_Ti"])
    n_i = n_center * density_shape
    n_D = fuel_center * c["deuterium_fraction"] * density_shape
    n_T = fuel_center * (1.0 - c["deuterium_fraction"]) * density_shape
    reaction = xp.sum(weights_xp * n_D * n_T * dt_reactivity(Ti), axis=1)
    pressure = xp.sum(weights_xp * (n_i * Ti + n_i * Te) * KEV_TO_J, axis=1)
    brem_shape = xp.sum(weights_xp * n_i ** 2 * xp.sqrt(Te), axis=1)
    reaction_rate = VOLUME_M3 * reaction
    fusion_W = reaction_rate * E_FUSION
    alpha_W = fusion_W * ALPHA_FRACTION
    neutron_W = fusion_W * NEUTRON_FRACTION
    alpha_dep_W = alpha_W * c["alpha_deposition"][:, 0]
    brem_W = VOLUME_M3 * 5.35e-37 * c["Z_eff"][:, 0] * brem_shape
    thermal_J = 1.5 * VOLUME_M3 * pressure
    transport_W = thermal_J / c["tau_E_s"][:, 0]
    laser_optical_W = RMAPLA_PULSE_ENERGY_J * c["repetition_rate_Hz"][:, 0]
    laser_absorbed_W = laser_optical_W * c["laser_coupling"][:, 0]
    self_ratio = alpha_dep_W / xp.maximum(brem_W + transport_W, 1.0)
    target_gain = (fusion_W / c["repetition_rate_Hz"][:, 0]) / RMAPLA_PULSE_ENERGY_J
    beta = 2.0 * MU0 * pressure / c["B0_T"][:, 0] ** 2
    captured_W = neutron_W * c["neutron_heat_capture"][:, 0] + alpha_W * c["alpha_heat_capture"][:, 0] + laser_absorbed_W
    high_W = captured_W * c["high_grade_heat_fraction"][:, 0]
    low_W = captured_W - high_W
    gross_module_W = c["eta_high_grade"][:, 0] * high_W + c["eta_low_grade"][:, 0] * low_W
    gross_hub_GWe = gross_module_W * ACTIVE_MODULES / 1e9
    laser_electric_GWe = laser_optical_W / c["wallplug_efficiency"][:, 0] * ACTIVE_MODULES / 1e9
    recirc_GWe = laser_electric_GWe + c["nonlaser_aux_GWe"][:, 0]
    net_GWe = gross_hub_GWe - recirc_GWe
    burn_g_h = reaction_rate * M_T * 1000.0 * 3600.0 * ACTIVE_MODULES
    surplus_g_h = c["tritium_process_eff"][:, 0] * c["TBR"][:, 0] * burn_g_h - burn_g_h
    tau_required = xp.where(alpha_dep_W > brem_W, thermal_J / xp.maximum(alpha_dep_W - brem_W, 1.0), xp.inf)
    tau_margin = c["tau_E_s"][:, 0] / xp.maximum(tau_required, 1e-30) - 1.0
    surplus_ratio = 1.0 + surplus_g_h / xp.maximum(burn_g_h, 1.0)
    gates = OrderedDict([
        ("fusion", fusion_W >= 5e9),
        ("gain", target_gain >= 200.0),
        ("wallplug", c["wallplug_efficiency"][:, 0] >= 0.15),
        ("self_heating", self_ratio >= 1.0),
        ("TBR", c["TBR"][:, 0] >= 1.15),
        ("tritium_surplus", surplus_g_h >= 0.0),
        ("captured_heat", captured_W >= 5e9),
        ("gross_electric", gross_hub_GWe >= 20.0),
        ("recirculating", recirc_GWe <= 3.0),
        ("net_electric", net_GWe >= 17.0),
    ])
    gate_all = xp.ones_like(fusion_W, dtype=bool)
    for value in gates.values():
        gate_all &= value
    normalized = xp.stack([
        fusion_W / 5e9, target_gain / 200.0, c["wallplug_efficiency"][:, 0] / 0.15,
        self_ratio, c["TBR"][:, 0] / 1.15, surplus_ratio, captured_W / 5e9,
        gross_hub_GWe / 20.0, 3.0 / xp.maximum(recirc_GWe, 1e-12), net_GWe / 17.0,
    ], axis=1)
    result = {
        "fusion_GW_module": fusion_W / 1e9,
        "target_gain": target_gain,
        "self_heating_ratio": self_ratio,
        "beta_percent": 100.0 * beta,
        "captured_heat_GWth_module": captured_W / 1e9,
        "gross_GWe_hub": gross_hub_GWe,
        "recirculating_GWe_hub": recirc_GWe,
        "net_GWe_hub": net_GWe,
        "T_burn_g_h_hub": burn_g_h,
        "T_surplus_g_h_hub": surplus_g_h,
        "tau_E_required_alpha_self_heating_s": tau_required,
        "tau_E_margin_ratio": tau_margin,
        "robust_score": xp.min(normalized, axis=1),
        "gate_all": gate_all,
    }
    for name, value in gates.items():
        result["gate_" + name] = value
    return {name: cpu(value).reshape(-1) for name, value in result.items()}

def add_parameters(matrix, result):
    frame = pd.DataFrame({name: matrix[:, i] for i, name in enumerate(PARAMETER_NAMES)})
    for name, value in result.items():
        frame[name] = value
    return frame

def run_mc(n_samples, seed, ranges=PARAMETER_RANGES, label="full"):
    start = time.perf_counter()
    rng = np.random.default_rng(seed)
    range_names = list(ranges)
    lows = np.array([v[0] for v in ranges.values()])
    highs = np.array([v[1] for v in ranges.values()])
    gate_names = ["fusion", "gain", "wallplug", "self_heating", "TBR", "tritium_surplus", "captured_heat", "gross_electric", "recirculating", "net_electric"]
    gate_counts = {name: 0 for name in gate_names}
    passed_frames = []
    convergence = []
    processed = 0
    next_checkpoint = min(100000, n_samples)
    for start_index in range(0, n_samples, BATCH_SIZE):
        count = min(BATCH_SIZE, n_samples - start_index)
        matrix = lows + rng.random((count, len(PARAMETER_NAMES))) * (highs - lows)
        result = evaluate(matrix)
        for name in gate_names:
            gate_counts[name] += int(np.count_nonzero(result["gate_" + name]))
        mask = result["gate_all"]
        if np.any(mask):
            frame = add_parameters(matrix[mask], {name: value[mask] for name, value in result.items()})
            frame.insert(0, "sample_id", np.flatnonzero(mask) + start_index)
            passed_frames.append(frame)
        processed += count
        if processed >= next_checkpoint or processed == n_samples:
            convergence.append({"processed_samples": processed, "pass_count": sum(len(x) for x in passed_frames), "pass_percent": 100.0 * sum(len(x) for x in passed_frames) / processed})
            next_checkpoint = min(n_samples, next_checkpoint + 100000)
    passed = pd.concat(passed_frames, ignore_index=True) if passed_frames else pd.DataFrame()
    if len(passed):
        passed = passed.sort_values("robust_score", ascending=False).reset_index(drop=True)
    convergence = pd.DataFrame(convergence)
    gates = pd.DataFrame([{"gate": name, "pass_count": count, "pass_percent": 100.0 * count / n_samples} for name, count in gate_counts.items()])
    summary = {
        "range_label": label,
        "backend": BACKEND,
        "gpu": GPU_NAME,
        "seed": seed,
        "samples": int(n_samples),
        "batch_size": int(BATCH_SIZE),
        "elapsed_seconds": time.perf_counter() - start,
        "simultaneous_gate_passes": int(len(passed)),
        "simultaneous_gate_pass_percent": 100.0 * len(passed) / n_samples,
        "best_passing_robust_score": None if not len(passed) else float(passed.iloc[0]["robust_score"]),
        "scope": "parameter-space 0-D Monte Carlo screen; not physical validation",
    }
    return passed, convergence, gates, summary

print({"backend": BACKEND, "gpu": GPU_NAME, "seed": SEED, "smoke": SMOKE_SAMPLES, "full": FULL_SAMPLES, "batch": BATCH_SIZE})
print("Geometry:", geometry_checks)
print("Pulse:", pulse_checks)

reference_matrix = np.array([[0.657, 1.06, 1.0, 0.5, 20.0, 1.25, 0.75, 1.0, 14.0, 1.36, 1.0, 0.90, 0.80, 10.0, 0.18, 0.98, 0.95, 0.95, 0.40, 0.12, 1.333, 1.18, 0.995]])
reference = add_parameters(reference_matrix, evaluate(reference_matrix))
reference.to_csv(OUT_DIR / "reference_metrics.csv", index=False)
print("Reference metrics:")
print(reference[["fusion_GW_module", "target_gain", "self_heating_ratio", "tau_E_required_alpha_self_heating_s", "tau_E_margin_ratio", "gross_GWe_hub", "recirculating_GWe_hub", "net_GWe_hub", "gate_all"]].round(6).to_string(index=False))

smoke, smoke_conv, smoke_gates, smoke_summary = run_mc(SMOKE_SAMPLES, SEED, PARAMETER_RANGES, "broad_smoke")
full, convergence, gate_rates, summary = run_mc(FULL_SAMPLES, SEED + 1, PARAMETER_RANGES, "broad_global")
local, local_convergence, local_gate_rates, local_summary = run_mc(FULL_SAMPLES, SEED + 2, LOCAL_PARAMETER_RANGES, "local_robustness")
print("Smoke summary:", json.dumps(smoke_summary, indent=2))
print("Broad global summary:", json.dumps(summary, indent=2))
print("Local robustness summary:", json.dumps(local_summary, indent=2))
if len(full):
    full.head(100).to_csv(OUT_DIR / "top_passing_cases.csv", index=False)
    print("Best interior passing case:")
    print(full.head(1)[["sample_id", "robust_score", "fusion_GW_module", "target_gain", "self_heating_ratio", "tau_E_margin_ratio", "captured_heat_GWth_module", "gross_GWe_hub", "recirculating_GWe_hub", "net_GWe_hub", "density_scale", "Ti0_keV", "tau_E_s", "TBR", "wallplug_efficiency"]].round(6).to_string(index=False))
else:
    pd.DataFrame().to_csv(OUT_DIR / "top_passing_cases.csv", index=False)
convergence.to_csv(OUT_DIR / "convergence.csv", index=False)
gate_rates.to_csv(OUT_DIR / "individual_gate_rates.csv", index=False)
(OUT_DIR / "local_convergence.csv").write_text(local_convergence.to_csv(index=False), encoding="utf-8")
local_gate_rates.to_csv(OUT_DIR / "local_individual_gate_rates.csv", index=False)
if len(local):
    local.head(100).to_csv(OUT_DIR / "local_top_passing_cases.csv", index=False)
else:
    pd.DataFrame().to_csv(OUT_DIR / "local_top_passing_cases.csv", index=False)
(OUT_DIR / "summary.json").write_text(json.dumps({"broad_global": summary, "local_robustness": local_summary}, indent=2), encoding="utf-8")
(OUT_DIR / "run_manifest.json").write_text(json.dumps({
    "model": "Tomahawk Rev2.2 R-MAPLA fast vectorized Monte Carlo",
    "python": platform.python_version(),
    "geometry_checks": geometry_checks,
    "pulse_checks": pulse_checks,
    "reference": reference.to_dict(orient="records")[0],
    "broad_global_summary": summary,
    "local_robustness_summary": local_summary,
    "local_acceptance_target": {
        "required_pass_percent": 60.0,
        "observed_pass_percent": local_summary["simultaneous_gate_pass_percent"],
        "pass": local_summary["simultaneous_gate_pass_percent"] >= 60.0,
    },
    "limits": [
        "This is a parameter-space screen, not Monte Carlo neutron transport.",
        "No 3-D equilibrium, MHD stability, target hydrodynamics, RF wave solve, neutronics, structural FEA, or experiment is performed.",
        "Pass percentages are conditional on the declared uniform parameter ranges.",
    ],
}, indent=2, default=float), encoding="utf-8")
zip_path = OUT_DIR / "Tomahawk_Rev22_Fast_MC_Results.zip"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(OUT_DIR.rglob("*")):
        if path.is_file() and path != zip_path:
            archive.write(path, path.relative_to(OUT_DIR))
print("Saved:", zip_path)
