# Tomahawk fuel-system foundation integration — Rev 0.2

This package maps the supplied foundational PDF into the protected fuel-cycle
model:

```text
DLE -> aqueous ALSB -> HTO -> CECE/LPCE -> PEM -> D2/T2 return
```

## Files

- `Tomahawk_Fuel_System_Foundation_Analysis_Rev0.2.md` — technical mapping,
  claim boundaries, and required inputs.
- `tomahawk_fuel_system_foundation_adapter.py` — process-specific adapter.
- `tomahawk_fuel_system_foundation.template.json` — input contract.
- `tomahawk_chemical_fuel_cycle_adapter.py` — generic inventory/plant ledger
  used by the process-specific adapter.

## Synthetic self-test

```bash
python3 tomahawk_fuel_system_foundation_adapter.py --self-test
```

The self-test is not a Tomahawk performance result.

## Real-case execution

Copy the template to a protected case file, fill the required performance-level
inputs, and run:

```bash
python3 tomahawk_fuel_system_foundation_adapter.py \
  tomahawk_fuel_system_foundation.json \
  --output tomahawk_fuel_system_foundation_output.json
```

The supplied template intentionally fails closed while the actual brine flow,
neutronics source, process efficiencies, inventory, losses, and auxiliary loads
remain unknown.

