# Tomahawk CAD-A1 — next assembly stage

This is a **partial CAD assembly and cassette packaging candidate**, not the completed reactor, a manufacturing release, or a G1 approval. It adds hardware geometry to the unchanged EV007 study boundary. No prior physics run is repeated and no old pass percentage is transferred to the new geometry.

## Run in FreeCAD Python — no macro, no typed file paths

1. Extract **all** files from `Tomahawk_CAD_A1_Python_Package.zip` into one folder. Do not run from inside the ZIP.
2. Open FreeCAD and enable **View → Panels → Python console**.
3. Paste this block; select `tomahawk_assembly.py` from that folder:

```python
import runpy
from PySide import QtWidgets
script = QtWidgets.QFileDialog.getOpenFileName(None, "Select tomahawk_assembly.py", "", "Python (*.py)")[0]
runpy.run_path(script, run_name="__main__") if script else print("Cancelled")
```

The corrected STEP and JSON settings beside the script are found automatically. If moved, a file picker asks for them. A plain system-Python interpreter does not contain FreeCAD: `--preflight` there checks dimensions only and produces no native CAD.

The builder opens a new assembly, leaves your existing documents unchanged, and saves to your actual **Desktop / Tomahawk_CAD_Assembly / CAD_A1_…** directory. Windows Desktop redirection, including OneDrive, is honored. The folder opens when finished. No remote upload is performed by the script.

## Geometry included

| Component | Representation | Authority / limitation |
|---|---|---|
| EV007 plasma | Imported original corrected STEP solid | Byte-identical; no scaling, smoothing or volume fitting |
| 16 coils | Exact elliptical centerline curves, 3.35 m × 2.45 m semiaxes | Existing G3 field-reference paths, not winding packs |
| 16 laser stations | Eight upper/eight lower layout-axis guides | Preserves poloidal sequence and 22.5° spacing; no bores or qualified rays |
| Four RF candidates | Grooved CuCrZr-intent cores and separate rear covers | Explicit 128 square channels per cassette; unqualified pressure/joining design |
| Coolant | 128 separate solid domains per cassette | Hidden initially; local domain STEP and boundary-center JSON exported |
| Legacy wall | Hidden revolved surface datum, scale 1.12 | Not an EV007 normal offset, wall layer or blanket |
| Original port alignment | Hidden zero-phase guides | Comparison record only; new candidate phase is +5.625° |

Coils and port guides are reference geometry, not material solids. The full assembly STEP name explicitly says `REFERENCE_ASSEMBLY`. Use the separate cassette exports to avoid treating the plasma/reference objects as solid hardware.

## An actual layout correction, kept separate from the old model

Constructing straight local-normal port guides at the old zero-degree phase places all 16 guides through their corresponding zero-thickness coil ellipses. This is a finding about **these constructed guides**, not proof that the previously unspecified real optical trains collide.

CAD-A1 proposes a **+5.625° global laser-station phase**. Coil locations and RF station azimuths stay fixed; port count and 22.5° spacing are unchanged. In the defined guide segments:

| Analytic geometric result | Value |
|---|---:|
| Zero-phase guides intersecting coplanar coil ellipses | 16 / 16 |
| Candidate minimum distance to any coil radial plane | 0.892335 m |
| Candidate minimum distance to a cassette bounding box | 0.527805 m |

The plane distance is a conservative lower bound to the zero-thickness coil curve, not a finite casing-clearance result. Segment-to-box distance is minimized over the entire guide segment, not only its endpoints. No port diameter, beam envelope, cryostat, support or wall/blanket penetration is included. The original model is preserved, and existing optical/field results are not inherited by this proposed port-layout change.

## Cassette dimensions and exact construction equations

The following values define an explicit, editable candidate. The 128-channel/16 mm/2–3 mm skin window comes from the earlier discussion, not a released manufacturing drawing. The ligament, edge and cover values below are **new CAD packaging proposals**.

| Input | Value | Status |
|---|---:|---|
| Face area per cassette | 2.5 m² | Existing reduced-order area |
| Channels | 128 square, one deck | Prior candidate window |
| Channel side / hydraulic diameter | 16 mm | Prior candidate window |
| Front skin | 2.5 mm | Within prior proposed 2–3 mm window |
| Interchannel ligament | 2 mm | New, not structurally qualified |
| End ligaments | 8 mm | New, not structurally qualified |
| Separate rear cover | 3 mm | New, not structurally qualified |
| Azimuths | 11.25°, 101.25°, 191.25°, 281.25° | Prior layout |
| Flat front-face mounting radius | 10.86 m | Legacy datum-based candidate, not approved wall interface |

Let N = channel count, d = square channel side, s = interchannel ligament, e = end ligament, A = face area, and t_f/t_r = front skin/rear cover. All equations below use metres.

```text
H = N d + (N − 1) s + 2 e              = 2.318 m
W = A / H                             = 1.078515962 m
L_flow = W                            = 1.078515962 m
t_total = t_f + d + t_r                = 0.0215 m
A_flow = N d²                         = 0.032768 m² / cassette
P_wetted,channel = 4 d                 = 0.064 m
D_h = 4 d² / (4 d)                    = d
A_wetted,geometric = N (4 d) L_flow    = 8.835202761 m² / cassette
V_coolant = N d² L_flow               = 0.035340811 m³ / cassette
V_core = A (t_f + d) − V_coolant       = 0.010909189 m³ / cassette
V_cover = A t_r                       = 0.007500000 m³ / cassette
V_core + V_cover + V_coolant           = A t_total
```

