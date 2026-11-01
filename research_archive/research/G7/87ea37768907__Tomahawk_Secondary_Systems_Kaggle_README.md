# Tomahawk Secondary Systems — Kaggle run guide

This package is a bounded feasibility screen for two downstream opportunity tracks associated with the Tomahawk concept:

- water processing: seawater reverse osmosis, thermal desalination, and industrial-water recovery;
- lithium: a simplified brine-to-lithium mass balance.

It is not reactor validation, plant validation, chemistry validation, potable-water certification, battery-grade certification, or a production forecast.

## Run it on Kaggle

1. Create a new Kaggle Notebook.
2. Upload `Tomahawk_Secondary_Systems_Kaggle_Screen.ipynb`, or copy its cells into the notebook.
3. Run all cells.
4. Download the generated `tomahawk_secondary_systems_screen` output folder if you want the CSVs, manifest, and plot.

The notebook is deterministic by default:

- seed: `20260829`;
- samples per branch: `10,000`;
- normalized interface: `1 MWth` of process heat plus `1 MWe` of electricity.

The normalized interface is deliberate. It keeps the screen from presenting an unvalidated Tomahawk reactor output as a demonstrated plant capability. The notebook converts continuous MW to 24-hour energy explicitly: 1 MWe = 24,000 kWh/day and 1 MWth = 24,000 kWhth/day.

## What the outputs mean

The water outputs show the throughput compatible with declared energy and recovery ranges if a validated interface supplied the normalized heat/electricity. The RO electric range is anchored to DOE's water-energy report; the other ranges are labeled screening assumptions in the notebook.

The lithium outputs show the mass balance implied if a brine had the declared concentration and a process achieved the declared recovery and purity. They do not model direct-lithium-extraction chemistry, sorbent selectivity, impurity rejection, crystallization, or product certification.

`accounting_pass_percent` means that the declared arithmetic, mass-balance identity, and normalized-interface capacity gates closed. It must not be described as process success, reactor success, or probability of success. Every branch is marked `NOT_VALIDATED` for process validity. The lithium branch now enforces the available electrical interface instead of merely reporting energy use.

## Local smoke-test reference

With the default seed and normalized interface, the local run produced these median scenario outputs:

| Track | Median output | Interpretation |
|---|---:|---|
| Seawater RO | 6,231.3 m³/day | Energy-bounded screen from 1 MWe using the DOE-anchored electric range |
| Thermal desalination | 483.9 m³/day | Energy-bounded screen using declared thermal/electric assumptions |
| Industrial-water recovery | 2,384.9 m³/day | Energy-bounded screen using declared recovery assumptions |
| Lithium mass balance | 2,041.1 kg/day* | Broad brine scenario; 54.99% of rows fit the normalized 1 MWe interface |

*The lithium all-scenario median is 2,041.1 kg/day. Among the 54.99% of rows that fit within the normalized 1 MWe electrical interface, the median is 1,246.6 kg/day. Use neither number as a Tomahawk production claim.

These values are scenario outputs, not proof-of-concept results for the reactor or downstream processes. They should stay out of the investor deck until the underlying interface, feed conditions, process assumptions, and validation pathway are independently supported.

## Optional environment controls

The Python script accepts these environment variables:

- `TOMAHAWK_SECONDARY_SEED`
- `TOMAHAWK_SECONDARY_SAMPLES`
- `TOMAHAWK_PROCESS_HEAT_MWTH`
- `TOMAHAWK_PROCESS_ELECTRIC_MWE`
- `TOMAHAWK_SECONDARY_OUTPUT_ROOT`

## Reference anchors

- DOE water-energy report: https://www.energy.gov/sites/prod/files/2016/06/f32/Capturing%20the%20Benefits%20of%20Integrated%20Resource%20Management%20for%20Water%20%26%20Electricity%20Utilities%20and%20their%20Partners.pdf
- DOE geothermal lithium overview: https://www.energy.gov/hgeo/geothermal/lithium
