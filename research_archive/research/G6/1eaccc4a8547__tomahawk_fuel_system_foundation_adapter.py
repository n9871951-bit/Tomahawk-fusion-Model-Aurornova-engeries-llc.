#!/usr/bin/env python3
"""Process-specific Tomahawk fuel-system adapter.

Maps the documented DLE -> ALSB -> CECE/LPCE -> PEM architecture into the
generic protected D-T fuel-cycle accounting adapter. The code exposes only
performance-level quantities and does not implement a chemical recipe.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping

from tomahawk_chemical_fuel_cycle_adapter import InputBlocked, simulate


SOURCE_SHA256 = "399fbf7373cba67f2e7f7d9a01ca9bb34eac7030a5789bc1a2be9822c41b1522"


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputBlocked(f"{path} must be a finite number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise InputBlocked(f"{path} must be finite")
    return result


def _fraction(value: Any, path: str) -> float:
    result = _number(value, path)
    if not 0.0 <= result <= 1.0:
        raise InputBlocked(f"{path} must be between 0 and 1")
    return result


def _required(mapping: Mapping[str, Any], key: str, path: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise InputBlocked(f"missing required input: {path}.{key}")
    return value


def compute_dle(case: Mapping[str, Any]) -> Dict[str, float]:
    dle = case["dle"]
    flow = _number(_required(dle, "brine_flow_m3_s", "dle"), "dle.brine_flow_m3_s")
    density = _number(_required(dle, "brine_density_kg_m3", "dle"), "dle.brine_density_kg_m3")
    li_ppm = _number(_required(dle, "li_concentration_ppm", "dle"), "dle.li_concentration_ppm")
    recovery = _fraction(_required(dle, "recovery_per_pass", "dle"), "dle.recovery_per_pass")
    if flow < 0.0 or density <= 0.0 or li_ppm < 0.0:
        raise InputBlocked("DLE flow/density/concentration values are invalid")
    li_feed = flow * density * li_ppm * 1.0e-6
    return {
        "brine_flow_m3_s": flow,
        "li_feed_kg_s": li_feed,
        "li_recovered_kg_s": li_feed * recovery,
        "li_reject_kg_s": li_feed * (1.0 - recovery),
        "recovery_per_pass": recovery,
    }


def build_generic_case(case: Mapping[str, Any]) -> Dict[str, Any]:
    nuclear = case["nuclear_source"]
    alsb = case["alsb"]
    cece = case["cece_lpce"]
    pem = case["pem"]
    return_cfg = case["fuel_return"]
    inventory = case["inventory"]
    time_cfg = case["time"]

    slipstream = _fraction(
        _required(cece, "alsb_slipstream_fraction", "cece_lpce"),
        "cece_lpce.alsb_slipstream_fraction",
    )
    hto_capture = _fraction(
        _required(alsb, "hto_capture_efficiency", "alsb"),
        "alsb.hto_capture_efficiency",
    )
    t_lpce = _fraction(
        _required(cece, "tritium_lpce_transfer_efficiency", "cece_lpce"),
        "cece_lpce.tritium_lpce_transfer_efficiency",
    )
    d_lpce = _fraction(
        _required(cece, "deuterium_lpce_transfer_efficiency", "cece_lpce"),
        "cece_lpce.deuterium_lpce_transfer_efficiency",
    )
    t_pem = _fraction(
        _required(pem, "tritium_product_recovery_efficiency", "pem"),
        "pem.tritium_product_recovery_efficiency",
    )
    d_pem = _fraction(
        _required(pem, "deuterium_product_recovery_efficiency", "pem"),
        "pem.deuterium_product_recovery_efficiency",
    )
    t_purity = _fraction(
        _required(return_cfg, "tritium_product_purity", "fuel_return"),
        "fuel_return.tritium_product_purity",
    )
    d_purity = _fraction(
        _required(return_cfg, "deuterium_product_purity", "fuel_return"),
        "fuel_return.deuterium_product_purity",
    )
    d_feed = _number(
        _required(pem, "deuterium_feed_to_pem_kg_s", "pem"),
        "pem.deuterium_feed_to_pem_kg_s",
    )
    if d_feed < 0.0:
        raise InputBlocked("pem.deuterium_feed_to_pem_kg_s must be non-negative")

    delay = _number(
        _required(cece, "lpce_delay_s", "cece_lpce"), "cece_lpce.lpce_delay_s"
    ) + _number(_required(pem, "pem_delay_s", "pem"), "pem.pem_delay_s")
    if delay < 0.0:
        raise InputBlocked("total process delay must be non-negative")

    generic = {
        "schema_version": "TOMAHAWK-CHEMICAL-FUEL-CYCLE-0.1",
        "case_id": case.get("case_id", "TOMAHAWK_FOUNDATION_CASE"),
        "classification": {
            "process_type": "DLE_ALSB_CECE_LPCE_PEM_D_T_RETURN",
            "recipe_disclosure": "PROTECTED_BLACK_BOX",
            "chemistry_can_create_nuclei": False,
            "claimed_chemical_nuclear_breeding": False,
        },
        "time": time_cfg,
        "nuclear_source": nuclear,
        "process": {
            "delay_s": delay,
            "process_feed_kg_s": {"D": d_feed, "T": 0.0},
            "direct_makeup_kg_s": {"D": 0.0, "T": 0.0},
            "bred_delivery_efficiency": {"T": slipstream * hto_capture},
            "capture_efficiency": {"D": d_lpce, "T": t_lpce},
            "separation_efficiency": {"D": d_pem, "T": t_pem},
            "purification_efficiency": {"D": d_purity, "T": t_purity},
            "recovery_feed_already_debited": False,
            "aux_power_W": _number(
                _required(pem, "auxiliary_power_W", "pem"), "pem.auxiliary_power_W"
            ) + _number(
                _required(cece, "auxiliary_power_W", "cece_lpce"),
                "cece_lpce.auxiliary_power_W",
            ),
            "aux_heat_W": _number(
                _required(pem, "process_heat_W", "pem"), "pem.process_heat_W"
            ) + _number(
                _required(cece, "process_heat_W", "cece_lpce"),
                "cece_lpce.process_heat_W",
            ),
        },
        "inventory": inventory,
    }
    return generic


def simulate_foundation(case: Mapping[str, Any]) -> Dict[str, Any]:
    dle = compute_dle(case)
    generic_case = build_generic_case(case)
    generic_result = simulate(generic_case)
    alsb = case["alsb"]
    cece = case["cece_lpce"]
    pem = case["pem"]
    return {
        "schema_version": "TOMAHAWK-FUEL-SYSTEM-FOUNDATION-0.2",
        "status": "CALCULATED_REDUCED_ORDER_NOT_VALIDATED",
        "claim_status": "ARCHITECTURE_INTEGRATED_NO_PERFORMANCE_CLAIM",
        "source_document": {
            "name": "tech summary new fuel system.pdf",
            "sha256": SOURCE_SHA256,
        },
        "architecture": [
            "desalination_reject_brine",
            "direct_lithium_extraction",
            "aqueous_lithium_salt_blanket",
            "hto_formation",
            "cece_lpce",
            "pem_electrolysis",
            "d2_t2_fuel_return",
        ],
        "dle": dle,
        "alsb": {
            "salt_case": alsb.get("salt_case"),
            "medium": "aqueous",
            "tritium_form": "HTO",
            "design_tbr_floor": alsb.get("design_tbr_floor"),
            "realized_tbr_source": "3-D_NEUTRONICS_REQUIRED",
            "lpce_temperature_C": cece.get("lpce_temperature_C"),
        },
        "product_interface": {
            "product_species": "D2/T2",
            "direct_to_ignition": bool(case["fuel_return"].get("direct_to_ignition", False)),
            "D2_mass_in_product_kg_s": generic_result["rates"]["D_returned_steady_kg_s"],
            "T2_mass_in_product_kg_s": generic_result["rates"]["T_returned_steady_kg_s"],
            "oxygen_coproduct": "PEM_O2_OUTPUT_REQUIRES_WATER_AND_POWER_BALANCE",
        },
        "plant_interface": generic_result["plant_interface"],
        "fuel_cycle_result": generic_result,
        "declared_not_validated": {
            "dle_recovery_range": "0.70-0.90 per pass from source document",
            "tbr_greater_than_1_05": "design target from source document",
            "cece_performance": "not supplied",
            "pem_performance": "not supplied",
        },
    }


def self_test() -> Dict[str, Any]:
    case = {
        "case_id": "SYNTHETIC_FOUNDATION_TEST_ONLY",
        "time": {"dt_s": 1.0, "horizon_s": 5.0},
        "nuclear_source": {"tbr": 1.2, "reaction_rate_s": 1.0e20},
        "dle": {
            "brine_flow_m3_s": 1.0,
            "brine_density_kg_m3": 1100.0,
            "li_concentration_ppm": 0.5,
            "recovery_per_pass": 0.8,
        },
        "alsb": {
            "salt_case": "LiOH",
            "design_tbr_floor": 1.05,
            "hto_capture_efficiency": 0.98,
        },
        "cece_lpce": {
            "alsb_slipstream_fraction": 1.0,
            "lpce_temperature_C": {"min": 40.0, "max": 80.0},
            "tritium_lpce_transfer_efficiency": 0.98,
            "deuterium_lpce_transfer_efficiency": 0.98,
            "lpce_delay_s": 1.0,
            "auxiliary_power_W": 1.0e5,
            "process_heat_W": 2.0e5,
        },
        "pem": {
            "deuterium_feed_to_pem_kg_s": 5.0e-7,
            "tritium_product_recovery_efficiency": 0.98,
            "deuterium_product_recovery_efficiency": 0.98,
            "pem_delay_s": 1.0,
            "auxiliary_power_W": 2.0e5,
            "process_heat_W": 3.0e5,
        },
        "fuel_return": {
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
    result = simulate_foundation(case)
    assert result["status"] == "CALCULATED_REDUCED_ORDER_NOT_VALIDATED"
    assert result["dle"]["li_recovered_kg_s"] > 0.0
    assert result["product_interface"]["T2_mass_in_product_kg_s"] > 0.0
    return {"self_test": "PASS", "dle": result["dle"], "status": result["status"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.self_test:
        output: Dict[str, Any] = self_test()
    elif args.case:
        try:
            output = simulate_foundation(json.loads(args.case.read_text(encoding="utf-8")))
        except (InputBlocked, KeyError) as exc:
            output = {
                "status": "BLOCKED_INPUTS",
                "claim_status": "NO_SELF_SUFFICIENCY_CLAIM",
                "error": str(exc),
            }
    else:
        parser.error("provide a case JSON or --self-test")
        return 2

    rendered = json.dumps(output, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if output.get("status") != "BLOCKED_INPUTS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

