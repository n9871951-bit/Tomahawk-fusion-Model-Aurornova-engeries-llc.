# Tomahawk G1 boundary repair and Kaggle evidence handoff

Revision: CAD-A2-WHOLE-CONCEPT-1.4-G1-TIGHT-ROUNDTRIP.

Revision 1.3 responds to two native FreeCAD 1.1.3 execution records. Rev1.1
passed ordinary BRep validity but BOPAlgo rejected both clamped seam edges as
`SelfIntersect`. Rev1.2 converted the carrier surface to native U- and
V-periodicity; the same two full-wrap free-form seam edges still failed.
Rev1.3 keeps the identical periodic surface but trims copies into a 4 x 16 grid
of 64 bounded faces and sews them into one shell. No face edge spans a complete
period, and no splitter-removal operation is allowed to collapse the repaired
topology. The changed builder identity forces a fresh boundary and audit
checkpoint; neither failed checkpoint is reused.

Rev1.3 then passed native BRep validity, one-solid closure, detailed BOP,
64-face topology, mesh topology, self-intersection, refinement, volume,
periodicity and seam-normal checks. Its only rejection was the STEP bounding-box
comparison: ordinary `TopoShape.BoundBox` reported 42.831 micrometres after
re-import even though round-trip volume error was zero. That property includes
stored shape-tolerance padding. Rev1.4 retains the 10 micrometre gate but
measures geometric bounds with `optimalBoundingBox(False, False)`. The
tolerance-inclusive difference remains reported as a diagnostic. The changed
audit source hash forces a fresh audit; the already verified Rev1.3 boundary
construction may be reused because its geometry and builder are unchanged.

## What is fixed

- Reconstructed the malformed plasma-boundary closure using a helical formula recovered from 8,001 retained interpolation sites in the supplied STEP.
- Rebuilt a smooth, rotationally consistent tensor-product cubic spline, with matching values and first/second derivatives at the seams, represented by 64 sewn bounded faces for native CAD robustness.
- Integrated the native G1 boundary audit into the single-file whole-model workflow.
- Made failed, missing and unrun mandatory G1 checks block assembly construction. Failed containment now enters the overall failure list.
- Enabled detailed native BOP checks by default.
- Preserved prior CAD inputs and Kaggle work. No Kaggle notebook, dataset, equation, gate or recorded pass count was changed or rerun.

The geometry repair is implemented and its mathematical checks have run. Native FreeCAD construction and its G1 audit have not run in this preparation environment. Formal interface acceptance and confinement validation are not implied.

## Run the updated Python file

Download `tomahawk_entire_model.py`. No separate input, ZIP extraction, network or pip installation is needed in FreeCAD.

Paste into FreeCAD's Python console:

```python
import runpy
from PySide import QtWidgets
script = QtWidgets.QFileDialog.getOpenFileName(None, "Select tomahawk_entire_model.py", "", "Python (*.py)")[0]
runpy.run_path(script, run_name="__main__") if script else print("Cancelled")
```

The default performs the repaired boundary audit first. Only if all mandatory boundary checks pass does it build the whole reactor/plant concept. The number of physical component definitions remains 269 reactor objects plus 34 plant-layout objects; boundary/reference/display objects are separate.

To check only the repaired boundary first, use the same launcher but replace its last line with:

```python
runpy.run_path(script, run_name="__main__", init_globals={"G1_ONLY": True}) if script else print("Cancelled")
```

That mode avoids building the remaining assembly. A later full run can reuse the verified boundary and mesh checkpoints. Neither mode reruns Kaggle work.

Results save under the actual Desktop, including Windows/OneDrive redirection:

`Desktop/Tomahawk_Whole_Model/CAD_A2_<timestamp>_<unique suffix>/`

The folder opens at completion. Return `Tomahawk_Whole_Model_Results.zip` for review. It contains nested G1 evidence as well as the assembly result record. Existing runs and source files are not overwritten.

## Root cause and recovery basis

The original STEP stores a 64 × 128 interpolation-site grid with chord-length parameters. The closing row and column coincide with the first. The preceding 8,001 sites match angular indices theta_i = 2 pi i/64 and phi_j = 2 pi j/128 and the helical formula below. The final unique row and column are absent; forcing closure across the enlarged last intervals produced the observed seam defects.

