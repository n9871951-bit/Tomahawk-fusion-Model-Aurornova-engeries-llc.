# Tomahawk fuel-system foundation analysis — Rev 0.2

Source document: `tech summary new fuel system.pdf`  
Source SHA-256: `399fbf7373cba67f2e7f7d9a01ca9bb34eac7030a5789bc1a2be9822c41b1522`  
Author/date shown in source: Nicole Bryant, 24 May 2026

## What the document establishes

The previously omitted architecture is now identifiable as a coupled
desalination, lithium, tritium, and D-T fuel loop:

```text
hypersaline desalination reject brine
    -> direct lithium extraction (DLE)
    -> LiOH or LiNO3 aqueous ALSB
    -> neutron-driven Li-6 tritium production
    -> HTO-bearing blanket stream
    -> CECE / LPCE
    -> PEM electrolysis
    -> D2/T2 fuel return to the ignition core
```

This is a strong foundation for the black-box interface created previously.
It supplies the process identity and major unit-operation boundaries without
requiring disclosure of proprietary implementation details.

## Correct model interpretation

The DLE stage does not directly manufacture fusion fuel. It supplies lithium
salt feedstock to the ALSB. The new tritium source remains the nuclear
Li-6-neutron reaction in the blanket. The chemical portion performs HTO
handling, isotope transfer, electrolysis, gas production, purification, and
fuel return.

The model therefore treats the architecture as:

- `DLE`: lithium feedstock and salt-makeup accounting;
- `ALSB`: neutron transport, TBR, HTO formation, heat removal, and blanket
  inventory;
- `CECE/LPCE`: tritium transfer from the aqueous phase to the gas phase;
- `PEM`: water splitting and D2/T2 product recovery;
- `fuel return`: usable isotope mass, delay, losses, and ignition injection;
- `plant ledger`: CECE/PEM auxiliary power and process heat.

## Inputs directly recovered from the source

| Quantity | Source value | Model status |
|---|---:|---|
| Primary fuel | D-T gas mixture | architecture input |
| Fast-neutron energy | 14.1 MeV | source design input |
| DLE feed | desalination reject brine | architecture input |
| Lithium concentration | approximately 0.5 ppm Li | declared estimate; requires feed assay |
| DLE recovery | 70–90% per pass | declared range; not a measured result in this PDF |
| Sorbent family | manganese-oxide or titanium-oxide lithium-ion sieve | candidate material input |
| ALSB salt | LiOH or LiNO3 aqueous solution | comparison/design cases |
| Tritium chemical form | HTO | process-state input |
| LPCE temperature | 40–80 °C | declared operating envelope; requires qualification |
| TBR | greater than 1.05 | design target, not demonstrated result |
| Product route | D2/T2 returned to laser ignition system | architecture interface |

## Required additions before a quantitative run

The document identifies the architecture but does not provide the numerical
values needed to close the fuel and plant balances:

1. reject-brine volumetric flow and density;
2. measured lithium concentration and Li-6 atom fraction/enrichment;
3. ALSB lithium inventory, salt concentration, temperature, pressure, and
   residence time;
4. realized 3-D neutron spectrum and TBR from neutronics;
5. HTO capture fraction and ALSB-to-CECE slipstream fraction;
6. LPCE transfer efficiency and processing delay;
7. PEM D2/T2 product recovery and purity;
8. D2 source/feed rate, since lithium breeding alone supplies tritium but not
   deuterium;
9. CECE/PEM electrical power, heat rejection, and water consumption;
10. permeation, inventory, maintenance, and startup-reserve losses.

The new process-specific template leaves these values open rather than
silently substituting optimistic assumptions.

## Claim boundary

The source supports the statement that AuroraNova has defined a proposed
integrated fuel-system architecture. It does not, by itself, establish:

- a realized TBR above 1.05;
- continuous tritium self-sufficiency;
- sufficient DLE lithium throughput;
- CECE/PEM recovery or purity performance;
- net energy after fuel-cycle auxiliary loads; or
- validated operation of an aqueous ALSB under the Tomahawk neutron and heat
  environment.

Those are now explicit model gates rather than hidden assumptions.

