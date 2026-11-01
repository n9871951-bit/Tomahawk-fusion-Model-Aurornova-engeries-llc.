# D-D cycle / Rev4 native conversion integration screen

Status: **coupling screen, not hardware validation**

## Placement

The Rev4 component is placed after a field-guided charged-product exhaust/collector. Its input is the outward waveform at the receiver boundary; raw plasma and unconditioned charged particles do not enter the DAB or grid inverter.

`D-D products -> charged exhaust/collector -> directional receiver/matching -> native rectifier -> protected DC link -> DAB/inverter`

Neutrons remain on a separate shielding/thermal path. This is therefore a charged-energy recovery and product-control interface, not a blanket replacement for neutron handling.

## Coupled result at the field-screen candidate

At T=30 keV, density multiplier=10, and the prior 10 s product-retention case, the screen gives **5.469 GW** total D-D-cycle power, **2.208 GW** charged-product power, and **3.261 GW** neutron power. The He-3 secondary-burn fraction is **0.09701**, with a beta≤5% axis-field target of **19.82 T**.

To hold the reduced-order He-3 burn fraction at 1%, the exhaust target is **tau_He3 <= 0.9402 s**. At that target, the screen gives **3.066 GW** total, **1.411 GW** charged, and **1.655 GW** neutron power; the beta≤5% field target moves to **19.56 T**.

## What the conversion component can handle

The native conversion ledger can recover the charged portion according to:

`P_grid_gross = P_charged * f_capture * f_product_to_waveform * (1-r_reflected) * eta_rectifier * eta_DAB * eta_inverter`

The current Rev4 package leaves those efficiencies, the product-to-waveform coupling, calibrated terminal traces, and drive/auxiliary loads unfilled. The CSV sweep exposes those two upstream coupling fractions rather than treating them as demonstrated performance. Its output is gross or ‘before drive/aux’ power, not plant net power.

The key design split is: the exhaust/collector establishes the He-3 residence-time target; the Rev4 component conditions and converts the validated charged-product waveform. The converter alone cannot suppress D-He-3 reactions.

## Files

- `conversion_product_integration_results.csv`: locked screen cases.
- `conversion_product_integration_sweep.csv`: notional coupling sensitivity.
- `conversion_product_integration_summary.json`: machine-readable provenance, equations, and guardrails.
