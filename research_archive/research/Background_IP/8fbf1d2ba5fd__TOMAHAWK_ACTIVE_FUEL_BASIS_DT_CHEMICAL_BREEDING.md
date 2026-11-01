# Tomahawk active fuel basis — D–T chemical breeding

Decision record: 18 September 2026

## Active path

The active Tomahawk fuel model returns to the established closed D–T basis:

```text
D–T fuel injection
    -> D + T fusion
    -> neutron-driven lithium tritium source
    -> HTO capture
    -> CECE / LPCE isotope transfer
    -> PEM D₂/T₂ recovery
    -> purified D₂/T₂ return to injection
```

The existing feedstock and process boundary remain:

```text
desalination reject brine
    -> direct lithium extraction (DLE)
    -> aqueous LiOH or LiNO₃ ALSB
    -> lithium-bearing tritium-breeding stream
    -> HTO handling and chemical recovery
```

The private chemical recipe stays represented by performance-level inputs and
does not need to be exposed in the public model.

## Explicitly inactive for the current run

The blanket-free D–D branch, D–D tritium/He-3 intermediate balance, and
D–He-3 product-control screen are **not governing the active Tomahawk model**.
The prior D–D artifacts remain archived for traceability; they are not deleted
and must not be used as the current fuel-cycle result.

The Rev4 native waveform-conversion component is also held separate from the
fuel-breeding calculation. The active plant conversion baseline returns to the
existing thermal/sCO₂ ledger until a separate conversion study is requested.

## Helium scope

D–T fusion necessarily produces He-4 alpha particles. For this revision they
are treated only as a plasma self-heating/energy-balance product. No He-3 fuel
cycle, D–He-3 secondary reaction, helium breeding path, or helium-exhaust
optimization is included.

## Accounting that remains required

The chemical process does not create tritium nuclei by chemistry. New tritium
must enter through the neutron/lithium nuclear source represented by the
neutronics stage. The fuel-system ledger must retain:

- nuclear tritium production from realized neutronics;
- Li-6 fraction/enrichment and ALSB inventory/state points;
- HTO capture and ALSB-to-CECE slipstream;
- CECE/LPCE transfer efficiency and delay;
- PEM D₂/T₂ recovery and purity;
- D₂ feed and makeup;
- permeation, inventory, maintenance, startup, and decay losses;
- CECE/PEM auxiliary power and process heat.

`TBR > 1.05` remains a design target, not a demonstrated result. The active
fuel stage accepts a realized `tritium_bred_kg_s`, or both `realized_TBR` and
`reaction_rate_s`, from the neutronics handoff.

## Active validation order

```text
MHD -> NEUTRONICS -> FUEL_SYSTEM -> CFD -> CHF
```

The next D–T run should therefore use the chemical-fuel-cycle interface and
D–T consumption demand only; no D–D/He-3 rows should be included in its active
power or fuel-supply ledger.
