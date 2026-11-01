# Tomahawk Rev2.4 confinement review

Review status: `DO_NOT_RUN_EXTERNAL_SOLVER`

This review incorporates the recorded user-provided reference correction of
63% self-heating at the reference condition. The correction is defined as:

    deposited alpha power / modeled losses = 0.63

The value is preserved as a comparison datum. It is not substituted for the
active Rev1.7 radial profile because the underlying input changes that
produced the correction are not present in the current bundle.

## Current local screen

| Check | Result |
|---|---:|
| Fixed-boundary equilibrium/profile numerical screen | PASS |
| Active-profile self-heating ratio | 0.3077 |
| Recorded reference-condition ratio | 0.6300 |
| Reference-to-active discrepancy | 0.3223 |
| Reference correction reconciliation | BLOCKED |
| Alpha self-heating gate (requires ratio >= 1) | FAIL |
| Tau-E margin gate (requires margin >= 0.20) | FAIL |
| Reduced uncertainty all-gate pass rate | 0.0% |

The active profile gives 0.186 GW deposited alpha power against 0.605 GW of
modeled losses, with a net alpha margin of -0.419 GW per modeled module. Since
deposited alpha power is below bremsstrahlung in this branch, a finite
alpha-balance tau-E requirement cannot be calculated for it.

## Decision

The 63% correction improves the recorded reference result but does not close
the strict self-heating threshold. The physical confinement-feasibility gate
therefore remains closed. The current result is a reproducible screening
disposition, not a sustained-burn, ignition, 3-D-MHD, or hardware-validation
claim.

## Required closure before promotion

Supply a revised profile-consistent input package that reproduces the 63%
reference result, including the density/species definitions, `Ti(rho)`,
`Te(rho)`, `Z_eff`, alpha-deposition/orbit treatment, and the tau-E closure.
Then rerun the power balance and require both alpha self-heating and tau-E
margin gates to pass. The free-boundary 3-D equilibrium, nonlinear MHD,
orbit-resolved alpha transport, qualified neutronics, CFD/CHT, and CHF gates
remain separate external blockers.
