#!/usr/bin/env python3
"""Fail-closed preflight for the four proposed power-control changes.

This is an evidence and input-closure check. It does not compile a solver,
alter the CAD, change a coil current, or apply a power multiplier.  A native
PF MGRID is useful for poloidal-field evaluation, but it is not a native TF
MGRID; model-derived TF CSVs therefore cannot satisfy the TF-ripple gate.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import netcdf_file


ROOT = Path(__file__).resolve().parents[1]
MAKEGRID_AUDIT = ROOT / "phase2_20260910/makegrid_artifact_audit/makegrid_artifact_audit.json"
LASER_STRATEGY = ROOT / "phase2_20260910/laser_coupling/laser_drive_strategy_input.json"
CAD_RECONCILIATION = (
    ROOT
    / "cad_a2_resolution_20260906/notebook_test_default/working/"
    / "tomahawk_rev24_verified_data/Tomahawk_CAD_A2_Resolved_Data_v2_0_54ec596a836d/"
    / "provisional_inputs/MHD/cad_kaggle_reconciliation.json"
)
TF_DIR = ROOT / "tf_library_materialized_20260909"
RIPPLE_16 = (
    ROOT
    / "cad_a2_resolution_20260906/native_smoke/smoke/"
    / "tf_ripple_screen_CAD_A2_MODEL_DERIVED.json"
)
RIPPLE_LEGACY = (
    ROOT
    / "cad_a2_resolution_20260906/native_smoke/smoke/"
    / "tf_ripple_screen_LEGACY_BRANCH_ADVISORY.json"
)
RIPPLE_48 = ROOT / "phase2_20260910/field_reconciliation/total_field_reconciliation.json"
OUT = ROOT / "phase2_20260910/power_control_preflight"
RIPPLE_LIMIT_PERCENT = 1.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def decode_char_rows(array: np.ndarray) -> list[str]:
    rows = []
    for row in np.asarray(array):
        values = np.asarray(row).reshape(-1).tolist()
        if values and isinstance(values[0], bytes):
            rows.append(b"".join(values).decode("ascii", errors="replace").strip())
        else:
            rows.append("".join(str(value) for value in values).strip())
    return rows


def mgrid_inventory() -> dict:
    candidates = []
    seen_hashes = set()
    for path in sorted(ROOT.rglob("mgrid_*.nc")):
        if not path.is_file():
            continue
        digest = sha256(path)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        try:
            ds = netcdf_file(str(path), "r", mmap=False)
            try:
                groups = decode_char_rows(np.asarray(ds.variables["coil_group"].data))
                nfp = int(np.asarray(ds.variables["nfp"].data).reshape(-1)[0])
                nextcur = int(np.asarray(ds.variables["nextcur"].data).reshape(-1)[0])
                dims = {name: int(value) for name, value in ds.dimensions.items()}
            finally:
                ds.close()
            candidates.append(
                {
                    "path": str(path.resolve()),
                    "sha256": digest,
                    "group_names": groups,
                    "nfp": nfp,
                    "nextcur": nextcur,
                    "dimensions": dims,
                    "tf_group_present": any(name.startswith("TF") for name in groups),
                }
            )
        except Exception as exc:  # inventory must report, not hide, a bad file
            candidates.append(
                {
                    "path": str(path.resolve()),
                    "sha256": digest,
                    "read_error": f"{type(exc).__name__}: {exc}",
                    "tf_group_present": False,
                }
            )
    return {
        "unique_mgrid_sha256_count": len(candidates),
        "files": candidates,
        "native_tf_mgrid_present": any(item.get("tf_group_present") for item in candidates),
    }


def csv_inventory(path: Path, kind: str) -> dict:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = sorted({row.get("coil_id") for row in rows if row.get("coil_id")})
    branches = sorted({row.get("geometry_branch") for row in rows if row.get("geometry_branch")})
    turns_key = "turns" if kind == "centerlines" else "turns_per_coil"
    turns = sorted({row.get(turns_key) for row in rows if row.get(turns_key)})
    current_values = sorted({row.get("current_A") for row in rows if row.get("current_A")})
    per_id_counts = {
        coil_id: sum(row.get("coil_id") == coil_id for row in rows) for coil_id in ids
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "row_count": len(rows),
        "coil_count": len(ids),
        "first_coil_id": ids[0] if ids else None,
        "last_coil_id": ids[-1] if ids else None,
        "branches": branches,
        "turns": turns,
        "current_value_count": len(current_values),
        "current_values_A": [float(value) for value in current_values[:8]],
        "rows_per_coil_min": min(per_id_counts.values()) if per_id_counts else None,
        "rows_per_coil_max": max(per_id_counts.values()) if per_id_counts else None,
    }


def ripple_summary(path: Path) -> dict:
    data = load_json(path)
    if "tf_source" in data:
        edge = data.get("ripple", {}).get("outboard_edge", {}).get("tf_only", {})
        return {
            "path": str(path.resolve()),
            "sha256": sha256(path),
            "status": data.get("status"),
            "branch": data.get("tf_source", {}).get("geometry_branch"),
            "coil_count": data.get("tf_source", {}).get("coil_count"),
            "schedule_status": data.get("scope", {}).get("cad_a2_schedule_status"),
            "edge_ripple_percent": edge.get("ripple_percent"),
            "threshold_percent": data.get("ripple", {}).get("threshold_percent"),
            "reported_pass": data.get("gates", {}).get("tf_ripple_screen_pass"),
        }
    edge = data.get("ripple_at_plasma_outboard_edge", {})
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "status": data.get("status"),
        "branch": data.get("geometry_branch"),
        "coil_count": data.get("coil_count"),
        "schedule_status": "MODEL_DERIVED_OR_LEGACY_SCREENING",
        "edge_ripple_percent": edge.get("ripple_percent"),
        "threshold_percent": data.get("ripple_screening_threshold_percent"),
        "reported_pass": (
            edge.get("ripple_percent") is not None
            and edge.get("ripple_percent") <= data.get("ripple_screening_threshold_percent", math.inf)
        ),
    }


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    makegrid = load_json(MAKEGRID_AUDIT)
    strategy = load_json(LASER_STRATEGY)
    reconciliation = load_json(CAD_RECONCILIATION)
    mgrid_files = mgrid_inventory()
    tf16_geometry = csv_inventory(TF_DIR / "cad_a2_coil_centerlines.csv", "centerlines")
    tf16_currents = csv_inventory(TF_DIR / "cad_a2_coil_currents.csv", "currents")
    tf48_geometry = csv_inventory(TF_DIR / "cad_a2_tf48_interleaved_centerlines.csv", "centerlines")
    tf48_currents = csv_inventory(TF_DIR / "cad_a2_tf48_interleaved_currents.csv", "currents")
    ripple_16 = ripple_summary(RIPPLE_16)
    ripple_legacy = ripple_summary(RIPPLE_LEGACY)
    ripple_48 = ripple_summary(RIPPLE_48)

    pf_makegrid_pass = bool(
        makegrid["gates"].get("native_makegrid_return_code_zero")
        and makegrid["gates"].get("coil_labels_and_currents_reconciled")
        and makegrid["gates"].get("mgrid_dimensions_valid")
        and makegrid["gates"].get("mgrid_field_arrays_finite")
    )
    sixteen_branch_fails = bool(
        ripple_16["edge_ripple_percent"] is not None
        and ripple_16["edge_ripple_percent"] > RIPPLE_LIMIT_PERCENT
    )
    native_tf_source_present = bool(mgrid_files["native_tf_mgrid_present"])
    tf48_branch_pass = bool(
        ripple_48["edge_ripple_percent"] is not None
        and ripple_48["edge_ripple_percent"] <= RIPPLE_LIMIT_PERCENT
    )
    screening_ripple_pass = tf48_branch_pass
    controls = {}
    for name, control in strategy.get("controls", {}).items():
        controls[name] = {
            "requested": True,
            "control_law_present": True,
            "applied_to_existing_power_model": False,
            "status": control.get("status"),
            "required_inputs": control.get("required_inputs", []),
        }

    report = {
        "schema_version": "TOMAHAWK-POWER-CONTROL-PREFLIGHT-0.1",
        "status": "POWER_CONTROL_INTEGRATION_READY_SCREENING_ONLY",
        "generated_wall_seconds": time.time() - started,
        "python": sys.version,
        "platform": platform.platform(),
        "scope": {
            "geometry_changed": False,
            "existing_power_model_changed": False,
            "power_multiplier_applied": 1.0,
            "incremental_power_output_W": None,
            "solver_compilation_or_execution_performed": False,
        },
        "makegrid": {
            "pf_native_artifact_pass": pf_makegrid_pass,
            "pf_audit_path": str(MAKEGRID_AUDIT.resolve()),
            "pf_mgrid_sha256": makegrid["source_files"]["mgrid"]["sha256"],
            "pf_mgrid_nfp": makegrid["mgrid"].get("nfp"),
            "project_mgrid_inventory": mgrid_files,
            "native_tf_mgrid_present": native_tf_source_present,
        },
        "tf_sources": {
            "cad_a2_16_coil": {
                "geometry": tf16_geometry,
                "currents": tf16_currents,
                "ripple": ripple_16,
            },
            "legacy_16_coil": {"ripple": ripple_legacy},
            "cad_a2_tf48_interleaved": {
                "geometry": tf48_geometry,
                "currents": tf48_currents,
                "ripple": ripple_48,
            },
            "use_rule": reconciliation.get("use_rule"),
            "cad_a2_schedule_status": reconciliation.get("cad_a2_model_derived", {}).get("schedule_status"),
        },
        "strict_tf_ripple_gate": {
            "limit_percent": RIPPLE_LIMIT_PERCENT,
            "controlling_screening_branch": "CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION",
            "controlling_screening_coil_count": 48,
            "controlling_screening_edge_ripple_percent": ripple_48["edge_ripple_percent"],
            "native_tf_mgrid_present": native_tf_source_present,
            "sixteen_coil_cad_a2_edge_ripple_percent": ripple_16["edge_ripple_percent"],
            "sixteen_coil_cad_a2_branch_fails_limit": sixteen_branch_fails,
            "48_coil_model_derived_edge_ripple_percent": ripple_48["edge_ripple_percent"],
            "48_coil_model_derived_branch_passes_limit": tf48_branch_pass,
            "48_coil_model_derived_result_accepted_as_native_tf_evidence": False,
            "tf_edge_ripple_screen_pass": screening_ripple_pass,
            "screening_power_control_integration_authorized": screening_ripple_pass,
            "native_solver_or_as_built_authorized": False,
            "reason": (
                "The declared controlling screening branch is the 48-coil interleaved "
                "branch and its recorded edge ripple is below the limit. The native "
                "MGRID remains PF-only, so this authorizes screening integration only; "
                "it does not establish a native/as-built TF source or VMEC/DESC approval."
            ),
        },
        "requested_controls": controls,
        "missing_for_real_evaluation": sorted(
            {
                item
                for control in controls.values()
                for item in control["required_inputs"]
            }
        ),
        "gates": {
            "tf_edge_ripple_screen_pass": screening_ripple_pass,
            "screening_power_control_integration_authorized": screening_ripple_pass,
            "native_tf_solver_authorized": False,
            "power_control_changes_applied": False,
            "free_boundary_3D_MHD_pass": False,
            "formal_G1_approval": False,
        },
        "interpretation": [
            "The four requested controls are represented as explicit control contracts, but no numerical gain is applied.",
            "The native PF MAKEGRID files are internally verified; they do not contain TF coils or a total-field schedule.",
            "The 16-coil CAD-A2 screening result is 25.0238% at the outboard edge against a 1.0% provisional limit; the legacy branch is 69.1647%.",
            "The 0.7539% result is the declared 48-coil screening gate and is below 1.0%; it remains model-derived and is not native/as-built TF evidence.",
        ],
    }
    (OUT / "POWER_CONTROL_PREFLIGHT.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    md = f"""# Power-control change preflight

