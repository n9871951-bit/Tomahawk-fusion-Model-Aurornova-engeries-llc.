# Tomahawk Rev1.7 multiphysics preparation package

This package fixes the “CAD completed but no simulation ran” failure mode. It contains two separate Python entry points:

1. `Tomahawk_Rev1_7_Multiphysics_CAD_Export.py` runs in FreeCAD/FreeCADCmd. It performs the repaired EV007 G1 numerical gate, builds the whole concept geometry, and—when `--multiphysics-prep` is supplied—exports named MHD, neutronics, and CFD/CHF regions plus the equation/input/output contract.
2. `tomahawk_multiphysics_run.py` runs in ordinary Python. It checks that the CAD preparation is complete, then runs MHD -> neutronics -> CFD/CHT -> CHF in one continuous, single-folder pipeline. Each stage must return zero and produce a declared output before the next stage starts. It is fail-closed: missing inputs, solver executables, or outputs produce `BLOCKED_*` statuses instead of synthetic “results.”

When the Rev1.7 CAD file is launched from the FreeCAD GUI with no command-line arguments, it now defaults to the complete one-folder CAD plus multiphysics-preparation path.
For the least ambiguous handoff, use `TOMAHAWK_REV1_7_RUN_THIS.py`; it is the same verified standalone script under a unique filename and prints `TOMAHAWK_REV1_7_ALL_IN_ONE_ACTIVE` at launch.
Its resulting `build_report.json` also records `model_version: CAD-A2-WHOLE-CONCEPT-1.7-MULTIPHYSICS-DOMAINS` and `all_in_one_path: true`.

`Tomahawk_FreeCAD_Multiphysics_Launcher.py` is the short GUI-console launcher. Use it when the FreeCAD console reports a syntax error after a pasted command. Do not paste the large CAD file itself; select it through the launcher's file dialog.

## 1. Build the solver-ready CAD package

Windows PowerShell example (change the FreeCAD path and output directory):

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" `
  "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_7_Multiphysics_CAD_Export.py" `
  --full --multiphysics-prep `
  --output-parent "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_7"
```

The successful result folder must contain:

- `build_report.json` with `assembly_build_accepted: true`;
- `g1_audit.status: PASS_PROPOSED_NUMERICAL_CHECKS`;
- `Tomahawk_Multiphysics_Physics_Contract.json`;
- `Solver_Geometry/` with the named STEP regions and boundary seed JSON;
- `Tomahawk_Simulation_Prep.zip` and `simulation_prep_manifest.json`.

The CAD run is preparation only. It does not run VMEC/MHD, OpenMC/DAGMC, NekRS/CFD, or CHF.

### FreeCAD GUI console method

Open FreeCAD's Python console and paste only this short command, after placing both `.py` files in the same directory:

```python
import runpy; runpy.run_path(r'C:\Users\YOUR_NAME\Desktop\Tomahawk_FreeCAD_Multiphysics_Launcher.py', run_name='__main__')
```

The launcher opens a file picker. Select `Tomahawk_Rev1_7_Multiphysics_CAD_Export.py`. It calls the script's `run()` function directly and therefore avoids FreeCAD's own command-line arguments.
It verifies the embedded version marker and stops immediately if an older `tomahawk_assembly.py` or CAD-A1 script is selected.

If you open `tomahawk_multiphysics_run.py` from FreeCAD with no arguments, its interactive fallback shows a results-folder picker and starts the continuous pipeline. It reads `Tomahawk_Continuous_Run_Config.json` from that folder. If the config is absent it writes `Tomahawk_Continuous_Run_Config.template.json` and stops, so commands and real inputs can be filled once rather than re-entered for every stage.

## 2. Configure and run the continuous pipeline

Copy `Tomahawk_Continuous_Run_Config.template.json` into the CAD_A2 folder as `Tomahawk_Continuous_Run_Config.json`, then replace every `null` command and every placeholder input path with the real files on the machine. Commands may be JSON lists (recommended on Windows) or command strings. For NEUTRONICS, CFD, and CHF, set `consumes_previous_output: true` and include `{previous_output}` in the command, or set `consumes_previous_output_via_manifest: true` when the solver reads `stage_input_manifest.json` itself.

Example command shapes inside the JSON config:

```json
"command": ["C:/path/to/vmec2000.exe", "{mhd_input}"],
"command": ["C:/path/to/openmc.exe", "-s", "{settings}", "{previous_output}"],
"command": ["C:/path/to/nekrs.exe", "{cfd_case}", "{previous_output}"],
"command": ["python", "chf_postprocess.py", "{previous_output}"]
```

Run the single pipeline:

```powershell
py .\tomahawk_multiphysics_run.py `
  --results-folder "C:\Users\YOUR_NAME\OneDrive\Desktop\Tomahawk_Whole_Model\CAD_A2_..."
```

