"""Automatic checks of the exercises of the LoKI twin (MSc notebooks): the twin knows the true sample (written in
entry/twin of every file), so a student's result can be compared with the truth, with feedback.

The tolerances include what the instrument does to a perfect sample: the resolution (spread of wavelengths, beam
size) makes Rg look 1-2 % larger and fills in the minima of the form factor.
"""
import numpy as np

import loki_samples as ls

_, _, TRUE = ls.silica_spheres()
R_TRUE, PHI_TRUE = TRUE["radius"], TRUE["phi"]
RG_TRUE = np.sqrt(3 / 5) * R_TRUE
I0_TRUE = TRUE["i0"]


def _ok(msg):
    print("✔ " + msg)


def _no(msg):
    print("✘ " + msg)


def _given(x, dx, name):
    if x is None:
        _no(f"{name} is still None")
        return False
    if dx is None or not np.isfinite(dx) or dx <= 0:
        _no(f"give the uncertainty of {name} as well (square root of the diagonal of the covariance matrix)")
        return False
    return True


def check_guinier(rg, drg, i0=None):
    if not _given(rg, drg, "rg"):
        return False
    if abs(rg / np.sqrt(3 / 5) - R_TRUE) < 2 and abs(rg - RG_TRUE) > 3:
        return _no(f"{rg:.1f} Å looks like the radius R, not the radius of gyration Rg = √(3/5) R")
    if abs(rg - RG_TRUE) / RG_TRUE < 0.04:
        _ok(f"Rg = {rg:.1f} ± {drg:.1f} Å: right (the instrument resolution makes it look 1-2 % larger than the true "
            f"{RG_TRUE:.1f} Å).")
        if i0 is not None:
            (_ok if abs(i0 - I0_TRUE) / I0_TRUE < 0.06 else _no)(
                f"I(0) = {i0:.3f} cm⁻¹ (true {I0_TRUE:.3f} cm⁻¹)" + ("" if abs(i0 - I0_TRUE) / I0_TRUE < 0.06 else
                ": check the units (cm⁻¹: divided by the thickness?) and that the solvent was subtracted"))
        return True
    if rg > RG_TRUE * 1.04:
        return _no(f"Rg = {rg:.1f} Å is too large: is your Q range too wide (Q·Rg must stay below about 1.3), or the "
                   f"solvent not subtracted?")
    return _no(f"Rg = {rg:.1f} Å is too small: are the lowest-Q points used? Is ln I plotted against Q² (not Q)?")


def check_sphere(radius, dradius, phi=None, dphi=None):
    if not _given(radius, dradius, "radius"):
        return False
    good = abs(radius - R_TRUE) / R_TRUE < 0.03
    (_ok if good else _no)(f"R = {radius:.1f} ± {dradius:.1f} Å" + (": right." if good else
                                                                   f": {radius - R_TRUE:+.1f} Å from the truth. "
                                                                   "Check the starting values and the units (Å)."))
    if phi is not None:
        if phi > 0.5:
            _no(f"φ = {phi:.3g}: a volume fraction, not a percentage? (scale of sasmodels)")
            return False
        gp = abs(phi - PHI_TRUE) / PHI_TRUE < 0.08
        (_ok if gp else _no)(f"φ = {100 * phi:.2f} %" + (" : right." if gp else
                                                       f" : the true value is {100 * PHI_TRUE:g} %. Are the SLDs right "
                                                       "(silica 3.47, D2O 6.36, in 10⁻⁶ Å⁻²)? Data in cm⁻¹?"))
        good = good and gp
    return good
