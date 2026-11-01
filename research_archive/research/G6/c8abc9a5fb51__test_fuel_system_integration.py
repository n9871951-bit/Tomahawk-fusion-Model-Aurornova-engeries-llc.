#!/usr/bin/env python3
"""Tests for the Rev1.7 fuel-system handoff.

These are accounting and orchestration tests. They do not run VMEC, OpenMC,
NekRS, a CHF solver, or a physical MHD calculation.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path
import sys

import tomahawk_multiphysics_run as runner
from tomahawk_fuel_system_foundation_adapter import self_test as foundation_self_test
from tomahawk_fuel_system_stage import InputBlocked, load_realized_neutronics, run as run_stage


def synthetic_case() -> dict:
    return {
        "case_id": "SYNTHETIC_MHD_HANDOFF_TEST_ONLY",
        "time": {"dt_s": 1.0, "horizon_s": 5.0},
        "nuclear_source": {
            "source_status": "REQUIRED_FROM_3D_NEUTRONICS",
            "tbr": None,
            "reaction_rate_s": None,
            "tritium_bred_kg_s": None,
        },
        "dle": {
            "feedstock": "DESALINATION_REJECT_BRINE",
            "brine_flow_m3_s": 1.0,
            "brine_density_kg_m3": 1100.0,
            "li_concentration_ppm": 0.5,
            "recovery_per_pass": 0.8,
        },
        "alsb": {
            "salt_case": "LiOH",
            "medium": "AQUEOUS",
            "hto_capture_efficiency": 0.98,
            "design_tbr_floor": 1.05,
        },
        "cece_lpce": {
            "alsb_slipstream_fraction": 1.0,
            "lpce_temperature_C": {"min": 40.0, "max": 80.0},
            "tritium_lpce_transfer_efficiency": 0.98,
            "deuterium_lpce_transfer_efficiency": 0.98,
            "lpce_delay_s": 1.0,
            "auxiliary_power_W": 100000.0,
            "process_heat_W": 200000.0,
        },
        "pem": {
            "deuterium_feed_to_pem_kg_s": 5.0e-7,
            "tritium_product_recovery_efficiency": 0.98,
            "deuterium_product_recovery_efficiency": 0.98,
            "pem_delay_s": 1.0,
            "auxiliary_power_W": 200000.0,
            "process_heat_W": 300000.0,
        },
        "fuel_return": {
            "product_species": "D2_T2_MIXTURE",
            "tritium_product_purity": 0.99,
            "deuterium_product_purity": 0.99,
            "direct_to_ignition": True,
        },
        "inventory": {
            "initial_kg": {"D": 1.0, "T": 1.0},
            "reserve_kg": {"D": 0.0, "T": 0.0},
            "permeation_loss_kg_s": {"T": 0.0},
            "other_loss_kg_s": {"D": 0.0, "T": 0.0},
        },
    }


def test_foundation_accounting() -> None:
    result = foundation_self_test()
    assert result["self_test"] == "PASS"


def test_realized_neutronics_handoff_and_stage() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        case_path = root / "case.json"
        neutronics_path = root / "neutronics_output.json"
        output_path = root / "fuel_system_output.json"
        case_path.write_text(json.dumps(synthetic_case()), encoding="utf-8")
        neutronics_path.write_text(json.dumps({
            "realized_TBR": 1.20,
            "reaction_rate_s": 1.0e20,
            "handoff_status": "NATIVE_NEUTRONICS_JSON",
        }), encoding="utf-8")
        handoff = load_realized_neutronics(neutronics_path)
        assert handoff["tbr"] == 1.20
        assert handoff["reaction_rate_s"] == 1.0e20
        assert run_stage(case_path, neutronics_path, output_path) == 0
        result = json.loads(output_path.read_text(encoding="utf-8"))
        assert result["status"] == "CALCULATED_REDUCED_ORDER_NOT_VALIDATED"
        assert result["provenance"]["handoff_status"] == "REALIZED_NEUTRONICS_JSON_CONSUMED"
        assert result["product_interface"]["T2_mass_in_product_kg_s"] > 0.0


def test_missing_realized_neutronics_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "neutronics_output.json"
        path.write_text(json.dumps({"tbr": 1.2}), encoding="utf-8")
        try:
            load_realized_neutronics(path)
        except InputBlocked:
            pass
        else:
            raise AssertionError("missing reaction rate was not blocked")


def test_runner_preflight_contract() -> None:
    assert runner.STAGES == ("MHD", "NEUTRONICS", "FUEL_SYSTEM", "CFD", "CHF")
    assert "fuel_system_output.json" in runner.DEFAULT_OUTPUTS["FUEL_SYSTEM"]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "Solver_Geometry").mkdir()
        for name in (
            "MHD_Plasma_Domain.step",
            "MHD_Vacuum_Region.step",
            "MHD_Coil_And_Casing_Regions.step",
            "NEUTRONICS_Material_To_STEP_Map.json",
            "CFD_RF_Connected_Coolant_Domains.step",
            "CFD_RF_Cassette_Solid_Regions.step",
            "CFD_RF_Named_Boundary_Seeds.json",
        ):
            (root / "Solver_Geometry" / name).write_text("fixture", encoding="utf-8")
        (root / "Tomahawk_Multiphysics_Physics_Contract.json").write_text("{}", encoding="utf-8")
        (root / "build_report.json").write_text(json.dumps({
            "native_execution": "COMPLETED_CONCEPT_BUILD_BOUNDARY_G1_NUMERICAL_PASS",
            "assembly_build_accepted": True,
            "failed": [],
            "g1_audit": {"status": "PASS"},
        }), encoding="utf-8")
        for relative in (
            "MHD/input.toml", "NEUTRONICS/dagmc.h5m", "NEUTRONICS/materials.xml",
            "NEUTRONICS/settings.xml", "NEUTRONICS/cross_sections.xml",
            "FUEL_CYCLE/tomahawk_fuel_system_foundation.json",
            "CFD/cassette.re2", "CFD/cassette.par", "CHF/chf_input.json",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture", encoding="utf-8")
        config_path = root / "Tomahawk_Continuous_Run_Config.json"
        command = [sys.executable, "-c", "print('fixture command')"]
        config = {
            "stages": {
                "MHD": {"command": command, "inputs": {"mhd_input": "MHD/input.toml"}, "outputs": ["mhd_output.json"]},
                "NEUTRONICS": {"command": command, "inputs": {"dagmc": "NEUTRONICS/dagmc.h5m", "materials": "NEUTRONICS/materials.xml", "settings": "NEUTRONICS/settings.xml", "cross_sections": "NEUTRONICS/cross_sections.xml"}, "outputs": ["neutronics_output.json"]},
                "FUEL_SYSTEM": {"command": [sys.executable, str(Path(__file__).with_name("tomahawk_fuel_system_stage.py")), "{fuel_system_input}", "--previous-output", "{previous_output}", "--output", "{stage_dir}/fuel_system_output.json"], "inputs": {"fuel_system_input": "FUEL_CYCLE/tomahawk_fuel_system_foundation.json"}, "outputs": ["fuel_system_output.json"]},
                "CFD": {"command": command, "inputs": {"cfd_mesh": "CFD/cassette.re2", "cfd_case": "CFD/cassette.par"}, "outputs": ["cfd_output.json"]},
                "CHF": {"command": command, "inputs": {"chf_results": "CHF/chf_input.json"}, "outputs": ["chf_results.json"]},
            }
        }
        config_path.write_text(json.dumps(config), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = runner.main(["--results-folder", str(root), "--config", str(config_path), "--preflight"])
        assert code == 0, stdout.getvalue()
        report = json.loads((root / "Tomahawk_Continuous_Run" / "physics_run_report.json").read_text(encoding="utf-8"))
        assert report["overall_status"] == "PREFLIGHT_COMPLETE_SOLVER_INPUTS_READY"
        assert list(report["stages"]) == ["MHD", "NEUTRONICS", "FUEL_SYSTEM", "CFD", "CHF"]


def test_runner_executes_fuel_stage_orchestration_only() -> None:
    """Run the pipeline with fixture commands, not physical solvers."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "Solver_Geometry").mkdir()
        for name in (
            "MHD_Plasma_Domain.step",
            "MHD_Vacuum_Region.step",
            "MHD_Coil_And_Casing_Regions.step",
            "NEUTRONICS_Material_To_STEP_Map.json",
            "CFD_RF_Connected_Coolant_Domains.step",
            "CFD_RF_Cassette_Solid_Regions.step",
            "CFD_RF_Named_Boundary_Seeds.json",
        ):
            (root / "Solver_Geometry" / name).write_text("fixture", encoding="utf-8")
        (root / "Tomahawk_Multiphysics_Physics_Contract.json").write_text("{}", encoding="utf-8")
        (root / "build_report.json").write_text(json.dumps({
            "native_execution": "COMPLETED_CONCEPT_BUILD_BOUNDARY_G1_NUMERICAL_PASS",
            "assembly_build_accepted": True,
            "failed": [],
            "g1_audit": {"status": "PASS"},
        }), encoding="utf-8")
        for relative in (
            "MHD/input.toml", "NEUTRONICS/dagmc.h5m", "NEUTRONICS/materials.xml",
            "NEUTRONICS/settings.xml", "NEUTRONICS/cross_sections.xml",
            "FUEL_CYCLE/tomahawk_fuel_system_foundation.json",
            "CFD/cassette.re2", "CFD/cassette.par", "CHF/chf_input.json",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(synthetic_case()) if path.suffix == ".json" else "fixture", encoding="utf-8")

        fake = root / "fixture_stage.py"
        fake.write_text(
            "import json, pathlib, sys\n"
            "stage=sys.argv[1]; output=pathlib.Path(sys.argv[2]); output.parent.mkdir(parents=True, exist_ok=True)\n"
            "value={'stage':stage}\n"
            "if stage=='NEUTRONICS': value.update({'realized_TBR':1.20,'reaction_rate_s':1.0e20})\n"
            "output.write_text(json.dumps(value), encoding='utf-8')\n",
            encoding="utf-8",
        )
        config = {
            "stages": {
                "MHD": {"command": [sys.executable, str(fake), "MHD", "{stage_dir}/mhd_output.json"], "inputs": {"mhd_input": "MHD/input.toml"}, "outputs": ["mhd_output.json"]},
                "NEUTRONICS": {"command": [sys.executable, str(fake), "NEUTRONICS", "{stage_dir}/neutronics_output.json"], "inputs": {"dagmc": "NEUTRONICS/dagmc.h5m", "materials": "NEUTRONICS/materials.xml", "settings": "NEUTRONICS/settings.xml", "cross_sections": "NEUTRONICS/cross_sections.xml"}, "outputs": ["neutronics_output.json"], "consumes_previous_output_via_manifest": True},
                "FUEL_SYSTEM": {"command": [sys.executable, str(Path(__file__).with_name("tomahawk_fuel_system_stage.py")), "{fuel_system_input}", "--previous-output", "{previous_output}", "--output", "{stage_dir}/fuel_system_output.json"], "inputs": {"fuel_system_input": "FUEL_CYCLE/tomahawk_fuel_system_foundation.json"}, "outputs": ["fuel_system_output.json"]},
                "CFD": {"command": [sys.executable, str(fake), "CFD", "{stage_dir}/cfd_output.json"], "inputs": {"cfd_mesh": "CFD/cassette.re2", "cfd_case": "CFD/cassette.par"}, "outputs": ["cfd_output.json"], "consumes_previous_output_via_manifest": True},
                "CHF": {"command": [sys.executable, str(fake), "CHF", "{stage_dir}/chf_results.json"], "inputs": {"chf_results": "CHF/chf_input.json"}, "outputs": ["chf_results.json"], "consumes_previous_output_via_manifest": True},
            }
        }
        config_path = root / "Tomahawk_Continuous_Run_Config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = runner.main(["--results-folder", str(root), "--config", str(config_path)])
        assert code == 0, stdout.getvalue()
        report = json.loads((root / "Tomahawk_Continuous_Run" / "physics_run_report.json").read_text(encoding="utf-8"))
        assert report["overall_status"] == "CONTINUOUS_PIPELINE_COMPLETE"
        assert report["completed_stages"] == ["MHD", "NEUTRONICS", "FUEL_SYSTEM", "CFD", "CHF"]
        fuel_output = root / "Tomahawk_Continuous_Run" / "03_FUEL_SYSTEM" / "fuel_system_output.json"
        fuel_result = json.loads(fuel_output.read_text(encoding="utf-8"))
        assert fuel_result["provenance"]["handoff_status"] == "REALIZED_NEUTRONICS_JSON_CONSUMED"
        assert fuel_result["claim_status"] == "ARCHITECTURE_INTEGRATED_NO_PERFORMANCE_CLAIM"


def main() -> int:
    tests = [
        test_foundation_accounting,
        test_realized_neutronics_handoff_and_stage,
        test_missing_realized_neutronics_is_blocked,
        test_runner_preflight_contract,
        test_runner_executes_fuel_stage_orchestration_only,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL FUEL-SYSTEM INTEGRATION TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
