# Power-control change preflight

Status: **POWER_CONTROL_INTEGRATION_READY_SCREENING_ONLY**

This is a fail-closed integration check for the four proposed power-output controls. It does not change CAD, currents, the existing fusion-power result, or solver authorization.

## TF-ripple prerequisite

| Evidence | Result |
|---|---:|
| Native PF MAKEGRID artifact | **PASS** |
| Native TF MGRID present anywhere in project | **False** |
| 16-coil CAD-A2 model-derived edge ripple | **25.023778%** |
| Legacy 16-coil edge ripple | **69.164654%** |
| 48-coil model-derived correction edge ripple | **0.753916%** |
| Limit | **1.000000%** |
| Strict TF-ripple screening gate (TF48 branch) | **True** |

The only native `mgrid_*.nc` files found are copies of the PF-only file with `nfp=1`, six `PF_*` groups, and no TF group. The declared 48-coil interleaved branch is below the screening limit and therefore authorizes screening integration. Its model-derived status does not authorize a native/as-built VMEC/DESC run. The 16-coil CAD-A2 branch remains above the limit.

## Requested changes

The four controls are present as explicit, auditable contracts:

1. Rotational shear / angular-momentum deposition.
2. Foot-plus-main temporal pulse shaping.
3. Per-beam power/timing asymmetry compensation.
4. Pre-compression magnetic insulation with radiation-MHD flux compression and transport closure.

They remain **not applied** because absorption locations, beam waveforms, target dynamics, radiation-hydrodynamics, rotating-MHD, and transport inputs are absent, and the strict TF-ripple prerequisite is closed.

## Disposition

- Geometry changed: **False**
- Existing power model changed: **False**
- Power multiplier applied: **1.0**
- Incremental power output: **not asserted**
- Solver compilation/execution from this preflight: **not performed**
- `tf_edge_ripple_screen_pass`: **True** for the declared TF48 screening branch
- Screening power-control integration authorization: **True**
- Native/as-built solver authorization: **False**