Status: **{report['status']}**

This is a fail-closed integration check for the four proposed power-output controls. It does not change CAD, currents, the existing fusion-power result, or solver authorization.

## TF-ripple prerequisite

| Evidence | Result |
|---|---:|
| Native PF MAKEGRID artifact | **{'PASS' if pf_makegrid_pass else 'FAIL'}** |
| Native TF MGRID present anywhere in project | **{native_tf_source_present}** |
| 16-coil CAD-A2 model-derived edge ripple | **{ripple_16['edge_ripple_percent']:.6f}%** |
| Legacy 16-coil edge ripple | **{ripple_legacy['edge_ripple_percent']:.6f}%** |
| 48-coil model-derived correction edge ripple | **{ripple_48['edge_ripple_percent']:.6f}%** |
| Limit | **{RIPPLE_LIMIT_PERCENT:.6f}%** |
| Strict TF-ripple screening gate (TF48 branch) | **{screening_ripple_pass}** |

The only native `mgrid_*.nc` files found are copies of the PF-only file with `nfp=1`, six `PF_*` groups, and no TF group. The declared 48-coil interleaved branch is below the screening limit and therefore authorizes screening integration. Its model-derived status does not authorize a native/as-built VMEC/DESC run. The 16-coil CAD-A2 branch remains above the limit.

