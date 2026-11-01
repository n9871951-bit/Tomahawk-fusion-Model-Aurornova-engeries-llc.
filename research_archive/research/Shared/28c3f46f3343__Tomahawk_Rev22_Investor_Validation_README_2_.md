# Tomahawk Rev2.2 — Kaggle investor-validation package

## Run in Kaggle

1. Create or upload a Kaggle Dataset containing all files whose names begin with `Tomahawk_Rev22_` in this package.
2. Open `Tomahawk_Rev22_Investor_Validation_Kaggle.ipynb` as a Kaggle Notebook.
3. Attach the dataset with **Add data**.
4. Use **Run All**.

The notebook uses CPU NumPy/Pandas/Matplotlib. A GPU is not required, so the 29.37 GPU-hours allocation can be preserved. The local four-dataset audit evaluates 400,000 external rows, repeats each evaluation, and completes in seconds on a CPU; Kaggle startup time will dominate.

## Files

- `Tomahawk_Rev22_Investor_Validation_Kaggle.ipynb` — one-click audit notebook.
- `Tomahawk_Rev22_Broad_Input_Dataset.csv` — broad global stress input.
- `Tomahawk_Rev22_Independent_Holdout_Input_Dataset.csv` — independent computational holdout; synthetic, not measured data.
- `Tomahawk_Rev22_Controlled_Envelope_v2_Input_Dataset.csv` — proposed controlled tolerance envelope.
- `Tomahawk_Rev22_Multifactor_Improved_Envelope_Input_Dataset.csv` — proposed improvement scenario.
- The four `*_Spec.json` files — row counts, seeds, ranges, and scenario disclosures.

## Outputs

Kaggle writes these to `/kaggle/working/tomahawk_rev22_investor_validation/`:

- `investor_validation_report.md`
- `validation_manifest.json`
- `validation_checks.csv`
- `validation_summary.csv`
- `validation_gate_rates.csv`
- `validation_sensitivity.csv`
- `quadrature_convergence.csv`
- `validation_audit_sample.csv`
- `validation_top_passing_cases.csv`
- two PNG plots

## How to describe the result

Use the result as reproducible computational evidence: implementation verification, reference-rate agreement, accounting identities, numerical convergence, repeatability, and conditional scenario screening. Do not describe the controlled-envelope pass rate as a probability of reactor success. The notebook explicitly records that physical validation still requires experimental data and validated 3-D MHD, neutronics, RF, target, structural, materials, tritium, and plant models.

The Bosch–Hale D–T rate check uses the rounded values reproduced in UWFDM-1268, Table 6; the paper cites Bosch and Hale, *Nuclear Fusion* 32 (1992) 611.
