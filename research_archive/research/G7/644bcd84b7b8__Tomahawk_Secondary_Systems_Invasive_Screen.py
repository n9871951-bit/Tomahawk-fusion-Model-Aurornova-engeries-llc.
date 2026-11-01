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
OUTPUT_ROOT = Path(output_root_env) if output_root_env else (Path("/kaggle/working/tomahawk_secondary_systems_invasive") if Path("/kaggle/working").exists() else Path.cwd() / "tomahawk_secondary_systems_invasive")
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


# Invasive deep-run extension: repeated stress, convergence, dispatch, and sensitivity analysis.
# Default Kaggle behavior is a minimum 30-minute run. Set TOMAHAWK_SECONDARY_DEEP_RUN=0 for a short preflight.
DEEP_RUN = os.environ.get("TOMAHAWK_SECONDARY_DEEP_RUN", "1") == "1"
TARGET_MINUTES = float(os.environ.get("TOMAHAWK_SECONDARY_DEEP_RUN_MINUTES", "30"))
BATCH_SIZE = int(os.environ.get("TOMAHAWK_SECONDARY_BATCH_SIZE", "250000"))
MAX_BATCHES = int(os.environ.get("TOMAHAWK_SECONDARY_MAX_BATCHES", "0"))
if TARGET_MINUTES < 0.0 or BATCH_SIZE < 1000:
    raise ValueError("Deep-run minutes must be nonnegative and batch size must be at least 1000")

input_root = Path("/kaggle/input")
input_files = [p for p in input_root.rglob("*") if p.is_file()] if input_root.exists() else []
inventory_rows = []
for path in input_files:
    row = {"path": str(path), "suffix": path.suffix.lower(), "bytes": path.stat().st_size, "read_status": "INVENTORIED_ONLY", "columns_or_keys": "", "error": ""}
    try:
        if path.suffix.lower() in {".csv", ".tsv"}:
            frame = pd.read_csv(path, sep="\t" if path.suffix.lower() == ".tsv" else ",", nrows=100)
            row["read_status"] = "READ_SAMPLE_ONLY"
            row["columns_or_keys"] = "|".join(str(c) for c in frame.columns)
        elif path.suffix.lower() == ".json":
            json.loads(path.read_text(encoding="utf-8"))
            row["read_status"] = "PARSED_JSON"
        elif path.suffix.lower() == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                row["read_status"] = "PARSED_NPZ"
                row["columns_or_keys"] = "|".join(archive.files)
    except Exception as exc:
        row["read_status"] = "READ_ERROR"
        row["error"] = repr(exc)
    inventory_rows.append(row)
if not inventory_rows:
    inventory_rows = [{"path": str(input_root), "suffix": "", "bytes": 0, "read_status": "NO_EXTERNAL_INPUT_FILES", "columns_or_keys": "", "error": ""}]
pd.DataFrame(inventory_rows).to_csv(OUTPUT_ROOT / "deep_input_inventory.csv", index=False)
data_file = os.environ.get("TOMAHAWK_SECONDARY_DATA_FILE", "").strip()
if data_file:
    candidate_data_file = Path(data_file)
    if not candidate_data_file.is_absolute() and input_root.exists():
        candidate_data_file = input_root / candidate_data_file
    if not candidate_data_file.exists():
        raise FileNotFoundError(f"Declared TOMAHAWK_SECONDARY_DATA_FILE does not exist: {candidate_data_file}")
    data_file = str(candidate_data_file)
    data_status = "DECLARED_FILE_INVENTORIED_NOT_SILENTLY_USED"
else:
    data_status = "NO_PROCESS_DATASET_CONNECTED"

class Reservoir:
    def __init__(self, seed, max_samples=100000):
        self.rng = np.random.default_rng(seed)
        self.max_samples = max_samples
        self.values = np.empty(0, dtype=float)
        self.count = 0
        self.total = 0.0
        self.minimum = np.inf
        self.maximum = -np.inf
    def update(self, values):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return
        self.count += int(values.size)
        self.total += float(values.sum())
        self.minimum = min(self.minimum, float(values.min()))
        self.maximum = max(self.maximum, float(values.max()))
        take = min(2000, values.size)
        chosen = values[self.rng.integers(0, values.size, size=take)]
        if self.values.size < self.max_samples:
            room = self.max_samples - self.values.size
            self.values = np.concatenate([self.values, chosen[:room]])
            chosen = chosen[room:]
        if chosen.size:
            slots = self.rng.integers(0, self.max_samples, size=chosen.size)
            self.values[slots] = chosen
    def summarize(self):
        return {"count": self.count, "P10": float(np.quantile(self.values, 0.10)), "P50": float(np.quantile(self.values, 0.50)), "P90": float(np.quantile(self.values, 0.90)), "mean": self.total / self.count, "min": self.minimum, "max": self.maximum}

