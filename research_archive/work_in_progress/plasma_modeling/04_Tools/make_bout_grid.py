"""BOUT++ grid (closed flux surfaces, orthogonal mesh) from AuroraNova's Tomahawk N9A2 equilibrium (DESC, axisymmetric).

x = poloidal flux per radian chi (Wb/rad), y = orthogonal poloidal angle (0..2 pi), z = toroidal angle.
Mesh lines in x follow orthogonal trajectories of the flux surfaces (d theta / d rho = -g_rho_theta / g_theta_theta),
so the grid is orthogonal, as elm-pb assumes. Curvature, shift and current use the same formulas that reproduce the
BOUT++ cbm18 reference grid (bxcvx to 2e-6, ShiftAngle exact).

usage: python make_bout_grid.py N9A2.h5 out.nc [--nx 68 --ny 64 --psin0 0.40 --psin1 1.0 --density 3.46e20]
"""
import argparse, json, math, sys
from pathlib import Path
import numpy as np
from scipy.io import netcdf_file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from desc_axisym import Eq, MU0

ap = argparse.ArgumentParser()
ap.add_argument("eq"); ap.add_argument("out")
ap.add_argument("--nx", type=int, default=68); ap.add_argument("--ny", type=int, default=64)
ap.add_argument("--pscale", type=float, default=1.0)
ap.add_argument("--psin0", type=float, default=0.40); ap.add_argument("--psin1", type=float, default=1.0)
a = ap.parse_args()
e = Eq(a.eq)
nx, ny = a.nx, a.ny

# 1. poloidal flux chi(rho): d chi / d rho = iota * d psi / d rho, psi = Psi rho^2 / (2 pi)
rf = np.linspace(0.0, 1.0, 20001)
dchi = e.profile("iota", rf) * e.Psi * rf / math.pi
chi = np.concatenate([[0.0], np.cumsum(0.5 * (dchi[1:] + dchi[:-1]) * np.diff(rf))])
chi_b = chi[-1]
psin = np.linspace(a.psin0, a.psin1, nx)
rho_i = np.interp(psin * chi_b, chi, rf)

# 2. orthogonal trajectories from the outer surface inward (start: equal poloidal arc length on the outermost surface)
def dtheta_drho(r, t):
    g = e.geometry(np.full_like(t, r), t)
    return -(g["Rr"] * g["Rt"] + g["Zr"] * g["Zt"]) / (g["Rt"] ** 2 + g["Zt"] ** 2)
tt = np.linspace(0, 2 * np.pi, 4001)
go = e.geometry(np.full_like(tt, rho_i[-1]), tt)
s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(go["R"]), np.diff(go["Z"])))])
ang0 = np.arctan2(go["Z"], go["R"] - e.geometry(np.array([1e-4]), np.array([0.0]))["R"][0])
j_out = np.argmin(np.abs(ang0))                                    # outboard midplane = y index 0 reference
L_pol = s[-1]
s = (s[:-1] - s[j_out]) % L_pol; tt_ = tt[:-1]
order = np.argsort(s)
theta_start = np.interp(np.arange(ny) / ny * L_pol, s[order], tt_[order], period=L_pol)
theta_start = np.unwrap(theta_start)
theta = np.zeros((nx, ny)); theta[-1] = theta_start
t = theta_start.copy()
for i in range(nx - 1, 0, -1):                                     # RK4 in rho, 10 substeps per cell
    r0, r1 = rho_i[i], rho_i[i - 1]; n_sub = 10; h = (r1 - r0) / n_sub; r = r0
    for _ in range(n_sub):
        k1 = dtheta_drho(r, t); k2 = dtheta_drho(r + h / 2, t + h / 2 * k1)
        k3 = dtheta_drho(r + h / 2, t + h / 2 * k2); k4 = dtheta_drho(r + h, t + h * k3)
        t = t + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4); r += h
    theta[i - 1] = t
RHO = np.repeat(rho_i[:, None], ny, axis=1)
G = e.geometry(RHO, theta)

# 3. metric quantities
dy = 2 * np.pi / ny; y = np.arange(ny) * dy
kk = np.fft.fftfreq(ny, d=dy) * 2 * np.pi
def dY(f):
    return np.real(np.fft.ifft(1j * kk * np.fft.fft(f, axis=1), axis=1))
thu = np.unwrap(theta, axis=1)
dth_dy = 1.0 + dY(thu - y[None, :])                                 # theta - y is periodic
hthe = np.hypot(G["Rt"], G["Zt"]) * dth_dy
R, Z, Bp, Bt, B = G["R"], G["Z"], G["Bp"], G["Bphi"], G["B"]
psixy = np.repeat((psin * chi_b)[:, None], ny, axis=1)
dxv = (psin[1] - psin[0]) * chi_b
def dX(f):
    return np.gradient(f, psin * chi_b, axis=0, edge_order=2)
