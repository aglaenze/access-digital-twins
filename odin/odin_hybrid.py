"""Hybrid mode of the ODIN digital twin: counting times as long as on the real instrument.

Why: the real ODIN counts ~10⁵ neutrons/s in 6 mm × 6 mm. Drawing each count from a McStas event ("mcstas" mode of
odin_virtual) reuses the same simulated neutrons after a few tenths of a second at short λ (see README, mc_factor).
Here we separate what McStas must compute from what can be computed exactly.

Open beam, in the detector field of view:
    I_O(x, y, t, λ) = S(t, λ) · a(λ) · f(x, y)
  * S(t, λ): ALL neutrons of the McStas upstream part (guide exit) that pass the pinhole D, with their arrival time
    at the detector (free flight from the guide exit; the diffuser is elastic and deflects by a few degrees at most:
    path lengthening < 10⁻³, neglected). ~2·10⁷ distinct neutrons for the 1e10 upstream file;
  * a(λ): fraction of these neutrons reaching the field of view (diffuser, divergence): ratio between the full McStas
    simulation of the open beam (focused diffuser) and S, smoothed by a spline (χ²/n ≈ 1);
  * f(x, y): spatial profile in the field of view, fitted (degree-2 polynomial) on the same simulation.
Sample (attenuation of the direct beam, Beer-Lambert law):
    T(x, y, λ) = exp(-Σ_i Σ_tot,i(λ) · L_i(x, y)),
  Σ_tot,i: total macroscopic cross-section of material i (NCrystal, same files as in McStas);
  L_i: path length through volume i along the beam (geometry, stage translation and rotation).

Neglected (but included in "mcstas" mode): neutrons scattered by the sample that still reach the detector, and the
variation of the spectrum with position in the field of view.
Noise: the Monte Carlo noise of S is the same in the sample and open-beam measurements and cancels in the
transmission E/O. Otherwise counts follow a true Poisson law.
"""
import os

import numpy as np

import odin_paths  # noqa: F401  (sets sys.path)
import odin_mcstas as tw

H_OVER_M = 3956.034            # m·Å/s
Z_DET = tw.Z_SAMPLE + tw.DET_DIST


# --------------------------------------------------------------------------- open beam
def pinhole_spectrum(front_mcpl, D, cache_dir):
    """S: upstream neutrons passing the square pinhole D (at Z_PINHOLE), with t at the detector. Cached .npz."""
    name = os.path.join(cache_dir, f"S_D{D:.3f}.npz")
    if os.path.isfile(name):
        z = np.load(name)
        return {k: z[k] for k in z.files}
    fr = tw.read_mcpl(front_mcpl, light=False)
    dzp = tw.Z_PINHOLE - fr["z"]
    xp = fr["x"] + fr["ux"] / fr["uz"] * dzp
    yp = fr["y"] + fr["uy"] / fr["uz"] * dzp
    ok = (np.abs(xp) <= D / 2) & (np.abs(yp) <= D / 2)
    lam = fr["lam"][ok].astype(np.float64)
    v = H_OVER_M / lam
    t_det = fr["t"][ok] + (Z_DET - fr["z"][ok]) / (v * fr["uz"][ok])
    S = dict(t=t_det, lam=lam.astype(np.float32), w=fr["w"][ok].astype(np.float64))
    os.makedirs(cache_dir, exist_ok=True)
    np.savez(name, **S)
    return S


