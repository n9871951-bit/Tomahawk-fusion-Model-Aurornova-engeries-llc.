"""Build the Tomahawk BOUT++ plasma-stability notebooks (Kaggle, CPU, internet on, no inputs).

Each notebook: builds BOUT++ 5.1.1 + elm-pb from source (same recipe as the tested workspace build), makes BOUT++ grids
from AuroraNova's N9A2 equilibrium (embedded), runs its share of the case matrix, and saves growth rates, mode pictures
and ParaView (.vts) files. Fails loudly (raises) if any case fails.
"""
import base64, hashlib, io, json, sys, tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PL = Path("/home/claude/plasma")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "notebooks"
OUT.mkdir(parents=True, exist_ok=True)
VERSION = "Tomahawk plasma stability (BOUT++ elm-pb) v1"


def md(t):
    return {"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)}


def code(t):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)}


def notebook(cells):
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "kaggle": {"accelerator": "none", "isInternetEnabled": True}},
          "cells": cells}
    for c in nb["cells"]:
        c["id"] = hashlib.sha1((c["cell_type"] + "".join(c["source"])).encode()).hexdigest()[:8]
    return nb


# ---------------------------------------------------------------- payload (all code + the equilibrium)
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    tar.add(PL / "N9A2_axisymmetric_enlarged_TF.h5", "tp/N9A2_axisymmetric_enlarged_TF.h5")
    for f in sorted((PL / "pyfive").glob("*.py")):
        tar.add(f, f"tp/pyfive/{f.name}")
    for f in ("desc_axisym.py", "make_bout_grid.py", "bout_results.py"):
        tar.add(PL / "tools" / f, f"tp/tools/{f}")
    tar.add(PL / "runs/template/BOUT.inp", "tp/BOUT.inp")
    tar.add(HERE / "kaggle_build_bout.sh", "tp/kaggle_build_bout.sh")
    tar.add(HERE / "OPEN_IN_PARAVIEW.py", "tp/OPEN_IN_PARAVIEW.py")
PAYLOAD = base64.b64encode(buf.getvalue()).decode()
N9A2_SHA = hashlib.sha256((PL / "N9A2_axisymmetric_enlarged_TF.h5").read_bytes()).hexdigest()

SETUP = r'''
import base64, io, json, os, shutil, subprocess, sys, tarfile, time, zipfile, hashlib
from pathlib import Path
print("NOTEBOOK VERSION: __VERSION__")
START = time.monotonic(); BUDGET_H = 11.3
TP = Path("/tmp/tp"); RUNS = Path("/tmp/runs"); WORK = Path("/kaggle/working") if Path("/kaggle").exists() else Path.cwd() / "working"
RES = WORK / "results"; RES.mkdir(parents=True, exist_ok=True); RUNS.mkdir(parents=True, exist_ok=True)
PAYLOAD = "__PAYLOAD__"
shutil.rmtree(TP, ignore_errors=True)
with tarfile.open(fileobj=io.BytesIO(base64.b64decode(PAYLOAD)), mode="r:gz") as t:
    t.extractall("/tmp", filter="data") if sys.version_info >= (3, 12) else t.extractall("/tmp")
TP = Path("/tmp/tp")
sha = hashlib.sha256((TP / "N9A2_axisymmetric_enlarged_TF.h5").read_bytes()).hexdigest()
assert sha == "__N9A2_SHA__", "equilibrium file damaged"
print("N9A2 equilibrium SHA-256 OK:", sha)
shutil.copy(TP / "OPEN_IN_PARAVIEW.py", RES / "OPEN_IN_PARAVIEW.py")
print("CPUs:", os.cpu_count())
'''

BUILD = r'''
t0 = time.monotonic()
p = subprocess.Popen(["bash", str(TP / "kaggle_build_bout.sh")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in p.stdout:
    print(line, end="", flush=True)
p.wait()
if p.returncode != 0:
    for log in sorted(Path("/tmp/bout/logs").glob("*.log")):
        print("----", log.name); print("".join(log.read_text(errors="replace").splitlines(True)[-25:]))
    raise RuntimeError("BOUT++ build failed (last lines of each log above)")
print(f"BOUT++ + elm-pb built in {(time.monotonic() - t0) / 60:.1f} min")
ENV = dict(os.environ, PATH="/tmp/bout/bin:" + os.environ["PATH"], LD_LIBRARY_PATH="/tmp/bout/lib:" + os.environ.get("LD_LIBRARY_PATH", ""))
'''

