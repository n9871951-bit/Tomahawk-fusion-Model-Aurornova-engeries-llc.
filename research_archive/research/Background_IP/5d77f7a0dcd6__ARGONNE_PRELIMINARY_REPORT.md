# Tomahawk Revision 2.1 Kaggle Preliminary Screening Report

Generated: 2026-08-25T04:22:38.664330+00:00

## Scope

This run evaluates the corrected Revision 2.1 algebra, a bounded uncertainty screen, and a separate
nearest-feasible design-point search. It is a preliminary model-consistency exercise for discussion
with Argonne. It is not evidence that the reactor, target, magnet, blanket, tritium system,
materials, or power plant will achieve the stated performance.

## Run record

- Mode: full
- Completed Monte Carlo cases: 2,097,152 of 2,097,152
- Elapsed runtime: 0.028 hours
- Random/scramble seed: 20260824
- Active modules: 10; hot standbys: 2
- CAD plasma volume used in integrals: 950.0 m3
- Circular torus reference volume: 1332.40 m3
- Circular first-wall reference area: 888.26 m2
- 351 nm critical density: 9.050e+21 cm^-3 = 9.050e+27 m^-3
- 35 T magnetic-pressure load scale: 487.41 MPa; this is not solved winding-pack stress
- Initial absolute D-T prefill pressure: 0.300 Pa at 300.0 K

## Locked target ledger

- 5.00 GW D-T fusion-source target per active module
- 5.00 GWth captured-heat target per active module
- 50.0 GWth captured heat across ten active modules
- 20.0 GWe gross target at a 40% equivalent cycle efficiency
- Recirculating ceiling: 3.0 GWe, including laser, non-laser loads, and hot standbys
- Net export target: 17.0 GWe
- Delivered-laser target gain: at least 200
- UV wall-plug efficiency development target: at least 15%
- Realized TBR acceptance target: at least 1.15
- Selected-point arithmetic tau_E margin target: at least 20% above the alpha self-heating threshold

The uncertainty model does not force the 40% equivalent efficiency. It decomposes high- and
low-grade heat so that the net-output claim passes only when the sampled heat split, conversion
efficiencies, and auxiliary loads close.

## Nearest-feasible design point

The global Monte Carlo median is not an operating point. This constrained search keeps the
profiled baseline assumptions, sets explicit reserve targets of 18% UV wall-plug efficiency and
TBR 1.18, and searches density scale, edge temperature, temperature peaking, and confinement time
for the smallest change that clears the programmed gates plus a 20% arithmetic tau_E robustness
margin. These are design assumptions to validate, not measurements.

| design_status | density_scale | Ti_edge_keV | gamma_T | tau_E_s | tau_E_required_alpha_self_heating_s | tau_E_margin_ratio | wallplug_efficiency | TBR | fusion_GW_module | captured_heat_GWth_module | target_gain | self_heating_ratio | gross_GWe_hub | recirculating_GWe_hub | net_GWe_hub | engineering_gain | prefill_pressure_abs_Pa | core_equivalent_pressure_Pa | prefill_to_core_density_ratio | minimum_gate_margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| feasible_with_margin | 1.06 | 1.25 | 0.75 | 1.36 | 1.0863 | 0.25193 | 0.18 | 1.18 | 5.4159 | 5.2953 | 216.64 | 1.2342 | 20.44 | 2.7219 | 17.718 | 7.5095 | 0.3 | 0.63661 | 2.122 | 0.021996 |

The companion `design_candidates.csv` file contains the next-nearest points in the same bounded
search window.

## Confinement audit

The selected point clears the zero-dimensional alpha self-heating threshold only if the assumed
energy-confinement time is real. The audit rearranges the modeled balance
`P_alpha,deposited >= P_brem + W/tau_E` to obtain the minimum tau_E, and performs a small deterministic
degradation sweep. This is an arithmetic threshold check, not a confinement measurement.

