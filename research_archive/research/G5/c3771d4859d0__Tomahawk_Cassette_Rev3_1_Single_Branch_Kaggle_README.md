# Tomahawk Cassette Rev3.1 — Kaggle single-branch runs

The three earlier Kaggle notebooks failed because each copy of the combined evaluator required all three CSV inputs. These corrected notebooks each require only the matching single CSV.

## Run procedure

For each run:

1. Start a new Kaggle notebook from the corresponding `.ipynb` file.
2. Select **Add Input** and attach only the matching CSV dataset.
3. Select **Run All**.
4. Download the branch-specific result bundle written to `/kaggle/working`.
5. Return the executed `.ipynb` and result bundle for verification.

| Notebook | Attach this CSV | Acceptance rule |
|---|---|---|
| `Tomahawk_Cassette_Rev3_1_Controlled_Deposition_Kaggle.ipynb` | `Tomahawk_Cassette_Rev3_Controlled_Envelope_Input.csv` | At least 60% pass all gates |
| `Tomahawk_Cassette_Rev3_1_Engineered_Full_Incident_Kaggle.ipynb` | `Tomahawk_Cassette_Rev3_Engineered_Full_Incident_Input.csv` | At least 60% pass all gates |
| `Tomahawk_Cassette_Rev3_1_Broad_Full_Incident_Challenge_Kaggle.ipynb` | `Tomahawk_Cassette_Rev3_Full_Incident_Stress_Input.csv` | At least one case passes |

The loader can identify a Kaggle-renamed CSV by its required schema and exact `analysis_branch` value. It prints the selected path, row count, SHA-256 hash, and branch before evaluation. A wrong branch is rejected instead of being silently evaluated.

The model equations, constants, and gates are unchanged from the combined Rev3.1 evaluator. Results are deterministic reduced-order screening evidence, not CFD, neutron transport, structural, irradiation, experimental, or hardware validation.
