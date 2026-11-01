# TOMAHAWK SIS Rev 3.2 — R0 Audit + MODEL_CLOSURE Notebook: README

## What this is
`TOMAHAWK_SIS_R0_MODEL_CLOSURE.ipynb` — executes exactly `AUDIT_ONLY` and
`MODEL_CLOSURE` as defined in SIS Rev 3.2 Section 3.4. It does **not** run
`FULL_CONFINEMENT`, `FUEL_PLANT`, or `UQ_MCMC`. This was verified by actually
running the notebook end-to-end in both `AUDIT_ONLY` and `MODEL_CLOSURE`
mode (pure numpy/scipy — no execution-environment blockers here, unlike a
JAX/MCMC stack).

## What it produces
- Bosch-Hale D-T reactivity: validated against the SIS's own quoted 20 keV
  anchor (0.005% agreement) and basic physical-shape sanity (finite,
  positive, monotonic rise to 30 keV). **Not** validated against a full
  Bosch & Hale (1992) reference table — see "A mistake caught mid-build"
  below.
- Geometry/profile algebraic identities (EQ-GEO/EQ-PROF): all match
  analytic values to machine precision; prefill mass reproduces the SIS's
  quoted 0.571 g to 0.66%; the Greenwald-equivalent diagnostic reproduces
  the SIS's quoted ~41 MA once a unit bug (caught during testing, see below)
  was fixed.
- A regenerated `MODEL_CLOSURE` package (parametric mesh, 16 Biot-Savart
  coils, Ti/Te profiles, Bosch-Hale alpha/neutron source, 16-port ray map,
  blanket bookkeeping), independently built from the equations in
  `Tomahawk_Model_Closure_Adjustment_Map_Rev3_2.md` rather than copied from
  it. It reproduces that document's own numbers closely wherever the input
  was fully pinned down (κ=0.713000922 exact match; deposition-fraction
  0.9000000000000001 exact match down to the same floating-point artifact;
  coupled power 21.5 MW exact match) and differs where a free parameter
  (coil minor radius) wasn't specified — labeled as such, not forced to
  match.
- An honest seven-gate table: **G1/G2/G5/G6/G7 = NOT ASSESSABLE, G3 = FAIL
  (zero torque by construction of the radial-focus closure), G4 =
  UNRESOLVED.** No gate is marked PASS, because none of the six blocking
  handoffs (real CAD, real coil data, measured profiles, orbit-resolved
  alpha, real ray/coupling data, neutronics transport) were supplied — this
  is reported explicitly as `INPUT_BLOCKED` for `FULL_CONFINEMENT`,
  `FUEL_PLANT`, and `UQ_MCMC` rather than silently skipped.

## Two mistakes caught and fixed during this build (reported, not hidden)
1. **Fabricated Bosch-Hale reference table.** An early draft compared the
   reactivity fit against a "reference table" typed from memory. Most rows
   were imprecise and produced a spurious 14.6% "discrepancy" at 1 keV that
   wasn't a real problem with the fit — the fit matches the SIS's own
   quoted 20 keV value to 0.005%. That fabricated table was deleted rather
   than kept as padding; the notebook now states plainly that a full
   reference-table check is `OPEN` pending an actual digitized source
   (e.g., attach the real Bosch & Hale 1992 Table VII as a CSV to close
   this item for real).
2. **Greenwald-equivalent unit bug.** A stray `*10` in the diagnostic
   comparison gave 409 MA instead of the SIS's quoted ~41 MA. Caught by
   comparing against the SIS's own quoted figure, not left in.

## What this notebook is not, and will not become
`MODEL_CLOSURE` output is deterministic algebra, not evidence. It cannot be
promoted to a `FULL_CONFINEMENT` claim by re-running it, by relabeling its
outputs, or by supplying more deterministic closures for the same six
handoffs. The only way any G1–G7 gate moves off NOT ASSESSABLE/UNRESOLVED/
FAIL is real CAD, real coil data, measured or solved (not algebraic)
profiles, an orbit-resolved alpha map, real per-port ray/coupling data, or
an actual neutronics transport tally, per SIS Section 3.3.1.

## Suggested next step
Per the notebook's own final-report "exact next action": supply one real
handoff, starting with a non-radial 16-port impact parameter or a verified
target/corona coupling model (G3 is the gate closest to being assessable
from a single new input, since the current radial-focus closure produces
exactly zero torque by construction — the adjustment-map document itself
names this as the first diagnostic adjustment to make). Re-run
`MODEL_CLOSURE` with that one file replaced and diff against this run's
`run_manifest.json` to see exactly what moved.
