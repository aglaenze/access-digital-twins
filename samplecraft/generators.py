"""Building a scene: components expanded, and the "fill" of each body run (generators of microstructures), all from
the seed of the scene (the same file gives the same sample).

A fill entry (in a body: fill: [...]) is one of

grains (default): bodies placed at random in the body, none overlapping, none touching its surface:
    material: name           or   use: <component>   (each grain a copy of a component, with its own inner parts)
    count: N                 or   fraction: f        (of the volume of the body)
    size_mm: [min, max]                              longest axis, uniform
      or size: {lognormal: {median_mm, sigma}, min_mm, max_mm}   or   size: {values_mm: [...]} (measured sizes)
      (for a component: scale: [min, max] or the same forms, times the component's own size)
    aspect: [[min, max], [min, max]]                 the two other axes / the longest (default [[0.45, 0.9], [0.5, 0.95]])
    grain: {type: blob, wobble: 0.1} | {type: ellipsoid} | {type: box} | {type: superellipsoid, exponent: 4}
    orientation: random | fixed | {axis: [x, y, z], spread_deg: s}   (texture: longest axis near `axis`)
    clusters: {count: n, spread_mm: s, group: g}     gathered around n random points (the populations of one
                                                     group share the same points)
    gap_mm: 0.008, margin_mm: 0.04, secret: true, name: prefix
  Placement: each grain held as an oriented ellipsoid around it; drawn uniformly (or around a cluster center) until
  it fits; grains placed from the largest down (small ones always find room between large ones). What could not
  be placed is reported (Scene.report).

voronoi: the body filled by a polycrystal (Voronoi cells of random seeds, cut by the body's surface):
    voronoi: {count: N, phases: {material: fraction, ...}, name: prefix}

pores (Gaussian random field): a voxel body of pores in the body:
    pores: {porosity: p, correlation_mm: l, voxel_mm: v, material: void}
  A Gaussian random field (white noise convolved with a Gaussian of width l) thresholded so that the fraction p of
  the body is pore; voxels outside the body left out.
"""
import copy

import numpy as np

from .scene import Body, Scene, VoxelBody, _moved, body_from_dict, sample_points, scaled
from .shapes import make, rotation

GAP_MM, MARGIN_MM = 0.008, 0.04
_U = None


def _sphere_pts(n=96):
    i = np.arange(n) + 0.5
    th, ph = np.arccos(1 - 2 * i / n), np.pi * (1 + 5 ** 0.5) * i
    return np.c_[np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)]


def volume_of(shape, h=None):
    """Volume of a shape [mm³]: exact if known, else the integral of its chords over a grid of parallel rays."""
    v = shape.volume()
    if v is not None:
        return v
    lo, hi = shape.bounds()
    h = h or float(np.max(hi - lo)) / 300
    X, Y = np.meshgrid(np.arange(lo[0], hi[0], h) + h / 2, np.arange(lo[1], hi[1], h) + h / 2)
    o = np.c_[X.ravel(), Y.ravel(), np.full(X.size, lo[2] - 1)]
    return float(shape.intervals(o, np.tile([0, 0, 1.0], (len(o), 1))).lengths().sum() * h * h)


def bounding_ellipsoid(shape):
    """(center, semi-axes, rotation) of an ellipsoid around a shape (exact for ellipsoids and blobs)."""
    from .shapes import Blob, Ellipsoid
    if isinstance(shape, Blob):
        return shape.t, shape.size / 2 * (1 + abs(shape.w)), shape.R
    if isinstance(shape, Ellipsoid):
        return shape.t, shape.size / 2, shape.R
    lo, hi = shape._local_bounds()
    c = 0.5 * (lo + hi)
    return shape.t + shape.R @ c, 0.5 * (hi - lo) * np.sqrt(3), shape.R


