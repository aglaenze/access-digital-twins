"""Irregular shapes of natural samples (rocks, meteorites) for the hybrid model of ODIN and the drawings.

Two shapes, both defined in the frame of the sample (x across the beam at 0°, y vertical, z along the beam at 0°),
lengths in meters, and seen by the beam after a rotation of the stage by θ about y (the convention of odin_hybrid: a
point (x, z) of the sample appears at x cos θ + z sin θ across the beam and −x sin θ + z cos θ along it):

* "blob": a grain or a clast, an ellipsoid of full axes (sx, sy, sz) turned in 3D (angles about z, then x, then y,
  in degrees), its surface made lumpy by a smooth random function of the direction: radius × (1 + w f(u)), with
  |f| ≤ 1 and w the "wobble" (0: a plain ellipsoid). The lumps are set by a seed: the same seed, the same grain.
      dims = (sx, sy, sz, az, ax, ay, w, seed)
* "slab": a sawn section of a rock, as a piece cut for imaging: two nearly flat faces (the cuts, z = ± t/2, slightly
  wavy), irregular broken sides, rounded edges, and one chipped corner.
      dims = (w, h, t, seed)

Path lengths along the beam: the slab exactly (a polygon per row of the map), a blob by sampling along the ray
(20 to 100 steps, a fifth of its smallest semi-axis at most) with the surface found by interpolation. Inside tests: inside(shape, dims, points).
"""
import numpy as np



# --------------------------------------------------------------------------- blob
def _rot(az, ax, ay):
    """Rotation matrix (sample frame <- grain frame): about z by az, then x by ax, then y by ay (degrees)."""
    a, b, c = np.radians([az, ax, ay])
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    Ry = np.array([[np.cos(c), 0, np.sin(c)], [0, 1, 0], [-np.sin(c), 0, np.cos(c)]])
    return Ry @ Rx @ Rz


_LUMPS = {}


def _lumps(seed):
    """Six plane waves on the unit sphere (random directions, frequencies 1.5 to 3.5, phases), weights summing to 1."""
    seed = int(seed)
    if seed not in _LUMPS:
        rng = np.random.default_rng(seed)
        k = rng.normal(size=(6, 3))
        k = k / np.linalg.norm(k, axis=1)[:, None] * rng.uniform(1.5, 3.5, (6, 1))
        a = rng.uniform(0.5, 1.0, 6)
        _LUMPS[seed] = (k, rng.uniform(0, 2 * np.pi, 6), a / a.sum())
    return _LUMPS[seed]


def blob_radius_factor(u, wobble, seed):
    """1 + w f(u) for unit vectors u [n, 3] of the grain frame."""
    if not wobble:
        return np.ones(len(u))
    k, ph, a = _lumps(seed)
    return 1.0 + wobble * (np.sin(u @ k.T + ph) * a).sum(axis=1)


def blob_bound(dims):
    """Radius of a sphere around the blob [m] (its lumps reach at most 1 + w times the ellipsoid)."""
    return 0.5 * max(dims[:3]) * (1 + abs(dims[6]))


def blob_volume(dims, n=4000):
    """Volume of a blob [m³]: the ellipsoid times the mean of (1 + w f)³ over directions (uniform in the frame of
    the unit sphere, fixed sample of directions)."""
    v = np.pi / 6 * float(np.prod(dims[:3]))
    if not dims[6]:
        return v
    u = np.random.default_rng(0).normal(size=(n, 3))
    u /= np.linalg.norm(u, axis=1)[:, None]
    return v * float(np.mean(blob_radius_factor(u, dims[6], dims[7]) ** 3))


def _inside_blob_body(q, dims):
    """q: points [n, 3] in the frame of the grain (center at 0)."""
    semi = 0.5 * np.asarray(dims[:3], float)
    n = q / semi
    rho = np.sqrt((n * n).sum(axis=1))
    u = n / np.where(rho > 0, rho, 1)[:, None]
    return rho < blob_radius_factor(u, dims[6], dims[7])


