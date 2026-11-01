# MGRID-to-G1 preflight check

**Run date:** 2026-09-09  
**Scope:** supplied PF MAKEGRID artifacts versus the recovered EV007/G1 candidate plasma boundary  
**Disposition:** `SCREENING_COMPATIBLE_BUT_NOT_AUTHORIZED_FOR_VMEC`

## Executive result

The supplied `mgrid_tomahawk_pf.nc` is a readable, native-successful MAKEGRID result and is internally consistent with the supplied `coils.tomahawk_pf` and `extcur.tomahawk_pf` files. The PF centerline branch also matches the archived CAD export exactly.

Against the recovered G1 surface, all sampled boundary points are inside the MGRID interpolation box and all six PF field groups interpolate finite values. The smallest PF filament-centerline clearance is **1.85324 m**, from `PF_M_OUT`.

This is a **preflight compatibility result**, not a free-boundary equilibrium result. The project’s own G1 verification record says `formal_G1_approved=false` and `native_FreeCAD_executed=false`. The MGRID is PF-only (`nfp=1`); it is not the complete 3-D external field needed to validate a 16-period plasma boundary. No VMEC/DESC run was performed.

## Gate table

| Check | Result | Evidence / margin |
|---|---|---|
| Native MAKEGRID evidence | PASS-AS-SUPPLIED | `return_code=0`; status `NATIVE_MAKEGRID_COMPLETED`; command recorded as `/home/STELLOPT/MAKEGRID/Release/xgrid` |
| MGRID readable | PASS | NetCDF 64-bit offset; dimensions `201 x 201 x 36`; 6 external groups |
| Coil groups versus MGRID groups | PASS | Six labels match: `PF_L_IN`, `PF_L_OUT`, `PF_M_IN`, `PF_M_OUT`, `PF_U_IN`, `PF_U_OUT` |
| Coil geometry versus archived PF CAD CSV | PASS | 578 loops; 128 filament points per loop; maximum coordinate error `0 m`; maximum signed-current error `0 A` |
| `extcur` versus coil/MGRID current schedule | PASS | All six current differences are exactly `0 A` at stored precision |
| Candidate-boundary units/source identity | PASS-SCREENING | Corrected STEP uses metres; STEP SHA-256 equals G1 source hash `8317664c...d2899` |
| Candidate boundary inside MGRID box | PASS-SCREENING | (R=4.49000)–(10.51000) m; (Z=-2.148969)–(2.148969) m; box (R=4)–11 m, (Z=-3.5)–(3.5) m |
| Boundary coverage margin | PASS-SCREENING | Minimum radial margin `0.49000 m`; minimum vertical margin `1.35103 m` |
| PF field interpolation on candidate boundary | PASS-SCREENING | 524,288 samples; all finite; summed PF field `0.4862`–`0.5441 T` |
| PF filament clearance to candidate boundary | PASS-SCREENING | Minimum `1.85324 m` at `PF_M_OUT`; filament centerlines only, no winding-pack envelope |
| Formal/native G1 approval | BLOCKED | G1 record: `formal_G1_approved=false`, `native_FreeCAD_executed=false` |
| Total 3-D external field | BLOCKED | Supplied MGRID is PF-only and has `nfp=1`; TF/combined field source is not present in this check |
| VMEC/DESC execution | BLOCKED | No `vmec`, `vmec2000`, `desc`, `simsopt`, or `vmecpp` executable/module is available in this workspace |
| `free_boundary_3D_MHD_pass` | BLOCKED | Must remain unresolved until the preceding blockers are closed and a solver run is evidenced |

## Exact PF inputs

The native coil source contains 578 closed filamentary loops, each with 128 points. The current schedule is:

| Group | Loops | Current |
|---|---:|---:|
| `PF_L_IN` | 28 | `+19123.4976703 A` |
| `PF_L_OUT` | 162 | `+19904.2740987 A` |
| `PF_M_IN` | 48 | `-19395.6036404 A` |
| `PF_M_OUT` | 150 | `+19304.7552541 A` |
| `PF_U_IN` | 28 | `+19123.4976703 A` |
| `PF_U_OUT` | 162 | `+19904.2740987 A` |

