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
def pinhole_spectrum(front_mcpl, D, cache_dir, z_det=Z_DET):
    """S: upstream neutrons passing the square pinhole D (at Z_PINHOLE), with t at the detector (z_det: moderator ->
    detector [m], measuring position 1 by default). Cached .npz."""
    tag = "" if abs(z_det - Z_DET) < 1e-9 else f"_z{z_det:.3f}"
    name = os.path.join(cache_dir, f"S_D{D:.3f}{tag}.npz")
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
    t_det = fr["t"][ok] + (z_det - fr["z"][ok]) / (v * fr["uz"][ok])
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


def fit_profile_map(events_ob, field, n=24, smooth=1.0):
    """f(x, y) for a large field (the full field of the camera box, 10 or 20 cm), where a degree-2 polynomial is too
    stiff: the McStas intensity on an n x n grid, smoothed by a Gaussian of `smooth` cells, normalized to a mean of 1;
    read by bilinear interpolation (profile). Returns (("map", x0, x1, y0, y1, values), diagnostics)."""
    from scipy.ndimage import gaussian_filter
    x0, x1, y0, y1 = field
    xe, ye = np.linspace(x0, x1, n + 1), np.linspace(y0, y1, n + 1)
    h = np.zeros((n, n)); v = np.zeros((n, n))
    for e in tw.iter_mcpl(events_ob, light=True):
        w = e["w"].astype(float)
        a, _, _ = np.histogram2d(e["y"], e["x"], [ye, xe], weights=w)           # rows y, columns x
        b, _, _ = np.histogram2d(e["y"], e["x"], [ye, xe], weights=w * w)
        h += a; v += b
    m = gaussian_filter(h, smooth, mode="nearest")
    m = m / m.mean()
    model = m * h.mean()
    resid = (h - model) / np.sqrt(np.where(v > 0, v, np.inf))
    return (("map", x0, x1, y0, y1, m.astype(np.float64)),
            dict(chi2n=float(np.mean(resid ** 2)), variation=float(m.max() / m.min() - 1), kind="map", n=n))


def profile(c, x, y):
    if isinstance(c, tuple) and c and c[0] == "map":          # a smoothed map (fit_profile_map)
        _, x0, x1, y0, y1, m = c
        n = m.shape[0]
        fx = np.clip((np.asarray(x, float) - x0) / (x1 - x0) * n - 0.5, 0, n - 1)
        fy = np.clip((np.asarray(y, float) - y0) / (y1 - y0) * n - 0.5, 0, n - 1)
        i, j = np.minimum(fx.astype(int), n - 2), np.minimum(fy.astype(int), n - 2)
        ax, ay = fx - i, fy - j
        return ((1 - ax) * (1 - ay) * m[j, i] + ax * (1 - ay) * m[j, i + 1] + (1 - ax) * ay * m[j + 1, i]
                + ax * ay * m[j + 1, i + 1])
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
MAP_CACHE = f"{odin_paths.RUN_ROOT}/hybrid/maps"     # thickness maps of large samples, by sample and position
MAP_CACHE_MIN = 200        # volumes: below, computing the maps is faster than reading them
MAP_CACHE_FILES = 600      # files kept (a tomography: 60 angles; the oldest go first)
MAP_CACHE_VERSION = 1      # to change when the computation of the maps changes
MAP_POINTS = 2000          # largest number of grid steps across a map (memory: 4 bytes x 2001^2 per material)


def map_grid(field_half=None):
    """(half-width, step) [m] of the thickness maps for a field of view of half-width field_half: the 14 mm field keeps
    MAP_HALF and MAP_STEP; a larger field (the full field of the camera box, 10 or 20 cm) a grid of MAP_POINTS steps
    (50 or 100 µm, below its pixels: 0.2 mm at the finest)."""
    if field_half is None:
        return MAP_HALF, MAP_STEP
    half = max(MAP_HALF, 1.02 * field_half)
    return half, max(MAP_STEP, 2 * half / MAP_POINTS)


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


