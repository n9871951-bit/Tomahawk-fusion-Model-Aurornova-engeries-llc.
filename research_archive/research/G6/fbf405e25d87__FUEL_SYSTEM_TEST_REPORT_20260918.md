# Tomahawk fuel-system integration test report

Date: 18 September 2026  
Package: `Tomahawk_Rev1_7_Fuel_System_Integration_Test_Package_20260918.zip`  
The final archive checksum is recorded separately after package assembly.

## Result

```text
ALL FUEL-SYSTEM INTEGRATION TESTS PASSED
```

## Tests completed

| Test | Result |
|---|---|
| Foundation DLE/ALSB/CECE/PEM accounting self-test | PASS |
| Realized-neutronics JSON handoff to fuel stage | PASS |
| Missing realized TBR/reaction-rate fail-closed behavior | PASS |
| Rev1.7 runner preflight with five-stage order | PASS |
| Synthetic end-to-end orchestration through FUEL_SYSTEM | PASS |

## Stage order tested

```text
MHD -> NEUTRONICS -> FUEL_SYSTEM -> CFD -> CHF
```

The fuel stage accepts only a machine-readable neutronics handoff containing
`tritium_bred_kg_s`, or both `realized_TBR` and `reaction_rate_s`. The test
does not generate those values; the fixture supplies them explicitly so the
handoff contract can be tested.

## Not tested by this report

No VMEC, OpenMC/DAGMC, NekRS, CHF correlation, 3-D equilibrium, or physical
MHD calculation was run. No TBR, DLE recovery, CECE/LPCE performance, PEM
recovery, or continuous-self-sufficiency claim is established by these tests.