deep_metrics = {
    "water": ["product_water_m3_day", "electric_fraction_used", "thermal_fraction_used"],
    "lithium": ["product_kg_day", "energy_kwh_per_kg_product", "electric_fraction_used", "product_purity_fraction"],
}
reservoirs = {}
for index, (system, metrics) in enumerate(deep_metrics.items()):
    for metric_index, metric in enumerate(metrics):
        reservoirs[(system, metric)] = Reservoir(SEED + 1000 + index * 100 + metric_index)
batch_rows = []
pass_rows = []
start_time = time.monotonic()
last_report = start_time
batch_number = 0
target_seconds = TARGET_MINUTES * 60.0
original_electric_mwe = AVAILABLE_ELECTRIC_MWE

while True:
    elapsed = time.monotonic() - start_time
    if batch_number > 0 and (not DEEP_RUN or elapsed >= target_seconds):
        break
    if MAX_BATCHES > 0 and batch_number >= MAX_BATCHES:
        break
    batch_number += 1
    rng = np.random.default_rng(SEED + batch_number * 1009)
    for process_name in WATER_PROCESSES:
        frame = run_water_screen(process_name, BATCH_SIZE)
        for metric in deep_metrics["water"]:
            reservoirs[("water", metric)].update(frame[metric].to_numpy())
            quantiles = frame[metric].replace([np.inf, -np.inf], np.nan).dropna().quantile([0.10, 0.50, 0.90])
            batch_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "water", "process": process_name, "metric": metric, "P10": float(quantiles.loc[0.10]), "P50": float(quantiles.loc[0.50]), "P90": float(quantiles.loc[0.90])})
        pass_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "water", "process": process_name, "rows": len(frame), "accounting_pass_percent": float(frame["accounting_pass"].mean() * 100.0), "interface_capacity_pass_percent": float(frame["interface_capacity_pass"].mean() * 100.0), "battery_grade_screen_percent": np.nan})
        del frame
    frame = run_lithium_screen(BATCH_SIZE)
    for metric in deep_metrics["lithium"]:
        reservoirs[("lithium", metric)].update(frame[metric].to_numpy())
        quantiles = frame[metric].replace([np.inf, -np.inf], np.nan).dropna().quantile([0.10, 0.50, 0.90])
        batch_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "lithium", "process": "simplified_brine_mass_balance", "metric": metric, "P10": float(quantiles.loc[0.10]), "P50": float(quantiles.loc[0.50]), "P90": float(quantiles.loc[0.90])})
    pass_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "lithium", "process": "simplified_brine_mass_balance", "rows": len(frame), "accounting_pass_percent": float(frame["accounting_pass"].mean() * 100.0), "interface_capacity_pass_percent": float(frame["interface_capacity_pass"].mean() * 100.0), "battery_grade_screen_percent": float(frame["battery_grade_screen"].mean() * 100.0)})
    del frame
    if batch_number % 10 == 0:
        pd.DataFrame(batch_rows).to_csv(OUTPUT_ROOT / "deep_batch_convergence_checkpoint.csv", index=False)
        pd.DataFrame(pass_rows).to_csv(OUTPUT_ROOT / "deep_pass_rates_checkpoint.csv", index=False)
    if time.monotonic() - last_report >= 60.0:
        print(f"heartbeat: batch={batch_number}, elapsed_minutes={(time.monotonic() - start_time) / 60.0:.2f}")
        last_report = time.monotonic()

deep_elapsed_seconds = time.monotonic() - start_time
deep_summary_rows = []
for (system, metric), accumulator in reservoirs.items():
    deep_summary_rows.append({"system": system, "metric": metric, **accumulator.summarize()})
