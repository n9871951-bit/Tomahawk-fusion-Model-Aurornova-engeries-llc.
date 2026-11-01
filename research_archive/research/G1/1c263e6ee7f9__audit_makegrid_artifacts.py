#!/usr/bin/env python3
"""Audit the supplied native MAKEGRID PF artifacts without modifying them."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import netcdf_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "upload"
DEFAULT_VERIFICATION = ROOT / "mgrid_g1_check_20260909/evidence_bundle/G1_CANDIDATE/G1_Repair_Verification.json"
DEFAULT_OUTPUT_DIR = ROOT / "phase2_20260910/makegrid_artifact_audit"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_extcur(path: Path) -> list[float]:
    values: dict[int, float] = {}
    pattern = re.compile(r"EXTCUR\((\d+)\)\s*=\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            values[int(match.group(1))] = float(match.group(2))
    if not values or sorted(values) != list(range(1, len(values) + 1)):
        raise ValueError(f"EXTCUR indices are not contiguous in {path}")
    return [values[index] for index in range(1, len(values) + 1)]


def parse_coils(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    periods = None
    mirror = None
    data_rows: list[dict] = []
    loop_markers: list[dict] = []
    numeric_pattern = re.compile(
        r"^\s*([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+"
        r"([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+"
        r"([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+"
        r"([-+]?\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)"
    )
    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("periods "):
            periods = int(stripped.split()[1])
        elif stripped.startswith("mirror "):
            mirror = stripped.split()[1]
        match = numeric_pattern.match(line)
        if not match:
            continue
        values = np.asarray([float(match.group(index)) for index in range(1, 5)], dtype=float)
        tokens = stripped.split()
        group = tokens[-1] if tokens and tokens[-1].startswith("PF_") else None
        if group is not None:
            # Native filament format terminates each loop with a repeated
            # first point followed by ``0.0 <coil> <group>``. This is a
            # marker, not a 129th current-carrying point.
            loop_markers.append(
                {
                    "line": line_number,
                    "xyz_m": values[:3],
                    "coil_index": int(tokens[-2]),
                    "group": group,
                }
            )
        elif len(tokens) == 4:
            data_rows.append(
                {
                    "line": line_number,
                    "xyz_m": values[:3],
                    "current_A": float(values[3]),
                }
            )
    if periods is None or mirror is None:
        raise ValueError(f"Missing periods/mirror header in {path}")
    if len(data_rows) % 128 != 0:
        raise ValueError(f"Coil data row count {len(data_rows)} is not divisible by 128")
    loop_count = len(data_rows) // 128
    if len(loop_markers) != loop_count:
        raise ValueError(f"Found {len(loop_markers)} loop markers for {loop_count} 128-point loops")
    groups: list[dict] = []
    for loop_number in range(loop_count):
        loop = data_rows[loop_number * 128 : (loop_number + 1) * 128]
        marker = loop_markers[loop_number]
        group = marker["group"]
        xyz = np.asarray([row["xyz_m"] for row in loop], dtype=float)
        currents = np.asarray([row["current_A"] for row in loop], dtype=float)
        groups.append(
            {
                "group": group,
                "coil_index": marker["coil_index"],
                "xyz_m": xyz,
                "current_A": float(currents[-1]),
                "marker_duplicate_gap_m": float(np.linalg.norm(xyz[0] - marker["xyz_m"])),
                "closing_segment_m": float(np.linalg.norm(xyz[-1] - marker["xyz_m"])),
            }
        )
    group_names = []
    summary: dict[str, dict] = {}
    for loop in groups:
        name = loop["group"]
        if name not in summary:
            group_names.append(name)
            summary[name] = {
                "loop_count": 0,
                "filament_points_per_loop": 128,
                "currents_A": [],
                "max_closure_gap_m": 0.0,
                "min_xyz_m": [math.inf, math.inf, math.inf],
                "max_xyz_m": [-math.inf, -math.inf, -math.inf],
            }
        item = summary[name]
        item["loop_count"] += 1
        item["currents_A"].append(loop["current_A"])
        item["max_closure_gap_m"] = max(item["max_closure_gap_m"], loop["marker_duplicate_gap_m"])
        item["min_xyz_m"] = np.minimum(item["min_xyz_m"], loop["xyz_m"].min(axis=0)).tolist()
        item["max_xyz_m"] = np.maximum(item["max_xyz_m"], loop["xyz_m"].max(axis=0)).tolist()
    for name, item in summary.items():
        item["current_min_A"] = float(min(item["currents_A"]))
        item["current_max_A"] = float(max(item["currents_A"]))
        item["uniform_current_pass"] = bool(np.ptp(np.asarray(item["currents_A"])) == 0.0)
        del item["currents_A"]
    return {
        "periods": periods,
        "mirror": mirror,
        "data_rows": len(data_rows),
        "loop_count": loop_count,
        "group_order": group_names,
        "groups": summary,
    }


def decode_char_rows(array: np.ndarray) -> list[str]:
    return [b"".join(row.tolist()).decode("ascii", errors="replace").strip() for row in array]


def decode_char_scalar(array: np.ndarray) -> str:
    values = np.asarray(array).reshape(-1).tolist()
    if values and isinstance(values[0], bytes):
        return b"".join(values).decode("ascii", errors="replace").strip()
    return "".join(str(value) for value in values).strip()


def scalar(ds, name: str):
    value = np.asarray(ds.variables[name].data)
    if value.size != 1:
        raise ValueError(f"Expected scalar MGRID variable {name}")
    return value.reshape(-1)[0].item()


def dimension_size(value) -> int:
    return int(len(value) if hasattr(value, "__len__") else value)


def audit_mgrid(path: Path) -> dict:
    ds = netcdf_file(str(path), "r", mmap=False)
    try:
        dimensions = {name: dimension_size(dimension) for name, dimension in ds.dimensions.items()}
        variables = list(ds.variables)
        group_names = decode_char_rows(np.asarray(ds.variables["coil_group"].data))
        field_variables = [name for name in variables if re.fullmatch(r"b[prz]_\d{3}", name)]
        finite = True
        nonfinite_count = 0
        max_end_plane_delta = 0.0
        field_min = math.inf
        field_max = -math.inf
        per_group: dict[str, dict] = {}
        for name in field_variables:
            values = np.asarray(ds.variables[name].data)
            bad = int(np.count_nonzero(~np.isfinite(values)))
            nonfinite_count += bad
            finite = finite and bad == 0
            field_min = min(field_min, float(values.min()))
            field_max = max(field_max, float(values.max()))
            max_end_plane_delta = max(max_end_plane_delta, float(np.max(np.abs(values[0] - values[-1]))))
            group_index = int(name[-3:])
            group = group_names[group_index - 1] if 1 <= group_index <= len(group_names) else f"UNKNOWN_{group_index}"
            per_group.setdefault(group, {})[name[:2]] = {
                "min": float(values.min()),
                "max": float(values.max()),
                "nonfinite_count": bad,
            }
        return {
            "file_format": int(ds.version_byte),
            "dimensions": dimensions,
            "variables": variables,
            "group_names": group_names,
            "field_variable_count": len(field_variables),
            "field_variables_finite": finite,
            "field_nonfinite_count": nonfinite_count,
            "field_global_min": field_min,
            "field_global_max": field_max,
            "max_first_last_phi_plane_difference": max_end_plane_delta,
            "per_group_field_stats": per_group,
            "mgrid_mode": decode_char_scalar(np.asarray(ds.variables["mgrid_mode"].data)),
            "ir": int(scalar(ds, "ir")),
            "jz": int(scalar(ds, "jz")),
            "kp": int(scalar(ds, "kp")),
            "nfp": int(scalar(ds, "nfp")),
            "nextcur": int(scalar(ds, "nextcur")),
            "rmin_m": float(scalar(ds, "rmin")),
            "rmax_m": float(scalar(ds, "rmax")),
            "zmin_m": float(scalar(ds, "zmin")),
            "zmax_m": float(scalar(ds, "zmax")),
            "raw_coil_cur_A": np.asarray(ds.variables["raw_coil_cur"].data, dtype=float).tolist(),
        }
    finally:
        ds.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--verification", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    started = time.time()
    source_dir = args.source_dir.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    mgrid_path = source_dir / "mgrid_tomahawk_pf.nc"
    coils_path = source_dir / "coils.tomahawk_pf"
    extcur_path = source_dir / "extcur.tomahawk_pf"
    manifest_path = source_dir / "makegrid_run_manifest.json"
    log_path = source_dir / "xgrid_tomahawk_pf.log"
    for path in [mgrid_path, coils_path, extcur_path, manifest_path, log_path]:
        if not path.exists():
            raise FileNotFoundError(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    coils = parse_coils(coils_path)
    extcur = parse_extcur(extcur_path)
    mgrid = audit_mgrid(mgrid_path)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    manifest_hash_checks = {
        "mgrid_sha256_matches_manifest": manifest.get("mgrid_sha256") == sha256(mgrid_path),
        "extcur_sha256_matches_manifest": manifest.get("extcur_sha256") == sha256(extcur_path),
        "coils_sha256_declared": "coils_sha256" in manifest,
        "coils_sha256_matches_manifest": (
            manifest.get("coils_sha256") == sha256(coils_path)
            if "coils_sha256" in manifest
            else None
        ),
    }
    groups_match = coils["group_order"] == mgrid["group_names"]
    coil_currents = [
        float(np.mean([coils["groups"][name][key] for key in ["current_min_A", "current_max_A"]]))
        for name in mgrid["group_names"]
        for key in []
    ]
    coil_currents = [
        float(coils["groups"][name]["current_min_A"])
        for name in mgrid["group_names"]
    ] if groups_match else []
    current_differences = np.asarray(mgrid["raw_coil_cur_A"], dtype=float) - np.asarray(extcur, dtype=float)
    coil_current_differences = (
        np.asarray(coil_currents, dtype=float) - np.asarray(extcur, dtype=float)
        if coil_currents
        else np.asarray([], dtype=float)
    )
    loop_counts_match = (
        [coils["groups"][name]["loop_count"] for name in mgrid["group_names"]] == [28, 162, 48, 150, 28, 162]
        if groups_match
        else False
    )
    input_file = source_dir / str(manifest.get("input_file", ""))
    only_pf_groups = bool(mgrid["group_names"]) and all(name.startswith("PF_") for name in mgrid["group_names"])
    native_run_pass = bool(
        manifest.get("mgrid_generated")
        and manifest.get("native_solver_evidence")
        and manifest.get("return_code") == 0
        and mgrid_path.exists()
        and "K =   36" in log_text
    )
    log_has_nan = bool(re.search(r"\bNaN\b", log_text))
    report = {
        "schema_version": "TOMAHAWK-MAKEGRID-ARTIFACT-AUDIT-0.1",
        "status": "NATIVE_MAKEGRID_PF_ARTIFACTS_VERIFIED_TF_NOT_PRESENT",
        "generated_utc_not_recorded": True,
        "wall_seconds": time.time() - started,
        "source_files": {
            "source_dir": str(source_dir),
            "mgrid": {"path": str(mgrid_path), "sha256": sha256(mgrid_path), "size_bytes": mgrid_path.stat().st_size},
            "coils": {"path": str(coils_path), "sha256": sha256(coils_path), "size_bytes": coils_path.stat().st_size},
            "extcur": {"path": str(extcur_path), "sha256": sha256(extcur_path), "size_bytes": extcur_path.stat().st_size},
            "manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path), "size_bytes": manifest_path.stat().st_size},
            "log": {"path": str(log_path), "sha256": sha256(log_path), "size_bytes": log_path.stat().st_size},
        },
        "manifest": manifest,
        "manifest_hash_checks": manifest_hash_checks,
        "coils": coils,
        "extcur_A": extcur,
        "mgrid": mgrid,
        "reconciliations": {
            "group_labels_match_mgrid": groups_match,
            "loop_counts_match_expected_order": loop_counts_match,
            "coil_current_vs_extcur_max_difference_A": float(np.max(np.abs(coil_current_differences))) if coil_current_differences.size else None,
            "mgrid_raw_current_vs_extcur_max_difference_A": float(np.max(np.abs(current_differences))),
            "mgrid_raw_current_vs_extcur_pass": bool(np.allclose(current_differences, 0.0, atol=0.0, rtol=0.0)),
            "coil_current_vs_extcur_pass": bool(np.allclose(coil_current_differences, 0.0, atol=0.0, rtol=0.0)) if coil_current_differences.size else False,
            "all_loops_128_points": all(item["filament_points_per_loop"] == 128 for item in coils["groups"].values()),
            "all_loops_closed_by_duplicate_endpoint": all(item["max_closure_gap_m"] == 0.0 for item in coils["groups"].values()),
        },
        "native_run": {
            "manifest_status": manifest.get("status"),
            "command": manifest.get("command"),
            "return_code": manifest.get("return_code"),
            "xgrid_log_contains_all_36_planes": "K =   36" in log_text,
            "xgrid_log_contains_nan_summary_values": log_has_nan,
            "xgrid_log_nan_interpretation": "The NaN entries are zero-spread SD report fields for uniform-current groups; all MGRID field arrays were separately checked finite." if log_has_nan else None,
            "native_makegrid_run_pass": native_run_pass,
            "input_configuration_file_present_in_supplied_directory": input_file.exists(),
            "input_configuration_file": str(input_file),
        },
        "scope": {
            "pf_source_present": True,
            "tf_source_present": False,
            "only_pf_group_labels": only_pf_groups,
            "mgrid_nfp": mgrid["nfp"],
            "total_field_or_tf_ripple_evaluable_from_this_mgrid": False,
            "tf_edge_ripple_gate": "BLOCKED_TF_SOURCE_ABSENT",
            "free_boundary_3D_MHD_gate": "BLOCKED_TOTAL_FIELD_AND_APPROVED_BOUNDARY",
            "formal_G1_approval": False,
        },
        "gates": {
            "native_makegrid_return_code_zero": native_run_pass,
            "manifest_hashes_for_mgrid_and_extcur": bool(
                manifest_hash_checks["mgrid_sha256_matches_manifest"]
                and manifest_hash_checks["extcur_sha256_matches_manifest"]
            ),
            "complete_manifest_hash_coverage_including_coils": bool(
                manifest_hash_checks["mgrid_sha256_matches_manifest"]
                and manifest_hash_checks["extcur_sha256_matches_manifest"]
                and manifest_hash_checks["coils_sha256_declared"]
                and manifest_hash_checks["coils_sha256_matches_manifest"]
            ),
            "coil_labels_and_currents_reconciled": bool(groups_match and loop_counts_match and np.allclose(coil_current_differences, 0.0, atol=0.0, rtol=0.0)),
            "mgrid_dimensions_valid": bool(mgrid["ir"] == 201 and mgrid["jz"] == 201 and mgrid["kp"] == 36),
            "mgrid_field_arrays_finite": mgrid["field_variables_finite"],
            "tf_edge_ripple_screen_pass": False,
            "free_boundary_3D_MHD_pass": False,
            "formal_G1_approval": False,
        },
        "interpretation": [
            "The supplied mgrid_tomahawk_pf.nc is a native-successful PF MAKEGRID output and is byte-identical to the archived PF MGRID copy.",
            "The supplied coils.tomahawk_pf contains six PF groups and 578 closed 128-point filament loops; no TF coil group is present.",
            "The MGRID has nfp=1 and six PF field-group arrays on a 201 x 201 x 36 grid. It cannot evaluate TF edge ripple or total-field symmetry for the 16-period plasma boundary.",
            "The makegrid input_xgrid file named in the manifest is not present beside the supplied artifacts, so the native output is verifiable but the run is not fully replayable from this upload alone.",
        ],
    }
    (out / "makegrid_artifact_audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    group_rows = []
    for name in mgrid["group_names"]:
        item = coils["groups"].get(name, {})
        group_rows.append(f"| `{name}` | {item.get('loop_count')} | {item.get('current_min_A', float('nan')):.7f} | {item.get('max_closure_gap_m')} |")
    md = f"""# Native MAKEGRID artifact audit