The channel direction is tangential across W, with 128 channels stacked vertically across H. This avoids assuming 128 × 16 mm channels can be packed side-by-side across a 1.47 m horizontal bay. The earlier bay width is only a screening envelope; it leaves 195.742 mm on each side of this **core**, before headers, fasteners, tolerances and replacement access.

The grooved core is one solid. The cover is a second touching solid, not an invented pressure-tight weld. Channels open through the left and right ends. **No external manifold is modeled.** The requested wetted perimeter exists geometrically, but uniform heat transfer to all four sides is not established. No area-efficiency or Nusselt multiplier is applied here.

The new 1.0785 m flow length and cover/ligament dimensions change thermal, hydraulic and structural inputs. None of the historical 6.15%, 63.7769%, or controlled-envelope pass rates validates this candidate.

## Outputs from a successful native run

- `Tomahawk_CAD_A1.FCStd` — editable document with grouped components and provenance properties. Change dimensions through JSON and rerun; it is not a full sketch-constrained PartDesign feature history.
- `Tomahawk_CAD_A1_REFERENCE_ASSEMBLY.step` — visible hardware candidates plus plasma and reference paths.
- `RF_Four_Cores_And_Covers_CANDIDATE.step` — four placed core/cover pairs only.
- `RF_Local_Core_And_Cover_CANDIDATE.step` — one local prototype pair.
- `RF_Local_128_Coolant_Domains.step` — separate square-channel domains, no manifold.
- `channel_interfaces_local_m.json` — channel inlet/outlet centers, normals, areas and placement convention; not solver boundary conditions.
- `assembly_report.json`, `layout_checks.json`, `dimensions.json`, `progress.json`, `manifest_sha256.json`, `RESULTS.html`.
- `FreeCAD_Assembly.png` — native screenshot when the graphics driver permits it.
- `Tomahawk_CAD_A1_Results.zip` — the new run evidence to return for review.

If construction fails, `assembly_report.json` records `FAILED_NO_APPROVAL` and the exact error. An invalid BREP is not silently repaired or assigned a pass. A layout clash may leave a completed reviewable assembly but its `geometry_checks_status` will be `FAIL`.

## What gets reused

No old G1 integration, mesh study, MCMC, confinement, or thermal screen is rerun. Component BREP checkpoints are keyed by the relevant component inputs, code hash and FreeCAD/OpenCASCADE/Python versions. Changing cassette dimensions retains unchanged plasma/coil checkpoints; moving a station retains the expensive channel-core template. Valid exports and interface results are reused. Tampered or incomplete checkpoints are rejected.

This workflow still imports cached BREP components into a fresh document and refreshes the display. Existing older G1 result folders have a different contract and are not misrepresented as assembly checkpoints. Do not run two instances concurrently in the same output directory.

## Work still needed to CAD the remaining systems

The recovered Rev3.4.1 records do not contain approved dimensions for first-wall layers, the S20 aqueous blanket container, vessel/supports, finite coil winding pack/casing/cryostat, RF dielectric/face stack, laser bores/optics, or external coolant headers. These are not fabricated from missing data. In particular, 0.2687 m first-collision depth is **not** used as blanket thickness, and the active blanket is **not FLiBe**.

Next design input: a dimensioned wall/blanket/vessel radial stack and a finite coil-pack section. Those are needed to replace the reference envelope and establish the available radial build. Full pressure, CHF, irradiation, joining/HAZ, fatigue, manufacturability and maintenance analyses remain separate work.

## Verification performed here

24 pure-Python tests passed: units, source hash, counts, exact packing/volume partition, layout distances, preserved pitch, conflict negative control, invalid input rejection, cache reuse/tamper handling and honest preflight status. The two preview PNGs were visually checked. The DXF is an actual generated 2-D millimetre layout, not a native 3-D export.

**FreeCAD/OpenCASCADE is unavailable in the preparation runtime. Native boolean construction, STEP exports and FCStd opening have not been executed here.** The supplied Python runs those checks on your FreeCAD installation; the test count does not imply native CAD validation.

## Source basis

- Your `Tomahawk_Design_Update_Rev3_4_1.docx`, pages 1, 3–6, and corrected SIS: component/reference inputs and explicit unresolved engineering interfaces.
- Your `ev007_boundary_units_corrected.step`, SHA-256 `8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899`.
- [FreeCAD's official topological-data scripting documentation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Topological_data_scripting.md): ellipse construction, boxes, compounds, transformations and boolean operations.
- [FreeCAD's official screenshot scripting documentation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Std_ViewScreenShot.md): Python screenshot export.
- [Microsoft's SHGetKnownFolderPath documentation](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath): current-user Desktop resolution.

Design-specific geometry/configuration is intended for your controlled technical workflow. Generic API methods are public documentation; no IP or publication agreement is changed by this package.
