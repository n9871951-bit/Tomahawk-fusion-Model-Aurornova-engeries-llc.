"""Read BOUT++ elm-pb dump files (netCDF4/HDF5, read with pyfive: no netCDF library needed), assemble the global
arrays, fit the linear growth rate, and write ParaView files (VTK XML structured grids, 3-D torus, time series).

usage: python bout_results.py RUN_DIR [--grid GRID.nc] [--vtk] [--vtk-every 5]
"""
import argparse, base64, json, math, struct, sys, zlib
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pyfive


def collect(run, var):
    files = sorted(Path(run).glob("BOUT.dmp.*.nc"), key=lambda p: int(p.name.split(".")[2]))
    parts = {}
    for fp in files:
        f = pyfive.File(str(fp))
        myg = int(f["MYG"][()]); mxg = int(f["MXG"][()]); xi = int(f["PE_XIND"][()]); yi = int(f["PE_YIND"][()])
        nxpe = int(f["NXPE"][()])
        d = np.asarray(f[var][()])
        sl = [slice(None)] * d.ndim
        ax_x = 1 if d.ndim == 4 else 0
        ax_y = ax_x + 1
        lx0 = 0 if xi == 0 else mxg; lx1 = d.shape[ax_x] if xi == nxpe - 1 else d.shape[ax_x] - mxg
        sl[ax_x] = slice(lx0, lx1); sl[ax_y] = slice(myg, d.shape[ax_y] - myg)
        parts[(xi, yi)] = d[tuple(sl)]
    xs = sorted({k[0] for k in parts}); ys = sorted({k[1] for k in parts})
    ax_x = 1 if next(iter(parts.values())).ndim == 4 else 0
    rows = [np.concatenate([parts[(x, y)] for y in ys], axis=ax_x + 1) for x in xs]
    return np.concatenate(rows, axis=ax_x)


def scalar(run, var):
    f = pyfive.File(str(sorted(Path(run).glob("BOUT.dmp.*.nc"))[0]))
    return np.asarray(f[var][()])


