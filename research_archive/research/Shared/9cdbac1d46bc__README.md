# Tomahawk G1 — plain Python script

Version 1.2: results save to **Desktop → Tomahawk_G1_Results → Run_...**, and verified checkpoints avoid repeating completed native checks. On Windows, the system's actual Desktop location is used, including OneDrive redirection. No macro installation or `.FCMacro` file is required. Inputs and previous runs are never overwritten.

## Run with FreeCAD's Python console — full CAD checks

1. Download the updated `tomahawk_g1.py`. Either the reviewed original STEP or `ev007_boundary_units_corrected.step` is accepted.
2. In FreeCAD select **View → Panels → Python console**.
3. Run this file-picker launcher; no typed file path is needed:

```python
import runpy
from PySide import QtWidgets
script = QtWidgets.QFileDialog.getOpenFileName(None, "Select updated tomahawk_g1.py", "", "Python files (*.py)")[0]
runpy.run_path(script, run_name="__main__") if script else print("Cancelled")
```

A second file picker asks for the STEP. Select your original **or corrected** STEP. The corrected file is recognized by hash and is **not scaled again**.

Results are written to a new `Run_<date>_<time>_...` folder beneath `Desktop/Tomahawk_G1_Results`. The folder opens at completion. Open **RESULTS.html** to read the checks; return **Tomahawk_G1_Evidence.zip** for review. A `boundary_preview.png` is also saved when FreeCAD's image capture succeeds. No file is uploaded to an external service by this script. If your Desktop is synced by OneDrive, your own sync settings still apply.

## Resume instead of repeat

- BREP validity/BOP checks, native exports and STEP roundtrip, each mesh resolution, mesh exports, and sampled periodicity have separate checkpoints.
- Each completed stage is committed atomically. If a run is interrupted, completed checkpoints remain available to the next run. Do not run two copies concurrently.
- A checkpoint is reused only when canonical corrected-geometry hash, numerical settings, audit-code hash, FreeCAD/OCC/Python versions and platform match. Saved payloads and artifact files must also pass SHA-256 checks.
- If all native checks finished, the next matching run restores the saved outputs instead of rerunning the native audit. A failed numerical result stays failed; reuse does not promote it to a pass.
- `progress.json` is updated after every completed/reused stage. `RESULTS.html` also lists the stage actions. `REUSED_VERIFIED_CHECKPOINT` means saved work was reused; `COMPUTED_AND_CHECKPOINTED` means a stage ran now.
- Keep the `Checkpoints` folder beside the run folders. Changed inputs/settings/audit implementation/runtime invalidate the cache conservatively; missing or damaged stage evidence is recomputed.
- Lightweight source/hash verification and report packaging still run. This avoids silently accepting altered files.
- Earlier independent volume calculations are not rerun or relabeled as native FreeCAD checks. Older runs without these verified checkpoints cannot be assumed complete: retain their evidence ZIP for review. This first checkpoint-enabled native run must perform any checks for which no compatible checkpoint exists.

Neither downloading the script nor importing a STEP means a native audit completed. The progress file and evidence report distinguish these states.

For an explicit source and destination instead of the picker:

```python
import runpy
runpy.run_path(r"C:/your-folder/tomahawk_g1.py", run_name="__main__", init_globals={"INPUT_STEP": r"C:/your-folder/ev007_study_boundary_solid.step", "OUTPUT_PARENT": r"C:/your-folder/results"})
```

Forward slashes work in Windows Python paths. Linux/macOS users substitute their own absolute paths. No packages need to be installed in FreeCAD; this path uses its built-in `Part` and `MeshPart` modules.

## Run with ordinary Python — unit preparation only

```sh
python tomahawk_g1.py ev007_study_boundary_solid.step
```