RUN = r'''
CASES = __CASES__
sys.path.insert(0, str(TP / "tools")); sys.path.insert(0, str(TP))
import importlib, bout_results as BR; importlib.reload(BR)
NP = os.cpu_count()
ZIP = WORK / "__ZIPNAME__"
def save_zip():
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(RES.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(WORK))
def grid_for(nx, ny, ps):
    g = TP / "grids" / f"tomahawk_N9A2_nx{nx}_ny{ny}_p{ps}.nc"
    if not g.exists():
        g.parent.mkdir(exist_ok=True)
        r = subprocess.run([sys.executable, str(TP / "tools/make_bout_grid.py"), str(TP / "N9A2_axisymmetric_enlarged_TF.h5"), str(g),
                            "--nx", str(nx), "--ny", str(ny), "--pscale", str(ps)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("grid failed: " + r.stderr[-2000:])
        d = json.loads(g.with_suffix(".json").read_text())
        print(f"  grid nx={nx} ny={ny} p x{ps}: orthogonality {d['max_abs_cos_angle_x_y_lines_interior']:.1e}, q check {d['ShiftAngle_over_2pi_vs_q_max_rel_diff']:.1e}", flush=True)
    return g
summary, failed = [], []
for c in CASES:
    name = c["name"]; hours_used = (time.monotonic() - START) / 3600
    if hours_used > BUDGET_H - c.get("est_h", 0.5):
        print(f"SKIP {name}: not enough time left ({hours_used:.1f} h used)"); failed.append(name + " (time)"); continue
    print(f"\n=== {name}: n={c['n']} nx={c['nx']} ny={c['ny']} pressure x{c['pscale']} {c['opts']}", flush=True)
    try:
        g = grid_for(c["nx"], c["ny"], c["pscale"])
        d = RUNS / name; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        shutil.copy(TP / "BOUT.inp", d / "BOUT.inp"); shutil.copy(g, d / g.name)
        t0 = time.monotonic()
        cmd = ["/tmp/bout/bin/mpiexec", "-n", str(NP), "/tmp/bout/elmpb/build/elm_pb", "-d", ".", f"grid={g.name}", f"zperiod={c['n']}",
               f"nout={c['nout']}", "wall_limit=" + str(max(0.2, BUDGET_H - hours_used - 0.3))] + c["opts"]
        r = subprocess.run(cmd, cwd=d, env=ENV, capture_output=True, text=True)
        wall = time.monotonic() - t0
        if r.returncode != 0 or not list(d.glob("BOUT.dmp.*.nc")):
            raise RuntimeError(f"elm_pb rc={r.returncode}: " + (d / "BOUT.log.0").read_text(errors="replace")[-3000:] if (d / "BOUT.log.0").exists() else r.stderr[-3000:])
        res, P, t, rms = BR.growth_rate(d); res.update(case=c, wall_s=wall)
        (d / "growth_rate.json").write_text(json.dumps(res, indent=1))
        o = RES / name; o.mkdir(exist_ok=True)
        BR.plot_mode(d, d / g.name, o / "mode.png", f"Tomahawk N9A2 p x{c['pscale']}")
        if c.get("vtk", True):
            vdir = BR.export_vtk(d, d / g.name, P, t, every=max(1, len(t) - 1), nphi=48, last_only=True)
            shutil.copytree(vdir, o / "paraview", dirs_exist_ok=True)
        for f in ("growth_rate.json", "BOUT.inp", "BOUT.settings", "BOUT.log.0"):
            shutil.copy(d / f, o / f)
        summary.append({"name": name, **{k: c[k] for k in ("n", "nx", "ny", "pscale")}, "physics": c["physics"],
                        "gamma_per_tau_A": res["gamma_per_alfven_time"], "converged": res["converged"],
                        "peak_psin": c["psin0"] + (c["psin1"] - c["psin0"]) * res["peak_x_index"] / (c["nx"] - 1),
                        "peak_y_index": res["peak_y_index"], "tau_A_s": res["Tbar_s"], "wall_min": wall / 60})
        print(f"  gamma = {res['gamma_per_alfven_time']:.4f} / tau_A (converged: {res['converged']}), wall {wall / 60:.1f} min", flush=True)
        shutil.rmtree(d, ignore_errors=True)
    except Exception as e:
        print("  FAILED:", str(e)[-1500:], flush=True); failed.append(name)
    (RES / "summary.json").write_text(json.dumps({"version": "__VERSION__", "cases": summary, "failed": failed}, indent=1))
    save_zip()
print("\nResults zip:", ZIP)
if failed:
    raise RuntimeError(f"{len(failed)} case(s) did not finish: {failed}. Kaggle marks this run failed on purpose.")
'''

SHOW = r'''
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
S = json.loads((RES / "summary.json").read_text())["cases"]
print(f"{'case':38s} {'n':>3s} {'nx':>4s} {'p x':>4s} {'gamma/tau_A':>11s} {'conv':>5s} {'peak psi_n':>10s} {'peak y':>6s} {'min':>6s}")
for s in S:
    print(f"{s['name']:38s} {s['n']:3d} {s['nx']:4d} {s['pscale']:4.1f} {s['gamma_per_tau_A']:11.4f} {str(s['converged']):>5s} {s['peak_psin']:10.3f} {s['peak_y_index']:6d} {s['wall_min']:6.1f}")
fig, ax = plt.subplots(figsize=(8, 5))
for ps in sorted({s["pscale"] for s in S}):
    pts = sorted((s["n"], s["gamma_per_tau_A"]) for s in S if s["pscale"] == ps and s["nx"] == max(x["nx"] for x in S if x["pscale"] == ps))
    if pts:
        ax.plot(*zip(*pts), "o-", label=f"pressure x{ps}")
ax.axhline(0, color="k", lw=0.5); ax.set_xlabel("toroidal mode number n"); ax.set_ylabel("growth rate (1 / tau_A)"); ax.legend()
ax.set_title("Tomahawk N9A2: elm-pb linear growth rates"); plt.tight_layout(); plt.savefig(RES / "growth_vs_n.png", dpi=110)
save_zip(); print("Saved", ZIP)
'''