def growth_rate(run):
    P = collect(run, "P"); t = scalar(run, "t_array")
    rms = np.sqrt((P ** 2).mean(axis=3))                              # rms over z: (t, x, y)
    nt, nx, ny = rms.shape
    amp = rms.reshape(nt, -1).max(axis=1)                             # peak over the plane
    it, ix, iy = np.unravel_index(np.argmax(rms[-1]), rms[-1].shape) if False else (None, *np.unravel_index(np.argmax(rms[-1]), rms[-1].shape))
    trace = rms[:, ix, iy]
    lg = np.log(np.maximum(trace, 1e-300))
    gam = np.gradient(lg, t)
    n_last = max(5, nt // 4)                                           # fit the last quarter (at least 5 outputs)
    k, c = np.polyfit(t[-n_last:], lg[-n_last:], 1)
    spread = float(np.std(gam[-n_last:]))
    return {"gamma_per_alfven_time": float(k), "gamma_last_quarter_std": spread, "peak_x_index": int(ix), "peak_y_index": int(iy),
            "t": t.tolist(), "log_rms_at_peak": lg.tolist(), "growth_rate_history": gam.tolist(),
            "converged": bool(spread < 0.05 * abs(k) + 1e-3), "Tbar_s": float(scalar(run, "Tbar")), "Va_m_s": float(scalar(run, "Va")),
            "zperiod_n": int(scalar(run, "zperiod"))}, P, t, rms


def write_vts(path, pts, fields):
    """VTK XML StructuredGrid, binary (base64, zlib) data."""
    ni, nj, nk = pts.shape[:3]
    def enc(a):
        raw = np.ascontiguousarray(a, dtype="<f4").tobytes()
        comp = zlib.compress(raw)
        hdr = struct.pack("<4I", 1, len(raw), len(raw), len(comp))
        return base64.b64encode(hdr).decode() + base64.b64encode(comp).decode()
    out = [f'<?xml version="1.0"?>\n<VTKFile type="StructuredGrid" version="1.0" byte_order="LittleEndian" header_type="UInt32" compressor="vtkZLibDataCompressor">',
           f'<StructuredGrid WholeExtent="0 {ni-1} 0 {nj-1} 0 {nk-1}"><Piece Extent="0 {ni-1} 0 {nj-1} 0 {nk-1}">', "<PointData>"]
    for name, a in fields.items():
        out.append(f'<DataArray type="Float32" Name="{name}" format="binary">{enc(a.transpose(2, 1, 0).ravel())}</DataArray>')
    out.append("</PointData><Points>")
    out.append(f'<DataArray type="Float32" NumberOfComponents="3" format="binary">{enc(pts.transpose(2, 1, 0, 3).reshape(-1, 3))}</DataArray>')
    out.append("</Points></Piece></StructuredGrid></VTKFile>")
    Path(path).write_text("\n".join(out))


def export_vtk(run, grid, P, t, every, nphi=96, last_only=False):
    from scipy.io import netcdf_file
    g = {k: v.data.copy() for k, v in netcdf_file(grid, mmap=False).variables.items()}
    R, Z = g["Rxy"], g["Zxy"]
    n = int(scalar(run, "zperiod"))
    nt, nx, ny, nz = P.shape
    # P is stored in shifted (locally toroidal) coordinates: z = toroidal angle over one 1/n wedge -> repeat n times
    phi = np.linspace(0, 2 * np.pi, nphi, endpoint=False)
    zfrac = (phi * n / (2 * np.pi)) % 1.0 * nz
    j0 = np.floor(zfrac).astype(int) % nz; j1 = (j0 + 1) % nz; w = zfrac - np.floor(zfrac)
    Rc = np.concatenate([R, R[:, :1]], axis=1); Zc = np.concatenate([Z, Z[:, :1]], axis=1)   # close the poloidal seam
    pts = np.zeros((nx, ny + 1, nphi + 1, 3))
    ph = np.append(phi, 2 * np.pi)
    pts[..., 0] = Rc[:, :, None] * np.cos(ph)[None, None, :]
    pts[..., 1] = Rc[:, :, None] * np.sin(ph)[None, None, :]
    pts[..., 2] = Zc[:, :, None]
    outdir = Path(run) / "paraview"; outdir.mkdir(exist_ok=True)
    for old in outdir.glob("P_*"):
        old.unlink()
    series = []
    for it in ([nt - 1] if last_only else range(0, nt, every)):
        f = P[it]; f = np.concatenate([f, f[:, :1, :]], axis=1)
        a = f[:, :, j0] * (1 - w) + f[:, :, j1] * w
        a = np.concatenate([a, a[:, :, :1]], axis=2)
        p0 = np.concatenate([g["pressure"], g["pressure"][:, :1]], axis=1)[:, :, None] * np.ones((1, 1, nphi + 1))
        rel = a / (np.abs(a).max() + 1e-300)
        name = f"P_{it:04d}.vts"
        write_vts(outdir / name, pts, {"P_perturbation_normalised": rel, "P0_equilibrium_Pa": p0})   # absolute amplitude is arbitrary in a linear run
        series.append({"name": name, "time": float(t[it])})
    (outdir / "P_series.vts.series").write_text(json.dumps({"file-series-version": "1.0", "files": series}, indent=1))
    return outdir


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--grid"); ap.add_argument("--vtk", action="store_true")
    ap.add_argument("--vtk-every", type=int, default=5)
    a = ap.parse_args()
    res, P, t, rms = growth_rate(a.run)
    Path(a.run, "growth_rate.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if not isinstance(v, list)}))
    if a.vtk:
        print("ParaView files:", export_vtk(a.run, a.grid, P, t, a.vtk_every))


def plot_mode(run, grid, png, title=""):
    """Poloidal cross-section of the final pressure perturbation (z = 0) and its growth history."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from scipy.io import netcdf_file
    g = {k: v.data.copy() for k, v in netcdf_file(grid, mmap=False).variables.items()}
    res = json.loads(Path(run, "growth_rate.json").read_text())
    P = collect(run, "P")[-1, :, :, 0]
    R = np.concatenate([g["Rxy"], g["Rxy"][:, :1]], 1); Z = np.concatenate([g["Zxy"], g["Zxy"][:, :1]], 1)
    Pc = np.concatenate([P, P[:, :1]], 1); Pc = Pc / (np.abs(Pc).max() + 1e-300)
    fig, ax = plt.subplots(1, 2, figsize=(12, 5.5))
    im = ax[0].pcolormesh(R, Z, Pc, shading="gouraud", cmap="RdBu_r", vmin=-1, vmax=1)
    ax[0].set_aspect("equal"); ax[0].set_xlabel("R (m)"); ax[0].set_ylabel("Z (m)"); plt.colorbar(im, ax=ax[0], label="P perturbation (normalised)")
    ax[0].set_title(f"{title} n = {res['zperiod_n']}: mode at t = {res['t'][-1]:.0f} tau_A")
    ax[1].plot(res["t"], res["growth_rate_history"], color="#1f5fa8"); ax[1].axhline(res["gamma_per_alfven_time"], color="#c0392b", ls="--",
              label=f"fit gamma = {res['gamma_per_alfven_time']:.4f} / tau_A")
    ax[1].set_ylim(min(-0.05, res["gamma_per_alfven_time"] - 0.1), max(0.3, res["gamma_per_alfven_time"] * 2)); ax[1].set_xlabel("t / tau_A")
    ax[1].set_ylabel("d ln(rms P) / dt"); ax[1].legend(); ax[1].set_title("Growth rate history")
    plt.tight_layout(); plt.savefig(png, dpi=100); plt.close(fig)
