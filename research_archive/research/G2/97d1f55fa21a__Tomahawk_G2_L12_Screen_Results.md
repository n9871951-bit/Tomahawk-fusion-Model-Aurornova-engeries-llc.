# Tomahawk G2 L12 design screens — 16 October 2026

Exact 16 T / 16 field period, seven-group MGRID; map SHA-256 `afb07089205aa3d2cdfa03d53b48298ae5092f23c0e70db72938c21f59a78013`. DESC 0.17.3, L12/M12/N3. Fixed TF current −125000 A; six PF currents initially 0.5 nominal (signed); baseline pressure center 1.266985 MPa, raised case 1.329001 MPa. Toroidal flux and iota profile fixed. All boundary metrics use the same M18/N7 grid, force metric the same M20/N6 volume grid.

| Re-solved case | Normal max | Pressure max | Force RMS | Solver status |
|---|---:|---:|---:|---|
| baseline | 0.079944 | 0.020700 | 0.0000713 | converged |
| R00_low | 0.080403 | 0.015674 | 0.0000760 | iteration limit |
| R10_high | 0.081876 | 0.016431 | 0.0000933 | converged |
| R20_low | 0.080415 | 0.017642 | 0.0000870 | converged |
| Zm10_low | 0.079768 | 0.018389 | 0.0002047 | converged |
| Zm10_high | 0.080083 | 0.022597 | 0.0000907 | converged |
| Zm20_high | 0.080408 | 0.017835 | 0.0000882 | converged |
| combined_fit | 0.080787 | 0.012261 | 0.0001191 | converged |
| combined_high_pressure | 0.081301 | 0.012461 | 0.0001147 | converged |

The normal-field and magnetic-pressure normalized maximum gates are each ≤0.001; the normalized force RMS gate is ≤0.001. None of the shape cases closes both boundary gates. The lowest normal-field maximum of the individually changed modes is 0.079768 (`Zm10_low`). The combined shape lowers pressure error but retains normal error near 0.081. The one `R00_low` case hit its iteration limit despite a small final force residual; treat it as a directional screen.

## Combined shape at increased pressure

- Pressure center: 1329000.62 Pa (1.048947 times baseline).
- Normal-field maximum: 0.081301, or 81.3 times the gate. Magnetic-pressure maximum: 0.012461, or 12.5 times the gate.
- Force RMS: 0.0001147. Symmetric nearest-point CAD section distance: 0.01319 m RMS, 0.02828 m maximum; under the shape gates of 0.1 m and 0.25 m. This geometric sampling is not a BREP validity audit.
- Seven-radius ideal ballooning proxy (8 field-line labels, 3 turns, 601 points per line): worst lambda -0.00095236 ≤0 and minimum Newcomb metric 0.01450575 ≥0. This is a proxy screen, not a complete stability qualification.
- Bounded six-group PF fit on this fixed high-pressure surface selects scales [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]; no reduction in normal-field error. These bounds are the exploratory 0.5–1.5 nominal range, not verified electrical ratings.

## Interpretation

Within the tested 15 mm axisymmetric Fourier-coefficient envelope and the signed PF-current range, the existing field map offers no G2 closure. The combined high-pressure state satisfies the force, sampled CAD shape, and declared ballooning proxy screens; it fails both boundary-error gates. An engineering follow-up should vary PF coil placement or coil geometry, recompute the 16 T MGRID, and re-solve force balance at 1.329 MPa before claiming a closed state. These screens do not provide a net-electric power prediction.

## Reproduction files

The ZIP includes the JSON gate outputs, normalized residual arrays, force-solve logs, L12 equilibrium checkpoints, and Python scripts. It omits the 651,589,664-byte MGRID. The original `Tomahawk_G2_Corrected_Input_v2.zip` containing `mgrid_tomahawk_16T_TF_PF_16FP_FULL_RECOMPUTED.nc` is required to rerun the field calculations. The scripts verify its SHA-256 before loading.
