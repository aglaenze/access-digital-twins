"""Automatic checks of the exercises of the ODIN twin (MSc notebooks): the twin knows the true sample, so a student's
result can be compared with the truth, with feedback rather than just "right" or "wrong".

The iron of the twin is NCrystal's α-iron (Fe_sg229_Iron-alpha.ncmat), lattice parameter A_FE; its (110) edge is at
2 d_110 = A_FE·√2. The twin's measurement of this edge has a small systematic offset (about +0.005 Å, from the
time -> λ conversion; see ODIN_analysis.ipynb part 6): a result within TOL of the truth counts as right.
"""
import numpy as np

A_FE = 2.8665                       # Å
EDGE_110 = A_FE * np.sqrt(2)        # Å
TOL = 0.012                         # Å on the edge (systematic offset + a few standard deviations)


def _ok(msg):
    print("✔ " + msg)


def _no(msg):
    print("✘ " + msg)


def check_edge(lam_edge, dlam_edge):
    if lam_edge is None:
        return _no("no edge yet: fit the (110) edge first (button Fit)")
    if dlam_edge is None or not np.isfinite(dlam_edge) or dlam_edge <= 0:
        return _no("give the uncertainty dlam_edge as well (square root of the diagonal of the covariance matrix)")
    diff = lam_edge - EDGE_110
    if abs(diff) > 0.3:
        return _no(f"{lam_edge:.3f} Å is far from the (110) edge: is your window around 2·d_110 = a·√2? Another edge, "
                   f"or the baseline, may have been fitted")
    if dlam_edge > 0.05:
        return _no(f"the uncertainty ({dlam_edge:.3f} Å) is very large: is the range wide enough to include the "
                   f"baseline on both sides? Are the error bars used (sigma=dT, absolute_sigma=True)?")
    if abs(diff) <= TOL:
        _ok(f"(110) edge at {lam_edge:.4f} ± {dlam_edge:.4f} Å: right (the true edge is within {TOL} Å).")
        if abs(diff) > 3 * dlam_edge:
            print(f"  Note: you are {abs(diff) / dlam_edge:.0f} standard deviations from the truth. Counting longer "
                  f"would not fix this: it is a systematic error (part 7).")
        return True
    _no(f"{lam_edge:.4f} ± {dlam_edge:.4f} Å is {diff:+.3f} Å from the truth. Check the model (is the step going "
        f"up with λ?), the range, and the start values of the fit.")
    return False


def check_lattice(a, da):
    if a is None:
        return _no("a_fe is still None")
    if da is None or not np.isfinite(da) or da <= 0:
        return _no("give the uncertainty da_fe as well (propagate dlam_edge)")
    if abs(a - A_FE) <= TOL / np.sqrt(2):
        _ok(f"a = {a:.4f} ± {da:.4f} Å: right (reference {A_FE} Å).")
        return True
    if abs(a * 2 - A_FE) < 0.05 or abs(a / np.sqrt(2) - A_FE) < 0.05 or abs(a * np.sqrt(2) - A_FE) < 0.05:
        return _no(f"a = {a:.4f} Å: a factor 2 or √2 is wrong. Remember λ_edge = 2 d_110 and d_110 = a / √2.")
    return _no(f"a = {a:.4f} Å is {a - A_FE:+.4f} Å from the reference {A_FE} Å.")
