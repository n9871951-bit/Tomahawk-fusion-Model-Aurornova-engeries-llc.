import json
import math
import os
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = int(os.environ.get("TOMAHAWK_SECONDARY_SEED", "20260829"))
N_SAMPLES = int(os.environ.get("TOMAHAWK_SECONDARY_SAMPLES", "10000"))
AVAILABLE_PROCESS_HEAT_MWTH = float(os.environ.get("TOMAHAWK_PROCESS_HEAT_MWTH", "1.0"))
AVAILABLE_ELECTRIC_MWE = float(os.environ.get("TOMAHAWK_PROCESS_ELECTRIC_MWE", "1.0"))
HOURS_PER_DAY = 24.0
output_root_env = os.environ.get("TOMAHAWK_SECONDARY_OUTPUT_ROOT", "")
OUTPUT_ROOT = Path(output_root_env) if output_root_env else (Path("/kaggle/working/tomahawk_secondary_systems_screen") if Path("/kaggle/working").exists() else Path.cwd() / "tomahawk_secondary_systems_screen")
OUTPUT_ROOT = OUTPUT_ROOT.resolve()
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

if N_SAMPLES < 1:
    raise ValueError("TOMAHAWK_SECONDARY_SAMPLES must be at least 1")
if AVAILABLE_PROCESS_HEAT_MWTH <= 0.0 or AVAILABLE_ELECTRIC_MWE <= 0.0:
    raise ValueError("Process heat and electricity interface values must be positive")

rng = np.random.default_rng(SEED)
print("Python:", platform.python_version())
print("Seed:", SEED)
print("Samples per branch:", N_SAMPLES)
print("Normalized process interface:", AVAILABLE_PROCESS_HEAT_MWTH, "MWth +", AVAILABLE_ELECTRIC_MWE, "MWe")
print("Continuous interface energy:", AVAILABLE_PROCESS_HEAT_MWTH * 1000.0 * HOURS_PER_DAY, "kWhth/day +", AVAILABLE_ELECTRIC_MWE * 1000.0 * HOURS_PER_DAY, "kWhe/day")
print("Output:", OUTPUT_ROOT)


# Water process archetypes.
# RO energy range is anchored to the DOE water-energy report above.
# Other ranges are screening assumptions pending process-specific evidence.
WATER_PROCESSES = {
    "seawater_ro": {
        "electric_kwh_per_m3": (3.0, 4.7),
        "thermal_kwhth_per_m3": (0.0, 0.0),
        "recovery_fraction": (0.35, 0.50),
        "basis": "DOE-reported seawater RO electric range; recovery is a screening assumption",
    },
    "thermal_desalination": {
        "electric_kwh_per_m3": (1.0, 3.0),
        "thermal_kwhth_per_m3": (20.0, 80.0),
        "recovery_fraction": (0.25, 0.50),
        "basis": "Thermal-demand and recovery ranges are screening assumptions",
    },
    "industrial_water_recovery": {
        "electric_kwh_per_m3": (0.5, 4.0),
        "thermal_kwhth_per_m3": (0.0, 20.0),
        "recovery_fraction": (0.50, 0.95),
        "basis": "Electric/thermal demand and recovery are screening assumptions",
    },
}

def sample_range(bounds, n):
    low, high = bounds
    return rng.uniform(low, high, n)

