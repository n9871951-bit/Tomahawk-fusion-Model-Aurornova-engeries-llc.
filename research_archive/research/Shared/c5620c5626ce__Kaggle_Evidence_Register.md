# Tomahawk — Kaggle evidence register accompanying the G1 repair

This register references the available Tomahawk notebooks and the preceding chat history. No Kaggle job was rerun, altered, or overwritten. DBC/cosmology is excluded.

## Verified recorded outputs

| Notebook / branch | Recorded result | Meaning |
|---|---|---|
| notebook98960ad648.ipynb — controlled deposition | 1,346 / 1,728 = 77.8935% | Conditional local-deposition screen |
| full-incident.ipynb — broad challenge | 672 / 10,935 = 6.1454% | Historical broad failure map |
| notebook6d6019742f.ipynb — engineered full incident | 336 / 432 = 77.7778% | Narrower engineered envelope |
| cassette-correction.ipynb — Rev3.2 area correction | 6,974 / 10,935 = 63.7769% | Corrected wetted-area model, same broad row count |
| secondary-systems-poc.ipynb | 30.092 minutes; 1,270 batches; 317,500,000 rows per listed process | Synthetic computational POC, not physical process validation |

The three Rev3.1 returned notebooks now inspected contain all five executed code cells and no embedded errors. Earlier missing-file attempts do not negate these later recorded executions.

### Cassette correction: what was actually changed

The Rev3.2 notebook uses square channels and Q/(h A_effective), with A_effective = 0.85 × N_decks × N_channels × 4D_h × L. Its ribbed option still applies Nu × 1.25 and pressure-drop × 1.60; neither multiplier is a resolved 3-D CFD result.

Remaining recorded failures: velocity 2,994; boiling margin 547; velocity + pressure drop 243; temperature + boiling 93; boiling + velocity 81; temperature + boiling + velocity 3. These sum to 3,961 failures.

Sensitivity to area utilization: 0.65 → 54.4033%; 0.70 → 57.3480%; 0.75 → 60.0183%; 0.80 → 62.0302%; 0.85 → 63.7769%; 0.90 → 65.1395%; 1.00 → 67.2702%. The 0.85 assumption is a validation target, not a measured result.

### Secondary systems

Recorded accounting checks were 100%. Median computational POC pass fractions: simplified lithium brine balance 18.5988%, industrial water recovery 47.8428%, seawater RO 59.3164%, thermal desalination 32.4718%. The lithium battery-grade screen was 4.0384%; all process-validity statuses remained NOT_VALIDATED.

## Full prior-work register