def fit_acceptance(S, events_ob, field, lam_edges=np.arange(1.0, 9.0001, 0.1)):
    """a(λ) = (McStas intensity in the field of view) / (intensity of S), smoothed: cubic spline of log a weighted by
    the Monte Carlo noise, smoothing set for χ²/n ≈ 1 (s = number of points). Returns (spline tck, diagnostics)."""
    from scipy.interpolate import splrep, splev
    x0, x1, y0, y1 = field
    num = np.zeros(len(lam_edges) - 1); var = np.zeros_like(num)
    for e in tw.iter_mcpl(events_ob, light=True):
        s = (e["x"] >= x0) & (e["x"] < x1) & (e["y"] >= y0) & (e["y"] < y1)
        w = e["w"][s].astype(float)
        a, _ = np.histogram(e["lam"][s], lam_edges, weights=w)
        b, _ = np.histogram(e["lam"][s], lam_edges, weights=w * w)
        num += a; var += b
    den, _ = np.histogram(S["lam"], lam_edges, weights=S["w"])
    ok = (num > 0) & (den > 0)
    lc = 0.5 * (lam_edges[1:] + lam_edges[:-1])
    r = num[ok] / den[ok]
    sig_log = np.sqrt(var[ok]) / num[ok]                           # relative error = error on log r
    tck = splrep(lc[ok], np.log(r), w=1 / sig_log, s=float(ok.sum()))
    resid = (np.log(r) - splev(lc[ok], tck)) / sig_log
    return tck, dict(lc=lc[ok], a_mc=r, sig_rel=sig_log, a_fit=np.exp(splev(lc[ok], tck)),
                     chi2n=float(np.mean(resid ** 2)), n=int(ok.sum()), knots=len(tck[0]))


def fit_profile(events_ob, field, n=14):
    """f(x, y) = 1 + c·(x, y, x², y², xy), normalized, fitted on the McStas intensity (n × n grid)."""
    x0, x1, y0, y1 = field
    xe, ye = np.linspace(x0, x1, n + 1), np.linspace(y0, y1, n + 1)
    h = np.zeros((n, n)); v = np.zeros((n, n))
    for e in tw.iter_mcpl(events_ob, light=True):
        w = e["w"].astype(float)
        a, _, _ = np.histogram2d(e["x"], e["y"], [xe, ye], weights=w)
        b, _, _ = np.histogram2d(e["x"], e["y"], [xe, ye], weights=w * w)
        h += a; v += b
    X, Y = np.meshgrid(0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1]), indexing="ij")
    A = np.c_[np.ones(X.size), X.ravel(), Y.ravel(), X.ravel() ** 2, Y.ravel() ** 2, (X * Y).ravel()]
    sw = 1 / np.sqrt(v.ravel())
    c, *_ = np.linalg.lstsq(A * sw[:, None], h.ravel() * sw, rcond=None)
    c = c / c[0]
    model = A @ c
    resid = (h.ravel() - model * h.sum() / model.sum()) * sw
    return c, dict(chi2n=float(np.mean(resid ** 2)), variation=float(model.max() / model.min() - 1))


def profile(c, x, y):
    return c[0] + c[1] * x + c[2] * y + c[3] * x * x + c[4] * y * y + c[5] * x * y


# --------------------------------------------------------------------------- sample
def box_path_length(x, y, center, dims, rot_deg):
    """Path length (m) through a box (dims = width x, height y, thickness z) rotated by rot_deg about the vertical axis
    (y) and centered at `center`, for rays parallel to the beam axis (z) passing at (x, y). Slab method in the box
    frame. Convention: a point (x, z) of the box frame appears at x·cos θ + z·sin θ in the lab frame."""
    th = np.radians(rot_deg)
    c, s = np.cos(th), np.sin(th)
    # Ray: origin (x, y, -1), direction (0, 0, 1), expressed in the box frame (inverse rotation)
    ox, oy, oz = x - center[0], y - center[1], -1.0 - center[2]
    ox_b, oz_b = c * ox - s * oz, s * ox + c * oz
    dx_b, dz_b = -s, c
    tmin = np.full(np.shape(x), -np.inf); tmax = np.full(np.shape(x), np.inf)
    for o, d, h in ((ox_b, dx_b, dims[0] / 2), (oz_b, dz_b, dims[2] / 2)):
        if abs(d) < 1e-15:
            tmin = np.where(np.abs(o) <= h, tmin, np.inf)
        else:
            t1, t2 = (-h - o) / d, (h - o) / d
            tmin = np.maximum(tmin, np.minimum(t1, t2)); tmax = np.minimum(tmax, np.maximum(t1, t2))
    tmin = np.where(np.abs(oy) <= dims[1] / 2, tmin, np.inf)
    return np.clip(tmax - tmin, 0, None)