The MGRID header reports:

```text
rad=201, zee=201, phi=36
nfp=1, nextcur=6, mgrid_mode=S
R=4.0..11.0 m, Z=-3.5..3.5 m
```

`mgrid_mode=S` is treated as unit-current field data; the reported `raw_coil_cur` values are applied for the summed PF field check. The reconstructed values agree with the `EXTCUR(1..6)` file exactly.

## Boundary used for this check

The available G1 artifact is revision `EV007_PERIODIC_REPAIR_1`, represented by the recovered surface:

```text
R(theta,phi) = R0 + a*cos(theta) + epsilon*cos(theta - 16*phi)
Z(theta,phi) = b*sin(theta) + epsilon*sin(theta - 16*phi)
R0=7.499999999999888 m
a =2.999999999999756 m
b =2.138969432449380 m
epsilon=0.009999999999999069 m
periods=16
```

The corrected STEP and recovered surface use the same source hash. The STEP’s raw `CARTESIAN_POINT` records include B-spline control/support points, so their raw extrema were not misidentified as the geometric surface boundary; the analytic recovered surface was used for the coverage and clearance calculations.

The supplied G1 package itself lists the remaining native checks as BREP/BOP validity, STEP roundtrip, mesh topology/self-intersection, mesh refinement, native seam-normal checks, containment, and interface review. Those are not silently converted into a pass here.

## Clearance results

Clearance was computed from the straight line segments joining the 128 native filament points of each coil loop to the recovered analytic boundary. Values are centerline-to-surface distances:

| Group | Minimum distance |
|---|---:|
| `PF_L_IN` | `2.938678 m` |
| `PF_L_OUT` | `2.758854 m` |
| `PF_M_IN` | `1.915782 m` |
| `PF_M_OUT` | `1.853240 m` |
| `PF_U_IN` | `2.938678 m` |
| `PF_U_OUT` | `2.758854 m` |

No centerline intersection was found. This does not certify conductor insulation, winding-pack thickness, support structure, or manufacturing clearance because those solids were not part of the MAKEGRID filament file.

## What can proceed

The files can proceed to a **solver-machine preflight** as a matched PF input set. Before a free-boundary VMEC/DESC run, the next controlled sequence is:

1. Run the native FreeCAD G1 audit on the exact boundary revision and record formal/interface approval.
2. Confirm the VMEC symmetry convention: the PF grid is full-torus `nfp=1`, while the candidate plasma surface has a 16-period helical term. If the intended equilibrium is 16-period, supply a consistent total external-field representation, including the TF source, or explicitly configure the solver for the full torus.
3. Run VMEC/DESC with the approved boundary, plasma profiles, PF current schedule, and total external field.
4. Compare the converged boundary and flux quantities against the approved G1 target; only then update `free_boundary_3D_MHD_pass`.

No screening notebook, threshold, or physics result was changed by this preflight.

## File hashes

| Artifact | SHA-256 |
|---|---|
| `coils.tomahawk_pf` | `b65e977cf7b24c4f2e2640ac963ec99a0692849a2be409b59f8900171b32b37c` |
| `extcur.tomahawk_pf` | `1db04e2d69d5e7b8ec31ee1fa3d0cd0547a3414c7614b6e574dc38eeb62bbb27` |
| `mgrid_tomahawk_pf.nc` | `027aabea0dde0962c66e9825a859f913faa707ae6f604f69f55a940bc154962e` |
| `makegrid_run_manifest.json` | `d2b3d6786229ea92e2443b179147307eb840dc0f5d0e914f91b6c548edf0dc7f` |
| `xgrid_tomahawk_pf.log` | `aeef387b70c35af9c4fe064d720bc10b3f4b05ed25991e3034e2dd51f39e2435` |
| `ev007_boundary_units_corrected.step` | `8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899` |
| `repaired_surface.json` | source hash `8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899` |

The native upstream software is staged as separate MAKEGRID and VMEC2000 components in the [STELLOPT repository](https://github.com/PrincetonUniversity/STELLOPT); this workspace has the generated PF artifact and evidence log, but not a local VMEC/DESC runtime.