PSIN = (0.40, 1.0)
SPITZER = ["highbeta:spitzer_resist=true"]


def case(name, n, nx, ps, physics="spitzer", ny=64, nout=200, vtk=True):
    opts = {"spitzer": SPITZER, "S1e8": [], "ideal": ["highbeta:core_lund=-1", "highbeta:vac_lund=-1", "highbeta:hyperresist=-1"]}[physics]
    est = {68: 0.1, 132: 0.15, 260: 0.4, 516: 1.6}[nx] * (2 if ny == 128 else 1) * nout / 200
    return {"name": name, "n": n, "nx": nx, "ny": ny, "pscale": ps, "physics": physics, "opts": opts, "nout": nout, "vtk": vtk,
            "est_h": est, "psin0": PSIN[0], "psin1": PSIN[1]}


NS = [5, 10, 15, 20, 30, 40]
PARTS = {
    "P1": ("design pressure and x1.5: n-scan, Spitzer resistivity, nx 260",
           [case(f"p{ps}_n{n}_nx260", n, 260, ps) for ps in (1, 1.5) for n in NS]),
    "P2": ("pressure x2 and x3: n-scan, Spitzer resistivity, nx 260",
           [case(f"p{ps}_n{n}_nx260", n, 260, ps) for ps in (2, 3) for n in NS]),
    "P3": ("pressure x4 and x6: n-scan, Spitzer resistivity, nx 260",
           [case(f"p{ps}_n{n}_nx260", n, 260, ps) for ps in (4, 6) for n in NS]),
    "P4": ("resolution and physics checks at n = 15 (nx 132 / 260 / 516, ny 128, S = 1e8 benchmark, ideal)",
           [case(f"conv_p{ps}_n15_nx{nx}", 15, nx, ps) for ps in (1, 3) for nx in (132, 260, 516)]
           + [case("conv_p1_n15_nx260_ny128", 15, 260, 1, ny=128), case("conv_p3_n15_nx260_ny128", 15, 260, 3, ny=128),
              case("phys_p1_n15_nx260_S1e8", 15, 260, 1, physics="S1e8"), case("phys_p1_n15_nx260_ideal", 15, 260, 1, physics="ideal")]),
}

for tag, (what, cases) in PARTS.items():
    total = sum(c["est_h"] for c in cases)
    head = f"""
# Tomahawk {tag}: plasma stability with BOUT++ (elm-pb), {what}

**Settings:** Internet **ON**, accelerator **None (CPU)**. **No inputs needed.** Use **Save Version -> Save & Run All (Commit)**.
Run P1-P4 at the same time (each one is independent).

**What it is:** AuroraNova's Tomahawk N9A2 equilibrium (enlarged TF48, axisymmetric, SHA-256 `{N9A2_SHA[:16]}...`, embedded) is turned
into a BOUT++ grid (closed flux surfaces psi_n 0.40-1.00, orthogonal mesh), and BOUT++ 5.1.1's elm-pb model (3-field reduced MHD,
peeling-ballooning) computes the linear growth rate of each toroidal mode n. Pressure is scaled (x1 = design) to find the
ballooning margin. Density 3.46e20 m^-3 (N9A2 axis pressure at Ti = Te = 12 keV), D-T ion mass 2.5.

**Time:** BOUT++ build about 15-25 min, then about {total:.1f} h of runs (estimate; capped at 11.3 h, cases that don't fit are reported).

**Output:** `Tomahawk_Plasma_{tag}_Results.zip`: per case growth_rate.json, mode.png, ParaView .vts files, BOUT.inp/settings/log; summary.json; growth_vs_n.png.
Open the .vts files in ParaView (File -> Open, or run OPEN_IN_PARAVIEW.py from ParaView's Python Shell).

**If any case fails, the notebook raises an error so Kaggle shows the run as failed.**
"""
    run_src = (RUN.replace("__CASES__", json.dumps(cases)).replace("__ZIPNAME__", f"Tomahawk_Plasma_{tag}_Results.zip")
               .replace("__VERSION__", VERSION))
    nb = notebook([md(head), md("## 1. Unpack code and equilibrium"),
                   code(SETUP.replace("__PAYLOAD__", PAYLOAD).replace("__N9A2_SHA__", N9A2_SHA).replace("__VERSION__", VERSION)),
                   md("## 2. Build BOUT++ 5.1.1 + elm-pb"), code(BUILD), md("## 3. Grids and runs"), code(run_src),
                   md("## 4. Summary"), code(SHOW)])
    (OUT / f"Tomahawk_Plasma_{tag}.ipynb").write_text(json.dumps(nb, indent=1) + "\n")
    print(f"wrote {tag}: {len(cases)} cases, est {total:.1f} h")
