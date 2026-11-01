# Tomahawk whole-system CAD — CAD-A2 concept 1.4, tight-roundtrip G1 repair

Version 1.4 reconstructs the plasma boundary's malformed seams from 8,001 retained STEP interpolation sites, converts the carrier to native U/V periodic geometry, and represents it as a sewn 4 x 16 grid of bounded faces before the mandatory native G1 audit. Rev1.3 proved this removes the two BOPAlgo seam self-intersections and yields one valid closed 64-face solid. Rev1.4 corrects the remaining audit error by comparing STEP round-trip geometry with tolerance-free optimal bounding boxes while retaining tolerance-inclusive bounds as a diagnostic. The 10 micrometre gate and every design dimension remain unchanged. The original STEP remains embedded and is saved unchanged for comparison. See `G1_Repair_README.md` and `Kaggle_Evidence_Register.md`.

## Download and run ONE Python file

Use `tomahawk_entire_model.py`. It embeds the original corrected STEP, repaired spline definition, G1 auditor, Kaggle evidence register and all default dimensions. **No ZIP extraction, external input file, config file, internet access, or Python package installation is needed by the FreeCAD run.** This is plain Python, not a FreeCAD macro.

Open FreeCAD → View → Panels → Python console, then paste:

```python
import runpy
from PySide import QtWidgets
script = QtWidgets.QFileDialog.getOpenFileName(None, "Select tomahawk_entire_model.py", "", "Python (*.py)")[0]
runpy.run_path(script, run_name="__main__") if script else print("Cancelled")
```

Select the downloaded `.py` file. The script creates **two FreeCAD documents**: a reactor assembly and a whole-plant general arrangement. It finds the actual Windows Desktop, including OneDrive redirection, and saves to:

```text
Desktop / Tomahawk_Whole_Model / CAD_A2_<timestamp>_<unique suffix>
```

The output folder opens when finished. Existing source files, previous runs, and open documents are not overwritten. No results are uploaded anywhere by this script.

Ordinary system Python cannot build native FreeCAD geometry unless FreeCAD modules are configured there. `--preflight --output-parent <directory>` runs dimensional checks only. It never presents those checks as native CAD.

## What “whole model” means in this deliverable

All documented subsystem families are now represented, with **269 reactor component objects and 34 plant-layout objects**. This is a complete *concept/general-arrangement scope*, not every manufacturing detail of an entire power station.

| Area | CAD representation |
|---|---|
| Plasma | Periodically repaired EV007 boundary; original STEP retained separately |
| First wall | W armor, CuCrZr sink, separate high-temperature loop volume and backwall |
| Blanket | Inner containment, S20 aqueous breeder/moderator volume, outer containment |
| Shield/vessel | Separate shield envelope and ODS-FeCrAl-intent vessel |
| Magnets | 16 finite winding-pack envelopes plus individual casings; old filament paths retained hidden for comparison |
| Cryostat | Closed cylindrical enclosure and thermal-shield envelope, with geometric penetrations |
| Lasers | 16 hollow ducts, final-optic housing envelopes and window envelopes; two sets of eight poloidal positions |
| Fuel/diagnostics | Four service ducts |
| Exhaust | Four ducts plus 16 W tile/CuCrZr sink pairs; not solved strike surfaces |
| Blanket services | Four ducts starting inside the blanket, not the plasma |
| RF | Four complete concept stacks, grooved cores, separate covers, helium interspaces, headers, strap envelopes, sleeves |
| RF coolant | 128 square channels per cassette, connected-header coolant recipes, 4 taps per header, external collector routes |
| Cooling | Separate RF, blanket, high-temperature and helium supply/return rings |
| Structure | Foundation slab, 16 cryostat pedestals, 16 magnet supports, maintenance rail |
| Plant | 10 active/2 standby module envelopes, driver hall, RF/magnet power, cryoplant, fuel processing, vacuum/exhaust, hot cell |
| Power conversion | Heat-exchanger, turbine-generator, compressor/recuperator and heat-rejection equipment-space reservations |
| Secondary systems | Water recovery, lithium/brine recovery, reverse osmosis and thermal desalination space reservations |
| Other plant | Switchyard, controls/safety/diagnostics and utility corridors |

**Equipment envelopes do not contain pump impellers, turbine internals, fuel-processing machinery, electrical schematics or detailed process piping.** The reserve volumes are not capacity calculations, safety separation distances, licensed siting, or performance validation.

## Explicit changes from the earlier model

The original EV007 STEP is retained unchanged for comparison. Its SHA-256 remains:

`8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899`

