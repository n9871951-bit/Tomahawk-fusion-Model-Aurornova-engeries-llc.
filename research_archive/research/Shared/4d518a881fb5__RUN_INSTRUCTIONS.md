# Tomahawk Rev2.4 Kaggle run — v1.5

Use one of these two input arrangements:

1. Attach `Tomahawk_Rev2_4_Integrated_Screening.py` and
   `tomahawk_rev24_data_inputs_v1_5.zip` as Kaggle inputs, then run
   `integrated-screening.ipynb` from the first cell through the last cell.
2. Attach `Tomahawk_Rev2_4_Integrated_Screening_Package_v1_5.zip` as the only
   model/data input, then run the same notebook.

Do not attach older Rev2.4 runner or data packages. The notebook rejects stale,
ambiguous, incomplete, or hash-mismatched inputs with `INPUT_BLOCKED` before it
produces a screening result.

Expected successful markers:

- `Runner: TOMAHAWK-REV2.4-INTEGRATED-SCREEN-1.5`
- `SMOKE_PASS`
- `FULL_SCREEN_PASS`
- overall status `SCREENING_PASS_WITH_EXTERNAL_BLOCKERS`

The result is a reproducible numerical screening artifact. It does not qualify
free-boundary 3-D MHD, nonlinear MHD stability, orbit-resolved alpha transport,
nuclear-data neutronics, CFD/CHT, CHF/DNBR, secondary-system capacity, or
hardware performance.
