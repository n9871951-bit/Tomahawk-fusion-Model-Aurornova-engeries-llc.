# Tomahawk 16 T G2: targeted corrective solution

**Status:** Evidence-backed run design, not a passed equilibrium. Date: 2026-10-12.

## Decision

Start the next finite-pressure free-boundary solve from an **uncorrugated plasma surface** while retaining the 16 T, 48-coil TF field and the 16-period MGRID. Remove the imposed 1 cm helical term from the *plasma-boundary seed*, then jointly correct the axisymmetric equilibrium shape and the six signed PF currents under hard CAD and current limits. Keep the 6.1 GWth/core pressure case as the first closure target; advance to the higher-pressure power case only after its equilibrium and ideal-ballooning gates pass.

This is a specific correction to the dominant field-shape mismatch in the existing configuration. The finite-pressure pressure-balance and force-balance gaps still require a coupled solve, and no unrun configuration can be certified as G2-closed.

## Evidence from the three completed Kaggle runs

| Case, selected flux | L16 normal RMS | L16 pressure-jump RMS | CAD RMS movement | Outcome |
|---|---:|---:|---:|---|
| Negative TF, Ψ = 336.60685 Wb | 2.685% | 3.396% | 0.00627 m | Solver failed; G2 failed |
| Negative TF, Ψ = 353.43719 Wb | 4.093% | 6.064% | 0.01993 m | Solver reported success; G2 failed |
| Positive TF, Ψ = 336.60685 Wb | 3.275% | 3.549% | 0.00847 m | Solver failed; G2 failed |

At Ψ = 336.60685 Wb in the negative-current screen, the six PF-group fit reduced normal RMS only from 3.095% to 2.801%; several exploratory ±50% current bounds were saturated. The 0.1% normal and pressure acceptance levels remain far away. A wider flux sweep is poorly motivated by the steep pressure-jump increase on both sides of the original flux.

## The identified geometric mismatch

The archived CAD plasma-surface seed is

```text
R(θ,φ) = 7.5 + 3 cos θ + 0.01 cos(θ − 16φ) m
Z(θ,φ) = 2.13896943244938 sin θ + 0.01 sin(θ − 16φ) m
```

For this surface, the toroidal unit-normal component changes at the 16-fold frequency. A 16 T toroidal field then contributes directly to `B·n` even if it has no radial error. An independent local field calculation on the archived 96-plane MGRID (`b5758ac6…`, 24 toroidal × 256 poloidal samples; bilinear R/Z interpolation; surface-area-weighted RMS after subtracting the toroidal mean at each θ) gave:

| Plasma seed helical amplitude | TF 16-fold vacuum `B·n` RMS | PF 16-fold vacuum `B·n` RMS | TF `Bφ nφ` RMS |
|---|---:|---:|---:|
| 0.010 m, existing seed | 0.3073 T | 0.0010 T | 0.3060 T |
| 0 m, proposed seed | 0.0276 T | <0.0001 T | 0 T |

The toroidal-field tangent-to-surface geometry accounts for nearly all of the large 16-fold vacuum component. The six PF groups are almost axisymmetric and cannot efficiently cancel it through group-current scaling. Removing the imposed term moves each corresponding seed point exactly 0.010 m, below the recorded CAD shift gates of 0.10 m RMS and 0.25 m maximum. It does **not** change TF coil geometry or MGRID arrays.

The local diagnostic uses the earlier archived MGRID, while the last Kaggle runs report the different SHA-256 `afb07089…`. Their field-array identity has not been established here. Recompute the same mode decomposition on the exact last-run input before accepting the correction; the geometric `Bφ nφ` mechanism itself follows from the surface definition and the 16 T toroidal field. The table is vacuum geometry, not a prediction of final finite-pressure G2 residuals.

## One coordinated run, with no broad parameter sweep

