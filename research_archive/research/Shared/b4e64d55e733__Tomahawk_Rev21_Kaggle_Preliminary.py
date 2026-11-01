"""
Tomahawk Fusion Architecture, Revision 2.1
Kaggle preliminary physics and plant-balance screening runner

Purpose
-------
This program converts the corrected Revision 2.1 equations into a reproducible
parameter-screening run suitable for a Kaggle notebook. It is intended to
produce preliminary evidence for an Argonne discussion. It is not a 3-D MHD,
target-hydrodynamics, neutronics, structural-FEA, or power-cycle validation.

Kaggle use
----------
1. Create a Kaggle notebook with Internet OFF; CPU is sufficient.
2. Use the companion .ipynb notebook for individually testable cells, or upload
   this file and run:  %run /kaggle/input/<dataset-name>/Tomahawk_Rev21_Kaggle_Preliminary.py
3. The default full run uses up to 9.25 hours and writes its deliverables under
   /kaggle/working. It normally finishes earlier if the requested scan closes.
4. Download Tomahawk_Rev21_Kaggle_Preliminary_Results.zip from notebook Output.

Optional environment controls
-----------------------------
TOMAHAWK_RUN_MODE=smoke|standard|full   (default: full)
TOMAHAWK_MAX_HOURS=9.25                 (default: 9.25)
TOMAHAWK_SAMPLES=<integer>              (overrides mode sample count)
TOMAHAWK_SEED=<integer>                 (default: 20260824)
TOMAHAWK_OUTPUT_ROOT=<absolute path>     (default: /kaggle/working)

Model basis
-----------
- Bosch-Hale D-T Maxwellian reactivity fit.
- Self-similar radial flux surfaces with normalized volume weight 2*rho d-rho.
- Ten active modules plus two hot standbys.
- 351 nm, 2.50 MJ/module-shot, nominal 10 Hz ultraviolet laser driver.
- 5.00 GW fusion-source and 5.00 GWth captured-heat targets per active module.
- 17.0 GWe net hub target, evaluated from a decomposed two-loop heat cycle.
- Beryllium-free aqueous lithium-salt breeder cases are represented only by
  TBR and process-efficiency scans; no TBR is claimed without neutronics.

The code deliberately keeps targets, calculated quantities, and provisional
screening assumptions separate.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
import traceback
import warnings
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


# Keep numerical libraries from oversubscribing a small Kaggle CPU instance.
_CPU_COUNT = max(1, os.cpu_count() or 1)
_THREADS = str(min(8, _CPU_COUNT))
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name, _THREADS)
os.environ.setdefault("MPLCONFIGDIR", "/tmp/tomahawk-matplotlib")

import numpy as np
import pandas as pd

# No SciPy, scikit-learn, SALib, pyarrow, or custom package is required.
# Matplotlib is optional so a missing plotting package cannot stop the scan.
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOTS_AVAILABLE = True
except ModuleNotFoundError:
    matplotlib = None
    plt = None
    PLOTS_AVAILABLE = False

warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---------------------------------------------------------------------------
# Configuration and physical constants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunConfig:
    run_mode: str
    requested_samples: int
    batch_size: int
    quadrature_nodes: int
    reservoir_rows: int
    trees: int
    top_rows: int
    max_runtime_hours: float
    reserve_minutes: float
    seed: int
    save_full_chunks: bool = True


def build_config() -> RunConfig:
    mode = os.getenv("TOMAHAWK_RUN_MODE", "full").strip().lower()
    modes = {
        "smoke": dict(samples=2**13, batch=2**11, quad=20, reservoir=6000, trees=40, top=500),
        "standard": dict(samples=2**18, batch=2**14, quad=28, reservoir=80000, trees=160, top=2500),
        "full": dict(samples=2**21, batch=2**16, quad=32, reservoir=200000, trees=300, top=5000),
    }
    if mode not in modes:
        raise ValueError("TOMAHAWK_RUN_MODE must be smoke, standard, or full")
    selected = modes[mode]
    requested = int(os.getenv("TOMAHAWK_SAMPLES", str(selected["samples"])))
    if requested < 1024:
        raise ValueError("TOMAHAWK_SAMPLES must be at least 1024")
    return RunConfig(
        run_mode=mode,
        requested_samples=requested,
        batch_size=min(selected["batch"], requested),
        quadrature_nodes=selected["quad"],
        reservoir_rows=min(selected["reservoir"], requested),
        trees=selected["trees"],
        top_rows=selected["top"],
        max_runtime_hours=float(os.getenv("TOMAHAWK_MAX_HOURS", "9.25")),
        reserve_minutes=15.0,
        seed=int(os.getenv("TOMAHAWK_SEED", "20260824")),
        save_full_chunks=True,
    )


MU0 = 4.0e-7 * math.pi
KB = 1.380649e-23
E_CHARGE = 1.602176634e-19
AMU = 1.66053906660e-27
KEV_TO_J = 1.0e3 * E_CHARGE
MEV_TO_J = 1.0e6 * E_CHARGE
M_D = 2.01410177812 * AMU
M_T = 3.01604928199 * AMU
E_FUSION = 17.6 * MEV_TO_J
E_ALPHA = 3.5 * MEV_TO_J
E_NEUTRON = 14.1 * MEV_TO_J
ALPHA_FRACTION = 3.5 / 17.6
NEUTRON_FRACTION = 14.1 / 17.6

ACTIVE_MODULES = 10
HOT_STANDBY_MODULES = 2
R0_M = 7.5
A_M = 3.0
CAD_PLASMA_VOLUME_M3 = 950.0
CIRCULAR_TORUS_VOLUME_M3 = 2.0 * math.pi**2 * R0_M * A_M**2
CIRCULAR_FIRST_WALL_AREA_M2 = 4.0 * math.pi**2 * R0_M * A_M
PREFILL_PRESSURE_PA = 0.300
PREFILL_TEMPERATURE_K = 300.0
N_D0_BASE = 1.2e20
N_T0_BASE = 1.2e20
B_PEAK_CONDUCTOR_T = 35.0
LASER_WAVELENGTH_UM = 0.351
LASER_ENERGY_J = 2.50e6
FUSION_SOURCE_TARGET_W_PER_MODULE = 5.00e9
CAPTURED_HEAT_TARGET_W_PER_MODULE = 5.00e9
GROSS_ELECTRIC_TARGET_GWE = 20.0
NET_ELECTRIC_TARGET_GWE = 17.0
RECIRCULATING_CEILING_GWE = 3.0
TBR_ACCEPTANCE_TARGET = 1.15
TARGET_GAIN_REQUIREMENT = 200.0
WALLPLUG_REQUIREMENT = 0.15
CP_ALSB_J_KG_K = 3450.0


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    low: float
    high: float
    units: str
    meaning: str


PARAMETERS: Tuple[ParameterSpec, ...] = (
    ParameterSpec("gamma_n", 0.50, 1.00, "1", "D-T density peaking exponent"),
    ParameterSpec("density_scale", 0.85, 1.20, "1", "central total-ion density multiplier"),
    ParameterSpec("fuel_fraction", 0.80, 1.00, "1", "D-T fraction of central ions after dilution"),
    ParameterSpec("deuterium_fraction", 0.45, 0.55, "1", "deuterium fraction of D plus T"),
    ParameterSpec("Ti0_keV", 15.0, 25.0, "keV", "central ion temperature"),
    ParameterSpec("Ti_edge_keV", 0.20, 5.00, "keV", "ion edge temperature"),
    ParameterSpec("gamma_T", 0.50, 2.00, "1", "temperature-profile exponent"),
    ParameterSpec("Te_to_Ti", 0.80, 1.20, "1", "electron-to-ion temperature ratio"),
    ParameterSpec("B0_T", 12.0, 16.0, "T", "on-axis plasma magnetic field"),
    ParameterSpec("tau_E_s", 0.35, 2.00, "s", "energy-confinement screening time"),
    ParameterSpec("Z_eff", 1.00, 2.00, "1", "effective ionic charge for bremsstrahlung"),
    ParameterSpec("alpha_deposition", 0.75, 0.98, "1", "alpha energy retained in plasma"),
    ParameterSpec("wall_area_factor", 0.85, 1.25, "1", "CAD first-wall area divided by circular surrogate"),
    ParameterSpec("wall_peak_factor", 1.20, 2.50, "1", "neutron wall-load peak-to-average screen"),
    ParameterSpec("laser_coupling", 0.60, 0.90, "1", "delivered optical energy absorbed in target/plasma"),
    ParameterSpec("repetition_rate_Hz", 8.0, 12.0, "Hz", "per-module laser repetition rate"),
    ParameterSpec("wallplug_efficiency", 0.10, 0.20, "1", "UV laser wall-plug efficiency"),
    ParameterSpec("neutron_heat_capture", 0.90, 0.99, "1", "neutron energy captured as usable heat"),
    ParameterSpec("alpha_heat_capture", 0.85, 0.99, "1", "alpha energy captured as usable heat"),
    ParameterSpec("high_grade_heat_fraction", 0.70, 0.98, "1", "captured heat reaching high-temperature loop"),
    ParameterSpec("eta_high_grade", 0.36, 0.45, "1", "high-temperature cycle efficiency"),
    ParameterSpec("eta_low_grade", 0.08, 0.20, "1", "low-temperature heat conversion efficiency"),
    ParameterSpec("nonlaser_aux_GWe", 0.60, 1.60, "GWe", "all non-laser and standby electric load"),
    ParameterSpec("TBR", 0.88, 1.20, "1", "realized tritium breeding ratio"),
    ParameterSpec("tritium_process_eff", 0.970, 0.995, "1", "combined recovery and processing efficiency"),
    ParameterSpec("ALSB_deltaT_K", 60.0, 120.0, "K", "aqueous blanket loop temperature rise"),
    ParameterSpec("radiated_SOL_fraction", 0.30, 0.80, "1", "fraction of alpha plus driver exhaust radiated before divertor"),
    ParameterSpec("divertor_wetted_area_m2", 50.0, 200.0, "m2", "modeled divertor wetted area"),
)

PARAMETER_NAMES = [p.name for p in PARAMETERS]
PARAMETER_LOW = np.array([p.low for p in PARAMETERS], dtype=np.float64)
PARAMETER_HIGH = np.array([p.high for p in PARAMETERS], dtype=np.float64)

GATE_COLUMNS = [
    "gate_fusion_source",
    "gate_target_gain",
    "gate_wallplug",
    "gate_self_heating",
    "gate_tritium",
    "gate_captured_heat",
    "gate_gross_electric",
    "gate_recirculating",
    "gate_net_export",
    "gate_all",
]

CORE_METRIC_COLUMNS = [
    "fusion_GW_module",
    "alpha_GW_module",
    "neutron_GW_module",
    "target_gain",
    "self_heating_ratio",
    "driven_heating_ratio",
    "beta_percent",
    "brem_MW_module",
    "thermal_energy_GJ_module",
    "captured_heat_GWth_module",
    "effective_cycle_efficiency",
    "gross_GWe_hub",
    "laser_electric_GWe_hub",
    "recirculating_GWe_hub",
    "net_GWe_hub",
    "engineering_gain",
    "neutron_wall_avg_MW_m2",
    "neutron_wall_peak_MW_m2",
    "divertor_avg_MW_m2",
    "ALSB_flow_kg_s_module",
    "T_burn_g_h_hub",
    "T_bred_g_h_hub",
    "T_returned_g_h_hub",
    "T_surplus_g_h_hub",
    "minimum_gate_margin",
]


# ---------------------------------------------------------------------------
# Physics kernels
# ---------------------------------------------------------------------------


def bosch_hale_dt_reactivity(T_keV: np.ndarray | float) -> np.ndarray:
    """Return Maxwellian D-T reactivity in m3/s for T_i in keV.

    Coefficients and form are the Bosch-Hale D-T fit. Values outside the fit's
    0.2-to-100 keV range are clipped only to keep a screening run numerically
    stable; the caller should not interpret extrapolated values as validated.
    """

    T = np.clip(np.asarray(T_keV, dtype=np.float64), 0.2, 100.0)
    BG = 34.3827
    mrc2 = 1.124656e6
    C1 = 1.17302e-9
    C2 = 1.51361e-2
    C3 = 7.51886e-2
    C4 = 4.60643e-3
    C5 = 1.35000e-2
    C6 = -1.06750e-4
    C7 = 1.36600e-5
    numerator = T * (C2 + T * (C4 + T * C6))
    denominator = 1.0 + T * (C3 + T * (C5 + T * C7))
    theta = T / (1.0 - numerator / denominator)
    xi = (BG**2 / (4.0 * theta)) ** (1.0 / 3.0)
    sv_cm3_s = C1 * theta * np.sqrt(xi / (mrc2 * T**3)) * np.exp(-3.0 * xi)
    return 1.0e-6 * sv_cm3_s


def critical_density_351nm() -> Tuple[float, float]:
    nc_cm3 = 1.115e21 / LASER_WAVELENGTH_UM**2
    return nc_cm3, nc_cm3 * 1.0e6


def volume_midpoint_rule(nodes: int) -> Tuple[np.ndarray, np.ndarray]:
    """Dependency-free midpoint rule for integral_0^1 f(rho)*2*rho*d-rho."""

    rho = (np.arange(nodes, dtype=np.float64) + 0.5) / float(nodes)
    weights = 2.0 * rho / float(nodes)
    return rho.astype(np.float64), weights.astype(np.float64)


def scale_unit_samples(unit: np.ndarray) -> Dict[str, np.ndarray]:
    values = PARAMETER_LOW + unit * (PARAMETER_HIGH - PARAMETER_LOW)
    return {name: values[:, i] for i, name in enumerate(PARAMETER_NAMES)}


def evaluate_parameters(
    p: Mapping[str, np.ndarray], rho_nodes: np.ndarray, rho_weights: np.ndarray
) -> pd.DataFrame:
    """Evaluate a vectorized batch of independent screening cases."""

    n_cases = len(next(iter(p.values())))
    gamma_n = p["gamma_n"]
    gamma_T = p["gamma_T"]
    total_ion_center = (N_D0_BASE + N_T0_BASE) * p["density_scale"]
    fuel_center = total_ion_center * p["fuel_fraction"]
    n_D0 = fuel_center * p["deuterium_fraction"]
    n_T0 = fuel_center * (1.0 - p["deuterium_fraction"])

    integral_reaction = np.zeros(n_cases, dtype=np.float64)
    integral_pressure = np.zeros(n_cases, dtype=np.float64)
    integral_brem_shape = np.zeros(n_cases, dtype=np.float64)
    integral_n_D = np.zeros(n_cases, dtype=np.float64)
    integral_n_T = np.zeros(n_cases, dtype=np.float64)
    integral_n_total = np.zeros(n_cases, dtype=np.float64)

    for rho, weight in zip(rho_nodes, rho_weights):
        base = max(0.0, 1.0 - float(rho) ** 2)
        density_shape = np.power(base, gamma_n)
        temperature_shape = np.power(base, gamma_T)
        T_i = p["Ti_edge_keV"] + (p["Ti0_keV"] - p["Ti_edge_keV"]) * temperature_shape
        T_e = np.maximum(0.2, T_i * p["Te_to_Ti"])
        n_i_total = total_ion_center * density_shape
        n_e = n_i_total  # Hydrogenic-equivalent pressure model; Z_eff handles radiation screening.
        n_D = n_D0 * density_shape
        n_T = n_T0 * density_shape
        sv = bosch_hale_dt_reactivity(T_i)

        integral_reaction += weight * n_D * n_T * sv
        integral_pressure += weight * (n_i_total * T_i + n_e * T_e) * KEV_TO_J
        integral_brem_shape += weight * n_e**2 * np.sqrt(T_e)
        integral_n_D += weight * n_D
        integral_n_T += weight * n_T
        integral_n_total += weight * n_i_total

    reaction_rate = CAD_PLASMA_VOLUME_M3 * integral_reaction
    fusion_W = reaction_rate * E_FUSION
    alpha_W = fusion_W * ALPHA_FRACTION
    neutron_W = fusion_W * NEUTRON_FRACTION
    alpha_deposited_W = alpha_W * p["alpha_deposition"]

    # P_brem = 5.35e-37 Z_eff n_e^2 sqrt(T_e[keV]) W/m3.
    brem_W = CAD_PLASMA_VOLUME_M3 * 5.35e-37 * p["Z_eff"] * integral_brem_shape
    thermal_energy_J = 1.5 * CAD_PLASMA_VOLUME_M3 * integral_pressure
    transport_W = thermal_energy_J / p["tau_E_s"]

    laser_optical_W = LASER_ENERGY_J * p["repetition_rate_Hz"]
    laser_absorbed_W = laser_optical_W * p["laser_coupling"]
    self_heating_ratio = alpha_deposited_W / np.maximum(brem_W + transport_W, 1.0)
    driven_heating_ratio = (alpha_deposited_W + laser_absorbed_W) / np.maximum(
        brem_W + transport_W, 1.0
    )

    fusion_energy_per_shot_J = fusion_W / p["repetition_rate_Hz"]
    target_gain = fusion_energy_per_shot_J / LASER_ENERGY_J
    beta = 2.0 * MU0 * integral_pressure / p["B0_T"] ** 2
    magnetic_pressure_axis_MPa = p["B0_T"] ** 2 / (2.0 * MU0) / 1.0e6

    wall_area_m2 = CIRCULAR_FIRST_WALL_AREA_M2 * p["wall_area_factor"]
    wall_avg_MW_m2 = neutron_W / wall_area_m2 / 1.0e6
    wall_peak_MW_m2 = wall_avg_MW_m2 * p["wall_peak_factor"]

    sol_W = (1.0 - p["radiated_SOL_fraction"]) * (alpha_deposited_W + laser_absorbed_W)
    divertor_avg_MW_m2 = sol_W / p["divertor_wetted_area_m2"] / 1.0e6

    captured_heat_W = (
        neutron_W * p["neutron_heat_capture"]
        + alpha_W * p["alpha_heat_capture"]
        + laser_absorbed_W
    )
    high_grade_W = captured_heat_W * p["high_grade_heat_fraction"]
    low_grade_W = captured_heat_W - high_grade_W
    gross_electric_W_module = p["eta_high_grade"] * high_grade_W + p["eta_low_grade"] * low_grade_W
    effective_cycle_eff = gross_electric_W_module / np.maximum(captured_heat_W, 1.0)
    gross_GWe_hub = gross_electric_W_module * ACTIVE_MODULES / 1.0e9
    laser_electric_GWe_hub = (
        laser_optical_W / p["wallplug_efficiency"] * ACTIVE_MODULES / 1.0e9
    )
    recirculating_GWe_hub = laser_electric_GWe_hub + p["nonlaser_aux_GWe"]
    net_GWe_hub = gross_GWe_hub - recirculating_GWe_hub
    engineering_gain = gross_GWe_hub / np.maximum(recirculating_GWe_hub, 1.0e-12)

    # Primary blanket-loop screening flow must remove the captured heat, not
    # merely the fraction later classified as low-grade heat.
    alsb_flow_kg_s_module = captured_heat_W / (CP_ALSB_J_KG_K * p["ALSB_deltaT_K"])

    D_burn_g_h_hub = reaction_rate * M_D * 1000.0 * 3600.0 * ACTIVE_MODULES
    T_burn_g_h_hub = reaction_rate * M_T * 1000.0 * 3600.0 * ACTIVE_MODULES
    T_bred_g_h_hub = p["TBR"] * T_burn_g_h_hub
    T_returned_g_h_hub = p["tritium_process_eff"] * T_bred_g_h_hub
    T_surplus_g_h_hub = T_returned_g_h_hub - T_burn_g_h_hub

    N_D = integral_n_D * CAD_PLASMA_VOLUME_M3
    N_T = integral_n_T * CAD_PLASMA_VOLUME_M3
    fuel_mass_g_module = (N_D * M_D + N_T * M_T) * 1000.0
    equivalent_prefill_Pa = (N_D + N_T) * KB * PREFILL_TEMPERATURE_K / CAD_PLASMA_VOLUME_M3

    gate_fusion = fusion_W >= FUSION_SOURCE_TARGET_W_PER_MODULE
    gate_gain = target_gain >= TARGET_GAIN_REQUIREMENT
    gate_wallplug = p["wallplug_efficiency"] >= WALLPLUG_REQUIREMENT
    gate_self = self_heating_ratio >= 1.0
    gate_tritium = (p["TBR"] >= TBR_ACCEPTANCE_TARGET) & (T_surplus_g_h_hub >= 0.0)
    gate_heat = captured_heat_W >= CAPTURED_HEAT_TARGET_W_PER_MODULE
    gate_gross = gross_GWe_hub >= GROSS_ELECTRIC_TARGET_GWE
    gate_recirc = recirculating_GWe_hub <= RECIRCULATING_CEILING_GWE
    gate_net = net_GWe_hub >= NET_ELECTRIC_TARGET_GWE
    gate_all = (
        gate_fusion
        & gate_gain
        & gate_wallplug
        & gate_self
        & gate_tritium
        & gate_heat
        & gate_gross
        & gate_recirc
        & gate_net
    )

    # A positive minimum margin means every defined Revision 2.1 screening gate passes.
    margin_stack = np.vstack(
        [
            fusion_W / FUSION_SOURCE_TARGET_W_PER_MODULE - 1.0,
            target_gain / TARGET_GAIN_REQUIREMENT - 1.0,
            p["wallplug_efficiency"] / WALLPLUG_REQUIREMENT - 1.0,
            self_heating_ratio - 1.0,
            p["TBR"] / TBR_ACCEPTANCE_TARGET - 1.0,
            T_returned_g_h_hub / np.maximum(T_burn_g_h_hub, 1.0e-30) - 1.0,
            captured_heat_W / CAPTURED_HEAT_TARGET_W_PER_MODULE - 1.0,
            gross_GWe_hub / GROSS_ELECTRIC_TARGET_GWE - 1.0,
            1.0 - recirculating_GWe_hub / RECIRCULATING_CEILING_GWE,
            net_GWe_hub / NET_ELECTRIC_TARGET_GWE - 1.0,
        ]
    )
    minimum_gate_margin = np.min(margin_stack, axis=0)

    result: Dict[str, np.ndarray] = {name: np.asarray(p[name]) for name in PARAMETER_NAMES}
    result.update(
        {
            "n_D0_m3": n_D0,
            "n_T0_m3": n_T0,
            "average_total_ion_density_m3": integral_n_total,
            "fusion_GW_module": fusion_W / 1.0e9,
            "alpha_GW_module": alpha_W / 1.0e9,
            "neutron_GW_module": neutron_W / 1.0e9,
            "reaction_rate_s_module": reaction_rate,
            "fusion_MJ_per_shot": fusion_energy_per_shot_J / 1.0e6,
            "target_gain": target_gain,
            "brem_MW_module": brem_W / 1.0e6,
            "transport_GW_module": transport_W / 1.0e9,
            "thermal_energy_GJ_module": thermal_energy_J / 1.0e9,
            "self_heating_ratio": self_heating_ratio,
            "driven_heating_ratio": driven_heating_ratio,
            "beta_percent": 100.0 * beta,
            "magnetic_pressure_axis_MPa": magnetic_pressure_axis_MPa,
            "fuel_inventory_g_module": fuel_mass_g_module,
            "equivalent_prefill_pressure_Pa": equivalent_prefill_Pa,
            "captured_heat_GWth_module": captured_heat_W / 1.0e9,
            "effective_cycle_efficiency": effective_cycle_eff,
            "gross_GWe_hub": gross_GWe_hub,
            "laser_electric_GWe_hub": laser_electric_GWe_hub,
            "recirculating_GWe_hub": recirculating_GWe_hub,
            "net_GWe_hub": net_GWe_hub,
            "engineering_gain": engineering_gain,
            "neutron_wall_avg_MW_m2": wall_avg_MW_m2,
            "neutron_wall_peak_MW_m2": wall_peak_MW_m2,
            "divertor_avg_MW_m2": divertor_avg_MW_m2,
            "ALSB_flow_kg_s_module": alsb_flow_kg_s_module,
            "D_burn_g_h_hub": D_burn_g_h_hub,
            "T_burn_g_h_hub": T_burn_g_h_hub,
            "T_bred_g_h_hub": T_bred_g_h_hub,
            "T_returned_g_h_hub": T_returned_g_h_hub,
            "T_surplus_g_h_hub": T_surplus_g_h_hub,
            "minimum_gate_margin": minimum_gate_margin,
            "gate_fusion_source": gate_fusion,
            "gate_target_gain": gate_gain,
            "gate_wallplug": gate_wallplug,
            "gate_self_heating": gate_self,
            "gate_tritium": gate_tritium,
            "gate_captured_heat": gate_heat,
            "gate_gross_electric": gate_gross,
            "gate_recirculating": gate_recirc,
            "gate_net_export": gate_net,
            "gate_all": gate_all,
        }
    )
    return pd.DataFrame(result)


# ---------------------------------------------------------------------------
# Baselines, chunk storage, and aggregation
# ---------------------------------------------------------------------------


def nominal_parameter_case(profiled: bool) -> Dict[str, np.ndarray]:
    values = {
        "gamma_n": 0.657,
        "density_scale": 1.0,
        "fuel_fraction": 1.0,
        "deuterium_fraction": 0.5,
        "Ti0_keV": 20.0,
        "Ti_edge_keV": 1.0 if profiled else 20.0,
        "gamma_T": 1.0,
        "Te_to_Ti": 1.0,
        "B0_T": 14.0,
        "tau_E_s": 0.96,
        "Z_eff": 1.0,
        # The uniform row reproduces the source-only algebra check; the profiled
        # row applies a provisional 90% alpha-deposition fraction.
        "alpha_deposition": 0.90 if profiled else 1.00,
        "wall_area_factor": 1.0,
        "wall_peak_factor": 1.5,
        "laser_coupling": 0.80,
        "repetition_rate_Hz": 10.0,
        "wallplug_efficiency": 0.15,
        "neutron_heat_capture": 0.98,
        "alpha_heat_capture": 0.95,
        "high_grade_heat_fraction": 0.95,
        "eta_high_grade": 0.40,
        "eta_low_grade": 0.12,
        "nonlaser_aux_GWe": 1.333,
        "TBR": 1.15,
        "tritium_process_eff": 0.995,
        "ALSB_deltaT_K": 100.0,
        "radiated_SOL_fraction": 0.60,
        "divertor_wetted_area_m2": 100.0,
    }
    return {k: np.array([v], dtype=np.float64) for k, v in values.items()}


def calculate_baselines(rho: np.ndarray, weights: np.ndarray) -> pd.DataFrame:
    ideal = evaluate_parameters(nominal_parameter_case(profiled=False), rho, weights)
    ideal.insert(0, "case", "ideal_uniform_20keV")
    profiled = evaluate_parameters(nominal_parameter_case(profiled=True), rho, weights)
    profiled.insert(0, "case", "profiled_20_to_1keV")
    return pd.concat([ideal, profiled], ignore_index=True)


def write_npz_atomic(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_suffix(".tmp.npz")
    arrays = {}
    for col in frame.columns:
        values = frame[col].to_numpy()
        if values.dtype == bool:
            values = values.astype(np.uint8)
        elif np.issubdtype(values.dtype, np.floating):
            values = values.astype(np.float32)
        arrays[col] = values
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def read_npz_frame(path: Path) -> pd.DataFrame:
    with np.load(path, allow_pickle=False) as loaded:
        return pd.DataFrame({name: loaded[name] for name in loaded.files})


class ScanAggregator:
    def __init__(self, config: RunConfig):
        self.config = config
        self.gate_counts = {name: 0 for name in GATE_COLUMNS}
        self.total_rows = 0
        self.reservoir_parts: List[pd.DataFrame] = []
        self.top_margin_parts: List[pd.DataFrame] = []
        self.top_net_parts: List[pd.DataFrame] = []
        expected_batches = max(1, math.ceil(config.requested_samples / config.batch_size))
        self.reservoir_per_batch = max(256, math.ceil(config.reservoir_rows / expected_batches))

    def add(self, frame: pd.DataFrame, chunk_index: int) -> None:
        self.total_rows += len(frame)
        for gate in GATE_COLUMNS:
            self.gate_counts[gate] += int(np.asarray(frame[gate]).astype(bool).sum())
        n_sample = min(self.reservoir_per_batch, len(frame))
        self.reservoir_parts.append(
            frame.sample(n=n_sample, random_state=self.config.seed + chunk_index, replace=False)
        )
        self.top_margin_parts.append(frame.nlargest(200, "minimum_gate_margin"))
        passing = frame[np.asarray(frame["gate_all"]).astype(bool)]
        if not passing.empty:
            self.top_net_parts.append(passing.nlargest(200, "net_GWe_hub"))

    def finalize(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        reservoir = pd.concat(self.reservoir_parts, ignore_index=True)
        if len(reservoir) > self.config.reservoir_rows:
            reservoir = reservoir.sample(
                n=self.config.reservoir_rows, random_state=self.config.seed, replace=False
            )
        near = (
            pd.concat(self.top_margin_parts, ignore_index=True)
            .drop_duplicates("sample_id")
            .nlargest(self.config.top_rows, "minimum_gate_margin")
        )
        if self.top_net_parts:
            passing = (
                pd.concat(self.top_net_parts, ignore_index=True)
                .drop_duplicates("sample_id")
                .nlargest(self.config.top_rows, "net_GWe_hub")
            )
        else:
            passing = pd.DataFrame(columns=near.columns)
        return reservoir, near, passing


# ---------------------------------------------------------------------------
# Diagnostics, sensitivity, plots, and reporting
# ---------------------------------------------------------------------------


def safe_to_csv(frame: pd.DataFrame, path: Path, **kwargs) -> None:
    frame.to_csv(path, index=False, **kwargs)


def quantile_table(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    rows = []
    for col in columns:
        series = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if series.empty:
            continue
        rows.append(
            {
                "metric": col,
                "P05": float(series.quantile(0.05)),
                "P50": float(series.quantile(0.50)),
                "P95": float(series.quantile(0.95)),
                "mean": float(series.mean()),
            }
        )
    return pd.DataFrame(rows)


def rank_correlation(x: pd.Series, y: pd.Series) -> float:
    """Spearman-style rank correlation without SciPy."""

    x_rank = pd.Series(x).rank(method="average").to_numpy(dtype=np.float64)
    y_rank = pd.Series(y).rank(method="average").to_numpy(dtype=np.float64)
    x_centered = x_rank - x_rank.mean()
    y_centered = y_rank - y_rank.mean()
    denominator = math.sqrt(float(x_centered @ x_centered) * float(y_centered @ y_centered))
    if denominator == 0.0:
        return float("nan")
    return float((x_centered @ y_centered) / denominator)


def sensitivity_table(frame: pd.DataFrame, config: RunConfig, deadline: float) -> pd.DataFrame:
    sample = frame.dropna(subset=["net_GWe_hub", "minimum_gate_margin"]).copy()
    max_rows = min(len(sample), 125000 if config.run_mode == "full" else 50000)
    if len(sample) > max_rows:
        sample = sample.sample(max_rows, random_state=config.seed)

    rows = []
    for feature in PARAMETER_NAMES:
        rho_net = rank_correlation(sample[feature], sample["net_GWe_hub"])
        rho_margin = rank_correlation(sample[feature], sample["minimum_gate_margin"])
        rows.append(
            {
                "feature": feature,
                "rank_correlation_net_GWe": float(rho_net),
                "rank_correlation_gate_margin": float(rho_margin),
            }
        )
    result = pd.DataFrame(rows)
    result["importance_rank_score"] = result[
        ["rank_correlation_net_GWe", "rank_correlation_gate_margin"]
    ].abs().max(axis=1)
    return result.sort_values("importance_rank_score", ascending=False)


def plot_reactivity(output_dir: Path) -> None:
    if not PLOTS_AVAILABLE:
        return
    T = np.geomspace(0.2, 100.0, 500)
    sv = bosch_hale_dt_reactivity(T)
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.loglog(T, sv, color="#1479a6", linewidth=2.2)
    ax.axvline(20.0, color="#b52a2a", linestyle="--", linewidth=1.2, label="20 keV reference")
    ax.set_xlabel("Ion temperature (keV)")
    ax.set_ylabel("D-T reactivity (m3/s)")
    ax.set_title("Bosch-Hale D-T Maxwellian Reactivity")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "bosch_hale_reactivity.png", dpi=180)
    plt.close(fig)


def plot_profiles(output_dir: Path) -> None:
    if not PLOTS_AVAILABLE:
        return
    rho = np.linspace(0.0, 1.0, 400)
    gamma_n = 0.657
    density_shape = np.power(np.maximum(0.0, 1.0 - rho**2), gamma_n)
    T_profile = 1.0 + 19.0 * np.power(np.maximum(0.0, 1.0 - rho**2), 1.0)
    fig, ax1 = plt.subplots(figsize=(8.5, 5.0))
    ax1.plot(rho, density_shape, color="#1479a6", linewidth=2.2, label="n/n0")
    ax1.set_xlabel("Normalized flux radius")
    ax1.set_ylabel("Normalized D-T density", color="#1479a6")
    ax1.tick_params(axis="y", labelcolor="#1479a6")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(rho, T_profile, color="#b52a2a", linewidth=2.0, label="Ti")
    ax2.set_ylabel("Ion temperature (keV)", color="#b52a2a")
    ax2.tick_params(axis="y", labelcolor="#b52a2a")
    ax1.set_title("Revision 2.1 Baseline Radial Profiles")
    fig.tight_layout()
    fig.savefig(output_dir / "baseline_profiles.png", dpi=180)
    plt.close(fig)


def plot_ignition_map(output_dir: Path) -> pd.DataFrame:
    T_values = np.linspace(1.0, 40.0, 180)
    tau_values = np.geomspace(0.08, 4.0, 170)
    gamma_n = 0.657
    density_product_avg = N_D0_BASE * N_T0_BASE / (2.0 * gamma_n + 1.0)
    ion_density_avg = (N_D0_BASE + N_T0_BASE) / (gamma_n + 1.0)
    ne2_avg = (N_D0_BASE + N_T0_BASE) ** 2 / (2.0 * gamma_n + 1.0)

    T_grid, tau_grid = np.meshgrid(T_values, tau_values)
    reaction_rate = CAD_PLASMA_VOLUME_M3 * density_product_avg * bosch_hale_dt_reactivity(T_grid)
    alpha = reaction_rate * E_ALPHA * 0.90
    brem = CAD_PLASMA_VOLUME_M3 * 5.35e-37 * ne2_avg * np.sqrt(T_grid)
    pressure_avg = 2.0 * ion_density_avg * T_grid * KEV_TO_J
    thermal = 1.5 * CAD_PLASMA_VOLUME_M3 * pressure_avg
    transport = thermal / tau_grid
    ratio = alpha / np.maximum(brem + transport, 1.0)

    if PLOTS_AVAILABLE:
        fig, ax = plt.subplots(figsize=(8.7, 5.4))
        levels = np.linspace(-2.0, 1.0, 25)
        mesh = ax.contourf(T_grid, tau_grid, np.log10(np.maximum(ratio, 1.0e-6)), levels=levels, cmap="viridis")
        ax.contour(T_grid, tau_grid, ratio, levels=[1.0], colors=["white"], linewidths=2.0)
        ax.plot([], [], color="white", linewidth=2.0, label="self-heating ratio = 1 boundary")
        ax.set_yscale("log")
        ax.set_xlabel("Uniform ion/electron temperature (keV)")
        ax.set_ylabel("Energy-confinement time (s)")
        ax.set_title("Idealized Alpha Self-Heating Screen")
        ax.legend(loc="lower right", framealpha=0.85)
        cbar = fig.colorbar(mesh, ax=ax)
        cbar.set_label("log10(P_alpha,deposited / (P_brem + W/tau_E))")
        fig.tight_layout()
        fig.savefig(output_dir / "idealized_ignition_map.png", dpi=180)
        plt.close(fig)

    return pd.DataFrame(
        {
            "T_keV": T_grid.ravel(),
            "tau_E_s": tau_grid.ravel(),
            "self_heating_ratio": ratio.ravel(),
        }
    )


def plot_screening_results(
    sample: pd.DataFrame,
    gate_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    output_dir: Path,
) -> None:
    if not PLOTS_AVAILABLE:
        return
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.hist(sample["net_GWe_hub"], bins=80, color="#1479a6", alpha=0.85)
    ax.axvline(NET_ELECTRIC_TARGET_GWE, color="#b52a2a", linestyle="--", linewidth=2.0)
    ax.set_xlabel("Net electrical export (GWe)")
    ax.set_ylabel("Sample count")
    ax.set_title("Uncertainty Screen: Net Grid Export")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "net_output_distribution.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    hb = ax.hexbin(
        sample["fusion_GW_module"],
        sample["net_GWe_hub"],
        gridsize=55,
        bins="log",
        mincnt=1,
        cmap="Blues",
    )
    ax.axvline(5.0, color="#b52a2a", linestyle="--", linewidth=1.5)
    ax.axhline(17.0, color="#b52a2a", linestyle="--", linewidth=1.5)
    ax.set_xlabel("Fusion source per active module (GW)")
    ax.set_ylabel("Net hub export (GWe)")
    ax.set_title("Fusion Source Versus Net Export")
    fig.colorbar(hb, ax=ax, label="log10 count")
    fig.tight_layout()
    fig.savefig(output_dir / "fusion_vs_net_hexbin.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 5.3))
    plot_gates = gate_summary[gate_summary["gate"] != "gate_all"].copy()
    ax.barh(plot_gates["gate"].str.replace("gate_", "", regex=False), plot_gates["pass_percent"], color="#1479a6")
    ax.set_xlim(0.0, 100.0)
    ax.set_xlabel("Cases passing gate (%)")
    ax.set_title("Exact Gate Pass Rates")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "gate_pass_rates.png", dpi=180)
    plt.close(fig)

    if not sensitivity.empty:
        top = sensitivity.head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(9.0, 6.0))
        ax.barh(top["feature"], top["importance_rank_score"], color="#1479a6")
        ax.set_xlabel("Sensitivity ranking score")
        ax.set_title("Top Preliminary Sensitivity Drivers")
        ax.grid(True, axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(output_dir / "sensitivity_ranking.png", dpi=180)
        plt.close(fig)


def markdown_table(frame: pd.DataFrame, columns: Sequence[str], rows: int = 20) -> str:
    sub = frame.loc[:, [c for c in columns if c in frame.columns]].head(rows).copy()
    if sub.empty:
        return "No rows available."
    for col in sub.columns:
        if np.issubdtype(sub[col].dtype, np.floating):
            sub[col] = sub[col].map(lambda x: f"{x:.5g}")
    header = "| " + " | ".join(sub.columns) + " |"
    rule = "| " + " | ".join(["---"] * len(sub.columns)) + " |"
    body = ["| " + " | ".join(map(str, row)) + " |" for row in sub.itertuples(index=False, name=None)]
    return "\n".join([header, rule] + body)


def write_summary(
    output_dir: Path,
    config: RunConfig,
    baseline: pd.DataFrame,
    gate_summary: pd.DataFrame,
    quantiles: pd.DataFrame,
    passing: pd.DataFrame,
    near: pd.DataFrame,
    sensitivity: pd.DataFrame,
    completed_samples: int,
    elapsed_seconds: float,
) -> None:
    nc_cm3, nc_m3 = critical_density_351nm()
    peak_pressure = B_PEAK_CONDUCTOR_T**2 / (2.0 * MU0) / 1.0e6
    baseline_cols = [
        "case",
        "fusion_GW_module",
        "target_gain",
        "self_heating_ratio",
        "beta_percent",
        "captured_heat_GWth_module",
        "gross_GWe_hub",
        "net_GWe_hub",
        "neutron_wall_avg_MW_m2",
    ]
    gate_cols = ["gate", "passed", "tested", "pass_percent"]
    quant_cols = ["metric", "P05", "P50", "P95", "mean"]
    candidate = passing if not passing.empty else near
    candidate_label = "passing cases ranked by net output" if not passing.empty else "closest-to-feasible cases; no all-gate pass was found"
    candidate_cols = [
        "sample_id",
        "fusion_GW_module",
        "target_gain",
        "self_heating_ratio",
        "TBR",
        "effective_cycle_efficiency",
        "gross_GWe_hub",
        "recirculating_GWe_hub",
        "net_GWe_hub",
        "minimum_gate_margin",
    ]

    text = f"""# Tomahawk Revision 2.1 Kaggle Preliminary Screening Report

