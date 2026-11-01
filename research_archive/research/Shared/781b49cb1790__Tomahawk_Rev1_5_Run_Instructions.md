# Tomahawk Rev1.5 — G1, union geometry, sweeps, and solver exports

Model marker: `CAD-A2-WHOLE-CONCEPT-1.5-G1-UNION-SWEEP-EXPORT`

Rev1.5 carries forward the Rev1.4 periodic 4 × 16 sewn-patch G1 repair. It changes each connected RF collector plus ring branch from a non-Boolean compound to a Boolean union. It removes the obsolete disjoint filament comparison object. It deliberately does **not** fuse the entire reactor into one solid because CFD, MHD, thermal, and neutronics workflows require identifiable material and fluid interfaces.

## Fastest G1-only run in FreeCAD GUI

Use `Tomahawk_Rev1_5_FreeCAD_Copy_Paste_Launcher.txt`. It verifies the internal revision marker, runs the G1 audit only, enables the simulation-prep package, and rejects the older one-face build.

Successful numerical G1 evidence must report all of the following in `build_report.json`:

- `native_execution`: `BOUNDARY_G1_NUMERICAL_PASS_ASSEMBLY_NOT_RUN`
- `g1_audit.status`: `PASS_PROPOSED_NUMERICAL_CHECKS`
- `g1_audit.surface_topology`: `U_AND_V_NATIVE_PERIODIC_SEWN_4X16_PATCHES`
- `g1_audit.brep_counts.Faces`: `64`
- `g1_audit.brep_counts.Edges`: `128`
- every required `g1_audit.checks.*.status`: `PASS`

Formal G1 engineering approval remains separate from this numerical pass.

## Command-line use

Replace the FreeCADCmd path if FreeCAD is installed somewhere else.

```powershell
& "C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe" "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_5_G1_Union_Sweep_Export.py" --g1-only --simulation-prep --output-parent "C:\Users\YOUR_NAME\Desktop"
```

Full native model after G1 passes:

```powershell
& "C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe" "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_5_G1_Union_Sweep_Export.py" --full --simulation-prep --output-parent "C:\Users\YOUR_NAME\Desktop"
```

Ordinary Python angle sweep (FreeCAD not required):

```powershell
python "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_5_G1_Union_Sweep_Export.py" --sweep-only --toroidal-phase-sweep "0,2.8125,5.625,8.4375,11.25" --poloidal-scale-sweep "0.90,0.95,1.00,1.05,1.10" --output-parent "C:\Users\YOUR_NAME\Desktop"
```

The sweep writes CSV, JSON, SHA-256 manifest, and ZIP outputs. It is a static 16-port geometry/clearance preflight; it does not claim absorbed-fluence, compression, MHD, instability, or dynamic-focus validation.

## Simulation-prep contents

`--simulation-prep` writes `Tomahawk_Simulation_Prep.zip` and a solver-region map. A full native run includes the available multi-region STEP/FCStd files. A G1-only run contains the repaired boundary and model definitions. The manifest labels routes for MHD/confinement, optical ray tracing, CFD/conjugate heat transfer, and neutronics without inventing solver results.
