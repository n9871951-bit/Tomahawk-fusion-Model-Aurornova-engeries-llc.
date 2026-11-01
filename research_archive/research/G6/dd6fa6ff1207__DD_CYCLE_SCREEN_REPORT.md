# Tomahawk D–D closed-fuel-cycle screen

Run ID: `TOMAHAWK_DD_CLOSED_FUEL_CYCLE_SCREEN_20260918`  
Status: **REDUCED-ORDER SCREEN — NOT VALIDATED**

## Candidate mechanism

```text
D + D -> T + p       (tritium intermediate)
D + D -> He-3 + n   (helium-3 intermediate)
D + T -> He-4 + n
D + He-3 -> He-4 + p
```

The D–D branches create the tritium and helium-3 intermediates inside the
plasma. The liquid wall is therefore not used as the nuclear fuel source in
this candidate. It may still be retained for heat removal, shielding, and
neutron management, but that is a separate wall/thermal requirement.

## Locked reference case

The run uses the Revision 2.1 baseline: `V = 950 m³`, central
`n_D = n_T = 1.200e+20 m⁻³`, `gamma_n = 0.657`, and `T_i = 20 keV`.
The profile reaction factor is the declared reduced-order surrogate
`gamma_n² = 0.431649`.

At the reference state:

| Quantity | Result |
|---|---:|
| Baseline D–T reference power | 7.21021 GW |
| D–D-cycle power | 0.0104732 GW |
| D–D / baseline D–T power ratio | 0.00145255 |
| Tritium produced internally | 3.54729e-05 g/s |
| External tritium makeup | 0 g/s |
| T secondary burn fraction, tau = 3 s | 0.092903 |
| He-3 secondary burn fraction, tau = 3 s | 0.000822912 |

## Interpretation

The mechanism **does eliminate the blanket as the fuel-source dependency** in
the reduced-order model: tritium is an in-plasma D–D product and no external T
makeup is required by the algebra. At the locked 20-keV, baseline-density
state, however, the D–D cycle is not power-competitive with the reference
D–T state. The scan tests higher temperature, density, and intermediate
retention; any high-ratio case is conditional on those inputs and is not a
validated operating point.

The highest screened ratio was **138.463** at
`T = 100 keV`, density multiplier
`64`, and product-retention time
`10 s`. That row is a sensitivity
result, not a feasibility claim.

## Gate result for tonight’s lock

**Fuel-source architecture: LOCKABLE AS A CANDIDATE.** The model can now
represent a blanket-free D–D closed fuel cycle without exposing the private
process recipe.

**Performance claim: NOT LOCKED.** The locked baseline does not surpass the
D–T reference in this screen. A claim of surpassing requires a solved
high-density/high-temperature state, product confinement and burn transport,
wall/neutron handling, and full plant power balance.

## Reproducibility

- `run_dd_cycle_screen.py` — executable screening model.
- `dd_cycle_screen_results.csv` — 405 state points.
- `dd_cycle_screen_summary.json` — machine-readable results and checks.
- Reactivity coefficients: [UWFDM-1268](https://fti.neep.wisc.edu/fti.neep.wisc.edu/pdf/fdm1268.pdf), based on the Bosch–Hale fit ([DOI](https://doi.org/10.1088/0029-5515/32/4/I07)).