def blob_path_length(x, y, center, dims, stage_rot, sampled=False):
    """Path length [m] through a blob (center in the lab frame, after the stage) for rays along z at (x, y), by the
    method of blobs_path_length. sampled=True (a check): the function g = ρ − (1 + w f) (negative inside) sampled
    along each ray, its zeros found by linear interpolation between samples (a few µm)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    R = _stage(stage_rot) @ _rot(*dims[3:6])           # grain -> lab
    r = blob_bound(dims)
    out = np.zeros(x.shape)
    near = (x - center[0]) ** 2 + (y - center[1]) ** 2 <= r * r
    if not near.any():
        return out
    if not dims[6] or not sampled:                     # the method of blobs_path_length (exact without lumps)
        out[near] = blobs_path_length(x[near], y[near], np.zeros(int(near.sum()), np.int64),
                                      np.asarray(center, float)[None], [dims], stage_rot)
        return out
    semi_min = 0.5 * min(dims[:3])
    n = int(np.clip(np.ceil(2 * r / (semi_min / 5)), 20, 100))
    zs = np.linspace(-r, r, n + 1)
    dz = zs[1] - zs[0]
    xi, yi = x[near] - center[0], y[near] - center[1]
    P = np.empty((xi.size, zs.size, 3))
    P[:, :, 0] = xi[:, None]
    P[:, :, 1] = yi[:, None]
    P[:, :, 2] = zs[None, :]
    q = P.reshape(-1, 3) @ R                           # lab -> grain: R^T p, as row vectors p R
    semi = 0.5 * np.asarray(dims[:3], float)
    nq = q / semi
    rho = np.sqrt((nq * nq).sum(axis=1))
    u = nq / np.where(rho > 0, rho, 1)[:, None]
    g = (rho - blob_radius_factor(u, dims[6], dims[7])).reshape(xi.size, zs.size)
    g0, g1 = g[:, :-1], g[:, 1:]
    frac = np.where((g0 < 0) & (g1 < 0), 1.0,
                    np.where(g0 < 0, g0 / np.where(g0 != g1, g0 - g1, 1),
                             np.where(g1 < 0, g1 / np.where(g0 != g1, g1 - g0, 1), 0.0)))
    out[near] = frac.sum(axis=1) * dz
    return out


def blobs_path_length(x, y, idx, centers, dims, stage_rot, iters=6, chunk=250_000):
    """Path lengths [m] through many blobs at once: ray k (along z at x[k], y[k]) through blob idx[k] (centers [B, 3]
    in the lab frame, after the stage; dims: B tuples). Along a ray, the point of the grain at depth t is
    u0 + t v in the frame where the ellipsoid is the unit sphere, so ρ² = a t² + b t + c. Without lumps the chord is
    exact (ρ = 1). With lumps (surface ρ = k(u)), the entry and the exit are each found by fixed-point iteration:
    solve ρ(t) = k for the current k, then take k at the point found (k varies slowly along the surface: a few
    iterations reach a fraction of a µm). A ray through a hollow of the surface (four crossings) counts only the
    outer two: a small error, on a few rays at the edge of a lump."""
    x = np.asarray(x, float); y = np.asarray(y, float); idx = np.asarray(idx, np.int64)
    out = np.zeros(x.shape)
    if not len(dims):
        return out
    S = _stage(stage_rot)
    D = np.asarray([tuple(d[:8]) for d in dims], float)
    semi = 0.5 * D[:, :3]
    R = np.einsum("ij,bjk->bik", S, np.array([_rot(*d[3:6]) for d in D]))       # grain -> lab
    N = R / semi[:, None, :]                            # lab point p (row) -> p @ N: the unit-sphere frame
    wob = D[:, 6]
    seeds = D[:, 7].astype(np.int64)
    lumpy = np.flatnonzero(wob != 0)
    K = np.zeros((len(D), 6, 3)); PH = np.zeros((len(D), 6)); A = np.zeros((len(D), 6))
    for b in lumpy:
        K[b], PH[b], A[b] = _lumps(seeds[b])
    for s in range(0, len(x), chunk):
        sl = slice(s, s + chunk)
        bi = idx[sl]
        dx = x[sl] - centers[bi, 0]
        dy = y[sl] - centers[bi, 1]
        u0 = dx[:, None] * N[bi, 0] + dy[:, None] * N[bi, 1]
        v = N[bi, 2]
        a = (v * v).sum(axis=1)
        b = 2 * (u0 * v).sum(axis=1)
        c = (u0 * u0).sum(axis=1)
        L = np.sqrt(np.clip(b * b - 4 * a * (c - 1), 0, None)) / a
        w = wob[bi]
        m = w != 0
        L[m & (b * b - 4 * a * (c - (1 + np.abs(w)) ** 2) < 0)] = 0.0          # misses even the largest lumps
        m &= b * b - 4 * a * (c - (1 + np.abs(w)) ** 2) >= 0
        if m.any():
            am, bm, cm, u0m, vm, wm = a[m], b[m], c[m], u0[m], v[m], w[m]
            Km, PHm, Am = K[bi[m]], PH[bi[m]], A[bi[m]]

            def kfac(t):
                q = u0m + t[:, None] * vm
                r = np.sqrt((q * q).sum(axis=1))
                q = q / np.where(r > 0, r, 1)[:, None]
                return 1.0 + wm * (np.sin(np.einsum("pi,pji->pj", q, Km) + PHm) * Am).sum(axis=1)

            k_in = k_out = kfac(-bm / (2 * am))         # start: k at the point of the ray nearest the center
            for _ in range(iters):
                d_in = bm * bm - 4 * am * (cm - k_in ** 2)
                d_out = bm * bm - 4 * am * (cm - k_out ** 2)
                t_in = (-bm - np.sqrt(np.clip(d_in, 0, None))) / (2 * am)
                t_out = (-bm + np.sqrt(np.clip(d_out, 0, None))) / (2 * am)
                k_in, k_out = 0.5 * (k_in + kfac(t_in)), 0.5 * (k_out + kfac(t_out))   # damped: no see-saw
            d_in = bm * bm - 4 * am * (cm - k_in ** 2)
            d_out = bm * bm - 4 * am * (cm - k_out ** 2)
            t_in = (-bm - np.sqrt(np.clip(d_in, 0, None))) / (2 * am)
            t_out = (-bm + np.sqrt(np.clip(d_out, 0, None))) / (2 * am)
            L[m] = np.where((d_in >= 0) & (d_out >= 0), np.clip(t_out - t_in, 0, None), 0.0)
        out[sl] = L
    return out


def _stage(theta_deg):
    """Sample -> lab for a stage turned by θ: (x, z) -> (x cos θ + z sin θ, −x sin θ + z cos θ)."""
    t = np.radians(theta_deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


# --------------------------------------------------------------------------- slab
NV_SIDE = 48               # points along each long edge of the cross-section polygon
NV_CORNER = 6              # points on each rounded corner


_SLABS = {}


def _slab_params(dims):
    key = tuple(float(d) for d in dims[:4])
    if key not in _SLABS:
        _SLABS[key] = _make_slab_params(dims)
    return _SLABS[key]


def _make_slab_params(dims):
    w, h, t, seed = dims[:4]
    rng = np.random.default_rng(int(seed))
    return dict(
        w=w, h=h, t=t,
        rc=min(0.3e-3, 0.25 * t),                                     # rounded vertical edges (x-z corners)
        rt=min(0.5e-3, 0.1 * h),                                      # rounded top and bottom edges
        side=[(rng.uniform(0.04, 0.09) * 1e-3, rng.uniform(2, 4) / h * 2e-3, rng.uniform(0, 6.3)) for _ in range(4)],
        face=[(rng.uniform(0.02, 0.05) * 1e-3, rng.uniform(1.2, 4.5) / w * 8e-3, rng.uniform(0, 6.3)) for _ in range(4)],
        top=[(rng.uniform(0.05, 0.12) * 1e-3, rng.uniform(1.5, 3.5) / w * 8e-3, rng.uniform(0, 6.3)) for _ in range(2)],
        chip=(rng.uniform(1.0, 1.6) * 1e-3, rng.uniform(0.6, 1.0) * 1e-3, rng.choice([-1, 1])),   # a broken corner
    )


def _wave(terms, s):
    return sum(a * np.sin(k * s + p) for a, k, p in terms)


def slab_rows(dims, ys):
    """Cross-section of the slab at heights ys (sample frame): (xl, xr, inset) per row, and the half-thickness
    function ht(x). xl, xr: the sides; inset: how much the rounded top/bottom edges shrink the row (nan: no slab)."""
    P = _slab_params(dims)
    ys = np.asarray(ys, float)
    s0, s1 = P["side"][:2], P["side"][2:]
    xl = -P["w"] / 2 + _wave(s0, ys)
    xr = P["w"] / 2 + _wave(s1, ys)
    ch, cw, sign = P["chip"]                         # chipped corner at the top, on one side
    d = ys - (P["h"] / 2 - ch)
    cut = np.clip(d / ch, 0, None) * cw
    if sign > 0:
        xr = xr - cut
    else:
        xl = xl + cut
    return xl, xr, P


def _top(P, x):
    return P["h"] / 2 + _wave(P["top"][:1], x) - 0.5 * P["top"][0][0]


def _bottom(P, x):
    return -P["h"] / 2 + _wave(P["top"][1:], x) + 0.5 * P["top"][1][0]


def slab_polygon(dims, y):
    """Cross-section (x, z) of the slab at height y, counter-clockwise [n, 2], or None above or below it."""
    xl, xr, P = slab_rows(dims, [y])
    xl, xr = float(xl[0]), float(xr[0])
    xs = np.linspace(xl, xr, NV_SIDE)
    # top and bottom: the rows near them shrink (rounded edges) from the local height of the top/bottom
    yt, yb = _top(P, xs), _bottom(P, xs)
    rt = P["rt"]
    dt = np.clip(y - (yt - rt), 0, None); db = np.clip((yb + rt) - y, 0, None)
    over = (y > yt) | (y < yb)
    inset = np.where(over, np.inf, rt - np.sqrt(np.clip(rt * rt - np.maximum(dt, db) ** 2, 0, None)))
    ht = P["t"] / 2 + _wave(P["face"], xs) - inset
    keep = ht > 1e-6
    if keep.sum() < 3:
        return None
    xs, ht = xs[keep], ht[keep]
    # rounded vertical edges: the ends of the faces bend over a radius rc
    rc = min(P["rc"], 0.45 * (xs[-1] - xs[0]), 0.9 * float(ht.min()))
    a = np.linspace(0, np.pi / 2, NV_CORNER)
    # right end: from the bottom face up to the top face
    right = np.r_[np.c_[xs[-1] - rc + rc * np.sin(a), -(ht[-1] - rc) - rc * np.cos(a)],
                  np.c_[xs[-1] - rc + rc * np.cos(a), (ht[-1] - rc) + rc * np.sin(a)]]
    left = np.r_[np.c_[xs[0] + rc - rc * np.sin(a), (ht[0] - rc) + rc * np.cos(a)],
                 np.c_[xs[0] + rc - rc * np.cos(a), -(ht[0] - rc) - rc * np.sin(a)]]
    inner = (xs > xs[0] + rc) & (xs < xs[-1] - rc)
    top = np.c_[xs[inner][::-1], ht[inner][::-1]]
    bottom = np.c_[xs[inner], -ht[inner]]
    return np.r_[bottom, right, top, left]


def slab_inside(dims, pts):
    """Which points [n, 3] (sample frame, relative to the center) are inside the slab: the same surfaces as
    slab_polygon (sides, wavy faces, rounded edges, broken corner), tested point by point."""
    pts = np.asarray(pts, float)
    x, y, z = pts[:, 0], pts[:, 1], np.abs(pts[:, 2])
    xl, xr, P = slab_rows(dims, y)
    yt, yb = _top(P, x), _bottom(P, x)
    rt = P["rt"]
    dt = np.clip(y - (yt - rt), 0, None); db = np.clip((yb + rt) - y, 0, None)
    inset = rt - np.sqrt(np.clip(rt * rt - np.maximum(dt, db) ** 2, 0, None))
    ht = P["t"] / 2 + _wave(P["face"], x) - inset
    ok = (y <= yt) & (y >= yb) & (x >= xl) & (x <= xr) & (z < ht)
    rc = np.minimum(P["rc"], np.minimum(0.45 * (xr - xl), 0.9 * np.clip(ht, 0, None)))
    for end, sgn in ((xr - rc, 1), (xl + rc, -1)):          # the rounded vertical edges
        m = (sgn * (x - end) > 0) & (z > ht - rc)
        ok &= ~m | ((x - end) ** 2 + (z - (ht - rc)) ** 2 < rc ** 2)
    return ok


def slab_bound(dims):
    return 0.5 * float(np.hypot(dims[0], dims[2])) + 0.3e-3, 0.5 * dims[1] + 0.2e-3


def _chord(poly, xq):
    """Length of the vertical (z) chords of a polygon (counter-clockwise, (x, z)) at abscissae xq: sum of the z of
    the edges going toward −x minus those going toward +x (exact, also for a non-convex polygon)."""
    a, b = poly[:, 0], poly[:, 1]
    c, d = np.roll(a, -1), np.roll(b, -1)
    ok = a != c
    a, b, c, d = a[ok], b[ok], c[ok], d[ok]
    lo, hi = np.minimum(a, c), np.maximum(a, c)
    X = xq[:, None]
    m = (X >= lo) & (X < hi)
    z = b + (d - b) * (X - a) / (c - a)
    return (np.where(m, z, 0.0) * np.where(c < a, 1.0, -1.0)).sum(axis=1)


def slab_path_length(x, y, center, dims, stage_rot):
    """Path length [m] through the slab for rays along z at (x, y) (lab frame; center already after the stage)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    out = np.zeros(x.shape)
    t = np.radians(stage_rot)
    c, s = np.cos(t), np.sin(t)
    ys, inv = np.unique(y, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    bounds = np.searchsorted(inv[order], np.arange(len(ys) + 1))
    for k, yv in enumerate(ys):
        poly = slab_polygon(dims, yv - center[1])
        if poly is None:
            continue
        lab = np.c_[poly[:, 0] * c + poly[:, 1] * s, -poly[:, 0] * s + poly[:, 1] * c]   # still counter-clockwise
        idx = order[bounds[k]:bounds[k + 1]]
        xq = x[idx] - center[0]
        m = (xq >= lab[:, 0].min()) & (xq <= lab[:, 0].max())
        out[idx[m]] = _chord(lab, xq[m])
    return out


# --------------------------------------------------------------------------- inside tests (sample frame)
def inside(shape, dims, pts):
    """Which points [n, 3] (sample frame, relative to the center of the volume, meters) are inside."""
    pts = np.asarray(pts, float)
    if shape == "blob":
        return _inside_blob_body(pts @ _rot(*dims[3:6]), dims)
    if shape == "slab":
        return slab_inside(dims, pts)
    raise ValueError(shape)