| Work | Reported result | Scope / qualification |
|---|---|---|
| Rev2.2 R-MAPLA proof-of-concept screen | 495/262144 = 0.1888%; geometry and laser bookkeeping reportedly passed. | 0-D design-range screen, not absorbed-fluence or plasma validation. |
| Rev2.2 fast million-case broad screen | 1877/1000000 = 0.1877%. | Broad feasibility inputs, not hardware reliability. |
| Local Rev2.2 robustness envelope | 795680/1000000 = 79.568%. | Conditional on narrowed synthetic ranges. |
| Frozen external broad dataset | 184/100000 = 0.184%. | Same frozen equations, external synthetic broad inputs. |
| Original frozen controlled dataset | 79460/100000 = 79.46%. | Superseded by distinct CONTROLLED_ENVELOPE_V2 inputs. |
| Controlled envelope V2 | 79555/100000 = 79.555%. | Synthetic controlled envelope; not measured uncertainty. |
| Multifactor improvement envelope | 96107/100000 = 96.107%. | Design-range changes, not proof of improved physical reactor performance. |
| Four-dataset numerical validation audit | 400000 external rows; broad 0.184%, holdout 0.189%, controlled 79.555%, multifactor 96.107%. | Local preflight reported in chat. A supplied notebook template is not an executed Kaggle record. |
| D-T reference and quadrature checks | Bosch-Hale reference discrepancy reportedly 0.336%; 32-to-64-node change 3.52e-6. | Implementation/reference checks only; not transport or experimental validation. |
| Rev3.1 local-deposition cassette screen | 1346/1728 = 77.8935%. | Executed notebook verified below; local nuclear-deposition assumptions. |
| Rev3.1 full-incident broad challenge | 672/10935 = 6.1454%. | Executed notebook verified below; retain as historical failure map. |
| Rev3.1 engineered full-incident envelope | 336/432 = 77.7778%. | Executed notebook verified below; narrower envelope than broad challenge. |
| Rev3.2 area-corrected full-incident broad challenge | 6974/10935 = 63.7769%. | Executed cassette-correction.ipynb verified below. Effective wetted-area utilization 0.85 remains an assumption. |
| Superseded zero-pass full wall-load branch | Zero passing cases reported in chat; exact executed artifact not recovered in this task. | Do not erase. Superseded reduced-order branch; not a result for repaired G1 geometry. |
| Coupled Ti/Te and self-heating root searches | Earlier positive thermal eigenvalue and no-root baseline discussed; no executed numeric artifacts recovered here. | Retrieved source notebooks are included. A thermal root/eigenvalue does not establish 3-D MHD stability. |
| Rev2.3 equilibrium/MHD feasibility and confinement notebooks | Source templates recovered; uploaded plasma-confinement-validation.ipynb not resolved in this task. | Do not claim a completed 3-D equilibrium/confinement result from the templates. |
| Bayesian MCMC work | Four-chain identifiable-parameter/synthetic-recovery workflow discussed; no completed chain output recovered. | No R-hat, ESS, posterior predictive agreement or measured-data calibration claimed. |
| Secondary-systems checks and computational POC | Executed secondary-systems-poc.ipynb recovered; 30.092 minutes and 1270 batches recorded. | Resource/accounting/target screens, not physical water or lithium process validation. |
| Historical missing-input Kaggle attempts | FileNotFoundError attempts discussed before the successful returned cassette runs. | Those errors are not assigned to the now-recovered successful notebooks. |
| Optical/FRC/toroidal alternatives and 8–20 cm target discussion | Geometry/ray-tracing changes discussed; no additional executed result established here. | Design discussion is not a completed optical-hydrodynamic validation run. |
| G3 / 3-D MHD / alpha / target-corona / neutronics requests | Packages and missing-input work referenced in project history; completed transport/equilibrium output not recovered. | 10% alpha loss, 95% neutron capture and TBR=1.15 must not be promoted from assumptions by this CAD repair. |

Unless explicitly matched above to embedded notebook outputs, values in the prior-work table are historical chat reports, not newly verified executions.

## Artifact inventory

| File | Code cells / execution counts | Output blocks | Evidence status |
|---|---:|---:|---|
| Tomahawk_Cassette_Channel_Topology_Kaggle.ipynb | 6 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Preliminary_Thermal_Neutronics_Screen.ipynb | 10 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev21_Kaggle_No_Extra_Modules.ipynb | 7 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev21_Kaggle_Smoke_Then_Full.ipynb | 8 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_Kaggle_RMAPLA_Smoke_Then_Full.ipynb | 9 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_RMAPLA_Proof_of_Concept_Kaggle.ipynb | 9 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev231_Coupled_TwoTemperature_HardwareInputs_Kaggle.ipynb | 8 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev231_Coupled_TwoTemperature_IonHeating_Kaggle.ipynb | 6 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev231_SelfHeating_RootSearch.ipynb | 9 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev23_Equilibrium_MHD_Feasibility_Kaggle.ipynb | 7 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_v2_0_Kaggle_Fixed.ipynb | 7 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Cassette_Channel_Topology_Solution_Screen_Kaggle.ipynb | 7 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_Fast_Vectorized_MonteCarlo_Kaggle(1).ipynb | 1 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_Fast_Vectorized_MonteCarlo_Kaggle.ipynb | 1 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_Frozen_External_Input_Evaluator_Kaggle.ipynb | 1 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_Investor_Validation_Kaggle(1).ipynb | 1 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| Tomahawk_Rev22_Investor_Validation_Kaggle.ipynb | 1 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| cassette-correction.ipynb | 1 / 1 | 1 | RECORDED_OUTPUTS_INSPECTED |
| full-incident.ipynb | 5 / 5 | 9 | RECORDED_OUTPUTS_INSPECTED |
| notebook6d6019742f.ipynb | 5 / 5 | 9 | RECORDED_OUTPUTS_INSPECTED |
| notebook98960ad648.ipynb | 5 / 5 | 9 | RECORDED_OUTPUTS_INSPECTED |
| secondary-systems-check.ipynb | 5 / 0 | 0 | NO_EMBEDDED_OUTPUTS |
| secondary-systems-poc.ipynb | 1 / 1 | 1 | RECORDED_OUTPUTS_INSPECTED |