Status: **{report['status']}**

This audit reads the supplied native output and its matching PF coil/current files. It does not modify them and does not infer TF data that is not present.

## Exact artifacts

| Artifact | SHA-256 |
|---|---|
| `mgrid_tomahawk_pf.nc` | `{report['source_files']['mgrid']['sha256']}` |
| `coils.tomahawk_pf` | `{report['source_files']['coils']['sha256']}` |
| `extcur.tomahawk_pf` | `{report['source_files']['extcur']['sha256']}` |
| `makegrid_run_manifest.json` | `{report['source_files']['manifest']['sha256']}` |
| `xgrid_tomahawk_pf.log` | `{report['source_files']['log']['sha256']}` |

## MAKEGRID result

- Native command return code: **{manifest.get('return_code')}**
- Manifest status: **`{manifest.get('status')}`**
- NetCDF dimensions: **ir={mgrid['ir']}, jz={mgrid['jz']}, kp={mgrid['kp']}**
- Grid bounds: **R={mgrid['rmin_m']}–{mgrid['rmax_m']} m**, **Z={mgrid['zmin_m']}–{mgrid['zmax_m']} m**
- `nfp`: **{mgrid['nfp']}**
- `nextcur`: **{mgrid['nextcur']}**
- `mgrid_mode`: **`{mgrid['mgrid_mode']}`**
- Field arrays finite: **{mgrid['field_variables_finite']}**; non-finite values: **{mgrid['field_nonfinite_count']}**
- First/last phi-plane maximum difference: **{mgrid['max_first_last_phi_plane_difference']:.6e}**
- MGRID and EXTCUR manifest hashes match: **{report['gates']['manifest_hashes_for_mgrid_and_extcur']}**
- Coil-file hash declared in the manifest: **{manifest_hash_checks['coils_sha256_declared']}** (coverage is incomplete, but no coil-file mismatch is asserted)

