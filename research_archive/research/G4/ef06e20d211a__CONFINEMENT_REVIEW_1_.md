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
| Active-profile self-heating ratio | 0.6235 |
| Recorded reference-condition ratio | 0.6300 |
| Reference-to-active discrepancy | 0.0065 |
| Reference correction reconciliation | PASS within 0.02 |
| Alpha self-heating gate (requires ratio >= 1) | FAIL |
| Tau-E margin gate (requires margin >= 0.20) | FAIL |
| Reduced uncertainty all-gate pass rate | 0.0% |

The active profile gives approximately 0.186 GW deposited alpha power against
0.298 GW of modeled losses: approximately 0.010 GW bremsstrahlung plus
0.288 GW transport loss at tau-E = 1.36 s. The net alpha margin remains
negative, so the strict unity self-heating gate is not closed.

## Decision

The equation correction reconciles the recorded 63% result to the active
profile within the declared tolerance. It does not close the strict
self-heating threshold: 0.6235 is below unity, and the tau-E robustness margin
also fails. The physical confinement-feasibility gate therefore remains
closed. The current result is a reproducible screening disposition, not a
sustained-burn, ignition, 3-D-MHD, or hardware-validation claim.

## Required closure before promotion

The next closure is not equation reconciliation; that is now complete. Supply
validated profile, alpha-deposition/orbit, transport, and tau-E inputs that
raise the active balance to unity with the required 20% margin. The
free-boundary 3-D equilibrium, nonlinear MHD, orbit-resolved alpha transport,
qualified neutronics, CFD/CHT, and CHF gates remain separate external
blockers.