NO_EMBEDDED_OUTPUTS means the recovered copy does not establish execution, even when the same workflow was reported elsewhere. It does not prove the user never ran it.

## Hashes and output excerpts

### Tomahawk_Cassette_Channel_Topology_Kaggle.ipynb

Notebook SHA-256: `1c0d8ca266639d4b12696e20ab333a59d47412e31498353a25a147c172cfd1f3`.
Source-code SHA-256: `fe8a4ccb547c26f1f337ab215dd7e68f5690f6335896a6b41400d4483acf5974`.

### Tomahawk_Preliminary_Thermal_Neutronics_Screen.ipynb

Notebook SHA-256: `3bdfaea1de7d66c4ff5a9f7f7778d685015c7bb936cbaa106102c78a98231ec6`.
Source-code SHA-256: `6768b4b0d761f6da9d956627915e79f60c4e2616ca00970e0be080e83089a4a9`.

### Tomahawk_Rev21_Kaggle_No_Extra_Modules.ipynb

Notebook SHA-256: `4bf33e851a5fb3861fdf6c1ed9d4731312033e11c6ef4b582549873142e0d17d`.
Source-code SHA-256: `72a623852bb17ac8943876a8157a57cd3569f6497627e66f43aab2c41772ffee`.

### Tomahawk_Rev21_Kaggle_Smoke_Then_Full.ipynb

Notebook SHA-256: `1f0086d875cc600a60c1abcc970b1baf57408bfb962dbc520292c07588af63e3`.
Source-code SHA-256: `82d4b9d3b92c6f44da3ab10bf761d1761cff541eb9889f0a853c814493ce6c8b`.

### Tomahawk_Rev22_Kaggle_RMAPLA_Smoke_Then_Full.ipynb

Notebook SHA-256: `20f167ac635fe13e5b35cd5740fc3553eaf5988a35e750adf1ee5e894bbf98db`.
Source-code SHA-256: `227bfabad40205936d0c3ad5a7be2843618bdd87926e3ebc2315dfaeceb47276`.

### Tomahawk_Rev22_RMAPLA_Proof_of_Concept_Kaggle.ipynb

Notebook SHA-256: `e343e2672c8a68338606314449f30f701b7fc57060a26f4914e3efa2a5053a12`.
Source-code SHA-256: `1bf7d441830608ea7a2df4f76e5f403b950bdb815801efd53b2d8e305dd7f87f`.

### Tomahawk_Rev231_Coupled_TwoTemperature_HardwareInputs_Kaggle.ipynb

Notebook SHA-256: `b6c9245fb2b6180a73b2a26a769a5a4d3660989d9fd69c00383a5805afed7884`.
Source-code SHA-256: `3562b642b158f750b8da3242c423a3f592c7623919ff9fcaf518f914c15b685f`.

### Tomahawk_Rev231_Coupled_TwoTemperature_IonHeating_Kaggle.ipynb

Notebook SHA-256: `e97cf6111561896d87a3b8aa63aa720905c3150e0896b5abb04fda008a7700ea`.
Source-code SHA-256: `7b1d879a2cebe7a4dc299b9b92d381e1a38d047c5cdc7d8c4d95e98c6368d52f`.

### Tomahawk_Rev231_SelfHeating_RootSearch.ipynb

Notebook SHA-256: `010a7877bd492d7523daf456309b825044d628546efe30e7ed10c09dfc6a7f0b`.
Source-code SHA-256: `880cf57d315b103b5614b0fb6c5819a643b45e5ef8f334f28e9dbcb8f19b1199`.

### Tomahawk_Rev23_Equilibrium_MHD_Feasibility_Kaggle.ipynb

Notebook SHA-256: `9286247d26bbb84979e79ae6325d59ddf6e3b278ace0b6c8cba83c5a9b2b093e`.
Source-code SHA-256: `c538d0c022002e89cf9684d2c884fa1980fb4425a7c8857dddfdac151a0da60d`.

### Tomahawk_v2_0_Kaggle_Fixed.ipynb

Notebook SHA-256: `4bf33e851a5fb3861fdf6c1ed9d4731312033e11c6ef4b582549873142e0d17d`.
Source-code SHA-256: `72a623852bb17ac8943876a8157a57cd3569f6497627e66f43aab2c41772ffee`.

