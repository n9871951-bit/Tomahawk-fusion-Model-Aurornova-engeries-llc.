# G2 free-boundary continuation: review and recovery plan

VERIFIED = I computed it from your files. DERIVED = analytic argument plus my own numerics, which needs one confirming check inside DESC. I could not run DESC here.

## Summary
The L12 failure is not "needs more iterations". It has four separate causes:

1. **Polarity (DERIVED, most important).** With the engine's setup (iota > 0, Psi > 0, TF = +16 T) the plasma current runs parallel to B_phi. That needs a *negative* PF vertical field at the axis. Your PF set gives **+0.505 T**, so it pushes the plasma outward. Every PF group sitting at its minimum magnitude is exactly what this produces.
2. **Geometry gate (VERIFIED).** The "3 m CAD error" is a theta-orientation artifact.
3. **Force metric (VERIFIED).** The two force metrics use different denominators. At beta of about 1% the optimizer's 1e-3 gate is about 16% of the pressure-gradient force.
4. **Not converged (VERIFIED).** The free solve ended at `maxiter` = 120 and made force balance **176x worse** than its own fixed-boundary start.

## Q1: formulation, signs, units
- MGRID normalization (VERIFIED): stored field x `raw_coil_cur`. On the 16 T grid, axis B_phi = 16.0000 T and PF Bz = +0.5050 T. The engine's PF bounds are built correctly, including the negative PF_M_IN (bounds -29094..-9698 A).
- Polarity (DERIVED):
  - The engine uses `Z_lmn = -b`, mode (-1,0), so Z = -b sin(theta). That is DESC's right-handed convention.
  - B = psi'/(2 pi sqrt(g)) (e_zeta + iota e_theta) with iota > 0 gives poloidal B along -Z at the outboard midplane.
  - That field is produced by a current along **+phi**, parallel to the +16 T toroidal field.
  - A +phi current needs Bv < 0. The PF set gives Bv > 0.
  - Numerical support: fitting the six PF currents to cancel the plasma's own normal field on the smooth boundary gives **PF Bz < 0 for +Ip and > 0 for -Ip** (`g2_preflight_polarity_authority.py`). The nominal +0.505 T matches the -Ip case.
  - Confirm in DESC with one cell: the sign of `eq.compute('current')`, or the sign of the plasma Bz at the axis.
- Your vacuum-only "independent fit prefers 50%" (`independent_field_screen.json`) is close to a tautology. Without the plasma field in the fit, any normal-field least-squares is minimized by the smallest PF. It does not corroborate the DESC result.

## Q2: why all six PF variables sit at 50%
Primary cause: polarity, as above. Second cause: authority, once polarity is fixed.

Plasma needs the following vertical field (Shafranov with your pressure profile, <p> = 732 kPa, li 0.6-1.0), against PF Bz of 0.253 / 0.505 / 0.758 T at 50 / 100 / 150%:

| Ip (MA) | required abs(Bv) | x nominal | vs 150% bound |
|---|---|---|---|
| 18.3 | 0.70-0.75 T | 1.39-1.49 | within |
| 22.6 (q96=4.0) | 0.77-0.83 T | 1.53-1.65 | exceeds |
| 25.5 (q96=3.5) | 0.83-0.90 T | 1.64-1.78 | exceeds |
| 28.9 (q96=3.0, the failed run) | 0.90-0.98 T | 1.78-1.93 | exceeds |

Check: the boundary-normal fit gives 0.57-0.90 T. This was a screen, not a result. My first hand estimate (1.2-1.9 T) used a wrong beta_p, and the numbers above replace it.

Options, in order of cost. I did not infer any hardware rating:
1. Pick the plasma-current direction deliberately: flip the sign of iota, or flip all PF currents. This is a design choice.
2. Run a *diagnostic* free solve with bounds [0.25x, 3.0x] to see what the equilibrium asks for. Compare to hardware ratings afterwards.
3. If more than 1.5x is needed: lower the current requirement, add PF ampere-turns, or move the PF coils.
4. Note: the new `Tomahawk_Rebuilt_Magnetics_Geometry.FCStd` has PF turn counts **21/221/36/114/21/221 = 634**, not the 578 in the MGRID. Decide which PF set is the design of record before the next solve. If 634 is, the PF response must be regenerated.