This mode needs Python's standard library only. It creates the unit-corrected STEP, input hashes, a draft interface record and an evidence ZIP. It **does not** perform BREP or mesh validation unless FreeCAD's Python modules are available in that interpreter. A `NOT_RUN_FREECAD_UNAVAILABLE` result is intentional, not a geometry failure. Use the FreeCAD-console command above to perform the CAD checks without any macro setup.

## What was actually found in the uploads

- The STEP contains one `MANIFOLD_SOLID_BREP`, one closed shell and one B-spline face. These are file declarations, not a kernel validity result.
- Its length unit is `SI_UNIT(.MILLI.,.METRE.)`; a point at `(10.51, 0, 0)` is therefore 10.51 mm from the origin.
- The backup contains one `Part::Feature`, internally named `EV007_StudyBoundary_NOT_ASBUILT`, with label `EV007_study_boundary_ANALYTIC_NOT_CAD`. Its native document was saved by FreeCAD `1.1R20260725`.
- Against the SIS baseline of major radius 7.5 m and reference volume 950 m³, the reviewed coordinates support a metre/mm declaration mismatch.
- An independent numerical integration of the supplied B-spline surface gives approximately **949.40778 coordinate-units³**. The source declares those units to be millimetres, so this means approximately 0.000000949408 m³ as uploaded; after the unit correction, approximately **949.40778 m³**. The difference from 950 m³ is about **0.06234%**. This is not a FreeCAD/OpenCASCADE volume result.

The script changes only the known STEP's length-unit declaration from millimetres to metres. All coordinate data, topology records and shape parameters remain unchanged. The declared STEP accuracy scales with its length unit as well. There is no volume fitting, smoothing, gap filling, port addition, or change to the plasma equilibrium.

The change is locked to source SHA-256:

```text
871c8dc94ccff5b390cbd6d07a30eb2367e238edbefa8b66a042fecfb4a35764
```

The already-corrected hash `8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899` is also accepted unchanged. Any other file is rejected instead of guessed at or rescaled. The backup is inspected as XML only; its geometry has **not** been proven identical to the STEP.

## Full FreeCAD audit and outputs

When launched in FreeCAD, the script:

- Imports the corrected STEP using FreeCAD's internal millimetre convention.
- Checks shape validity, a single closed solid/shell, and the more detailed BOP check.
- Saves a new `ev007_candidate_boundary.FCStd`, a millimetre BREP, and a STEP roundtrip.
- Reimports that STEP and compares volume and bounding box.
- Generates separate surface meshes at 20, 10 and 5 mm absolute deflection; angular deflection is also refined.
- Checks boundary edges, vertex/edge manifoldness, duplicate/degenerate triangles, connectedness, toroidal genus, adjacent orientation, and signed volume. Only exactly coincident vertices are identified; gaps are not welded shut.
- Reverses every triangle together only when an otherwise closed, consistently oriented mesh has negative signed volume. It does not patch locally inconsistent normals.
- Requests FreeCAD's finest-mesh self-intersection check.
- Compares mesh volume to CAD volume and volume/area changes across refinements.
- Samples rotational correspondence at ±22.5° against the CAD **shell**, not the solid interior. This is a sampled diagnostic, not exact symmetry certification or proof that 16 is the fundamental period.
- Exports `boundary_surface_m.vtk` and `boundary_surface_m.json` with coordinates in **metres**. JSON triangle indices are zero-based; the boundary region is `EV007_plasma_boundary`.
- Writes `RESULTS.html`, `g1_report.json`, `g1_interface_review.json`, `sha256_manifest.json` and `Tomahawk_G1_Evidence.zip` to the Desktop results folder, plus a preview when available.

If a BREP check fails, downstream mesh generation stops. If a mesh check fails, exported candidate meshes remain clearly unapproved in the report. No runtime estimate is promised for the detailed BOP, meshing or distance checks; they run locally and require no GPU or allocation.

## Numerical windows are proposed, not approved gate criteria

The SIS did not supply numerical G1 tolerances in its closure section. The script records these draft screening settings explicitly:

| Check | Proposed window |
|---|---:|
| CAD volume vs 950 m³ reference | ≤1% relative difference |
| Finest mesh vs CAD volume | ≤0.2% relative difference |
| Last two mesh volumes | ≤0.1% relative change |
| Last two mesh areas | ≤0.2% relative change |
| STEP roundtrip volume | ≤10⁻⁶ relative difference |
| STEP roundtrip bounding coordinates | ≤10⁻⁵ m maximum difference |
| Sampled ±22.5° surface correspondence | ≤1 mm maximum sampled distance |
| Topology | One watertight, manifold, consistently oriented genus-one surface |

Smaller deflections do not establish independence on their own; the script also requires triangle counts to increase at each level. Approve task-specific windows before using the results as acceptance evidence. Do not loosen windows just to obtain a pass.

## What closes G1

This is the **project G1 topology/interface gate**, not the CAD term for tangent continuity. SIS Rev3.4.1, printed pages 6–7, requires a controlled CAD-derived watertight mesh, approved coordinates and normals, periodicity, volume reconciliation, mesh-independence evidence and a signed producing/consuming team interface-control record.

Successful CAD checks can support that review. They cannot establish that the analytic study surface is the approved engineering boundary, compare against missing EV007 solver coefficients, invent coil/first-wall/blanket interfaces, or provide other teams' signatures. Accordingly, the script can report `PASS_PROPOSED_NUMERICAL_CHECKS`, but **never grants formal G1 approval**. The formal status remains `UNRESOLVED_PENDING_INTERFACE_REVIEW`.

Send back the generated `Tomahawk_G1_Evidence.zip` for interpretation. Preserve the original failed or incomplete results when revising the geometry.

## Verification performed here

Twenty-two standard-library regression tests passed, including torus topology/volume, a missing triangle, reversed normals, duplicate facets, disconnected surfaces, invalid points, source preservation, prevention of double scaling, default Desktop output, unique run folders, corrected-input preservation, and a simulated Windows known-folder API contract. Checkpoint tests cover artifact restoration, changed-geometry/settings/runtime invalidation, payload/artifact tamper rejection, interrupted-stage recovery, unchanged failed results, and progress records. Ordinary-Python unit preparation also completed. The independent SciPy surface audit uses the actual STEP control net and knot intervals, with 32,768 / 131,072 / 524,288-triangle samples and 3- versus 5-point per-knot quadrature. Sampled volumes approach 949.40778 coordinate-units³.

**FreeCAD itself is not available in the preparation environment. Its native CAD path has not been executed here.** API calls were checked against official FreeCAD documentation/source. The independent audit requires NumPy/SciPy; the delivered main script does not.

Windows Desktop resolution and the screenshot API were not tested on an actual Windows/FreeCAD installation here. Desktop path logic was exercised using a simulated redirected folder and simulated API contract; it uses Microsoft's documented `SHGetKnownFolderPath` with `FOLDERID_Desktop`. No administrator token or folder redirection change is requested.

## Primary documentation

- [FreeCAD Python console](https://wiki.freecad.org/Python_Console)
- [FreeCAD scripting basics](https://wiki.freecad.org/FreeCAD_Scripting_Basics)
- [TopoShape implementation: validity, detailed checks, STEP/BREP export](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Part/App/TopoShapePyImp.cpp)
- [MeshPart implementation: meshFromShape arguments](https://github.com/FreeCAD/FreeCAD/blob/master/src/Mod/MeshPart/App/AppMeshPartPy.cpp)
- [FreeCAD Mesh API](https://wiki.freecad.org/Mesh_API)
- [Windows known-folder path API](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
- [Python SHA-256 hashing](https://docs.python.org/3/library/hashlib.html)

## Handling

The design-specific geometry and generated boundary coordinates remain controlled design material. Generic checking methods can be reviewed separately from the geometry under your publication/IP schedule. No license or publication permission is assigned by this script.