1. **Freeze provenance.** Verify the exact last-run MGRID hash, TF group orientation and signed current, PF group mapping, current ratings, CAD wall clearance, pressure profile, and full G2 metric definitions. The negative-TF sign is the better numerical hypothesis from the completed runs; the signed hardware convention remains unresolved.
2. **Replace only the equilibrium seed.** Set the 16-fold coefficients of the seed to zero, leaving `R=7.5+3 cos θ` and `Z=2.13896943244938 sin θ` before low-order corrections. Use Ψ = 336.60685 Wb and the same 6.1 GWth/core pressure center, approximately 1.273 MPa. Preserve a q96 target of at least 3.0 and the intended plasma-current sign.
3. **Couple field and plasma.** Optimize the six PF currents, allowed low-order axisymmetric R/Z surface modes, and any small 16-fold correction together against both `B·n=0` and finite-pressure magnetic pressure balance. Enforce equilibrium force balance, actual PF current/ramp limits, plasma-wall clearance, CAD movement no greater than 0.10 m RMS and 0.25 m maximum, and a flux/current consistency check. Do not use the old weight-20 CAD tether in place of the hard displacement limits. If current ratings are unavailable, label the result a feasibility candidate, not a hardware-qualified solution.
4. **Make failure informative in the same job.** Save area-weighted `B·n/|B|` and magnetic pressure residual maps split by toroidal Fourier mode, the six PF response columns and singular values, limiting active bounds, geometry shifts, and full-volume force residual. These distinguish a remaining axisymmetric mismatch from a 16-fold correction that would require another actuator.
5. **Refine and independently verify the one selected state.** Use the required L8/L10/L12/L16 ladder, the same profiles and current signs at every level, an independent free-boundary equilibrium comparison, and the predeclared G2 gates: normal RMS ≤0.1%, normal maximum ≤0.5%, pressure-jump RMS ≤0.1%, full force RMS ≤0.1%, CAD shift within the limits. A numerical optimizer-success flag is insufficient.
6. **Increase pressure only on a closed equilibrium.** For the previously discussed 10-core, 40%-efficiency, 3.0-GWe-recirc route to about 22 GWe, the separate 6.65 GWth/core case requires roughly 1.329 MPa center pressure. Repeat the coupled equilibrium, force and ideal-ballooning checks at that pressure, with q96 ≥3.0 and no positive ideal-ballooning growth metric on the evaluated surfaces/field lines (DESC's positive λ denotes instability). Power arithmetic alone is not a stable operating point.

If the exact-field mode decomposition confirms the seed diagnosis but the axisymmetric pressure and force residuals cannot satisfy the hard CAD/current constraints, the documented conclusion is **insufficient control authority in the existing six-group configuration**. Then redesign an appropriate PF/shaping actuator or the plasma reference shape using the saved residual maps; do not increase PF currents outside unknown hardware limits or claim that a different toroidal flux solves it.

## Research basis

- DESC free-boundary tutorial: the finite-pressure boundary conditions, force-balance constraints, and `BoundaryError` optimization: https://desc-docs.readthedocs.io/en/latest/notebooks/tutorials/free_boundary_equilibrium.html
- DESC `BoundaryError` reference: simultaneous normal-field and magnetic-pressure conditions and virtual-casing plasma field: https://desc-docs.readthedocs.io/en/stable/_api/objectives/desc.objectives.BoundaryError.html
- DESC field API: current-group scaling of an MGRID-backed `SplineMagneticField`: https://desc-docs.readthedocs.io/en/latest/_api/magnetic_fields/desc.magnetic_fields.SplineMagneticField.html
- DESC ideal-ballooning tutorial: evaluate the finite-pressure equilibrium along field lines before stability approval: https://desc-docs.readthedocs.io/en/latest/notebooks/tutorials/ideal_ballooning_stability.html
- DESC stage-two coil tutorial: flux consistency matters in addition to normal-field error: https://desc-docs.readthedocs.io/en/latest/notebooks/tutorials/coil_stage_two_optimization.html
