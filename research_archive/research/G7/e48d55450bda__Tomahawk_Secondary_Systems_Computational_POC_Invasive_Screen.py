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
BASE_ROWS_PER_BRANCH = int(os.environ.get("TOMAHAWK_SECONDARY_BASE_ROWS", "10000"))
AVAILABLE_PROCESS_HEAT_MWTH = float(os.environ.get("TOMAHAWK_PROCESS_HEAT_MWTH", "1.0"))
AVAILABLE_ELECTRIC_MWE = float(os.environ.get("TOMAHAWK_PROCESS_ELECTRIC_MWE", "1.0"))
HOURS_PER_DAY = 24.0
DATASET_ID = "secondary_systems_computational_poc_v1"
DATASET_SOURCE = "model_generated_from_declared_screening_ranges"
PRIOR_POC_DATA_MIXED = False

output_root_env = os.environ.get("TOMAHAWK_SECONDARY_OUTPUT_ROOT", "")
OUTPUT_ROOT = Path(output_root_env) if output_root_env else (Path("/kaggle/working/tomahawk_secondary_systems_computational_poc") if Path("/kaggle/working").exists() else Path.cwd() / "tomahawk_secondary_systems_computational_poc")
OUTPUT_ROOT = OUTPUT_ROOT.resolve()
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

if BASE_ROWS_PER_BRANCH < 100:
    raise ValueError("TOMAHAWK_SECONDARY_BASE_ROWS must be at least 100")
if AVAILABLE_PROCESS_HEAT_MWTH <= 0.0 or AVAILABLE_ELECTRIC_MWE <= 0.0:
    raise ValueError("Process heat and electricity interface values must be positive")
if OUTPUT_ROOT.name in {"tomahawk_secondary_systems_screen", "tomahawk_secondary_systems_invasive"}:
    raise ValueError("Refusing to write into an earlier secondary-systems output folder")

print("Python:", platform.python_version())
print("Seed:", SEED)
print("Dataset ID:", DATASET_ID)
print("Dataset source:", DATASET_SOURCE)
print("Prior POC data mixed:", PRIOR_POC_DATA_MIXED)
print("Base rows per branch:", BASE_ROWS_PER_BRANCH)
print("Normalized process interface:", AVAILABLE_PROCESS_HEAT_MWTH, "MWth +", AVAILABLE_ELECTRIC_MWE, "MWe")
print("Continuous interface energy:", AVAILABLE_PROCESS_HEAT_MWTH * 1000.0 * HOURS_PER_DAY, "kWhth/day +", AVAILABLE_ELECTRIC_MWE * 1000.0 * HOURS_PER_DAY, "kWhe/day")
print("Output:", OUTPUT_ROOT)
# Declared model ranges. RO electric intensity is anchored to the DOE water-energy reference;
# the other ranges are screening assumptions until replaced by process-specific evidence.
WATER_PROCESSES = {
    "seawater_ro": {
        "electric_kwh_per_m3": (3.0, 4.7),
        "thermal_kwhth_per_m3": (0.0, 0.0),
        "recovery_fraction": (0.35, 0.50),
        "target_product_m3_day": (1000.0, 10000.0),
        "basis": "DOE-reported seawater RO electric range; recovery and target throughput are screening assumptions",
    },
    "thermal_desalination": {
        "electric_kwh_per_m3": (1.0, 3.0),
        "thermal_kwhth_per_m3": (20.0, 80.0),
        "recovery_fraction": (0.25, 0.50),
        "target_product_m3_day": (100.0, 1500.0),
        "basis": "Thermal demand, recovery, and target throughput are screening assumptions",
    },
    "industrial_water_recovery": {
        "electric_kwh_per_m3": (0.5, 4.0),
        "thermal_kwhth_per_m3": (0.0, 20.0),
        "recovery_fraction": (0.50, 0.95),
        "target_product_m3_day": (500.0, 6000.0),
        "basis": "Electric/thermal demand, recovery, and target throughput are screening assumptions",
    },
}

LITHIUM_INPUT_RANGES = {
    "brine_flow_m3_day": (100.0, 10000.0),
    "lithium_mg_per_L": (20.0, 300.0),
    "recovery_fraction": (0.40, 0.90),
    "product_purity_fraction": (0.90, 0.999),
    "energy_kwh_per_m3": (0.5, 10.0),
    "process_water_m3_per_kg_product": (0.10, 2.0),
    "reagent_kg_per_kg_product": (0.10, 5.0),
    "target_product_kg_day": (100.0, 5000.0),
}

LI_TO_LI2CO3 = 73.89 / 13.88

def arr(value):
    return np.asarray(value, dtype=float)