## Q3: geometry gate
Verified: if only the Z sign differs, the same-theta error is RMS sqrt(2)*b = 3.025 m and max 2b = 4.278 m. The engine reports 3.017 and 4.277 m. The mapping that fixes it (verified identity, error 0.0 m) is theta_cad = -theta_d. The helical term then becomes (theta_d + 16 phi):

    R = R0 + a cos(th) + eps cos(th + 16 phi)
    Z = -( b sin(th) + eps sin(th + 16 phi) )

Proposed gates:
- **A (pass/fail):** two-sided nearest-point distance to the *smooth axisymmetric mean* CAD (eps = 0), with tolerances you set.
- **B (reported):** nearest-point distance to the actual corrugated CAD. Report it, but do not gate below about eps = 10 mm.

Why the corrugation cannot be the equilibrium boundary (DERIVED):
- It is mostly a toroidal "breathing" of the minor radius, with tilt 16 eps / R0 = 0.0213 rad against a 16 T toroidal field.
- That gives a 0.24 T rms TF normal field at the surface (0.307 T reported, including the 1/R weighting).
- The axisymmetric PF set supplies about 0.001 T at 16-fold.
- The engine never imposes the corrugation: the initial surface is smooth and the ripple modes target 0 within +/-3 mm.

Also verified: all three saved states (L12 fixed, L12 free, L16 fixed) differ from the CAD by **2.7-2.8 cm rms / 5.4-5.6 cm max**. The offset is inherited from the starting state (R_min 4.544 m vs 4.49-4.51 m). The free solve moved the boundary by 1 mm or less. That 5.5 cm exceeds the 5 cm placeholder liquid-wall standoff.

## Q4: force-error reconciliation (VERIFIED from the log)
- Absolute / normalized: 1.501e8 N / 2.268e-3 = 6.62e10 N. The fixed state gives 8.538e5 / 1.290e-5 = 6.62e10 N. That is about B^2 V/(mu0 a) = 6.45e10 N.
- B^2/(mu0 p0) = 161. So a DESC-normalized error e equals about 161 e of the p0/a force density.
- Gate 1e-3 corresponds to about 16% of the pressure-gradient force. Final 2.27e-3 corresponds to about 36%. The fixed start 1.29e-5 corresponds to about 0.2%. This is consistent with the independent 0.78 max.
- Keep the existing gate and **add** a pressure-scaled one: rms|F| / rms|grad p| (DESC keys `|F|`, `|grad(p)|`) on the dense grid. Do not close an unconverged state.

## Q5: L16 exit -9
The log ends 407 s after "Starting optimization" with no traceback. That is consistent with the kernel OOM killer at the first Jacobian, but it is not confirmed.
- `g2_memory_monitor.py` is tested here: it polls the PID and its children, plus the cgroup limit, usage and peak.
- Staged continuation: L12 free must pass first, then L14, then L16. Save fixed and free states at each stage.
- If your DESC exposes `jac_chunk_size`, try it. Check `inspect.signature(ObjectiveFunction)`. I have not verified the API.

## Staged plan
- **S0 (minutes, no solve):**
  - Run the preflight.
  - Confirm polarity in DESC.
  - Re-grade the saved L12 states with the corrected gate and pressure-scaled force.
  - Settle the PF turn set (578 vs 634).
- **S1 (L8 free, short):** corrected polarity, bounds [0.25, 3.0]. Success means the PF variables leave their bounds and force error does not degrade by orders of magnitude.
- **S2 (L12 free):** continue until constraints are met, with telemetry on. Save both states.
- **S3 (L14, then L16):** only after S2 passes its own gates.

## Not verified
DESC itself; any 3D or pressure-balance effects in my polarity and authority numbers; hardware ratings; a corrected-polarity run.