def volumes_transmission(volumes, stage_x, stage_rot, lam_grid=np.linspace(0.3, 20.0, 4000), strains=None,
                         field_half=None):
    """Function T(x, y, λ) for a sample made of volumes [(NCrystal cfg, center (m), dims (m)[, shape[, host cfg]]), ...]
    (boxes, spheres, vertical cylinders; an inclusion names the material of the volume around it, which it replaces),
    centers given with
    respect to the rotation-stage axis; the stage is translated by stage_x then rotated by stage_rot (degrees) about
    the vertical axis. Σ_tot(λ) is interpolated on a grid covering all chopper modes (NCrystal called once).
    strains: lattice strain ε of each volume along the beam (a sample under load, sample_library.odin_strain_per_kN):
    every lattice spacing seen by the beam becomes d (1 + ε), so every Bragg edge (λ = 2d) moves to λ (1 + ε):
    Σ_tot(λ) of the strained volume = Σ_tot(λ / (1 + ε)) of the unstrained material. (The smooth parts of Σ_tot,
    absorption and inelastic scattering, move with it: an error of ε, about 10⁻³, on a slowly varying term.)
    A sample described as a samplecraft scene (sample_library.SceneSample): scene_transmission.
    field_half: half-width of the field of view [m] (None: the 14 mm field): sets the grid of the thickness maps."""
    if hasattr(volumes, "scene"):
        if strains is not None and any(strains):
            raise ValueError("a sample described as a scene cannot be strained (load frame) yet")
        return scene_transmission(volumes, stage_x, stage_rot, lam_grid, field_half=field_half)
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

    if len(vols) > 20:                                                     # many volumes: on maps
        return _mapped_transmission(volumes, vols, stage_rot, lam_grid, epss, grid=map_grid(field_half))

    def T(x, y, lam):
        mu = np.zeros(len(x))
        for sig, center, dims, shape in vols:
            L = _path(shape, x, y, center, dims, stage_rot)
            k = L > 0
            mu[k] += np.interp(lam[k], lam_grid, sig) * L[k]
        return np.exp(-mu)
    return T


def _mapped_transmission(volumes, vols, stage_rot, lam_grid, epss=None, grid=(MAP_HALF, MAP_STEP)):
    """A sample made of many volumes (a rock: hundreds of grains): the thickness crossed in each material is computed
    once, on a grid of MAP_STEP over the field (each volume only within its own extent), then read for each neutron
    or pixel; T = exp(−Σ_m Σ_m(λ) L_m(x, y)). The volumes of the same material (and host, and strain) share one
    map."""
    half, step = grid
    n = int(round(2 * half / step)) + 1
    g = -half + np.arange(n) * step
    maps, sigs = {}, {}
    keys = []
    for k, (v, (sig, center, dims, shape)) in enumerate(zip(volumes, vols)):
        key = (v[0], v[4] if len(v) > 4 else None, round(float(epss[k]), 9) if epss else 0.0)
        sigs[key] = sig
        keys.append(key)
    cached = _map_cache_file(vols, keys, grid) if len(vols) >= MAP_CACHE_MIN else None
    if cached and os.path.exists(cached):
        try:
            maps = _read_maps(cached, n)
        except Exception:                              # a file being written by another kernel, or damaged
            maps = {}
    if not maps:
        maps = _compute_maps(vols, keys, g, n, stage_rot, step)
        if cached:
            _write_maps(cached, maps)
    return _transmission_from_maps(maps, sigs, n, lam_grid, grid)