| overall_status | arithmetic_power_balance_status | empirical_scaling_status | equilibrium_status | closed_flux_surface_status | tau_E_assumed_s | tau_E_required_alpha_self_heating_s | tau_E_margin_percent | self_heating_ratio | P_alpha_deposited_GW_module | P_loss_GW_module | lawson_n_tau_T_keV_s_m3 | beta_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PRELIMINARY_ONLY__CONFINEMENT_NOT_LOCKED | PASS_THRESHOLD | BLOCKED_MISSING_INPUTS | NOT_SOLVED | NOT_EVALUATED | 1.36 | 1.0863 | 25.199 | 1.2342 | 0.96906 | 0.78516 | 2.9562e+21 | 0.89313 |

The empirical-scaling status is intentionally blocked. A conventional IPB98(y,2)-style estimate needs
plasma current, shape/elongation, q95, and an equilibrium/current profile that this notebook does not
have. Closed flux surfaces, force balance, MHD stability, transport coefficients, and power-loss
channels therefore remain unvalidated. `confinement_tau_scan.csv` shows how the selected point responds
to a +/-10% change in the assumed tau_E.

## Deterministic checks

| case | fusion_GW_module | target_gain | self_heating_ratio | beta_percent | captured_heat_GWth_module | gross_GWe_hub | net_GWe_hub | neutron_wall_avg_MW_m2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ideal_uniform_20keV | 7.2186 | 288.75 | 1.0007 | 1.1903 | 7.0512 | 27.218 | 24.218 | 6.5106 |
| profiled_20_to_1keV | 4.2584 | 170.34 | 0.81744 | 0.76469 | 4.1678 | 16.088 | 13.088 | 3.8407 |

The uniform 20 keV row is an algebra check. The profiled row demonstrates why the unresolved edge
temperature and temperature peaking parameters materially affect the fusion result. Smoke and full
runs use different quadrature resolutions; the full-run values are the final screening values.

## Gate pass rates

| gate | passed | tested | pass_percent |
| --- | --- | --- | --- |
| gate_fusion_source | 263213 | 2097152 | 12.551 |
| gate_target_gain | 293982 | 2097152 | 14.018 |
| gate_wallplug | 1047981 | 2097152 | 49.972 |
| gate_self_heating | 432440 | 2097152 | 20.62 |
| gate_tritium | 328108 | 2097152 | 15.645 |
| gate_captured_heat | 199156 | 2097152 | 9.4965 |
| gate_gross_electric | 122827 | 2097152 | 5.8568 |
| gate_recirculating | 1359080 | 2097152 | 64.806 |
| gate_net_export | 129865 | 2097152 | 6.1924 |
| gate_all | 3976 | 2097152 | 0.18959 |

## Approximate uncertainty statistics

These P05/P50/P95 values come from a deterministic reservoir sample of the completed Monte Carlo run.
Exact gate counts use every completed case.

