# G2 force/boundary pass record

**G2 status: NOT CLOSED.** Force-balance, boundary-residual and solver-convergence checks **PASS** for the polished L16/M16/N9 PF634 equilibrium. G2 still needs the stability screen, CAD and clearance regeneration, and the formal acceptance decision.

**Candidate:** `outputs/repair/newton_L16_N9_polish/fixed_boundary_newton.h5`
SHA-256 `9479af3beda691d1177fb1674c7f7b70b18c390f3b23173a8f0e02adfaddf4b2`
Field map (PF634) SHA-256 `8a062337fe59cd2217ce59b4b02675f17dab18ca98f0b6363bb0a2dd75034be0`

## Checks that pass

| Check | Limit | N9 value | Result |
|---|---:|---:|---|
| Solver converged (Newton, gradient tolerance) | 1e-11 | 7.45e-12 | PASS |
| Normal-field maximum | 0.001 | 0.000736 | PASS |
| Boundary pressure maximum | 0.001 | 0.000395 | PASS |
| Normalized force RMS (G2 gate) | 0.001 | 2.78e-05 | PASS |
| Nested surfaces | — | yes | PASS |
| Boundary, pressure, iota, flux, PF634 currents unchanged | — | yes | PASS |

## Pressure-scaled force (proposed limits, not yet formally assigned)

| Region | Proposed limit | N6 | N9 |
|---|---:|---:|---:|
| All radii | 0.25% | 0.097% | 0.082% |
| Excluding the edge surface | 0.1% | 0.042% | 0.034% |
| Edge surface (rho 0.995) | 1% | 0.437% | 0.372% |

## Open before G2 can close

1. Formal acceptance decision: assign these limits, and decide the edge-surface resolution exception (N6→N9 change 14.8% at 0.37%; N3→N6→N9 sequence 6.44% → 0.437% → 0.372%). Either accept on two converged resolutions, or run N12.
2. Seven-radius stability screen on this equilibrium: not run.
3. CAD regeneration for the coupled-L12 boundary: not run.
4. Clearance and CAD-fit checks on the new CAD: not run.

Full evidence, hashes and provenance are in `G2_FORCE_BOUNDARY_PASS.json`.