def scene_transmission(sample, stage_x, stage_rot, lam_grid=np.linspace(0.3, 20.0, 4000), field_half=None):
    """T(x, y, λ) of a samplecraft scene: rays along the beam (lab z) through the grid of the thickness maps, taken
    into the frame of the sample (stage translated by stage_x [m], turned by stage_rot [deg] about y); the exact path
    length of each (material, material around) from the scene (mm), Σ_material − Σ_around applied to it. Maps kept
    on disk per sample file and position (as for the other samples)."""
    scene = sample.scene
    cfg = scene.cfg()
    t = np.radians(stage_rot)
    S = np.array([[np.cos(t), 0, np.sin(t)], [0, 1, 0], [-np.sin(t), 0, np.cos(t)]])   # sample -> lab
    if sum(1 for _ in scene.walk()) <= 20:
        # a few bodies: the exact path of each neutron (as volumes_transmission does for few volumes)
        sigs = {}

        def sig(key):
            if key not in sigs:
                sg = sigma_tot(key[0], lam_grid)
                sigs[key] = sg - sigma_tot(key[1], lam_grid) if key[1] is not None else sg
            return sigs[key]

        def T(x, y, lam):
            o = np.c_[np.asarray(x) * 1e3 - stage_x * 1e3, np.asarray(y) * 1e3, np.full(len(x), -1e3)] @ S
            d = np.tile(np.array([0.0, 0.0, 1.0]) @ S, (len(o), 1))
            mu = np.zeros(len(o))
            for (m, around), L in scene.path_lengths(o, d).items():
                L = np.asarray(L, float) * 1e-3
                k = L > 0
                key = (cfg[m], cfg[around] if around is not None else None)
                mu[k] += np.interp(lam[k], lam_grid, sig(key)) * L[k]
            return np.exp(-mu)
        return T
    half, step = grid = map_grid(field_half)
    n = int(round(2 * half / step)) + 1
    g = -half + np.arange(n) * step
    import hashlib
    name = hashlib.sha1(repr((MAP_CACHE_VERSION, "scene", sample.key, round(float(stage_x), 9),
                              round(float(stage_rot), 9), step, half)).encode()).hexdigest()[:24]
    cached = os.path.join(MAP_CACHE, f"{name}.npz") if not sample.key.startswith("mem:") else None
    maps = {}
    if cached and os.path.exists(cached):
        try:
            maps = _read_maps(cached, n)
        except Exception:
            maps = {}
    if not maps:
        X, Y = np.meshgrid(g * 1e3, g * 1e3)                       # mm
        o_lab = np.c_[X.ravel() - stage_x * 1e3, Y.ravel(), np.full(X.size, -1e3)]
        o = o_lab @ S                                              # lab -> sample: S^T p (row vectors)
        d = np.tile(np.array([0.0, 0.0, 1.0]) @ S, (len(o), 1))
        for (m, around), L in scene.path_lengths(o, d).items():
            key = (cfg[m], cfg[around] if around is not None else None, 0.0)
            arr = np.asarray(L, float).reshape(n, n) * 1e-3          # m
            if key in maps:
                maps[key] += arr.astype(np.float32)
            else:
                maps[key] = arr.astype(np.float32)
        if cached:
            _write_maps(cached, maps)
    sigs = {}
    for key in maps:
        sig = sigma_tot(key[0], lam_grid)
        if key[1] is not None:
            sig = sig - sigma_tot(key[1], lam_grid)
        sigs[key] = sig
    return _transmission_from_maps(maps, sigs, n, lam_grid, grid)


def _map_cache_file(vols, keys, grid=(MAP_HALF, MAP_STEP)):
    """The file of the thickness maps of this sample in this position (a class measures the same rock at the same
    angles: the first student computes them, the others read them)."""
    import hashlib
    h = hashlib.sha1(repr((MAP_CACHE_VERSION, grid[1], grid[0],
                           [(key, tuple(np.round(np.asarray(v[1], float), 12)), tuple(np.ravel(v[2]).tolist()), v[3])
                            for key, v in zip(keys, vols)])).encode()).hexdigest()[:24]
    return os.path.join(MAP_CACHE, f"{h}.npz")


