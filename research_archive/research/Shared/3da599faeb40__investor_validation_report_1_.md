# Tomahawk Rev2.2 — Kaggle computational validation report

Run time (UTC): 2026-08-26T04:32:08.110080+00:00
Model revision: `REV22-FROZEN-20260825`
Model specification SHA-256: `ca406cee9733fea0a5969369e1dc9ffd0d4d4994c883f260bee042716f1be661`

## Executive result

This run verifies the frozen implementation, its numerical bookkeeping, its reference-rate implementation, and its repeatability on external CSV inputs. It does **not** establish that the reactor, target, confinement system, RF system, blanket, or power plant will work in hardware.

The all-gate percentages below are conditional on the declared input scenarios. The broad and computational-holdout rows are stress/software checks. The controlled and multifactor rows are proposed design envelopes, not measured probability distributions.

| dataset_role | rows | simultaneous_passes | pass_rate_percent | wilson_95_low_percent | wilson_95_high_percent |
| --- | --- | --- | --- | --- | --- |
| broad_global_stress | 100000 | 184 | 0.184 | 0.159 | 0.213 |
| independent_computational_holdout | 100000 | 189 | 0.189 | 0.164 | 0.218 |
| controlled_envelope_v2 | 100000 | 79555 | 79.555 | 79.304 | 79.804 |
| multifactor_improved_envelope | 100000 | 96107 | 96.107 | 95.985 | 96.225 |

## Verification status

Implementation checks: **PASS**. A failure means the run should not be presented to investors until corrected.

| check | status | detail |
| --- | --- | --- |
| Bosch-Hale D-T reference table | PASS | max relative error=0.3364% at published rounded values |
| Fusion energy partition | PASS | alpha plus neutron power equals total fusion power |
| Captured-heat accounting | PASS | neutron, alpha, and absorbed laser terms reconcile |
| Thermal-to-electric accounting | PASS | high-grade plus low-grade heat equals captured heat |
| Finite and nonnegative core outputs | PASS | fusion output is finite and nonnegative for the probe |
| Laser reference power | PASS | 2.50 MJ/module-shot at 10 Hz maps to 25 MW/module optical input |
| Radial quadrature convergence | PASS | max 32-to-64 relative change=3.519e-06 |
| Repeatability: broad_global_stress | PASS | two evaluations of the same external CSV are bytewise-equivalent in output arrays; 100,000 rows |
| Repeatability: independent_computational_holdout | PASS | two evaluations of the same external CSV are bytewise-equivalent in output arrays; 100,000 rows |
| Repeatability: controlled_envelope_v2 | PASS | two evaluations of the same external CSV are bytewise-equivalent in output arrays; 100,000 rows |
| Repeatability: multifactor_improved_envelope | PASS | two evaluations of the same external CSV are bytewise-equivalent in output arrays; 100,000 rows |

## What this evidence supports

- The same frozen evaluator gives identical output arrays when rerun on the same external CSV.
- The Bosch-Hale D-T reactivity implementation reproduces the rounded reference table used for the audit within the stated tolerance.
- Energy partition, captured-heat accounting, thermal-to-electric accounting, and radial quadrature are internally consistent.
- The scenario results are traceable to input-file hashes, a declared model revision, row counts, and a fixed quadrature setting.

## What it does not support

- It is not experimental validation or independent hardware qualification.
- Synthetic input ranges are not empirical uncertainty distributions, and their pass rate cannot be quoted as a probability that a reactor will operate.
- The model does not solve 3-D MHD equilibrium/stability, target hydrodynamics, RF wave coupling, neutronics/TBR transport, structural FEA, materials lifetime, tritium systems, or plant commissioning risk.
- The 60% threshold, if used, must be described as a pass rate inside a specified computational envelope, not as global feasibility or a field probability.

## Recommended investor wording

"An independently rerunnable Kaggle audit verified the frozen Rev2.2 screening implementation against a published Bosch-Hale D-T reactivity table, conservation/accounting identities, quadrature convergence, repeatability, and external input datasets. The results are preliminary computational evidence and define the next engineering validation gates; they are not a claim of demonstrated reactor performance."

## Source for the reaction-rate benchmark

Bosch-Hale reference-rate values and the reproduced Table 6 are documented in [UWFDM-1268](https://fti.neep.wisc.edu/fti.neep.wisc.edu/pdf/fdm1268.pdf), which cites Bosch and Hale, *Nuclear Fusion* 32 (1992) 611. The original bibliographic record is available from [OSTI](https://www.osti.gov/etdeweb/biblio/5161054).

### Input: Tomahawk_Rev22_Broad_Input_Dataset.csv
- Role: broad_global_stress
- Dataset ID: broad_global_stress
- Rows: 100000
- CSV SHA-256: `25c2253c8f4ad169fb1e5a2a0499f94290fbb393d629e6310bc68047a40057ca`
- Spec SHA-256: `733081a2e088d8ac4b67f827c5bbcc1c417165613ec10a083900f8ab9b2ebcc6`

### Input: Tomahawk_Rev22_Independent_Holdout_Input_Dataset.csv
- Role: independent_computational_holdout
- Dataset ID: INDEPENDENT_HOLDOUT_BROAD_LHS_V1
- Rows: 100000
- CSV SHA-256: `0896b071ee881ce97541af2844d440d47b3d95c03cb9485fddb704501fc6d2a2`
- Spec SHA-256: `8e9c91f03f44a0e8001fc774037e07ebab3da9d9e69aad289dd30788c03fa5d1`

### Input: Tomahawk_Rev22_Controlled_Envelope_v2_Input_Dataset.csv
- Role: controlled_envelope_v2
- Dataset ID: CONTROLLED_ENVELOPE_V2
- Rows: 100000
- CSV SHA-256: `ec9575de38d7d4704ca41e34b0b292e86cf9d1de295997da2a77d26f0ef8ae1d`
- Spec SHA-256: `a4ed7d1183178c324e9e43d2869ca74f2befcb4aec1e90dc87ee6893e96dfc21`

### Input: Tomahawk_Rev22_Multifactor_Improved_Envelope_Input_Dataset.csv
- Role: multifactor_improved_envelope
- Dataset ID: MULTIFACTOR_IMPROVED_ENVELOPE_V1
- Rows: 100000
- CSV SHA-256: `4fd1f320de4cea7e8816e7f2d916f7807c24b26ee7c78562ab2c16b61692959c`
- Spec SHA-256: `8496148ad24dce74a466803dbab2bef81cf05cbd7e6503e97d58b013ec28e6a6`
