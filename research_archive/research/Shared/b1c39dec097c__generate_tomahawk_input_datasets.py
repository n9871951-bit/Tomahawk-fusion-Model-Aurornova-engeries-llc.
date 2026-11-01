#!/usr/bin/env python3
"""Generate one auditable, provisional Tomahawk multiphysics input bundle.

This script creates *inputs and sweep rows*, not solver output.  Values that
come from the Rev1.7 contract are marked CONTRACT; screening values selected
by this script are marked PROVISIONAL.  Unknown quantities (coil currents,
isotopic cards, cross sections, volume meshes, and local heat-flux fields) are
left as REQUIRED rather than invented.

The output can be copied into one CAD_A2 results folder and then wired into
``tomahawk_multiphysics_run.py``.  External solvers still have to be installed
and configured before the runner will launch them.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path


VERSION = "INPUT-DATA-GENERATOR-1.0"
MODEL_VERSION = "CAD-A2-WHOLE-CONCEPT-1.7-MULTIPHYSICS-DOMAINS"
DEFAULT_BUILD_REPORT = Path(__file__).resolve().parents[1] / "upload" / "build_report(6).json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows, fieldnames) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        count = 0
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def load_build_report(path: Path | None):
    if path is None or not path.is_file():
        return {}, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except (OSError, ValueError):
        return {}, path


def contract_values():
    # Values are copied from full_model_source.PHYSICS_BASELINE and SETTINGS.
    # They are intentionally kept here so this generator has no import-time
    # dependency on FreeCAD.
    return {
        "coolant_pressure_Pa": 7.0e6,
        "coolant_inlet_temperature_K": 348.15,
        "velocity_min_m_s": 3.5,
        "velocity_max_m_s": 4.5,
        "bulk_rise_min_K": 17.5,
        "bulk_rise_max_K": 25.0,
        "pressure_drop_limit_Pa": 1.0e5,
        "CuCrZr_temperature_limit_K": 573.15,
        "minimum_DNBR": 1.30,
        "major_radius_m": 7.5,
        "reference_volume_m3": 950.0,
        "central_ion_temperature_keV": 22.0,
        "central_electron_temperature_keV": 18.0,
        "magnetic_field_T": 35.0,
        "rf_channels": 128,
        "rf_channel_side_m": 0.016,
        "rf_front_skin_m": 0.0025,
        "rf_width_m": 1.079,
        "rf_height_m": 2.318,
    }


def material_names(build_report) -> list[str]:
    names = set()
    exported = build_report.get("multiphysics_exports", {}).get("files", {})
    for filename in exported:
        prefix = "NEUTRONICS_MATERIAL_"
        if filename.startswith(prefix) and filename.endswith(".step"):
            names.add(filename[len(prefix):-5])
    if not names:
        # Fallback mirrors the material labels in the Rev1.7 CAD source.  No
        # densities or isotopic compositions are inferred from these labels.
        names.update({
            "ALLOY_UNQUALIFIED", "AlN", "BRAZE_UNQUALIFIED", "CONCRETE",
            "CONDUCTOR_UNQUALIFIED", "CONDUCTOR_UNSPECIFIED", "CuCrZr",
            "DUCT_ALLOY_UNQUALIFIED", "HEADER_ALLOY_UNQUALIFIED", "HELIUM",
            "HELIUM_PIPE", "HOUSING_ALLOY_UNQUALIFIED", "HT_FLUID_UNSPECIFIED",
            "HT_LOOP_PIPE", "Mo", "MoCu_GRADED", "ODS_FeCrAl",
            "OPTICAL_MATERIAL_UNQUALIFIED", "PIPE_ALLOY_UNQUALIFIED",
            "S20_AQUEOUS_EV010", "S20_LOOP_PIPE", "SHIELD_UNSPECIFIED",
            "SLEEVE_ALLOY_UNQUALIFIED", "STAINLESS_STEEL", "STEEL",
            "STRUCTURAL_ALLOY_UNQUALIFIED", "STRUCTURAL_STEEL",
            "SUPPORT_ALLOY_UNQUALIFIED", "THERMAL_SHIELD_UNSPECIFIED", "W",
            "WATER", "WATER_LOOP_PIPE",
        })
    return sorted(names)


def generate_mhd(out: Path, c: dict) -> dict:
    stage = out / "MHD"
    stage.mkdir(parents=True, exist_ok=True)
    profile_rows = []
    # A smooth screening profile is useful for a parser/preflight, but it is
    # not an equilibrium solution.  The stage metadata says so explicitly.
    for i in range(11):
        rho = i / 10.0
        te = max(0.25, c['central_electron_temperature_keV'] * (1.0-rho*rho))
        ti = max(0.30, c['central_ion_temperature_keV'] * (1.0-rho*rho))
        density = max(1.0e18, 1.10e20 * (1.0-0.65*rho*rho))
        # Screening-only ideal two-temperature pressure closure.  This keeps
        # the generated row internally consistent without claiming equilibrium.
        pressure = density * 1.602176634e-16 * (te + ti)
        profile_rows.append({
            "normalized_flux": f"{rho:.3f}",
            "pressure_Pa": f"{pressure:.6g}",
            "electron_temperature_keV": f"{te:.6g}",
            "ion_temperature_keV": f"{ti:.6g}",
            "density_m3": f"{density:.6g}",
            "value_status": "PROVISIONAL_IDEAL_TWO_TEMPERATURE_SCREENING_PROFILE",
        })
    profile_path = stage / "mhd_profile_sweep.csv"
    profile_fields = ["normalized_flux", "pressure_Pa", "electron_temperature_keV",
                      "ion_temperature_keV", "density_m3", "value_status"]
    count = write_csv(profile_path, profile_rows, profile_fields)

    coils = []
    for i in range(16):
        coils.append({
            "coil_id": f"C{i+1:02d}",
            "toroidal_angle_deg": f"{(360.0*i/16.0):.6f}",
            "current_A": "REQUIRED_FROM_COIL_DESIGN",
            "turn_count": "REQUIRED_FROM_COIL_DESIGN",
            "cross_section_m": "REQUIRED_FROM_CAD_WINDING_SECTION",
            "value_status": "REQUIRED_NOT_INFERRED",
        })
    coil_path = stage / "mhd_coil_table.csv"
    coil_fields = ["coil_id", "toroidal_angle_deg", "current_A", "turn_count",
                   "cross_section_m", "value_status"]
    count += write_csv(coil_path, coils, coil_fields)

    input_json = {
        "schema_version": "TOMAHAWK-MHD-INPUT-1.0",
        "case_id": "REV1_7_PROVISIONAL_MHD_SCREEN",
        "model_version": MODEL_VERSION,
        "data_status": "PROVISIONAL_INPUTS_NOT_EQUILIBRIUM_RESULT",
        "geometry": {
            "plasma_domain_step": "../Solver_Geometry/MHD_Plasma_Domain.step",
            "vacuum_region_step": "../Solver_Geometry/MHD_Vacuum_Region.step",
            "coil_regions_step": "../Solver_Geometry/MHD_Coil_And_Casing_Regions.step",
            "units": "m in solver; STEP source is mm",
        },
        "equilibrium_route": "VMEC_FREE_BOUNDARY_OR_QUALIFIED_EQUIVALENT",
        "coil_table": "mhd_coil_table.csv",
        "profiles": "mhd_profile_sweep.csv",
        "screening_parameters": {
            "major_radius_m": c["major_radius_m"],
            "reference_volume_m3": c["reference_volume_m3"],
            "central_ion_temperature_keV": c["central_ion_temperature_keV"],
            "central_electron_temperature_keV": c["central_electron_temperature_keV"],
            "magnetic_field_target_T": c["magnetic_field_T"],
        },
        "required_before_solver": [
            "coil current by conductor and turn",
            "free-boundary mgrid/MAKEGRID input",
            "pressure, density, Ti, Te profiles from a specified source",
            "resistivity, viscosity, and transport closure",
            "initial perturbation spectrum and time-step/convergence plan",
        ],
    }
    input_path = stage / "mhd_input.json"
    write_json(input_path, input_json)
    return {"files": [profile_path, coil_path, input_path], "rows": count}


def generate_neutronics(out: Path, c: dict, build_report) -> dict:
    stage = out / "NEUTRONICS"
    stage.mkdir(parents=True, exist_ok=True)
    exported = build_report.get("multiphysics_exports", {}).get("files", {})
    rows = []
    for name in material_names(build_report):
        filename = f"NEUTRONICS_MATERIAL_{name}.step"
        rows.append({
            "material_id": name,
            "cad_step": f"../Solver_Geometry/{filename}" if filename in exported else "REQUIRED_CAD_EXPORT",
            "composition": "REQUIRED_ISOTOPIC_COMPOSITION",
            "density_g_cm3": "REQUIRED_TEMPERATURE_DEPENDENT_DENSITY",
            "temperature_K": f"{c['coolant_inlet_temperature_K']:.2f}" if name in {"WATER", "WATER_LOOP_PIPE"} else "REQUIRED",
            "li6_enrichment": "REQUIRED_IF_BREEDING_MATERIAL",
            "cross_section_library": "REQUIRED_EVALUATED_NUCLEAR_DATA",
            "value_status": "CAD_LABEL_ONLY_MATERIAL_CARD_REQUIRED",
        })
    material_path = stage / "material_region_map.csv"
    material_fields = ["material_id", "cad_step", "composition", "density_g_cm3",
                       "temperature_K", "li6_enrichment", "cross_section_library",
                       "value_status"]
    count = write_csv(material_path, rows, material_fields)

    source_rows = []
    for scenario, scale in (("nominal", 1.0), ("low", 0.5), ("high", 1.5)):
        source_rows.append({
            "source_case": scenario,
            "particle_energy_eV": "14100000",
            "source_strength_scale": f"{scale:.3f}",
            "spatial_distribution": "REQUIRED_FROM_MHD_OR_SOURCE_MODEL",
            "angular_distribution": "REQUIRED_FROM_SOURCE_MODEL",
            "normalization": "per_source_particle_until_power_is_declared",
            "value_status": "PROVISIONAL_SCENARIO_SCALE",
        })
    source_path = stage / "source_sweep.csv"
    source_fields = ["source_case", "particle_energy_eV", "source_strength_scale",
                     "spatial_distribution", "angular_distribution", "normalization",
                     "value_status"]
    count += write_csv(source_path, source_rows, source_fields)

    write_json(stage / "openmc_input_manifest.json", {
        "schema_version": "TOMAHAWK-OPENMC-INPUT-MANIFEST-1.0",
        "data_status": "PROVISIONAL_MANIFEST_DAGMC_AND_MATERIAL_CARDS_REQUIRED",
        "dagmc_geometry": "../Solver_Geometry/Tomahawk_reactor_CONCEPT_FULL.h5m",
        "material_region_map": "material_region_map.csv",
        "source_sweep": "source_sweep.csv",
        "settings": {
            "run_mode": "fixed source",
            "particles": 100000,
            "batches": 100,
            "inactive": 0,
            "value_status": "PROVISIONAL_CONVERGENCE_STARTING_POINT",
        },
        "required_before_solver": [
            "watertight imprinted DAGMC h5m",
            "OpenMC materials.xml with isotope cards and densities",
            "cross_sections.xml pointing to an evaluated data library",
            "source spatial/angular distribution",
            "tally definitions for heating, TBR, dpa, helium, and spectra",
        ],
    })
    return {"files": [material_path, source_path, stage / "openmc_input_manifest.json"], "rows": count}


def darcy_screening_dp(rho: float, velocity: float, diameter: float,
                       length: float = 2.318, roughness: float = 1.0e-5,
                       mu: float = 3.5e-4) -> tuple[float, float]:
    """Return a screening-only Darcy pressure drop and Reynolds number."""
    re = rho * velocity * diameter / mu
    if re <= 0.0:
        return 0.0, re
    # Swamee-Jain explicit approximation; not a substitute for CFD.
    friction = 0.25 / math.log10(roughness / (3.7 * diameter) + 5.74 / re**0.9)**2
    dp = friction * (length / diameter) * rho * velocity**2 / 2.0
    return dp, re


def generate_cfd(out: Path, c: dict) -> dict:
    stage = out / "CFD"
    stage.mkdir(parents=True, exist_ok=True)
    rows = []
    case_id = 0
    heat_flux_scenarios = (("transport_screen", 0.650e6),
                           ("layer_screen", 0.772e6),
                           ("full_incident_stress", 4.000e6))
    for n, diameter, velocity, skin, rise, scenario in itertools.product(
            (112, 128, 144, 160), (0.014, 0.016, 0.018), (3.5, 4.0, 4.5),
            (0.002, 0.0025, 0.003), (17.5, 21.25, 25.0), heat_flux_scenarios):
        case_id += 1
        flow_area = n * diameter * diameter
        rho = 997.0  # screening constant only; replace with property table.
        mass_flow = rho * velocity * flow_area
        dp, reynolds = darcy_screening_dp(rho, velocity, diameter)
        rows.append({
            "case_id": f"CFD_{case_id:05d}",
            "channel_count": n,
            "hydraulic_diameter_m": f"{diameter:.6f}",
            "velocity_m_s": f"{velocity:.6f}",
            "CuCrZr_skin_thickness_m": f"{skin:.6f}",
            "pressure_Pa": f"{c['coolant_pressure_Pa']:.3f}",
            "inlet_temperature_K": f"{c['coolant_inlet_temperature_K']:.3f}",
            "allowed_bulk_rise_K": f"{rise:.3f}",
            "heat_flux_scenario": scenario[0],
            "local_heat_flux_W_m2": f"{scenario[1]:.6g}",
            "flow_area_m2": f"{flow_area:.9g}",
            "screening_mass_flow_kg_s": f"{mass_flow:.9g}",
            "screening_Reynolds": f"{reynolds:.9g}",
            "screening_Darcy_pressure_drop_Pa": f"{dp:.9g}",
            "pressure_drop_limit_Pa": f"{c['pressure_drop_limit_Pa']:.3f}",
            "CuCrZr_temperature_limit_K": f"{c['CuCrZr_temperature_limit_K']:.3f}",
            "value_status": "PROVISIONAL_SCREENING_ROW_NOT_CFD_RESULT",
        })
    fields = list(rows[0].keys())
    sweep_path = stage / "cfd_cht_parameter_sweep.csv"
    count = write_csv(sweep_path, rows, fields)
    write_json(stage / "cfd_case_manifest.json", {
        "schema_version": "TOMAHAWK-CFD-CHT-INPUT-MANIFEST-1.0",
        "data_status": "PROVISIONAL_SWEEP_MESH_REQUIRED",
        "solid_geometry": "../Solver_Geometry/CFD_RF_Cassette_Solid_Regions.step",
        "coolant_geometry": "../Solver_Geometry/CFD_RF_Connected_Coolant_Domains.step",
        "boundary_seed_file": "../Solver_Geometry/CFD_RF_Named_Boundary_Seeds.json",
        "sweep_csv": "cfd_cht_parameter_sweep.csv",
        "property_model": "REQUIRED_TEMPERATURE_AND_PRESSURE_DEPENDENT_WATER_PROPERTIES",
        "screening_assumptions": {
            "constant_density_kg_m3": 997.0,
            "dynamic_viscosity_Pa_s": 3.5e-4,
            "roughness_m": 1.0e-5,
            "heated_length_m": 2.318,
            "note": "Only for row generation and parser checks; do not report as CFD output.",
        },
        "required_before_solver": [
            "watertight volume mesh with named boundaries",
            "temperature/pressure-dependent fluid properties",
            "transport or volumetric heat source field",
            "solid thermal properties and interface conditions",
            "three-level mesh and time-step convergence plan",
        ],
    })
    return {"files": [sweep_path, stage / "cfd_case_manifest.json"], "rows": count}


def generate_chf(out: Path, c: dict) -> dict:
    stage = out / "CHF"
    stage.mkdir(parents=True, exist_ok=True)
    input_json = {
        "schema_version": "TOMAHAWK-CHF-INPUT-1.0",
        "case_id": "REV1_7_PROVISIONAL_CHF_POSTPROCESS",
        "data_status": "PROVISIONAL_BOUNDARY_CONDITIONS_CORRELATION_NOT_SELECTED",
        "correlation": "REQUIRED_APPLICABILITY_QUALIFIED_CORRELATION_OR_LUT",
        "upstream_cfd_csv": "../CFD/cfd_cht_parameter_sweep.csv",
        "required_local_fields": {
            "pressure_Pa": "REQUIRED_FROM_CFD",
            "mass_flux_kg_m2_s": "REQUIRED_FROM_CFD",
            "quality": "REQUIRED_FROM_CFD",
            "heated_length_m": "REQUIRED_FROM_GEOMETRY",
            "hydraulic_diameter_m": "REQUIRED_FROM_MESH",
            "local_heat_flux_W_m2": "REQUIRED_FROM_CFD_OR_TRANSPORT",
        },
        "acceptance": {
            "minimum_DNBR": c["minimum_DNBR"],
            "maximum_CuCrZr_temperature_K": c["CuCrZr_temperature_limit_K"],
            "maximum_pressure_drop_Pa": c["pressure_drop_limit_Pa"],
        },
        "required_before_solver": [
            "select a correlation or LUT after checking pressure, mass flux, quality, geometry, and heated length applicability",
            "supply local CFD heat flux/state fields",
            "report uncertainty and correlation validity range",
        ],
    }
    path = stage / "chf_input.json"
    write_json(path, input_json)
    return {"files": [path], "rows": 1}


def generate_config(out: Path) -> Path:
    config = {
        "schema_version": "TOMAHAWK-CONTINUOUS-1.0",
        "purpose": "Generated one-folder wiring for the provisional input bundle; commands remain null until real solvers are selected.",
        "stages": {
            "MHD": {
                "command": None,
                "inputs": {"mhd_input": "provisional_inputs/MHD/mhd_input.json"},
                "outputs": ["mhd_output.json", "wout_*.nc", "mhd_output.h5"],
                "consumes_previous_output": False,
            },
            "NEUTRONICS": {
                "command": None,
                "inputs": {
                    "dagmc": "provisional_inputs/NEUTRONICS/dagmc.h5m",
                    "materials": "provisional_inputs/NEUTRONICS/materials.xml",
                    "settings": "provisional_inputs/NEUTRONICS/settings.xml",
                    "cross_sections": "provisional_inputs/NEUTRONICS/cross_sections.xml",
                },
                "outputs": ["statepoint*.h5", "neutronics_output.json", "tallies*.json"],
                "consumes_previous_output": True,
            },
            "CFD": {
                "command": None,
                "inputs": {"cfd_mesh": "provisional_inputs/CFD/cassette.re2", "cfd_case": "provisional_inputs/CFD/cassette.par"},
                "outputs": ["cfd_output.json", "*.vtu", "*.vtk", "*.csv"],
                "consumes_previous_output": True,
            },
            "CHF": {
                "command": None,
                "inputs": {"chf_results": "provisional_inputs/CHF/chf_input.json"},
                "outputs": ["chf_results.json", "chf_results.csv"],
                "consumes_previous_output": True,
            },
        },
        "note": "Do not run until null commands and REQUIRED files are replaced with real solver executables and data.",
    }
    path = out / "Tomahawk_Continuous_Run_Config.provisional.json"
    write_json(path, config)
    return path


def generate_bundle(output: Path, build_report_path: Path | None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    build_report, report_path = load_build_report(build_report_path)
    c = contract_values()
    mhd = generate_mhd(output, c)
    neutronics = generate_neutronics(output, c, build_report)
    cfd = generate_cfd(output, c)
    chf = generate_chf(output, c)
    config_path = generate_config(output)

    metadata = {
        "generator_version": VERSION,
        "model_version": MODEL_VERSION,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_status": "PROVISIONAL_INPUTS_GENERATED_NOT_SOLVER_RESULTS",
        "build_report_used": str(report_path.resolve()) if report_path else None,
        "build_report_sha256": sha256(report_path) if report_path else None,
        "contract_values": c,
        "datasets": {
            "MHD": {"rows": mhd["rows"]},
            "NEUTRONICS": {"rows": neutronics["rows"]},
            "CFD": {"rows": cfd["rows"]},
            "CHF": {"rows": chf["rows"]},
        },
        "provenance": {
            "CONTRACT": [
                "coolant baseline and G1 geometry dimensions from Rev1.7 contract",
                "acceptance thresholds from Tomahawk_Multiphysics_Physics_Contract.json",
            ],
            "PROVISIONAL": [
                "smooth MHD screening profile using ideal two-temperature pressure closure",
                "MHD source/coil placeholders",
                "CFD sweep values and screening Darcy estimates",
                "neutronics source scale scenarios",
            ],
            "REQUIRED": [
                "coil currents and mgrid",
                "equilibrium profiles and perturbation spectrum",
                "DAGMC h5m, isotope cards, and cross-section library",
                "CFD volume mesh and transport heat source",
                "CHF correlation/LUT and local CFD fields",
            ],
        },
        "runner_note": "This bundle does not create solver outputs. The fail-closed continuous runner must remain blocked until real executables and required files are supplied.",
    }
    file_records = {}
    for path in sorted(output.rglob("*")):
        if (path.is_file() and path.name != "dataset_manifest.json"
                and path.suffix.lower() != ".zip"):
            file_records[path.relative_to(output).as_posix()] = sha256(path)
    metadata["files"] = file_records
    write_json(output / "dataset_manifest.json", metadata)
    # The ZIP is a convenience handoff.  It is intentionally not included in
    # its own hash manifest, so regenerating it cannot create a hash cycle.
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path != archive:
                handle.write(path, path.relative_to(output).as_posix())
    metadata["bundle_zip"] = str(archive)
    return metadata


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-folder", type=Path, required=True,
                        help="Folder in which MHD/NEUTRONICS/CFD/CHF datasets are created.")
    parser.add_argument("--build-report", type=Path, default=None,
                        help="Optional CAD_A2 build_report.json used for material filenames.")
    args = parser.parse_args(argv)
    build_report = args.build_report
    if build_report is None and DEFAULT_BUILD_REPORT.is_file():
        build_report = DEFAULT_BUILD_REPORT
    metadata = generate_bundle(args.output_folder.resolve(), build_report)
    print(json.dumps({
        "output_folder": str(args.output_folder.resolve()),
        "data_status": metadata["data_status"],
        "datasets": metadata["datasets"],
        "manifest": str((args.output_folder.resolve() / "dataset_manifest.json")),
        "bundle_zip": metadata.get("bundle_zip"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
