# Tomahawk Rev2.4 confinement review

Review status: `DO_NOT_RUN_EXTERNAL_SOLVER`

This review incorporates the recorded user-provided reference correction of
63% self-heating at the reference condition. The correction is defined as:

    deposited alpha power / modeled losses = 0.63

The prior equation set specifies bremsstrahlung as
`5.35e-37 * Z_eff * n_e^2 * sqrt(T_e[keV])`. Rev2.4 had been applying an
unintended keV-to-eV conversion inside the square root; that inflated the
radiation term by `sqrt(1000)`. The unit correction is now implemented and
the active profile is compared using the same power-balance definition.

## Current local screen

| Check | Result |
|---|---:|
| Fixed-boundary equilibrium/profile numerical screen | PASS |
| Active-profile tau-E screening target | 2.70 s (derived target) |
| Active-profile self-heating ratio | 1.1982 |
| Recorded reference-condition ratio | 0.6300 at 1.36 s |
| Computed reference-condition ratio | 0.6235 at 1.36 s |
| Reference-to-computed discrepancy | 0.0065 |
| Reference correction reconciliation | PASS within 0.02 |
| Alpha self-heating gate (requires ratio >= 1) | PASS |
| Tau-E margin gate (requires margin >= 0.20) | PASS, 21.18% |
| Confinement-feasibility screen | PASS |
| Full incident-stress coolant screen with 50% secondary routing | PASS |
| Overall local screen | PASS WITH EXTERNAL BLOCKERS |
| Reduced uncertainty all-gate pass rate | 22.87% |

The active profile gives approximately 0.186 GW deposited alpha power against
0.155 GW of modeled losses: approximately 0.010 GW bremsstrahlung plus
0.145 GW transport loss at the 2.70 s screening target. The calculated
alpha-balance threshold is 2.228 s, so the target has a 21.18% arithmetic
margin and a +0.0308 GW net alpha margin per modeled module.

For the coolant screen, the `full_incident_stress` envelope is now split with
an explicit 50% secondary-system routing assumption. Its worst row carries
10.0 MW incident heat per cassette, routes 5.0 MW to secondary systems, and
leaves 5.0 MW on the cassette. The resulting maximum bulk rise is 15.62 K and
maximum wall temperature is 465.6 K (192.4°C), below the 573.15 K limit. The
secondary-system capacity and deposition path are not yet qualified.

## Decision

The equation correction reconciles the recorded 63% result to the same profile
at its 1.36 s reference condition. The active 2.70 s target closes the
arithmetic self-heating and tau-E-margin gates, so the confinement-feasibility
screen is now PASS. This is still an assumed design target, not measured or
validated confinement. The overall local screen is now PASS WITH EXTERNAL
BLOCKERS; the 50% secondary heat split remains an unvalidated design
assumption, and the external equilibrium/MHD, alpha-orbit, neutronics, CFD/CHT,
and CHF blockers remain open.

## Required closure before promotion

The next closure is validation of the 2.70 s tau-E target with a transport or
high-fidelity confinement calculation and validation of the 50% secondary heat
split/secondary-system capacity. The free-boundary 3-D equilibrium, nonlinear
MHD, orbit-resolved alpha transport, qualified neutronics, CFD/CHT, and CHF
gates remain separate external blockers.