def _read_maps(path, n):
    import json
    with np.load(path) as f:
        meta = json.loads(str(f["meta"]))
        maps = {}
        for i, (key, (y0, y1, x0, x1)) in enumerate(meta):
            m = np.zeros((n, n), np.float32)
            m[y0:y1, x0:x1] = f[f"m{i}"]
            maps[tuple(key)] = m
    return maps


def _write_maps(path, maps):
    """Each map cropped to where it is not zero, compressed; written to a temporary file then renamed (other kernels
    may read it at the same time). The oldest files go when there are more than MAP_CACHE_FILES."""
    import json
    os.makedirs(MAP_CACHE, exist_ok=True)
    meta, arrays = [], {}
    for i, (key, m) in enumerate(maps.items()):
        ys, xs = np.nonzero(m.any(axis=1))[0], np.nonzero(m.any(axis=0))[0]
        box = (int(ys[0]), int(ys[-1]) + 1, int(xs[0]), int(xs[-1]) + 1) if len(ys) else (0, 0, 0, 0)
        meta.append((list(key), box))
        arrays[f"m{i}"] = m[box[0]:box[1], box[2]:box[3]]
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "wb") as fh:
            np.savez_compressed(fh, meta=np.array(json.dumps(meta)), **arrays)
        os.replace(tmp, path)
        files = sorted((os.path.join(MAP_CACHE, f) for f in os.listdir(MAP_CACHE) if f.endswith(".npz")),
                       key=os.path.getmtime)
        for f in files[:max(0, len(files) - MAP_CACHE_FILES)]:
            os.remove(f)
    except OSError:
        pass                                           # no cache: computed again next time


def _compute_maps(vols, keys, g, n, stage_rot, step=MAP_STEP):
    """{key: thickness map [m]} of the volumes of each material (and host, strain)."""
    maps = {}
    for k, (sig, center, dims, shape) in enumerate(vols):
        key = keys[k]
        r = 0.5 * float(np.sqrt(dims[0] ** 2 + dims[2] ** 2)) if shape in ("box", "ellipsoid") else 0.5 * dims[0]
        hy = 0.5 * (dims[1] if shape != "sphere" else dims[0])
        ix = np.where((g >= center[0] - r - step) & (g <= center[0] + r + step))[0]
        iy = np.where((g >= center[1] - hy - step) & (g <= center[1] + hy + step))[0]
        if not len(ix) or not len(iy):
            continue
        X, Y = np.meshgrid(g[ix], g[iy])
        L = _path(shape, X.ravel(), Y.ravel(), center, dims, stage_rot).reshape(X.shape)
        m = maps.setdefault(key, np.zeros((n, n), np.float32))
        m[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1] += L.astype(np.float32)
    return maps