class Packer:
    """Places ellipsoids in a host shape without overlap (the registry holds what is already in the host)."""

    def __init__(self, host_shape, rng, existing=()):
        self.host, self.rng = host_shape, rng
        self.lo, self.hi = host_shape.bounds()
        self.n = 0                                       # arrays grown by doubling (placing n grains costs O(n))
        self._c = np.zeros((64, 3)); self._r = np.zeros(64); self._semi = np.zeros((64, 3)); self._R = np.zeros((64, 3, 3))
        self.U = _sphere_pts()
        for s in existing:
            self.take(*bounding_ellipsoid(s))

    def surface(self, c, semi, R, pad=0.0):
        return np.asarray(c) + (self.U * (np.asarray(semi) + pad)) @ np.asarray(R).T

    @staticmethod
    def _q(p, c, semi, R):
        loc = (p - c) @ R / semi
        return (loc * loc).sum(axis=-1)

    def touches(self, c, semi, R, gap):
        if not len(self.r):
            return False
        close = np.flatnonzero(np.linalg.norm(self.c - c, axis=1) < self.r + float(np.max(semi)) + gap)
        if not len(close):
            return False
        mine = self.surface(c, semi, R, gap)
        for j in close:
            if (self._q(mine, self.c[j], self.semi[j], self.R[j]) < 1).any() or \
                    (self._q(self.surface(self.c[j], self.semi[j], self.R[j]), c, np.asarray(semi) + gap, R) < 1).any():
                return True
        return False

    def fits(self, c, semi, R, margin):
        ext = np.abs(R) @ semi
        if (np.asarray(c) - ext < self.lo - 1e-9).any() or (np.asarray(c) + ext > self.hi + 1e-9).any():
            return False
        return bool(self.host.inside(self.surface(c, semi, R, margin)).all())

    c = property(lambda self: self._c[:self.n])
    r = property(lambda self: self._r[:self.n])
    semi = property(lambda self: self._semi[:self.n])
    R = property(lambda self: self._R[:self.n])

    def take(self, c, semi, R):
        if self.n == len(self._r):
            grow = lambda a: np.concatenate([a, np.zeros_like(a)])
            self._c, self._r, self._semi, self._R = map(grow, (self._c, self._r, self._semi, self._R))
        k = self.n
        self._c[k], self._r[k], self._semi[k], self._R[k] = c, float(np.max(semi)), semi, R
        self.n += 1

    def place(self, semi, R, near=None, spread=None, tries=300, gap=GAP_MM, margin=MARGIN_MM):
        for _ in range(tries):
            c = self.rng.uniform(self.lo, self.hi) if near is None else near + self.rng.normal(0, spread, 3)
            if self.touches(c, semi, R, gap) or not self.fits(c, semi, R, margin):
                continue
            self.take(c, semi, R)
            return c
        return None


def random_rotation(rng):
    """A rotation uniform over SO(3) (from a random unit quaternion)."""
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    a, b, c, d = q
    return np.array([[a * a + b * b - c * c - d * d, 2 * (b * c - a * d), 2 * (b * d + a * c)],
                     [2 * (b * c + a * d), a * a - b * b + c * c - d * d, 2 * (c * d - a * b)],
                     [2 * (b * d - a * c), 2 * (c * d + a * b), a * a - b * b - c * c + d * d]])


def _orientation(spec, rng):
    if spec in (None, "random"):
        return random_rotation(rng)
    if spec == "fixed":
        return np.eye(3)
    axis = np.asarray(spec["axis"], float); axis /= np.linalg.norm(axis)
    # the longest axis (local x) near `axis`, spread by a normal law of width spread_deg; a random spin about it
    spin = rotation({"axis": [1, 0, 0], "angle_deg": rng.uniform(0, 360)})
    tilt_dir = rng.normal(size=3); tilt_dir -= tilt_dir.dot(axis) * axis
    tilt_dir /= np.linalg.norm(tilt_dir)
    t = np.radians(rng.normal(0, float(spec.get("spread_deg", 0))))
    target = np.cos(t) * axis + np.sin(t) * tilt_dir
    x = np.array([1.0, 0, 0])
    v = np.cross(x, target); s = np.linalg.norm(v); c = x.dot(target)
    if s < 1e-12:
        align = np.eye(3) if c > 0 else rotation({"axis": [0, 1, 0], "angle_deg": 180})
    else:
        K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        align = np.eye(3) + K + K @ K * ((1 - c) / s ** 2)
    return align @ spin


