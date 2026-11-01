r"""Nicole's one-file launcher for the Tomahawk 16 T FreeCAD CAD handoff.

Save this file to C:\Users\Nicol\Downloads\RUN_THIS_IN_FREECAD.py.
In the FreeCAD Python console, copy and paste:

    import runpy; runpy.run_path(r"C:\Users\Nicol\Downloads\RUN_THIS_IN_FREECAD.py", run_name="__main__")

The ZIP stays in Downloads. This launcher extracts it and runs the assembly
builder shipped inside, with all its companion CSV and field files.
"""

from pathlib import Path
import runpy
import zipfile


ZIP_PATH = Path(r"C:\Users\Nicol\Downloads\Tomahawk_TF48_16FP_16T_CAD_Handoff.zip")
EXTRACT_TO = ZIP_PATH.parent / "Tomahawk_TF48_16FP_16T_CAD_Handoff_extracted"
PACKAGE_NAME = "Tomahawk_TF48_16FP_16T_CAD_Handoff"


def main():
    if not ZIP_PATH.is_file():
        raise FileNotFoundError("CAD ZIP not found: " + str(ZIP_PATH))

    EXTRACT_TO.mkdir(parents=True, exist_ok=True)
    destination = EXTRACT_TO.resolve()
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError("Damaged ZIP member: " + bad)
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError("Unsafe ZIP path: " + member.filename)
        archive.extractall(destination)

    package_dir = destination / PACKAGE_NAME
    builder = package_dir / "RUN_THIS_IN_FREECAD.py"
    if not builder.is_file():
        raise FileNotFoundError("Assembly builder missing from ZIP: " + str(builder))
    for companion in (
        "Tomahawk_Liquid_Wall_SOURCE.FCStd",
        "TF48_exact_centerlines_m.csv",
        "PF578_turn_placement.csv",
        "laser16_ports_and_timing.csv",
        "RF4_cassette_reserved_placement.csv",
    ):
        if not (package_dir / companion).is_file():
            raise FileNotFoundError("CAD companion file missing: " + companion)

    print("Building 16 T CAD from:", package_dir)
    runpy.run_path(str(builder), run_name="__main__")
    result = package_dir / "Tomahawk_TF48_16FP_16T_RF_Laser_Assembly.FCStd"
    if not result.is_file():
        raise RuntimeError("FreeCAD did not save the expected assembly: " + str(result))
    print("Saved CAD assembly:", result)


if __name__ == "__main__":
    main()