def evaluate_water_inputs(process_name, electric_kwh, thermal_kwh, recovery, target_product, available_electric_mwe=None, available_heat_mwth=None):
    electric_kwh = arr(electric_kwh)
    thermal_kwh = arr(thermal_kwh)
    recovery = arr(recovery)
    target_product = arr(target_product)
    available_electric_mwe = AVAILABLE_ELECTRIC_MWE if available_electric_mwe is None else float(available_electric_mwe)
    available_heat_mwth = AVAILABLE_PROCESS_HEAT_MWTH if available_heat_mwth is None else float(available_heat_mwth)
    electric_capacity_kwh_day = available_electric_mwe * 1000.0 * HOURS_PER_DAY
    thermal_capacity_kwh_day = available_heat_mwth * 1000.0 * HOURS_PER_DAY
    feed_water = target_product / recovery
    reject_water = feed_water - target_product
    required_electric = target_product * electric_kwh
    required_thermal = target_product * thermal_kwh
    max_by_electric = electric_capacity_kwh_day / electric_kwh
    max_by_thermal = np.full_like(thermal_kwh, np.inf, dtype=float)
    np.divide(thermal_capacity_kwh_day, thermal_kwh, out=max_by_thermal, where=thermal_kwh > 0.0)
    max_supported = np.minimum(max_by_electric, max_by_thermal)
    electric_fraction = required_electric / electric_capacity_kwh_day
    thermal_fraction = np.where(thermal_kwh > 0.0, required_thermal / thermal_capacity_kwh_day, 0.0)
    independently_recomputed_product = feed_water * recovery
    mass_balance_error = feed_water - target_product - reject_water
    recovery_identity_error = independently_recomputed_product - target_product
    domain_valid = ((electric_kwh > 0.0) & (thermal_kwh >= 0.0) & (recovery > 0.0) & (recovery < 1.0) & (target_product > 0.0) & np.isfinite(electric_kwh) & np.isfinite(thermal_kwh) & np.isfinite(recovery) & np.isfinite(target_product))
    mass_balance_pass = np.abs(mass_balance_error) <= 1e-9
    recovery_identity_pass = np.abs(recovery_identity_error) <= 1e-9
    interface_capacity_pass = (required_electric <= electric_capacity_kwh_day + 1e-9) & (required_thermal <= thermal_capacity_kwh_day + 1e-9)
    target_met = max_supported >= target_product - 1e-9
    accounting_pass = domain_valid & mass_balance_pass & recovery_identity_pass
    poc_pass = accounting_pass & interface_capacity_pass & target_met
    return pd.DataFrame({
        "dataset_id": DATASET_ID,
        "source_type": DATASET_SOURCE,
        "system": "water",
        "process": process_name,
        "electric_kwh_per_m3": electric_kwh,
        "thermal_kwhth_per_m3": thermal_kwh,
        "recovery_fraction": recovery,
        "target_product_water_m3_day": target_product,
        "feed_water_m3_day": feed_water,
        "product_water_m3_day": target_product,
        "reject_water_m3_day": reject_water,
        "required_electric_kwh_day": required_electric,
        "required_thermal_kwhth_day": required_thermal,
        "max_supported_product_water_m3_day": max_supported,
        "electric_fraction_used": electric_fraction,
        "thermal_fraction_used": thermal_fraction,
        "capacity_margin_water_m3_day": max_supported - target_product,
        "mass_balance_error_m3_day": mass_balance_error,
        "recovery_identity_error_m3_day": recovery_identity_error,
        "domain_valid": domain_valid,
        "mass_balance_pass": mass_balance_pass,
        "recovery_identity_pass": recovery_identity_pass,
        "interface_capacity_pass": interface_capacity_pass,
        "target_met": target_met,
        "accounting_pass": accounting_pass,
        "poc_pass": poc_pass,
        "quality_validation_status": "NOT_MODELED",
        "process_validity_status": "NOT_VALIDATED",
    })