def _sizes(pop, rng, host_vol, unit_vol):
    """Longest axes (or scales) of the grains of a population. unit_vol(a, rng-drawn aspect): volume of one grain."""
    aspect = pop.get("aspect", [[0.45, 0.9], [0.5, 0.95]])
    sz = pop.get("size") or {}
    if "size_mm" in pop or "scale" in pop:
        lo_hi = pop.get("size_mm", pop.get("scale"))
        draw = lambda: rng.uniform(*lo_hi)
    elif "lognormal" in sz:
        ln = sz["lognormal"]
        draw = lambda: float(np.clip(ln.get("median_mm", ln.get("median", 1.0)) * np.exp(ln["sigma"] * rng.standard_normal()),
                                     sz.get("min_mm", sz.get("min", 0)), sz.get("max_mm", sz.get("max", np.inf))))
    elif "values_mm" in sz or "values" in sz:
        vals = np.asarray(sz.get("values_mm", sz.get("values")), float)
        draw = lambda: float(rng.choice(vals))
    else:
        raise ValueError(f"population {pop.get('material', pop.get('use'))}: give size_mm, scale or size")
    out, vol = [], 0.0
    count, frac = pop.get("count"), pop.get("fraction")
    target = None if frac is None else float(frac) * host_vol
    while (len(out) < int(count)) if count is not None else (vol < target):
        if len(out) >= 30_000:
            raise ValueError(f"population {pop.get('name') or pop.get('material') or pop.get('use')}: more than 30 000 "
                             "grains. Grains much smaller than the resolution of the instrument are better described "
                             "as a mix (materials: {mix: ...}) than one by one.")
        a = draw()
        asp = (rng.uniform(*aspect[0]), rng.uniform(*aspect[1]))
        out.append((a, asp))
        vol += unit_vol(a, asp)
    return out, target


def _grain_shape(pop, a, asp, R, c, seed):
    g = dict(pop.get("grain") or {"type": "blob", "wobble": float(pop.get("wobble", 0.0))})
    size = [a, a * asp[0], a * asp[1]]
    kind = g.get("type", "blob")
    spec = {"type": kind, "size": size}
    if kind == "blob":
        wf = pop.get("wobble_from_mm")
        spec.update(wobble=g.get("wobble", 0.0) if wf is None or a >= wf else 0.0, seed=int(seed))
    elif kind == "superellipsoid":
        spec["exponent"] = g.get("exponent", 4.0)
    elif kind == "sphere":
        spec = {"type": "sphere", "diameter": a}
    spec["position"] = [float(x) for x in c]
    spec["rotation"] = {"matrix": np.asarray(R).tolist()}
    return spec


def run_fills(body, fills, components, rng, report, base_dir=None, seed_counter=None):
    """Adds to `body` the children made by its fill entries (populations of all entries placed together, the
    largest grains first)."""
    seed_counter = seed_counter if seed_counter is not None else [1000]
    host = body.shape
    host_vol = None
    pops = [f for f in fills if "voronoi" not in f and "pores" not in f]
    if pops:
        _grains(body, pops, components, rng, report, base_dir, seed_counter)
    for f in fills:                                    # then what fills the space left (after the grains)
        if "voronoi" in f:
            _voronoi(body, f["voronoi"], rng, report)
    for f in fills:
        if "pores" in f:
            _pores(body, f["pores"], rng, report)


