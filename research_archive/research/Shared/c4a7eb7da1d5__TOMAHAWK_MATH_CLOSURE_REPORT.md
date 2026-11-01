# Tomahawk — calculated mathematical requirements
AuroraNova Engeries LLC · 30 August 2026

**Actual calculations have been added and executed. They solve explicitly specified candidate models; they do not establish a qualified reactor.** The longer alpha slowing run was stopped when you requested faster delivery to conserve credits. No external HPC job was submitted.

| Requirement | Calculation now present | Result and scope |
|---|---|---|
| 3-D MHD equilibrium | Native nonlinear spectral variational solve; current independently calculated from curl B | Full force residual **0.74485%** of pressure-gradient RMS. Nonaxisymmetric, finite-pressure, fixed-boundary candidate; no fitted coil/free-boundary or stability result. |
| Orbit-resolved alpha transport | Full Lorentz/Boris trajectories in the computed 3-D field, plus collisional guiding-center implementation | **1 of 64** markers crosses the last closed flux surface by **100 microseconds** at both time steps. This is **1.5625% prompt LCFS exit**, not eventual wall loss. |
| Target/corona transport | Linear Maxwell-wave solution through underdense and overdense collisional plasma; reflection and deposition resolved | **26.8574%** absorption for the stated 100 micrometer, 2 keV ramp. An inverse 629.049 micrometer ramp gives **86.0024%** in this model. Target hydrodynamic/kinetic qualification remains open. |
| Nuclear-data neutronics | JENDL-5 isotope reaction probabilities; 400,000 first-collision histories per enrichment; thermal absorption competition | Actual evaluated-data screening tallies for S20 at 90% and 95% Li-6. Scattered/secondary neutron transport, full-device capture and TBR are not solved. |
| 10% / 95% / 1.15 | Explicit definitions and neutron/energy balance constraints | These remain design comparisons, not derived device results. |

## 1. Equilibrium equations and the specified solution

The solved equations are

$$\mathbf J\times\mathbf B=\nabla p,\qquad \mathbf J=\mu_0^{-1}\nabla\times\mathbf B,\qquad \nabla\cdot\mathbf B=0.$$

Coordinates are radius $r\in[0,1]$, poloidal angle $\theta$, and geometric toroidal angle $\phi$. The boundary is an explicitly chosen 16-period perturbation of the recovered ellipse:

$$R_b=7.5+3\cos\theta+0.01\cos(\theta-16\phi),$$
$$Z_b=b\sin\theta+0.01\sin(\theta-16\phi),\qquad b=\frac{950/(2\pi^2\,7.5)-0.01^2}{3}.$$

The 1 cm perturbation and $\iota(r)=0.5$ are **study choices**; they are not recovered engineering specifications. This choice makes the calculation genuinely nonaxisymmetric. The prescribed recovered-profile antecedents are

$$n_D=n_T=1.2\times10^{20}(1-r^2)^{0.657}\;\mathrm{m^{-3}},$$
$$T_i=1.25+28.75(1-r^2)^{0.8},\quad T_e=1.25+8.75(1-r^2)^{0.8}\quad[\mathrm{keV}],$$
$$p=(n_D+n_T)(T_i+T_e)10^3e.$$

Here $e$ is the elementary charge. Pressure and temperature are prescribed, not results of a heating/transport solution.

Let $\mathbf x(r,\theta,\phi)$ represent a nested surface, $J_v=R(R_rZ_\theta-R_\theta Z_r)>0$, and $\Psi=\Phi_t r^2/(2\pi)$. The solver uses

