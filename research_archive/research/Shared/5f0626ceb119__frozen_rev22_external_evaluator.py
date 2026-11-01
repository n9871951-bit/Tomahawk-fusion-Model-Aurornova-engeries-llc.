# Tomahawk Rev2.2 — frozen external-input evaluator
# The model equations are fixed here; all sampled values come from an external CSV.

import json
import math
import os
import platform
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

PARAMETER_NAMES = [
    "gamma_n", "density_scale", "fuel_fraction", "deuterium_fraction",
    "Ti0_keV", "Ti_edge_keV", "gamma_T", "Te_to_Ti", "B0_T", "tau_E_s",
    "Z_eff", "alpha_deposition", "laser_coupling", "repetition_rate_Hz",
    "wallplug_efficiency", "neutron_heat_capture", "alpha_heat_capture",
    "high_grade_heat_fraction", "eta_high_grade", "eta_low_grade",
    "nonlaser_aux_GWe", "TBR", "tritium_process_eff",
]

OUT_DIR = Path("/kaggle/working/tomahawk_rev22_external_eval") if Path("/kaggle/working").exists() else Path.cwd() / "tomahawk_rev22_external_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)
BATCH_SIZE = int(os.environ.get("TOMAHAWK_INPUT_BATCH", "65536"))

def find_input_file():
    requested = os.environ.get("TOMAHAWK_INPUT_CSV", "").strip()
    if requested:
        return Path(requested).expanduser().resolve()
    preferred_names = [
        "Tomahawk_Rev22_Controlled_Envelope_v2_Input_Dataset.csv",
        "Tomahawk_Rev22_Controlled_Envelope_Input_Dataset.csv",
    ]
    candidates = [Path.cwd() / name for name in preferred_names]
    if Path("/kaggle/input").exists():
        for name in preferred_names:
            candidates.extend(Path("/kaggle/input").rglob(name))
        candidates.extend(Path("/kaggle/input").rglob("Tomahawk_Rev22_*_Input_Dataset.csv"))
    candidates.extend(Path.cwd().glob("Tomahawk_Rev22_*_Input_Dataset.csv"))
    unique_candidates = []
    seen = set()
    for candidate in candidates:
        resolved = str(candidate.resolve())
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(candidate)
    for candidate in unique_candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("No external input CSV found. Set TOMAHAWK_INPUT_CSV to the uploaded dataset path.")

def bosch_hale_dt_reactivity(T):
    T = np.clip(np.asarray(T, dtype=np.float64), 0.2, 100.0)
    BG = 34.3827
    mrc2 = 1.124656e6
    C1, C2, C3, C4 = 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3
    C5, C6, C7 = 1.35000e-2, -1.06750e-4, 1.36600e-5
    numerator = T * (C2 + T * (C4 + T * C6))
    denominator = 1.0 + T * (C3 + T * (C5 + T * C7))
    theta = T / (1.0 - numerator / denominator)
    xi = (BG ** 2 / (4.0 * theta)) ** (1.0 / 3.0)
    return 1.0e-6 * C1 * theta * np.sqrt(xi / (mrc2 * T ** 3)) * np.exp(-3.0 * xi)

legendre_x, legendre_w = np.polynomial.legendre.leggauss(32)
RHO = 0.5 * (legendre_x + 1.0)
RHO_WEIGHTS = 0.5 * legendre_w * 2.0 * RHO
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