def _grains(body, pops, components, rng, report, base_dir, seed_counter):
    host = body.shape
    host_vol = None
    packer = Packer(host, rng, [c.shape for c in body.children if not isinstance(c, VoxelBody)])
    todo = []
    comp_info = {}
    for i, pop in enumerate(pops):
        if host_vol is None and pop.get("fraction") is not None:
            host_vol = volume_of(host)
        if "use" in pop:
            comp = components[pop["use"]]
            cshape = body_from_dict(comp, components, base_dir)
            c0, semi0, R0 = bounding_ellipsoid(cshape.shape)
            v0 = volume_of(cshape.shape)
            comp_info[i] = (c0, v0)                  # (its center, its volume at scale 1): computed once
            unit = lambda s, asp, v0=v0: v0 * s ** 3
            sizes, target = _sizes(dict(pop, aspect=[[1, 1], [1, 1]]), rng, host_vol or 0, unit)
            todo += [(i, s, None, semi0 * s) for s, _ in sizes]
        else:
            unit = lambda a, asp: np.pi / 6 * a ** 3 * asp[0] * asp[1]
            sizes, target = _sizes(pop, rng, host_vol or 0, unit)
            w = float((pop.get("grain") or {}).get("wobble", pop.get("wobble", 0.0)))
            todo += [(i, a, asp, 0.5 * np.array([a, a * asp[0], a * asp[1]]) * (1 + abs(w))) for a, asp in sizes]
        report.append(dict(body=body.name, population=pop.get("name") or pop.get("material") or pop.get("use"),
                           asked=pop.get("count") if pop.get("count") is not None else f"{100 * pop['fraction']:g} %",
                           placed=0, volume_mm3=0.0, target_mm3=target))
    rep0 = len(report) - len(pops)
    assert len(comp_info) == sum(1 for p in pops if "use" in p)
    centers, groups = {}, {}
    for i, pop in enumerate(pops):
        cl = pop.get("clusters")
        if cl:
            g = cl.get("group")                         # populations of the same group share their cluster centers
            if g is None or g not in groups:
                k = int(cl["count"])
                pts = sample_points(host, k * 4, rng)
                # centers kept away from the surface (a third of the spread)
                keep = pts[_depth_ok(host, pts, float(cl.get("spread_mm", 0.3)) / 3)][:k]
                if g is not None:
                    groups[g] = keep
            else:
                keep = groups[g]
            centers[i] = (keep, float(cl.get("spread_mm", 0.3)))
    todo.sort(key=lambda t: -float(np.max(t[3])))
    n_in = [0] * len(pops)
    for i, a, asp, semi in todo:
        pop = pops[i]
        R = _orientation(pop.get("orientation"), rng)
        near = spread = None
        if i in centers and len(centers[i][0]):
            near, spread = centers[i][0][n_in[i] % len(centers[i][0])], centers[i][1]
        n_in[i] += 1
        c = packer.place(semi, R, near, spread, int(pop.get("tries", 300)), float(pop.get("gap_mm", GAP_MM)),
                         float(pop.get("margin_mm", MARGIN_MM)))
        if c is None:
            continue
        seed_counter[0] += 1
        name = f"{pop.get('name') or pop.get('material') or pop.get('use')} {report[rep0 + i]['placed'] + 1}"
        if "use" in pop:
            comp = scaled(components[pop["use"]], a)
            # the component's own frame: its bounding ellipsoid centered on c
            c0 = comp_info[i][0] * a
            inst = _moved(comp, None, None)
            inst = _moved(inst, list(-c0), None)
            inst = _moved(inst, list(c), {"matrix": R.tolist()})
            inst["name"] = name
            if pop.get("secret"):
                inst["secret"] = True
            child = build_body(inst, components, rng, report, base_dir, seed_counter)
            if pop.get("secret"):
                for b, _, _ in child.walk():
                    b.secret = True
        else:
            child = Body(name, pop["material"], make(_grain_shape(pop, a, asp, R, c, seed_counter[0])),
                         secret=pop.get("secret", False))
        body.children.append(child)
        r = report[rep0 + i]
        r["placed"] += 1
        r["volume_mm3"] += comp_info[i][1] * a ** 3 if "use" in pop else (child.shape.volume() or volume_of(child.shape))


def _depth_ok(shape, pts, depth):
    """Points at least `depth` inside a shape (tested on six points around each)."""
    ok = np.ones(len(pts), bool)
    for a in range(3):
        for sgn in (-1, 1):
            q = pts.copy(); q[:, a] += sgn * depth
            ok &= shape.inside(q)
    return ok


def _voronoi(body, spec, rng, report):
    """The body filled by Voronoi cells (each the body ∩ the half-spaces closer to its seed than to its neighbors)."""
    from scipy.spatial import Delaunay
    n = int(spec["count"])
    seeds = sample_points(body.shape, n, rng)
    phases = spec.get("phases") or {spec.get("material"): 1.0}
    names, fr = list(phases), np.array(list(phases.values()), float)
    which = rng.choice(len(names), n, p=fr / fr.sum())
    lo, hi = body.shape.bounds()
    # neighbors from the Delaunay triangulation (with far points around, so that every cell is bounded)
    far = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    far = 0.5 * (lo + hi) + 3 * (far - 0.5 * (lo + hi))
    tri = Delaunay(np.vstack([seeds, far]))
    nb = [set() for _ in range(n)]
    for s in tri.simplices:
        for a in s:
            for b in s:
                if a != b and a < n and b < n:
                    nb[a].add(b)
    host_spec = body.shape.to_dict()
    for k in range(n):
        planes = []
        for j in nb[k]:
            m = 0.5 * (seeds[k] + seeds[j]); nrm = seeds[j] - seeds[k]; nrm /= np.linalg.norm(nrm)
            planes.append({"type": "halfspace", "normal": nrm.tolist(), "offset": float(nrm @ m)})
        cell = make({"type": "intersection", "of": [host_spec] + planes})
        body.children.append(Body(f"{spec.get('name', 'grain')} {k + 1}", names[which[k]], cell))
    report.append(dict(body=body.name, population=f"Voronoi, {n} grains", asked=n, placed=n))