deep_summary = pd.DataFrame(deep_summary_rows)
deep_summary.to_csv(OUTPUT_ROOT / "deep_summary.csv", index=False)
batch_convergence = pd.DataFrame(batch_rows)
pass_history = pd.DataFrame(pass_rows)
batch_convergence.to_csv(OUTPUT_ROOT / "deep_batch_convergence.csv", index=False)
pass_history.to_csv(OUTPUT_ROOT / "deep_pass_rates_history.csv", index=False)
branch_summary = pass_history.groupby(["system", "process"], as_index=False).agg(
    batches=("batch", "count"), rows=("rows", "sum"),
    accounting_pass_percent_P10=("accounting_pass_percent", lambda s: float(s.quantile(0.10))),
    accounting_pass_percent_P50=("accounting_pass_percent", lambda s: float(s.quantile(0.50))),
    accounting_pass_percent_P90=("accounting_pass_percent", lambda s: float(s.quantile(0.90))),
    interface_capacity_pass_percent_P50=("interface_capacity_pass_percent", "median"),
    battery_grade_screen_percent_P50=("battery_grade_screen_percent", "median"),
)
branch_summary["process_validity_status"] = "NOT_VALIDATED"
branch_summary["interpretation"] = "Declared scenario arithmetic and interface gates only; not process or reactor validation."
branch_summary.to_csv(OUTPUT_ROOT / "deep_branch_summary.csv", index=False)

dispatch_rows = []
for lithium_share in (0.10, 0.25, 0.50, 0.75, 0.90):
    AVAILABLE_ELECTRIC_MWE = original_electric_mwe * (1.0 - lithium_share)
    rng = np.random.default_rng(SEED + int(lithium_share * 10000) + 20000)
    water = run_water_screen("seawater_ro", 100000)
    AVAILABLE_ELECTRIC_MWE = original_electric_mwe * lithium_share
    rng = np.random.default_rng(SEED + int(lithium_share * 10000) + 21000)
    lithium = run_lithium_screen(100000)
    lithium_feasible = lithium[lithium["interface_capacity_pass"]]
    dispatch_rows.append({"lithium_electric_share": lithium_share, "water_electric_share": 1.0 - lithium_share, "water_product_m3_day_P50": float(water["product_water_m3_day"].median()), "lithium_product_kg_day_all_P50": float(lithium["product_kg_day"].median()), "lithium_capacity_pass_percent": float(lithium["interface_capacity_pass"].mean() * 100.0), "lithium_product_kg_day_capacity_feasible_P50": float(lithium_feasible["product_kg_day"].median()) if len(lithium_feasible) else np.nan})
AVAILABLE_ELECTRIC_MWE = original_electric_mwe
dispatch = pd.DataFrame(dispatch_rows)
dispatch.to_csv(OUTPUT_ROOT / "co_production_dispatch.csv", index=False)

def spearman(a, b):
    return float(pd.Series(a).rank(method="average").corr(pd.Series(b).rank(method="average")))

sensitivity_rows = []
rng = np.random.default_rng(SEED + 30000)
li_sens = run_lithium_screen(200000)
for input_col in ["brine_flow_m3_day", "lithium_mg_per_L", "recovery_fraction", "product_purity_fraction", "energy_kwh_per_m3"]:
    for target_col in ["product_kg_day", "energy_kwh_per_kg_product", "electric_fraction_used"]:
        rho = spearman(li_sens[input_col], li_sens[target_col])
        sensitivity_rows.append({"system": "lithium", "input": input_col, "target": target_col, "spearman_r": rho, "abs_spearman_r": abs(rho)})
rng = np.random.default_rng(SEED + 31000)
water_sens = run_water_screen("seawater_ro", 200000)
for input_col in ["electric_kwh_per_m3", "recovery_fraction"]:
    rho = spearman(water_sens[input_col], water_sens["product_water_m3_day"])
    sensitivity_rows.append({"system": "water", "input": input_col, "target": "product_water_m3_day", "spearman_r": rho, "abs_spearman_r": abs(rho)})
sensitivity = pd.DataFrame(sensitivity_rows).sort_values(["system", "target", "abs_spearman_r"], ascending=[True, True, False])
sensitivity.to_csv(OUTPUT_ROOT / "sensitivity_rank.csv", index=False)

def water_point(case, electric_kwh, thermal_kwh, recovery):
    electric_cap = original_electric_mwe * 1000.0 * HOURS_PER_DAY
    thermal_cap = AVAILABLE_PROCESS_HEAT_MWTH * 1000.0 * HOURS_PER_DAY
    product = min(electric_cap / electric_kwh, np.inf if thermal_kwh == 0.0 else thermal_cap / thermal_kwh)
    feed = product / recovery
    return {"system": "water", "case": case, "product_water_m3_day": product, "feed_water_m3_day": feed, "reject_water_m3_day": feed - product, "capacity_pass": True}

