"""FreeCAD macro for an auditable PF/CS centerline export.

This macro reads the existing finite-turn PF winding-pack tables, creates
axisymmetric centerline geometry in FreeCAD, and exports the coil tables that
are needed as input to a real MAKEGRID/native equilibrium workflow.

It deliberately does not invent missing currents, conductor dimensions,
current limits, mgrid data, or solver results.  The generated FCStd file is
wire/centerline CAD for solver preparation, not a fabrication release or a
native-solver result.

Run from the FreeCAD Python console with:

    import runpy
    runpy.run_path(r'C:\\path\\Tomahawk_PF_CAD_MAKEGRID_Export.py',
                   run_name='__main__')

The macro opens a file picker. Select either pf_winding_pack_turns.csv or the
canonical Tomahawk_Kaggle_Data.zip. If the turns CSV is selected, the matching
pf_winding_pack_screen.csv is found beside it or in a nearby engineering
folder. If it cannot be found, the macro asks for it explicitly.
"""

from __future__ import print_function

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import time
import zipfile

VERSION = "PF-CAD-MAKEGRID-EXPORT-1.3"
POINTS_PER_TURN = 128


def _freecad_modules():
    try:
        import FreeCAD as App
        import Part
    except ImportError as exc:
        raise RuntimeError(
            "Run this macro from the FreeCAD Python console; FreeCAD/Part "
            "could not be imported: %s" % exc
        )
    try:
        import FreeCADGui as Gui
    except ImportError:
        Gui = None
    return App, Part, Gui


def _qt_widgets():
    for module_name in ("PySide", "PySide2", "PySide6"):
        try:
            module = __import__(module_name, fromlist=["QtWidgets"])
            return module.QtWidgets
        except ImportError:
            continue
    raise RuntimeError("FreeCAD Qt widgets could not be imported.")


def _file_picker(title, file_filter):
    QtWidgets = _qt_widgets()
    application = QtWidgets.QApplication.instance()
    if application is None:
        application = QtWidgets.QApplication([])
    path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
        None, title, "", file_filter
    )
    if not path:
        raise RuntimeError("Cancelled: no input file selected.")
    return Path(str(path)).resolve()


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _select_consistent_duplicate(candidates, label, base=None, preferred_relative=None):
    candidates = [Path(path) for path in candidates]
    if not candidates:
        raise RuntimeError("No %s found." % label)

    hashes = {path: _sha256(path) for path in candidates}
    if len(set(hashes.values())) > 1:
        def display(path):
            if base is not None:
                try:
                    return path.relative_to(base).as_posix()
                except ValueError:
                    pass
            return str(path)

        details = ", ".join(
            "%s=%s" % (display(path), digest[:16])
            for path, digest in hashes.items()
        )
        raise RuntimeError(
            "Duplicate %s files differ; refusing to choose one. %s" %
            (label, details)
        )

    chosen = None
    if base is not None and preferred_relative is not None:
        for path in candidates:
            try:
                if path.relative_to(base).as_posix() == preferred_relative:
                    chosen = path
                    break
            except ValueError:
                continue
    if chosen is None:
        chosen = candidates[0]

    if len(candidates) > 1:
        print(
            "IDENTICAL_DUPLICATES_ACCEPTED:",
            len(candidates),
            label,
            "copies; selected",
            chosen,
        )
    return chosen.resolve()


def _require_nonempty_file(path, label):
    path = Path(path)
    if not path.is_file():
        raise RuntimeError("%s was not created: %s" % (label, path))
    size = path.stat().st_size
    if size <= 0:
        raise RuntimeError("%s was created but is empty: %s" % (label, path))
    return path


def _new_output_dir(parent):
    parent = Path(parent).resolve()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = parent / ("Tomahawk_PF_CAD_Output_" + stamp)
    suffix = 1
    while candidate.exists():
        candidate = parent / ("Tomahawk_PF_CAD_Output_%s_%d" % (stamp, suffix))
        suffix += 1
    return candidate


def _safe_extract(archive, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(archive)) as source:
        for member in source.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise RuntimeError("Unsafe ZIP member rejected: %s" % member.filename)
        source.extractall(str(destination))


