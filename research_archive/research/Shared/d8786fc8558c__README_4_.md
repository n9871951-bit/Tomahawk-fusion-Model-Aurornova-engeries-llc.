# Tomahawk 16 T G1 validation handoff

This focused package brings together the recovered native G1 boundary audit, the current liquid-wall CAD and its EV007 plasma-boundary subshape, and field grids at the active 16 T baseline.

## Results

- Recovered smooth-boundary G1 native audit: `PASS_PROPOSED_NUMERICAL_CHECKS` (13 required numerical checks). Its source report is included verbatim.
- Formal G1 interface approval in that source report: `UNRESOLVED_PENDING_INTERFACE_REVIEW`; approval is false.
- Current supplied CAD EV007 boundary: BREP validity, closed shell and sampled 16-fold vertex correspondence are audited in `G1_16T_validation_report.json`.
- Active TF/PF MGRID values were interpolated and checked against direct finite-segment TF calculations at every EV007 boundary vertex.
- TF input is 48 physical coils, 100 turns each, −125,000 A per turn; native ampere-turn equivalent is −12.5 MA.

The MGRID axis check is 16.00000010 T TF, with supplied PF retained separately. The native periodic grid and preferred independent FP64 grid are both included. The full direct-grid and independent quadrature records are preserved. No 14 T array was amplitude-rescaled into this case.

The field check covers vacuum fields and geometric sampling. It is not an MHD equilibrium, stability, stress, thermal, optical, reactor, or formal interface approval. The CAD-to-boundary volume comparison is recorded as a diagnostic because the currently supplied boundary is faceted.