# orthogonality check: tangent along y vs along x (finite differences)
tx = np.stack([dX(R), dX(Z)]); ty = np.stack([dY(R), dY(Z)])
cosang = (tx * ty).sum(0) / (np.linalg.norm(tx, axis=0) * np.linalg.norm(ty, axis=0))

nu = Bt * hthe / (R * Bp)                                            # d phi / d y along the field line
nu_mean = nu.mean(axis=1, keepdims=True)
fk = np.fft.fft(nu - nu_mean, axis=1); kk_safe = np.where(kk == 0, 1, kk)
integ = np.real(np.fft.ifft(np.where(kk == 0, 0, fk / (1j * kk_safe)), axis=1))
zShift = nu_mean * y[None, :] + integ
zShift = zShift - zShift[:, [ny // 2]]                              # zero at mid-index, as in the BOUT++ reference grid
ShiftAngle = 2 * np.pi * nu_mean[:, 0]
sinty = dX(zShift)
ShiftTorsion = dX(nu)                                               # = d nu / d x (matches the BOUT++ reference grid exactly)

bxcvx = 0.5 * B * Bp / hthe * dY(Bt * R / B ** 2)
bxcvy = -0.5 * B * Bp / hthe * dX(Bt * R / B ** 2)
bxcvphi = 0.5 * B * Bp / hthe * dX(Bp * hthe / B ** 2)
bxcvz = bxcvphi - nu * bxcvy - sinty * bxcvx

Jy = -(Bp / hthe) * dX(R * Bt) / MU0
Jphi = (Bp / hthe) * dX(Bp * hthe) / MU0
Jpar0 = (Jy * Bp * hthe + Jphi * R * Bt) / B
pressure = a.pscale * np.maximum(G["p"], 0.0)                      # pscale != 1: pressure-margin test (J and geometry kept)

# checks
q_desc = 1.0 / e.profile("iota", rho_i)
F = R * Bt
diag = {
    "nx": nx, "ny": ny, "pressure_scale": a.pscale, "psin_range": [a.psin0, a.psin1], "rho_range": [float(rho_i[0]), float(rho_i[-1])],
    "chi_boundary_Wb_per_rad": float(chi_b),
    "max_abs_cos_angle_x_y_lines_interior": float(np.abs(cosang[2:-2]).max()),
    "ShiftAngle_over_2pi_vs_q_max_rel_diff": float(np.abs(ShiftAngle / (2 * np.pi) / q_desc - 1).max()),
    "q_range": [float(q_desc.min()), float(q_desc.max())],
    "F_RBt_poloidal_variation_max_rel": float((np.ptp(F, axis=1) / np.abs(F.mean(1))).max()),
    "B_range_T": [float(B.min()), float(B.max())], "pressure_range_Pa": [float(pressure.min()), float(pressure.max())],
    "Jpar0_range_A_m2": [float(Jpar0[2:-2].min()), float(Jpar0[2:-2].max())],
    "hthe_range_m": [float(hthe.min()), float(hthe.max())], "R_range_m": [float(R.min()), float(R.max())],
    "non_axisymmetric_residual_m": e.nonaxi,
}
with netcdf_file(a.out, "w", version=2) as f:
    f.createDimension("x", nx); f.createDimension("y", ny)
    def put(name, val):
        val = np.asarray(val, dtype=float)
        if val.ndim == 2:
            v = f.createVariable(name, "d", ("x", "y"))
        elif val.ndim == 1:
            v = f.createVariable(name, "d", ("x",))
        else:
            v = f.createVariable(name, "d", ())
        v[...] = val
    def puti(name, val):
        v = f.createVariable(name, "i", ()); v[...] = int(val)
    puti("nx", nx); puti("ny", ny)
    puti("ixseps1", nx); puti("ixseps2", nx)
    puti("jyseps1_1", -1); puti("jyseps1_2", ny // 2); puti("jyseps2_1", ny // 2); puti("jyseps2_2", ny - 1)
    for k, v in dict(Rxy=R, Zxy=Z, Bpxy=Bp, Btxy=Bt, Bxy=B, hthe=hthe, psixy=psixy, dx=np.full((nx, ny), dxv),
                     dy=np.full((nx, ny), dy), zShift=zShift, sinty=sinty, bxcvx=bxcvx, bxcvy=bxcvy, bxcvz=bxcvz,
                     Jpar0=Jpar0, pressure=pressure, ShiftTorsion=ShiftTorsion, pol_angle=np.repeat(y[None, :], nx, 0)).items():
        put(k, v)
    put("ShiftAngle", ShiftAngle)
    put("psi_axis", 0.0); put("psi_bndry", chi_b)
    put("bmag", float(e.geometry(np.array([1e-4]), np.array([0.0]))["B"][0]))
    put("rmag", float(e.geometry(np.array([1e-4]), np.array([0.0]))["R"][0]))
print(json.dumps(diag, indent=1))
Path(a.out).with_suffix(".json").write_text(json.dumps(diag, indent=1))