Generated: {datetime.now(timezone.utc).isoformat()}

## Scope

This run evaluates the corrected Revision 2.1 algebra and a bounded uncertainty screen. It is a
preliminary model-consistency exercise for discussion with Argonne. It is not evidence that the
reactor, target, magnet, blanket, tritium system, materials, or power plant will achieve the stated
performance.

## Run record

- Mode: {config.run_mode}
- Completed Monte Carlo cases: {completed_samples:,} of {config.requested_samples:,}
- Elapsed runtime: {elapsed_seconds / 3600.0:.3f} hours
- Random/scramble seed: {config.seed}
- Active modules: {ACTIVE_MODULES}; hot standbys: {HOT_STANDBY_MODULES}
- CAD plasma volume used in integrals: {CAD_PLASMA_VOLUME_M3:.1f} m3
- Circular torus reference volume: {CIRCULAR_TORUS_VOLUME_M3:.2f} m3
- Circular first-wall reference area: {CIRCULAR_FIRST_WALL_AREA_M2:.2f} m2
- 351 nm critical density: {nc_cm3:.3e} cm^-3 = {nc_m3:.3e} m^-3
- 35 T magnetic-pressure load scale: {peak_pressure:.2f} MPa; this is not solved winding-pack stress

## Locked target ledger

