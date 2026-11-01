#!/usr/bin/env python3
"""Runner bridge for the DLE/ALSB/CECE/PEM fuel-system stage.

The bridge requires a machine-readable realized neutronics handoff. It never
turns a missing or provisional TBR into a synthetic value.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from tomahawk_fuel_system_foundation_adapter import InputBlocked, simulate_foundation


def _find_numeric(data: Any, keys: tuple[str, ...]) -> Optional[float]:
    if isinstance(data, Mapping):
        for key in keys:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        for value in data.values():
            found = _find_numeric(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_numeric(value, keys)
            if found is not None:
                return found
    return None


def load_realized_neutronics(path: Path) -> Dict[str, float]:
    if not path.is_file():
        raise InputBlocked(f"missing realized neutronics handoff: {path}")
    if path.suffix.lower() != ".json":
        raise InputBlocked(
            "FUEL_SYSTEM requires neutronics_output.json with realized_TBR and "
            "reaction_rate_s; binary statepoint handoff is not accepted directly"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise InputBlocked(f"could not parse neutronics handoff: {exc}")
    if not isinstance(data, Mapping):
        raise InputBlocked("neutronics handoff must be a JSON object")

    tbr = _find_numeric(data, ("realized_TBR", "TBR_realized", "tbr_realized"))
    reaction_rate = _find_numeric(data, ("reaction_rate_s", "R_DT_total"))
    bred = _find_numeric(data, ("tritium_bred_kg_s", "R_T_bred_kg_s"))
    if bred is None and (tbr is None or reaction_rate is None):
        raise InputBlocked(
            "neutronics handoff must provide tritium_bred_kg_s or both "
            "realized_TBR and reaction_rate_s"
        )
    result: Dict[str, float] = {}
    if tbr is not None:
        result["tbr"] = tbr
    if reaction_rate is not None:
        result["reaction_rate_s"] = reaction_rate
    if bred is not None:
        result["tritium_bred_kg_s"] = bred
    return result


def run(case_path: Path, previous_output: Path, output_path: Path) -> int:
    try:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        if not isinstance(case, dict):
            raise InputBlocked("fuel-system case must be a JSON object")
        case.setdefault("nuclear_source", {}).update(load_realized_neutronics(previous_output))
        case["nuclear_source"]["source_status"] = "FROM_3D_NEUTRONICS"
        result = simulate_foundation(case)
        result["provenance"] = {
            "fuel_system_input": str(case_path.resolve()),
            "neutronics_handoff": str(previous_output.resolve()),
            "handoff_status": "REALIZED_NEUTRONICS_JSON_CONSUMED",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    except (InputBlocked, KeyError, json.JSONDecodeError) as exc:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({
            "status": "BLOCKED_INPUTS",
            "claim_status": "NO_SELF_SUFFICIENCY_CLAIM",
            "error": str(exc),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--previous-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run(args.case, args.previous_output, args.output)


if __name__ == "__main__":
    raise SystemExit(main())