def run_water_screen(process_name, n=N_SAMPLES):
    spec = WATER_PROCESSES[process_name]
    electric_kwh = sample_range(spec["electric_kwh_per_m3"], n)
    thermal_kwh = sample_range(spec["thermal_kwhth_per_m3"], n)
    recovery = sample_range(spec["recovery_fraction"], n)
    electric_capacity_kwh_day = AVAILABLE_ELECTRIC_MWE * 1000.0 * HOURS_PER_DAY
    thermal_capacity_kwh_day = AVAILABLE_PROCESS_HEAT_MWTH * 1000.0 * HOURS_PER_DAY
    water_by_electric = electric_capacity_kwh_day / electric_kwh
    water_by_thermal = np.full_like(thermal_kwh, np.inf, dtype=float)
    np.divide(thermal_capacity_kwh_day, thermal_kwh, out=water_by_thermal, where=thermal_kwh > 0.0)
    product_water_m3_day = np.minimum(water_by_electric, water_by_thermal)
    feed_water_m3_day = product_water_m3_day / recovery
    reject_water_m3_day = feed_water_m3_day - product_water_m3_day
    electric_fraction_used = product_water_m3_day * electric_kwh / electric_capacity_kwh_day
    thermal_fraction_used = np.where(thermal_kwh > 0.0, product_water_m3_day * thermal_kwh / thermal_capacity_kwh_day, 0.0)
    mass_balance_error_m3_day = feed_water_m3_day - product_water_m3_day - reject_water_m3_day
    interface_capacity_pass = (
        (electric_fraction_used <= 1.0 + 1e-12)
        & (thermal_fraction_used <= 1.0 + 1e-12)
    )
    accounting_pass = (
        np.isfinite(product_water_m3_day)
        & (product_water_m3_day > 0.0)
        & (recovery > 0.0)
        & (recovery < 1.0)
        & (np.abs(mass_balance_error_m3_day) <= 1e-9)
        & interface_capacity_pass
    )
    return pd.DataFrame({
        "system": "water",
        "process": process_name,
        "electric_kwh_per_m3": electric_kwh,
        "thermal_kwhth_per_m3": thermal_kwh,
        "recovery_fraction": recovery,
        "product_water_m3_day": product_water_m3_day,
        "feed_water_m3_day": feed_water_m3_day,
        "reject_water_m3_day": reject_water_m3_day,
        "electric_fraction_used": electric_fraction_used,
        "thermal_fraction_used": thermal_fraction_used,
        "mass_balance_error_m3_day": mass_balance_error_m3_day,
        "interface_capacity_pass": interface_capacity_pass,
        "accounting_pass": accounting_pass,
        "quality_validation_status": "NOT_MODELED",
    })


# Lithium screen: simplified brine-to-lithium mass balance.
# This does not model sorbent chemistry, selectivity, impurity rejection, or product crystallization.
LI_TO_LI2CO3 = 73.89 / 13.88  # stoichiometric mass conversion, Li to Li2CO3

def run_lithium_screen(n=N_SAMPLES):
    brine_flow_m3_day = rng.uniform(100.0, 10000.0, n)
    lithium_mg_per_L = rng.uniform(20.0, 300.0, n)
    recovery_fraction = rng.uniform(0.40, 0.90, n)
    product_purity_fraction = rng.uniform(0.90, 0.999, n)
    energy_kwh_per_m3 = rng.uniform(0.5, 10.0, n)
    process_water_m3_per_kg_product = rng.uniform(0.10, 2.0, n)
    reagent_kg_per_kg_product = rng.uniform(0.10, 5.0, n)

    lithium_feed_kg_day = lithium_mg_per_L * brine_flow_m3_day * 1000.0 / 1e6
    lithium_recovered_kg_day = lithium_feed_kg_day * recovery_fraction
    nominal_product_kg_day = lithium_recovered_kg_day * LI_TO_LI2CO3
    product_kg_day = nominal_product_kg_day * product_purity_fraction
    energy_kwh_day = brine_flow_m3_day * energy_kwh_per_m3
    water_use_m3_day = product_kg_day * process_water_m3_per_kg_product
    reagent_use_kg_day = product_kg_day * reagent_kg_per_kg_product
    energy_kwh_per_kg_product = energy_kwh_day / np.maximum(product_kg_day, 1e-12)
    mass_balance_error_kg_day = lithium_feed_kg_day * recovery_fraction - lithium_recovered_kg_day
    electric_capacity_kwh_day = AVAILABLE_ELECTRIC_MWE * 1000.0 * HOURS_PER_DAY
    electric_fraction_used = energy_kwh_day / electric_capacity_kwh_day
    interface_capacity_pass = electric_fraction_used <= 1.0 + 1e-12
    mass_balance_identity_pass = np.abs(mass_balance_error_kg_day) <= 1e-12
    accounting_pass = (
        (brine_flow_m3_day > 0.0)
        & (lithium_mg_per_L > 0.0)
        & (recovery_fraction > 0.0)
        & (recovery_fraction <= 1.0)
        & (product_purity_fraction > 0.0)
        & (product_purity_fraction <= 1.0)
        & (product_kg_day > 0.0)
        & mass_balance_identity_pass
        & interface_capacity_pass
    )
    battery_grade_screen = product_purity_fraction >= 0.995
    return pd.DataFrame({
        "system": "lithium",
        "process": "simplified_brine_mass_balance",
        "brine_flow_m3_day": brine_flow_m3_day,
        "lithium_mg_per_L": lithium_mg_per_L,
        "recovery_fraction": recovery_fraction,
        "product_purity_fraction": product_purity_fraction,
        "lithium_feed_kg_day": lithium_feed_kg_day,
        "lithium_recovered_kg_day": lithium_recovered_kg_day,
        "product_kg_day": product_kg_day,
        "energy_kwh_per_m3": energy_kwh_per_m3,
        "energy_kwh_day": energy_kwh_day,
        "electric_fraction_used": electric_fraction_used,
        "energy_kwh_per_kg_product": energy_kwh_per_kg_product,
        "process_water_m3_per_kg_product": process_water_m3_per_kg_product,
        "water_use_m3_day": water_use_m3_day,
        "reagent_kg_per_kg_product": reagent_kg_per_kg_product,
        "reagent_use_kg_day": reagent_use_kg_day,
        "mass_balance_error_kg_day": mass_balance_error_kg_day,
        "interface_capacity_pass": interface_capacity_pass,
        "mass_balance_identity_pass": mass_balance_identity_pass,
        "accounting_pass": accounting_pass,
        "battery_grade_screen": battery_grade_screen,
        "product_basis": "Li2CO3-equivalent mass/day after declared purity adjustment",
        "chemistry_validation_status": "NOT_MODELED",
    })


