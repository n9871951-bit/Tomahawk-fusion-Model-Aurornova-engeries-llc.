# Tomahawk laser-source numeric handoff

This handoff supplies the numbers that already exist in the Tomahawk confinement-screen record and derives the contract outputs from those values. It does not convert the unresolved laser coupling, wall-loss map, or pulse timing into a validation claim.

## Values to propagate now

| Contract input | Numeric value | Meaning |
|---|---:|---|
| `P_total_absorbed_heating_required_W` | `155,293,526.9 W` | Latest CAD-A2 reference screen: modeled total losses, used as the steady `dW/dt = 0` requirement |
| `P_alpha_to_plasma_W` | `186,072,047.5 W` | Deposited-alpha screen output |
| `P_RF_absorbed_W` | `0 W` | Laser-only balance boundary; not a statement that RF cannot contribute |
| `P_other_absorbed_W` | `0 W` | No other source included in this balance |
| `P_external_laser_absorbed_required_W` | `0 W` | `max(0, 155,293,526.9 - 186,072,047.5)` |
| `eta_laser_to_plasma` nominal | `0.268574` | Existing nominal model observation; not qualified hardware coupling |
| `eta_laser_to_plasma` optimized sensitivity | `0.860024` | Existing inverse-model result; validation remains open |
| wavelength | `351 nm` | Declared UV driver baseline |
| module shot energy | `2.50 MJ` | Sum over 16 channels |
| `f_pre` | `0.50` | Recovered `F_PRE = 0.50` preset in `TOMAHAWK_Verified_Quick_Run.ipynb`; not a validated optimum |
| `f_spike` | `0.50` | Recovered `F_SPIKE = 0.50` preset in the same notebook |
| preconditioning energy | `1.25 MJ` | `2.50 MJ × 0.50` |
| spike energy | `1.25 MJ` | `2.50 MJ × 0.50` |
| nominal conditional stray-wall ceiling | `0.731426` | Fraction of incident energy; requires `eta = 0.268574` and all uncoupled light absorbed at the liquid wall |
| optimized-coupling conditional stray-wall ceiling | `0.139976` | Separate sensitivity at `eta = 0.860024`, with the same maximum-transfer assumption |
| repetition rate | `10 Hz` | Declared module baseline |
| long-pulse component | `5 ns` | Compression/conditioning component |
| fast-spike component | `10 ps` | Fast-ignition component |
| equal per-port energy | `156.25 kJ` | `2.50 MJ / 16`, fraction `0.0625` per port |
| average delivered optical power | `25 MW` | `2.50 MJ × 10 Hz` |
| wall-plug target | `15%` | Internal development target; do not use as plasma coupling |

On this latest reference branch, the laser is not required for the steady alpha balance. It is still required as a transient/startup/perturbation input, but the current screen does not contain a validated transient energy-to-state map.

## Pulse quantities that are numerical but not fully closed

The earlier quick-run notebook sets a numerical screening preset. That supplies the split without claiming a target-specific optimum:

```text
f_pre   = 0.50
f_spike = 0.50
E_pre   = 1,250,000 J
E_spike = 1,250,000 J
E_pre_per_equal_port   = 78,125 J
E_spike_per_equal_port = 78,125 J
```

The notebook uses Gaussian components with 5 ns and 10 ps FWHM, each normalized by its trapezoidal integral on 801 samples. The individual component peaks are approximately `2.34877e14 W` and `1.17439e17 W`. The legacy `E/FWHM` expressions give `2.5e14 W` and `1.25e17 W`; they are scales, not the normalized Gaussian peaks. The component duty fields describe FWHM fractions of the repetition period, not finite-support Gaussian on-time.

The notebook's coupling preset was `0.86`. Recovering its split does not qualify that coupling or silently replace the selected nominal `0.268574` case. Port energies are specified, but wall-deposition shares and delays remain unresolved. Geometry also needs reconciliation: the architecture uses azimuths beginning at 0 degrees, while the later CAD-A2 beam strategy starts at 5.625 degrees. Toroidal launch angles do not supply optical phase or timing.

The separately prescribed `2.50 MJ × 10 Hz = 25 MW` optical-on case gives a direct stray-wall ceiling of `1,828,565 J/shot` or `18,285,650 W` at nominal coupling. The separate optimized-coupling sensitivity gives `349,940 J/shot` or `3,499,400 W`. Neither is an actual deposition estimate or part of the zero supplemental steady-laser requirement.

## The important legacy branch

The earlier corrected Rev2.4 active-profile review used approximately `0.298 GW` of modeled loss against `0.186 GW` deposited alpha power. If that branch is intentionally selected, it requires approximately `112 MW` of absorbed external laser power. The corresponding incident laser powers are approximately:

- `417 MW` at the nominal `0.268574` coupling observation;
- `130 MW` at the optimized `0.860024` sensitivity.

That branch must remain separate from the later CAD-A2 reference screen. Mixing them would manufacture a power balance.

## What is still not a real number

No defensible actual point value is available yet for `fraction_stray_laser_to_liquid_wall`. The September 10 beam strategy explicitly reports that the 3-D ray trace and absorption map remain unsolved. The normal-incidence linear-corona calculation supplies absorption, not a chamber-wall deposition tally. `1 - eta_laser_to_plasma` therefore supplies only a conditional upper bound at the stated coupling.

The missing quantity is direct laser energy absorbed by the liquid wall in the same shot and at the same optical reference plane:

```text
fraction_stray_laser_to_liquid_wall = E_liquid_wall_absorbed_direct_laser_J / E_incident_J
```

For the declared 2.50 MJ shot, divide the wall-absorption tally by `2,500,000 J`. Exclude plasma radiation, alpha, neutron and gamma energy from that direct-laser numerator. A numeric actual fraction cannot be recovered from the supplied files without that tally or a resolved optical trace with wall absorptivity.

The original source contract and this handoff now carry `f_pre = f_spike = 0.50` with provenance. Actual wall deposition, qualified alpha transport, target-specific pulse validation, delays, spot size, polarization and demonstrated 10-Hz module capability remain unresolved. The qualification gate remains disabled.