| metric | P05 | P50 | P95 | mean |
| --- | --- | --- | --- | --- |
| fusion_GW_module | 1.6716 | 3.2298 | 5.9396 | 3.44 |
| alpha_GW_module | 0.33242 | 0.64229 | 1.1812 | 0.68409 |
| neutron_GW_module | 1.3392 | 2.5875 | 4.7584 | 2.7559 |
| target_gain | 65.577 | 130.07 | 246.63 | 139.5 |
| self_heating_ratio | 0.26745 | 0.69968 | 1.3075 | 0.7289 |
| driven_heating_ratio | 0.27922 | 0.72765 | 1.3389 | 0.75382 |
| beta_percent | 0.46633 | 0.73812 | 1.1705 | 0.768 |
| brem_MW_module | 39.25 | 67.042 | 111.25 | 70.091 |
| thermal_energy_GJ_module | 0.56151 | 0.81576 | 1.1789 | 0.83586 |
| tau_E_required_alpha_self_heating_s | 1.1337 | 1.6867 | 2.6693 | 1.7665 |
| tau_E_margin_ratio | -0.76268 | -0.33162 | 0.35149 | -0.28754 |
| captured_heat_GWth_module | 1.5869 | 3.0548 | 5.6048 | 3.2523 |
| effective_cycle_efficiency | 0.31266 | 0.3611 | 0.41685 | 0.36258 |
| gross_GWe_hub | 5.6509 | 11.022 | 20.577 | 11.793 |
| laser_electric_GWe_hub | 1.1708 | 1.667 | 2.5005 | 1.7329 |
| recirculating_GWe_hub | 2.0641 | 2.8028 | 3.7106 | 2.8322 |
| net_GWe_hub | 2.757 | 8.2019 | 17.762 | 8.961 |
| engineering_gain | 1.9108 | 3.944 | 7.8819 | 4.2947 |
| neutron_wall_avg_MW_m2 | 1.4099 | 2.7854 | 5.2703 | 2.9913 |
| neutron_wall_peak_MW_m2 | 2.3547 | 5.0438 | 10.366 | 5.5305 |
| divertor_avg_MW_m2 | 0.72023 | 2.0666 | 5.9897 | 2.5361 |
| ALSB_flow_kg_s_module | 4847.9 | 9978.8 | 20033 | 10889 |
| T_burn_g_h_hub | 106.88 | 206.51 | 379.77 | 219.95 |
| T_bred_g_h_hub | 108.8 | 213.89 | 399.65 | 228.72 |
| T_returned_g_h_hub | 106.85 | 210.14 | 392.61 | 224.71 |
| T_surplus_g_h_hub | -28.463 | 4.0055 | 40.904 | 4.7638 |
| minimum_gate_margin | -0.83862 | -0.57457 | -0.17968 | -0.54645 |

## Top candidate table

The table below contains passing cases ranked by net output. A passing row is still only a mutually consistent
screening point, not a validated design point.

| sample_id | fusion_GW_module | target_gain | self_heating_ratio | TBR | effective_cycle_efficiency | gross_GWe_hub | recirculating_GWe_hub | net_GWe_hub | minimum_gate_margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 99686 | 10.128 | 342.75 | 1.3908 | 1.1706 | 0.40437 | 39.162 | 2.5076 | 36.654 | 0.017952 |
| 1013660 | 9.5059 | 473.2 | 1.497 | 1.163 | 0.42883 | 38.475 | 2.2918 | 36.183 | 0.011347 |
| 1731067 | 9.7991 | 369.07 | 1.3872 | 1.1542 | 0.406 | 38.173 | 2.5925 | 35.58 | 0.0036934 |
| 334197 | 10.519 | 453.2 | 1.7194 | 1.1512 | 0.37708 | 37.861 | 2.3957 | 35.466 | 0.0010236 |
| 474393 | 10.412 | 384.71 | 1.3694 | 1.1879 | 0.39282 | 37.385 | 2.8941 | 34.491 | 0.032939 |
| 447151 | 9.9942 | 387.75 | 1.4938 | 1.1832 | 0.38382 | 36.737 | 2.4294 | 34.308 | 0.028854 |
| 503338 | 9.8124 | 483.63 | 1.1627 | 1.1694 | 0.39349 | 36.666 | 2.678 | 33.988 | 0.016853 |
| 763178 | 9.0654 | 391.48 | 1.2981 | 1.1804 | 0.43322 | 36.03 | 2.1225 | 33.908 | 0.026456 |
| 1035456 | 10.128 | 356 | 1.8358 | 1.1864 | 0.39194 | 36.452 | 2.5506 | 33.901 | 0.031669 |
| 1384433 | 9.3817 | 372.22 | 1.5239 | 1.1655 | 0.39661 | 36.526 | 2.8752 | 33.651 | 0.013472 |
| 1796278 | 9.9535 | 479.54 | 1.7597 | 1.1986 | 0.39378 | 35.958 | 2.3382 | 33.62 | 0.042288 |
| 122508 | 9.6668 | 328.19 | 1.3322 | 1.1823 | 0.41291 | 36.224 | 2.7743 | 33.45 | 0.028045 |
| 693944 | 9.3786 | 316.87 | 1.5514 | 1.1745 | 0.40764 | 35.789 | 2.7157 | 33.073 | 0.021278 |
| 614748 | 9.2385 | 409.2 | 1.1903 | 1.1733 | 0.41788 | 35.553 | 2.6886 | 32.864 | 0.020276 |
| 403231 | 9.8552 | 407.68 | 1.1449 | 1.1904 | 0.36816 | 34.938 | 2.2291 | 32.708 | 0.035143 |

