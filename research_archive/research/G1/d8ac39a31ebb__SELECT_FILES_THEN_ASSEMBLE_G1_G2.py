r"""Select each Tomahawk G1/G2 file individually, then build one FreeCAD assembly.

First extract the CAD handoff and G2 Ready ZIPs in Windows Explorer.
Save this file to C:\Users\Nicol\Downloads and run in FreeCAD's Python console:

import runpy; runpy.run_path(r"C:\Users\Nicol\Downloads\SELECT_FILES_THEN_ASSEMBLE_G1_G2.py", run_name="__main__")

The dialogs select individual files, never ZIP archives.
"""

import csv
import hashlib
import json
import lzma
import math
import os
from pathlib import Path
import runpy
import shutil


CAD_FOLDER = "Tomahawk_TF48_16FP_16T_CAD_Handoff"
G2_FOLDER = "Tomahawk_G2_16T_Preflight"
MGRID_NAME = "mgrid_tomahawk_16T_TF_PF_16FP.nc"
INPUTS = (
    ("G1 CAD source", "Tomahawk_Liquid_Wall_SOURCE.FCStd", "FreeCAD documents (*.FCStd)"),
    ("TF48 centerlines", "TF48_exact_centerlines_m.csv", "CSV files (*.csv)"),
    ("PF578 turn placement", "PF578_turn_placement.csv", "CSV files (*.csv)"),
    ("16 laser port placement", "laser16_ports_and_timing.csv", "CSV files (*.csv)"),
    ("four RF cassette placements", "RF4_cassette_reserved_placement.csv", "CSV files (*.csv)"),
    ("G1 validation report", "G1_16T_validation_report.json", "JSON files (*.json)"),
    ("G2 field and geometry audit", "G2_field_geometry_audit.json", "JSON files (*.json)"),
    ("G2 vacuum flux seed", "G2_vacuum_flux_seed.json", "JSON files (*.json)"),
    ("G2 gate ledger", "G2_gate_ledger.json", "JSON files (*.json)"),
    ("G2 combined MGRID (.nc or .nc.xz)", MGRID_NAME, "NetCDF/XZ files (*.nc *.xz)"),
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_file(title, directory, pattern):
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide import QtGui as QtWidgets
    selection = QtWidgets.QFileDialog.getOpenFileName(
        None, title, str(directory), pattern + ";;All files (*)"
    )
    selected = selection[0] if isinstance(selection, tuple) else selection
    if not selected:
        raise RuntimeError("File selection cancelled: " + title)
    path = Path(selected).resolve()
    if not path.is_file():
        raise FileNotFoundError("Select an extracted file: " + str(path))
    return path


def put_file(source, destination, expected_sha=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if expected_sha and sha256(destination) == expected_sha:
            return destination
        if destination.resolve() == source.resolve():
            if expected_sha and sha256(source) != expected_sha:
                raise ValueError("File does not match its audit: " + source.name)
            return destination
    temporary = destination.with_name(destination.name + ".partial")
    try:
        shutil.copyfile(str(source), str(temporary))
        if expected_sha and sha256(temporary) != expected_sha:
            raise ValueError("File does not match its audit: " + source.name)
        os.replace(str(temporary), str(destination))
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def unpack_mgrid(source, output, expected_sha):
    if output.is_file() and sha256(output) == expected_sha:
        return output
    if source.suffix.lower() == ".nc":
        return put_file(source, output, expected_sha)
    if not source.name.lower().endswith(".nc.xz"):
        raise ValueError("G2 field must be the combined .nc or .nc.xz file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    digest = hashlib.sha256()
    try:
        with lzma.open(str(source), "rb") as compressed, temporary.open("wb") as dst:
            for chunk in iter(lambda: compressed.read(4 * 1024 * 1024), b""):
                dst.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != expected_sha:
            raise ValueError("G2 field grid does not match its audit")
        os.replace(str(temporary), str(output))
    finally:
        if temporary.exists():
            temporary.unlink()
    return output


def csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def check_csvs(cad_directory):
    tf = csv_rows(cad_directory / "TF48_exact_centerlines_m.csv")
    pf = csv_rows(cad_directory / "PF578_turn_placement.csv")
    laser = csv_rows(cad_directory / "laser16_ports_and_timing.csv")
    rf = csv_rows(cad_directory / "RF4_cassette_reserved_placement.csv")
    if len(tf) != 48 * 512 or len({r["coil_id"] for r in tf}) != 48:
        raise ValueError("TF file must contain 48 coils with 512 segments each")
    if len(pf) != 578 or len({r["coil_id"] for r in pf}) != 6:
        raise ValueError("PF file must contain 578 turns in six groups")
    if len(laser) != 16 or len(rf) != 4:
        raise ValueError("Select the 16-port laser and four-station RF files")


def prepare_inputs(paths):
    source_fcstd = paths["Tomahawk_Liquid_Wall_SOURCE.FCStd"]
    downloads = Path(r"C:\Users\Nicol\Downloads")
    work = (downloads if downloads.is_dir() else source_fcstd.parent) / "Tomahawk_G1_G2_Work"
    cad_directory, g2_directory = work / CAD_FOLDER, work / G2_FOLDER
    g1 = json.loads(paths["G1_16T_validation_report.json"].read_text(encoding="utf-8"))
    audit = json.loads(paths["G2_field_geometry_audit.json"].read_text(encoding="utf-8"))
    flux = json.loads(paths["G2_vacuum_flux_seed.json"].read_text(encoding="utf-8"))
    source_hash = sha256(source_fcstd)
    if source_hash != g1["current_supplied_cad_boundary_check"]["source_fcstd_sha256"]:
        raise ValueError("Selected FCStd does not match the G1 report")
    if source_hash != audit["CAD_boundary"]["cad_fcstd_sha256"]:
        raise ValueError("Selected G1 CAD and G2 audit refer to different boundaries")
    for _, filename, _ in INPUTS[:6]:
        source = paths[filename]
        expected = source_hash if filename == "Tomahawk_Liquid_Wall_SOURCE.FCStd" else None
        put_file(source, cad_directory / filename, expected)
    for _, filename, _ in INPUTS[6:9]:
        put_file(paths[filename], g2_directory / filename)
    check_csvs(cad_directory)

    builder = source_fcstd.parent / "RUN_THIS_IN_FREECAD.py"
    if not builder.is_file():
        builder = select_file("Select the CAD builder RUN_THIS_IN_FREECAD.py", source_fcstd.parent, "Python files (*.py)")
    builder_text = builder.read_text(encoding="utf-8")
    if any(marker not in builder_text for marker in (
        "import FreeCAD as App", "TF48_exact_centerlines_m.csv",
        "Tomahawk_TF48_16FP_16T_RF_Laser_Assembly.FCStd",
    )):
        raise ValueError("Select the assembly builder inside the extracted CAD folder: " + str(builder))
    put_file(builder, cad_directory / "RUN_THIS_IN_FREECAD.py")

    field = unpack_mgrid(paths[MGRID_NAME], g2_directory / MGRID_NAME, audit["combined_MGRID_sha256"])
    return work, cad_directory, g2_directory, field, g1, audit, flux


def set_prop(obj, key, value):
    if key not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", key, "Tomahawk_G1_G2")
    setattr(obj, key, str(value))


def seed_shape(App, Part):
    wires = []
    # Ninety-six toroidal sections plus twenty-four longitudinal traces.
    # All coordinates sent to FreeCAD are millimetres.
    def point(theta, phi):
        r = 7.5 + 3.0 * math.cos(theta) + 0.01 * math.cos(theta - 16.0 * phi)
        z = 2.138969432449380 * math.sin(theta) + 0.01 * math.sin(theta - 16.0 * phi)
        return App.Vector(1000.0 * r * math.cos(phi),
                          1000.0 * r * math.sin(phi), 1000.0 * z)
    for j in range(96):
        phi = 2.0 * math.pi * j / 96.0
        vertices = [point(2.0 * math.pi * k / 64.0, phi) for k in range(65)]
        wires.append(Part.makePolygon(vertices))
    for k in range(24):
        theta = 2.0 * math.pi * k / 24.0
        vertices = [point(theta, 2.0 * math.pi * j / 384.0) for j in range(385)]
        wires.append(Part.makePolygon(vertices))
    return Part.makeCompound(wires)


def build_assembly(work, cad_directory, g2_directory, field, g1, audit, flux):
    import FreeCAD as App
    import Part

    builder = cad_directory / "RUN_THIS_IN_FREECAD.py"
    print("Building the CAD assembly from:", builder)
    runpy.run_path(str(builder), run_name="__main__")
    intermediate = cad_directory / "Tomahawk_TF48_16FP_16T_RF_Laser_Assembly.FCStd"
    if not intermediate.is_file():
        raise RuntimeError("CAD builder did not save the expected assembly: " + str(intermediate))
    doc = App.activeDocument()
    if doc is None or Path(doc.FileName).resolve() != intermediate.resolve():
        doc = App.openDocument(str(intermediate))
    boundary = doc.getObject("EV007_Plasma_Boundary")
    if boundary is None or boundary.Shape.isNull():
        raise RuntimeError("The G1 EV007 boundary is missing from the CAD source")

    g1_group = doc.getObject("G1_Boundary_16T") or doc.addObject("App::DocumentObjectGroup", "G1_Boundary_16T")
    g1_group.Label = "G1 | audited 16 T CAD boundary"
    g1_obj = doc.getObject("G1_CAD_Boundary") or doc.addObject("Part::Feature", "G1_CAD_Boundary")
    g1_obj.Label = "G1 | EV007 faceted CAD boundary"
    g1_obj.Shape = boundary.Shape.copy()
    g1_group.addObject(g1_obj)
    set_prop(g1_group, "BoundaryBREPSHA256", g1["current_supplied_cad_boundary_check"]["brep_sha256"])
    set_prop(g1_group, "ValidationReport", str(cad_directory / "G1_16T_validation_report.json"))
    set_prop(g1_group, "FieldBaselineT", 16.0)

    g2_group = doc.getObject("G2_Inputs_16T") or doc.addObject("App::DocumentObjectGroup", "G2_Inputs_16T")
    g2_group.Label = "G2 | Fourier boundary seed and combined field"
    g2_obj = doc.getObject("G2_Fourier_Seed") or doc.addObject("Part::Feature", "G2_Fourier_Seed")
    g2_obj.Label = "G2 | 16-period Fourier seed (wireframe)"
    g2_obj.Shape = seed_shape(App, Part)
    if g2_obj.Shape.isNull() or not g2_obj.Shape.isValid():
        raise RuntimeError("G2 Fourier seed CAD geometry was not valid")
    g2_group.addObject(g2_obj)
    set_prop(g2_group, "MGRIDFile", str(field))
    set_prop(g2_group, "MGRIDSHA256", audit["combined_MGRID_sha256"])
    set_prop(g2_group, "FieldPeriods", audit["nfp"])
    set_prop(g2_group, "PlanesPerPeriod", audit["kp"])
    set_prop(g2_group, "EXTCUR_A_per_turn", json.dumps(audit["EXTCUR_A_per_turn_in_group_order"]))
    set_prop(g2_group, "PFProjectionMaxErrorT", audit["PF_projection"]["combined_PF_vector_max_error_T"])
    set_prop(g2_group, "VacuumFluxSeedMeanWb", flux["quadrature"][-1]["mean_Wb"])
    set_prop(g2_group, "GeometryAudit", str(g2_directory / "G2_field_geometry_audit.json"))
    set_prop(g2_group, "GateLedger", str(g2_directory / "G2_gate_ledger.json"))
    set_prop(g2_group, "Status", "G2 geometry and vacuum-field input preflight")

    if getattr(App, "GuiUp", False):
        boundary.ViewObject.Visibility = False
        g1_obj.ViewObject.ShapeColor = (0.16, 0.73, 0.36)
        g1_obj.ViewObject.Transparency = 82
        g2_obj.ViewObject.LineColor = (0.04, 0.85, 0.96)
        g2_obj.ViewObject.LineWidth = 2.0
    doc.recompute()
    output = work / "Tomahawk_G1_G2_16T_Assembly.FCStd"
    doc.saveAs(str(output))
    if not output.is_file():
        raise RuntimeError("FreeCAD did not save the combined assembly: " + str(output))
    if getattr(App, "GuiUp", False):
        try:
            import FreeCADGui as Gui
            Gui.activeDocument().activeView().viewAxonometric()
            Gui.activeDocument().activeView().fitAll()
        except Exception:
            pass
    return output


def main():
    downloads = Path(r"C:\Users\Nicol\Downloads")
    directory = downloads if downloads.is_dir() else Path.home()
    selected = {}
    for number, (label, filename, pattern) in enumerate(INPUTS, 1):
        path = select_file("%d of %d: %s" % (number, len(INPUTS), label), directory, pattern)
        selected[filename] = path
        directory = path.parent
        print("Selected %d/%d: %s" % (number, len(INPUTS), path))
    work, cad_directory, g2_directory, field, g1, audit, flux = prepare_inputs(selected)
    output = build_assembly(work, cad_directory, g2_directory, field, g1, audit, flux)
    print("Saved G1 + G2 CAD assembly:", output)


if __name__ == "__main__":
    main()
