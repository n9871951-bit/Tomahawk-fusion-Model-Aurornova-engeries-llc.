# Tomahawk Rev 2.1 Plasma Information Files v1.0

This package contains standalone information files for post-processing the Tomahawk reactor model. It is not a Kaggle runtime-input package and it does not replace any completed checkpoint or solver result.

## Included information

- `04_plasma/profiles.csv`: 101-point normalized-flux density and temperature profiles for two screening realizations.
- `04_plasma/species.yaml`: species, quasineutrality, and ash conventions.
- `04_plasma/initial_state.yaml`: Rev 2.1 geometry, fill, magnetic field, density, and temperature baseline.
- `07_transport/closures.yaml`: IPB98(y,2) confinement scaling, energy content, and power-balance definitions.
- `07_transport/radiation_reaction.yaml`: Bosch-Hale D-T reaction convention, alpha-energy accounting, radiation reference, and blanket assumptions.
- `coefficients.json`: portable scalar coefficients for software that does not use HDF5.
- `power_balance.yaml`: conversion from fusion source power to usable thermal and net electric power.
- `manifest.json`: file hashes and provenance.

## Important status labels

The CSV profiles are assumed screening realizations. The 10% alpha-loss value, 95% neutron-capture value, and TBR=1.15 are design assumptions, not measurements or derived results. The 0.63 reference value is deposited-alpha power divided by modeled losses; it is not the intrinsic alpha fraction of D-T fusion power.

The intrinsic alpha energy fraction is 3.5/17.6 = 0.1988636364. With the 10% loss assumption, the deposited alpha heating fraction is 0.1789772727 of fusion power. A plant claim still requires a solved/declared current and equilibrium, volume-weighted density and temperature profiles, impurity/ash dilution, radiation, alpha deposition, recirculating loads, and a complete power balance.

The IPB98(y,2) relation is included as an empirical tokamak-like H-mode screening closure. It is not a substitute for a 3-D MHD equilibrium or transport solution.

## References

1. ITER Physics Basis, Chapter 2, *Plasma confinement and transport*, Nuclear Fusion 39 (1999): https://scipub.euro-fusion.org/
2. H.-S. Bosch and G. M. Hale, *Improved formulas for fusion cross-sections and thermal reactivities*, Nuclear Fusion 32 (1992) 611-631: https://doi.org/10.1088/0029-5515/32/4/I07
