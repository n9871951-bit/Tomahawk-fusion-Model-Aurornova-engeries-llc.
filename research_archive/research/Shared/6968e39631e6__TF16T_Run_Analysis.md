# Tomahawk 16 T full-torus runs, power screen and stability packages: analysis

What I checked myself is marked VERIFIED. What I only read from your files is marked AS REPORTED. I did not re-run the engine or DESC.

## 1. Full-torus field (Runs 1-3): VERIFIED

| Check | Result |
|---|---|
| Plane checkpoints | 96/96 present, all finite (32 per run) |
| Chunk SHA-256 vs each report | 3/3 match; all runs share source manifest 797b100d... |
| Sector-vs-sector max abs dB | 2.47e-5 / 2.24e-5 / 3.57e-5 T (gate 1e-3 T) |
| Axis B_phi (R=7.5, Z=0) | 16.00000000 T, spread +/-1e-7 over 96 planes |
| Axis abs(B) incl. PF | 16.008 T (PF contributes Bz = 0.505 T) |
| Independent Biot-Savart (48 CAD centerlines x 100 turns, my code) | agrees to 1.3e-5 relative at all 9 sampled nodes, including planes 27, 31, 62, 63, 95 |
| Earlier FP64 16-field grid | max abs(B_phi) difference 3.8e-6 T |
| Mirror symmetry plane k vs 96-k across different notebooks | identical flux seed in 26 cross-notebook pairs |

Edge ripple with 96 resolved planes per period: 0.677% at R=10.475, **0.756% at R=10.500**, **0.787% at R=10.510** (outboard edge). The 1% gate passes.

My uniform 1.3e-5 offset against the engine is the same at every node, so it does not affect ripple. The two engine pipelines agree with each other to about 2e-7, so the offset is most likely my midpoint-rule discretisation.

Not available: no zip contains an assembled 96-plane MGRID (`final_mgrid_sha256` is null in all three reports). The ballooning manifest cites an assembled-MGRID digest, afb07089..., but that file was not provided, so it is unverified.

## 2. Power screen: AS REPORTED, arithmetic VERIFIED

10 active modules, usable thermal fraction 0.94006 of fusion power.

| Scenario | Fusion/module | eta | Recirc | Net GWe |
|---|---|---|---|---|
| Provisional profile (the report's own) | 1.87 GW | 0.40 | 3.0 | 4.03 |
| Previous 5 GW assumption | 5.00 GW | 0.40 | 3.0 | 15.80 |
| combined_6p1 | 6.10 GW | **0.46** | 3.5 | 22.88 (19.4 at eta = 0.40) |
| source_only_22 | 6.65 GW | 0.40 | 3.0 | 22.00 |

- 22 GWe is scenario arithmetic. The package says no 16 T plasma response is inferred from the vacuum MGRID.
- The provisional profile gives 1.87 GW/module. Reaching 22 GWe needs about 3.6x that source, or 1.9x density at fixed temperature.
- The combined_6p1 case reaches 22 GWe only by assuming 46% conversion efficiency. At 40% it gives about 19.4 GWe.
- There is an unattributed 0.72 GWe offset between your 15.08 anchor and the same arithmetic (15.80).

### Correction: neutron wall load
Earlier I used 27 and 46 MW/m2. Those belong to the constant-beta B^4 proxy at 13.2 and 22.6 GW/module, not to the 22 GWe path. Scaling linearly from sample 1892060 in your own file (0.901 MW/m2 average and 2.046 MW/m2 peak per GW/module):

| Fusion/module | Average | Peak |
|---|---|---|
| 6.1 GW | 5.5 MW/m2 | 12.5 MW/m2 |
| 6.65 GW | 6.0 MW/m2 | 13.6 MW/m2 |

That is still too high for a solid wall at 100 dpa and 10 dpa per MW-yr/m2 (about 1.7 FPY average, about 0.7 FPY peak), so a replaceable or liquid boundary is still indicated, but the load is roughly 2-3x lower than I said.

## 3. Stability: AS REPORTED

| Model | Case | Result |
|---|---|---|
| s-alpha / Suydam proxy (circular fixed boundary, B0 set to 16 T) | 6.1 GW, original q | **fails**: alpha/alpha_crit 1.59 |
| | 6.65 GW, original q | **fails**: 1.66 |
| | 6.1 / 6.65 GW, revised-shear q (q96 = 4) | passes: 0.68 / 0.71, but needs **26.4 MA** vs 18.3 MA |
| DESC fixed-boundary, real EV007 boundary, nfp = 16, N = 1, p0 = 1.27 MPa | q96 = 4.0, L = 12 | **fails**: ballooning lambda +2.0e-4, Newcomb -0.094; edge current 22.6 MA |
| | q96 = 3.5, L = 14 | passes (lambda -1.4e-4); 25.5 MA |
| | q96 = 3.0, L = 14 / 16 / 18 | passes, converged (lambda -1.02e-3, -0.99e-3, -0.99e-3); 28.9-29.0 MA |

Findings:
- The proxy's "revised shear passes" result is contradicted by DESC at q96 = 4.0.
- A DESC pass needs 25.5 MA or more.
- Equilibrium force residuals are small (rms force over rms(JxB + grad p) is about 5e-4).

Limits:
- The failing q96 = 4.0 case ran only at L = 12, with no convergence study.
- q96 = 3.5 ran at a single resolution.
- DESC was run only at the 1.27 MPa (6.1 GW) pressure, not at 1.33 MPa (6.65 GW).
- Both packages state they are fixed-boundary and not coupled to the coil field.

### Geometry observation
The boundary formula gives a cross-section 3.0 m wide and 2.139 m tall, so b/a = 0.713 (wider than tall). That is outside the elongation range of the IPB98 database (closures.yaml), so IPB98 is not applicable as it stands. Please confirm this is intended.

## 4. Open items
1. Drive and feasibility of 25-29 MA plasma current (bootstrap fraction, current drive, disruption loads).
2. DESC re-run at 1.33 MPa; q96 = 4.0 at L = 14-18; q96 = 3.5 at more resolutions.
3. Free-boundary equilibrium with the assembled MGRID (not done anywhere yet).
4. Confinement: I_p is now definable, but H98 is still missing and IPB98 is out of range.
5. Provenance and a re-hash of the assembled 96-plane MGRID.
6. The eta = 0.46 assumption and the 0.72 GWe offset.

## 5. Corrections to my earlier statements
- The 0.594% TF48 ripple I called "better than the reference" was an aliasing artifact (36 planes per 360 deg against a 7.5 deg coil pitch). The resolved value is about 0.756% at R=10.5. It still passes.
- `tomahawk_entire_model.py` has the `union` fix only. The cache-validation guard I described was not in the delivered file.
- `liquid_wall_geometry.py` does not contain the periodic-surface fix, and your FCStd (24,576 triangulated faces) was not produced by that script as delivered.
- The wall loads of 27 and 46 MW/m2 were for the B^4 proxy cases, not the 22 GWe path (see section 2).