- 5.00 GW D-T fusion-source target per active module
- 5.00 GWth captured-heat target per active module
- 50.0 GWth captured heat across ten active modules
- 20.0 GWe gross target at a 40% equivalent cycle efficiency
- Recirculating ceiling: 3.0 GWe, including laser, non-laser loads, and hot standbys
- Net export target: 17.0 GWe
- Delivered-laser target gain: at least 200
- UV wall-plug efficiency development target: at least 15%
- Realized TBR acceptance target: at least 1.15

The uncertainty model does not force the 40% equivalent efficiency. It decomposes high- and
low-grade heat so that the net-output claim passes only when the sampled heat split, conversion
efficiencies, and auxiliary loads close.

## Deterministic checks

{markdown_table(baseline, baseline_cols, rows=10)}

The uniform 20 keV row is an algebra check. The profiled row demonstrates why the unresolved edge
temperature and temperature peaking parameters materially affect the fusion result.

## Gate pass rates

{markdown_table(gate_summary, gate_cols, rows=20)}

## Approximate uncertainty statistics

These P05/P50/P95 values come from a deterministic reservoir sample of the completed Monte Carlo run.
Exact gate counts use every completed case.

{markdown_table(quantiles, quant_cols, rows=40)}

## Top candidate table

The table below contains {candidate_label}. A passing row is still only a mutually consistent
screening point, not a validated design point.

