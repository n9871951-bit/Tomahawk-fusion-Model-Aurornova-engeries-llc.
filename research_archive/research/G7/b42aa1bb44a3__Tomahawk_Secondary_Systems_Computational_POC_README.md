# Tomahawk Secondary Systems — Computational POC Run

This package is a separate computational POC artifact for AuroraNova's downstream secondary-system models. It does not overwrite or merge with earlier Tomahawk POC or secondary-systems screen files.

## Kaggle run

1. Upload `Tomahawk_Secondary_Systems_Computational_POC_Invasive_Kaggle.ipynb` to Kaggle.
2. Run all cells.
3. Leave the defaults in place for the invasive run: a minimum target runtime of 30 minutes and a batch size of 250,000 rows.
4. Download the folder `tomahawk_secondary_systems_computational_poc` from `/kaggle/working`.

The notebook does not require an input CSV. It creates the row-level computational dataset from the declared model ranges. The primary dataset is:

`secondary_systems_computational_poc_dataset.csv`

The deep run also writes a bounded representative sample:

`deep_poc_dataset_sample.csv`

## What is tested

- Water target throughput versus required electricity and process heat.
- Maximum supported water throughput and resource margins.
- Lithium brine mass balance, product calculation, electricity demand, and target attainment.
- 24-hour energy conversion: 1 MWe = 24,000 kWh/day and 1 MWth = 24,000 kWhth/day.
- Deterministic reproduction with identical seeds.
- Negative controls that must fail when invalid recovery or domain values are injected.
- Convergence, electricity-allocation dispatch, sensitivity ranking, and stress cases.

## Evidence boundary

Each dataset row is a model-generated computational test case with `source_type = model_generated_from_declared_screening_ranges`. It is not an experimental measurement. A `poc_pass` row means only that the declared target is compatible with the declared resource interface and that the explicit computational checks close.

The run does not establish Tomahawk reactor output, net energy, potable-water quality, lithium extraction chemistry, selectivity, impurity rejection, battery-grade certification, equipment lifetime, commercial economics, or experimental process validation.

For the investor deck, use the phrase **computational POC data** or **reproducible secondary-system feasibility model**. Do not describe it as measured process data or validated plant output.

## No-conflict protection

- Dataset ID: `secondary_systems_computational_poc_v1`
- Output folder: `tomahawk_secondary_systems_computational_poc`
- `prior_poc_data_mixed` is hard-coded to `False` and recorded in the manifest.
- The script refuses the two earlier output-folder names: `tomahawk_secondary_systems_screen` and `tomahawk_secondary_systems_invasive`.
