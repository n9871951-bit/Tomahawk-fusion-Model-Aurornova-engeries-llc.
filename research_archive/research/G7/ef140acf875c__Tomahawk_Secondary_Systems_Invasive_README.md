# Tomahawk Secondary Systems — invasive Kaggle run

This package is a deep, reproducible computational audit of the water and lithium downstream tracks. It is designed to test the declared energy interface, scenario convergence, capacity failures, co-production tradeoffs, stress edges, and parameter sensitivity.

It does **not** validate the Tomahawk reactor, net energy, water chemistry, potable-water quality, lithium-extraction chemistry, battery-grade product, equipment life, or commercial economics.

## Run instructions

1. Open a new Kaggle Notebook.
2. Upload `Tomahawk_Secondary_Systems_Invasive_Kaggle_Screen.ipynb`.
3. Run all cells.
4. Leave the default deep-run settings unchanged for the requested long run.
5. Download the generated `tomahawk_secondary_systems_invasive` output folder.

The default run is configured for a minimum of 30 minutes using repeated batches of 250,000 scenarios per branch. The loop stops only after the target time is reached unless `TOMAHAWK_SECONDARY_MAX_BATCHES` is set.

For a short preflight only, set:

```text
TOMAHAWK_SECONDARY_DEEP_RUN=0
TOMAHAWK_SECONDARY_BATCH_SIZE=5000
```

## What is checked

- continuous MW-to-kWh/day conversion;
- water mass balance and energy-capacity closure;
- lithium Li-to-Li₂CO₃-equivalent stoichiometric conversion;
- lithium electrical-capacity failures;
- convergence across repeated batches;
- water/lithium electricity-allocation tradeoffs;
- conservative edge cases and capacity-failure cases;
- rank-based sensitivity of output to declared inputs;
- inventory and read checks for files under `/kaggle/input`.

The notebook does not silently consume an arbitrary Kaggle dataset. If a process dataset is present, it is inventoried. The model remains range-based unless a specific, documented data-integration step is added.

## Safe interpretation

`deep_summary.csv` contains scenario percentiles, not experimental repeatability. `accounting_pass` and `interface_capacity_pass` indicate only that declared arithmetic and interface gates close. They are not process-success probabilities.

Keep these results as diligence and validation-planning material. Do not present them as demonstrated reactor output, potable-water production, or battery-grade lithium production in the Evergreen three-minute pitch.