{markdown_table(candidate, candidate_cols, rows=15)}

## Leading sensitivities

{markdown_table(sensitivity, ["feature", "rank_correlation_net_GWe", "rank_correlation_gate_margin", "importance_rank_score"], rows=15)}

## Mandatory interpretation limits

1. No three-dimensional coil-current equilibrium or closed-flux-surface solution is performed.
2. No resistive-MHD stability spectrum, nonlinear mode evolution, or field-line wall-strike map is solved.
3. The 351 nm driver is represented by delivered energy, repetition rate, coupling, and gain bookkeeping;
   no capsule/target hydrodynamics, laser-plasma instability, debris clearing, or chamber recovery is solved.
4. TBR is an input scan, not a neutron-transport result. A value at or above 1.15 is not proof that the
   beryllium-free ALSB geometry breeds enough tritium.
5. First-wall and divertor numbers are area-average screens. Local heat flux, DPA, erosion, stress,
   fatigue, joints, and irradiation properties require CAD-coupled analysis.
6. The aqueous ALSB flow is assigned only the low-grade heat fraction. Chemistry, boiling margin,
   radiolysis, corrosion, MHD pressure loss, and tritium speciation are not closed.
7. The sCO2 result is a heat-grade efficiency decomposition, not a state-point or turbomachinery solution.
8. The 17.0 GWe target is defensible only if gross generation, laser efficiency, all auxiliary loads,
   availability, and the two standby modules close simultaneously.
