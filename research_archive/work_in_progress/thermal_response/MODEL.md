# Fixed-profile thermal-response calculation

This work uses the saved N9A2 equilibrium and the saved 12 keV kinetic-profile screen.
It computes time-dependent thermal and fast-alpha energy for a fixed density,
composition, magnetic geometry and temperature-profile shape. It is a reduced 0D
screen, not a new gate acceptance calculation or a spatial plasma-fluid simulation.

Run the Python calculation from any working directory:

```sh
python -m pip install -r requirements.txt
python run_screen.py
```

The script locates its inputs relative to its own file and writes nine scenario CSVs,
`results/summary.json`, and `results/numerical_checks.json`. It does not need Kaggle
credentials or a hardcoded user directory. Python 3.12 was used for the recorded run.

## Equations and assumptions

The state is thermal energy W, fast-alpha reservoir A, cumulative retained energy
input, and cumulative modeled loss. Temperature scales with W/W0. The density and
species fractions remain fixed, implicitly requiring fuel replenishment and ash
control. Ion and electron temperatures share one common scale.

- dW/dt = A/t_alpha + P_external - W/tau_E - P_brems - P_sync.
- dA/dt = f_retention * P_alpha_birth - A/t_alpha.
- D–T reactivity uses the existing Bosch–Hale coefficients from the source package;
  its numerical check compares with the supplied rounded reference table.
- The initial alpha residence time is A0/P_alpha_birth0; its temperature dependence
  is assumed proportional to T^1.5 for this screen.
- Bremsstrahlung follows the fully ionized species sum at the supplied composition.
- Synchrotron power is anchored to the saved workbook, with an assumed T^2.5 response;
  exponents 2 and 3 are also screened. Radiation transport is not recalculated.
- tau_E = 1.47614200749459 s comes from the earlier required power balance. It is an
  assumed confinement time here, not an independently predicted one.
- The reference external source assumes complete absorption of 25 MW. Zero external
  heating and 90% alpha retention are also screened. No RF deposition is invented.
- Heat recovered from the wall for secondary systems is downstream recovery; it is
  not added as another plasma energy loss or counted twice as a source.

The equations stop at the screening interval W/W0 = 0.5 to 2.0, or after five physical
seconds. Exiting this interval is a model-range stop, not a plant safety limit.

## Numerical checks and scope

The independently implemented C++ equations were integrated with BOUT++ RK4 and
compared with SciPy Radau. The native reference calculation was also restarted from
its saved state at 2.5 s. Exact measured differences are in
`results/numerical_checks.json`. Energy accounting includes the alpha reservoir.

The volume quadrature uses 48 radial Gauss nodes and 65 poloidal nodes on the supplied
axisymmetric state. Additional geometry-quadrature convergence checks have not been
performed in this work. Integration agreement checks the implementation of these
equations; it does not validate the assumed transport or radiation response.

The reference and perturbation trajectories are conditional calculations. Interpret
their sensitivity using these assumptions, rather than assigning a reactor pass/fail
or a demonstrated electrical output.

## Optional native BOUT++ run

Build `model/` against BOUT++ and pass the resulting executable:

```sh
cmake -S model -B build -DCMAKE_PREFIX_PATH=/path/to/bout-build
cmake --build build
python run_screen.py --bout-executable build/tomahawk_thermal
```

The recorded native run used BOUT++ v5.2.0, commit
`650bfc6d0b952dc567fca625b2721b7ee543a608`, MPI enabled, one process, and the
RK4 integrator. No third-party binaries are distributed in this calculation package.
`BOUT_NO_NETCDF.patch` records the namespace qualification needed for the minimal
build without NetCDF. The patch changes no plasma equations.

The provided CSV checkpoint retains all four energy variables and the time offset;
it is the restart mechanism used here. This model uses a uniform one-cell state and
does not represent a mapped spatial plasma mesh.
