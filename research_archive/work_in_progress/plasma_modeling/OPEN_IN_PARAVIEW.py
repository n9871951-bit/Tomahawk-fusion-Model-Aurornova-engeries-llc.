"""Open Tomahawk BOUT++ results in ParaView.

ParaView: View -> Python Shell -> Run Script -> pick this file (it sits in the 'results' folder of the unzipped results).
It searches the folder this script is in (change `root` below for another folder), loads every */paraview/P_series.vts.series under it,
colours by the pressure perturbation, cuts away a quarter of the torus so you can see inside, and shows the first case.
Use the Pipeline Browser eye icons to switch cases; the time controls step through the saved frames.
"""
import os
from paraview.simple import *  # noqa: F401,F403

try:
    here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    here = os.getcwd()
root = here          # to load a different folder, put its full path here, e.g. root = r"C:\Users\me\Tomahawk_Plasma\results"

series = []
for d, _, files in os.walk(root):
    if "P_series.vts.series" in files:
        series.append(os.path.join(d, "P_series.vts.series"))
series.sort()
print(f"Found {len(series)} result series under {root}")
view = GetActiveViewOrCreate("RenderView")
first = True
for s in series:
    case = os.path.basename(os.path.dirname(os.path.dirname(s)))
    rdr = OpenDataFile(s)
    RenameSource(case, rdr)
    clip = Clip(registrationName=case + "_cutaway", Input=rdr)
    clip.ClipType = "Plane"; clip.ClipType.Origin = [0, 0, 0]; clip.ClipType.Normal = [1, 1, 0]
    disp = Show(clip, view)
    ColorBy(disp, ("POINTS", "P_perturbation_normalised"))
    lut = GetColorTransferFunction("P_perturbation_normalised"); lut.ApplyPreset("Cool to Warm", True); lut.RescaleTransferFunction(-1.0, 1.0)
    disp.SetScalarBarVisibility(view, True)
    if not first:
        Hide(clip, view)
    first = False
view.CameraPosition = [0, -35, 18]; view.CameraFocalPoint = [0, 0, 0]; view.CameraViewUp = [0, 0, 1]
ResetCamera(view)
Render(view)