def evaluate_batch(params):
    """Frozen Rev2.2 equations; params is a dict of equal-length NumPy arrays."""
    n_cases = len(next(iter(params.values())))
    gamma_n = params["gamma_n"]
    gamma_T = params["gamma_T"]
    total_ion_center = (N_D0_BASE + N_T0_BASE) * params["density_scale"]
    fuel_center = total_ion_center * params["fuel_fraction"]
    n_D0 = fuel_center * params["deuterium_fraction"]
    n_T0 = fuel_center * (1.0 - params["deuterium_fraction"])
    integral_reaction = np.zeros(n_cases)
    integral_pressure = np.zeros(n_cases)
    integral_brem_shape = np.zeros(n_cases)
    for rho, weight in zip(RHO, RHO_WEIGHTS):
        base = max(0.0, 1.0 - float(rho) ** 2)
        density_shape = base ** gamma_n
        temperature_shape = base ** gamma_T
        Ti = params["Ti_edge_keV"] + (params["Ti0_keV"] - params["Ti_edge_keV"]) * temperature_shape
        Te = np.maximum(0.2, Ti * params["Te_to_Ti"])
        n_i = total_ion_center * density_shape
        n_D = n_D0 * density_shape
        n_T = n_T0 * density_shape
        integral_reaction += weight * n_D * n_T * bosch_hale_dt_reactivity(Ti)
        integral_pressure += weight * (n_i * Ti + n_i * Te) * KEV_TO_J
        integral_brem_shape += weight * n_i ** 2 * np.sqrt(Te)
    reaction_rate = VOLUME_M3 * integral_reaction
    fusion_W = reaction_rate * E_FUSION
    alpha_W = fusion_W * ALPHA_FRACTION
    neutron_W = fusion_W * NEUTRON_FRACTION
    alpha_deposited_W = alpha_W * params["alpha_deposition"]
    brem_W = VOLUME_M3 * 5.35e-37 * params["Z_eff"] * integral_brem_shape
    thermal_energy_J = 1.5 * VOLUME_M3 * integral_pressure
    transport_W = thermal_energy_J / params["tau_E_s"]
    laser_optical_W = 2.50e6 * params["repetition_rate_Hz"]
    laser_absorbed_W = laser_optical_W * params["laser_coupling"]
    self_ratio = alpha_deposited_W / np.maximum(brem_W + transport_W, 1.0)
    target_gain = (fusion_W / params["repetition_rate_Hz"]) / 2.50e6
    beta = 2.0 * MU0 * integral_pressure / params["B0_T"] ** 2
    captured_W = neutron_W * params["neutron_heat_capture"] + alpha_W * params["alpha_heat_capture"] + laser_absorbed_W
    high_grade_W = captured_W * params["high_grade_heat_fraction"]
    low_grade_W = captured_W - high_grade_W
    gross_module_W = params["eta_high_grade"] * high_grade_W + params["eta_low_grade"] * low_grade_W
    gross_hub_GWe = gross_module_W * ACTIVE_MODULES / 1.0e9
    laser_electric_hub_GWe = laser_optical_W / params["wallplug_efficiency"] * ACTIVE_MODULES / 1.0e9
    recirc_hub_GWe = laser_electric_hub_GWe + params["nonlaser_aux_GWe"]
    net_hub_GWe = gross_hub_GWe - recirc_hub_GWe
    t_burn_g_h = reaction_rate * M_T * 1000.0 * 3600.0 * ACTIVE_MODULES
    t_surplus_g_h = params["tritium_process_eff"] * params["TBR"] * t_burn_g_h - t_burn_g_h
    tau_required = np.where(alpha_deposited_W > brem_W, thermal_energy_J / np.maximum(alpha_deposited_W - brem_W, 1.0), np.inf)
    tau_margin = params["tau_E_s"] / np.maximum(tau_required, 1.0e-30) - 1.0
    gate_arrays = {
        "fusion": fusion_W >= 5.0e9,
        "gain": target_gain >= 200.0,
        "wallplug": params["wallplug_efficiency"] >= 0.15,
        "self_heating": self_ratio >= 1.0,
        "TBR": params["TBR"] >= 1.15,
        "tritium_surplus": t_surplus_g_h >= 0.0,
        "captured_heat": captured_W >= 5.0e9,
        "gross_electric": gross_hub_GWe >= 20.0,
        "recirculating": recirc_hub_GWe <= 3.0,
        "net_electric": net_hub_GWe >= 17.0,
    }
    gate_all = np.ones(n_cases, dtype=bool)
    for values in gate_arrays.values():
        gate_all &= values
    result = {
        "fusion_GW_module": fusion_W / 1.0e9,
        "target_gain": target_gain,
        "self_heating_ratio": self_ratio,
        "beta_percent": 100.0 * beta,
        "captured_heat_GWth_module": captured_W / 1.0e9,
        "gross_GWe_hub": gross_hub_GWe,
        "recirculating_GWe_hub": recirc_hub_GWe,
        "net_GWe_hub": net_hub_GWe,
        "T_burn_g_h_hub": t_burn_g_h,
        "T_surplus_g_h_hub": t_surplus_g_h,
        "tau_E_required_alpha_self_heating_s": tau_required,
        "tau_E_margin_ratio": tau_margin,
        "gate_all": gate_all,
    }
    for name, values in gate_arrays.items():
        result["gate_" + name] = values
    return result