9. Magnetic field is not used as an independent B^4 power multiplier in this run. B0 affects beta and
   magnetic-pressure reporting only; a field-to-performance relation requires a solved equilibrium and
   confinement model. Density scaling and beta-field scaling must not be multiplied as independent gains.

## Files to take to Argonne

- baseline_checks.csv
- gate_pass_rates.csv
- uncertainty_quantiles.csv
- top_passing_candidates.csv or closest_to_feasible_candidates.csv
- sensitivity_importance.csv
- parameter_definitions.csv
- all plots in the plots folder
- config.json and run_manifest.json for reproducibility

"""
    (output_dir / "ARGONNE_PRELIMINARY_REPORT.md").write_text(text, encoding="utf-8")


def build_results_zip(output_dir: Path) -> Path:
    zip_path = output_dir / "Tomahawk_Rev21_Kaggle_Preliminary_Results.zip"
    include_names = {
        "ARGONNE_PRELIMINARY_REPORT.md",
        "baseline_checks.csv",
        "gate_pass_rates.csv",
        "uncertainty_quantiles.csv",
        "top_passing_candidates.csv",
        "closest_to_feasible_candidates.csv",
        "sensitivity_importance.csv",
        "parameter_definitions.csv",
        "screening_reservoir_sample.csv.gz",
        "idealized_ignition_map_sample.csv.gz",
        "config.json",
        "run_manifest.json",
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path == zip_path:
                continue
            if path.parent.name == "chunks":
                continue
            if path.name in include_names or path.suffix.lower() == ".png":
                archive.write(path, path.relative_to(output_dir))
    return zip_path


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------


def main() -> None:
    config = build_config()
    start = time.monotonic()
    deadline = start + config.max_runtime_hours * 3600.0

    default_root = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path.cwd()
    root = Path(os.getenv("TOMAHAWK_OUTPUT_ROOT", str(default_root))).expanduser().resolve()
    config_identity = {
        "model_revision": "2.1",
        "config": asdict(config),
        "parameter_bounds": [asdict(p) for p in PARAMETERS],
    }
    config_hash = hashlib.sha256(json.dumps(config_identity, sort_keys=True).encode()).hexdigest()[:12]
    output_dir = root / f"tomahawk_rev21_{config.run_mode}_{config_hash}"
    chunk_dir = output_dir / "chunks"
    plot_dir = output_dir / "plots"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78, flush=True)
    print("TOMAHAWK REVISION 2.1 - KAGGLE PRELIMINARY SCREEN", flush=True)
    print("=" * 78, flush=True)
    print(f"Mode: {config.run_mode}", flush=True)
    print(f"Requested cases: {config.requested_samples:,}", flush=True)
    print(f"Time ceiling: {config.max_runtime_hours:.2f} hours", flush=True)
    print(f"Output: {output_dir}", flush=True)
    print("Results are preliminary screening outputs, not reactor validation.\n", flush=True)

    (output_dir / "config.json").write_text(
        json.dumps(config_identity, indent=2, sort_keys=True), encoding="utf-8"
    )
    parameter_frame = pd.DataFrame([asdict(p) for p in PARAMETERS])
    safe_to_csv(parameter_frame, output_dir / "parameter_definitions.csv")

    rho, weights = volume_midpoint_rule(config.quadrature_nodes)
    baseline = calculate_baselines(rho, weights)
    safe_to_csv(baseline, output_dir / "baseline_checks.csv")
    baseline_view = baseline[
        ["case", "fusion_GW_module", "target_gain", "self_heating_ratio", "net_GWe_hub"]
    ]
    print("Deterministic checks:", flush=True)
    print(baseline_view.to_string(index=False), flush=True)

    plot_reactivity(plot_dir)
    plot_profiles(plot_dir)
    ignition_map = plot_ignition_map(plot_dir)
    ignition_map.iloc[::20].to_csv(
        output_dir / "idealized_ignition_map_sample.csv.gz", index=False, compression="gzip"
    )

    aggregator = ScanAggregator(config)
    existing_chunks = sorted(chunk_dir.glob("chunk_*.npz"))
    completed = 0
    chunk_index = 0

    # Rebuild aggregate state from completed chunks so an interrupted Kaggle run can resume.
    for chunk_path in existing_chunks:
        try:
            prior = read_npz_frame(chunk_path)
            if prior.empty:
                continue
            expected_start = completed
            actual_start = int(prior["sample_id"].iloc[0])
            if actual_start != expected_start:
                print(f"Resume stopped before non-contiguous chunk: {chunk_path.name}", flush=True)
                break
            aggregator.add(prior, chunk_index)
            completed += len(prior)
            chunk_index += 1
        except Exception as exc:
            print(f"Resume warning for {chunk_path.name}: {exc}", flush=True)
            break

    if completed:
        print(f"Resumed {completed:,} previously completed cases.", flush=True)

    # PCG64 is part of NumPy. Advancing by completed*dimensions makes resumed
    # runs reproduce the same stream without replaying earlier samples.
    bit_generator = np.random.PCG64(config.seed)
    if completed:
        bit_generator.advance(completed * len(PARAMETERS))
    engine = np.random.Generator(bit_generator)

    while completed < config.requested_samples:
        now = time.monotonic()
        if now >= deadline - config.reserve_minutes * 60.0:
            print("Time reserve reached; stopping scan cleanly before final exports.", flush=True)
            break
        n_batch = min(config.batch_size, config.requested_samples - completed)
        unit = engine.random((n_batch, len(PARAMETERS)), dtype=np.float64)
        params = scale_unit_samples(unit)
        frame = evaluate_parameters(params, rho, weights)
        frame.insert(0, "sample_id", np.arange(completed, completed + n_batch, dtype=np.int64))

        chunk_path = chunk_dir / f"chunk_{chunk_index:05d}.npz"
        if config.save_full_chunks:
            write_npz_atomic(chunk_path, frame)
        aggregator.add(frame, chunk_index)
        completed += n_batch
        chunk_index += 1
        elapsed = time.monotonic() - start
        pass_count = aggregator.gate_counts["gate_all"]
        print(
            f"Completed {completed:,}/{config.requested_samples:,} cases | "
            f"all-gate passes {pass_count:,} | elapsed {elapsed/60.0:.1f} min",
            flush=True,
        )

        checkpoint = {
            "completed_samples": completed,
            "requested_samples": config.requested_samples,
            "chunks": chunk_index,
            "gate_counts": aggregator.gate_counts,
            "elapsed_seconds": elapsed,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "checkpoint.json").write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")

    reservoir, near, passing = aggregator.finalize()
    reservoir.to_csv(
        output_dir / "screening_reservoir_sample.csv.gz", index=False, compression="gzip"
    )
    safe_to_csv(near, output_dir / "closest_to_feasible_candidates.csv")
    safe_to_csv(passing, output_dir / "top_passing_candidates.csv")

    gate_summary = pd.DataFrame(
        [
            {
                "gate": gate,
                "passed": aggregator.gate_counts[gate],
                "tested": aggregator.total_rows,
                "pass_percent": 100.0 * aggregator.gate_counts[gate] / max(1, aggregator.total_rows),
            }
            for gate in GATE_COLUMNS
        ]
    )
    safe_to_csv(gate_summary, output_dir / "gate_pass_rates.csv")

    quantiles = quantile_table(reservoir, CORE_METRIC_COLUMNS)
    safe_to_csv(quantiles, output_dir / "uncertainty_quantiles.csv")

    sensitivity = sensitivity_table(reservoir, config, deadline)
    safe_to_csv(sensitivity, output_dir / "sensitivity_importance.csv")
    plot_screening_results(reservoir, gate_summary, sensitivity, plot_dir)

    elapsed = time.monotonic() - start
    manifest = {
        "model_revision": "2.1",
        "status": "preliminary_screening_only",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "completed_samples": completed,
        "requested_samples": config.requested_samples,
        "config_hash": config_hash,
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": _CPU_COUNT,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sample_generator": "NumPy PCG64 independent uniform Monte Carlo",
        "plots_available": PLOTS_AVAILABLE,
        "gate_counts": aggregator.gate_counts,
        "output_directory": str(output_dir),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_summary(
        output_dir,
        config,
        baseline,
        gate_summary,
        quantiles,
        passing,
        near,
        sensitivity,
        completed,
        elapsed,
    )
    zip_path = build_results_zip(output_dir)

    print("\nRun complete.", flush=True)
    print(f"Completed cases: {completed:,}", flush=True)
    print(f"All-gate passes: {aggregator.gate_counts['gate_all']:,}", flush=True)
    print(f"Report: {output_dir / 'ARGONNE_PRELIMINARY_REPORT.md'}", flush=True)
    print(f"Download bundle: {zip_path}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