def sphere_path_length(x, y, center, diameter):
    """Path length (m) through a sphere for rays along the beam (z) passing at (x, y): a chord."""
    r2 = (diameter / 2) ** 2 - (np.asarray(x) - center[0]) ** 2 - (np.asarray(y) - center[1]) ** 2
    return 2 * np.sqrt(np.clip(r2, 0, None))


def cylinder_path_length(x, y, center, diameter, height):
    """Path length (m) through a vertical cylinder (axis y: the rotation of the stage does not change it) for rays
    along the beam (z) passing at (x, y)."""
    r2 = (diameter / 2) ** 2 - (np.asarray(x) - center[0]) ** 2
    return np.where(np.abs(np.asarray(y) - center[1]) <= height / 2, 2 * np.sqrt(np.clip(r2, 0, None)), 0.0)


def ellipsoid_path_length(x, y, center, dims, rot_deg):
    """Path length (m) through an ellipsoid of axes dims = (x, y, z) (full lengths), turned by rot_deg about the
    vertical axis (same convention as box_path_length), for rays along the beam (z) passing at (x, y)."""
    th = np.radians(rot_deg)
    c, s = np.cos(th), np.sin(th)
    a, b, cz = dims[0] / 2, dims[1] / 2, dims[2] / 2
    ox, oy, oz = np.asarray(x) - center[0], np.asarray(y) - center[1], -1.0 - center[2]
    ox_b, oz_b = c * ox - s * oz, s * ox + c * oz
    dx_b, dz_b = -s, c
    A = (dx_b / a) ** 2 + (dz_b / cz) ** 2
    B = 2 * (ox_b * dx_b / a ** 2 + oz_b * dz_b / cz ** 2)
    C = (ox_b / a) ** 2 + (oy / b) ** 2 + (oz_b / cz) ** 2 - 1
    disc = B * B - 4 * A * C
    return np.sqrt(np.clip(disc, 0, None)) / A


def _path(shape, x, y, center, dims, stage_rot):
    own = dims[3] if len(dims) > 3 else 0.0               # a box or an ellipsoid turned in the sample: its own angle
    if shape == "sphere":
        return sphere_path_length(x, y, center, dims[0])
    if shape == "cylinder":
        return cylinder_path_length(x, y, center, dims[0], dims[1])
    if shape == "ellipsoid":
        return ellipsoid_path_length(x, y, center, dims, stage_rot + own)
    return box_path_length(x, y, center, dims, stage_rot + own)


MAP_STEP = 20e-6           # [m] grid of the thickness maps of a sample made of many volumes (below the blurs)
MAP_HALF = 7.2e-3          # [m] half-width of that grid (the field of view of the cameras, ±7.05 mm)


_SIGMA = {}


def sigma_tot(cfg, lam):
    """Σ_tot(λ) in m⁻¹ (NCrystal gives cm⁻¹); kept for each material and grid (a rock: thousands of volumes, a few
    materials)."""
    lam = np.asarray(lam, dtype=float)
    key = (cfg, len(lam), float(lam[0]), float(lam[-1]))
    if key not in _SIGMA:
        if len(_SIGMA) > 64:
            _SIGMA.clear()
        _SIGMA[key] = 100.0 * tw.sigma_tot(cfg, lam)
    return _SIGMA[key]


