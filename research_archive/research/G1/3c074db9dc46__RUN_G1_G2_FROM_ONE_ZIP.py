r"""Build one G1 + G2 FreeCAD assembly from one complete input ZIP.

Save this launcher and Tomahawk_G1_G2_All_Inputs.zip to Downloads.
In FreeCAD's Python console, paste:

import runpy; runpy.run_path(r"C:\Users\Nicol\Downloads\RUN_G1_G2_FROM_ONE_ZIP.py", run_name="__main__")

Choose Tomahawk_G1_G2_All_Inputs.zip in the single file dialog.
"""

import hashlib
import json
import lzma
import math
import os
from pathlib import Path
import runpy
import zipfile


PACKAGE = "Tomahawk_G1_G2_All_Inputs"
CAD_FOLDER = "Tomahawk_TF48_16FP_16T_CAD_Handoff"
G2_FOLDER = "Tomahawk_G2_16T_Preflight"
MGRID_NAME = "mgrid_tomahawk_16T_TF_PF_16FP.nc"
CAD_FILES = (
    "RUN_THIS_IN_FREECAD.py",
    "Tomahawk_Liquid_Wall_SOURCE.FCStd",
    "TF48_exact_centerlines_m.csv",
    "PF578_turn_placement.csv",
    "laser16_ports_and_timing.csv",
    "RF4_cassette_reserved_placement.csv",
    "G1_16T_validation_report.json",
)
G2_FILES = (
    "G2_field_geometry_audit.json",
    "G2_vacuum_flux_seed.json",
    "G2_gate_ledger.json",
    MGRID_NAME + ".xz",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_zip():
    try:
        from PySide2 import QtWidgets
    except ImportError:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide import QtGui as QtWidgets
    downloads = Path(r"C:\Users\Nicol\Downloads")
    if not downloads.is_dir():
        downloads = Path.home() / "Downloads"
    proposed = downloads / (PACKAGE + ".zip")
    start = proposed if proposed.is_file() else downloads
    selection = QtWidgets.QFileDialog.getOpenFileName(
        None, "Select the ONE Tomahawk G1 + G2 inputs ZIP", str(start), "ZIP files (*.zip)"
    )
    selected = selection[0] if isinstance(selection, tuple) else selection
    if not selected:
        raise RuntimeError("No input ZIP selected")
    path = Path(selected).resolve()
    if not path.is_file() or not zipfile.is_zipfile(str(path)):
        raise ValueError("Choose the Tomahawk_G1_G2_All_Inputs.zip file")
    return path


def extract_checked(archive, member, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and sha256(target) == expected:
        return
    temporary = target.with_name(target.name + ".partial")
    digest = hashlib.sha256()
    try:
        with archive.open(member) as src, temporary.open("wb") as dst:
            for chunk in iter(lambda: src.read(4 * 1024 * 1024), b""):
                dst.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("Input checksum failed: " + member)
        os.replace(str(temporary), str(target))
    finally:
        if temporary.exists():
            temporary.unlink()


def unpack_mgrid(g2_directory, expected):
    target = g2_directory / MGRID_NAME
    if target.is_file() and sha256(target) == expected:
        return target
    source = g2_directory / (MGRID_NAME + ".xz")
    temporary = target.with_name(target.name + ".partial")
    digest = hashlib.sha256()
    try:
        with lzma.open(str(source), "rb") as src, temporary.open("wb") as dst:
            for chunk in iter(lambda: src.read(4 * 1024 * 1024), b""):
                dst.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("Expanded G2 field failed its checksum")
        os.replace(str(temporary), str(target))
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def prepare_inputs(bundle):
    work = bundle.parent / "Tomahawk_G1_G2_Work"
    cad_directory, g2_directory = work / CAD_FOLDER, work / G2_FOLDER
    with zipfile.ZipFile(str(bundle)) as archive:
        root = PACKAGE + "/"
        manifest = json.loads(archive.read(root + "MANIFEST_SHA256.json").decode("utf-8"))
        for folder, names, destination in (
            (CAD_FOLDER, CAD_FILES, cad_directory),
            (G2_FOLDER, G2_FILES, g2_directory),
        ):
            for name in names:
                relative = folder + "/" + name
                extract_checked(archive, root + relative, destination / name, manifest[relative])
    g1 = json.loads((cad_directory / "G1_16T_validation_report.json").read_text(encoding="utf-8"))
    audit = json.loads((g2_directory / "G2_field_geometry_audit.json").read_text(encoding="utf-8"))
    flux = json.loads((g2_directory / "G2_vacuum_flux_seed.json").read_text(encoding="utf-8"))
    source_hash = sha256(cad_directory / "Tomahawk_Liquid_Wall_SOURCE.FCStd")
    if source_hash != g1["current_supplied_cad_boundary_check"]["source_fcstd_sha256"]:
        raise ValueError("CAD source does not match the G1 report")
    if source_hash != audit["CAD_boundary"]["cad_fcstd_sha256"]:
        raise ValueError("G1 and G2 refer to different CAD boundaries")
    field = unpack_mgrid(g2_directory, audit["combined_MGRID_sha256"])
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
    bundle = select_zip()
    work, cad_directory, g2_directory, field, g1, audit, flux = prepare_inputs(bundle)
    output = build_assembly(work, cad_directory, g2_directory, field, g1, audit, flux)
    print("Saved G1 + G2 CAD assembly:", output)


if __name__ == "__main__":
    main()