### Tomahawk_Cassette_Channel_Topology_Solution_Screen_Kaggle.ipynb

Notebook SHA-256: `86ba039686860d41fe825be39d3173058e6a8c8df150a175528505ddc091c45e`.
Source-code SHA-256: `b6c589bacc9767957452e9331afb2866c28f4e74a77c671be804d00324581e64`.

### Tomahawk_Rev22_Fast_Vectorized_MonteCarlo_Kaggle(1).ipynb

Notebook SHA-256: `238bd040acb18f61c76b107c84de711641d83f84dc17121fec3c54f529e6c4b8`.
Source-code SHA-256: `0afeccdd934907082c99e1c5e28a6de80f9debe3d6895cc4545fd7c5375e4cae`.

### Tomahawk_Rev22_Fast_Vectorized_MonteCarlo_Kaggle.ipynb

Notebook SHA-256: `992af82d75562c377a0fa66d9207ce08d9703e85165e6e12883388897e953a63`.
Source-code SHA-256: `ef6dca24aeb326bf9ab5fb616fb21529165ab7f15f211aabed85a4e6d32f7f53`.

### Tomahawk_Rev22_Frozen_External_Input_Evaluator_Kaggle.ipynb

Notebook SHA-256: `e9d9521cc6fe95328307e18d57c2cb3d86d2cb726ad0b1add9a60fb57cde9f7d`.
Source-code SHA-256: `5f0626ceb119db72fbac1c22a6394a5c8d91d0f16ef47b672a001ad514238e51`.

### Tomahawk_Rev22_Investor_Validation_Kaggle(1).ipynb

Notebook SHA-256: `a53ee689e1739be0ac3f60ec2efa90e139ff6b8e8e28b5bfccc62351d54180b5`.
Source-code SHA-256: `80369d47aff6f7ae521a852f47113e8ce9733fb3ddf48c15567a20d2a5d41c01`.

### Tomahawk_Rev22_Investor_Validation_Kaggle.ipynb

Notebook SHA-256: `a53ee689e1739be0ac3f60ec2efa90e139ff6b8e8e28b5bfccc62351d54180b5`.
Source-code SHA-256: `80369d47aff6f7ae521a852f47113e8ce9733fb3ddf48c15567a20d2a5d41c01`.

### cassette-correction.ipynb

Notebook SHA-256: `b6fe4eb47ba64a057c5651d027dcec1d831ae5c830745549923c1eca3877fd8d`.
Source-code SHA-256: `6c58d397f6996c15af6b034d1ad75923bcec38251bdfebd8e4db6094ccf760ef`.

### full-incident.ipynb

Notebook SHA-256: `b12b72437b57c1a6102e05196804d34183d277ec807640c800abecd46a5c92d8`.
Source-code SHA-256: `691dd98e970e7de4e7f0a5291ec1e2fe76eb8624d64dafa8b0643bc8049800a9`.

```json
{
  "model": "Tomahawk Cassette Rev3.1 single-branch reduced-order thermal-hydraulic screen",
  "analysis_branch": "full_incident_broad_challenge",
  "scope": "deterministic reduced-order screen; not CFD, neutronics, structural, irradiation, or hardware validation",
  "input_path": "/kaggle/input/datasets/nicolebryant29/cassette/Tomahawk_Cassette_Rev3_Full_Incident_Stress_Input (2).csv",
  "input_sha256": "60cbec591ff27b1bed3f009bb165fcb515b3b9235200dcf4981b55c0f3683a5e",
  "frozen_evaluator_source_sha256": "8e509d0f5ac31fdbef099e14c54324632a72c4495e6895ed5de4f3eea46e4f09",
  "constants": {
    "n_cassettes_per_module": 4,
    "cassette_area_m2": 2.5,
    "rf_power_absorbed_MW_module": 15.0,
    "rho_kg_m3": 950.0,
    "mu_Pa_s": 0.00023,
    "water_k_W_mK": 0.68,
    "cp_J_kgK": 4180.0,
    "cucrzr_k_W_mK": 300.0,
    "minor_loss_K": 3.0,
    "pump_efficiency": 0.7
  },
  "gates": {
    "max_CuCrZr_temperature_C": 300.0,
    "minimum_boiling_margin_C": 10.0,
    "max_velocity_m_s": 5.0,
    "max_pressure_drop_MPa": 0.25,
    "max_pump_power_MW_module": 1.0,
    "max_flow_area_fraction": 0.08
  },
  "summary": {
    "analysis_branch": "full_incident_broad_challenge",
    "rows": 10935,
    "passing_rows": 672,
    "pass_percent": 6.145404663923182,
    "minimum_wall_temp_C": 156.5440161868553,
    "maximum_wall_temp_C": 664.6629995759971,
    "minimum_boiling_margin_C": -400.7629995759971,
    "maximum_velocity_m_s": 15.658414865194535,
    "maximum_pressure_drop_kPa": 674.5579742255012,
    "maximum_pump_power_MW": 0.9888922347623548,
    "minimum_passing_mass_flow_kg_s_module": 482.0574162679426,
    "maximum_passing_mass_flow_kg_s_module": 974.8803827751196
  },
  "acceptance_rule": "passing_rows > 0",
  "acceptance_passed": true,
  "elapsed_seconds": 0.018096646000003602
}
```