The active plasma boundary is now a repaired spline, not those original bytes. Its native STEP hash is recorded at runtime. Its recovered helical formula uses R0 ≈ 7.5 m, a ≈ 3 m, b ≈ 2.13896943244938 m and epsilon ≈ 0.01 m, with 16 periods. It is not replaced by the surrounding elliptical vacuum envelope. The recovered formula comes from retained CAD data, not an independently supplied equilibrium solver definition.

The following dimensions are **new concept-packaging proposals**. They do not silently become approved design requirements.

| Quantity | CAD-A2 proposal |
|---|---:|
| Major radius | 7.5 m, retained |
| Inner vacuum-layout semiaxes | 3.30 m radial, 2.50 m vertical |
| Combined warm-layer semiaxis increment | 0.624 m |
| S20 blanket semiaxis increment | 0.400 m |
| Coil winding inner semiaxes | 4.074 m, 3.274 m |
| New winding centerline semiaxes | 4.199 m, 3.399 m |
| Legacy filament centerline semiaxes | 3.35 m, 2.45 m; comparison only |
| Winding profile semiaxis increment / toroidal width | 0.250 m / 0.250 m |
| Coil casing increment | 0.040 m |
| Cryostat outer diameter / height | 24.928 m / 8.328 m |
| Cryostat wall | 0.030 m |
| Laser duct bore diameter / wall | 0.200 m / 0.010 m |
| Optical global phase / spacing | +5.625° / 22.5° |
| RF front-face radius | 10.75 m |
| Cassette area / count | 2.5 m² / 4 |
| Channels per cassette | 128, square 16 × 16 mm |
| Cassette face width / height | 1.078516 m / 2.318 m |
| Core skin / ligament / cover | 2.5 mm / 2 mm / 3 mm |
| Header width / depth / wall | 0.140 m / 0.120 m / 0.006 m |
| Header taps | Four per side, 0.100 m bore diameter |
| Core + headers + sleeve-frame width | 1.418516 m |
| Remaining side clearance in 1.47 m screening bay | 25.742 mm each side |
| Plant module pitch | 36 m, footprint proposal only |

The old filament coils cannot simply remain embedded inside a new blanket/vessel stack. The larger candidate winding envelopes therefore change the coil geometry. **A new field/current fit and equilibrium/confinement assessment are required.** No current density, critical current, 35 T performance, magnet stress, or field map is assigned from these dimensions.

The 0.400 m blanket proposal is not inferred from the old 0.2687 m first-collision result, and it does not imply TBR ≥ 1.15. S20 aqueous remains the active material-family reference; no FLiBe branch is introduced. Full isotope composition and material-property cards remain separate required inputs.

## Equations used to construct the concept geometry

All recipe dimensions are metres. Native FreeCAD lengths are millimetres: `x_CAD = 1000 x_m`; `V_m³ = V_CAD_mm³ / 10⁹`.

For the surrounding elliptical layout, not the frozen EV007 surface:

```text
R(θ) = R0 + a cos(θ)
x(θ,φ) = R(θ) cos(φ)
y(θ,φ) = R(θ) sin(φ)
z(θ) = b sin(θ)
V_elliptical_torus = 2 π² R0 a b
```

A radial layer uses `a_outer = a_inner + δ`, `b_outer = b_inner + δ`, with the inner torus subtracted from the outer torus. **δ is an increment of semiaxes, not constant normal wall thickness.** Port/sleeve openings are then subtracted. These axisymmetric envelopes require reconciliation to EV007; they are not conformal first-wall offsets or a solved magnetic boundary.

The finite coil profile is an elliptical annulus in its radial–vertical plane, extruded through a finite toroidal width. The casing subtracts that pack volume from a larger annular envelope. This is a packaging model, not individual turns or conductor tape.

```text
A_coil_profile = π (a_outer b_outer − a_inner b_inner)
V_pack = A_coil_profile × toroidal_width
φ_coil,j = 22.5° j
φ_laser,j = 5.625° + 22.5° j
```

Laser layout directions use the normalized local ellipse normal. They extend to the first intersection with either the cryostat cylindrical side or end plate. Pipe wall geometry subtracts an inner cylinder from an outer cylinder. No ray refraction, target coupling, dynamic focus, optical qualification or vacuum-window stress is computed.

```text
n_R ∝ cos(θ) / a
n_z ∝ sin(θ) / b
V_straight_pipe_wall = π (r_outer² − r_inner²) L
```

The cassette uses the square-channel geometry carried forward from the corrected area model:

```text
H = N d + (N − 1) s + 2 e
W = A_face / H
L_channel = W
D_h = 4 d² / (4 d) = d
A_flow = N d²
A_wetted,geometric = N (4 d) L_channel
```

