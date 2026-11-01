# Tomahawk magnetic correction branch

This directory is a correction branch for the resolved CAD-A2 screening bundle. It preserves the failing 16-coil baseline and adds two explicit design changes:

1. A 48-coil uniformly interleaved TF topology, calibrated to a 14 T plasma-axis toroidal-field target.
2. An explicit shear/current-profile target, `q(rho) = 1.20 + 5.00 rho^2`, derived into a positive toroidal-current-density target instead of relying on the pressure-only equilibrium's nearly flat shear.

## Screening result

The exact finite-segment Biot–Savart screen gives:

| Branch | TF coils | Edge ripple | 1% ripple gate |
|---|---:|---:|---|
| Resolved CAD-A2 baseline | 16 | 25.031% | FAIL |
| Correction candidate | 48 | 0.754% | PASS |

The target-profile proxy gives positive minimum Suydam D and maximum `alpha/alpha_crit < 1` on the supplied pressure profile. This is not a solved equilibrium and is not a qualified stability result.

## Important limits

The 48-coil geometry is an analytic interleaved screening topology, not released mechanical CAD or an as-built conductor definition. The q/current data are design targets, not measured or solver-converged profiles. The correction branch therefore remains blocked at the self-consistent-equilibrium gate.

Before treating this as a design pass, supply and solve:

- PF/shaping-coil geometry, currents, and engineering limits;
- a fixed- or free-boundary Grad–Shafranov / 3-D equilibrium with `p(psi)`, `F(psi)`, and plasma-current closure;
- nonlinear MHD stability and transport checks;
- orbit-resolved alpha transport and qualified neutronics, CFD/CHT, and CHF analyses.

## Files

- `MHD/cad_a2_tf48_interleaved_centerlines.csv` and `MHD/cad_a2_tf48_interleaved_currents.csv`: generated TF correction candidate.
- `MHD/mhd_coil_table_tf48_correction.csv` and `MHD/mhd_input_correction.json`: explicit correction-branch coil/equilibrium input contract.
- `MHD/mhd_shear_target.csv`: explicit q, enclosed-current, current-density, and local proxy target data.
- `MHD/magnetic_correction_input.json`: correction assumptions and required solver contract.
- `magnetic_correction_report.json`: baseline-versus-candidate results and gates.
- `magnetic_correction_manifest.json`: hashes and file inventory for this branch.
- `Tomahawk_Magnetic_Correction_Screen.py`: deterministic reproduction script.

The original baseline inputs remain unchanged in their original paths in this branch.