def _pores(body, spec, rng, report):
    """Pores from a thresholded Gaussian random field, as a voxel body inside the body."""
    from scipy.ndimage import gaussian_filter
    lo, hi = body.shape.bounds()
    v = float(spec.get("voxel_mm", spec["correlation_mm"] / 4))
    shape = np.maximum(1, np.ceil((hi - lo) / v).astype(int))
    if np.prod(shape) > 300e6:
        raise ValueError(f"pores: {np.prod(shape):.3g} voxels; use a larger voxel_mm")
    field = gaussian_filter(rng.standard_normal(tuple(shape)), sigma=float(spec["correlation_mm"]) / v, mode="wrap")
    g = [lo[a] + (np.arange(shape[a]) + 0.5) * v for a in range(3)]
    P = np.stack(np.meshgrid(*g, indexing="ij"), axis=-1).reshape(-1, 3)
    ins = body.shape.inside(P).reshape(tuple(shape))
    for c in body.children:                             # not where a grain already is: only the voxels of its box
        if isinstance(c, VoxelBody):
            continue
        lo_c, hi_c = c.shape.bounds()
        i0 = np.clip(np.floor((lo_c - lo) / v - 0.5).astype(int), 0, shape)
        i1 = np.clip(np.ceil((hi_c - lo) / v + 0.5).astype(int), 0, shape)
        if (i1 <= i0).any():
            continue
        sub = np.stack(np.meshgrid(*[g[a][i0[a]:i1[a]] for a in range(3)], indexing="ij"), axis=-1)
        blk = ins[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
        blk &= ~c.shape.inside(sub.reshape(-1, 3)).reshape(blk.shape)
    thr = np.quantile(field[ins], float(spec["porosity"])) if ins.any() else 0
    labels = ((field < thr) & ins).astype(np.int64)
    # the pores as label 1 (label 0, the body's own material, not listed: left to the body)
    center = lo + shape * v / 2
    vb = VoxelBody(spec.get("name", "pores"), labels, v, {1: spec.get("material", "void")}, center)
    body.children.append(vb)
    report.append(dict(body=body.name, population="pores (Gaussian random field)",
                       asked=f"{100 * spec['porosity']:g} %", placed=f"{100 * labels.sum() / max(ins.sum(), 1):.2f} %"))


def build_body(d, components, rng, report, base_dir=None, seed_counter=None):
    """A body with its components expanded and its fills run (children first, then the fill around them)."""
    if "use" in d:
        comp = scaled(components[d["use"]], float(d.get("scale", 1.0)))
        inst = _moved(comp, d.get("position"), d.get("rotation"))
        inst["name"] = d.get("name", d["use"])
        for k in ("secret", "material"):
            if k in d:
                inst[k] = d[k]
        return build_body(inst, components, rng, report, base_dir, seed_counter)
    d = dict(d)
    fills = d.pop("fill", None)
    kids = d.pop("children", [])
    b = body_from_dict(dict(d, children=[]), components, base_dir)
    for k in kids:
        b.children.append(build_body(k, components, rng, report, base_dir, seed_counter))
    if fills and isinstance(b, Body):
        run_fills(b, fills, components, rng, report, base_dir, seed_counter)
    return b


def build_scene(d, base_dir=None):
    """The scene of a description: components expanded, fills run (seed of the scene)."""
    d = copy.deepcopy(d)
    rng = np.random.default_rng(int(d.get("seed", 7)))
    comps = d.get("components") or {}
    report = []
    bodies = [build_body(b, comps, rng, report, base_dir, [1000]) for b in d.get("bodies", [])]
    s = Scene(bodies, d.get("materials", {}), d.get("name", ""), d.get("description", ""), d.get("provenance"),
              d.get("seed", 7), comps,
              recipe=d.get("recipe") or (d if any("fill" in str(b) or "use" in str(b) for b in d.get("bodies", []))
                                         else None))
    s.report = report
    return s