def summarize(frame, metrics):
    rows = []
    for metric in metrics:
        values = pd.to_numeric(frame[metric], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({
            "system": frame["system"].iloc[0],
            "process": frame["process"].iloc[0],
            "metric": metric,
            "P10": float(values.quantile(0.10)),
            "P50": float(values.quantile(0.50)),
            "P90": float(values.quantile(0.90)),
            "mean": float(values.mean()),
        })
    return pd.DataFrame(rows)

water_frames = [run_water_screen(name) for name in WATER_PROCESSES]
water_results = pd.concat(water_frames, ignore_index=True)
lithium_results = run_lithium_screen()
all_results = pd.concat([water_results, lithium_results], ignore_index=True, sort=False)

water_metrics = ["product_water_m3_day", "feed_water_m3_day", "reject_water_m3_day", "electric_fraction_used", "thermal_fraction_used"]
lithium_metrics = ["product_kg_day", "energy_kwh_per_kg_product", "water_use_m3_day", "reagent_use_kg_day", "product_purity_fraction"]
summary = pd.concat([
    pd.concat(
        [summarize(group, water_metrics) for _, group in water_results.groupby("process", sort=True)],
        ignore_index=True,
    ),
    summarize(lithium_results, lithium_metrics),
], ignore_index=True)

branch_summary = all_results.groupby(["system", "process"], dropna=False).agg(
    rows=("accounting_pass", "size"),
    passing_rows=("accounting_pass", "sum"),
    interface_passing_rows=("interface_capacity_pass", "sum"),
).reset_index()
branch_summary["accounting_pass_percent"] = 100.0 * branch_summary["passing_rows"] / branch_summary["rows"]
branch_summary["interface_capacity_pass_percent"] = 100.0 * branch_summary["interface_passing_rows"] / branch_summary["rows"]
branch_summary["interpretation"] = "Accounting closure of declared assumptions; not process validation or a probability of process success."
branch_summary["process_validity_status"] = "NOT_VALIDATED"

lithium_assumption_summary = {
    "purity_assumption_P10_percent": float(lithium_results["product_purity_fraction"].quantile(0.10) * 100.0),
    "purity_assumption_P50_percent": float(lithium_results["product_purity_fraction"].quantile(0.50) * 100.0),
    "purity_assumption_P90_percent": float(lithium_results["product_purity_fraction"].quantile(0.90) * 100.0),
    "battery_grade_screen_threshold_percent": 99.5,
    "battery_grade_screen_coverage_percent": float(lithium_results["battery_grade_screen"].mean() * 100.0),
}
lithium_capacity_feasible = lithium_results[lithium_results["interface_capacity_pass"]]
if lithium_capacity_feasible.empty:
    raise RuntimeError("No lithium scenarios fit within the declared electrical interface; widen the scenario or increase the interface before summarizing.")
lithium_capacity_feasible_summary = {
    "rows": int(len(lithium_capacity_feasible)),
    "coverage_percent": float(100.0 * len(lithium_capacity_feasible) / len(lithium_results)),
    "product_kg_day_P10": float(lithium_capacity_feasible["product_kg_day"].quantile(0.10)),
    "product_kg_day_P50": float(lithium_capacity_feasible["product_kg_day"].quantile(0.50)),
    "product_kg_day_P90": float(lithium_capacity_feasible["product_kg_day"].quantile(0.90)),
}

model_checks = {
    "hours_per_day": HOURS_PER_DAY,
    "continuous_electric_capacity_kwh_per_day": AVAILABLE_ELECTRIC_MWE * 1000.0 * HOURS_PER_DAY,
    "continuous_thermal_capacity_kwhth_per_day": AVAILABLE_PROCESS_HEAT_MWTH * 1000.0 * HOURS_PER_DAY,
    "water_max_abs_mass_balance_error_m3_day": float(np.max(np.abs(water_results["mass_balance_error_m3_day"]))),
    "lithium_max_abs_recovery_identity_error_kg_day": float(np.max(np.abs(lithium_results["mass_balance_error_kg_day"]))),
    "accounting_pass_is_subset_of_interface_capacity_pass": bool((~all_results["accounting_pass"] | all_results["interface_capacity_pass"]).all()),
}
assert model_checks["continuous_electric_capacity_kwh_per_day"] == 24000.0 * AVAILABLE_ELECTRIC_MWE
assert model_checks["continuous_thermal_capacity_kwhth_per_day"] == 24000.0 * AVAILABLE_PROCESS_HEAT_MWTH
assert model_checks["water_max_abs_mass_balance_error_m3_day"] <= 1e-9
assert model_checks["lithium_max_abs_recovery_identity_error_kg_day"] <= 1e-12
assert model_checks["accounting_pass_is_subset_of_interface_capacity_pass"]
print("Model checks: PASS")

water_results.to_csv(OUTPUT_ROOT / "water_screen_all_results.csv", index=False)
lithium_results.to_csv(OUTPUT_ROOT / "lithium_screen_all_results.csv", index=False)
all_results.to_csv(OUTPUT_ROOT / "secondary_systems_all_results.csv", index=False)
summary.to_csv(OUTPUT_ROOT / "secondary_systems_summary.csv", index=False)
branch_summary.to_csv(OUTPUT_ROOT / "secondary_systems_branch_summary.csv", index=False)

manifest = {
    "model": "Tomahawk secondary-systems bounded feasibility screen",
    "seed": SEED,
    "samples_per_branch": N_SAMPLES,
    "hours_per_day": HOURS_PER_DAY,
    "normalized_process_interface": {
        "available_process_heat_MWth": AVAILABLE_PROCESS_HEAT_MWTH,
        "available_electric_MWe": AVAILABLE_ELECTRIC_MWE,
    },
    "scope": "Water process energy/mass balance plus simplified lithium brine mass balance",
    "capacity_constraints_enforced": True,
    "not_established": [
        "Tomahawk reactor output",
        "potable-water quality",
        "lithium selectivity or impurity rejection",
        "battery-grade product certification",
        "process equipment lifetime",
        "commercial economics",
        "process validation despite accounting_pass coverage",
    ],
    "water_reference": "DOE water-energy report; seawater RO 3.0-4.7 kWh/m3",
    "lithium_reference": "DOE geothermal lithium overview; qualitative context only",
    "lithium_purity_assumption_summary": lithium_assumption_summary,
    "lithium_capacity_feasible_summary": lithium_capacity_feasible_summary,
    "model_checks": model_checks,
    "branch_summary": branch_summary.to_dict(orient="records"),
}
(OUTPUT_ROOT / "secondary_systems_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(branch_summary.to_string(index=False))
print("Wrote result bundle:", OUTPUT_ROOT)


# Compact visual summary for diligence review.
water_plot = summary[summary["system"] == "water"].pivot(index="process", columns="metric", values="P50")
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
water_plot["product_water_m3_day"].plot(kind="bar", ax=axes[0], color="#2E74B5", title="Median water production per normalized interface")
axes[0].set_ylabel("m³/day from 1 MW interface")
axes[0].tick_params(axis="x", rotation=20)
axes[0].grid(axis="y", alpha=0.25)

li = summary[(summary["system"] == "lithium") & (summary["metric"] == "product_kg_day")].iloc[0]
li_energy = summary[(summary["system"] == "lithium") & (summary["metric"] == "energy_kwh_per_kg_product")].iloc[0]
axes[1].bar(["P10", "P50", "P90"], [li["P10"], li["P50"], li["P90"]], color="#16A4BA")
axes[1].set_title("Lithium-product screen: daily output")
axes[1].set_ylabel("kg/day; simplified mass balance")
axes[1].grid(axis="y", alpha=0.25)
fig.suptitle("Conditional secondary-systems screen — not process validation", fontsize=13)
fig.tight_layout()
fig.savefig(OUTPUT_ROOT / "secondary_systems_summary.png", dpi=170)
plt.close(fig)
print("Median lithium product kg/day:", round(float(li["P50"]), 3))
print("Median lithium energy kWh/kg product:", round(float(li_energy["P50"]), 3))