$$\mathbf B=\frac{\Psi'}{J_v}\left[(\iota-\lambda_\phi)\mathbf x_\theta+(1+\lambda_\theta)\mathbf x_\phi\right].$$

This representation conserves toroidal flux and enforces divergence-free, surface-tangent fields. The field scale is set by the declared reference flux **294.52454 Wb**, obtained by integrating $B_\phi=14(7.5/R)$ over the unperturbed ellipse. Consequently, 14 T is a reference normalization, not a claim that every point or the magnetic axis has that field.

For pressure prescribed in the moving surface label, the stationary functional is

$$\mathcal F=\int\left(\frac{B^2}{2\mu_0}-p(r)\right)dV.$$

For a fixed-boundary displacement, its first variation gives $-\int\boldsymbol\xi\cdot(\mathbf J\times\mathbf B-\nabla p)dV$. The minus-pressure functional is used for prescribed pressure; it is **not** the adiabatic ideal-MHD stability energy. The implementation expands $R,Z,\lambda$ in regular radial polynomials and poloidal/toroidal Fourier modes, and minimizes this functional.

The reported residual then uses a **separate fourth-order finite-difference curl of the solved field**. It does not define current from the desired pressure force and test that same algebraic identity.

| Independent result | Value |
|---|---:|
| Final spectral resolution $(L,M,N)$ | $(8,8,2)$, 1,016 coefficients |
| Force RMS | 6,046.68 N/m³ |
| Pressure-gradient RMS | 811,797.95 N/m³ |
| Relative full force residual | 0.00744851 |
| Relative full force residual, $0.05<r<0.95$ | 0.000501772 |
| Normalized divergence error | $5.11\times10^{-11}$ |
| Integrated volume | 950 m³ |
| Sampled plasma-field range | 9.85588–23.97554 T |
| Plasma-current magnitude from the boundary Ampere integral | 37.2705 MA |
| Maximum field change on the same Cartesian test points, $(6,6,2)$ to $(8,8,2)$ | $5.45\times10^{-6}$ relative |

Current sign follows the chosen poloidal contour; the table reports its magnitude. A transform sensitivity study gave about **26.8008 MA** at $\iota=0.35$ and **47.6207 MA** at $\iota=0.65$. Those choices also change force-balance solutions; they are not uncertainty bars on a known device current.

Nested surfaces are assumed. Islands, stochastic fields, nonlinear stability, realizable shaping coils, and plasma-current drive are not established by this result. The native research implementation has not been benchmarked against an independently executed equilibrium code.

**Why TF current alone is insufficient:** for a purely toroidal static field, force balance requires

$$\partial_Z\left(p+\frac{B_\phi^2}{2\mu_0}\right)=0,\qquad
\partial_R\left(p+\frac{B_\phi^2}{2\mu_0}\right)=-\frac{B_\phi^2}{\mu_0 R}.$$

Together they require $p$ to be independent of $Z$. The prescribed confined pressure profile is not. A poloidal field/current contribution or different physical model is therefore required; matching a TF field magnitude is not an equilibrium solution.

The original parametric coil centerline extended 1 cm inside the modeled first wall. A separate clearance candidate now uses the exact convex parallel-curve construction

$$\mathbf x_c(\theta)=\mathbf x_w(\theta)+1.18\,\hat{\mathbf n}_w(\theta).$$

The 1.18 m allocation comprises 0.73 m of listed material layers plus explicitly chosen 0.20 m shielding, 0.10 m mechanical clearance, and 0.15 m winding half-width allowances. Exact segment Biot–Savart evaluation gives **327,202 A per 100-turn coil**, for 16 coils and 14 T at $(R,Z)=(7.5,0)$ m. This resolves the geometric overlap for that alternative; it does not fit those coils to the equilibrium above or establish conductor stress/peak field limits.

## 2. Alpha trajectories and the unresolved 10% claim

The full-orbit calculation integrates

$$\dot{\mathbf x}=\mathbf v,\qquad m_\alpha\dot{\mathbf v}=2e\,\mathbf v\times\mathbf B,$$

with a Boris update, 3.5 MeV isotropic births, and birth-position density proportional to $n_Dn_T\langle\sigma v\rangle J_v$. In the solved candidate coordinates, the source integral is **$3.08331\times10^{21}$ births/s**, or **1.72900 GW** alpha birth power. This differs from the old undeformed-mesh source because the prescribed density/temperature now follow the solved flux surfaces. Neither source integral establishes achievable fusion power.

The 100 microsecond run was repeated at **100 ps and 50 ps** steps. Both runs lost the same one marker across the specified LCFS. Its exit time changed by **1.75 ns**. Maximum particle energy change in the finer run was **$2.86\times10^{-13}$ relative**. The cubic field interpolator was checked against the spectral field and its magnetic-magnitude gradient against independent finite differences.

The exact 95% binomial interval for the **finite-time particle-exit probability** is approximately **0.0396%–8.401%**. This does not bound eventual reactor wall loss. About **98.4375% of birth energy remains in tracked particles** at that short horizon.

The collisional guiding-center calculation implements

$$\mathbf B^*=\mathbf B+\frac{m_\alpha v_\parallel}{2e}\nabla\times\mathbf b,\quad B_\parallel^*=\mathbf b\cdot\mathbf B^*,$$
$$\dot{\mathbf X}=\frac{v_\parallel\mathbf B^*+(\mu/2e)\mathbf b\times\nabla B}{B_\parallel^*},\quad
\dot v_\parallel=-\frac{\mu}{m_\alpha}\frac{\mathbf B^*\cdot\nabla B}{B_\parallel^*}.$$

Here $\mathbf b=\mathbf B/B$ and $\mu=m_\alpha v_\perp^2/(2B)$. Published Maxwellian collision moments supply continuous slowing and pitch scattering. The adaptive Cash–Karp integration rejects inaccurate steps without projecting energy onto a desired value. A 1 ms pilot passed its numerical-energy check; it is not a slowing-complete result. Earlier lower-accuracy trials are retained as exploratory records, not accepted production predictions.

The physically required ledger is

$$1=f_{\rm wall}+f_e+f_i+f_{\rm still\ tracked}+f_{<100\,keV}+\epsilon_{\rm numerical}.$$

The present diagnostic uses **first LCFS exit** in place of a wall tally and labels it accordingly. Exterior fields and recapture are missing; energy below 100 keV is unresolved. The attempted 0.25 s run was **interrupted for your credit/time request**. Therefore **10% alpha wall loss is not derived**.

## 3. Corona wave equation and inverse absorption input

For an explicitly prescribed, fully ionized D/T corona,

$$n_c=\frac{\epsilon_0m_e\omega^2}{e^2}=9.04907\times10^{27}\;\mathrm{m^{-3}}\quad(351\;\mathrm{nm}),$$
$$\epsilon(z)=1-\frac{\omega_p^2(z)}{\omega[\omega+i\nu_{ei}(z)]},\qquad
\frac{d^2E}{dz^2}+\frac{\omega^2}{c^2}\epsilon(z)E=0.$$

A passive layered scattering recursion solves this equation without propagating exponentially growing evanescent fields. It includes reflected power, absorption in each layer, and power entering a lossy substrate. Tests recover Fresnel reflection, homogeneous-slab partition invariance, and total reflection from a collisionless overdense half-space. These benchmark the **linear wave solver**, not a reactor target.

For $n_e(z)=5n_cz/L$, constant $T_e$, normal incidence, and a semi-infinite overdense substrate, the 100 micrometer, 2 keV case absorbs **0.26857419**. The 2,400-to-4,800-layer refinement changes absorption by **2.2969232e-05 absolute**; see the exact value in `corona_result.json`.

The two-pass optical-depth approximation $A=1-e^{-\tau}$ gives $\tau_{86\%}=1.96611286$. Its inverted ramp lengths were independently checked with the full-wave calculation:

| Electron temperature | Full ramp length for the inverse 86% case | Full-wave absorption |
|---|---:|---:|
| 0.5 keV | 96.5522 µm | 85.9864% |
| 1 keV | 245.154 µm | 85.9999% |
| 2 keV | 629.049 µm | 86.0024% |
| 5 keV | 2,214.82 µm | 85.9996% |

These lengths close an **inverse linear-corona design problem**. They are not measured target inputs. Spot-radius and pulse-energy-split scans calculate $I=E_{\rm beam}/(\pi r_{\rm spot}^2\Delta t)$ and $a_0=e\sqrt{2I/(\epsilon_0c)}/(m_ec\omega)$ to expose regimes where the linear collision model fails.

Time-dependent target density, temperature, EOS/opacity, ablation, radiation/conduction, nonlinear laser–plasma interactions, and an applicable experimental benchmark remain necessary for qualified target coupling. Absorption is not target gain.

## 4. Evaluated nuclear-data tallies and breeding requirement

Macroscopic cross sections are calculated from isotope number densities:

$$\Sigma_r(E)=\sum_jN_j\sigma_{jr}(E).$$

For a homogeneous slab with normal path length $L$, the uncollided probability and a specified first-collision reaction probability are

$$P_0=e^{-\Sigma_tL},\qquad P_r=\frac{\Sigma_r}{\Sigma_t}(1-e^{-\Sigma_tL}).$$

These expressions were compared with **400,000 Monte Carlo histories for each of two Li-6 enrichments**. The evaluated endpoints are exactly **14.00 MeV** and **0.0253 eV**, not a fabricated continuous spectrum or a silent substitute for the 14.10 MeV source.

For 20 wt% aqueous lithium sulfate at the provisional 1,210 kg/m³ density and 90 atom% Li-6:

| Derived quantity | Value |
|---|---:|
| 14 MeV total macroscopic cross section | 11.15038 m⁻¹ |
| 14 MeV radiative-capture macroscopic cross section | 0.000588511 m⁻¹ |
| 14 MeV listed tritium-channel macroscopic cross section | 0.00679472 m⁻¹ |
| 14 MeV $(n,2n)$ macroscopic cross section | 0.0252010 m⁻¹ |
| Thickness for 95% first collision at normal incidence | 0.268666 m |
| Thermal Li-6 tritium macroscopic cross section | 227.7747 m⁻¹ |
| Thermal terminal absorption fraction on Li-6, homogeneous infinite medium | 0.990287 |

A first collision can be scattering; **95% collision is not 95% capture**. The Li-7 tritium-producing breakup yield is not provided by the selected summary tables and is not silently set to zero for a full-device calculation.

Normalize all reaction counts to one fusion-source neutron. With net neutron multiplication $M$, Li-6 terminal absorption $A_6$, other terminal absorption $A_o$, leakage $L_n$, and other tritium-producing channels $T_7,T_o$:

$$1+M=A_6+A_o+L_n,\qquad\mathrm{TBR}=A_6+T_7+T_o,$$
$$M+T_7+T_o=\mathrm{TBR}-1+A_o+L_n.$$

For TBR 1.15 and leakage 0.05 neutrons/source, the additional budget is **$M+T_7+T_o=0.20+A_o$**. Alternatively, if 95% of all available neutrons undergo terminal thermal absorption, with no Li-7/other tritium channel,

$$\mathrm{TBR}=0.95(1+M)f_6.$$

The 90% enriched S20 case then gives **TBR 0.940773 when $M=0$**, and requires **$M\ge0.222399$** to reach 1.15. These are conditional balance results, not predicted device TBR. The 95% enriched case gives 0.941262 without multiplication.

Full-spectrum moderation, secondary-neutron distributions, geometry/penetrations, structural absorption, photon heating, damage and activation tallies remain uncomputed. Reaction Q-values also mean recovered heat divided by neutron birth energy is not a capture probability.

## Files and reproduction

Numerical outputs are under `math_results/`; code is under `transport/`. The small notebook displays saved results by default and launches no long computation. All current code, input tables, spectra endpoints, coefficients, marker records, and references are included in the ZIP.

From the extracted package directory, explicit reruns are:

```bash
python3 -m transport.variational_mhd --L 8 --M 8 --N 2 --initial math_results/mhd/nonaxisymmetric_L6M6N2.json --output math_results/mhd/repeat.json
python3 complete_math_constraints.py
python3 -m transport.candidate_alpha --output math_results/alpha/repeat_prompt --count 64 --end 0.0001 --dt 5e-11 --full --no-collisions
```

Only if you choose to spend the runtime, the interrupted longer calculation can be restarted with:

```bash
python3 -m transport.candidate_alpha --output math_results/alpha/slowing_32 --count 32 --end 0.25 --dt 1e-7
```

It restarts, rather than resuming a saved particle state. A completed result would still be a candidate-model LCFS tally, not qualified reactor wall loss. Dependencies are NumPy, SciPy, pandas, and a C++17 compiler with OpenMP; no paid job or automatic dependency installation is used. Earlier external DESC/OpenMC/qualified-target adapters remain available for a fully specified physical case.

## Primary references

- [Princeton STELLOPT / VMEC theory](https://princetonuniversity.github.io/STELLOPT/VMEC.html): ideal-MHD equations, nested-surface representation, fixed/free boundaries. The native implementation here is independent research code, not VMEC.
- [PlasmaPy collision-frequency definitions](https://docs.plasmapy.org/en/stable/api/plasmapy.formulary.collisions.frequencies.SingleParticleCollisionFrequencies.html): collision moments used in the recovered stopping tables.
- [ASCOT5 documentation](https://ascot4fusion.github.io/ascot5/): distinction between full-orbit and guiding-center transport; ASCOT was not executed here.
- [JENDL-5 overview](https://wwwndc.jaea.go.jp/jendl/j5/j5.html) and [Li-6 evaluated table](https://wwwndc.jaea.go.jp/jendl/j5/elm/Table/z003/T6.html): evaluated nuclear data. Every isotope table URL is stored in `reference_data/jendl5_endpoint_cross_sections.json`.
- [JENDL-5 reference paper](https://doi.org/10.1080/00223131.2022.2141903).

The recovered project documents, their conflicting blanket alternatives, and all provisional input choices remain documented in `TOMAHAWK_INPUT_RECOVERY_REPORT.md` and `reference_data/recovered_design_excerpts.json`.