input_path = find_input_file()
input_frame = pd.read_csv(input_path)
missing = [name for name in PARAMETER_NAMES if name not in input_frame.columns]
if missing:
    raise ValueError(f"Input dataset is missing columns: {missing}")
if not np.isfinite(input_frame[PARAMETER_NAMES].to_numpy(dtype=np.float64)).all():
    raise ValueError("Input dataset contains non-finite parameter values.")
if "dataset_id" in input_frame.columns:
    dataset_ids = sorted(input_frame["dataset_id"].astype(str).unique().tolist())
    print("Input dataset ID:", dataset_ids)
    if any("CONTROLLED_ENVELOPE" in value for value in dataset_ids):
        if float(input_frame["TBR"].min()) < 1.15 or float(input_frame["wallplug_efficiency"].min()) < 0.16:
            raise ValueError("Controlled-envelope dataset failed its range signature; broad inputs may have been uploaded by mistake.")

start = time.perf_counter()
pieces = []
for start_index in range(0, len(input_frame), BATCH_SIZE):
    stop = min(start_index + BATCH_SIZE, len(input_frame))
    block = input_frame.iloc[start_index:stop].copy()
    params = {name: block[name].to_numpy(dtype=np.float64) for name in PARAMETER_NAMES}
    metrics = evaluate_batch(params)
    metric_frame = pd.DataFrame(metrics, index=block.index)
    pieces.append(pd.concat([block, metric_frame], axis=1))
result = pd.concat(pieces, ignore_index=True)
gate_names = [name for name in result.columns if name.startswith("gate_") and name != "gate_all"]
pass_count = int(result["gate_all"].sum())
summary = {
    "model": "Tomahawk Rev2.2 frozen external-input evaluator",
    "input_dataset": str(input_path),
    "rows": int(len(result)),
    "batch_size": BATCH_SIZE,
    "elapsed_seconds": time.perf_counter() - start,
    "simultaneous_gate_passes": pass_count,
    "simultaneous_gate_pass_percent": 100.0 * pass_count / len(result),
    "individual_gate_pass_percent": {name[5:]: 100.0 * float(result[name].mean()) for name in gate_names},
    "scope": "external-input 0-D parameter-space evaluation; not physical validation",
}
result.to_csv(OUT_DIR / "evaluated_cases.csv", index=False)
(OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
if pass_count:
    result[result["gate_all"]].sort_values("net_GWe_hub", ascending=False).head(100).to_csv(OUT_DIR / "passing_cases.csv", index=False)
else:
    pd.DataFrame().to_csv(OUT_DIR / "passing_cases.csv", index=False)
zip_path = OUT_DIR / "Tomahawk_Rev22_External_Input_Evaluation_Results.zip"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(OUT_DIR.rglob("*")):
        if path.is_file() and path != zip_path:
            archive.write(path, path.relative_to(OUT_DIR))
print(json.dumps(summary, indent=2))
print("Saved result bundle:", zip_path)
