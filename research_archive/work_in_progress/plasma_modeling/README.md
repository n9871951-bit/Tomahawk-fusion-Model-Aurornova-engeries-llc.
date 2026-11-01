# Tomahawk plasma modeling: BOUT++ (elm-pb) on the N9A2 equilibrium

**Reactor research, design and modeling:** Nicole Marie Bryant / AuroraNova Engeries LLC (Tomahawk concept, 16 T design, enlarged TF48, N9A2 equilibrium, profiles).
**Published software used:** BOUT++ 5.1.1 and its elm-pb model (boutproject/BOUT-dev). Original software and literature retain their source-specific attribution and notices.

## Preliminary status

This package is work in progress. The investigator reports an unresolved issue and intends to revise it. It is preserved for review and continuation; it is not an accepted reactor stability result.

## What is in this package

| Folder | Contents |
|---|---|
| `01_Kaggle_notebooks/` | P1–P4: the full-resolution matrix (nx 260/516). No inputs needed. Internet on, CPU. Run all four at once. Each builds BOUT++, makes the grids and runs its cases (under 12 h each). If any case fails, the notebook raises an error so Kaggle shows the run as failed. |
| `02_Results/` | The runs done in the workspace: per case `growth_rate.json`, `mode.png` (cross-section and growth history), ParaView files (`paraview/*.vts`), and BOUT.inp/settings/log. Also `summary.csv` and `summary_pressure_margin_and_n_scan.png`. |
| `03_Grids/` | BOUT++ grid files made from N9A2 (nx 68/132/260/516, ny 64/128, pressure-scaled versions), each with a JSON of checks. Also the N9A2 file itself and a grid picture. |
| `04_Tools/` | The DESC reader (numpy only), the grid generator, results/ParaView exporter, build scripts (workspace and Kaggle) and the notebook builder. |
| `05_Benchmark_cbm18/` | The standard BOUT++ elm-pb benchmark, run with this build. |
| `OPEN_IN_PARAVIEW.py` | Loads every result into ParaView (see below). |

## ParaView

ParaView couldn't be installed in the cloud workspace: its download servers, PyPI, conda-forge and apt are all blocked there. Install it on your own computer instead. It's free from paraview.org: Windows, macOS and Linux.

1. Unzip, then open ParaView.
2. Go to View → Python Shell → Run Script, and pick `OPEN_IN_PARAVIEW.py`. It loads every case and cuts a quarter of the torus away so you can see inside.

Alternatively, use File → Open on any `paraview/P_series.vts.series` file. The fields are:
- `P_perturbation_normalised`: the growing mode at the end of the run, scaled to ±1 (in a linear run the absolute size has no meaning).
- `P0_equilibrium_Pa`: N9A2 pressure.

The geometry is the real 3-D torus in metres.

## How the grid was made (checks in each grid's JSON)

- **Reading the equilibrium.** N9A2 (SHA-256 8e6b295e…83f8) is read directly with numpy. The boundary reproduces the file's own surface to 9e-15 m. The non-axisymmetric residual is at most 1.3e-7 m.
- **Domain.** Closed flux surfaces from ψ_n 0.40 to 1.00. Mesh lines follow orthogonal trajectories of the flux surfaces; the grid is orthogonal to 4e-5.
- **Field-line consistency.** The field-line twist integrated on the grid matches the equilibrium's q to 1e-6. R·B_t is constant on each surface to 5e-5, which is GS force balance.
- **Formula check.** The curvature, shift and current formulas were first checked against the BOUT++ reference grid (cbm18): curvature to 2e-6, shift angle exact.
- **Plasma parameters.**
  - Density 3.46e20 m⁻³, which gives N9A2's 1.33 MPa axis pressure at Ti = Te = 12 keV (kinetic screen C7).
  - D-T ion mass 2.5.
  - Alfvén time τ_A = 0.648 µs.

## Results so far (workspace runs, nx 132)

| Check | Result |
|---|---|
| **Benchmark (cbm18, n = 15)** | 0.256 / τ_A, settled. The README of the example quotes 0.275 from an older code version; the peak is at the same grid point as the example's own analysis script. |
| **Design pressure, n = 15** | No ballooning mode. A weak mode grows (0.035–0.06 / τ_A) in a thin layer on the inboard side, where the curvature is favourable. It goes away when the curvature drive is switched off (0.003 / τ_A) and it shrinks with finer resolution (0.048 at nx 68, 0.035 at nx 132). It is a resistive interchange-type mode at the benchmark Lundquist number S = 1e8. Tomahawk's own Spitzer S is 3e8–6e10, which is higher. |
| **Pressure margin, n = 15** | ×1.5: 0.075, inboard. ×2: 0.091, inboard. ×3: 0.274, **outboard ballooning**. ×4 and ×6 (0.55): outboard ballooning. **Ballooning onset lies between 2× and 3× the design pressure.** |
| **Design pressure, n = 5–30 (Spitzer resistivity)** | 0.045–0.094 / τ_A. For n = 5–20 the mode sits on the last closed surface, where the pressure goes to zero, the temperature is set by the floor and the resistivity is extreme. That is a boundary effect of a grid that ends at the last closed surface, not a core instability. n = 30 peaks inside, at ψ_n 0.91 inboard. |
| **Ideal (no resistivity), n = 15** | An edge-localised mode at the last closed surface, not settled. Same caveat. |

**Limits of these results:**
- **No region outside the plasma.** The DESC equilibrium is fixed-boundary, so the grid ends at the last closed surface: there is no vacuum or scrape-off region outside it. Peeling (edge-current) modes can't be judged properly here. Doing so needs a free-boundary equilibrium or a vacuum region added outside the plasma.
- **Linear runs only.** These are linear growth rates, single n per run. No nonlinear ELM crash has been simulated.
- **Resolution.** The workspace runs are at nx 132. Notebook P4 checks resolution up to nx 516, and P1–P3 repeat the full n × pressure matrix at nx 260.

## Re-running anything

- **Grids:** `python 04_Tools/make_bout_grid.py N9A2.h5 out.nc --nx 260 --ny 64 --pscale 1`
- **Results:** `python 04_Tools/bout_results.py RUN_DIR --grid GRID.nc --vtk`

Both need only numpy, scipy and matplotlib; the bundled pyfive reads the HDF5 files.

The repository contains browsable notebooks, tools and small result tables. Full grids, images and ParaView results are supplied with the download packages. `MANIFEST.csv` lists the published file hashes.