This diagnosis is recovered from the supplied CAD data. The original generating script and authoritative equilibrium coefficients were not retrieved. The repaired geometry is therefore a traceable CAD reconstruction, not a claim that an equilibrium solver has produced or approved it.

The fit used 6,400 sites, with 1,601 separate holdout sites. Maximum held-out coordinate residual was 3.531e-11 m. The reference volume was not an input to the fit.

## Recovered equations

For theta, phi in [0, 2 pi], define psi = theta - 16 phi:

\[
R(\theta,\phi)=R_0+a\cos\theta+\epsilon\cos(\theta-16\phi),
\]

\[
Z(\theta,\phi)=b\sin\theta+\epsilon\sin(\theta-16\phi),
\]

\[
X=R\cos\phi,\qquad Y=R\sin\phi.
\]

Recovered dimensions, displayed at meaningful precision:

| Parameter | Value |
|---|---:|
| R0 | 7.5 m |
| a | 3.0 m |
| b | 2.13896943244938 m |
| epsilon | 0.010 m |
| Toroidal periods | 16 |

The JSON retains the fitted full-precision coefficients; the CAD is not rescaled after fitting.

The exact volume of this recovered parameterization is

\[
V=2\pi^2 R_0(ab+\epsilon^2)\simeq950\ \mathrm{m^3}.
\]

Its agreement with 950 m³ follows from the recovered design definition. It is not independent physical validation.

## Numerical before/after evidence

| Quantity | Original STEP / previous audit | Repaired mathematical spline |
|---|---:|---:|
| Maximum sampled u-seam normal jump | 77.0356° | 5.00e-12° |
| Maximum sampled v-seam normal jump | 74.7307° | 2.78e-12° |
| Sampled seam position gap | 0 | At most 3.55e-15 m |
| Volume | 949.40777675 m³, prior integration reused | 949.99975231 m³ |
| Volume change | — | +0.0623521% |
| Sampled +22.5° correspondence error | Previous numerical nearest-surface maximum 42.24 mm | 1.124e-14 m |
| Spline versus recovered analytic formula | — | Maximum sampled error 1.323 micrometres |

The rotational before/after diagnostics use different metrics: the earlier number was nearest-surface projection after rotation, while the repaired number compares corresponding spline points. For the repaired surface, correspondence distance is an upper bound on nearest-surface distance at those samples. Neither sampled number is an exact global CAD-distance certificate.

Old-to-recovered-surface displacement was evaluated at 262,144 original surface samples: maximum 78.739 mm, RMS 5.436 mm and 99th percentile 25.685 mm. These are one-sided sampled distances to the recovered analytic surface, not a certified bidirectional Hausdorff bound. Local changes near malformed closure must not be hidden by the small volume change.

The delivered spline uses 64 unique poloidal and 256 unique toroidal sample intervals. Closure is appended correctly. Cubic periodic interpolation enforces matching endpoint derivatives. Exact knot insertion first creates ordinary clamped data on [0,1] x [0,1]; FreeCAD then converts the carrier to native U/V periodic form. Rev1.3/1.4 segment copies of that carrier into 4 x 16 exact sub-surfaces before sewing. Segmentation changes the topological representation, not the represented geometry.

## G1 acceptance logic

The native audit requires:

1. A valid single closed BREP solid and detailed BOP check.
2. Volume reconciliation with the declared reference.
3. STEP export/import roundtrip with volume and tolerance-free optimal bounding-box agreement; the tolerance-inclusive bounding-box difference is retained separately.
4. Independent surface meshes at 20, 10 and 5 mm linear deflection, with angular refinement.
5. One connected, consistently oriented, watertight genus-one mesh and no detected finest-mesh self-intersections.
6. Increasing mesh resolution, CAD/mesh volume agreement, and volume/area refinement convergence.
7. Sampled ±22.5° native rotational correspondence.
8. Retention of one valid closed imported solid/shell with at least 64 bounded faces.
9. Seam position and surface-normal correspondence on the unchanged periodic carrier surface.

The existing draft tolerances are retained: reference volume 1%; finest mesh/CAD volume 0.2%; last-two volume change 0.1%; last-two area change 0.2%; STEP volume relative error 1e-6 and bounding-box error 1e-5 m; rotation distance 1 mm. Added draft seam limits are 1 micrometre position and 0.01° normal angle. These are proposed screening values, not approval from Argonne or other consuming teams.

