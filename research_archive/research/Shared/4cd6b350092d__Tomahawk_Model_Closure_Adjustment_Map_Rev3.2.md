# Tomahawk model-closure adjustment map — Rev 3.2

## Result

The six missing input classes are now populated in `tomahawk_inputs_model_derived_rev3_2/` using deterministic engineering equations and fixed grids. No random or Monte Carlo samples are used in this package.

This is the first runnable model-closure baseline. It is not as-built CAD, measured diagnostic data, qualified optical coupling, orbit-resolved alpha transport, or a nuclear-data transport tally.

## Current closure values

| Input | Generated baseline | Verification |
|---|---|---|
| CAD/mesh | Parametric torus, R0 = 7.5 m, a = 3.0 m, kappa = 0.713000922; 69,632 nodes, 65,536 cells | Cell-volume sum = 950.000 m³; relative error = 0 |
| Coils/currents | 16 poloidal filamentary coils, 100 turns/coil, 321,547.590 A/coil at the 14 T target | Biot–Savart field at (R0,0,0) = 14.000 T |
| Ti/Te | 257 radial points; Ti0/Te0 = 30/10 keV; Ti_edge/Te_edge = 1.25/1.25 keV; gamma_n = 0.657; gamma_Ti = gamma_Te = 0.80 | n_e = n_D + n_T to floating-point precision |
| Alpha source | Bosch–Hale D-T source; alpha birth = 1.626675 GW/module; deposited = 1.464008 GW/module; loss = 10%; ion partition = 15% | Integrated deposition fraction = 0.9000000000000001 |
| 16-port rays | A1/B1 through A8/B8; 351 nm; 156.25 kJ/port; equal weights; 0.86 reduced-order coupling | 16 unit directions; energy weights sum to 1 |
| Blanket/neutron source | 14.1 MeV neutron source = 6.553178 GW/module; W/CuCrZr/ODS-FeCrAl/FLiBe concentric-layer closure; 95% capture; TBR = 1.15 design target | Source and capture power are conserved in `power_tallies.csv`; DPA/gamma still require a nuclear-data run |

## What each adjustment changes

| Edit this file | Adjusts these results | Rerun |
|---|---|---|
| `01_geometry/*` | Volume, area, flux coordinates, wall strikes and local loads | R1, R3, R4, R6 |
| `02_field/coil_centerlines.csv` or `coil_currents.csv` | B, J, Lorentz loads, q/iota, topology and equilibrium | R1, R2, R4, R5 |
| `04_plasma/profiles.csv` | Pressure, D-T reactivity, bremsstrahlung, Q_ie, transport and burn residual | R4, R5 |
| `04_plasma/alpha_source.csv` and `alpha_orbit.yaml` | Local alpha heating, orbit loss, Ti/Te source partition and self-heating | R3, R4, R6 |
| `05_driver/rmapla_ports.csv`, `ray_paths.csv`, `target_corona.yaml` | Coupled laser source, momentum, signed torque and timing | R3, R4 |
| `09_neutronics/*` | Blanket heat, TBR, DPA, gamma, tritium and plant power ledger | R6, FUEL_PLANT |

## Equations used to create the package

```text
R(rho,theta) = R0 + a*rho*cos(theta)
Z(rho,theta) = kappa*a*rho*sin(theta)
V = 2*pi^2*R0*a*(kappa*a) = 950 m^3

n_D(rho) = n_D0*(1-rho^2)^gamma_n
n_T(rho) = n_T0*(1-rho^2)^gamma_n
Ti(rho) = Ti_edge + (Ti0-Ti_edge)*(1-rho^2)^gamma_Ti
Te(rho) = Te_edge + (Te0-Te_edge)*(1-rho^2)^gamma_Te
n_e = n_D + n_T + 2*n_He + sum(Z_s*n_s)

Q_fusion = n_D*n_T*<sigma v>_Bosch-Hale(Ti)*17.6 MeV
Q_alpha,birth = Q_fusion*(3.5/17.6)
Q_alpha,dep = 0.90*Q_alpha,birth
Q_neutron,birth = Q_fusion*(14.1/17.6)

B(r) = mu0/(4*pi) * sum(I*dl x (r-r')/|r-r'|^3)
I = B0_target / (B_per_ampere * turns)

E_pulse = sum_j E_j = 2.50 MJ
E_j = 2.50 MJ/16 = 156.25 kJ
P_laser,delivered = E_pulse*f_rep = 25.0 MW
P_laser,coupled = eta_coupling*P_laser,delivered = 21.5 MW
```

## Use sequence

1. Run the `MODEL_CLOSURE` case against this package.
2. Change one input class at a time.
3. Preserve the prior manifest and record the new SHA-256 values.
4. Compare the delta in the listed rerun gates.
5. Only promote a result to the controlling SIS after replacing the model-derived closure with qualified source data and passing the corresponding evidence gate.

The first diagnostic adjustment is the 16-port ray geometry: the radial-focus closure has zero signed torque. A nonzero torque result requires a supplied non-radial impact parameter or verified asymmetric target/corona coupling; it must not be inserted as a favorable scalar.
