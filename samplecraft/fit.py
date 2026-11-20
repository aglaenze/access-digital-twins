"""Fitting a sample to a measurement: any number of the recipe becomes a parameter (bounds, ties between parameters),
fitted to a measured transmission, an image or spectra (idea of the EasyScience libraries: parameters with a value, an
error, bounds, fixed or free, ties; the sample model is what is fitted).

    from samplecraft import fit
    params = [fit.Parameter("materials.duplex.mix.ferrite", 0, 1, name="f")]
    ties = {"materials.duplex.mix.austenite": "1 - f"}
    r = fit.fit(recipe, params, o, d, wavelength_A, T, dT, ties=ties)
    r.values, r.errors, r.correlation, r.chi2_red, r.report()
    r.recipe                     # the recipe with the fitted values (fit.set_value, fit.get_value: by path)

A path goes down the recipe: dict keys, and in lists an index or the `name` of an element:
"bodies.plate.shape.size.2" (the thickness of the body named plate), "materials.steel.density_factor",
"bodies.plate.fill.0.voronoi.phases.ferrite".
T: one value per measured point (a pixel) or one row per point and one column per wavelength (spectra). dT: its
errors (same shape); the fit minimizes χ² = Σ ((T_model − T) / dT)². o, d: one ray per point, or k rays per point
(arrays n × k × 3, the transmission averaged over them: a pixel is not a point; `image_rays` draws them). Fitting
a size or a position needs several rays per pixel: with one, a small change moves no ray across an edge.
When all the parameters are in `materials`, the path lengths are computed once (fast: a spectrum fit); otherwise
the scene is rebuilt at every step. Generated microstructures (fills: counts, fractions of a Voronoi polycrystal)
change by steps with the same seed (a cell changes phase or not): χ² is then a staircase that a gradient cannot
follow; fit them as a homogeneous `mix` (same spectrum when the grains are small compared with a pixel), or scan.
"""
import copy
import math

import numpy as np

from . import materials as mats
from .scene import Scene


class Parameter:
    """A number of the recipe, given by its path; free between min and max (fixed=True: kept at its value)."""

    def __init__(self, path, min=-math.inf, max=math.inf, name=None, value=None, fixed=False):
        self.path, self.min, self.max = path, float(min), float(max)
        self.name = name or path.split(".")[-1]
        self.value, self.fixed = value, fixed
        self.error = None

    def __repr__(self):
        e = f" ± {self.error:.3g}" if self.error is not None else ""
        return f"Parameter({self.name} = {self.value!r}{e}, [{self.min:g}, {self.max:g}], {self.path!r})"


def _step(node, key, path):
    if isinstance(node, list):
        if key.lstrip("-").isdigit():
            return int(key)
        hits = [i for i, x in enumerate(node) if isinstance(x, dict) and x.get("name") == key]
        if len(hits) != 1:
            raise KeyError(f"{path}: {'no' if not hits else 'several'} element named {key!r}")
        return hits[0]
    if not isinstance(node, dict) or key not in node:
        raise KeyError(f"{path}: no {key!r} here")
    return key


def get_value(recipe, path):
    node = recipe
    for key in path.split("."):
        node = node[_step(node, key, path)]
    return node


def set_value(recipe, path, value):
    keys = path.split(".")
    node = recipe
    for key in keys[:-1]:
        node = node[_step(node, key, path)]
    node[_step(node, keys[-1], path)] = float(value)


def _unwrap(recipe):
    return recipe.get("recipe") or recipe.get("scene") or recipe


class Result:
    def __init__(self, params, recipe, chi2, n_points, cov, model, success, message):
        self.parameters, self.recipe, self.chi2, self.n_points = params, recipe, chi2, n_points
        free = [p for p in params if not p.fixed]
        self.dof = max(1, n_points - len(free))
        self.chi2_red = chi2 / self.dof
        self.values = {p.name: p.value for p in params}
        self.errors = {p.name: p.error for p in params}
        self.covariance = cov
        s = np.sqrt(np.diag(cov)) if cov is not None else None
        self.correlation = (cov / np.outer(s, s)) if s is not None and (s > 0).all() else None
        self.model, self.success, self.message = model, success, message

    def scene(self, base_dir=None):
        return Scene.from_dict(self.recipe, base_dir)

    def report(self):
        lines = [f"χ² = {self.chi2:.4g} for {self.n_points} points, {self.dof} degrees of freedom: "
                 f"χ²/dof = {self.chi2_red:.3f}"]
        for p in self.parameters:
            if p.fixed:
                lines.append(f"  {p.name:16s} {p.value:.6g} (fixed)")
            else:
                lines.append(f"  {p.name:16s} {p.value:.6g} ± {p.error:.2g}   [{p.min:g}, {p.max:g}]")
        free = [p.name for p in self.parameters if not p.fixed]
        if self.correlation is not None and len(free) > 1:
            for i in range(len(free)):
                for j in range(i + 1, len(free)):
                    if abs(self.correlation[i, j]) > 0.8:
                        lines.append(f"  strongly correlated: {free[i]} and {free[j]} ({self.correlation[i, j]:+.2f})")
        if not self.success:
            lines.append(f"  the fit did not converge: {self.message}")
        return "\n".join(lines)