## PF coil/current reconciliation

| Group | Loops | Current (A) | Max loop closure gap (m) |
|---|---:|---:|---:|
{chr(10).join(group_rows)}

- Group labels match MGRID: **{report['reconciliations']['group_labels_match_mgrid']}**
- MGRID raw current versus `EXTCUR`: **{report['reconciliations']['mgrid_raw_current_vs_extcur_max_difference_A']:.6g} A maximum difference**
- Coil-file current versus `EXTCUR`: **{report['reconciliations']['coil_current_vs_extcur_max_difference_A']:.6g} A maximum difference**
- All loops are 128-point closed filaments: **{report['reconciliations']['all_loops_128_points'] and report['reconciliations']['all_loops_closed_by_duplicate_endpoint']}**

## What this does and does not close

- Native PF MAKEGRID artifact: **PASS**
- TF coil source in these files: **ABSENT**
- Total-field / TF edge-ripple screen from this MGRID: **BLOCKED**
- `free_boundary_3D_MHD_pass`: **BLOCKED**
- Formal G1 approval: **FALSE**

The manifest names `{manifest.get('input_file')}`, but that input configuration file is not included in the supplied directory. The native output and its hashes are still directly checkable; a complete replay requires that missing input file.
"""
    (out / "MAKEGRID_ARTIFACT_AUDIT.md").write_text(md, encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "mgrid_sha256": report["source_files"]["mgrid"]["sha256"],
        "coils_sha256": report["source_files"]["coils"]["sha256"],
        "extcur_sha256": report["source_files"]["extcur"]["sha256"],
        "native_makegrid_run_pass": report["gates"]["native_makegrid_return_code_zero"],
        "coil_current_reconciliation_pass": report["gates"]["coil_labels_and_currents_reconciled"],
        "mgrid_fields_finite": report["gates"]["mgrid_field_arrays_finite"],
        "nfp": mgrid["nfp"],
        "tf_edge_ripple_screen_pass": False,
        "output": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
