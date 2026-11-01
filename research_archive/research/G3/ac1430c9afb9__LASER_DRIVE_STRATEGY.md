# Laser-drive strategy integration

Status: `LASER_COUPLING_CONTROL_LAW_DEFINED_NOT_SOLVED`

The four requested laser-drive ideas are integrated as explicit control laws and input fields. CAD geometry is unchanged, and the existing power screen receives no gain multiplier.

## Exact CAD input

- Source: `/workspace/scratch/9740310843df/tomahawk_full_cad/preflight/CAD_A2_20260830_214318_qb5q9bp6/whole_model_definition.json`
- SHA-256: `82c8c1c2a1570d814d38169a8dbd011f59f952b9d817cc6be4abd84258b03319`
- CAD version: `CAD-A2-WHOLE-CONCEPT-1.0`
- Laser ports extracted: **16**
- Azimuth step: **22.500000°** (maximum error 0.000e+00°)
- Geometry scope: `WHOLE_SYSTEM_CONCEPT_LOD_MIXED_NOT_ALL_PARTS_DETAILED`

The port origins, outward normals, bore radii, wall thicknesses, and lengths are copied into `laser_geometry_audit.json` and the per-beam command template. The port-origin lever arm is only a geometry reference; physical torque requires the time-dependent absorption point.

## Four controls

1. **Rotational shear:** phase ordering and the torque equation are defined. Power, absorption, interaction location, target angular momentum, and a rotating-MHD/RHD stability calculation are still required.
2. **Foot/main pulse:** a piecewise foot/main waveform is defined, but energy, duration, delay, and allowable peak power remain blank until supplied by the laser system and hydro model.
3. **Asymmetry compensation:** each of the 16 CAD ports has baseline weight 1 and timing offset 0; calibrated weights/offsets are intentionally blank and must come from a 3-D ray trace plus radiation-hydrodynamics objective.
4. **Magnetic insulation:** the 14 T TF48 field is retained as the initial reference. The ideal flux-freezing relation is provided, but the compression-area history and transport suppression must come from radiation-MHD. Initial field/current was not increased, so the ripple and coil-load checks are not silently invalidated.

## Ripple prerequisite

- TF branch: `CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION`
- Edge ripple: **0.753916%**
- Limit: **1.0%**
- Gate: **True**

The strict project preflight clears the ripple prerequisite.
A model-derived TF branch, even if its standalone number is below the screening limit, is not treated as native/as-built evidence.

## Output disposition

`fusion_power_multiplier_applied = 1.0`; incremental power remains blocked pending a native laser-coupling/radiation-hydrodynamics/burn calculation. The generated files are therefore solver inputs and an audit trail, not a claim that these controls increased power.

See `laser_drive_strategy_input.json` for the machine-readable control contract and `laser_beam_command_template.csv` for the 16-beam fill-in table.
