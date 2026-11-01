# Tomahawk Open Research

Research by **Nicole Marie Bryant / AuroraNova Engeries LLC**.

This archive preserves the Tomahawk research record: Python programs, Kaggle notebooks,
equilibria, CAD, meshes, calculation inputs, outputs, supporting documents, and earlier
iterations. Successful, unsuccessful and incomplete runs are retained with their
original reports. This release does not assign new gate passes.

## Archive coverage

- **636 saved records**, including all 630 records from the 2026-10-28 preservation
  inventory and six additional records.
- **568 distinct original file payloads**, totalling **8,747,085,606 bytes**. Identical
  files are stored once; every original filename and record remains in the catalog.
- **142 standalone notebook records**; the execution index covers 154 distinct
  notebook payloads when notebooks inside archives are included.
- All 630 previously inventoried record checksums match the recovered files.

`research/` contains unchanged, browsable copies of small source files and notebooks.
`catalog/original_records.csv` maps every saved record to its original-file download.
`catalog/release_assets.json` and `catalog/SHA256SUMS.txt` describe all 568 original
downloads, including larger CAD and simulation packages intended for a GitHub release.
Archives are retained byte for byte, including nested originals.

**Publication status:** the source repository is being published at
https://github.com/n9871951-bit/Tomahawk-fusion-Model-Aurornova-engeries-llc.. The code, notebooks, catalog and new thermal screen are in
`research_archive/`. Upload of the complete original CAD and simulation downloads
is pending; see `catalog/PUBLICATION_STATUS.json`. An indexed record does not yet
mean its large original download is available on GitHub.

## Current design entry points

- `Tomahawk_Full_Model.FCStd`: current native assembly, SHA-256
  `2baa050fedaadd737369680b16d4b1edd31847f22be5ee01da8002895342735b`.
- `Tomahawk_FreeCAD_All_Components.zip`: current assembly together with restored
  historical CAD. Historical files remain identifiable as earlier versions.
- `Tomahawk_Full_Model_for_CAD.zip`: source design records, including
  `02_Design_records/equilibrium_N9A2/N9A2_axisymmetric_enlarged_TF.h5`.
  The current native assembly above takes precedence for updated component placement.

Use the catalog to find these exact original filenames and their release-asset names.
Do not combine placements from different iterations without checking their source.

## Gates and results

The investigator identifies G1 through G3 as the officially computed scope.
The preserved archive also contains G4–G7 material; these folder labels are historical
categories, not evidence that those gates were completed. Consult each original report
for its assumptions, criteria and unresolved items. Recorded notebook execution or a
filename containing PASS is not a new verification by this archive.

Some packages use G1/G2 as stage names for CAD/placement and combined-field checks.
Those names must not be confused with geometric G1/G2 surface continuity.

## Dates, integrity and attribution

Original file bytes and embedded archive timestamps are preserved. `record_created_at`
and `record_modified_at` are saved-record metadata; they are not a verified date of
first authorship. Embedded dates, where available, are recorded separately. No original
creation date has been invented or replaced with the publication date.

The catalogs include the earlier preservation record and its 28 embedded-original
entries. `catalog/archive_member_index.json` indexes 15,391 entries inside packages.
An existing nested ZIP in `Tomahawk_Rev22_RMAPLA_Kaggle_PoC_Upload.zip` could not be
opened as a complete ZIP; its bytes are retained as received. See `catalog/KNOWN_ISSUES.md`.

Use `python tools/verify_archive.py --asset-dir /path/to/release_assets` to verify all
original downloads against their recorded SHA-256 hashes. It uses Python's standard
library and does not execute research code.

## Open-source licenses

The investigator selected permissive release terms. See `LICENSE` for the allocation:
MIT for original software, CC BY 4.0 for original research documents and data, and
CERN-OHL-P-2.0 for original hardware-design documentation and CAD. Existing licenses
on external software and datasets remain in place; see `THIRD_PARTY.md`.

The original archival copies are unchanged, including any historical notices. The
release licensing notice states the current permission for material owned by the
investigator. Original authorship and source attribution remain part of the record.
