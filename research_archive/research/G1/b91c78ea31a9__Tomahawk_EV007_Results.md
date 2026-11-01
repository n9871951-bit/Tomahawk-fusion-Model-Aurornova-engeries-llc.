# Tomahawk EV007 — computed boundary results

These are results for the reuploaded `ev007_boundary_units_corrected.step`, not a report from the user's local FreeCAD session. Its bytes match the prepared unit correction exactly. Its entire geometry is unchanged from the original, so the completed independent integration is reused with metre units; no plasma simulation was rerun.

![EV007 boundary](Tomahawk_EV007_Boundary_Results.png)

## Quantitative findings

| Quantity | Result |
|---|---:|
| Integrated volume, corrected metre interpretation | 949.40777675 m³ |
| SIS reference volume | 950 m³ |
| Volume below reference | 0.06234% |
| Sampled overall height | 4.29782 m |
| Sampled overall x extent | 21.05621 m |
| Finest sampled triangular surface | 524,288 triangles |
| Finest surface-volume error vs integration | 0.00784% |
| Sampled parameter-endpoint gaps | 0 in both parameter directions |

Lengths/extents are sampled, not certified CAD bounding-box extrema. A zero endpoint gap does not test self-intersections, normal continuity, engineering clearances, or magnetic periodicity.

## Surface discretization convergence

| Triangles | Volume (m³) | Difference from integrated volume |
|---:|---:|---:|
| 32,768 | 948.182304 | 0.12908% |
| 131,072 | 949.106442 | 0.03174% |
| 524,288 | 949.333348 | 0.00784% |

Per-knot 3- and 5-point Gauss integration gives 949.40780305 and 949.40777675 m³, respectively. These are numerical integration consistency checks, not physical measurement uncertainty or independent solver validation.

## What was corrected

The original STEP uses millimetre length units with coordinate magnitudes appropriate to the metre-scale SIS design. As declared, its integrated volume is approximately 9.49407776753e-07 m³. Changing the known file's length-unit declaration to metres gives 949.40777675 m³ while retaining every coordinate and shape parameter. Lengths increase by 1,000 and physical volume by 1,000,000,000. Nothing was fitted to exactly 950 m³.

Original SHA-256: `871c8dc94ccff5b390cbd6d07a30eb2367e238edbefa8b66a042fecfb4a35764`.

Current corrected STEP SHA-256: `8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899`.

## G1 result

The unit inconsistency has been corrected in a separate file, and the numerical volume agrees closely with the stated reference. **Formal G1 remains unresolved**: this result does not include native FreeCAD/OpenCASCADE BREP validity, BOP checks, a native mesh self-intersection test, a verified 16-period cross-solver mapping, or the required producing/consuming team review.

FreeCAD's [official shape-check implementation](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Part/App/TopoShapePyImp.cpp) performs separate native geometry checks. A visually closed toroidal surface and a converged volume alone do not substitute for those tests.

No confinement duration, stability margin, fusion output, or cassette heat-load improvement was computed in this geometry audit. No geometry design changes beyond the unit correction were made.

To establish the native CAD outcome, return the generated `Tomahawk_G1_Evidence.zip` from the FreeCAD Python run. That is a different result from the downloadable Python code package.
