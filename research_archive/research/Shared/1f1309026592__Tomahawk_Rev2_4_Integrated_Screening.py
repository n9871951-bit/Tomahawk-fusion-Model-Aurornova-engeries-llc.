#!/usr/bin/env python3
"""Tomahawk Rev2.4 integrated numerical screening.

This program is a reproducible screening layer for the current Rev1.7
provisional input bundle.  It performs:

* a fixed-boundary, axisymmetric Grad-Shafranov solve;
* D-T reaction-rate, stored-energy, bremsstrahlung, alpha-heating, and
  confinement-loss calculations using the Bosch-Hale reactivity fit;
* consistency and conservation checks on the supplied profile;
* a first-pass RF-cassette coolant hydraulic/energy screen; and
* a reduced uncertainty sweep.

It deliberately does not claim a free-boundary 3-D equilibrium, nonlinear MHD
stability, orbit-resolved alpha transport, OpenMC/DAGMC tallies, CFD/CHT, or a
qualified CHF result.  Those items are emitted as explicit external-solver
blockers.  All numerical pass/fail labels in this file are screening labels.

The input bundle is expected to contain:
    MHD/mhd_input.json
    MHD/mhd_profile_sweep.csv
    CFD/cfd_cht_parameter_sweep.csv
    CHF/chf_input.json

The runner is fail-closed: it verifies the dataset manifest and SHA-256 map,
requires the corrected Rev2.4 confinement/coolant fields, and never substitutes
a fallback profile for a missing or malformed input.

NumPy is required.  SciPy is used for the fast sparse Grad-Shafranov solve
when available; a NumPy SOR fallback is retained for portability.  Matplotlib
is optional and only affects plot generation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import zipfile

import numpy as np


VERSION = "TOMAHAWK-REV2.4-INTEGRATED-SCREEN-1.5"
MODEL_VERSION = "CAD-A2-WHOLE-CONCEPT-1.7-MULTIPHYSICS-DOMAINS"
EXPECTED_ACTIVE_TAU_E_S = 2.70
EXPECTED_REFERENCE_TAU_E_S = 1.36
EXPECTED_REFERENCE_SELF_HEATING_RATIO = 0.63
EXPECTED_FULL_INCIDENT_SECONDARY_FRACTION = 0.50
REQUIRED_INPUT_FILES = (
    "MHD/mhd_input.json",
    "MHD/mhd_profile_sweep.csv",
    "CFD/cfd_cht_parameter_sweep.csv",
    "CHF/chf_input.json",
    "dataset_manifest.json",
)
MU0 = 4.0e-7 * math.pi
KEV_TO_J = 1.0e3 * 1.602176634e-19
MEV_TO_J = 1.0e6 * 1.602176634e-19
E_FUSION_J = 17.6 * MEV_TO_J
ALPHA_FRACTION = 3.5 / 17.6
NEUTRON_FRACTION = 14.1 / 17.6

# Bosch-Hale D-T Maxwellian reactivity coefficients.  C1..C7 are the
# published D-T fit coefficients; the fit returns cm^3/s and is converted to
# m^3/s below.
BH_DT = {
    "B_G_sqrt_keV": 34.3827,
    "mrc2_keV": 1124656.0,
    "C1": 1.17302e-9,
    "C2": 1.51361e-2,
    "C3": 7.51886e-2,
    "C4": 4.60643e-3,
    "C5": 1.35000e-2,
    "C6": -1.06750e-4,
    "C7": 1.36600e-5,
    "source": "Bosch and Hale, Nuclear Fusion 32 (1992) 611-631",
}

DEFAULTS = {
    "R0_m": 7.5,
    "a_m": 3.0,
    "kappa": 1.0,
    "CAD_volume_m3": 950.0,
    # This is an explicit plasma-axis screening assumption.  It is not
    # inferred from the Rev1.7 35 T target, which is retained as Bpeak here.
    "B0_plasma_T": 14.0,
    "Bpeak_coil_T": 35.0,
    "Z_eff": 1.0,
    "tau_E_s": 2.70,
    "reference_condition_tau_E_s": 1.36,
    "alpha_deposition_fraction": 0.90,
    "auxiliary_absorbed_MW": 20.0,
    "rf_face_area_m2": 2.5,
    "water_density_kg_m3": 997.0,
    "water_dynamic_viscosity_Pa_s": 3.5e-4,
    "water_conductivity_W_mK": 0.67,
    "water_cp_J_kgK": 4180.0,
    "water_roughness_m": 1.0e-5,
    "heated_length_m": 2.318,
    "pressure_drop_limit_Pa": 1.0e5,
    "CuCrZr_temperature_limit_K": 573.15,
    "minimum_DNBR": 1.30,
    "GS_residual_tolerance": 2.0e-3,
    "divB_relative_tolerance": 2.0e-10,
    "q95_proxy_min": 2.0,
    "beta_N_proxy_max": 3.5,
    "beta_axis_proxy_max_percent": 5.0,
    "tau_E_margin_min": 0.20,
    # A stored reference result may be compared against the current profile,
    # but it is never substituted for the current recomputation.
    "reference_self_heating_reconciliation_tolerance": 0.02,
    "secondary_heat_removal_fraction_by_scenario": {},
    "secondary_heat_removal_provenance": (
        "No secondary heat split supplied; cassette-local heat is used."),
}

class InputBlockedError(RuntimeError):
    """Raised when required inputs cannot be verified without substitution."""


def input_blocked(reason):
    raise InputBlockedError("INPUT_BLOCKED: %s" % reason)


def json_safe(value):
    """Convert NumPy values and non-finite floats into strict JSON values."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(value), indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_json(path, label=None):
    path = Path(path)
    label = label or str(path)
    if not path.is_file():
        input_blocked("required JSON is missing: %s" % label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        input_blocked("invalid JSON in %s: %s" % (label, exc))
    if not isinstance(value, dict):
        input_blocked("JSON root must be an object: %s" % label)
    return value


def _close(value, expected, tolerance=1.0e-12):
    try:
        return math.isclose(float(value), float(expected), rel_tol=0.0,
                            abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def audit_input_root(root):
    """Verify required files, declared hashes, model identity, and corrections."""
    root = Path(root).expanduser().resolve()
    for relative in REQUIRED_INPUT_FILES:
        if not (root / relative).is_file():
            input_blocked("required input is missing: %s" % relative)

    manifest_path = root / "dataset_manifest.json"
    manifest = read_json(manifest_path, "dataset_manifest.json")
    if manifest.get("model_version") != MODEL_VERSION:
        input_blocked(
            "dataset model_version mismatch: expected %s, found %r"
            % (MODEL_VERSION, manifest.get("model_version")))
    declared = manifest.get("files")
    if not isinstance(declared, dict) or not declared:
        input_blocked("dataset_manifest.json has no file-hash map")
    for relative in REQUIRED_INPUT_FILES:
        if relative == "dataset_manifest.json":
            continue
        if relative not in declared:
            input_blocked("manifest omits required file: %s" % relative)
    verified = {}
    for relative, expected_hash in sorted(declared.items()):
        candidate = (root / str(relative)).resolve()
        if candidate != root and root not in candidate.parents:
            input_blocked("manifest path escapes input root: %s" % relative)
        if not candidate.is_file():
            input_blocked("manifest-declared file is missing: %s" % relative)
        actual_hash = sha256(candidate)
        if actual_hash != str(expected_hash):
            input_blocked(
                "SHA-256 mismatch for %s: expected %s, found %s"
                % (relative, expected_hash, actual_hash))
        verified[str(relative)] = actual_hash

    mhd_input = read_json(root / "MHD" / "mhd_input.json",
                          "MHD/mhd_input.json")
    parameters = mhd_input.get("screening_parameters")
    if not isinstance(parameters, dict):
        input_blocked("MHD/mhd_input.json lacks screening_parameters")
    if not _close(parameters.get("tau_E_screening_target_s"),
                  EXPECTED_ACTIVE_TAU_E_S):
        input_blocked("active tau-E target must be 2.70 s")
    reference = parameters.get("reference_condition_correction")
    if not isinstance(reference, dict):
        input_blocked("reference_condition_correction is missing")
    if not _close(reference.get("tau_E_s"), EXPECTED_REFERENCE_TAU_E_S):
        input_blocked("reference-condition tau-E must be 1.36 s")
    if not _close(reference.get("self_heating_ratio"),
                  EXPECTED_REFERENCE_SELF_HEATING_RATIO):
        input_blocked("reference self-heating ratio must be 0.63")
    if reference.get("use_in_current_profile_prediction") is not False:
        input_blocked("the 63% reference result must not replace the active profile")
    routing = parameters.get("secondary_heat_removal_fraction_by_scenario")
    if not isinstance(routing, dict) or not _close(
            routing.get("full_incident_stress"),
            EXPECTED_FULL_INCIDENT_SECONDARY_FRACTION):
        input_blocked(
            "full_incident_stress secondary heat routing must be 0.50")
    return {
        "passed": True,
        "root": str(root),
        "manifest_sha256": sha256(manifest_path),
        "verified_file_count": len(verified),
        "verified_files": verified,
        "model_version": manifest.get("model_version"),
    }


def discover_input_root(explicit=None):
    """Find one verified provisional_inputs directory without guessing."""
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if root.name.upper() == "MHD" and root.parent.name == "provisional_inputs":
            root = root.parent
        audit_input_root(root)
        return root

    search_roots = []
    for value in (os.environ.get("TOMAHAWK_INPUT_ROOT"),
                  os.environ.get("TOMAHAWK_KAGGLE_INPUT_ROOT"),
                  "/kaggle/input",
                  os.environ.get("TOMAHAWK_KAGGLE_WORKING_ROOT"),
                  "/kaggle/working", str(Path.cwd())):
        if value:
            candidate = Path(value)
            if candidate.exists() and candidate not in search_roots:
                search_roots.append(candidate)
    candidates = []
    for search_root in search_roots:
        if (search_root / "MHD" / "mhd_profile_sweep.csv").is_file():
            candidates.append(search_root.resolve())
        try:
            matches = sorted(search_root.rglob("mhd_profile_sweep.csv"))
        except OSError:
            matches = []
        for match in matches:
            if match.parent.name == "MHD":
                candidates.append(match.parent.parent.resolve())
    candidates = list(dict.fromkeys(candidates))
    valid = []
    rejected = []
    for candidate in candidates:
        try:
            audit = audit_input_root(candidate)
            valid.append((candidate, audit))
        except InputBlockedError as exc:
            rejected.append("%s -> %s" % (candidate, exc))
    if not valid:
        detail = "; ".join(rejected[:4]) if rejected else "no candidates found"
        input_blocked("no verified provisional_inputs bundle: %s" % detail)
    fingerprints = {item[1]["manifest_sha256"] for item in valid}
    if len(fingerprints) != 1:
        input_blocked(
            "multiple different verified input bundles were found; set "
            "TOMAHAWK_INPUT_ROOT explicitly")
    return sorted(valid, key=lambda item: (len(str(item[0])), str(item[0])))[0][0]


def load_profile(path):
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for line_number, raw in enumerate(csv.DictReader(handle), start=2):
            try:
                rows.append({
                    "normalized_flux": float(raw["normalized_flux"]),
                    "pressure_Pa": float(raw["pressure_Pa"]),
                    "electron_temperature_keV": float(raw["electron_temperature_keV"]),
                    "ion_temperature_keV": float(raw["ion_temperature_keV"]),
                    "density_m3": float(raw["density_m3"]),
                    "value_status": raw.get("value_status", ""),
                })
            except (KeyError, TypeError, ValueError) as exc:
                input_blocked(
                    "malformed MHD profile row %d: %s" % (line_number, exc))
    if not rows:
        input_blocked("MHD profile CSV is empty: %s" % path)
    rows.sort(key=lambda item: item["normalized_flux"])
    return rows


def load_cfd_rows(path):
    rows = []
    if not path or not Path(path).is_file():
        input_blocked("CFD/CHT parameter sweep is missing: %s" % path)
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for line_number, raw in enumerate(csv.DictReader(handle), start=2):
            try:
                rows.append({
                    "case_id": raw["case_id"],
                    "channel_count": int(raw["channel_count"]),
                    "hydraulic_diameter_m": float(raw["hydraulic_diameter_m"]),
                    "velocity_m_s": float(raw["velocity_m_s"]),
                    "allowed_bulk_rise_K": float(raw["allowed_bulk_rise_K"]),
                    "heat_flux_scenario": raw["heat_flux_scenario"],
                    "local_heat_flux_W_m2": float(raw["local_heat_flux_W_m2"]),
                    "pressure_Pa": float(raw["pressure_Pa"]),
                    "inlet_temperature_K": float(raw["inlet_temperature_K"]),
                    "screening_Darcy_pressure_drop_Pa": float(
                        raw["screening_Darcy_pressure_drop_Pa"]),
                    "pressure_drop_limit_Pa": float(raw["pressure_drop_limit_Pa"]),
                    "CuCrZr_temperature_limit_K": float(
                        raw["CuCrZr_temperature_limit_K"]),
                })
            except (KeyError, TypeError, ValueError) as exc:
                input_blocked(
                    "malformed CFD/CHT row %d: %s" % (line_number, exc))
    if not rows:
        input_blocked("CFD/CHT parameter sweep contains no usable rows")
    return rows


def load_bundle(input_root=None):
    root = discover_input_root(input_root)
    audit = audit_input_root(root)
    paths = {
        "mhd_input": root / "MHD" / "mhd_input.json",
        "profile": root / "MHD" / "mhd_profile_sweep.csv",
        "cfd_sweep": root / "CFD" / "cfd_cht_parameter_sweep.csv",
        "chf_input": root / "CHF" / "chf_input.json",
        "dataset_manifest": root / "dataset_manifest.json",
    }
    files = {
        name: {
            "path": str(path.resolve()),
            "sha256": sha256(path),
            "present": True,
        }
        for name, path in paths.items()
    }
    profile = load_profile(paths["profile"])
    mhd_input = read_json(paths["mhd_input"], "MHD/mhd_input.json")
    cfd_rows = load_cfd_rows(paths["cfd_sweep"])
    chf_input = read_json(paths["chf_input"], "CHF/chf_input.json")
    return {
        "input_root": str(root),
        "files": files,
        "profile": profile,
        "mhd_input": mhd_input,
        "cfd_rows": cfd_rows,
        "chf_input": chf_input,
        "source_status": "BUNDLE_INPUTS_VERIFIED",
        "input_audit": audit,
    }


def profile_arrays(profile):
    return {
        key: np.asarray([row[key] for row in profile], dtype=float)
        for key in ("normalized_flux", "pressure_Pa",
                    "electron_temperature_keV", "ion_temperature_keV",
                    "density_m3")
    }


def validate_profile(profile):
    arrays = profile_arrays(profile)
    rho = arrays["normalized_flux"]
    density = arrays["density_m3"]
    te = arrays["electron_temperature_keV"]
    ti = arrays["ion_temperature_keV"]
    supplied_p = arrays["pressure_Pa"]
    calculated_p = density * (te + ti) * KEV_TO_J
    relative = np.abs(supplied_p - calculated_p) / np.maximum(np.abs(calculated_p), 1.0)
    gates = {
        "finite_values": bool(np.all(np.isfinite(np.column_stack(
            (rho, density, te, ti, supplied_p))))),
        "flux_strictly_increasing": bool(np.all(np.diff(rho) > 0.0)),
        "flux_bounded_0_1": bool(np.min(rho) >= 0.0 and np.max(rho) <= 1.0),
        "positive_density_and_temperature": bool(
            np.all(density > 0.0) and np.all(te > 0.0) and np.all(ti > 0.0)),
        "pressure_closure_pass": bool(np.max(relative) <= 2.0e-5),
    }
    return {
        "rows": int(len(profile)),
        "rho_min": float(np.min(rho)),
        "rho_max": float(np.max(rho)),
        "central_density_m3": float(density[0]),
        "central_electron_temperature_keV": float(te[0]),
        "central_ion_temperature_keV": float(ti[0]),
        "central_pressure_Pa_supplied": float(supplied_p[0]),
        "central_pressure_Pa_reconstructed": float(calculated_p[0]),
        "maximum_pressure_closure_relative_error": float(np.max(relative)),
        "gates": gates,
        "profile_consistency_pass": bool(all(gates.values())),
        "density_definition": "total quasi-neutral DT ion/electron density; nD=nT=n_total/2",
        "status": "PROVISIONAL_PROFILE_CONSISTENCY_CHECK",
    }, arrays


def dt_reactivity(T_keV):
    """Bosch-Hale D-T reactivity in m^3/s for a Maxwellian ion temperature."""
    T = np.clip(np.asarray(T_keV, dtype=float), 0.2, 100.0)
    p = BH_DT
    numerator = T * (p["C2"] + T * (p["C4"] + T * p["C6"]))
    denominator = 1.0 + T * (p["C3"] + T * (p["C5"] + T * p["C7"]))
    theta = T / (1.0 - numerator / denominator)
    xi = (p["B_G_sqrt_keV"] ** 2 / (4.0 * theta)) ** (1.0 / 3.0)
    cm3_per_s = (p["C1"] * theta
                  * np.sqrt(xi / (p["mrc2_keV"] * T ** 3))
                  * np.exp(-3.0 * xi))
    return 1.0e-6 * cm3_per_s


def make_grid(config, nr=161, nz=161):
    R0, a, kappa = config["R0_m"], config["a_m"], config["kappa"]
    R = np.linspace(R0 - 1.10 * a, R0 + 1.10 * a, int(nr))
    Z = np.linspace(-1.10 * kappa * a, 1.10 * kappa * a, int(nz))
    RR, ZZ = np.meshgrid(R, Z, indexing="xy")
    dR, dZ = float(R[1] - R[0]), float(Z[1] - Z[0])
    rho2 = ((RR - R0) / a) ** 2 + (ZZ / (kappa * a)) ** 2
    mask = rho2 <= 1.0
    return {
        "R": R, "Z": Z, "RR": RR, "ZZ": ZZ, "dR": dR, "dZ": dZ,
        "rho": np.sqrt(np.maximum(rho2, 0.0)), "mask": mask,
    }


def delta_star(psi, grid):
    """Finite-difference Delta-star operator with zero Dirichlet exterior."""
    RR, mask = grid["RR"], grid["mask"]
    dR, dZ = grid["dR"], grid["dZ"]
    east = np.zeros_like(psi)
    west = np.zeros_like(psi)
    north = np.zeros_like(psi)
    south = np.zeros_like(psi)
    east[:, :-1] = np.where(mask[:, 1:], psi[:, 1:], 0.0)
    west[:, 1:] = np.where(mask[:, :-1], psi[:, :-1], 0.0)
    north[:-1, :] = np.where(mask[1:, :], psi[1:, :], 0.0)
    south[1:, :] = np.where(mask[:-1, :], psi[:-1, :], 0.0)
    ae = 1.0 / dR ** 2 - 1.0 / (2.0 * RR * dR)
    aw = 1.0 / dR ** 2 + 1.0 / (2.0 * RR * dR)
    ap = -2.0 / dR ** 2 - 2.0 / dZ ** 2
    return ae * east + aw * west + north / dZ ** 2 + south / dZ ** 2 + ap * psi


def build_sparse_operator(grid):
    """Build the linear fixed-boundary Delta-star matrix."""
    from scipy import sparse

    RR, mask = grid["RR"], grid["mask"]
    dR, dZ = grid["dR"], grid["dZ"]
    nz, nr = mask.shape
    index = -np.ones(mask.shape, dtype=int)
    index[mask] = np.arange(int(mask.sum()))
    ae = 1.0 / dR ** 2 - 1.0 / (2.0 * RR * dR)
    aw = 1.0 / dR ** 2 + 1.0 / (2.0 * RR * dR)
    an = 1.0 / dZ ** 2
    ap = -2.0 / dR ** 2 - 2.0 / dZ ** 2
    row, col, data = [], [], []
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
    matrix = sparse.coo_matrix((data, (row, col)),
                               shape=(int(mask.sum()), int(mask.sum()))).tocsr()
    return matrix, index


def solve_gs_sor(grid, source, max_iters):
    """Portable fallback for the fixed-source linear equation."""
    RR, mask = grid["RR"], grid["mask"]
    dR, dZ = grid["dR"], grid["dZ"]
    ae = 1.0 / dR ** 2 - 1.0 / (2.0 * RR * dR)
    aw = 1.0 / dR ** 2 + 1.0 / (2.0 * RR * dR)
    ap = -2.0 / dR ** 2 - 2.0 / dZ ** 2
    checker = (np.indices(mask.shape).sum(axis=0) % 2) == 0
    psi = np.zeros_like(source)
    relaxation = 1.65
    scale = max(float(np.max(np.abs(source[mask]))), 1.0)
    relative = math.inf
    used = int(max_iters)
    for iteration in range(1, int(max_iters) + 1):
        east = np.zeros_like(psi)
        west = np.zeros_like(psi)
        north = np.zeros_like(psi)
        south = np.zeros_like(psi)
        east[:, :-1] = np.where(mask[:, 1:], psi[:, 1:], 0.0)
        west[:, 1:] = np.where(mask[:, :-1], psi[:, :-1], 0.0)
        north[:-1, :] = np.where(mask[1:, :], psi[1:, :], 0.0)
        south[1:, :] = np.where(mask[:-1, :], psi[:-1, :], 0.0)
        trial = (source - ae * east - aw * west
                 - (north + south) / dZ ** 2) / ap
        for parity in (True, False):
            active = mask & (checker == parity)
            psi[active] = ((1.0 - relaxation) * psi[active]
                           + relaxation * trial[active])
        psi[~mask] = 0.0
        if iteration == 1 or iteration % 25 == 0:
            residual = delta_star(psi, grid) - source
            relative = float(np.max(np.abs(residual[mask])) / scale)
            if relative <= 1.0e-6:
                used = iteration
                break
    residual = delta_star(psi, grid) - source
    relative = float(np.max(np.abs(residual[mask])) / scale)
    return psi, used, relative, "numpy_sor"


def solve_fixed_boundary_gs(config, target_pressure_pa, nr=161, nz=161,
                            max_iters=12000):
    """Solve Delta-star psi = -mu0 R^2 dp/dpsi for a fixed circular boundary."""
    grid = make_grid(config, nr=nr, nz=nz)
    RR, mask = grid["RR"], grid["mask"]
    unit_source = np.where(mask, -MU0 * RR ** 2, 0.0)
    method = "numpy_sor"
    iterations = int(max_iters)
    if target_pressure_pa <= 0.0:
        raise ValueError("The target central pressure must be positive.")

    try:
        matrix, index = build_sparse_operator(grid)
        from scipy.sparse.linalg import spsolve
        unit_flat = spsolve(matrix, unit_source[mask])
        unit_psi = np.zeros_like(RR)
        unit_psi[mask] = unit_flat
        method = "scipy_sparse_direct"
        iterations = 1
        solver_residual = float(np.max(
            np.abs(delta_star(unit_psi, grid)[mask] - unit_source[mask]))
            / max(float(np.max(np.abs(unit_source[mask]))), 1.0))
    except (ImportError, ModuleNotFoundError, RuntimeError, ValueError):
        unit_psi, iterations, solver_residual, method = solve_gs_sor(
            grid, unit_source, max_iters)

    psi_axis_unit = float(np.max(unit_psi[mask]))
    if not math.isfinite(psi_axis_unit) or psi_axis_unit <= 0.0:
        raise RuntimeError("Fixed-boundary GS solve returned a non-positive axis flux.")
    # The source is proportional to dp/dpsi, so the solved psi is also
    # proportional to dp/dpsi.  Because p = (dp/dpsi)*psi, the axis pressure
    # is quadratic in this calibration factor.
    dp_dpsi = math.sqrt(target_pressure_pa / psi_axis_unit)
    psi = dp_dpsi * unit_psi
    source = dp_dpsi * unit_source
    residual = delta_star(psi, grid) - source
    relative = float(np.max(np.abs(residual[mask]))
                    / max(float(np.max(np.abs(source[mask]))), 1.0))
    return grid, psi, source, {
        "method": method,
        "iterations": iterations,
        "dp_dpsi_Pa_Wb": float(dp_dpsi),
        "residual_relative": relative,
        "unit_solve_residual_relative": solver_residual,
        "target_pressure_Pa": float(target_pressure_pa),
    }


def equilibrium_metrics(config, grid, psi, source, gs_info):
    RR, mask, rho = grid["RR"], grid["mask"], grid["rho"]
    dR, dZ = grid["dR"], grid["dZ"]
    p_axis = float(np.max(psi[mask]) * gs_info["dp_dpsi_Pa_Wb"])
    p_eq = np.where(mask, np.maximum(psi * gs_info["dp_dpsi_Pa_Wb"], 0.0), 0.0)
    dpsi_dz, dpsi_dr = np.gradient(psi, dZ, dR, edge_order=2)
    br = np.where(mask, -dpsi_dz / RR, 0.0)
    bz = np.where(mask, dpsi_dr / RR, 0.0)
    f_edge = config["R0_m"] * config["B0_plasma_T"]
    bphi = np.where(mask, f_edge / RR, 0.0)
    jphi = np.where(mask, RR * gs_info["dp_dpsi_Pa_Wb"], 0.0)
    dA = dR * dZ
    volume = float(np.sum((2.0 * math.pi * RR)[mask]) * dA)
    ip = float(np.sum(jphi[mask]) * dA)
    core = mask & (rho <= 0.90)
    divb = (np.gradient(RR * br, dR, axis=1, edge_order=2) / RR
            + np.gradient(bz, dZ, axis=0, edge_order=2))
    field_scale = max(float(np.max(np.abs(br[core]))),
                      float(np.max(np.abs(bz[core]))), 1.0) / config["a_m"]
    divb_relative = float(np.max(np.abs(divb[core])) / field_scale)
    ip95 = float(np.sum(jphi[mask & (rho <= 0.95)]) * dA)
    q95 = (2.0 * math.pi * (0.95 * config["a_m"]) ** 2
           * config["B0_plasma_T"]
           / (MU0 * config["R0_m"] * max(abs(ip95), 1.0)))
    p_volume = float(np.sum(p_eq[mask] * (2.0 * math.pi * RR[mask])) * dA
                     / max(volume, 1.0))
    beta_axis = 2.0 * MU0 * p_axis / config["B0_plasma_T"] ** 2
    beta_volume = 2.0 * MU0 * p_volume / config["B0_plasma_T"] ** 2
    beta_n = 100.0 * beta_volume * config["a_m"] * config["B0_plasma_T"] / max(
        abs(ip) / 1.0e6, 1.0e-12)
    shells = np.linspace(0.05, 0.95, 19)
    shell_p = np.asarray([
        np.nanmean(p_eq[(rho >= value - 0.025) & (rho < value + 0.025)])
        for value in shells
    ])
    finite_shell = shell_p[np.isfinite(shell_p)]
    monotonic = bool(len(finite_shell) > 1
                     and np.all(np.diff(finite_shell) <= 1.0e-6 * max(p_axis, 1.0)))
    residual_relative = float(gs_info["residual_relative"])
    gates = {
        "GS_residual_pass": residual_relative <= config["GS_residual_tolerance"],
        "divB_pass": divb_relative <= config["divB_relative_tolerance"],
        "positive_pressure_pass": bool(p_axis > 0.0 and np.min(p_eq[mask]) >= -1.0e-9),
        "pressure_monotonic_pass": monotonic,
        "q95_proxy_pass": bool(q95 >= config["q95_proxy_min"]),
        "beta_N_proxy_pass": bool(beta_n <= config["beta_N_proxy_max"]),
        "beta_axis_proxy_pass": bool(
            100.0 * beta_axis <= config["beta_axis_proxy_max_percent"]),
    }
    gates["equilibrium_numerical_pass"] = bool(all(
        gates[name] for name in ("GS_residual_pass", "divB_pass",
                                 "positive_pressure_pass")))
    gates["ideal_MHD_proxy_pass"] = bool(all(
        gates[name] for name in ("pressure_monotonic_pass", "q95_proxy_pass",
                                 "beta_N_proxy_pass", "beta_axis_proxy_pass")))
    metrics = {
        "solver_method": gs_info["method"],
        "gs_iterations": gs_info["iterations"],
        "gs_residual_relative": residual_relative,
        "unit_solve_residual_relative": gs_info["unit_solve_residual_relative"],
        "divB_relative": divb_relative,
        "psi_axis_Wb": float(np.max(psi[mask])),
        "p_axis_MPa": p_axis / 1.0e6,
        "p_volume_average_MPa": p_volume / 1.0e6,
        "I_p_solved_MA": ip / 1.0e6,
        "I_p_95_MA": ip95 / 1.0e6,
        "q95_cylindrical_proxy": q95,
        "beta_axis_percent": 100.0 * beta_axis,
        "beta_volume_percent": 100.0 * beta_volume,
        "beta_N_proxy": beta_n,
        "grid_toroidal_volume_m3": volume,
        "CAD_volume_m3": config["CAD_volume_m3"],
        "grid_to_CAD_volume_ratio": volume / config["CAD_volume_m3"],
        "magnetic_pressure_axis_MPa": config["B0_plasma_T"] ** 2 / (2.0 * MU0) / 1e6,
        "magnetic_pressure_coil_MPa": config["Bpeak_coil_T"] ** 2 / (2.0 * MU0) / 1e6,
        "gates": gates,
        "status": "FIXED_BOUNDARY_AXISYMMETRIC_SCREEN_NOT_3D_MHD",
    }
    fields = {
        "psi": psi, "pressure": p_eq, "BR": br, "BZ": bz, "BPHI": bphi,
        "JPHI": jphi,
    }
    return metrics, fields


def weighted_profile_values(profile, arrays, quadrature_order=128):
    nodes, weights = np.polynomial.legendre.leggauss(quadrature_order)
    rq = 0.5 * (nodes + 1.0)
    volume_weights = 0.5 * weights * (nodes + 1.0)
    values = {
        key: np.interp(rq, arrays["normalized_flux"], arrays[key])
        for key in ("pressure_Pa", "electron_temperature_keV",
                    "ion_temperature_keV", "density_m3")
    }
    return rq, volume_weights, values


def confinement_metrics(config, profile, arrays):
    rq, weights, values = weighted_profile_values(profile, arrays)
    density = values["density_m3"]
    n_d = density / 2.0
    n_t = density / 2.0
    n_e = density
    n_i = density
    te = values["electron_temperature_keV"]
    ti = values["ion_temperature_keV"]
    reactivity = dt_reactivity(ti)
    reaction_rate = config["CAD_volume_m3"] * float(np.sum(
        weights * n_d * n_t * reactivity))
    p_fusion = reaction_rate * E_FUSION_J
    p_alpha = p_fusion * ALPHA_FRACTION
    p_neutron = p_fusion * NEUTRON_FRACTION
    p_alpha_deposited = p_alpha * config["alpha_deposition_fraction"]
    # The coefficient is expressed for electron temperature in keV.  Do not
    # apply an extra sqrt(1000) conversion here; that was the source of the
    # earlier overestimated bremsstrahlung loss and failed smoke gate.
    p_brem_density = 5.35e-37 * config["Z_eff"] * n_e ** 2 * np.sqrt(te)
    p_brem = config["CAD_volume_m3"] * float(np.sum(weights * p_brem_density))
    pressure_reconstructed = n_i * (ti + te) * KEV_TO_J
    p_avg = float(np.sum(weights * pressure_reconstructed))
    w_thermal = 1.5 * config["CAD_volume_m3"] * p_avg
    p_transport = w_thermal / config["tau_E_s"]
    modeled_losses = p_transport + p_brem
    p_aux = config["auxiliary_absorbed_MW"] * 1.0e6
    alpha_ratio = p_alpha_deposited / max(modeled_losses, 1.0)
    if p_alpha_deposited > p_brem:
        tau_required = w_thermal / (p_alpha_deposited - p_brem)
        tau_margin = config["tau_E_s"] / tau_required - 1.0
    else:
        tau_required = math.inf
        tau_margin = -math.inf
    n_avg = float(np.sum(weights * density))
    ti_avg = float(np.sum(weights * ti))
    te_avg = float(np.sum(weights * te))
    reference_ratio = config.get("reference_self_heating_ratio")
    reference_tau_e = float(config.get(
        "reference_condition_tau_E_s",
        DEFAULTS["reference_condition_tau_E_s"]))
    reference_transport = w_thermal / max(reference_tau_e, 1.0e-30)
    reference_modeled_losses = reference_transport + p_brem
    reference_ratio_computed = p_alpha_deposited / max(
        reference_modeled_losses, 1.0)
    if reference_ratio is None:
        reference_delta = None
        reference_reconciled = None
        reference_status = "NOT_SUPPLIED"
    else:
        reference_delta = float(reference_ratio - reference_ratio_computed)
        reference_reconciled = bool(
            abs(reference_delta)
            <= config["reference_self_heating_reconciliation_tolerance"])
        reference_status = (
            "RECONCILED_TO_CURRENT_PROFILE"
            if reference_reconciled else
            "BLOCKED_UNMAPPED_REFERENCE_CORRECTION")
    metrics = {
        "fusion_GW_module": p_fusion / 1.0e9,
        "alpha_GW_module": p_alpha / 1.0e9,
        "alpha_deposited_GW_module": p_alpha_deposited / 1.0e9,
        "neutron_GW_module": p_neutron / 1.0e9,
        "bremsstrahlung_GW_module": p_brem / 1.0e9,
        "bremsstrahlung_equation": (
            "P_brem = 5.35e-37 * Z_eff * n_e^2 * sqrt(T_e_keV)"),
        "bremsstrahlung_temperature_units": "keV",
        "transport_loss_GW_module": p_transport / 1.0e9,
        "modeled_total_loss_GW_module": modeled_losses / 1.0e9,
        "thermal_energy_GJ_module": w_thermal / 1.0e9,
        "absorbed_auxiliary_MW_module": p_aux / 1.0e6,
        "Q_fusion_over_absorbed_auxiliary": p_fusion / max(p_aux, 1.0),
        "Q_fusion_over_modeled_losses": p_fusion / max(modeled_losses, 1.0),
        "alpha_self_heating_ratio": alpha_ratio,
        "tau_E_assumption_s": config["tau_E_s"],
        "active_tau_E_screening_target_s": config["tau_E_s"],
        "active_tau_E_screening_target_provenance": config.get(
            "active_tau_E_screening_target_provenance"),
        "tau_E_required_for_alpha_balance_s": tau_required,
        "tau_E_margin_ratio": tau_margin,
        "net_alpha_margin_GW_module": (
            p_alpha_deposited - p_brem - p_transport) / 1.0e9,
        "triple_product_nT_keV_s_m3": n_avg * ti_avg * config["tau_E_s"],
        "volume_weighted_density_m3": n_avg,
        "volume_weighted_Ti_keV": ti_avg,
        "volume_weighted_Te_keV": te_avg,
        "reactivity_at_volume_weighted_Ti_m3_s": float(dt_reactivity(ti_avg)),
        "reactivity_model": BH_DT["source"],
        "volume_weighting": "normalized-radius weight 2*rho; screening approximation",
        "self_heating_definition": (
            "deposited alpha power / (bremsstrahlung + W/tau_E)"),
        "reference_condition_self_heating_ratio": reference_ratio,
        "reference_condition_self_heating_ratio_computed": (
            reference_ratio_computed if reference_ratio is not None else None),
        "reference_condition_tau_E_s": reference_tau_e,
        "reference_condition_self_heating_ratio_delta": reference_delta,
        "reference_condition_self_heating_definition": config.get(
            "reference_self_heating_definition"),
        "reference_condition_self_heating_provenance": config.get(
            "reference_self_heating_provenance"),
        "reference_condition_self_heating_source_status": config.get(
            "reference_self_heating_source_status"),
        "reference_condition_self_heating_used_as_model_input": config.get(
            "reference_self_heating_used_as_model_input", False),
        "reference_condition_reconciliation_tolerance": config.get(
            "reference_self_heating_reconciliation_tolerance"),
        "reference_condition_reconciliation_status": reference_status,
        "gates": {
            "alpha_self_heating_pass": bool(alpha_ratio >= 1.0),
            "tau_E_margin_pass": bool(tau_margin >= config["tau_E_margin_min"]),
            "reference_self_heating_reconciliation_pass": reference_reconciled,
        },
        "status": "0D_DT_POWER_AND_CONFINEMENT_SCREEN_NOT_BURNING_PLASMA_VALIDATION",
    }
    return metrics


def darcy_pressure_drop(rho, velocity, diameter, length, roughness, dynamic_mu):
    reynolds = rho * velocity * diameter / dynamic_mu
    if reynolds <= 0.0:
        return 0.0, reynolds, 0.0
    friction = 0.25 / math.log10(
        roughness / (3.7 * diameter) + 5.74 / reynolds ** 0.9) ** 2
    dp = friction * (length / diameter) * rho * velocity ** 2 / 2.0
    return dp, reynolds, friction


def coolant_screen(config, cfd_rows):
    if not cfd_rows:
        return {
            "status": "BLOCKED_MISSING_CFD_SWEEP",
            "rows": 0,
            "gates": {
                "hydraulic_screen_pass": None,
                "thermal_capacity_screen_pass": None,
                "wall_temperature_screen_pass": None,
                "coolant_screen_pass": None,
            },
            "reason": "CFD/CHT sweep was not supplied; no coolant result was invented.",
        }, []
    rho = config["water_density_kg_m3"]
    mu = config["water_dynamic_viscosity_Pa_s"]
    k = config["water_conductivity_W_mK"]
    cp = config["water_cp_J_kgK"]
    roughness = config["water_roughness_m"]
    length = config["heated_length_m"]
    face_area = config["rf_face_area_m2"]
    routing = config.get("secondary_heat_removal_fraction_by_scenario", {})
    if not isinstance(routing, dict):
        raise ValueError("secondary heat routing must be a scenario-to-fraction mapping")
    pressure_rows = []
    for row in cfd_rows:
        n = row["channel_count"]
        d = row["hydraulic_diameter_m"]
        velocity = row["velocity_m_s"]
        qflux = row["local_heat_flux_W_m2"]
        flow_area = n * d ** 2
        mass_flow = rho * velocity * flow_area
        dp, reynolds, friction = darcy_pressure_drop(
            rho, velocity, d, length, roughness, mu)
        prandtl = cp * mu / k
        nusselt = 0.023 * reynolds ** 0.8 * prandtl ** 0.4
        h = nusselt * k / d
        scenario = row["heat_flux_scenario"]
        secondary_fraction = float(routing.get(scenario, 0.0))
        if not 0.0 <= secondary_fraction <= 1.0:
            raise ValueError(
                "secondary heat removal fraction must be between 0 and 1: "
                f"{scenario}={secondary_fraction}")
        incident_heat_load = qflux * face_area
        secondary_heat_load = incident_heat_load * secondary_fraction
        heat_load = incident_heat_load - secondary_heat_load
        effective_local_heat_flux = heat_load / max(face_area, 1.0e-30)
        bulk_rise = heat_load / max(mass_flow * cp, 1.0)
        wall_rise = effective_local_heat_flux / max(h, 1.0)
        wall_temperature = row["inlet_temperature_K"] + bulk_rise + wall_rise
        declared_dp_error = abs(dp - row["screening_Darcy_pressure_drop_Pa"])
        hydraulic_pass = dp <= row["pressure_drop_limit_Pa"]
        capacity_pass = bulk_rise <= row["allowed_bulk_rise_K"]
        wall_pass = wall_temperature <= row["CuCrZr_temperature_limit_K"]
        pressure_rows.append({
            **row,
            "flow_area_m2": flow_area,
            "mass_flow_kg_s": mass_flow,
            "Reynolds": reynolds,
            "Prandtl_screening": prandtl,
            "Darcy_friction_factor": friction,
            "recomputed_pressure_drop_Pa": dp,
            "declared_Darcy_absolute_error_Pa": declared_dp_error,
            "Nusselt_screening": nusselt,
            "h_screening_W_m2K": h,
            "incident_heat_load_W_per_cassette": incident_heat_load,
            "secondary_heat_removal_fraction": secondary_fraction,
            "secondary_heat_routed_W_per_cassette": secondary_heat_load,
            "heat_load_W_per_cassette": heat_load,
            "incident_local_heat_flux_W_m2": qflux,
            "effective_cassette_heat_flux_W_m2": effective_local_heat_flux,
            "heat_balance_residual_W": (
                incident_heat_load - secondary_heat_load - heat_load),
            "bulk_rise_K_screening": bulk_rise,
            "wall_superheat_K_screening": wall_rise,
            "wall_temperature_K_screening": wall_temperature,
            "hydraulic_screen_pass": hydraulic_pass,
            "thermal_capacity_screen_pass": capacity_pass,
            "wall_temperature_screen_pass": wall_pass,
            "screen_pass": bool(hydraulic_pass and capacity_pass and wall_pass),
            "value_status": "PROVISIONAL_CORRELATION_SCREEN_NOT_CFD_OR_CHF_RESULT",
        })
    hydraulic = all(row["hydraulic_screen_pass"] for row in pressure_rows)
    capacity = all(row["thermal_capacity_screen_pass"] for row in pressure_rows)
    wall = all(row["wall_temperature_screen_pass"] for row in pressure_rows)
    scenarios = {}
    for scenario in sorted({row["heat_flux_scenario"] for row in pressure_rows}):
        subset = [row for row in pressure_rows if row["heat_flux_scenario"] == scenario]
        scenarios[scenario] = {
            "rows": len(subset),
            "secondary_heat_removal_fraction": sorted({
                row["secondary_heat_removal_fraction"] for row in subset}),
            "max_incident_heat_load_W_per_cassette": max(
                row["incident_heat_load_W_per_cassette"] for row in subset),
            "max_secondary_heat_routed_W_per_cassette": max(
                row["secondary_heat_routed_W_per_cassette"] for row in subset),
            "max_local_heat_load_W_per_cassette": max(
                row["heat_load_W_per_cassette"] for row in subset),
            "max_heat_balance_residual_W": max(abs(
                row["heat_balance_residual_W"]) for row in subset),
            "max_pressure_drop_Pa": max(row["recomputed_pressure_drop_Pa"] for row in subset),
            "max_bulk_rise_K": max(row["bulk_rise_K_screening"] for row in subset),
            "max_wall_temperature_K": max(
                row["wall_temperature_K_screening"] for row in subset),
            "screen_pass": bool(all(row["screen_pass"] for row in subset)),
        }
    summary = {
        "rows": len(pressure_rows),
        "max_pressure_drop_Pa": max(
            row["recomputed_pressure_drop_Pa"] for row in pressure_rows),
        "max_bulk_rise_K": max(row["bulk_rise_K_screening"] for row in pressure_rows),
        "max_wall_temperature_K": max(
            row["wall_temperature_K_screening"] for row in pressure_rows),
        "maximum_declared_Darcy_check_error_Pa": max(
            row["declared_Darcy_absolute_error_Pa"] for row in pressure_rows),
        "secondary_heat_routing": {
            "fractions_by_scenario": {
                str(key): float(value) for key, value in routing.items()},
            "provenance": config.get("secondary_heat_removal_provenance"),
            "energy_balance": (
                "incident heat = secondary routed heat + cassette-local heat"),
            "secondary_system_capacity_status": (
                "NOT_MODELED; routed heat is reported but not qualified"),
        },
        "gates": {
            "hydraulic_screen_pass": hydraulic,
            "thermal_capacity_screen_pass": capacity,
            "wall_temperature_screen_pass": wall,
            "coolant_screen_pass": bool(hydraulic and capacity and wall),
        },
        "scenario_summary": scenarios,
        "water_properties_status": "CONSTANT_SCREENING_VALUES_NOT_PROPERTY_TABLE",
        "CHF_status": "BLOCKED_EXTERNAL_SOLVER_NO_QUALIFIED_CORRELATION",
        "status": "PROVISIONAL_COOLANT_HYDRAULIC_AND_ENERGY_SCREEN",
    }
    return summary, pressure_rows


def uncertainty_sweep(config, equilibrium, confinement, gates, output,
                      cases=65536, seed=20260905, chunk_size=4096):
    """Run a memory-bounded reduced envelope screen; no new GS solve per sample."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_id", "density_scale", "Ti_scale", "Te_scale", "B0_scale",
        "tau_E_scale", "alpha_deposition_fraction", "Z_eff", "a_scale",
        "R0_scale", "Ip_scale", "fusion_GW_module", "alpha_ratio",
        "tau_E_required_s", "tau_E_margin_ratio", "beta_axis_percent",
        "beta_N_proxy", "q95_proxy", "gate_all",
    ]
    path = output / "reduced_uncertainty_cases.csv"
    rng = np.random.default_rng(int(seed))
    base_fusion = confinement["fusion_GW_module"] * 1.0e9
    base_brem = confinement["bremsstrahlung_GW_module"] * 1.0e9
    base_w = confinement["thermal_energy_GJ_module"] * 1.0e9
    ti0 = confinement["volume_weighted_Ti_keV"]
    base_reactivity = float(dt_reactivity(ti0))
    p_avg = confinement["volume_weighted_density_m3"] * (
        confinement["volume_weighted_Ti_keV"]
        + confinement["volume_weighted_Te_keV"]) * KEV_TO_J
    base_beta_axis = 100.0 * 2.0 * MU0 * p_avg / config["B0_plasma_T"] ** 2
    base_beta_n = equilibrium["beta_N_proxy"]
    base_q95 = equilibrium["q95_cylindrical_proxy"]
    base_eq_pass = bool(
        equilibrium["gates"]["equilibrium_numerical_pass"]
        and equilibrium["gates"]["pressure_monotonic_pass"])
    reference_reconciliation_pass = gates.get(
        "reference_self_heating_reconciliation_pass")
    reference_reconciliation_ok = reference_reconciliation_pass is True
    passes = 0
    best_ratio = -math.inf
    best_margin = -math.inf
    best_q95 = -math.inf
    plot_x, plot_y = [], []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for start in range(0, int(cases), int(chunk_size)):
            n = min(int(chunk_size), int(cases) - start)
            ds = rng.uniform(0.80, 1.30, n)
            tis = rng.uniform(0.80, 1.30, n)
            tes = rng.uniform(0.80, 1.30, n)
            bs = rng.uniform(0.85, 1.15, n)
            taus = rng.uniform(0.60, 3.00, n)
            alpha_dep = rng.uniform(0.80, 0.98, n)
            zeff = rng.uniform(1.00, 1.80, n)
            a_scale = rng.uniform(0.87, 1.13, n)
            r_scale = rng.uniform(0.91, 1.09, n)
            ip_scale = rng.uniform(0.72, 1.28, n)
            fusion = base_fusion * ds ** 2 * (
                dt_reactivity(ti0 * tis) / max(base_reactivity, 1.0e-99))
            brem = base_brem * ds ** 2 * np.sqrt(tes) * zeff
            thermal = base_w * ds * 0.5 * (tis + tes)
            transport = thermal / taus
            alpha_power = fusion * ALPHA_FRACTION * alpha_dep
            ratio = alpha_power / np.maximum(brem + transport, 1.0)
            tau_req = np.where(alpha_power > brem,
                               thermal / np.maximum(alpha_power - brem, 1.0),
                               np.inf)
            margin = np.where(np.isfinite(tau_req), taus / tau_req - 1.0,
                              -np.inf)
            beta_axis = base_beta_axis * ds * 0.5 * (tis + tes) / bs ** 2
            beta_n = base_beta_n * ds * 0.5 * (tis + tes) * a_scale / (
                bs * ip_scale)
            q95 = base_q95 * a_scale ** 2 * bs / (r_scale * ip_scale)
            gate_all = (
                base_eq_pass
                & reference_reconciliation_ok
                & (q95 >= config["q95_proxy_min"])
                & (beta_n <= config["beta_N_proxy_max"])
                & (beta_axis <= config["beta_axis_proxy_max_percent"])
                & (ratio >= 1.0)
                & (margin >= config["tau_E_margin_min"])
            )
            passes += int(np.sum(gate_all))
            best_ratio = max(best_ratio, float(np.max(ratio)))
            finite_margin = margin[np.isfinite(margin)]
            if len(finite_margin):
                best_margin = max(best_margin, float(np.max(finite_margin)))
            best_q95 = max(best_q95, float(np.max(q95)))
            if len(plot_x) < 12000:
                take = min(n, 12000 - len(plot_x))
                plot_x.extend(q95[:take].tolist())
                plot_y.extend(beta_n[:take].tolist())
            for index in range(n):
                writer.writerow({
                    "case_id": start + index,
                    "density_scale": ds[index],
                    "Ti_scale": tis[index],
                    "Te_scale": tes[index],
                    "B0_scale": bs[index],
                    "tau_E_scale": taus[index],
                    "alpha_deposition_fraction": alpha_dep[index],
                    "Z_eff": zeff[index],
                    "a_scale": a_scale[index],
                    "R0_scale": r_scale[index],
                    "Ip_scale": ip_scale[index],
                    "fusion_GW_module": fusion[index] / 1.0e9,
                    "alpha_ratio": ratio[index],
                    "tau_E_required_s": tau_req[index],
                    "tau_E_margin_ratio": margin[index],
                    "beta_axis_percent": beta_axis[index],
                    "beta_N_proxy": beta_n[index],
                    "q95_proxy": q95[index],
                    "gate_all": bool(gate_all[index]),
                })
    summary = {
        "cases": int(cases),
        "seed": int(seed),
        "all_gate_passes": passes,
        "all_gate_pass_percent": 100.0 * passes / max(int(cases), 1),
        "best_alpha_self_heating_ratio": best_ratio,
        "best_tau_E_margin_ratio": best_margin,
        "best_q95_proxy": best_q95,
        "note": "Reduced scaling screen; it does not re-solve Grad-Shafranov per sample.",
        "status": "REDUCED_UNCERTAINTY_SCREEN",
    }
    write_json(output / "reduced_uncertainty_summary.json", summary)
    return summary, np.asarray(plot_x), np.asarray(plot_y)


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(json_safe(row) for row in rows)


def make_plots(output, grid, fields, uncertainty_x, uncertainty_y):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {"plots_status": "MATPLOTLIB_UNAVAILABLE"}
    output = Path(output)
    RR, ZZ, mask = grid["RR"], grid["ZZ"], grid["mask"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    psi = np.where(mask, fields["psi"], np.nan)
    pressure = np.where(mask, fields["pressure"] / 1e6, np.nan)
    current = np.where(mask, fields["JPHI"] / 1e6, np.nan)
    levels = np.linspace(float(np.nanmin(psi)), float(np.nanmax(psi)), 18)
    contours = axes[0].contour(RR, ZZ, psi, levels=levels, cmap="viridis")
    axes[0].clabel(contours, inline=True, fontsize=7, fmt="%.2g")
    axes[0].set_title("Fixed-boundary poloidal flux")
    image = axes[1].pcolormesh(RR, ZZ, pressure, shading="auto", cmap="magma")
    fig.colorbar(image, ax=axes[1], label="MPa")
    axes[1].set_title("Pressure screen")
    image = axes[2].pcolormesh(RR, ZZ, current, shading="auto", cmap="coolwarm")
    fig.colorbar(image, ax=axes[2], label="MA/m2")
    axes[2].set_title("Toroidal current-density screen")
    for axis in axes:
        axis.set_xlabel("R (m)")
        axis.set_ylabel("Z (m)")
    fig.savefig(output / "equilibrium_fields.png", dpi=160)
    plt.close(fig)

    if len(uncertainty_x):
        fig, axis = plt.subplots(figsize=(6.6, 5.0), constrained_layout=True)
        axis.scatter(uncertainty_x, uncertainty_y, s=3, alpha=0.22)
        axis.axvline(DEFAULTS["q95_proxy_min"], color="black", linestyle="--")
        axis.axhline(DEFAULTS["beta_N_proxy_max"], color="black", linestyle="--")
        axis.set_xlabel("q95 cylindrical proxy")
        axis.set_ylabel("beta_N proxy")
        axis.set_title("Reduced uncertainty MHD-proxy space")
        fig.savefig(output / "reduced_uncertainty_mhd_space.png", dpi=160)
        plt.close(fig)
    return {"plots_status": "GENERATED"}


def run_native_screen(input_root=None, output_root="tomahawk_rev24_screen",
                      label="full", cases=65536, seed=20260905, nr=161, nz=161,
                      max_gs_iters=12000, overrides=None):
    """Run one labeled screen and write all auditable artifacts."""
    started = time.time()
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle = load_bundle(input_root)
    config = dict(DEFAULTS)
    mhd_parameters = bundle["mhd_input"].get("screening_parameters", {})
    if mhd_parameters.get("magnetic_field_target_T") is not None:
        config["Bpeak_coil_T"] = float(mhd_parameters["magnetic_field_target_T"])
    active_tau_target = mhd_parameters.get("tau_E_screening_target_s")
    if active_tau_target is not None:
        config["tau_E_s"] = float(active_tau_target)
        config["active_tau_E_screening_target_provenance"] = str(
            mhd_parameters.get(
                "tau_E_screening_target_provenance",
                "active tau-E screening target supplied by MHD input"))
    else:
        config["active_tau_E_screening_target_provenance"] = (
            "default active tau-E screening target; not a measured confinement result")
    secondary_fractions = mhd_parameters.get(
        "secondary_heat_removal_fraction_by_scenario")
    if isinstance(secondary_fractions, dict):
        config["secondary_heat_removal_fraction_by_scenario"] = {
            str(key): float(value)
            for key, value in secondary_fractions.items()}
        config["secondary_heat_removal_provenance"] = str(
            mhd_parameters.get(
                "secondary_heat_removal_provenance",
                config["secondary_heat_removal_provenance"]))
    reference_correction = mhd_parameters.get(
        "reference_condition_correction", {})
    if isinstance(reference_correction, dict):
        if reference_correction.get("tau_E_s") is not None:
            config["reference_condition_tau_E_s"] = float(
                reference_correction["tau_E_s"])
        if reference_correction.get("self_heating_ratio") is not None:
            config["reference_self_heating_ratio"] = float(
                reference_correction["self_heating_ratio"])
            config["reference_self_heating_definition"] = str(
                reference_correction.get("definition", ""))
            config["reference_self_heating_provenance"] = str(
                reference_correction.get("provenance", ""))
            config["reference_self_heating_source_status"] = str(
                reference_correction.get("status", ""))
            config["reference_self_heating_used_as_model_input"] = bool(
                reference_correction.get("use_in_current_profile_prediction", False))
    if overrides:
        config.update(overrides)
    profile = bundle["profile"]
    profile_metrics, arrays = validate_profile(profile)
    target_pressure = profile_metrics["central_pressure_Pa_reconstructed"]
    grid, psi, source, gs_info = solve_fixed_boundary_gs(
        config, target_pressure, nr=nr, nz=nz, max_iters=max_gs_iters)
    eq_metrics, field_arrays = equilibrium_metrics(
        config, grid, psi, source, gs_info)
    conf_metrics = confinement_metrics(config, profile, arrays)
    coolant_summary, coolant_rows = coolant_screen(config, bundle["cfd_rows"])
    write_csv(output / "coolant_screen_rows.csv", coolant_rows)

    gates = dict(eq_metrics["gates"])
    gates.update(profile_metrics["gates"])
    gates.update(conf_metrics["gates"])
    gates["input_bundle_verified"] = bool(bundle["input_audit"]["passed"])
    gates["equilibrium_numerical_pass"] = bool(
        eq_metrics["gates"]["equilibrium_numerical_pass"])
    gates["ideal_MHD_proxy_pass"] = bool(
        eq_metrics["gates"]["ideal_MHD_proxy_pass"])
    gates["profile_consistency_pass"] = bool(
        profile_metrics["profile_consistency_pass"])
    gates["confinement_numerical_screen_pass"] = bool(
        gates["equilibrium_numerical_pass"]
        and gates["ideal_MHD_proxy_pass"]
        and gates["profile_consistency_pass"])
    gates["coolant_screen_pass"] = coolant_summary["gates"].get(
        "coolant_screen_pass")
    gates["free_boundary_3D_MHD"] = "BLOCKED_EXTERNAL_SOLVER"
    gates["nonlinear_MHD_stability_spectrum"] = "BLOCKED_EXTERNAL_SOLVER"
    gates["orbit_resolved_alpha_transport"] = "BLOCKED_EXTERNAL_SOLVER"
    gates["qualified_neutronics_tallies"] = "BLOCKED_EXTERNAL_SOLVER"
    gates["qualified_CFD_CHT"] = "BLOCKED_EXTERNAL_SOLVER"
    gates["qualified_CHF"] = "BLOCKED_EXTERNAL_SOLVER"
    gates["confinement_feasibility_screen_pass"] = bool(
        gates["equilibrium_numerical_pass"]
        and gates["ideal_MHD_proxy_pass"]
        and gates["profile_consistency_pass"]
        and gates["alpha_self_heating_pass"]
        and gates["tau_E_margin_pass"]
        and gates["reference_self_heating_reconciliation_pass"] is True)
    if bundle["source_status"] != "BUNDLE_INPUTS_VERIFIED":
        overall = "INPUT_BLOCKED"
    elif not gates["confinement_feasibility_screen_pass"]:
        overall = "SCREENING_FAIL_REVISE"
    elif gates["coolant_screen_pass"] is not True:
        overall = "SCREENING_FAIL_REVISE"
    else:
        overall = "SCREENING_PASS_WITH_EXTERNAL_BLOCKERS"

    uncertainty_summary, uncertainty_x, uncertainty_y = uncertainty_sweep(
        config, eq_metrics, conf_metrics, gates, output / "uncertainty",
        cases=cases, seed=seed)
    plot_status = make_plots(
        output, grid, field_arrays, uncertainty_x, uncertainty_y)
    write_json(output / "equilibrium_metrics.json", eq_metrics)
    write_json(output / "confinement_metrics.json", conf_metrics)
    write_json(output / "coolant_summary.json", coolant_summary)
    write_json(output / "profile_consistency.json", profile_metrics)
    write_json(output / "gate_results.json", gates)
    np.savez_compressed(
        output / "equilibrium_fields.npz",
        R=grid["R"], Z=grid["Z"], rho=grid["rho"], psi=field_arrays["psi"],
        pressure=field_arrays["pressure"], BR=field_arrays["BR"],
        BZ=field_arrays["BZ"], BPHI=field_arrays["BPHI"],
        JPHI=field_arrays["JPHI"])
    manifest = {
        "runner_version": VERSION,
        "model_version": MODEL_VERSION,
        "label": label,
        "started_utc": utc_now(),
        "elapsed_s": time.time() - started,
        "overall_status": overall,
        "input_source_status": bundle["source_status"],
        "input_root": bundle["input_root"],
        "input_files": bundle["files"],
        "input_audit": bundle["input_audit"],
        "config": config,
        "Bosch_Hale_DT": BH_DT,
        "profile_metrics": profile_metrics,
        "equilibrium_metrics": eq_metrics,
        "confinement_metrics": conf_metrics,
        "coolant_summary": coolant_summary,
        "uncertainty_summary": uncertainty_summary,
        "gates": gates,
        "plots": plot_status,
        "limitations": [
            "Fixed-boundary axisymmetric Grad-Shafranov solve; no free-boundary coil fit.",
            "B0 plasma field, tau_E, alpha deposition, and coolant properties are explicit screening assumptions.",
            "q95 and beta_N are cylindrical/normalized proxies, not stability eigenvalue results.",
            "D-T reaction rate uses a Maxwellian Bosch-Hale fit; no kinetic or orbit-resolved transport.",
            "The recorded reference-condition self-heating correction is compared to the current profile and is never substituted for it.",
            "The coolant calculation uses constant properties and a screening heat-transfer correlation.",
            "No DAGMC/OpenMC nuclear-data transport, CFD/CHT, or qualified CHF correlation was run.",
        ],
        "status": "SCREENING_ARTIFACT_NOT_ENGINEERING_VALIDATION",
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def zip_directory(root, destination=None):
    root = Path(root).resolve()
    destination = Path(destination).resolve() if destination else root.with_suffix(".zip")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as handle:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.resolve() != destination:
                handle.write(path, path.relative_to(root).as_posix())
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default=None,
                        help="Path to provisional_inputs, or let the script discover it.")
    parser.add_argument("--output-root", default="tomahawk_rev24_screen")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--full-only", action="store_true")
    parser.add_argument("--smoke-cases", type=int, default=256)
    parser.add_argument("--full-cases", type=int, default=65536)
    parser.add_argument("--seed", type=int, default=20260905)
    parser.add_argument("--nr", type=int, default=161)
    parser.add_argument("--nz", type=int, default=161)
    parser.add_argument("--gs-iters", type=int, default=12000)
    parser.add_argument("--b0-t", type=float, default=DEFAULTS["B0_plasma_T"])
    parser.add_argument("--tau-e-s", type=float, default=DEFAULTS["tau_E_s"])
    parser.add_argument("--alpha-deposition", type=float,
                        default=DEFAULTS["alpha_deposition_fraction"])
    parser.add_argument("--auxiliary-absorbed-mw", type=float,
                        default=DEFAULTS["auxiliary_absorbed_MW"])
    args = parser.parse_args(argv)
    if args.smoke_only and args.full_only:
        parser.error("--smoke-only and --full-only are mutually exclusive")
    root = Path(args.output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    overrides = {
        "B0_plasma_T": args.b0_t,
        "tau_E_s": args.tau_e_s,
        "alpha_deposition_fraction": args.alpha_deposition,
        "auxiliary_absorbed_MW": args.auxiliary_absorbed_mw,
    }
    results = {}
    try:
        if not args.full_only:
            results["smoke"] = run_native_screen(
                input_root=args.input_root, output_root=root / "smoke",
                label="smoke", cases=args.smoke_cases, seed=args.seed,
                nr=args.nr, nz=args.nz, max_gs_iters=args.gs_iters,
                overrides=overrides)
        if not args.smoke_only:
            results["full"] = run_native_screen(
                input_root=args.input_root, output_root=root / "full",
                label="full", cases=args.full_cases, seed=args.seed + 1,
                nr=args.nr, nz=args.nz, max_gs_iters=args.gs_iters,
                overrides=overrides)
    except InputBlockedError as exc:
        blocked = {
            "runner_version": VERSION,
            "created_utc": utc_now(),
            "results": {},
            "status": "INPUT_BLOCKED",
            "reason": str(exc),
            "exit_code": 3,
        }
        write_json(root / "run_manifest.json", blocked)
        archive = zip_directory(root)
        blocked["bundle_zip"] = str(archive)
        write_json(root / "run_manifest.json", blocked)
        print(json.dumps(json_safe(blocked), indent=2, allow_nan=False))
        return blocked["exit_code"]
    run_pass = all(
        result["overall_status"] == "SCREENING_PASS_WITH_EXTERNAL_BLOCKERS"
        and result["gates"]["input_bundle_verified"] is True
        and result["gates"]["confinement_feasibility_screen_pass"] is True
        and result["gates"]["coolant_screen_pass"] is True
        for result in results.values())
    summary = {
        "runner_version": VERSION,
        "created_utc": utc_now(),
        "results": {
            label: {
                "overall_status": result["overall_status"],
                "confinement_feasibility_screen_pass": result["gates"][
                    "confinement_feasibility_screen_pass"],
                "coolant_screen_pass": result["gates"]["coolant_screen_pass"],
                "full_reduced_screen_pass_percent": result[
                    "uncertainty_summary"]["all_gate_pass_percent"],
                "output": str((root / label).resolve()),
            }
            for label, result in results.items()
        },
        "status": (
            "NATIVE_SCREEN_COMPLETE_EXTERNAL_VALIDATION_STILL_REQUIRED"
            if run_pass else "NATIVE_SCREEN_FAIL_REVISE"),
        "exit_code": 0 if run_pass else 2,
    }
    write_json(root / "run_manifest.json", summary)
    archive = zip_directory(root)
    summary["bundle_zip"] = str(archive)
    write_json(root / "run_manifest.json", summary)
    print(json.dumps(json_safe(summary), indent=2, allow_nan=False))
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