def volumes_transmission(volumes, stage_x, stage_rot, lam_grid=np.linspace(0.3, 20.0, 4000), strains=None):
    """Function T(x, y, λ) for a sample made of volumes [(NCrystal cfg, center (m), dims (m)[, shape[, host cfg]]), ...]
    (boxes, spheres, vertical cylinders; an inclusion names the material of the volume around it, which it replaces),
    centers given with
    respect to the rotation-stage axis; the stage is translated by stage_x then rotated by stage_rot (degrees) about
    the vertical axis. Σ_tot(λ) is interpolated on a grid covering all chopper modes (NCrystal called once).
    strains: lattice strain ε of each volume along the beam (a sample under load, sample_library.odin_strain_per_kN):
    every lattice spacing seen by the beam becomes d (1 + ε), so every Bragg edge (λ = 2d) moves to λ (1 + ε):
    Σ_tot(λ) of the strained volume = Σ_tot(λ / (1 + ε)) of the unstrained material. (The smooth parts of Σ_tot,
    absorption and inelastic scattering, move with it: an error of ε, about 10⁻³, on a slowly varying term.)"""
    th = np.radians(stage_rot)
    c, s = np.cos(th), np.sin(th)
    if strains is not None:
        # a strain moves an edge by about 10⁻³ λ (0.004 Å), less than a step of the default grid (0.005 Å), on which
        # the edge would jump by a whole step or not at all: a grid of 0.0001 Å for a sample in a load frame (also
        # without load: the reference measurement must have its edge at the same place, to 10⁻⁵)
        lam_grid = np.linspace(lam_grid[0], lam_grid[-1], int(round((lam_grid[-1] - lam_grid[0]) / 1e-4)) + 1)
    vols, epss = [], []
    for k, v in enumerate(volumes):       # (cfg, center, dims[, shape]): boxes, spheres, vertical cylinders
        cfg, (cx, cy, cz), dims = v[:3]
        center = (stage_x + c * cx + s * cz, cy, -s * cx + c * cz)
        eps = float(strains[k]) if strains is not None else 0.0
        sig = sigma_tot(cfg, lam_grid / (1.0 + eps))
        if len(v) > 4 and v[4]:           # an inclusion: replaces the material of the volume around it on its path
            sig = sig - sigma_tot(v[4], lam_grid / (1.0 + eps))
        vols.append((sig, center, dims, v[3] if len(v) > 3 else "box"))
        epss.append(eps)

    if len(vols) > 20:
        return _mapped_transmission(volumes, vols, stage_rot, lam_grid, epss)

    def T(x, y, lam):
        mu = np.zeros(len(x))
        for sig, center, dims, shape in vols:
            L = _path(shape, x, y, center, dims, stage_rot)
            k = L > 0
            mu[k] += np.interp(lam[k], lam_grid, sig) * L[k]
        return np.exp(-mu)
    return T


def _mapped_transmission(volumes, vols, stage_rot, lam_grid, epss=None):
    """A sample made of many volumes (a rock: hundreds of grains): the thickness crossed in each material is computed
    once, on a grid of MAP_STEP over the field (each volume only within its own extent), then read for each neutron
    or pixel; T = exp(−Σ_m Σ_m(λ) L_m(x, y)). The volumes of the same material (and host, and strain) share one
    map."""
    n = int(round(2 * MAP_HALF / MAP_STEP)) + 1
    g = -MAP_HALF + np.arange(n) * MAP_STEP
    maps, sigs = {}, {}
    for k, (v, (sig, center, dims, shape)) in enumerate(zip(volumes, vols)):
        key = (v[0], v[4] if len(v) > 4 else None, round(float(epss[k]), 9) if epss else 0.0)
        sigs[key] = sig
        r = 0.5 * float(np.sqrt(dims[0] ** 2 + dims[2] ** 2)) if shape in ("box", "ellipsoid") else 0.5 * dims[0]
        hy = 0.5 * (dims[1] if shape != "sphere" else dims[0])
        ix = np.where((g >= center[0] - r - MAP_STEP) & (g <= center[0] + r + MAP_STEP))[0]
        iy = np.where((g >= center[1] - hy - MAP_STEP) & (g <= center[1] + hy + MAP_STEP))[0]
        if not len(ix) or not len(iy):
            continue
        X, Y = np.meshgrid(g[ix], g[iy])
        L = _path(shape, X.ravel(), Y.ravel(), center, dims, stage_rot).reshape(X.shape)
        m = maps.setdefault(key, np.zeros((n, n), np.float32))
        m[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1] += L.astype(np.float32)

    def thickness(x, y):
        """{material: thickness crossed [m]} at (x, y) (for images: read once, combined at each wavelength)."""
        jx = np.clip(np.rint((np.asarray(x) + MAP_HALF) / MAP_STEP).astype(np.int64), 0, n - 1)
        jy = np.clip(np.rint((np.asarray(y) + MAP_HALF) / MAP_STEP).astype(np.int64), 0, n - 1)
        inside = (np.abs(x) <= MAP_HALF) & (np.abs(y) <= MAP_HALF)
        return {key: m[jy, jx] * inside for key, m in maps.items()}

    def T(x, y, lam):
        jx = np.clip(np.rint((np.asarray(x) + MAP_HALF) / MAP_STEP).astype(np.int64), 0, n - 1)
        jy = np.clip(np.rint((np.asarray(y) + MAP_HALF) / MAP_STEP).astype(np.int64), 0, n - 1)
        inside = (np.abs(x) <= MAP_HALF) & (np.abs(y) <= MAP_HALF)
        mu = np.zeros(len(x))
        for key, m in maps.items():
            L = m[jy, jx] * inside
            k = L > 0
            mu[k] += np.interp(lam[k], lam_grid, sigs[key]) * L[k]
        return np.exp(-mu)
    T.thickness = thickness
    T.sigma = lambda key, lam: np.interp(lam, lam_grid, sigs[key])
    return T