## Leading sensitivities

| feature | rank_correlation_net_GWe | rank_correlation_gate_margin | importance_rank_score |
| --- | --- | --- | --- |
| Ti0_keV | 0.60832 | 0.54079 | 0.60832 |
| density_scale | 0.49112 | 0.43236 | 0.49112 |
| gamma_T | -0.38025 | -0.31626 | 0.38025 |
| fuel_fraction | 0.31439 | 0.31309 | 0.31439 |
| tau_E_s | -0.003804 | 0.27443 | 0.27443 |
| gamma_n | -0.15639 | -0.12639 | 0.15639 |
| eta_high_grade | 0.15033 | 0.11533 | 0.15033 |
| high_grade_heat_fraction | 0.14602 | 0.1115 | 0.14602 |
| Ti_edge_keV | 0.11846 | 0.097885 | 0.11846 |
| wallplug_efficiency | 0.076887 | 0.074835 | 0.076887 |
| nonlaser_aux_GWe | -0.071054 | -0.061095 | 0.071054 |
| neutron_heat_capture | 0.054615 | 0.041818 | 0.054615 |
| repetition_rate_Hz | -0.042573 | -0.03665 | 0.042573 |
| eta_low_grade | 0.04151 | 0.032095 | 0.04151 |
| alpha_deposition | -0.0015567 | 0.039994 | 0.039994 |

## Mandatory interpretation limits

1. No three-dimensional coil-current equilibrium or closed-flux-surface solution is performed.
2. No resistive-MHD stability spectrum, nonlinear mode evolution, or field-line wall-strike map is solved.
3. The 351 nm driver is represented by delivered energy, repetition rate, coupling, and gain bookkeeping;
   no capsule/target hydrodynamics, laser-plasma instability, debris clearing, or chamber recovery is solved.
4. TBR is an input scan, not a neutron-transport result. A value at or above 1.15 is not proof that the
   beryllium-free ALSB geometry breeds enough tritium.
5. First-wall and divertor numbers are area-average screens. Local heat flux, DPA, erosion, stress,
   fatigue, joints, and irradiation properties require CAD-coupled analysis.
6. The aqueous ALSB flow is assigned only the low-grade heat fraction. Chemistry, boiling margin,
   radiolysis, corrosion, MHD pressure loss, and tritium speciation are not closed.
7. The sCO2 result is a heat-grade efficiency decomposition, not a state-point or turbomachinery solution.
8. The 17.0 GWe target is defensible only if gross generation, laser efficiency, all auxiliary loads,
   availability, and the two standby modules close simultaneously.
9. Magnetic field is not used as an independent B^4 power multiplier in this run. B0 affects beta and
   magnetic-pressure reporting only; a field-to-performance relation requires a solved equilibrium and
   confinement model. Density scaling and beta-field scaling must not be multiplied as independent gains.
10. The design-point solver is a bounded algebraic search, not an optimizer coupled to equilibrium,
    transport, neutronics, materials, or controls models. Its result must be treated as a validation
    target rather than a demonstrated output.
11. The confinement audit is a threshold and sensitivity report. It must not be described as proof of
    confinement until a 3-D equilibrium/closed-flux-surface solution, a validated transport model, and
    experimental or high-fidelity simulation evidence for tau_E are supplied.

## Files to take to Argonne

- baseline_checks.csv
- design_point.csv
- design_candidates.csv
- confinement_audit.csv
- confinement_tau_scan.csv
- gate_pass_rates.csv
- uncertainty_quantiles.csv
- top_passing_candidates.csv or closest_to_feasible_candidates.csv
- sensitivity_importance.csv
- parameter_definitions.csv
- all plots in the plots folder
- config.json and run_manifest.json for reproducibility