An assembly containment failure is now propagated to the failure list. A successful boundary audit does not certify all 269 component interfaces, seals, cooling-circuit continuity or whole-assembly interference freedom. The whole assembly must not be assumed 16-periodic: the four RF stations and varying poloidal port pattern differ from the plasma boundary's symmetry.

Important statuses:

| Status | Meaning |
|---|---|
| BLOCKED_G1_BOUNDARY_CHECKS | No assembly build after a failed/missing/unrun mandatory boundary check |
| FAILED_NO_APPROVAL | Exception; no acceptance |
| BOUNDARY_G1_NUMERICAL_PASS_ASSEMBLY_NOT_RUN | Boundary-only mode completed its numerical checks |
| COMPLETED_WITH_FAILURES | Assembly contains recorded failures; not accepted |
| COMPLETED_CONCEPT_BUILD_BOUNDARY_G1_NUMERICAL_PASS | Component build and boundary checks completed; not formal G1 or manufacturing approval |

Formal G1 remains `UNRESOLVED_PENDING_INTERFACE_REVIEW` until the producing/consuming interface record, coordinate convention, approved boundary authority and solver mapping are actually reviewed. The script cannot sign for other teams.

## Kaggle work retained

`Kaggle_Evidence_Register.md` and `.json` inventory 23 retrieved notebooks. Five contain inspected successful execution records; the other copies include unexecuted templates or recorded errors. Full notebook hashes and source-code hashes are preserved. The evidence bundle includes the original notebook bytes.

The verified records include the latest cassette correction, **6,974/10,935 = 63.7769%**, alongside the historical controlled 77.8935%, engineered 77.7778% and broad 6.1454% branches. The separate 30.092-minute secondary-systems computational POC is included. Earlier Rev2.2 screens, numerical audits, thermal/root/MHD-feasibility work, MCMC discussion, missing-input attempts and unresolved G3/transport requests are explicitly referenced with their evidence status.

The original notebooks were inspected, not rerun. Printed input hashes remain reported hashes unless the actual corresponding CSV was recovered. Not every historical executed artifact was found; the register identifies those gaps rather than fabricating evidence.

No cassette or coil dimensions were changed in this G1 repair. The prior A2 coil enlargement still needs field revalidation. The repaired plasma surface requires updated geometry-dependent optical/field/transport interfaces before older numerical results can be applied to it.

## Local tests and reproducibility

The local suite covers 24 assembly tests plus repair/integration tests, including source identity, held-out recovery, C2 seams, between-node rotational covariance, native knot/pole dimensional consistency, exact 4 x 16 parameter-domain coverage, containment-failure propagation, blocked assembly on failed G1, G1-only mode, embedded assets, notebook hashes and preserved counts. The exact executed count is written to `G1_Repair_Test_Record.json`. Native workflow branches use mocks because FreeCAD/OpenCASCADE is unavailable here; only your returned native record can prove the BOP result.

The evidence bundle includes the preparation script, recovered poles/knots, audit source, tests, all retrieved notebooks, the original corrected STEP, the previous CAD version and this revised source. NumPy/SciPy are preparation dependencies only. The user-facing `.py` uses FreeCAD and Python's standard library.

## Public method references

- [SciPy periodic spline interpolation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.make_interp_spline.html): endpoint value and derivative conditions.
- [FreeCAD geometry scripting](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Topological_data_scripting.md): native geometry and shape operations.
- [FreeCAD native shape checks](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Part/App/TopoShapePyImp.cpp): BOP/shape checking implementation.
- [OCCT closed free-form seam defect/workaround](https://github.com/Open-Cascade-SAS/OCCT/issues/1371): periodic conversion alone can retain the failure; splitting identical geometry into multiple edges is an effective workaround.
- [OCCT B-spline surface API](https://occt3d.com/dev/doc/refman/html/class_geom___b_spline_surface.html): periodic conversion, copying and exact parametric segmentation used by Rev1.3/1.4.
- [OCCT optimal bounding-box API](https://occt3d.com/dev/doc/refman/html/class_b_rep_bnd_lib.html): explicitly distinguishes shape-tolerance padding from underlying geometric bounds.
- [Open CASCADE shape validity criteria](https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html): geometric/topological validity is separate from physical validation.
- [Kaggle notebook documentation](https://www.kaggle.com/docs/notebooks): execution artifacts referenced in the evidence register.
