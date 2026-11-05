"""Analysis brick of the LoKI twin (used by the web page; the notebooks show the same steps as code).

  * guinier(q, I, dI): radius of gyration from the lowest Q, range Q·Rg < 1.3 found iteratively;
  * sphere_fit(q, I, dI): the whole curve fitted with the sphere model of sasmodels (the computing engine of SasView),
    in absolute units: scale = volume fraction, radius, background; contrast fixed (silica in D₂O).
"""
import numpy as np

import loki_samples as ls


def guinier(q, I, dI, q_max=0.02, limit=1.3, bg=0.0):
    """dict(rg, drg, i0, di0, mask, a, b, q_max) or None if not enough points."""
    g = None
    for _ in range(20):
        m = (q < q_max) & (I - bg > 0)
        if m.sum() < 4:
            return g
        y, w = np.log(I[m] - bg), ((I[m] - bg) / dI[m]) ** 2
        A = np.column_stack([np.ones(m.sum()), q[m] ** 2])
        cov = np.linalg.inv(A.T @ (A * w[:, None]))
        a, b = cov @ (A.T @ (w * y))
        if b >= 0:
            return g
        rg = np.sqrt(-3 * b)
        g = dict(rg=rg, drg=1.5 / rg * np.sqrt(cov[1, 1]), i0=np.exp(a), di0=np.exp(a) * np.sqrt(cov[0, 0]), mask=m,
                 a=a, b=b, q_max=q_max)
        if abs(limit / rg - q_max) < 1e-5:
            break
        q_max = limit / rg
    return g


def sphere_model():
    from sasmodels.core import load_model
    return load_model("sphere")


def sphere_intensity(model, q, scale, radius, background, sld=ls.SLD["silica"], sld_solvent=ls.SLD["D2O"]):
    """I(Q) [cm⁻¹] of the sasmodels sphere model (scale = volume fraction)."""
    from sasmodels.direct_model import call_kernel
    kernel = model.make_kernel([q])
    return call_kernel(kernel, dict(scale=scale, radius=radius, background=background, sld=sld,
                                    sld_solvent=sld_solvent))


def sphere_fit(q, I, dI, radius0=50.0, scale0=0.01, background0=0.0):
    """Least-squares fit of the sasmodels sphere model: dict(phi, dphi, radius, dradius, background, dbackground,
    chi2, model) with phi the volume fraction."""
    from scipy.optimize import least_squares
    model = sphere_model()
    res = least_squares(lambda p: (sphere_intensity(model, q, *p) - I) / dI, [scale0, radius0, background0],
                        x_scale=[scale0, radius0, 0.01])
    J = res.jac
    cov = np.linalg.inv(J.T @ J)
    err = np.sqrt(np.diag(cov))
    chi2 = np.sum(res.fun ** 2) / max(len(q) - 3, 1)
    p = res.x
    return dict(phi=p[0], dphi=err[0], radius=p[1], dradius=err[1], background=p[2], dbackground=err[2], chi2=chi2,
                model=model, p=p)