### notebook6d6019742f.ipynb

Notebook SHA-256: `6bb3addacf1a754e5ebe59c7de5c19757f32ec7fd600ccada235aca8e7db9595`.
Source-code SHA-256: `11000fc7b7c27d27cdd388e04b58d6991061ae9557788615df41a1f063d5a745`.

```json
{
  "model": "Tomahawk Cassette Rev3.1 single-branch reduced-order thermal-hydraulic screen",
  "analysis_branch": "full_incident_engineered",
  "scope": "deterministic reduced-order screen; not CFD, neutronics, structural, irradiation, or hardware validation",
  "input_path": "/kaggle/input/datasets/nicolebryant29/engineered-full-incident/Tomahawk_Cassette_Rev3_Engineered_Full_Incident_Input (2).csv",
  "input_sha256": "4a40a8d14440b85222b073906409a339a3bfd03633778f126917c5eefbba6d33",
  "frozen_evaluator_source_sha256": "8e509d0f5ac31fdbef099e14c54324632a72c4495e6895ed5de4f3eea46e4f09",
  "constants": {
    "n_cassettes_per_module": 4,
    "cassette_area_m2": 2.5,
    "rf_power_absorbed_MW_module": 15.0,
    "rho_kg_m3": 950.0,
    "mu_Pa_s": 0.00023,
    "water_k_W_mK": 0.68,
    "cp_J_kgK": 4180.0,
    "cucrzr_k_W_mK": 300.0,
    "minor_loss_K": 3.0,
    "pump_efficiency": 0.7
  },
  "gates": {
    "max_CuCrZr_temperature_C": 300.0,
    "minimum_boiling_margin_C": 10.0,
    "max_velocity_m_s": 5.0,
    "max_pressure_drop_MPa": 0.25,
    "max_pump_power_MW_module": 1.0,
    "max_flow_area_fraction": 0.08
  },
  "summary": {
    "analysis_branch": "full_incident_engineered",
    "rows": 432,
    "passing_rows": 336,
    "pass_percent": 77.77777777777779,
    "minimum_wall_temp_C": 228.10501242056534,
    "maximum_wall_temp_C": 284.4704023324976,
    "minimum_boiling_margin_C": -8.870402332497576,
    "maximum_velocity_m_s": 4.97380422122891,
    "maximum_pressure_drop_kPa": 68.15243320674416,
    "maximum_pump_power_MW": 0.09917494417429225,
    "minimum_passing_mass_flow_kg_s_module": 482.0574162679426,
    "maximum_passing_mass_flow_kg_s_module": 967.7033492822967
  },
  "acceptance_rule": "pass_percent >= 60.0",
  "acceptance_passed": true,
  "elapsed_seconds": 0.018435473000181446
}
```

### notebook98960ad648.ipynb

Notebook SHA-256: `6fdf51a9045736fdb86d4ff2ea5ce309fd3bc6522c59668bd4c4e6290f037cf5`.
Source-code SHA-256: `df4a473b6f0d9fa42c81107fe05278bd89088c948e59a15ec085c277d97e9ffc`.