def evaluate_lithium_inputs(brine_flow_m3_day, lithium_mg_per_L, recovery_fraction, product_purity_fraction, energy_kwh_per_m3, process_water_m3_per_kg_product, reagent_kg_per_kg_product, target_product_kg_day, available_electric_mwe=None):
    brine_flow_m3_day = arr(brine_flow_m3_day)
    lithium_mg_per_L = arr(lithium_mg_per_L)
    recovery_fraction = arr(recovery_fraction)
    product_purity_fraction = arr(product_purity_fraction)
    energy_kwh_per_m3 = arr(energy_kwh_per_m3)
    process_water_m3_per_kg_product = arr(process_water_m3_per_kg_product)
    reagent_kg_per_kg_product = arr(reagent_kg_per_kg_product)
    target_product_kg_day = arr(target_product_kg_day)
    available_electric_mwe = AVAILABLE_ELECTRIC_MWE if available_electric_mwe is None else float(available_electric_mwe)
    electric_capacity_kwh_day = available_electric_mwe * 1000.0 * HOURS_PER_DAY
    lithium_feed = lithium_mg_per_L * brine_flow_m3_day * 1000.0 / 1e6
    lithium_recovered = lithium_feed * recovery_fraction
    lithium_tail = lithium_feed - lithium_recovered
    product = lithium_recovered * LI_TO_LI2CO3 * product_purity_fraction
    energy_day = brine_flow_m3_day * energy_kwh_per_m3
    water_use = product * process_water_m3_per_kg_product
    reagent_use = product * reagent_kg_per_kg_product
    energy_per_kg = energy_day / np.maximum(product, 1e-12)
    electric_fraction = energy_day / electric_capacity_kwh_day
    mass_balance_error = lithium_feed - lithium_recovered - lithium_tail
    product_recalculation_error = product - lithium_recovered * LI_TO_LI2CO3 * product_purity_fraction
    domain_valid = (
        (brine_flow_m3_day > 0.0) & (lithium_mg_per_L > 0.0) & (recovery_fraction > 0.0) & (recovery_fraction <= 1.0)
        & (product_purity_fraction > 0.0) & (product_purity_fraction <= 1.0) & (energy_kwh_per_m3 > 0.0)
        & (process_water_m3_per_kg_product >= 0.0) & (reagent_kg_per_kg_product >= 0.0) & (target_product_kg_day > 0.0)
        & np.isfinite(brine_flow_m3_day) & np.isfinite(lithium_mg_per_L) & np.isfinite(recovery_fraction)
        & np.isfinite(product_purity_fraction) & np.isfinite(energy_kwh_per_m3) & np.isfinite(target_product_kg_day)
    )
    mass_balance_pass = np.abs(mass_balance_error) <= 1e-12
    product_recalculation_pass = np.abs(product_recalculation_error) <= 1e-12
    interface_capacity_pass = energy_day <= electric_capacity_kwh_day + 1e-9
    target_met = product >= target_product_kg_day - 1e-9
    accounting_pass = domain_valid & mass_balance_pass & product_recalculation_pass
    poc_pass = accounting_pass & interface_capacity_pass & target_met
    return pd.DataFrame({
        "dataset_id": DATASET_ID,
        "source_type": DATASET_SOURCE,
        "system": "lithium",
        "process": "simplified_brine_mass_balance",
        "brine_flow_m3_day": brine_flow_m3_day,
        "lithium_mg_per_L": lithium_mg_per_L,
        "recovery_fraction": recovery_fraction,
        "product_purity_fraction": product_purity_fraction,
        "target_product_kg_day": target_product_kg_day,
        "lithium_feed_kg_day": lithium_feed,
        "lithium_recovered_kg_day": lithium_recovered,
        "lithium_tail_kg_day": lithium_tail,
        "product_kg_day": product,
        "energy_kwh_per_m3": energy_kwh_per_m3,
        "energy_kwh_day": energy_day,
        "electric_fraction_used": electric_fraction,
        "energy_kwh_per_kg_product": energy_per_kg,
        "process_water_m3_per_kg_product": process_water_m3_per_kg_product,
        "water_use_m3_day": water_use,
        "reagent_kg_per_kg_product": reagent_kg_per_kg_product,
        "reagent_use_kg_day": reagent_use,
        "target_margin_kg_day": product - target_product_kg_day,
        "mass_balance_error_kg_day": mass_balance_error,
        "product_recalculation_error_kg_day": product_recalculation_error,
        "domain_valid": domain_valid,
        "mass_balance_pass": mass_balance_pass,
        "product_recalculation_pass": product_recalculation_pass,
        "interface_capacity_pass": interface_capacity_pass,
        "target_met": target_met,
        "accounting_pass": accounting_pass,
        "poc_pass": poc_pass,
        "battery_grade_screen": product_purity_fraction >= 0.995,
        "product_basis": "Li2CO3-equivalent mass/day after declared purity adjustment",
        "chemistry_validation_status": "NOT_MODELED",
        "process_validity_status": "NOT_VALIDATED",
    })

def run_water_batch(process_name, n, rng, available_electric_mwe=None, available_heat_mwth=None):
    spec = WATER_PROCESSES[process_name]
    return evaluate_water_inputs(
        process_name,
        rng.uniform(*spec["electric_kwh_per_m3"], n),
        rng.uniform(*spec["thermal_kwhth_per_m3"], n),
        rng.uniform(*spec["recovery_fraction"], n),
        rng.uniform(*spec["target_product_m3_day"], n),
        available_electric_mwe=available_electric_mwe,
        available_heat_mwth=available_heat_mwth,
    )