def _locate_turns_csv(selected):
    if selected.suffix.lower() == ".zip":
        base = selected.parent / (selected.stem + "_PF_CAD_INPUT_" + time.strftime("%Y%m%d_%H%M%S"))
        _safe_extract(selected, base)
        candidates = sorted(base.rglob("pf_winding_pack_turns.csv"))
        if not candidates:
            raise RuntimeError(
                "The ZIP does not contain pf_winding_pack_turns.csv."
            )
        canonical_relative = "Tomahawk_Kaggle_Data/MHD/engineering/pf_winding_pack_turns.csv"
        return _select_consistent_duplicate(
            candidates,
            "pf_winding_pack_turns.csv",
            base=base,
            preferred_relative=canonical_relative,
        )
    if selected.name.lower() != "pf_winding_pack_turns.csv":
        raise RuntimeError(
            "Select pf_winding_pack_turns.csv or Tomahawk_Kaggle_Data.zip; received %s." % selected.name
        )
    return selected


def _locate_screen_csv(turns_path):
    candidates = []
    for parent in [turns_path.parent] + list(turns_path.parents):
        candidate = parent / "pf_winding_pack_screen.csv"
        if candidate.is_file() and candidate not in candidates:
            candidates.append(candidate)
        if len(candidates) >= 2:
            break
    if len(candidates) == 1:
        return candidates[0].resolve()
    if len(candidates) > 1:
        return _select_consistent_duplicate(
            candidates,
            "pf_winding_pack_screen.csv",
        )
    selected = _file_picker(
        "Select the matching pf_winding_pack_screen.csv",
        "PF screen CSV (pf_winding_pack_screen.csv)",
    )
    if selected.name.lower() != "pf_winding_pack_screen.csv":
        raise RuntimeError("The selected current-limit file must be pf_winding_pack_screen.csv.")
    return selected


def _read_csv(path):
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError("CSV has no header: %s" % path)
        reader.fieldnames = [str(field).strip() for field in reader.fieldnames]
        rows = []
        for row in reader:
            rows.append({str(key).strip(): value.strip() if isinstance(value, str) else value
                         for key, value in row.items()})
    return reader.fieldnames, rows


def _number(row, field, path, row_number):
    value = row.get(field)
    if value in (None, "", "null", "None"):
        raise RuntimeError("Missing %s in %s row %d." % (field, path, row_number))
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise RuntimeError("Non-numeric %s in %s row %d: %r" % (field, path, row_number, value))
    if not math.isfinite(value):
        raise RuntimeError("Non-finite %s in %s row %d." % (field, path, row_number))
    return value


def _required_columns(fieldnames, required, path):
    missing = [field for field in required if field not in fieldnames]
    if missing:
        raise RuntimeError("Missing columns in %s: %s" % (path, ", ".join(missing)))


def _signed_current(row, path, row_number):
    current = _number(row, "operating_current_A", path, row_number)
    direction = _number(row, "current_direction_sign", path, row_number)
    if abs(abs(direction) - 1.0) > 1.0e-9:
        raise RuntimeError("current_direction_sign must be +/-1 in %s row %d." % (path, row_number))
    # The retained table stores negative operating currents directly for the
    # negative-current coil and uses direction_sign=1 there. Preserve that
    # signed value; apply direction_sign to nonnegative magnitudes.
    return current if current < 0.0 else abs(current) * direction


