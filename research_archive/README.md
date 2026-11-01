# Tomahawk reactor research archive

**Nicole Marie Bryant / AuroraNova Engeries LLC**

This directory contains technical Tomahawk model files: CAD scripts, coil geometry and current tables, MAKEGRID/XGRID inputs and diagnostics, Kaggle notebooks, plasma and thermal models, configuration files, and recorded screen outputs. Files under `research/` retain their recovered bytes; `catalog/SOURCE_INDEX.csv` gives each path, original filename, byte count, SHA-256 hash, and classification.

## Scope and interpretation

| Area | Status |
| --- | --- |
| G1–G3 | Investigator-identified computed scope; individual reports document their own assumptions and results. |
| G4–G7 | Historical and preliminary development material; folder names do not assert completed gates. |
| `work_in_progress/thermal_response` | Fixed-profile thermal response screen, not a coupled reactor validation. |

Keep historical iterations distinct from the current 16 T geometry. A recorded notebook execution or a report named PASS does not independently validate reactor performance. Consult each calculation and its inputs before citing a result.

## Current CAD basis

`Tomahawk_Full_Model.FCStd` and `Tomahawk_FreeCAD_All_Components.zip` are preserved separately in the source collection. Those native CAD files and larger solver packages are not part of this source-code commit. The current assembly's recorded SHA-256 is `2baa050fedaadd737369680b16d4b1edd31847f22be5ee01da8002895342735b`. Earlier CAD scripts and geometry tables in G1 remain useful for reconstruction, but their placements must be reconciled with the current assembly.

## Authorship and references

Original Tomahawk reactor research, design and modeling are attributed to Nicole Marie Bryant, AuroraNova Engeries LLC. Previously published software, data and literature retain their specific citations and applicable notices. See [COPYRIGHT.md](../COPYRIGHT.md). No chat exports, marketing/solicitation material, or personal preservation inventories are included in this source tree.
