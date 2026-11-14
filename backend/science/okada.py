"""Surface displacement of a rectangular dislocation in an elastic half-space.

Okada, Y. (1985). Surface deformation due to shear and tensile faults in a half-space. BSSA 75(4), 1135-1154.
Equations (25)-(30) with Chinnery's notation, numpy-vectorized. Checked against Table 2 of the paper in
tests/test_science.py.

Okada frame (okada85): x along strike, y = up × strike (to the left of strike), z up. The fault dips toward -y
(right-hand rule). It spans 0 <= x' <= L along strike and 0 <= eta' <= W up-dip from its lower edge, which is at
depth d below the x axis. U1 is strike slip (hanging wall moves +x, i.e. left-lateral), U2 is dip slip
(positive = reverse), and U3 is tensile opening.

Geographic wrapper (fault_enu): east/north/up displacement of a fault given by the centre of its top edge, its
strike (clockwise from north), dip, rake (Aki & Richards), top depth, length, width and slip.
"""
from __future__ import annotations

import numpy as np

EPS = 1e-12  # relative tolerance used to detect the singular cases of Okada (1992, section 3)


def _guard(a: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return np.abs(a) > EPS * np.maximum(scale, 1.0)


def _corner(xi, eta, q, sd, cd, a):
    """The bracketed terms of eqs (25)-(30) at one corner (xi, eta). Returns 9 arrays: (ux,uy,uz) x (ss,ds,ts)."""
    R = np.sqrt(xi * xi + eta * eta + q * q)
    yt = eta * cd + q * sd
    dt = eta * sd - q * cd
    X = np.sqrt(xi * xi + q * q)
    with np.errstate(divide="ignore", invalid="ignore"):
        ok_eta = _guard(R + eta, R)
        inv_Reta = np.where(ok_eta, 1.0 / (R + eta), 0.0)
        ln_Reta = np.where(ok_eta, np.log(np.abs(R + eta)), -np.log(np.abs(R - eta)))
        inv_Rxi = np.where(_guard(R + xi, R), 1.0 / (R + xi), 0.0)
        theta = np.where(_guard(q, R), np.arctan(xi * eta / (q * R)), 0.0)
        Rdt = R + dt
        ok_dt = _guard(Rdt, R)
        inv_Rdt = np.where(ok_dt, 1.0 / Rdt, 0.0)
        if abs(cd) > 1e-9:
            ln_Rdt = np.where(ok_dt, np.log(np.abs(Rdt)), 0.0)
            I4 = a / cd * (ln_Rdt - sd * ln_Reta)
            num = eta * (X + q * cd) + X * (R + X) * sd
            den = xi * (R + X) * cd
            I5 = np.where(_guard(xi, R), a * 2.0 / cd * np.arctan(num / den), 0.0)
            I3 = a * (yt * inv_Rdt / cd - ln_Reta) + sd / cd * I4
            I1 = a * (-xi * inv_Rdt / cd) - sd / cd * I5
        else:  # vertical fault, eq (29)
            I1 = -a / 2.0 * xi * q * inv_Rdt ** 2
            I3 = a / 2.0 * (eta * inv_Rdt + yt * q * inv_Rdt ** 2 - ln_Reta)
            I4 = -a * q * inv_Rdt
            I5 = -a * xi * sd * inv_Rdt
        I2 = a * (-ln_Reta) - I3
        qRe = q / R * inv_Reta
        qRx = q / R * inv_Rxi
    return (
        xi * qRe + theta + I1 * sd,                       # strike slip
        yt * qRe + q * cd * inv_Reta + I2 * sd,
        dt * qRe + q * sd * inv_Reta + I4 * sd,
        q / R - I3 * sd * cd,                             # dip slip
        yt * qRx + cd * theta - I1 * sd * cd,
        dt * qRx + sd * theta - I5 * sd * cd,
        q * qRe - I3 * sd * sd,                           # tensile
        -dt * qRx - sd * (xi * qRe - theta) - I1 * sd * sd,
        yt * qRx + cd * (xi * qRe - theta) - I5 * sd * sd,
    )


def okada85(x, y, d: float, dip_deg: float, L: float, W: float, U1: float = 0.0, U2: float = 0.0, U3: float = 0.0,
            mu_over_lambda_mu: float = 0.5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ux, uy, uz) at the surface points (x, y), in the Okada frame. mu/(lambda+mu) = 1 - 2 nu (0.5 for nu=0.25)."""
    if L <= 0 or W <= 0:
        raise ValueError("L and W must be positive")
    if d - W * np.sin(np.radians(dip_deg)) < -1e-9:
        raise ValueError("the fault would cross the free surface (d < W sin(dip))")
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    dip = np.radians(dip_deg)
    sd, cd = np.sin(dip), np.cos(dip)
    if abs(cd) < 1e-12:
        cd = 0.0
    p = y * cd + d * sd
    q = y * sd - d * cd
    out = np.zeros((9,) + np.broadcast(x, y).shape)
    for xi, eta, sign in ((x, p, 1), (x, p - W, -1), (x - L, p, -1), (x - L, p - W, 1)):
        out += sign * np.array(_corner(xi, eta, q, sd, cd, mu_over_lambda_mu))
    k = 1.0 / (2.0 * np.pi)
    ux = -k * (U1 * out[0] + U2 * out[3]) + k * U3 * out[6]
    uy = -k * (U1 * out[1] + U2 * out[4]) + k * U3 * out[7]
    uz = -k * (U1 * out[2] + U2 * out[5]) + k * U3 * out[8]
    return ux, uy, uz


def fault_enu(east, north, *, x0: float, y0: float, strike_deg: float, dip_deg: float, rake_deg: float,
              top_depth: float, length: float, width: float, slip: float, nu: float = 0.25):
    """(ue, un, uu) at surface points (east, north) for a fault whose TOP EDGE CENTRE is at (x0, y0).

    Lengths in any one unit (km or m); displacements in the unit of `slip`. Rake: 0 left-lateral, 90 reverse.
    """
    if top_depth < 0:
        raise ValueError("top_depth must be >= 0")
    phi, dip, rake = np.radians(strike_deg), np.radians(dip_deg), np.radians(rake_deg)
    s_e, s_n = np.sin(phi), np.cos(phi)            # strike unit vector
    y_e, y_n = -np.cos(phi), np.sin(phi)           # Okada y axis = up x strike
    de = np.asarray(east, dtype=float) - x0
    dn = np.asarray(north, dtype=float) - y0
    xo = de * s_e + dn * s_n + length / 2.0        # origin at the lower-left corner
    yo = de * y_e + dn * y_n + width * np.cos(dip)
    d = top_depth + width * np.sin(dip)
    ux, uy, uz = okada85(xo, yo, d, dip_deg, length, width, U1=slip * np.cos(rake), U2=slip * np.sin(rake),
                         mu_over_lambda_mu=1.0 - 2.0 * nu)
    return ux * s_e + uy * y_e, ux * s_n + uy * y_n, uz