def _load_and_validate(turns_path, screen_path):
    turns_fields, turns_rows = _read_csv(turns_path)
    screen_fields, screen_rows = _read_csv(screen_path)
    _required_columns(
        turns_fields,
        ["coil_id", "turn_id", "R_m", "Z_m", "operating_current_A", "current_direction_sign"],
        turns_path,
    )
    _required_columns(
        screen_fields,
        ["coil_id", "operating_current_A", "reference_current_limit_A", "turn_count"],
        screen_path,
    )
    if not turns_rows:
        raise RuntimeError("No winding turns found in %s." % turns_path)
    if not screen_rows:
        raise RuntimeError("No coil screen rows found in %s." % screen_path)

    screen_by_coil = {}
    for row_number, row in enumerate(screen_rows, 2):
        coil_id = row.get("coil_id", "")
        if not coil_id or coil_id in screen_by_coil:
            raise RuntimeError("Missing or duplicate coil_id in %s row %d." % (screen_path, row_number))
        screen_by_coil[coil_id] = row

    turns_by_coil = {}
    for row_number, row in enumerate(turns_rows, 2):
        coil_id = row.get("coil_id", "")
        if not coil_id:
            raise RuntimeError("Missing coil_id in %s row %d." % (turns_path, row_number))
        radius = _number(row, "R_m", turns_path, row_number)
        _number(row, "Z_m", turns_path, row_number)
        if radius <= 0.0:
            raise RuntimeError("R_m must be positive in %s row %d." % (turns_path, row_number))
        _number(row, "turn_id", turns_path, row_number)
        row["_signed_current_A"] = _signed_current(row, turns_path, row_number)
        turns_by_coil.setdefault(coil_id, []).append(row)

    if set(turns_by_coil) != set(screen_by_coil):
        raise RuntimeError(
            "Coil IDs differ between tables. Turns-only=%s; screen-only=%s." % (
                sorted(set(turns_by_coil) - set(screen_by_coil)),
                sorted(set(screen_by_coil) - set(turns_by_coil)),
            )
        )

    validated = []
    for coil_id in sorted(turns_by_coil):
        coil_turns = turns_by_coil[coil_id]
        screen = screen_by_coil[coil_id]
        currents = [row["_signed_current_A"] for row in coil_turns]
        current = currents[0]
        tolerance = max(1.0e-6, abs(current) * 1.0e-8)
        if any(abs(value - current) > tolerance for value in currents[1:]):
            raise RuntimeError("Operating current changes between turns for %s." % coil_id)
        screen_current = _number(screen, "operating_current_A", screen_path, 0)
        limit = abs(_number(screen, "reference_current_limit_A", screen_path, 0))
        declared_turns = int(round(_number(screen, "turn_count", screen_path, 0)))
        if declared_turns != len(coil_turns):
            raise RuntimeError(
                "Turn-count mismatch for %s: screen=%d, turns CSV=%d." %
                (coil_id, declared_turns, len(coil_turns))
            )
        if abs(screen_current - current) > max(1.0e-5, abs(current) * 1.0e-7):
            raise RuntimeError(
                "Current mismatch for %s: turns=%g A, screen=%g A." %
                (coil_id, current, screen_current)
            )
        if abs(current) > limit + max(1.0e-6, limit * 1.0e-9):
            raise RuntimeError(
                "Current-limit screen fails for %s: |I|=%g A > limit=%g A." %
                (coil_id, abs(current), limit)
            )
        validated.append({
            "coil_id": coil_id,
            "turns": coil_turns,
            "screen": screen,
            "operating_current_A": current,
            "reference_current_limit_A": limit,
            "turn_count": len(coil_turns),
        })
    return validated


def _set_property(obj, property_type, name, group, value):
    obj.addProperty(property_type, name, group)
    setattr(obj, name, value)