def image_rays(nx, ny, extent, z0, rays_per_pixel=16, seed=0):
    """Rays along +z for an nx × ny image covering extent = (x0, x1, y0, y1) [mm], starting at z = z0: o, d of shape
    (ny·nx, k, 3), k points drawn at random in each pixel (fixed seed: the same rays at every step of a fit)."""
    rng = np.random.default_rng(seed)
    x0, x1, y0, y1 = extent
    px, py = (x1 - x0) / nx, (y1 - y0) / ny
    j, i = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    u = rng.random((ny * nx, rays_per_pixel, 2))
    o = np.empty((ny * nx, rays_per_pixel, 3))
    o[..., 0] = x0 + (i.ravel()[:, None] + u[..., 0]) * px
    o[..., 1] = y0 + (j.ravel()[:, None] + u[..., 1]) * py
    o[..., 2] = z0
    d = np.zeros_like(o)
    d[..., 2] = 1.0
    return o, d


def fit(recipe, params, o, d, wavelength_A, T, dT, ties=None, base_dir=None, diff_step=None):
    """Fits the free parameters of `recipe` (not changed: a copy is fitted) so that the scene's transmission along the
    rays o + t d at the wavelengths matches T ± dT. ties: {path: expression of the parameter names} (e.g. "1 - f").
    diff_step: relative step of the derivatives (default 1e-3 for materials, 1e-2 when the geometry changes)."""
    from scipy.optimize import least_squares
    base = copy.deepcopy(_unwrap(recipe))
    ties = dict(ties or {})
    lam = np.atleast_1d(np.asarray(wavelength_A, float))
    o, d = np.asarray(o, float), np.asarray(d, float)
    if o.ndim == 1:
        o, d = o[None], d[None]
    n, k = len(o), (o.shape[1] if o.ndim == 3 else 1)
    o, d = o.reshape(n * k, 3), np.broadcast_to(d, (n, k, 3) if k > 1 else (n, 3)).reshape(n * k, 3)
    T = np.asarray(T, float).reshape(n, -1)
    dT = np.broadcast_to(np.asarray(dT, float).reshape(n, -1) if np.ndim(dT) else dT, T.shape)
    if T.shape[1] != len(lam):
        raise ValueError(f"T: {T.shape[1]} columns for {len(lam)} wavelengths")
    if (dT <= 0).any():
        raise ValueError("dT: errors must be positive")
    for p in params:
        if p.value is None:
            p.value = float(get_value(base, p.path))
        if not p.min <= p.value <= p.max:
            raise ValueError(f"{p.name} = {p.value}: outside [{p.min}, {p.max}]")
    free = [p for p in params if not p.fixed]
    if not free:
        raise ValueError("no free parameter")
    paths = [p.path for p in params] + list(ties)
    geometry_fixed = all(path.startswith("materials.") for path in paths)
    if diff_step is None:
        diff_step = 1e-3 if geometry_fixed else 1e-2

    def recipe_of(x):
        r = copy.deepcopy(base)
        vals = {p.name: p.value for p in params}
        vals.update({p.name: v for p, v in zip(free, x)})
        for p in params:
            set_value(r, p.path, vals[p.name])
        for path, expr in ties.items():
            set_value(r, path, eval(expr, {"__builtins__": {}, "math": math}, dict(vals)))
        return r

    lengths = Scene.from_dict(base, base_dir).material_lengths(o, d) if geometry_fixed else None

    def model(x):
        r = recipe_of(x)
        if geometry_fixed:
            cfg, L = mats.resolve(r.get("materials", {}))[0], lengths
        else:
            s = Scene.from_dict(r, base_dir)
            cfg, L = s.cfg(), s.material_lengths(o, d)
        mu = np.zeros((n * k, len(lam)))
        for m, Lm in L.items():
            mu += np.asarray(Lm)[:, None] * 0.1 * mats.sigma(cfg[m], lam)[None, :]
        return np.exp(-mu).reshape(n, k, len(lam)).mean(axis=1)

    res = least_squares(lambda x: ((model(x) - T) / dT).ravel(), [p.value for p in free],
                        bounds=([p.min for p in free], [p.max for p in free]), diff_step=diff_step, x_scale="jac")
    for p, v in zip(free, res.x):
        p.value = float(v)
    J = res.jac
    try:
        cov = np.linalg.inv(J.T @ J)              # errors from dT (absolute): compare χ²/dof with 1
        for p, s in zip(free, np.sqrt(np.diag(cov))):
            p.error = float(s)
    except np.linalg.LinAlgError:
        cov = None
        for p in free:
            p.error = math.nan
    chi2 = float((res.fun ** 2).sum())
    best = recipe_of(res.x)
    return Result(params, best, chi2, T.size, cov, model(res.x), res.success, res.message)