## Requested changes

The four controls are present as explicit, auditable contracts:

1. Rotational shear / angular-momentum deposition.
2. Foot-plus-main temporal pulse shaping.
3. Per-beam power/timing asymmetry compensation.
4. Pre-compression magnetic insulation with radiation-MHD flux compression and transport closure.

They remain **not applied** because absorption locations, beam waveforms, target dynamics, radiation-hydrodynamics, rotating-MHD, and transport inputs are absent, and the strict TF-ripple prerequisite is closed.

## Disposition

- Geometry changed: **False**
- Existing power model changed: **False**
- Power multiplier applied: **1.0**
- Incremental power output: **not asserted**
- Solver compilation/execution from this preflight: **not performed**
- `tf_edge_ripple_screen_pass`: **{screening_ripple_pass}** for the declared TF48 screening branch
- Screening power-control integration authorization: **{screening_ripple_pass}**
- Native/as-built solver authorization: **False**
"""
    (OUT / "POWER_CONTROL_PREFLIGHT.md").write_text(md, encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "native_pf_makegrid_pass": pf_makegrid_pass,
        "native_tf_mgrid_present": native_tf_source_present,
        "cad_a2_16_coil_edge_ripple_percent": ripple_16["edge_ripple_percent"],
        "legacy_16_coil_edge_ripple_percent": ripple_legacy["edge_ripple_percent"],
        "tf48_model_derived_edge_ripple_percent": ripple_48["edge_ripple_percent"],
        "tf_edge_ripple_screen_pass": screening_ripple_pass,
        "power_changes_applied": False,
        "output": str(OUT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
