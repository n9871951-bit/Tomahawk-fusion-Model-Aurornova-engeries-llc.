"""Small FreeCAD-console-safe launcher for the Rev1.7 CAD preparation file.

Run this short file from FreeCAD's Python console or menu. Do not paste the
large embedded CAD file into the console. The launcher imports it from disk and
calls its Python API directly, so FreeCAD command-line arguments cannot reach
the CAD script's argparse parser.
"""
import runpy
from pathlib import Path

try:
    from PySide import QtWidgets
except ImportError:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets


def main():
    script, _ = QtWidgets.QFileDialog.getOpenFileName(
        None, 'Select Tomahawk Rev1.7 CAD script (not tomahawk_assembly.py)', '', 'Python (*.py)')
    if not script:
        print('Cancelled: no CAD script selected.')
        return
    path = Path(script).resolve()
    namespace = runpy.run_path(str(path), run_name='tomahawk_rev17_loaded')
    version = str(namespace.get('VERSION', ''))
    expected = 'CAD-A2-WHOLE-CONCEPT-1.7-MULTIPHYSICS-DOMAINS'
    if version != expected:
        raise RuntimeError(
            'Wrong CAD script selected. Expected VERSION=%s; found %s in %s. '
            'Select Tomahawk_Rev1_7_Multiphysics_CAD_Export.py, not the older tomahawk_assembly.py.'
            % (expected, version or 'missing VERSION', path))
    build = namespace.get('run')
    if not callable(build):
        raise RuntimeError('Selected file does not expose the Tomahawk run() API.')
    out, record = build(simulation_prep=True, multiphysics_prep=True,
                        open_result=True, close_documents=False)
    print('TOMAHAWK_MULTIPHYSICS_PREP_COMPLETE')
    print('native_execution:', record.get('native_execution'))
    print('saved_to:', out)


if __name__ == '__main__':
    main()