def run_lithium_batch(n, rng, available_electric_mwe=None):
    return evaluate_lithium_inputs(
        rng.uniform(*LITHIUM_INPUT_RANGES["brine_flow_m3_day"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["lithium_mg_per_L"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["recovery_fraction"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["product_purity_fraction"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["energy_kwh_per_m3"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["process_water_m3_per_kg_product"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["reagent_kg_per_kg_product"], n),
        rng.uniform(*LITHIUM_INPUT_RANGES["target_product_kg_day"], n),
        available_electric_mwe=available_electric_mwe,
    )
# Base computational POC dataset and hard checks.
def summarize(frame, metrics):
    rows = []
    for metric in metrics:
        values = pd.to_numeric(frame[metric], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({
            "dataset_id": DATASET_ID,
            "system": frame["system"].iloc[0],
            "process": frame["process"].iloc[0],
            "metric": metric,
            "rows": int(len(values)),
            "P10": float(values.quantile(0.10)),
            "P50": float(values.quantile(0.50)),
            "P90": float(values.quantile(0.90)),
            "mean": float(values.mean()),
        })
    return pd.DataFrame(rows)

base_rng = np.random.default_rng(SEED)
base_water = pd.concat([run_water_batch(name, BASE_ROWS_PER_BRANCH, base_rng) for name in WATER_PROCESSES], ignore_index=True)
base_lithium = run_lithium_batch(BASE_ROWS_PER_BRANCH, base_rng)
base_dataset = pd.concat([base_water, base_lithium], ignore_index=True, sort=False)
base_dataset.insert(0, "run_scope", "base_computational_poc")
base_dataset.insert(1, "batch", 0)
base_dataset.insert(2, "row_id", np.arange(1, len(base_dataset) + 1, dtype=np.int64))

water_metrics = ["target_product_water_m3_day", "max_supported_product_water_m3_day", "capacity_margin_water_m3_day", "electric_fraction_used", "thermal_fraction_used", "mass_balance_error_m3_day"]
lithium_metrics = ["target_product_kg_day", "product_kg_day", "target_margin_kg_day", "energy_kwh_per_kg_product", "electric_fraction_used", "product_purity_fraction", "mass_balance_error_kg_day"]
base_summary = pd.concat([
    pd.concat([summarize(group, water_metrics) for _, group in base_water.groupby("process", sort=True)], ignore_index=True),
    summarize(base_lithium, lithium_metrics),
], ignore_index=True)

base_branch_summary = base_dataset.groupby(["system", "process"], as_index=False).agg(
    rows=("poc_pass", "size"),
    accounting_pass_rows=("accounting_pass", "sum"),
    interface_capacity_pass_rows=("interface_capacity_pass", "sum"),
    target_met_rows=("target_met", "sum"),
    poc_pass_rows=("poc_pass", "sum"),
)
for name in ["accounting_pass", "interface_capacity_pass", "target_met", "poc_pass"]:
    base_branch_summary[f"{name}_percent"] = 100.0 * base_branch_summary[f"{name}_rows"] / base_branch_summary["rows"]
base_branch_summary["dataset_id"] = DATASET_ID
base_branch_summary["interpretation"] = "Computational target/resource feasibility under declared ranges; not physical process validation."
base_branch_summary["process_validity_status"] = "NOT_VALIDATED"

model_checks = {
    "status": "PASS",
    "dataset_id": DATASET_ID,
    "prior_poc_data_mixed": PRIOR_POC_DATA_MIXED,
    "hours_per_day": HOURS_PER_DAY,
    "electric_conversion_kwh_per_day_per_MWe": AVAILABLE_ELECTRIC_MWE * 1000.0 * HOURS_PER_DAY / AVAILABLE_ELECTRIC_MWE,
    "thermal_conversion_kwhth_per_day_per_MWth": AVAILABLE_PROCESS_HEAT_MWTH * 1000.0 * HOURS_PER_DAY / AVAILABLE_PROCESS_HEAT_MWTH,
    "water_max_abs_mass_balance_error_m3_day": float(np.max(np.abs(base_water["mass_balance_error_m3_day"]))),
    "water_max_abs_recovery_identity_error_m3_day": float(np.max(np.abs(base_water["recovery_identity_error_m3_day"]))),
    "lithium_max_abs_mass_balance_error_kg_day": float(np.max(np.abs(base_lithium["mass_balance_error_kg_day"]))),
    "lithium_max_abs_product_recalculation_error_kg_day": float(np.max(np.abs(base_lithium["product_recalculation_error_kg_day"]))),
    "water_required_fields_finite": bool(np.isfinite(base_water.select_dtypes(include=[np.number]).to_numpy()).all()),
    "lithium_required_fields_finite": bool(np.isfinite(base_lithium.select_dtypes(include=[np.number]).to_numpy()).all()),
    "output_folder_is_new": OUTPUT_ROOT.name not in {"tomahawk_secondary_systems_screen", "tomahawk_secondary_systems_invasive"},
}
assert model_checks["electric_conversion_kwh_per_day_per_MWe"] == 24000.0
assert model_checks["thermal_conversion_kwhth_per_day_per_MWth"] == 24000.0
assert model_checks["water_max_abs_mass_balance_error_m3_day"] <= 1e-9
assert model_checks["water_max_abs_recovery_identity_error_m3_day"] <= 1e-9
assert model_checks["lithium_max_abs_mass_balance_error_kg_day"] <= 1e-12
assert model_checks["lithium_max_abs_product_recalculation_error_kg_day"] <= 1e-12
assert model_checks["water_required_fields_finite"]
assert model_checks["lithium_required_fields_finite"]
assert model_checks["output_folder_is_new"]

# Determinism check: same seed and inputs must reproduce the same rows.
water_a = run_water_batch("seawater_ro", 128, np.random.default_rng(SEED + 77))
water_b = run_water_batch("seawater_ro", 128, np.random.default_rng(SEED + 77))
li_a = run_lithium_batch(128, np.random.default_rng(SEED + 78))
li_b = run_lithium_batch(128, np.random.default_rng(SEED + 78))
pd.testing.assert_frame_equal(water_a, water_b, check_exact=True)
pd.testing.assert_frame_equal(li_a, li_b, check_exact=True)
model_checks["deterministic_reproduction_check"] = True

# Negative controls: deliberately invalid rows must fail the domain gate.
invalid_water = evaluate_water_inputs("invalid_negative_recovery", [3.5], [0.0], [-0.1], [1000.0])
invalid_lithium = evaluate_lithium_inputs([100.0], [20.0], [1.2], [0.95], [1.0], [1.0], [1.0], [100.0])
assert not bool(invalid_water["domain_valid"].iloc[0])
assert not bool(invalid_lithium["domain_valid"].iloc[0])
assert not bool(invalid_water["poc_pass"].iloc[0])
assert not bool(invalid_lithium["poc_pass"].iloc[0])
model_checks["negative_control_rejection_check"] = True

base_dataset.to_csv(OUTPUT_ROOT / "secondary_systems_computational_poc_dataset.csv", index=False)
base_summary.to_csv(OUTPUT_ROOT / "secondary_systems_computational_poc_summary.csv", index=False)
base_branch_summary.to_csv(OUTPUT_ROOT / "secondary_systems_computational_poc_branch_summary.csv", index=False)
(OUTPUT_ROOT / "model_checks.json").write_text(json.dumps(model_checks, indent=2), encoding="utf-8")
(OUTPUT_ROOT / "poc_dataset_schema.json").write_text(json.dumps({
    "dataset_id": DATASET_ID,
    "source_type": DATASET_SOURCE,
    "row_count": int(len(base_dataset)),
    "rows_per_branch": BASE_ROWS_PER_BRANCH,
    "columns": list(base_dataset.columns),
    "interpretation": "Each row is one model-generated computational test case. It is not a measured process record.",
    "prior_poc_data_mixed": PRIOR_POC_DATA_MIXED,
}, indent=2), encoding="utf-8")
print("Model checks: PASS")
print(base_branch_summary.to_string(index=False))
print("Base computational POC rows:", len(base_dataset))
# Invasive deep run: convergence, repeatability, dispatch, sensitivity, stress, and bounded row sample.
DEEP_RUN = os.environ.get("TOMAHAWK_SECONDARY_DEEP_RUN", "1") == "1"
TARGET_MINUTES = float(os.environ.get("TOMAHAWK_SECONDARY_DEEP_RUN_MINUTES", "30"))
BATCH_SIZE = int(os.environ.get("TOMAHAWK_SECONDARY_BATCH_SIZE", "250000"))
MAX_BATCHES = int(os.environ.get("TOMAHAWK_SECONDARY_MAX_BATCHES", "0"))
if TARGET_MINUTES < 0.0 or BATCH_SIZE < 1000:
    raise ValueError("Deep-run minutes must be nonnegative and batch size must be at least 1000")

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
        if self.count == 0 or self.values.size == 0:
            raise RuntimeError("Reservoir has no finite values")
        return {"count": self.count, "P10": float(np.quantile(self.values, 0.10)), "P50": float(np.quantile(self.values, 0.50)), "P90": float(np.quantile(self.values, 0.90)), "mean": self.total / self.count, "min": self.minimum, "max": self.maximum}

class RowReservoir:
    def __init__(self, seed, max_rows=100000):
        self.rng = np.random.default_rng(seed)
        self.max_rows = max_rows
        self.frame = None
    def update(self, frame):
        if frame.empty:
            return
        take = min(500, len(frame))
        sampled = frame.iloc[self.rng.integers(0, len(frame), size=take)].copy()
        if self.frame is None:
            self.frame = sampled.head(self.max_rows).reset_index(drop=True)
            return
        combined = pd.concat([self.frame, sampled], ignore_index=True)
        if len(combined) > self.max_rows:
            keep = self.rng.choice(len(combined), size=self.max_rows, replace=False)
            self.frame = combined.iloc[keep].reset_index(drop=True)
        else:
            self.frame = combined
    def result(self):
        if self.frame is None:
            raise RuntimeError("Row reservoir has no rows")
        return self.frame.copy()

deep_metrics = {
    "water": ["target_product_water_m3_day", "max_supported_product_water_m3_day", "capacity_margin_water_m3_day", "electric_fraction_used", "thermal_fraction_used"],
    "lithium": ["target_product_kg_day", "product_kg_day", "target_margin_kg_day", "energy_kwh_per_kg_product", "electric_fraction_used", "product_purity_fraction"],
}
reservoirs = {(system, metric): Reservoir(SEED + 1000 + i * 100 + j) for i, (system, metrics) in enumerate(deep_metrics.items()) for j, metric in enumerate(metrics)}
row_reservoir = RowReservoir(SEED + 9000, max_rows=100000)
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
    batch_rng = np.random.default_rng(SEED + batch_number * 1009)
    for process_name in WATER_PROCESSES:
        frame = run_water_batch(process_name, BATCH_SIZE, batch_rng)
        frame.insert(0, "run_scope", "deep_computational_poc")
        frame.insert(1, "batch", batch_number)
        row_reservoir.update(frame)
        for metric in deep_metrics["water"]:
            reservoirs[("water", metric)].update(frame[metric].to_numpy())
            quantiles = frame[metric].replace([np.inf, -np.inf], np.nan).dropna().quantile([0.10, 0.50, 0.90])
            batch_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "water", "process": process_name, "metric": metric, "P10": float(quantiles.loc[0.10]), "P50": float(quantiles.loc[0.50]), "P90": float(quantiles.loc[0.90])})
        pass_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "water", "process": process_name, "rows": len(frame), "accounting_pass_percent": float(frame["accounting_pass"].mean() * 100.0), "interface_capacity_pass_percent": float(frame["interface_capacity_pass"].mean() * 100.0), "target_met_percent": float(frame["target_met"].mean() * 100.0), "poc_pass_percent": float(frame["poc_pass"].mean() * 100.0), "battery_grade_screen_percent": np.nan})
        del frame
    frame = run_lithium_batch(BATCH_SIZE, batch_rng)
    frame.insert(0, "run_scope", "deep_computational_poc")
    frame.insert(1, "batch", batch_number)
    row_reservoir.update(frame)
    for metric in deep_metrics["lithium"]:
        reservoirs[("lithium", metric)].update(frame[metric].to_numpy())
        quantiles = frame[metric].replace([np.inf, -np.inf], np.nan).dropna().quantile([0.10, 0.50, 0.90])
        batch_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "lithium", "process": "simplified_brine_mass_balance", "metric": metric, "P10": float(quantiles.loc[0.10]), "P50": float(quantiles.loc[0.50]), "P90": float(quantiles.loc[0.90])})
    pass_rows.append({"batch": batch_number, "elapsed_seconds": time.monotonic() - start_time, "system": "lithium", "process": "simplified_brine_mass_balance", "rows": len(frame), "accounting_pass_percent": float(frame["accounting_pass"].mean() * 100.0), "interface_capacity_pass_percent": float(frame["interface_capacity_pass"].mean() * 100.0), "target_met_percent": float(frame["target_met"].mean() * 100.0), "poc_pass_percent": float(frame["poc_pass"].mean() * 100.0), "battery_grade_screen_percent": float(frame["battery_grade_screen"].mean() * 100.0)})
    del frame
    if batch_number % 10 == 0:
        pd.DataFrame(batch_rows).to_csv(OUTPUT_ROOT / "deep_poc_batch_convergence_checkpoint.csv", index=False)
        pd.DataFrame(pass_rows).to_csv(OUTPUT_ROOT / "deep_poc_pass_rates_checkpoint.csv", index=False)
        row_reservoir.result().to_csv(OUTPUT_ROOT / "deep_poc_dataset_sample_checkpoint.csv", index=False)
    if time.monotonic() - last_report >= 60.0:
        print(f"heartbeat: batch={batch_number}, elapsed_minutes={(time.monotonic() - start_time) / 60.0:.2f}")
        last_report = time.monotonic()

deep_elapsed_seconds = time.monotonic() - start_time
deep_summary = pd.DataFrame([{"dataset_id": DATASET_ID, "system": system, "metric": metric, **accumulator.summarize()} for (system, metric), accumulator in reservoirs.items()])
batch_convergence = pd.DataFrame(batch_rows)
pass_history = pd.DataFrame(pass_rows)
deep_branch_summary = pass_history.groupby(["system", "process"], as_index=False).agg(
    batches=("batch", "count"), rows=("rows", "sum"),
    accounting_pass_percent_P10=("accounting_pass_percent", lambda s: float(s.quantile(0.10))),
    accounting_pass_percent_P50=("accounting_pass_percent", lambda s: float(s.quantile(0.50))),
    accounting_pass_percent_P90=("accounting_pass_percent", lambda s: float(s.quantile(0.90))),
    interface_capacity_pass_percent_P50=("interface_capacity_pass_percent", "median"),
    target_met_percent_P50=("target_met_percent", "median"),
    poc_pass_percent_P50=("poc_pass_percent", "median"),
    battery_grade_screen_percent_P50=("battery_grade_screen_percent", "median"),
)
deep_branch_summary["dataset_id"] = DATASET_ID
deep_branch_summary["process_validity_status"] = "NOT_VALIDATED"
deep_branch_summary["interpretation"] = "Computational target/resource feasibility under declared ranges; not physical process validation."

deep_summary.to_csv(OUTPUT_ROOT / "deep_poc_summary.csv", index=False)
batch_convergence.to_csv(OUTPUT_ROOT / "deep_poc_batch_convergence.csv", index=False)
pass_history.to_csv(OUTPUT_ROOT / "deep_poc_pass_rates_history.csv", index=False)
deep_branch_summary.to_csv(OUTPUT_ROOT / "deep_poc_branch_summary.csv", index=False)
row_reservoir.result().to_csv(OUTPUT_ROOT / "deep_poc_dataset_sample.csv", index=False)
# Co-production dispatch: vary electric allocation while preserving separate water/lithium accounting.
dispatch_rows = []
for lithium_share in (0.10, 0.25, 0.50, 0.75, 0.90):
    water_share = 1.0 - lithium_share
    water = run_water_batch("seawater_ro", 100000, np.random.default_rng(SEED + int(lithium_share * 10000) + 20000), available_electric_mwe=original_electric_mwe * water_share)
    lithium = run_lithium_batch(100000, np.random.default_rng(SEED + int(lithium_share * 10000) + 21000), available_electric_mwe=original_electric_mwe * lithium_share)
    dispatch_rows.append({
        "dataset_id": DATASET_ID,
        "lithium_electric_share": lithium_share,
        "water_electric_share": water_share,
        "water_product_m3_day_P50": float(water["product_water_m3_day"].median()),
        "water_poc_pass_percent": float(water["poc_pass"].mean() * 100.0),
        "lithium_product_kg_day_P50": float(lithium["product_kg_day"].median()),
        "lithium_capacity_pass_percent": float(lithium["interface_capacity_pass"].mean() * 100.0),
        "lithium_target_met_percent": float(lithium["target_met"].mean() * 100.0),
        "lithium_poc_pass_percent": float(lithium["poc_pass"].mean() * 100.0),
    })
dispatch = pd.DataFrame(dispatch_rows)
dispatch.to_csv(OUTPUT_ROOT / "co_production_dispatch.csv", index=False)

def spearman(a, b):
    return float(pd.Series(a).rank(method="average").corr(pd.Series(b).rank(method="average")))

sensitivity_rows = []
li_sens = run_lithium_batch(200000, np.random.default_rng(SEED + 30000))
for input_col in ["brine_flow_m3_day", "lithium_mg_per_L", "recovery_fraction", "product_purity_fraction", "energy_kwh_per_m3", "target_product_kg_day"]:
    for target_col in ["product_kg_day", "energy_kwh_per_kg_product", "poc_pass"]:
        rho = spearman(li_sens[input_col], li_sens[target_col])
        sensitivity_rows.append({"dataset_id": DATASET_ID, "system": "lithium", "input": input_col, "target": target_col, "spearman_r": rho, "abs_spearman_r": abs(rho)})
water_sens = run_water_batch("seawater_ro", 200000, np.random.default_rng(SEED + 31000))
for input_col in ["electric_kwh_per_m3", "recovery_fraction", "target_product_water_m3_day"]:
    for target_col in ["max_supported_product_water_m3_day", "capacity_margin_water_m3_day", "poc_pass"]:
        rho = spearman(water_sens[input_col], water_sens[target_col])
        sensitivity_rows.append({"dataset_id": DATASET_ID, "system": "water", "input": input_col, "target": target_col, "spearman_r": rho, "abs_spearman_r": abs(rho)})
sensitivity = pd.DataFrame(sensitivity_rows).sort_values(["system", "target", "abs_spearman_r"], ascending=[True, True, False])
sensitivity.to_csv(OUTPUT_ROOT / "sensitivity_rank.csv", index=False)

# Fixed stress cases include both feasible and intentionally infeasible conditions.
stress_rows = []
stress_rows.append(evaluate_water_inputs("seawater_ro", [4.7], [0.0], [0.35], [1000.0]).assign(case="water_conservative_feasible_edge"))
stress_rows.append(evaluate_water_inputs("thermal_desalination", [3.0], [80.0], [0.25], [1500.0]).assign(case="water_thermal_high_load"))
stress_rows.append(evaluate_water_inputs("industrial_water_recovery", [4.0], [20.0], [0.50], [6000.0]).assign(case="water_recovery_high_load"))
stress_rows.append(evaluate_lithium_inputs([100.0], [20.0], [0.40], [0.90], [10.0], [2.0], [5.0], [100.0]).assign(case="lithium_conservative_low_feed"))
stress_rows.append(evaluate_lithium_inputs([10000.0], [300.0], [0.40], [0.90], [10.0], [2.0], [5.0], [5000.0]).assign(case="lithium_high_load_capacity_stress"))
stress = pd.concat(stress_rows, ignore_index=True, sort=False)
stress.to_csv(OUTPUT_ROOT / "stress_cases.csv", index=False)

deep_manifest = {
    "model": "Tomahawk secondary-systems computational POC invasive run",
    "dataset_id": DATASET_ID,
    "dataset_source": DATASET_SOURCE,
    "prior_poc_data_mixed": PRIOR_POC_DATA_MIXED,
    "seed": SEED,
    "deep_run_enabled": DEEP_RUN,
    "target_runtime_minutes": TARGET_MINUTES,
    "actual_runtime_minutes": deep_elapsed_seconds / 60.0,
    "batch_size": BATCH_SIZE,
    "batches_completed": batch_number,
    "deep_rows_evaluated_per_branch": batch_number * BATCH_SIZE,
    "hours_per_day": HOURS_PER_DAY,
    "normalized_process_interface": {"available_process_heat_MWth": AVAILABLE_PROCESS_HEAT_MWTH, "available_electric_MWe": AVAILABLE_ELECTRIC_MWE},
    "scope": "Computational target/resource feasibility, conservation checks, convergence, dispatch, sensitivity, and stress cases",
    "not_established": ["Tomahawk reactor output or net energy", "potable-water quality", "lithium extraction chemistry/selectivity/impurity rejection", "battery-grade certification", "equipment lifetime/corrosion/fouling", "commercial economics or offtake", "experimental validation"],
    "reference_ranges": {"water": WATER_PROCESSES, "lithium": LITHIUM_INPUT_RANGES},
    "outputs": ["secondary_systems_computational_poc_dataset.csv", "secondary_systems_computational_poc_summary.csv", "secondary_systems_computational_poc_branch_summary.csv", "deep_poc_dataset_sample.csv", "deep_poc_summary.csv", "deep_poc_branch_summary.csv", "deep_poc_batch_convergence.csv", "deep_poc_pass_rates_history.csv", "co_production_dispatch.csv", "stress_cases.csv", "sensitivity_rank.csv", "model_checks.json", "poc_dataset_schema.json"],
    "input_data_used": [],
}
(OUTPUT_ROOT / "secondary_systems_computational_poc_manifest.json").write_text(json.dumps(deep_manifest, indent=2), encoding="utf-8")

fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
water_conv = batch_convergence[(batch_convergence["system"] == "water") & (batch_convergence["metric"] == "capacity_margin_water_m3_day")]
for process, group in water_conv.groupby("process"):
    axes[0].plot(group["batch"], group["P50"], label=process)
axes[0].set_title("Water capacity-margin convergence")
axes[0].set_xlabel("batch")
axes[0].set_ylabel("m³/day margin")
axes[0].grid(alpha=0.25)
axes[0].legend(fontsize=8)
axes[1].plot(dispatch["lithium_electric_share"], dispatch["water_product_m3_day_P50"], marker="o", label="water P50")
axes[1].set_title("Co-production electricity tradeoff")
axes[1].set_xlabel("electricity share allocated to lithium")
axes[1].set_ylabel("water P50 m³/day")
axes[1].grid(alpha=0.25)
fig.suptitle("Tomahawk secondary-systems computational POC — conditional model evidence")
fig.tight_layout()
fig.savefig(OUTPUT_ROOT / "secondary_systems_computational_poc_summary.png", dpi=180)
plt.close(fig)
print("Computational POC invasive run complete.")
print("Elapsed minutes:", round(deep_elapsed_seconds / 60.0, 3), "Batches:", batch_number)
print(deep_branch_summary.to_string(index=False))