def _transmission_from_maps(maps, sigs, n, lam_grid, grid=(MAP_HALF, MAP_STEP)):
    """T(x, y, λ) = exp(−Σ_m Σ_m(λ) L_m(x, y)), with T.thickness and T.sigma (images: maps read once per pixel)."""
    MAP_HALF, MAP_STEP = grid           # noqa: N806  (the grid of these maps; the module constants: the 14 mm field)

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

    def __init__(self, front_mcpl, D, events_ob, field, cache_dir, lam=(1.0, 9.0), z_sample=tw.Z_SAMPLE, tag=""):
        """z_sample: moderator -> sample [m] (the measuring position, odin_mcstas.POSITIONS); tag: the setting of
        position and lens (odin_virtual.config_tag, '' for position 1 with the zoom lens), in the name of the cache."""
        from scipy.interpolate import splev
        self.field, self.D = field, D
        self.z_sample = z_sample
        self.L = z_sample - tw.Z_PINHOLE                 # pinhole -> sample: the L of L/D
        self.det_dist = tw.DET_DIST           # sample -> detector [m]: the blur l·D/L and the flight time (set per count)
        self.S = pinhole_spectrum(front_mcpl, D, cache_dir, z_det=z_sample + tw.DET_DIST)
        name = os.path.join(cache_dir, f"model_D{D:.3f}_{os.path.basename(os.path.dirname(events_ob))}{tag}.npz")
        # the 14 mm field: a degree-2 polynomial; a larger field (more than 2 cm): a smoothed map of the beam
        large = (field[1] - field[0]) > 0.02
        if os.path.isfile(name):
            z = np.load(name, allow_pickle=True)
            self.c_a, self.c_f, self.diag = tuple(z["c_a"]), z["c_f"], z["diag"].item()
            if large:
                self.c_f = tuple(self.c_f.tolist())
        else:
            self.c_a, da = fit_acceptance(self.S, events_ob, field, lam_edges=np.arange(lam[0], lam[1] + 1e-4, 0.1))
            self.c_f, df = (fit_profile_map if large else fit_profile)(events_ob, field)
            self.diag = dict(acceptance=da, profile=df)
            c_f = np.array(self.c_f, dtype=object) if large else self.c_f
            np.savez(name, c_a=np.array(self.c_a, dtype=object), c_f=c_f, diag=np.array(self.diag, dtype=object))
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
        f = np.clip(profile(self.c_f, X, Y), 0, None)     # (a polynomial: never below zero at the corners)
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
        L = self.L
        sigma = np.hypot(self.det_dist * self.D / L / np.sqrt(12), blur_m) / ((x1 - x0) / bins)     # [pixels]
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
        f = np.clip(profile(self.c_f, X, Y), 0, None)     # (a polynomial: never below zero at the corners)
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
        Lp = self.L
        sigma = np.hypot(self.det_dist * self.D / Lp / np.sqrt(12), blur_m) / ((x1 - x0) / bins)
        out = np.array([gaussian_filter(o, sigma, mode="nearest") for o in out])
        return rng.poisson(out)

    def counts(self, t_exp, transmission=None, lam_abs=8.0, blur_m=0.1e-3, background=0.05, background_pixel=1e-3,
               beam_factor=1.0, rng=None):
        """Counts measured during t_exp: same output as odin_nexus.sample_counts (x, y, t, lam).

        transmission(x, y, lam) -> T: attenuation by the sample at (x, y) in the sample plane (None: open beam).
        Then the L/D geometric blur (the neutron starts from a point of the pinhole, drawn uniformly over D × D, and
        flies det_dist further to the detector), then the scintillator blur. The times of S are at DET_DIST: moved to
        det_dist.
        """
        from odin_nexus import efficiency, _background
        rng = rng or np.random.default_rng()
        lamS = self.S["lam"].astype(float)
        m = self.r * efficiency(lamS, lam_abs) * t_exp * beam_factor
        cum = np.cumsum(m)
        n = rng.poisson(cum[-1])
        idx = np.searchsorted(cum, rng.uniform(0, cum[-1], n))
        lam, t = lamS[idx], self.S["t"][idx]
        if self.det_dist != tw.DET_DIST:                          # the detector moved: shorter or longer flight
            t = t + (self.det_dist - tw.DET_DIST) * lam / H_OVER_M
        # Position: profile f(x, y), by rejection
        x0, x1, y0, y1 = self.field
        fmax = (1.05 * float(self.c_f[5].max()) if isinstance(self.c_f, tuple) else
                1.05 * max(profile(self.c_f, xx, yy) for xx in (x0, x1, 0) for yy in (y0, y1, 0)))
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
        L = self.L
        xs, ys = rng.uniform(-self.D / 2, self.D / 2, n), rng.uniform(-self.D / 2, self.D / 2, n)
        out = dict(x=(x + self.det_dist * (x - xs) / L + rng.normal(0, blur_m, n)).astype(np.float32),
                   y=(y + self.det_dist * (y - ys) / L + rng.normal(0, blur_m, n)).astype(np.float32),
                   t=t, lam=lam.astype(np.float32))
        if background > 0:
            out = _background(out, t_exp, self.field, background, background_pixel, rng)
        out.update(mc_factor=1.0, n_mcstas=len(lamS))
        return out