Outputs are kept under one folder, `Tomahawk_Continuous_Run\01_MHD`, `02_NEUTRONICS`, `03_CFD`, and `04_CHF`. Each stage writes a log, `stage_input_manifest.json`, `stage_output_manifest.json`, and a handoff path for the next stage. The final record is `Tomahawk_Continuous_Run\physics_run_report.json`.

## 3. Preflight before launching any solver

```powershell
py .\tomahawk_multiphysics_run.py `
  --results-folder "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_7\CAD_A2_..." `
  --preflight
```

If a directory contains old reports, select the intended report explicitly:

```powershell
py .\tomahawk_multiphysics_run.py `
  --results-folder "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_7\CAD_A2_..." `
  --build-report "C:\Users\YOUR_NAME\Desktop\Tomahawk_Rev1_7\CAD_A2_...\build_report.json" `
  --preflight
```

Do not point the runner at a chat upload directory containing historical `build_report*.json` files. The attached `build_report(5).json` is a valid CAD/G1 record, but it is not simulation-ready because it has no physics contract or `Solver_Geometry` directory.

## 4. Launch external stages (legacy command-line form)

The package does not bundle or fake the external solvers. Supply commands and their real input files. Example command shapes (replace every placeholder with your actual case):

```powershell
py .\tomahawk_multiphysics_run.py `
  --results-folder "C:\cases\CAD_A2_..." `
  --mhd-command "vmec2000 C:\cases\mhd\input.toml" `
  --mhd-input "C:\cases\mhd\input.toml" `
  --neutronics-command "openmc" `
  --dagmc "C:\cases\neutronics\dagmc.h5m" `
  --materials "C:\cases\neutronics\materials.xml" `
  --settings "C:\cases\neutronics\settings.xml" `
  --cross-sections "C:\data\cross_sections.xml" `
  --cfd-command "nekrs --setup C:\cases\cfd\rf_case --backend CUDA --device-id 0" `
  --cfd-mesh "C:\cases\cfd\rf_case\rf.re2" `
  --cfd-case "C:\cases\cfd\rf_case\rf.par" `
  --chf-command "py C:\cases\chf\chf_postprocess.py" `
  --chf-results "C:\cases\chf\chf_input.json" `
  --timeout-s 86400
```

The runner writes one JSON record and one combined log per stage. `new_physics_run` becomes true only when an external command was actually attempted; it is not a physics-validation claim. A zero return code without a declared output never advances the pipeline.

## Governing equations and gates

The complete machine-readable contract is generated as `Tomahawk_Multiphysics_Physics_Contract.json`. The governing set is:

```text
MHD equilibrium:       ∇×B = μ0 J,  ∇·B = 0,  J×B = ∇p
Resistive MHD:          ∂ρ/∂t + ∇·(ρu) = 0
                        ρ(∂u/∂t + u·∇u) = J×B − ∇p + ∇·τ
                        ∂B/∂t = ∇×(u×B − ηJ),  ∇·B = 0
Confinement:            W = (3/2)∫(ne kB Te + ni kB Ti)dV,  τE = W/Ploss
Neutronics:             (1/v)∂ψ/∂t + Ω·∇ψ + Σtψ = ∫Σsψ dΩ′dE′ + S
                        TBR = ∫∫ΣLi6,n t(E) φ(E,r)dE dV / source neutrons
CFD/CHT:                ∂ρ/∂t + ∇·(ρu) = 0
                        ∂(ρu)/∂t + ∇·(ρuu) = −∇p + ∇·τ + ρg
                        ρs cp,s ∂T/∂t = ∇·(ks∇T) + qvol
CHF:                    DNBR = qCHF / qlocal; require min(DNBR) ≥ 1.30
```

The initial conditions in the contract are explicit proposals, not measured values: 7 MPa water, 348.15 K inlet, 3.5–4.5 m/s target velocity, 100 kPa pressure-drop limit, 573.15 K CuCrZr limit, and 1.30 minimum DNBR. Replace them only with documented case inputs and report the source/hash.

## Solver handoff requirements

- MHD/confinement: actual coil currents, free-boundary vacuum field, pressure/density/temperature profiles, transport closure, and perturbation spectrum.
- DAGMC/OpenMC: imprinted/merged watertight `dagmc.h5m`, material cards, temperature-dependent densities, nuclear data, and source distribution.
- CFD/CHF: volume mesh, confirmed inlet/outlet face IDs, water property tables, heat-load map from transport, and a CHF correlation/LUT whose pressure, mass-flux, quality, diameter, and heated-length applicability is documented.

The exported geometry is a solver-ready handoff, not a completed multiphysics result or manufacturing release.
