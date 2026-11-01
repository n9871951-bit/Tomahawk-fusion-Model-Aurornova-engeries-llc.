# Tomahawk chemical fuel-cycle integration package

This package adds a protected, reduced-order interface for the omitted fuel-cycle
process. It does not reconstruct or expose the process recipe.

## Files

- `Tomahawk_Chemical_Fuel_Cycle_Integration_Rev0.1.md` — equations, scope,
  physics boundary, and IP-handling rules.
- `chemical_fuel_cycle_interface.template.json` — performance-level input
  contract. Unknown values remain `null` until recovered.
- `tomahawk_chemical_fuel_cycle_adapter.py` — deterministic species-inventory
  adapter with transient processing delay, losses, auxiliary power/heat, and
  double-counting protection.

## Run the accounting self-test

```bash
python3 tomahawk_chemical_fuel_cycle_adapter.py --self-test
```

The self-test uses synthetic values only. It is not a Tomahawk performance
result.

## Run a supplied protected parameter sheet

```bash
python3 tomahawk_chemical_fuel_cycle_adapter.py \
  chemical_fuel_cycle_interface.json \
  --output chemical_fuel_cycle_output.json
```

The template intentionally fails closed while required values are `null`.

## Host-model wiring

1. Pass the realized `reaction_rate_s` and TBR from the 3-D neutronics output.
2. Pass the private process's performance-level feed, efficiency, delay,
   inventory, loss, and auxiliary-load values.
3. Replace the host's generic processing-loss term with the adapter's returned
   fuel and loss terms; do not subtract the same feed twice.
4. Add `P_fuel_cycle_W` to the existing recirculating-power ledger and
   `Q_fuel_cycle_W` to the thermal ledger.
5. Report the result as a reduced-order screen until the neutronics and process
   inputs are independently qualified.

