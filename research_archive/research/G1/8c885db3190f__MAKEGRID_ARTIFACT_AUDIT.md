# Native MAKEGRID artifact audit

Status: **NATIVE_MAKEGRID_PF_ARTIFACTS_VERIFIED_TF_NOT_PRESENT**

This audit reads the supplied native output and its matching PF coil/current files. It does not modify them and does not infer TF data that is not present.

## Exact artifacts

| Artifact | SHA-256 |
|---|---|
| `mgrid_tomahawk_pf.nc` | `027aabea0dde0962c66e9825a859f913faa707ae6f604f69f55a940bc154962e` |
| `coils.tomahawk_pf` | `b65e977cf7b24c4f2e2640ac963ec99a0692849a2be409b59f8900171b32b37c` |
| `extcur.tomahawk_pf` | `1db04e2d69d5e7b8ec31ee1fa3d0cd0547a3414c7614b6e574dc38eeb62bbb27` |
| `makegrid_run_manifest.json` | `d2b3d6786229ea92e2443b179147307eb840dc0f5d0e914f91b6c548edf0dc7f` |
| `xgrid_tomahawk_pf.log` | `aeef387b70c35af9c4fe064d720bc10b3f4b05ed25991e3034e2dd51f39e2435` |

## MAKEGRID result

- Native command return code: **0**
- Manifest status: **`NATIVE_MAKEGRID_COMPLETED`**
- NetCDF dimensions: **ir=201, jz=201, kp=36**
- Grid bounds: **R=4.0–11.0 m**, **Z=-3.5–3.5 m**
- `nfp`: **1**
- `nextcur`: **6**
- `mgrid_mode`: **`S`**
- Field arrays finite: **True**; non-finite values: **0**
- First/last phi-plane maximum difference: **3.404508e-09**
- MGRID and EXTCUR manifest hashes match: **True**
- Coil-file hash declared in the manifest: **False** (coverage is incomplete, but no coil-file mismatch is asserted)

## PF coil/current reconciliation

| Group | Loops | Current (A) | Max loop closure gap (m) |
|---|---:|---:|---:|
| `PF_L_IN` | 28 | 19123.4976703 | 0.0 |
| `PF_L_OUT` | 162 | 19904.2740987 | 0.0 |
| `PF_M_IN` | 48 | -19395.6036404 | 0.0 |
| `PF_M_OUT` | 150 | 19304.7552541 | 0.0 |
| `PF_U_IN` | 28 | 19123.4976703 | 0.0 |
| `PF_U_OUT` | 162 | 19904.2740987 | 0.0 |

- Group labels match MGRID: **True**
- MGRID raw current versus `EXTCUR`: **0 A maximum difference**
- Coil-file current versus `EXTCUR`: **0 A maximum difference**
- All loops are 128-point closed filaments: **True**

## What this does and does not close

- Native PF MAKEGRID artifact: **PASS**
- TF coil source in these files: **ABSENT**
- Total-field / TF edge-ripple screen from this MGRID: **BLOCKED**
- `free_boundary_3D_MHD_pass`: **BLOCKED**
- Formal G1 approval: **FALSE**

The manifest names `input_xgrid.tomahawk_pf`, but that input configuration file is not included in the supplied directory. The native output and its hashes are still directly checkable; a complete replay requires that missing input file.
