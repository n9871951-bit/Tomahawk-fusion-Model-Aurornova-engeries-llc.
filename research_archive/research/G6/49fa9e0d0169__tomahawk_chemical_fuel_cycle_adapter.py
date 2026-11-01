#!/usr/bin/env python3
"""Reduced-order, protected black-box fuel-cycle adapter for Tomahawk.

This module is intentionally limited to species accounting and plant-interface
bookkeeping. It does not implement a chemical recipe, radioactive-material
handling procedure, or nuclear transport solver.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


U_KG = 1.66053906660e-27
M_D_KG = 2.01410177812 * U_KG
M_T_KG = 3.01604928199 * U_KG
T_HALF_LIFE_S = 12.32 * 365.25 * 24.0 * 3600.0
LAMBDA_T_S = math.log(2.0) / T_HALF_LIFE_S


class InputBlocked(ValueError):
    """Raised when the protected interface is not sufficiently specified."""


@dataclass(frozen=True)
class Species:
    name: str
    mass_kg: float


SPECIES = {
    "D": Species("D", M_D_KG),
    "T": Species("T", M_T_KG),
}


def _number(value: Any, path: str, *, allow_none: bool = False) -> float:
    if value is None and allow_none:
        raise InputBlocked(f"missing required input: {path}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputBlocked(f"{path} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise InputBlocked(f"{path} must be finite")
    return result


def _rate(mapping: Mapping[str, Any], species: str, path: str) -> float:
    value = mapping.get(species)
    result = _number(value, f"{path}.{species}")
    if result < 0.0:
        raise InputBlocked(f"{path}.{species} must be non-negative")
    return result


def _fraction(mapping: Mapping[str, Any], species: str, path: str) -> float:
    result = _number(mapping.get(species), f"{path}.{species}")
    if not 0.0 <= result <= 1.0:
        raise InputBlocked(f"{path}.{species} must be between 0 and 1")
    return result


def tritium_bred_from_tbr(tbr: float, reaction_rate_s: float) -> float:
    """Convert a reaction-based TBR to a tritium mass-production rate."""
    tbr = _number(tbr, "nuclear_source.tbr")
    reaction_rate_s = _number(reaction_rate_s, "nuclear_source.reaction_rate_s")
    if tbr < 0.0 or reaction_rate_s < 0.0:
        raise InputBlocked("TBR and reaction rate must be non-negative")
    return tbr * reaction_rate_s * M_T_KG


def _required_nuclear_tritium(case: Mapping[str, Any]) -> float:
    source = case.get("nuclear_source", {})
    explicit = source.get("tritium_bred_kg_s")
    if explicit is not None:
        value = _number(explicit, "nuclear_source.tritium_bred_kg_s")
        if value < 0.0:
            raise InputBlocked("nuclear_source.tritium_bred_kg_s must be non-negative")
        return value
    return tritium_bred_from_tbr(
        source.get("tbr"), source.get("reaction_rate_s")
    )


def _delay_steps(delay_s: float, dt_s: float) -> int:
    if delay_s < 0.0:
        raise InputBlocked("process.delay_s must be non-negative")
    return int(math.ceil(delay_s / dt_s))


def _series(value: float, count: int) -> List[float]:
    return [float(value) for _ in range(count)]


def _check_classification(case: Mapping[str, Any]) -> None:
    classification = case.get("classification", {})
    if classification.get("chemistry_can_create_nuclei") is True:
        raise InputBlocked("INVALID_CHEMICAL_NUCLEAR_BREEDING_CLAIM")
    if classification.get("claimed_chemical_nuclear_breeding") is True:
        raise InputBlocked("INVALID_CHEMICAL_NUCLEAR_BREEDING_CLAIM")


def simulate(case: Mapping[str, Any]) -> Dict[str, Any]:
    """Run a deterministic reduced-order fuel-cycle accounting case.

    All source/feed rates are system-boundary inflows unless
    ``recovery_feed_already_debited`` is true. In the latter case, the adapter
    subtracts that feed from the tracked inventory before adding returned fuel.
    """
    _check_classification(case)

    time_cfg = case.get("time", {})
    dt_s = _number(time_cfg.get("dt_s"), "time.dt_s")
    horizon_s = _number(time_cfg.get("horizon_s"), "time.horizon_s")
    if dt_s <= 0.0 or horizon_s <= 0.0:
        raise InputBlocked("time.dt_s and time.horizon_s must be positive")
    steps = int(math.ceil(horizon_s / dt_s))

    source = case.get("nuclear_source", {})
    reaction_rate_s = _number(source.get("reaction_rate_s"), "nuclear_source.reaction_rate_s")
    if reaction_rate_s < 0.0:
        raise InputBlocked("nuclear_source.reaction_rate_s must be non-negative")
    bred_T = _required_nuclear_tritium(case)

    process = case.get("process", {})
    delay_s = _number(process.get("delay_s"), "process.delay_s")
    delay_steps = _delay_steps(delay_s, dt_s)
    feed = process.get("process_feed_kg_s", {})
    direct = process.get("direct_makeup_kg_s", {})
    delivery = process.get("bred_delivery_efficiency", {})
    capture = process.get("capture_efficiency", {})
    separation = process.get("separation_efficiency", {})
    purification = process.get("purification_efficiency", {})

    for name, mapping in {
        "process.process_feed_kg_s": feed,
        "process.direct_makeup_kg_s": direct,
        "process.bred_delivery_efficiency": delivery,
        "process.capture_efficiency": capture,
        "process.separation_efficiency": separation,
        "process.purification_efficiency": purification,
    }.items():
        if not isinstance(mapping, Mapping):
            raise InputBlocked(f"{name} must be an object with D/T values")

    feed_D = _rate(feed, "D", "process.process_feed_kg_s")
    feed_T = _rate(feed, "T", "process.process_feed_kg_s")
    direct_D = _rate(direct, "D", "process.direct_makeup_kg_s")
    direct_T = _rate(direct, "T", "process.direct_makeup_kg_s")
    eta_delivery_T = _fraction(delivery, "T", "process.bred_delivery_efficiency")

    eta_D = (
        _fraction(capture, "D", "process.capture_efficiency")
        * _fraction(separation, "D", "process.separation_efficiency")
        * _fraction(purification, "D", "process.purification_efficiency")
    )
    eta_T = (
        _fraction(capture, "T", "process.capture_efficiency")
        * _fraction(separation, "T", "process.separation_efficiency")
        * _fraction(purification, "T", "process.purification_efficiency")
    )

    # Newly bred tritium is a nuclear source that becomes a process feed only
    # after blanket-to-process delivery. It is never chemically generated.
    bred_to_process_T = bred_T * eta_delivery_T
    total_feed_D = feed_D
    total_feed_T = feed_T + bred_to_process_T
    returned_D = total_feed_D * eta_D
    returned_T = total_feed_T * eta_T
    delivery_loss_T = bred_T - bred_to_process_T
    process_loss_D = total_feed_D - returned_D
    process_loss_T = total_feed_T - returned_T

    burn_T = reaction_rate_s * M_T_KG
    burn_D = reaction_rate_s * M_D_KG

    inventory = case.get("inventory", {})
    initial = inventory.get("initial_kg", {})
    reserve = inventory.get("reserve_kg", {})
    losses = inventory.get("other_loss_kg_s", {})
    permeation = inventory.get("permeation_loss_kg_s", {})
    initial_D = _rate(initial, "D", "inventory.initial_kg")
    initial_T = _rate(initial, "T", "inventory.initial_kg")
    reserve_D = _rate(reserve, "D", "inventory.reserve_kg")
    reserve_T = _rate(reserve, "T", "inventory.reserve_kg")
    other_D = _rate(losses, "D", "inventory.other_loss_kg_s")
    other_T = _rate(losses, "T", "inventory.other_loss_kg_s")
    permeation_T = _rate(permeation, "T", "inventory.permeation_loss_kg_s")

    recovery_feed_already_debited = bool(process.get("recovery_feed_already_debited", False))
    debited_D = feed_D if recovery_feed_already_debited else 0.0
    debited_T = feed_T if recovery_feed_already_debited else 0.0

    # A FIFO delay queue preserves the transient effect of processing delay.
    # Keep exactly ``delay_steps`` samples ahead of the output.  Do not set a
    # maxlen: appending before popping would otherwise discard the oldest
    # sample and erase the modeled delay when delay_steps == 1.
    q_D = deque(_series(0.0, delay_steps))
    q_T = deque(_series(0.0, delay_steps))
    M_D = initial_D
    M_T = initial_T
    rows: List[Dict[str, float]] = []
    min_D = M_D
    min_T = M_T

    for index in range(steps):
        if delay_steps:
            q_D.append(returned_D)
            q_T.append(returned_T)
            delayed_D = q_D.popleft()
            delayed_T = q_T.popleft()
        else:
            delayed_D = returned_D
            delayed_T = returned_T

        usable_D = delayed_D + direct_D
        usable_T = delayed_T + direct_T
        decay_T = LAMBDA_T_S * M_T
        delta_D = usable_D - burn_D - other_D - debited_D
        delta_T = usable_T - burn_T - decay_T - permeation_T - other_T - debited_T
        M_D = M_D + dt_s * delta_D
        M_T = M_T + dt_s * delta_T
        min_D = min(min_D, M_D)
        min_T = min(min_T, M_T)
        rows.append({
            "time_s": min((index + 1) * dt_s, horizon_s),
            "usable_D_kg_s": usable_D,
            "usable_T_kg_s": usable_T,
            "inventory_D_kg": M_D,
            "inventory_T_kg": M_T,
            "decay_T_kg_s": decay_T,
        })

    steady_supply_ratio_T = (returned_T + direct_T) / burn_T if burn_T else math.inf
    transient_supply_ratio_T = (
        min(row["usable_T_kg_s"] for row in rows) / burn_T if burn_T else math.inf
    )
    aux_power_W = _number(process.get("aux_power_W"), "process.aux_power_W")
    aux_heat_W = _number(process.get("aux_heat_W"), "process.aux_heat_W")
    if aux_power_W < 0.0 or aux_heat_W < 0.0:
        raise InputBlocked("process auxiliary power and heat must be non-negative")

    tbr = source.get("tbr")
    reported_tbr = None if tbr is None else _number(tbr, "nuclear_source.tbr")
    tbr_target_screen = reported_tbr is not None and reported_tbr >= 1.15
    inventory_screen = min_D >= reserve_D and min_T >= reserve_T

    return {
        "schema_version": "TOMAHAWK-CHEMICAL-FUEL-CYCLE-0.1",
        "status": "CALCULATED_REDUCED_ORDER_NOT_VALIDATED",
        "claim_status": "NOT_A_VALIDATED_SELF_SUFFICIENCY_RESULT",
        "classification": {
            "process_type": "CHEMICAL_RECOVERY_SEPARATION_RECYCLING",
            "chemistry_can_create_nuclei": False,
            "nuclear_tritium_source": "NEUTRONICS_INPUT_REQUIRED",
        },
        "rates": {
            "reaction_rate_s": reaction_rate_s,
            "T_bred_kg_s": bred_T,
            "T_bred_to_process_kg_s": bred_to_process_T,
            "T_delivery_loss_kg_s": delivery_loss_T,
            "D_burn_kg_s": burn_D,
            "T_burn_kg_s": burn_T,
            "D_returned_steady_kg_s": returned_D,
            "T_returned_steady_kg_s": returned_T,
            "D_process_loss_kg_s": process_loss_D,
            "T_process_loss_kg_s": process_loss_T,
        },
        "efficiencies": {
            "D_chemical_chain": eta_D,
            "T_chemical_chain": eta_T,
            "T_usable_fraction_of_bred_at_steady_state": (
                returned_T / bred_T if bred_T else 0.0
            ),
        },
        "plant_interface": {
            "P_fuel_cycle_W": aux_power_W,
            "Q_fuel_cycle_W": aux_heat_W,
            "delay_s": delay_s,
            "double_counting_guard": {
                "recovery_feed_already_debited": recovery_feed_already_debited,
                "host_must_not_subtract_same_feed_twice": True,
            },
        },
        "screens": {
            "steady_state_fuel_supply_ratio_T": steady_supply_ratio_T,
            "minimum_transient_fuel_supply_ratio_T": transient_supply_ratio_T,
            "minimum_D_inventory_kg": min_D,
            "minimum_T_inventory_kg": min_T,
            "TBR_ge_1_15_screen": tbr_target_screen,
            "positive_inventory_and_reserve_screen": inventory_screen,
            "gate_6_candidate_screen": bool(tbr_target_screen and inventory_screen),
        },
        "time_series": rows,
        "constants": {
            "T_half_life_s": T_HALF_LIFE_S,
            "lambda_T_s_minus_1": LAMBDA_T_S,
        },
    }


def self_test() -> Dict[str, Any]:
    """Synthetic accounting test; it is not a Tomahawk design case."""
    case = {
        "classification": {
            "process_type": "CHEMICAL_RECOVERY_SEPARATION_RECYCLING",
            "chemistry_can_create_nuclei": False,
            "claimed_chemical_nuclear_breeding": False,
        },
        "time": {"dt_s": 1.0, "horizon_s": 5.0},
        "nuclear_source": {
            "tbr": 1.2,
            "reaction_rate_s": 1.0e20,
        },
        "process": {
            "delay_s": 1.0,
            "process_feed_kg_s": {"D": 0.0, "T": 0.0},
            "direct_makeup_kg_s": {"D": 0.0, "T": 0.0},
            "bred_delivery_efficiency": {"T": 0.95},
            "capture_efficiency": {"D": 0.99, "T": 0.95},
            "separation_efficiency": {"D": 0.99, "T": 0.95},
            "purification_efficiency": {"D": 0.99, "T": 0.95},
            "aux_power_W": 1.0e6,
            "aux_heat_W": 2.0e6,
            "recovery_feed_already_debited": False,
        },
        "inventory": {
            "initial_kg": {"D": 1.0, "T": 1.0},
            "reserve_kg": {"D": 0.0, "T": 0.0},
            "other_loss_kg_s": {"D": 0.0, "T": 0.0},
            "permeation_loss_kg_s": {"T": 0.0},
        },
    }
    result = simulate(case)
    assert result["status"] == "CALCULATED_REDUCED_ORDER_NOT_VALIDATED"
    assert result["rates"]["T_bred_kg_s"] > result["rates"]["T_bred_to_process_kg_s"]
    assert result["plant_interface"]["double_counting_guard"]["host_must_not_subtract_same_feed_twice"]
    return {"self_test": "PASS", "result_summary": result["screens"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.self_test:
        output: Dict[str, Any] = self_test()
    elif args.case:
        case = json.loads(args.case.read_text(encoding="utf-8"))
        try:
            output = simulate(case)
        except InputBlocked as exc:
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