# --------------------------------------------------------------------------- drawing counts
class HybridModel:
    """Open beam of one configuration (upstream file, D, diffuser): S, a(λ), f(x, y). Built once, then reused."""

    def __init__(self, front_mcpl, D, events_ob, field, cache_dir, lam=(1.0, 9.0)):
        from scipy.interpolate import splev
        self.field, self.D = field, D
        self.S = pinhole_spectrum(front_mcpl, D, cache_dir)
        name = os.path.join(cache_dir, f"model_D{D:.3f}_{os.path.basename(os.path.dirname(events_ob))}.npz")
        if os.path.isfile(name):
            z = np.load(name, allow_pickle=True)
            self.c_a, self.c_f, self.diag = tuple(z["c_a"]), z["c_f"], z["diag"].item()
        else:
            self.c_a, da = fit_acceptance(self.S, events_ob, field, lam_edges=np.arange(lam[0], lam[1] + 1e-4, 0.1))
            self.c_f, df = fit_profile(events_ob, field)
            self.diag = dict(acceptance=da, profile=df)
            np.savez(name, c_a=np.array(self.c_a, dtype=object), c_f=self.c_f, diag=np.array(self.diag, dtype=object))
        lamS = self.S["lam"].astype(float)
        lo, hi = self.diag["acceptance"]["lc"][[0, -1]]
        self.r = self.S["w"] * np.exp(splev(np.clip(lamS, lo, hi), self.c_a))   # intensity (n/s) in the field

    def rate(self, lam_abs=8.0):
        """Expected count rate of the open beam in the field of view [counts/s] (detector efficiency included)."""
        from odin_nexus import efficiency
        return float((self.r * efficiency(self.S["lam"].astype(float), lam_abs)).sum())

    def image(self, t_exp, transmission=None, bins=128, lam_abs=8.0, blur_m=None, beam_factor=1.0, dark_per_s=None,
              n_lam=40, rng=None):
        """Image of an integrating camera (scintillator + sCMOS camera, as for white-beam imaging): no neutron is
        drawn one by one (2·10⁷ per second in a white beam); each pixel gets the expected number of neutrons, the
        spectrum S(λ) times the transmission of the sample at that pixel, summed over λ, then the L/D and scintillator
        blurs and Poisson noise, plus a dark signal of the camera (dark_per_s counts per pixel and second). Same
        model as counts() (spectrum, acceptance, profile, blurs): the same mean image, without the time of flight.
        Returns a bins × bins array (rows: y, columns: x) over the field."""
        from odin_nexus import efficiency
        from scipy.ndimage import gaussian_filter
        rng = rng or np.random.default_rng()
        if blur_m is None:            # the scintillator: thick and bright (128 pixels), or thin for high resolution
            blur_m = 0.1e-3 if bins <= 128 else 0.02e-3
        if dark_per_s is None:
            dark_per_s = 2.0 * (128 / bins) ** 2
        x0, x1, y0, y1 = self.field
        lamS = self.S["lam"].astype(float)
        edges = np.linspace(lamS.min(), lamS.max() + 1e-9, n_lam + 1)
        wl = np.histogram(lamS, edges, weights=self.r * efficiency(lamS, lam_abs))[0]
        lc = 0.5 * (edges[1:] + edges[:-1])
        k = wl > 0
        wl, lc = wl[k], lc[k]
        xc = x0 + (np.arange(bins) + 0.5) * (x1 - x0) / bins
        yc = y0 + (np.arange(bins) + 0.5) * (y1 - y0) / bins
        X, Y = (a.ravel() for a in np.meshgrid(xc, yc))
        f = profile(self.c_f, X, Y)
        f = f / f.sum()                                              # share of the beam in each pixel
        Tm = np.ones(X.size)
        if transmission is not None and hasattr(transmission, "thickness"):     # a sample on thickness maps
            L = transmission.thickness(X, Y)
            Tm = np.zeros(X.size)
            for lk, wk in zip(lc, wl):
                mu = np.zeros(X.size)
                for key, Lm in L.items():
                    mu += float(transmission.sigma(key, lk)) * Lm
                Tm += wk * np.exp(-mu)
            Tm /= wl.sum()
        elif transmission is not None:
            Tm = sum(wk * transmission(X, Y, np.full(X.size, lk)) for lk, wk in zip(lc, wl)) / wl.sum()
        mean = (wl.sum() * t_exp * beam_factor * f * Tm).reshape(bins, bins)
        L = tw.Z_SAMPLE - tw.Z_PINHOLE
        sigma = np.hypot(tw.DET_DIST * self.D / L / np.sqrt(12), blur_m) / ((x1 - x0) / bins)     # [pixels]
        mean = gaussian_filter(mean, sigma, mode="nearest")
        return rng.poisson(mean) + rng.poisson(dark_per_s * t_exp, mean.shape)

    def tof_image(self, t_exp, transmission=None, lam_edges=None, bins=128, rel_sigma=0.002, lam_abs=8.0,
                  beam_factor=1.0, rng=None, blur_m=0.055e-3):
        """Counts of the Timepix3 camera sorted by wavelength, without drawing the neutrons one by one (the event mode,
        counts(), is limited to a few 10⁷ neutrons per file): for each pixel and wavelength bin, the expected number,
        spectrum × transmission, smoothed in λ by the resolution of the chopper mode (a Gaussian of standard deviation
        rel_sigma · λ) and in space by the L/D blur, then Poisson noise. Returns (n_lam, bins, bins), rows y."""
        from odin_nexus import efficiency
        from scipy.ndimage import gaussian_filter, gaussian_filter1d
        rng = rng or np.random.default_rng()
        lam_edges = np.linspace(2.7, 4.5, 181) if lam_edges is None else np.asarray(lam_edges, float)
        x0, x1, y0, y1 = self.field
        # a fine grid of λ (4 points per bin), wide enough for the smoothing
        step = float(np.min(np.diff(lam_edges))) / 4
        pad = 5 * rel_sigma * lam_edges[-1]
        fine = np.arange(lam_edges[0] - pad, lam_edges[-1] + pad + step, step)
        lamS = self.S["lam"].astype(float)
        wl = np.histogram(lamS, np.r_[fine - step / 2, fine[-1] + step / 2],
                          weights=self.r * efficiency(lamS, lam_abs))[0]
        xc = x0 + (np.arange(bins) + 0.5) * (x1 - x0) / bins
        yc = y0 + (np.arange(bins) + 0.5) * (y1 - y0) / bins
        X, Y = (a.ravel() for a in np.meshgrid(xc, yc))
        f = profile(self.c_f, X, Y)
        f = f / f.sum()
        if transmission is None:
            Tm = np.ones((X.size, fine.size))
        elif hasattr(transmission, "thickness"):                 # thickness maps: (pixels × materials) @ (materials × λ)
            L = transmission.thickness(X, Y)
            keys = list(L)
            Lm = np.array([L[k] for k in keys]).T
            Sm = np.array([transmission.sigma(k, fine) for k in keys])
            Tm = np.exp(-(Lm @ Sm)) if keys else np.ones((X.size, fine.size))
        else:
            Tm = np.empty((X.size, fine.size))
            for j in range(0, fine.size, 64):
                lj = fine[j:j + 64]
                Tm[:, j:j + 64] = transmission(np.repeat(X, lj.size), np.repeat(Y, lj.size),
                                               np.tile(lj, X.size)).reshape(X.size, lj.size)
        mean = (t_exp * beam_factor) * f[:, None] * wl[None, :] * Tm                  # (pixels, fine λ)
        # resolution: a Gaussian in λ whose width grows with λ (applied with the width at the middle of the range)
        sig_bins = rel_sigma * 0.5 * (lam_edges[0] + lam_edges[-1]) / step
        mean = gaussian_filter1d(mean, sig_bins, axis=1, mode="nearest")
        idx = np.digitize(fine, lam_edges) - 1
        out = np.zeros((lam_edges.size - 1, X.size))
        for k in range(lam_edges.size - 1):
            out[k] = mean[:, idx == k].sum(axis=1)
        out = out.reshape(-1, bins, bins)
        Lp = tw.Z_SAMPLE - tw.Z_PINHOLE
        sigma = np.hypot(tw.DET_DIST * self.D / Lp / np.sqrt(12), blur_m) / ((x1 - x0) / bins)
        out = np.array([gaussian_filter(o, sigma, mode="nearest") for o in out])
        return rng.poisson(out)

    def counts(self, t_exp, transmission=None, lam_abs=8.0, blur_m=0.1e-3, background=0.05, background_pixel=1e-3,
               beam_factor=1.0, rng=None):
        """Counts measured during t_exp: same output as odin_nexus.sample_counts (x, y, t, lam).

        transmission(x, y, lam) -> T: attenuation by the sample at (x, y) in the sample plane (None: open beam).
        Then the L/D geometric blur (the neutron starts from a point of the pinhole, drawn uniformly over D × D, and
        flies DET_DIST further to the detector), then the scintillator blur.
        """
        from odin_nexus import efficiency, _background
        rng = rng or np.random.default_rng()
        lamS = self.S["lam"].astype(float)
        m = self.r * efficiency(lamS, lam_abs) * t_exp * beam_factor
        cum = np.cumsum(m)
        n = rng.poisson(cum[-1])
        idx = np.searchsorted(cum, rng.uniform(0, cum[-1], n))
        lam, t = lamS[idx], self.S["t"][idx]
        # Position: profile f(x, y), by rejection
        x0, x1, y0, y1 = self.field
        fmax = 1.05 * max(profile(self.c_f, xx, yy) for xx in (x0, x1, 0) for yy in (y0, y1, 0))
        x = rng.uniform(x0, x1, n); y = rng.uniform(y0, y1, n)
        rej = rng.uniform(0, fmax, n) > profile(self.c_f, x, y)
        while rej.any():
            k = rej.sum()
            x[rej] = rng.uniform(x0, x1, k); y[rej] = rng.uniform(y0, y1, k)
            rej[rej] = rng.uniform(0, fmax, k) > profile(self.c_f, x[rej], y[rej])
        if transmission is not None:
            keep = rng.uniform(0, 1, n) < transmission(x, y, lam)
            x, y, t, lam = x[keep], y[keep], t[keep], lam[keep]
        n = len(x)
        L = tw.Z_SAMPLE - tw.Z_PINHOLE
        xs, ys = rng.uniform(-self.D / 2, self.D / 2, n), rng.uniform(-self.D / 2, self.D / 2, n)
        out = dict(x=(x + tw.DET_DIST * (x - xs) / L + rng.normal(0, blur_m, n)).astype(np.float32),
                   y=(y + tw.DET_DIST * (y - ys) / L + rng.normal(0, blur_m, n)).astype(np.float32),
                   t=t, lam=lam.astype(np.float32))
        if background > 0:
            out = _background(out, t_exp, self.field, background, background_pixel, rng)
        out.update(mc_factor=1.0, n_mcstas=len(lamS))
        return out
