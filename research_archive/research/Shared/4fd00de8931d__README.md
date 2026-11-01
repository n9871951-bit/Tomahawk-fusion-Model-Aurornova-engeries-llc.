# Tomahawk TF48 native/MGRID handoff

This is the corrected 48-coil branch. The 16-coil branches are retained only
as rejected comparison cases.

## Controlling result

The source branch is `CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION`:

- 48 physical TF coils
- 100 turns per coil
- 512 centerline segments per coil
- 16 field periods, 7.5° spacing
- flattop current: 109,374.9999947 A/turn
- direct finite-filament edge ripple: **0.7539158737%**
- fixed edge limit: **1.0%**
- TF ripple gate: **PASS**

The native TF coil file uses three exact base coils with `periods 16`. That is
the standard symmetry-reduced representation of the verified 48 physical
coils, not a 16-coil physics branch. The source CSVs with all 48 coils are
included and hash-checked.

## Native Ubuntu run

Put this directory on Ubuntu with STELLOPT/MAKEGRID and run:

```bash
STELLOPT_XGRID=/absolute/path/to/xgrid bash RUN_TF48_NATIVE.sh
```

or add `xgrid` to `PATH` and run `bash RUN_TF48_NATIVE.sh`. A successful native
run must create `mgrid_tomahawk_tf48.nc`; the wrapper prints its SHA-256. The
interactive input sequence follows the STELLOPT MAKEGRID `xgrid` interface;
the official source is the
[STELLOPT MAKEGRID interactive input](https://github.com/PrincetonUniversity/STELLOPT/blob/develop/MAKEGRID/Sources/interactive_input.f)
and the
[MAKEGRID driver](https://github.com/PrincetonUniversity/STELLOPT/blob/develop/MAKEGRID/Sources/makegrid.f).

The current Codex execution image does not contain an `xgrid` or VMEC binary,
so this handoff does not falsely label a Python field grid as native output.

## Included solver inputs

- `coils.tomahawk_tf48`, `extcur.tomahawk_tf48`,
  `input_xgrid_tomahawk_tf48`: native TF48 MAKEGRID inputs.
- `mgrid_tomahawk_tf48_equivalent.nc`: DESC-generated TF48 field-grid
  equivalent, validated by `SplineMagneticField.from_mgrid`.
- `mgrid_tomahawk_total_tf48_equivalent.nc`: raw PF+TF48 total-field
  equivalent; it agrees with the separate PF+TF field on the G1 boundary to
  `2.11e-7 T` maximum in the audit.
- `mgrid_tomahawk_pf.nc`: supplied native PF MGRID used for the total field.
- `desc_tf48_mgrid_runtime.py`: actual DESC free-boundary vacuum runtime using
  the bundled PF MGRID and TF48 MGRID-equivalent.
- `vmec_tf48_free_boundary.input.template`: VMEC input template, blocked until
  qualified pressure/current profiles and final G1 boundary closure exist.

## Actual DESC result

DESC 0.17.3 did run with the TF48 MGRID-equivalent and supplied PF MGRID. The
initial force solve passed, but the free-boundary optimizer stopped at its
iteration limit:

- free-boundary solve: **FAIL/REVISE**
- post-run `|B·n|` maximum: 18.48 T on the 12×6 audit grid
- post-run `|B·n|` RMS: 8.62 T
- pressure/current closure: vacuum only; finite-beta closure is absent

The mesh audit is included in `boundary_mesh_resolution_audit.json` and
`boundary_normal_residual_map.png`. Refining `(M,N)` from `(6,3)` to `(36,18)`
changed post-run RMS from 8.542 T to 8.616 T and the sampled maximum from
18.283 T to 18.613 T. The residual is therefore not fixed by mesh density.

The present fixed-MGRID DESC problem contains no coil-shape harmonic degrees of
freedom and no Tikhonov coil-curvature/length penalty. Those changes require a
separate bounded 48-coil shape-optimization problem and must not be claimed as
resolved by changing the boundary sampling grid.