def lithium_point(case, flow, concentration, recovery, purity, energy):
    feed = concentration * flow * 1000.0 / 1e6
    product = feed * recovery * LI_TO_LI2CO3 * purity
    energy_day = flow * energy
    return {"system": "lithium", "case": case, "product_kg_day": product, "energy_kwh_day": energy_day, "electric_fraction_used": energy_day / (original_electric_mwe * 1000.0 * HOURS_PER_DAY), "capacity_pass": energy_day <= original_electric_mwe * 1000.0 * HOURS_PER_DAY}

stress_rows = [
    water_point("RO_conservative_range_edge", 4.7, 0.0, 0.35),
    water_point("thermal_desalination_worst_range_edge", 3.0, 80.0, 0.25),
    water_point("industrial_recovery_worst_range_edge", 4.0, 20.0, 0.50),
    lithium_point("lithium_conservative_low_feed", 100.0, 20.0, 0.40, 0.90, 10.0),
    lithium_point("lithium_high_load_capacity_failure", 10000.0, 300.0, 0.40, 0.90, 10.0),
]
pd.DataFrame(stress_rows).to_csv(OUTPUT_ROOT / "stress_cases.csv", index=False)

deep_manifest = {
    "model": "Tomahawk secondary-systems invasive validation screen",
    "seed": SEED, "deep_run_enabled": DEEP_RUN, "target_runtime_minutes": TARGET_MINUTES,
    "actual_runtime_minutes": deep_elapsed_seconds / 60.0, "batch_size": BATCH_SIZE,
    "batches_completed": batch_number, "samples_per_branch": batch_number * BATCH_SIZE,
    "hours_per_day": HOURS_PER_DAY, "input_inventory_status": data_status,
    "declared_data_file": data_file or None, "capacity_constraints_enforced": True,
    "scope": "Repeated capacity-constrained water/lithium scenarios, convergence, dispatch, stress, and sensitivity",
    "not_established": ["Tomahawk reactor output or net energy", "potable-water quality", "lithium chemistry/selectivity/impurity rejection", "battery-grade certification", "equipment lifetime/corrosion/fouling", "commercial economics or offtake", "process validation despite scenario-gate closure"],
    "water_reference": "DOE water-energy report; seawater RO 3.0-4.7 kWh/m3",
    "lithium_reference": "DOE geothermal lithium program; pilot-validation context only",
    "model_checks": model_checks,
    "outputs": ["deep_input_inventory.csv", "model_checks.json", "deep_summary.csv", "deep_branch_summary.csv", "deep_batch_convergence.csv", "deep_pass_rates_history.csv", "co_production_dispatch.csv", "stress_cases.csv", "sensitivity_rank.csv", "secondary_systems_invasive_manifest.json"],
}
(OUTPUT_ROOT / "secondary_systems_invasive_manifest.json").write_text(json.dumps(deep_manifest, indent=2), encoding="utf-8")

fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
water_conv = batch_convergence[(batch_convergence["system"] == "water") & (batch_convergence["metric"] == "product_water_m3_day")]
for process, group in water_conv.groupby("process"):
    axes[0].plot(group["batch"], group["P50"], label=process)
axes[0].set_title("Water P50 convergence")
axes[0].set_xlabel("batch")
axes[0].set_ylabel("m³/day")
axes[0].grid(alpha=0.25)
axes[0].legend(fontsize=8)
axes[1].plot(dispatch["lithium_electric_share"], dispatch["water_product_m3_day_P50"], marker="o")
axes[1].set_title("Co-production electricity tradeoff")
axes[1].set_xlabel("electricity share allocated to lithium")
axes[1].set_ylabel("water P50 m³/day")
axes[1].grid(alpha=0.25)
fig.suptitle("Tomahawk secondary-systems invasive screen — conditional, not process validation")
fig.tight_layout()
fig.savefig(OUTPUT_ROOT / "secondary_systems_invasive_summary.png", dpi=180)
plt.close(fig)
print("Invasive run complete.")
print("Elapsed minutes:", round(deep_elapsed_seconds / 60.0, 3), "Batches:", batch_number)
print(branch_summary.to_string(index=False))
