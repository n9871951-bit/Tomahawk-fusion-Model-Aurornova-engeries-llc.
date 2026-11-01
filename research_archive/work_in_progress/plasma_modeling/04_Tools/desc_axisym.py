"""Evaluate an axisymmetric DESC equilibrium (FourierZernike basis, n = 0 only) with numpy: R, Z, lambda and their
rho/theta derivatives, profiles, and B. Conventions follow DESC 0.17 (basis.fourier, zernike_radial, PowerSeriesProfile)."""
import math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pyfive

MU0 = 4e-7 * math.pi


def radial_coeffs(l, m):
    """Coefficients c_k of rho^k for the standard Zernike radial polynomial R_l^|m| (R(1) = 1)."""
    m = abs(m); c = {}
    for s in range((l - m) // 2 + 1):
        c[l - 2 * s] = (-1) ** s * math.factorial(l - s) / (math.factorial(s) * math.factorial((l + m) // 2 - s) * math.factorial((l - m) // 2 - s))
    return c


def radial(rho, l, m, dr=0):
    out = np.zeros_like(rho, dtype=float)
    for k, c in radial_coeffs(l, m).items():
        if k - dr < 0:
            continue
        f = math.factorial(k) / math.factorial(k - dr)
        out = out + c * f * rho ** (k - dr)
    return out


def ang(theta, m, dt=0):
    ma = abs(m); shift = (m >= 0) * math.pi / 2 + dt * math.pi / 2
    return ma ** dt * np.sin(ma * theta + shift)


class Eq:
    def __init__(self, path):
        f = pyfive.File(str(path))
        self.Psi = float(f["_Psi"][()]); self.NFP = int(f["_NFP"][()])
        self.c = {}
        for key in ("R", "Z", "L"):
            modes = np.asarray(f[f"_{key}_basis/_modes"][()]); coef = np.asarray(f[f"_{key}_lmn"][()])
            off = np.abs(coef[modes[:, 2] != 0]).max() if (modes[:, 2] != 0).any() else 0.0
            assert off < 1e-5, f"{key} has non-axisymmetric content {off}"
            self.nonaxi = getattr(self, "nonaxi", {}); self.nonaxi[key] = float(off)
            keep = (modes[:, 2] == 0) & (coef != 0)
            self.c[key] = list(zip(modes[keep, 0].astype(int), modes[keep, 1].astype(int), coef[keep]))
        self.prof = {}
        for key in ("pressure", "iota"):
            modes = np.asarray(f[f"_{key}/_basis/_modes"][()])[:, 0].astype(int); par = np.asarray(f[f"_{key}/_params"][()])
            self.prof[key] = list(zip(modes, par))

    def field(self, key, rho, theta, dr=0, dt=0):
        out = np.zeros(np.broadcast(rho, theta).shape)
        for l, m, c in self.c[key]:
            out = out + c * radial(rho, l, m, dr) * ang(theta, m, dt)
        return out

    def profile(self, key, rho, dr=0):
        out = np.zeros_like(np.asarray(rho, dtype=float))
        for k, c in self.prof[key]:
            if k - dr < 0:
                continue
            out = out + c * math.factorial(k) / math.factorial(k - dr) * rho ** (k - dr)
        return out

    def geometry(self, rho, theta):
        """Everything at (rho, theta): positions, covariant basis in (R, Z), Jacobian and B components."""
        R = self.field("R", rho, theta); Z = self.field("Z", rho, theta)
        Rr = self.field("R", rho, theta, dr=1); Rt = self.field("R", rho, theta, dt=1)
        Zr = self.field("Z", rho, theta, dr=1); Zt = self.field("Z", rho, theta, dt=1)
        Lt = self.field("L", rho, theta, dt=1)
        # zeta = phi (cylindrical, right-handed R, phi, Z): sqrt(g) = e_rho . (e_theta x e_zeta) = R (R_t Z_r - R_r Z_t)
        sg = R * (Rt * Zr - Rr * Zt)
        psi_r = self.Psi * rho / math.pi                      # d(psi)/d(rho), psi = toroidal flux / 2 pi
        iota = self.profile("iota", rho)
        Bth = psi_r * iota / sg                               # B^theta (lambda_zeta = 0, axisymmetric)
        Bze = psi_r * (1.0 + Lt) / sg                         # B^zeta
        BR = Bth * Rt; BZ = Bth * Zt; Bphi = Bze * R          # physical components
        return dict(R=R, Z=Z, Rr=Rr, Rt=Rt, Zr=Zr, Zt=Zt, sqrtg=sg, BR=BR, BZ=BZ, Bphi=Bphi,
                    Bp=np.hypot(BR, BZ), B=np.sqrt(BR ** 2 + BZ ** 2 + Bphi ** 2), iota=iota, p=self.profile("pressure", rho))