```json
{
  "model": "Tomahawk Cassette Rev3.1 single-branch reduced-order thermal-hydraulic screen",
  "analysis_branch": "transport_deposition_controlled",
  "scope": "deterministic reduced-order screen; not CFD, neutronics, structural, irradiation, or hardware validation",
  "input_path": "/kaggle/input/datasets/nicolebryant29/controlled/Tomahawk_Cassette_Rev3_Controlled_Envelope_Input (1).csv",
  "input_sha256": "ad7edd9e93eb8a1e3d6d6d5f3897e952b47a60b6cadd82355b19c126ec03128f",
  "frozen_evaluator_source_sha256": "8e509d0f5ac31fdbef099e14c54324632a72c4495e6895ed5de4f3eea46e4f09",
  "constants": {
    "n_cassettes_per_module": 4,
    "cassette_area_m2": 2.5,
    "rf_power_absorbed_MW_module": 15.0,
    "rho_kg_m3": 950.0,
    "mu_Pa_s": 0.00023,
    "water_k_W_mK": 0.68,
    "cp_J_kgK": 4180.0,
    "cucrzr_k_W_mK": 300.0,
    "minor_loss_K": 3.0,
    "pump_efficiency": 0.7
  },
  "gates": {
    "max_CuCrZr_temperature_C": 300.0,
    "minimum_boiling_margin_C": 10.0,
    "max_velocity_m_s": 5.0,
    "max_pressure_drop_MPa": 0.25,
    "max_pump_power_MW_module": 1.0,
    "max_flow_area_fraction": 0.08
  },
  "summary": {
    "analysis_branch": "transport_deposition_controlled",
    "rows": 1728,
    "passing_rows": 1346,
    "pass_percent": 77.89351851851852,
    "minimum_wall_temp_C": 157.82468853620173,
    "maximum_wall_temp_C": 347.43441867112904,
    "minimum_boiling_margin_C": -83.53441867112906,
    "maximum_velocity_m_s": 2.420810150938051,
    "maximum_pressure_drop_kPa": 17.765382751921518,
    "maximum_pump_power_MW": 0.003019801903184847,
    "minimum_passing_mass_flow_kg_s_module": 54.22647527910686,
    "maximum_passing_mass_flow_kg_s_module": 113.03827751196172
  },
  "acceptance_rule": "pass_percent >= 60.0",
  "acceptance_passed": true,
  "elapsed_seconds": 0.012671372999989217
}
```

### secondary-systems-check.ipynb

Notebook SHA-256: `001d38b22ae8e2541c713effef4fc28f6b50f94a9d6e4f707df30d2896eb9752`.
Source-code SHA-256: `111b46f513297f50b47929fa8b09696c80224764bf043a0dae4151dc2c96c64e`.

### secondary-systems-poc.ipynb

Notebook SHA-256: `ae63c2238383976a268c34278688885f6e3a4e1a9d6688fa13f29ca994d7ac7f`.
Source-code SHA-256: `e48d55450bdace8a71f6109d3775d06f141ad2b2f1800b2e524ff4bbe1c14521`.

## What carries forward after this CAD repair

| Earlier work | Treatment |
|---|---|
| Source equations, unit tests, input hashes, old outputs | Preserve unchanged as historical evidence |
| Broad / controlled / engineered pass fractions | Keep separate; no new reliability probability inferred |
| Cassette area correction | Retain 63.7769% for its recorded inputs; validate actual CAD channel/header paths and heat transfer before applying it to the assembly |
| Plasma-boundary geometry | New periodic repair gets its own hash, displacement comparison and native G1 audit |
| 16-port optical coupling, field/current fits, confinement, alpha deposition, wall tallies | Revalidate against the repaired boundary and previously enlarged A2 coils; no automatic inheritance |
| Secondary-system accounting | Preserve; capacity claims depend on a validated upstream power/heat balance |

The G1 repair changes no Kaggle dataset, threshold, pass count, cassette geometry, coil geometry or optical-port setting from CAD-A2 1.0. It also does not undo the earlier A2 coil enlargement; that separate change still requires field revalidation.

## Retrieval gaps

The exact executed copies supporting every early Rev2.2 rate, MCMC run, G3 request, zero-pass branch, no-root branch and optical alternative were not all recovered. They are referenced as historical/unverified rather than silently omitted or fabricated.

## Public documentation

Notebook inspection preserves cell execution counts, output/error blocks and file hashes; these remain recorded evidence rather than independent reruns. See [Kaggle notebook documentation](https://www.kaggle.com/docs/notebooks).