def _make_document(App, Part, coils):
    doc = App.newDocument("Tomahawk_PF_CAD_MAKEGRID")
    group = doc.addObject("App::DocumentObjectGroup", "PF_Coil_Centerlines")
    group.Label = "PF coil centerlines (finite-turn input)"
    for coil in coils:
        edges = []
        for turn in coil["turns"]:
            radius = float(turn["R_m"])
            z_value = float(turn["Z_m"])
            circle = Part.Circle(App.Vector(0.0, 0.0, z_value), App.Vector(0.0, 0.0, 1.0), radius)
            edges.append(circle.toShape())
        feature = doc.addObject("Part::Feature", "PF_" + coil["coil_id"])
        feature.Label = "PF %s | %d turns | I=%+.6g A" % (
            coil["coil_id"], coil["turn_count"], coil["operating_current_A"]
        )
        feature.Shape = Part.makeCompound(edges)
        _set_property(feature, "App::PropertyString", "CoilID", "Input", coil["coil_id"])
        _set_property(feature, "App::PropertyInteger", "TurnCount", "Input", coil["turn_count"])
        _set_property(feature, "App::PropertyFloat", "OperatingCurrentA", "Input", coil["operating_current_A"])
        _set_property(feature, "App::PropertyFloat", "ReferenceCurrentLimitA", "Input", coil["reference_current_limit_A"])
        _set_property(feature, "App::PropertyString", "GeometryStatus", "Audit", "FINITE_TURN_CENTERLINES_ONLY")
        _set_property(feature, "App::PropertyString", "QualificationStatus", "Audit", "NOT_QUALIFIED")
        feature.ViewObject.LineWidth = 2.0
        feature.ViewObject.LineColor = (1.0, 0.25, 0.25) if coil["operating_current_A"] >= 0.0 else (0.25, 0.45, 1.0)
        group.addObject(feature)
    metadata = doc.addObject("App::FeaturePython", "PF_CAD_Audit_Metadata")
    metadata.Label = "PF CAD export audit metadata"
    _set_property(metadata, "App::PropertyString", "MacroVersion", "Audit", VERSION)
    _set_property(metadata, "App::PropertyString", "CoordinateConvention", "Audit", "R_phi_Z; axisymmetric loops with phi 0..2*pi")
    _set_property(metadata, "App::PropertyInteger", "PointsPerTurnForExport", "Audit", POINTS_PER_TURN)
    _set_property(metadata, "App::PropertyString", "NativeSolverEvidence", "Audit", "NOT_PRESENT")
    _set_property(metadata, "App::PropertyString", "MgridStatus", "Audit", "NOT_GENERATED")
    _set_property(metadata, "App::PropertyString", "EngineeringStatus", "Audit", "MODEL_DERIVED_SCREEN_INPUT_NOT_QUALIFIED")
    doc.recompute()
    return doc