Manifolds and nozzle cavities are explicit boolean volumes, not an HTC multiplier. Recipe-level connectivity is defined; native boolean validity and one connected coolant solid still need to be confirmed on the FreeCAD run. The new flow path invalidates automatic use of historical cassette pass percentages.

## Outputs from FreeCAD

- `Tomahawk_reactor_CONCEPT.FCStd` and `Tomahawk_plant_CONCEPT.FCStd`.
- `Tomahawk_reactor_CONCEPT_FULL.step` and `Tomahawk_plant_CONCEPT_FULL.step`.
- Separate STEP exports for each reactor subsystem, including the identifiable fluid regions where present.
- `FreeCAD_reactor.png` and `FreeCAD_plant.png` when graphics export is available.
- Component register, settings, full CSG recipe definition, dimensional checks, build/error report, progress, hashes.
- Original STEP, repaired STEP, integrated G1 reports and surface meshes, recovery/displacement record, and Kaggle evidence register.
- `Tomahawk_Whole_Model_Results.zip` for returning the actual run results.

The reactor full-material STEP excludes the plasma reference and fluid-domain objects; named subsystem exports retain those fluid regions. They must not be mistaken for metal in a downstream material map. The full STEP is exported **before** display cutaways are made. The FCStd includes clearly named display-only cutaway clones; do not export those as transport geometry.

All solids are generated as `Part::Feature` objects. Dimensions are controlled by `SETTINGS` at the top of the Python script. The document is not a fully constrained sketch/PartDesign manufacturing feature tree.

## Restart and validation behavior

Heavy boolean and revolved/extruded shapes are cached by recipe, geometry-engine code hash and FreeCAD/OpenCASCADE/Python versions. Version 1.1 also recognizes the exact reviewed 1.0 cache signature for unchanged recipes. Mismatched or incomplete cache records are rebuilt. The repaired boundary and G1 audit have separate checkpoints. The builder revision, source hash, topology identifier and 4 x 16 grid prevent either failed single-face result from being reused. Rev1.4 can reuse the valid Rev1.3 boundary STEP, but its changed audit-source hash forces the corrected round-trip audit to execute. Monte Carlo, MCMC and physics jobs are not repeated. Do not run two instances simultaneously into the same output parent.

The first build may take time on the host CPU because it has actual channel/manifold booleans and many penetrations. It has no fixed runtime guarantee and uses no GPU solver. Progress prints each component. A failed component remains a failure in `build_report.json`; it is not silently omitted from a successful-build claim.

Detailed per-object BOP checks now default ON (`strict_bop_checks=True`). The mandatory boundary audit checks BREP/BOP validity, STEP roundtrip, three mesh refinements, topology, self-intersections, normals and sampled periodicity. Missing or failed gates block the full assembly build. Failed plasma containment enters the assembly failure list. **A boundary numerical pass is not formal G1 approval or proof of complete assembly interference freedom, pressure-tight joins, circuit continuity or structural safety.** Interface review and manufacturing/solver preparation remain distinct.

The local suite includes the original 24 assembly/software tests plus recovery, spline, provenance, 4 x 16 partition and fail-closed workflow tests. The exact count is written to `G1_Repair_Test_Record.json`. Native workflow branches are tested with mocks; they are not native CAD tests. **FreeCAD/OpenCASCADE is not installed in the preparation environment, so native solid generation and STEP/FCStd exports have not been run here.**

Earlier CAD-A2 preview images depict the pre-repair boundary and remain historical concept views, not screenshots of a completed native build. The updated native run produces new images when graphics export is available.

## Public method references and design provenance

User sources: corrected Rev3.4.1 SIS and Design Update govern the current plasma/material branch. Rev2.1 Architecture pages 3–6 supply the 10+2 hub topology and broad subsystem inventory only; its old performance targets are not asserted as achieved. The CAD-A1 square-channel candidate and original EV007 files are preserved.

[FreeCAD's official geometry documentation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Topological_data_scripting.md) defines primitive, ellipse and boolean scripting. Its [native shape implementation](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Part/App/TopoShapePyImp.cpp) provides the cut/fuse, BREP and validity APIs used here.

[ITER's cryostat description](https://www.iter.org/machine/cryostat) provides system-level context for surrounding enclosure and penetrations; no ITER dimensions are imported as Tomahawk requirements.

[INL's CAD-based fusion workflow](https://salamander.inl.gov/verification_validation_examples/cad_workflow/cad_workflow.html) illustrates that CAD geometry must still be meshed and coupled to transport/thermal solvers. Producing this concept CAD does not perform those steps.

Design-specific geometry is a controlled research proposal. Generic methods are public references; this deliverable changes no IP, royalty or publication agreement and is not a regulatory or construction authorization.
