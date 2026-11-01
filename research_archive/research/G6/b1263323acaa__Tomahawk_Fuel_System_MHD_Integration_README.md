# Tomahawk Rev1.7 fuel-system integration test package

This is a derivative of the Rev1.7 multiphysics package. The existing CAD,
material, solver-geometry, MHD, neutronics, CFD/CHT, and CHF files are
preserved. The only pipeline change is the addition of:

```text
MHD -> NEUTRONICS -> FUEL_SYSTEM -> CFD -> CHF
```

## Fuel-system handoff

The `FUEL_SYSTEM` stage consumes a realized `neutronics_output.json` containing
at least one of:

- `tritium_bred_kg_s`; or
- both `realized_TBR` and `reaction_rate_s`.

It then runs the documented DLE -> aqueous ALSB -> HTO -> CECE/LPCE -> PEM ->
D2/T2 return accounting model. Missing or assumption-only nuclear outputs are
blocked.

## Run the standard-library integration tests

From this package directory:

```bash
python3 test_fuel_system_integration.py
```

The tests cover the fuel accounting, realized-neutronics handoff, missing-input
failure behavior, preflight stage ordering, and a synthetic orchestration run.
They do not run VMEC, OpenMC, NekRS, CHF, or physical MHD.

## Configure a real run

Use `Tomahawk_Continuous_Run_Config.fuel_system_foundation.template.json` as a
starting point. Supply a populated:

```text
FUEL_CYCLE/tomahawk_fuel_system_foundation.json
```

and configure the real MHD, neutronics, CFD/CHT, and CHF commands. The
neutronics command must produce `neutronics_output.json` as the declared
handoff output. This package does not manufacture TBR, reaction rate, DLE
throughput, CECE/LPCE efficiency, PEM recovery, or self-sufficiency results.

## Status discipline

Outputs from the new stage are labeled reduced-order and not validated. The
existing geometry and G1/CAD records are not upgraded into physical solver
validation by this integration.

