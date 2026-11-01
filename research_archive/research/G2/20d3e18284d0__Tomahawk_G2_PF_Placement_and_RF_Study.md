# Tomahawk G2 PF placement and RF study

Based on the exact 16 T, 16-field-period MGRID (SHA-256 `afb07089205aa3d2cdfa03d53b48298ae5092f23c0e70db72938c21f59a78013`) and the force-balanced 1.329 MPa L12 high-pressure equilibrium. The TF coil configuration and current, 578 PF turns, six signed PF group currents at 0.5 nominal, iota profile and toroidal flux are unchanged. The source PF CSV is preserved.

## Placement screen

The circular-loop field calculation reproduces the six exact-MGRID PF boundary-response columns with relative errors between 0.000009 and 0.000054. Each trial shifts whole PF packs while preserving internal turn spacings and upper/lower symmetry. The residual is the exact saved high-pressure normal-field residual plus the computed PF field difference. The new full MGRID has **not** been generated.

| Placement | Maximum normalized normal error | RMS | Closest PF-to-TF centerline | Result |
|---|---:|---:|---:|---|
| Original | 0.081301 | 0.050655 | 0.667 m | Fails ≤0.001 |
| Mirrored moves up to 0.5 m | 0.080612 | 0.049752 | 1.167 m | Fails |
| Mirrored moves up to 1.0 m | 0.079748 | 0.048875 | 1.164 m | Fails |
| Wider seven-start search | 0.077845 | 0.047477 | 0.464 m | Fails |

The best wider case moves the paired inner coils radially about +0.071 m and 1.5 m toward the midplane; paired outer coils 2.0 m inward and 2.0 m away from the midplane; middle-inner 1.0 m inward; and middle-outer 1.5 m outward. It leaves 77.8 times the normal-field gate. Several moves sit at the search bounds. Its minimum sampled PF turn-center to plasma-surface distance is 1.691 m. Clearance is to TF **centerlines**, not to the TF winding pack, insulation or services; this is not an approved coil layout.

The supplied `broad_best_PF578_turn_placement.csv` and 1.0 m candidate are reviewable placement files, not selected production geometry. The inverse-target file includes 555 boundary nodes and the required pointwise normal-field correction (maximum magnitude 1.839 T). Current placement translations show insufficient control; the next PF design pass must change the winding topology/control authority or revisit the target equilibrium before a geometry revision is chosen.

## RF scenario to include in the geometry pass

The existing four side-launch cassette envelopes stay at their recorded positions with reference 107.4 MHz. On the exact field map at their common 11.25° field-period phase, the midplane field near R=7.5 m is 16.001992 T. At 107.4 MHz the calculated D fundamental layer is at R≈8.522 m and T fundamental at R≈5.690 m. Thus the reference frequency does place two off-axis resonances inside the plasma.

A **frequency study candidate** of 122.037 MHz places the D fundamental near R=7.5 m in the present field; a separate 81.488 MHz option places the T fundamental there. The four-station `RF4_central_D_frequency_candidate.csv` records the first option without moving antenna envelopes. The first option also places a T second-harmonic layer near R≈10.01 m, which may affect power deposition from the existing low-field-side launch. These are resonance locations, not predictions of coupling, absorption, ion/electron heating, or electrical output. No helium minority is assumed.

RF frequency and launcher geometry should be screened with a full-wave D/T model and the new field map before choosing the hardware setting. Published ICRF design studies show that resonance position, launcher location and antenna spectrum materially affect absorption: [SPARC physics basis](https://www.cambridge.org/core/journals/journal-of-plasma-physics/article/physics-basis-for-the-icrf-system-of-the-sparc-tokamak/22016DD64F3C5CAD47563A1E4AE59934) and [top-launch D/T study](https://doi.org/10.1088/1741-4326/adf569). RF is a profile/heating study here; it has not been credited as a reduction of the G2 boundary residual.

## Sequence

1. PF placement investigation completed for the original six current groups. The supplied candidate coordinates allow CAD review, but none satisfies G2. Redesign the PF winding/control topology before selecting a final placement.
2. Revise plasma/CAD geometry and RF cassette placement against that selected field design, while preserving the 1.329 MPa pressure and declared gate checks.
3. Generate the full 16 T MGRID from the final TF/PF geometry, then rerun finite-pressure equilibrium, boundary-pressure/normal-field, ballooning, and RF deposition checks. The new MGRID is deliberately deferred until the geometry exists.

## Files

The ZIP carries the exact starting PF and TF centerline CSVs, the placement candidate CSVs, the four-station RF frequency study CSV, all JSON and residual results, the inverse target, scripts and the high-pressure L12 equilibrium. It omits the 651 MB input MGRID, which remains in `Tomahawk_G2_Corrected_Input_v2.zip`.