def _write_exports(output_dir, turns_path, screen_path, coils):
    output_dir.mkdir(parents=True, exist_ok=True)
    centerline_path = output_dir / "pf_makegrid_centerlines.csv"
    current_path = output_dir / "pf_makegrid_currents.csv"
    manifest_path = output_dir / "pf_cad_export_manifest.json"

    with centerline_path.open("w", newline="") as handle:
        fields = [
            "coil_id", "turn_id", "point_id", "R_m", "phi_rad", "phi_deg", "Z_m",
            "X_m", "Y_m", "current_A", "signed_current_A", "current_direction_sign"
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for coil in coils:
            for turn in sorted(coil["turns"], key=lambda row: int(round(float(row["turn_id"])) )):
                radius = float(turn["R_m"])
                z_value = float(turn["Z_m"])
                current = float(turn["_signed_current_A"])
                direction = 1 if current >= 0.0 else -1
                for point_id in range(POINTS_PER_TURN + 1):
                    phi = 2.0 * math.pi * point_id / float(POINTS_PER_TURN)
                    writer.writerow({
                        "coil_id": coil["coil_id"],
                        "turn_id": int(round(float(turn["turn_id"]))),
                        "point_id": point_id,
                        "R_m": "%.12g" % radius,
                        "phi_rad": "%.12g" % phi,
                        "phi_deg": "%.12g" % (phi * 180.0 / math.pi),
                        "Z_m": "%.12g" % z_value,
                        "X_m": "%.12g" % (radius * math.cos(phi)),
                        "Y_m": "%.12g" % (radius * math.sin(phi)),
                        "current_A": "%.12g" % abs(current),
                        "signed_current_A": "%.12g" % current,
                        "current_direction_sign": direction,
                    })

    with current_path.open("w", newline="") as handle:
        fields = [
            "coil_id", "turn_count", "operating_current_A", "operating_current_abs_A",
            "reference_current_limit_A", "current_margin_A", "within_reference_limit",
            "source_current_status"
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for coil in coils:
            current = coil["operating_current_A"]
            limit = coil["reference_current_limit_A"]
            writer.writerow({
                "coil_id": coil["coil_id"],
                "turn_count": coil["turn_count"],
                "operating_current_A": "%.12g" % current,
                "operating_current_abs_A": "%.12g" % abs(current),
                "reference_current_limit_A": "%.12g" % limit,
                "current_margin_A": "%.12g" % (limit - abs(current)),
                "within_reference_limit": "true" if abs(current) <= limit else "false",
                "source_current_status": "MODEL_DERIVED_SCREEN_INPUT_NOT_QUALIFIED",
            })

    manifest = {
        "schema_version": "TOMAHAWK-PF-CAD-MAKEGRID-EXPORT-0.1",
        "macro_version": VERSION,
        "status": "CAD_CENTERLINES_EXPORTED_MGRID_REQUIRED",
        "source_files": {
            "winding_pack_turns_csv": str(turns_path),
            "winding_pack_turns_sha256": _sha256(turns_path),
            "winding_pack_screen_csv": str(screen_path),
            "winding_pack_screen_sha256": _sha256(screen_path),
        },
        "coordinate_convention": "R_phi_Z; exported X=R*cos(phi), Y=R*sin(phi), phi in radians",
        "points_per_turn": POINTS_PER_TURN,
        "coil_count": len(coils),
        "total_turn_count": sum(coil["turn_count"] for coil in coils),
        "outputs": {
            "fcstd": "Tomahawk_PF_CAD_MAKEGRID.FCStd",
            "centerlines_csv": centerline_path.name,
            "currents_csv": current_path.name,
        },
        "validation": {
            "table_ids_match": True,
            "turn_counts_match": True,
            "operating_currents_match": True,
            "reference_current_limits_checked": True,
            "all_exported_loops_closed_by_duplicate_endpoint": True,
            "native_solver_evidence": False,
            "mgrid_generated": False,
            "qualified_design": False,
        },
        "limitations": [
            "The CAD contains finite-turn axisymmetric centerlines only; it is not a winding-pack solid or fabrication release.",
            "The currents and limits are retained model-derived screening inputs, not independently qualified engineering data.",
            "A real MAKEGRID/native solver must consume the exported tables and generate a native mgrid file.",
            "This macro does not run VMEC, DESC, MAKEGRID, or any free-boundary equilibrium solver.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return centerline_path, current_path, manifest_path


def run():
    App, Part, Gui = _freecad_modules()
    print("PF_CAD_MACRO_VERSION:", VERSION)
    selected = _file_picker(
        "Select PF winding-pack turns CSV or Tomahawk data ZIP",
        "PF turns CSV (pf_winding_pack_turns.csv);;Tomahawk data ZIP (Tomahawk_Kaggle_Data*.zip);;All files (*)",
    )
    print("PF_CAD_INPUT_SELECTED:", selected)
    turns_path = _locate_turns_csv(selected)
    screen_path = _locate_screen_csv(turns_path)
    print("PF_CAD_BUILD_START")
    print("turns_source:", turns_path)
    print("screen_source:", screen_path)
    coils = _load_and_validate(turns_path, screen_path)
    doc = _make_document(App, Part, coils)
    # Keep exports beside the selected input.  In particular, when a ZIP is
    # selected, do not bury the result inside the temporary extraction tree.
    output_dir = _new_output_dir(selected.parent)
    fcstd_path = output_dir / "Tomahawk_PF_CAD_MAKEGRID.FCStd"
    output_dir.mkdir(parents=True, exist_ok=True)
    doc.saveAs(str(fcstd_path))
    _require_nonempty_file(fcstd_path, "FreeCAD document")
    centerline_path, current_path, manifest_path = _write_exports(output_dir, turns_path, screen_path, coils)
    _require_nonempty_file(centerline_path, "centerline CSV")
    _require_nonempty_file(current_path, "current CSV")
    _require_nonempty_file(manifest_path, "export manifest")
    if Gui is not None:
        try:
            Gui.activeDocument().activeView().viewAxonometric()
            Gui.activeDocument().activeView().fitAll()
        except Exception:
            pass
    print("PF_CAD_BUILD_COMPLETE")
    print("EXPORT_DIRECTORY:", output_dir)
    print("coil_count:", len(coils), "total_turn_count:", sum(coil["turn_count"] for coil in coils))
    print("fcstd:", fcstd_path)
    print("centerlines:", centerline_path)
    print("currents:", current_path)
    print("manifest:", manifest_path)
    print("MGRID_REQUIRED: true")
    print("NATIVE_SOLVER_EVIDENCE: NOT_GENERATED")
    return output_dir, {
        "fcstd": str(fcstd_path),
        "centerlines": str(centerline_path),
        "currents": str(current_path),
        "manifest": str(manifest_path),
    }


if __name__ == "__main__":
    run()
