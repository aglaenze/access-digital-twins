"""A sample as a scene: a tree of bodies, each of one material, inside its parent, not overlapping its siblings (as the
cells of Monte Carlo transport codes). What a ray crosses in each material is exact: the intervals of each body minus
those of its children.

Scene file (YAML), lengths in mm, angles in degrees:
    samplecraft: 1
    name: ...                 description: ...
    provenance: {sources: [...], assumptions: [...], data: [...]}
    seed: 7
    materials: {name: <material, see materials.py>}
    components: {name: <body>}                      reusable bodies (with their children)
    bodies: [<body>, ...]
A body:
    name, material, shape: <shape, see shapes.py> | use: <component> (+ position, rotation, scale),
    children: [<body>, ...], fill: [<population, see generators.py>, ...], secret: true (hidden in an exercise),
    holder: true (what the sample stands on), note: "..."
A voxel body (a segmented tomogram):
    name, voxels: {file: <.npy, .tif, .h5[:dataset]> | labels: [[[...]]] | packed: {shape, dtype, zlib_base64},
                   voxel_mm: [vx, vy, vz] | v,
                   materials: {label: material}}, position, rotation (the center of the grid)
The scene as built (build()): components and fills expanded into plain bodies, reproducible from the seed.
"""
import copy

import numpy as np
import yaml

from . import kernels, materials as mats
from .intervals import IntervalSet, combine
from .shapes import Blob, Box, Ellipsoid, Sphere, Union, make, rotation

LENGTH_KEYS = ("size", "diameter", "height", "thickness", "polygon", "vertices", "major_diameter", "minor_diameter",
               "diameter_bottom", "diameter_top", "position", "offset")


def scaled(spec, s):
    """A shape (or body) description scaled by s (lengths and positions)."""
    if s == 1:
        return copy.deepcopy(spec)
    out = {}
    for k, v in spec.items():
        if k in LENGTH_KEYS:
            out[k] = (np.asarray(v, float) * s).tolist() if not np.isscalar(v) else float(v) * s
        elif k == "unit_mm":
            out[k] = float(v) * s
        elif k in ("of", "children"):
            out[k] = [scaled(c, s) for c in v]
        elif k == "shape" and isinstance(v, dict):
            out[k] = scaled(v, s)
        elif k == "voxels":
            out[k] = dict(v, voxel_mm=(np.asarray(v["voxel_mm"], float) * s).tolist())
        else:
            out[k] = copy.deepcopy(v)
    return out


def placed(spec, position=None, rotation_=None):
    """A shape description moved as a whole: a union of one shape, with the pose given."""
    if position is None and not rotation_:
        return spec
    w = {"type": "union", "of": [spec]}
    if position is not None:
        w["position"] = [float(x) for x in position]
    if rotation_:
        w["rotation"] = rotation_
    return w


class Body:
    def __init__(self, name, material, shape, children=(), secret=False, holder=False, note=None):
        self.name, self.material, self.shape = name, material, shape
        self.children = list(children)
        self.secret, self.holder, self.note = bool(secret), bool(holder), note

    def walk(self, parent=None, depth=0):
        """(body, parent body, depth) for this body and all inside it."""
        yield self, parent, depth
        for c in self.children:
            yield from c.walk(self, depth + 1)

    def to_dict(self):
        d = dict(name=self.name, material=self.material, shape=self.shape.to_dict())
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        for k in ("secret", "holder"):
            if getattr(self, k):
                d[k] = True
        if self.note:
            d["note"] = self.note
        return d


class VoxelBody:
    """A grid of labels (a segmented tomogram), each label one material (label 0: the material around, if not given).
    Lengths per label exact for the voxel model (traversal of the grid)."""

    def __init__(self, name, labels, voxel_mm, materials, position=(0, 0, 0), rotation_=None, source=None,
                 secret=False):
        self.name, self.source, self.secret, self.holder = name, source, bool(secret), False
        self.labels = np.ascontiguousarray(np.asarray(labels).astype(np.int64))
        self.vox = np.broadcast_to(np.asarray(voxel_mm, float), (3,)).copy()
        self.materials = {int(k): v for k, v in materials.items()}
        self.t = np.asarray(position, float); self.R = rotation(rotation_)
        self.half = 0.5 * np.array(self.labels.shape) * self.vox
        self.children = []
        self.shape = self                                 # (bounds, inside: as a shape)
        self.material = None

    def walk(self, parent=None, depth=0):
        yield self, parent, depth

    def bounds(self):
        corners = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) * self.half
        w = corners @ self.R.T + self.t
        return w.min(axis=0), w.max(axis=0)

    def bounding_sphere(self):
        return self.t, float(np.linalg.norm(self.half))

    def label_at(self, p):
        q = (np.atleast_2d(p) - self.t) @ self.R + self.half
        idx = np.floor(q / self.vox).astype(np.int64)
        ok = ((idx >= 0) & (idx < np.array(self.labels.shape))).all(axis=1)
        out = np.full(len(q), -1, np.int64)
        out[ok] = self.labels[idx[ok, 0], idx[ok, 1], idx[ok, 2]]
        return out

    def inside(self, p):
        lab = self.label_at(p)
        return np.isin(lab, list(self.materials))

    def label_sets(self, o, d):
        """{label: IntervalSet} of the rays o + t d through the voxels of each label (label 0 left out)."""
        o_l = np.ascontiguousarray((np.atleast_2d(o) - self.t) @ self.R + self.half)
        d_l = np.ascontiguousarray(np.atleast_2d(d) @ self.R)
        n = len(o_l)
        K = 32
        while True:
            seg, lab, cnt = kernels.voxel_segments(o_l, d_l, self.labels, self.vox, K)
            if cnt.max(initial=0) <= K:
                break
            K = int(cnt.max())
        j = np.arange(K)[None, :] < cnt[:, None]
        ray = np.broadcast_to(np.arange(n)[:, None], (n, K))[j]
        t0, t1, lb = seg[..., 0][j], seg[..., 1][j], lab[j]
        return {int(L): IntervalSet(ray[lb == L], t0[lb == L], t1[lb == L], n, normalized=True)
                for L in self.materials if (lb == L).any()}

    def label_lengths(self, o, d):
        """{label: lengths per ray} for the rays o + t d."""
        o_l = (np.atleast_2d(o) - self.t) @ self.R + self.half
        d_l = np.atleast_2d(d) @ self.R
        L = kernels.voxel_lengths(np.ascontiguousarray(o_l), np.ascontiguousarray(d_l), self.labels, self.vox,
                                  int(self.labels.max()) + 1)
        return {lab: L[:, lab] for lab in self.materials if lab <= self.labels.max()}

    def to_dict(self):
        d = dict(name=self.name, voxels=dict(voxel_mm=self.vox.tolist(), materials=self.materials))
        if self.source:
            d["voxels"]["file"] = self.source
        else:
            d["voxels"]["packed"] = pack_labels(self.labels)     # a grid made here (e.g. pores): compressed
        if np.any(self.t):
            d["position"] = self.t.tolist()
        if not np.allclose(self.R, np.eye(3)):
            d["rotation"] = {"matrix": self.R.tolist()}
        if self.secret:
            d["secret"] = True
        return d


def pack_labels(labels):
    """A grid of labels as text (in a scene file or a sample kept in memory): zlib-compressed, base64."""
    import base64
    import zlib
    a = np.asarray(labels)
    dt = np.uint8 if a.max() < 256 else np.uint16 if a.max() < 65536 else np.int64
    return dict(shape=list(a.shape), dtype=np.dtype(dt).name,
                zlib_base64=base64.b64encode(zlib.compress(np.ascontiguousarray(a.astype(dt)).tobytes(), 6)).decode())


def unpack_labels(p):
    import base64
    import zlib
    return np.frombuffer(zlib.decompress(base64.b64decode(p["zlib_base64"])), np.dtype(p["dtype"])).reshape(p["shape"])


def load_labels(source):
    """A 3D array of labels from a file: .npy, .tif/.tiff (a stack), .h5/.hdf5/.nxs ('file.h5:dataset')."""
    import re
    path, key = str(source), None
    m = re.match(r"^(.*\.(?:h5|hdf5|nxs)):([^:\\]+)$", path, re.I)
    if m:
        path, key = m.groups()
    if path.lower().endswith(".npy"):
        return np.load(path)
    if path.lower().endswith((".tif", ".tiff")):
        import tifffile
        return tifffile.imread(path)
    if path.lower().endswith((".h5", ".hdf5", ".nxs")):
        import h5py
        with h5py.File(path, "r") as f:
            return f[key][()]
    raise ValueError(f"voxels: unknown file type {source!r} (.npy, .tif, .h5:dataset)")


class Scene:
    def __init__(self, bodies, materials, name="", description="", provenance=None, seed=7, components=None,
                 recipe=None):
        self.bodies, self.materials = list(bodies), dict(materials)
        self.name, self.description, self.provenance = name, description, provenance or {}
        self.seed, self.components, self.recipe = int(seed), components or {}, recipe
        self._cfg = None

    # ------------------------------------------------------------------ reading, writing
    @classmethod
    def from_dict(cls, d, base_dir=None, build=True):
        """A scene from its description; build=True expands the components and fills (generators.py)."""
        if build:
            from .generators import build_scene
            return build_scene(d, base_dir)
        return cls([body_from_dict(b, d.get("components") or {}, base_dir) for b in d.get("bodies", [])],
                   d.get("materials", {}), d.get("name", ""), d.get("description", ""), d.get("provenance"),
                   d.get("seed", 7), d.get("components"))

    @classmethod
    def load(cls, path, build=True):
        import os
        with open(path, encoding="utf-8") as f:
            d = yaml.load(f, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
        return cls.from_dict(d, os.path.dirname(os.path.abspath(path)), build)

    def to_dict(self):
        """The scene as built (plain Python types: numbers, strings, lists, dicts), with its recipe."""
        d = dict(samplecraft=1, name=self.name, description=self.description, provenance=self.provenance,
                 seed=self.seed, materials=self.materials, bodies=[b.to_dict() for b in self.bodies])
        if self.recipe:
            d["recipe"] = self.recipe
        return plain(d)

    def save(self, path):
        """Writes the scene (YAML); the grids of the voxel bodies made here go to .npy files beside it."""
        import os
        stem = os.path.splitext(path)[0]
        for b, _, _ in self.walk():
            if isinstance(b, VoxelBody) and not b.source:
                f = f"{stem}_{b.name.replace(' ', '_')}.npy"
                np.save(f, b.labels.astype(np.uint16 if b.labels.max() < 65536 else np.int64))
                b.source = os.path.basename(f)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# samplecraft scene (as built): https://github.com/aglaenze/access-digital-twins (samplecraft/)\n")
            yaml.safe_dump(self.to_dict(), f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)

    # ------------------------------------------------------------------ structure
    def walk(self):
        for b in self.bodies:
            yield from b.walk()

    def cfg(self):
        """{material name: NCrystal configuration}."""
        if self._cfg is None:
            self._cfg, self.material_notes = mats.resolve(self.materials)
        return self._cfg

    def leaves(self):
        """[(body, its material, the material around it)]: for a voxel body one entry per label (body, label)."""
        out = []
        for b, parent, _ in self.walk():
            around = parent.material if parent is not None else None
            if isinstance(b, VoxelBody):
                for lab, m in b.materials.items():
                    out.append(((b, lab), m, around))
            else:
                out.append((b, b.material, around))
        return out

    # ------------------------------------------------------------------ physics
    def path_lengths(self, o, d):
        """{(material, material around): lengths [n]} along the rays o + t d (mm): each body adds its own length
        with its material, its children theirs (Σ_child − Σ_parent on their part). A voxel body lies under its
        sibling bodies: its stretches where a sibling is are left to the sibling (exact, interval by interval)."""
        o = np.atleast_2d(np.asarray(o, float)); d = np.atleast_2d(np.asarray(d, float))
        n = len(o)
        index = RayIndex(o, d)
        out = {}

        def add(k, L):
            out[k] = out.get(k, 0) + L

        batch = []

        def go(bodies, around):
            sets = {}
            has_vox = any(isinstance(b, VoxelBody) for b in bodies)
            for b in bodies:
                if isinstance(b, VoxelBody):
                    continue
                if not has_vox and type(b.shape) in BATCHED:
                    batch.append((b, around))           # its length in the batch below (no interval needed)
                else:
                    rays = index.near(*b.shape.bounding_sphere())
                    if len(rays):
                        iv = b.shape.intervals(o[rays], d[rays]).put(rays, n)
                        sets[id(b)] = iv
                        add((b.material, around), iv.lengths())
                go(b.children, b.material)
            vox = [b for b in bodies if isinstance(b, VoxelBody)]
            if vox:
                others = [x for x in sets.values() if len(x)]
                taken = combine(others, lambda c: np.logical_or.reduce(c)) if others else None
                for b in vox:
                    for lab, iv in b.label_sets(o, d).items():
                        if taken is not None:
                            iv = iv - taken
                        add((b.materials[lab], around), iv.lengths())
        go(self.bodies, None)
        if batch:
            _batch(batch, o, d, index, add)
        return out

    def material_lengths(self, o, d):
        """{material: length crossed in it [n]} (the children's lengths taken from their parents)."""
        res = {}
        for (m, around), L in self.path_lengths(o, d).items():
            res[m] = res.get(m, 0) + L
            if around is not None:
                res[around] = res.get(around, 0) - L
        return res

    def material_at(self, p, skip=None):
        """The material of each point (None: outside the sample): the deepest body that holds it (skip(body): a body
        left out, with all inside it: its points keep the material around it). The tree is painted from the top
        down, each body over its parent (each child lies in its parent: check()), voxel bodies under their
        siblings; each body only looks at the points near it (a grid index of the points)."""
        p = np.atleast_2d(np.asarray(p, float))
        out = np.full(len(p), None, object)
        index = _PointIndex(p)

        def go(bodies):
            for b in sorted(bodies, key=lambda x: not isinstance(x, VoxelBody)):
                if skip is not None and skip(b):
                    continue
                lo, hi = b.shape.bounds() if not isinstance(b, VoxelBody) else b.bounds()
                near = index.within(lo, hi)
                if not len(near):
                    continue
                if isinstance(b, VoxelBody):
                    lab = b.label_at(p[near])
                    for k, m in b.materials.items():
                        out[near[lab == k]] = m
                    continue
                out[near[b.shape.inside(p[near])]] = b.material
                go(b.children)
        go(self.bodies)
        return out

    def transmission(self, o, d, wavelength_A):
        """T = exp(−Σ_m Σ_m(λ) L_m) along the rays (lengths mm, Σ in 1/cm)."""
        cfg = self.cfg()
        mu = 0.0
        for m, L in self.material_lengths(o, d).items():
            mu = mu + mats.sigma(cfg[m], [wavelength_A])[0] * L * 0.1
        return np.exp(-mu)

    # ------------------------------------------------------------------ checks
    def check(self, n=4000, rng=None):
        """Problems of the tree: a body not entirely inside its parent, two siblings that overlap. Tested on points
        drawn inside each body (n per body; a problem smaller than about 1/n of its volume can be missed).
        The grains placed by a fill (body.placed) are not tested again: the packer placed each one inside its host and
        apart from the bodies already there (generators.Packer.fits / touches); a rock has thousands of them, and
        testing them took most of the time of a build (17 s of 41 for the meteorite, 2026-11-23)."""
        rng = rng or np.random.default_rng(0)
        problems = []
        placed = lambda x: getattr(x, "placed", False)
        for b, parent, _ in self.walk():
            kids = [k for k in b.children if not isinstance(k, VoxelBody)]   # voxels lie under their siblings
            if parent is not None and not isinstance(b, VoxelBody) and not placed(b):
                pts = sample_points(b.shape, n, rng)
                if len(pts) and not parent.shape.inside(pts).all():
                    frac = 1 - parent.shape.inside(pts).mean()
                    problems.append(f"{b.name}: {100 * frac:.2g} % of it is outside {parent.name}")
            if len(kids) > 1:
                bb = np.array([np.r_[k.shape.bounds()] for k in kids])
                for i in range(len(kids)):
                    if placed(kids[i]):           # (a placed grain against the others: tested by the packer)
                        continue
                    meet = np.flatnonzero((np.minimum(bb[i, 3:], bb[i + 1:, 3:]) >
                                           np.maximum(bb[i, :3], bb[i + 1:, :3])).all(axis=1)) + i + 1
                    if not len(meet):
                        continue
                    pts = sample_points(kids[i].shape, max(200, n // 10), rng)
                    for j in meet:
                        if placed(kids[j]):
                            continue
                        if len(pts) and kids[j].shape.inside(pts).any():
                            problems.append(f"{kids[i].name} and {kids[j].name} overlap (in {b.name})")
        return problems

    def volumes(self, h=None):
        """{material: volume [mm³]}: exact for the shapes that know theirs, else by the integral of the chords over
        a grid of parallel rays of step h (default: 1/400 of the size of the sample)."""
        lo, hi = self.bounds()
        h = h or float(np.max(hi - lo)) / 400
        g0 = np.arange(lo[0], hi[0], h) + h / 2
        g1 = np.arange(lo[1], hi[1], h) + h / 2
        X, Y = np.meshgrid(g0, g1)
        o = np.c_[X.ravel(), Y.ravel(), np.full(X.size, lo[2] - 1.0)]
        d = np.tile([0.0, 0.0, 1.0], (len(o), 1))
        return {m: float(L.sum() * h * h) for m, L in self.material_lengths(o, d).items()}

    def bounds(self):
        b = [x.shape.bounds() for x in self.bodies]
        return np.min([x[0] for x in b], axis=0), np.max([x[1] for x in b], axis=0)


BATCHED = (Blob, Ellipsoid, Sphere, Box)


def _batch(pairs, o, d, index, add):
    """Path lengths of many blobs, ellipsoids, spheres and boxes [(body, material around)] in one compiled call over
    all the (ray, body) pairs (kernels.blob_pairs), added per (material, material around)."""
    bodies = [b for b, _ in pairs]
    nb = len(bodies)
    cen = np.array([b.shape.t for b in bodies]); rot = np.array([b.shape.R for b in bodies])
    semi = np.array([b.shape.size / 2 for b in bodies])
    isbox = np.array([isinstance(b.shape, Box) for b in bodies])
    wob = np.array([b.shape.w if isinstance(b.shape, Blob) else 0.0 for b in bodies])
    lk = np.zeros((nb, 6, 3)); lph = np.zeros((nb, 6)); la = np.zeros((nb, 6))
    for k, b in enumerate(bodies):
        if wob[k]:
            lk[k], lph[k], la[k] = b.shape._lumps
    step = semi.min(axis=1) / 16
    rays, which = [], []
    for k, b in enumerate(bodies):
        r = index.near(*b.shape.bounding_sphere())
        rays.append(r); which.append(np.full(len(r), k))
    ray = np.concatenate(rays).astype(np.int64); body = np.concatenate(which).astype(np.int64)
    if not len(ray):
        return
    L = kernels.blob_pairs(np.ascontiguousarray(o), np.ascontiguousarray(d), ray, body, cen, rot, semi, wob, lk, lph,
                           la, step, isbox)
    keys = [(b.material, a) for b, a in pairs]
    kid = {k: i for i, k in enumerate(dict.fromkeys(keys))}
    kb = np.array([kid[k] for k in keys])[body]
    n = len(o)
    for k, i in kid.items():
        sel = kb == i
        add(k, np.bincount(ray[sel], weights=L[sel], minlength=n))


class _PointIndex:
    """Points binned on a 3D grid: which points lie in a box, without looking at all of them."""

    def __init__(self, p, per_axis=64):
        self.p = p
        self.lo = p.min(axis=0)
        span = np.maximum(p.max(axis=0) - self.lo, 1e-9)
        self.cell = span / per_axis
        self.dim = np.minimum(np.floor(span / self.cell).astype(np.int64) + 1, per_axis + 1)
        ijk = np.minimum((((p - self.lo) / self.cell).astype(np.int64)), self.dim - 1)
        key = (ijk[:, 0] * self.dim[1] + ijk[:, 1]) * self.dim[2] + ijk[:, 2]
        self.order = np.argsort(key, kind="stable")
        self.key = key[self.order]

    def within(self, lo, hi):
        lo, hi = np.maximum(lo, self.lo), np.minimum(hi, self.lo + self.cell * self.dim)
        if (hi < lo).any():
            return np.zeros(0, np.int64)
        a = np.clip(((lo - self.lo) / self.cell).astype(np.int64), 0, self.dim - 1)
        b = np.clip(((hi - self.lo) / self.cell).astype(np.int64), 0, self.dim - 1)
        parts = []
        for i in range(a[0], b[0] + 1):
            for j in range(a[1], b[1] + 1):
                k0 = (i * self.dim[1] + j) * self.dim[2]
                s0 = np.searchsorted(self.key, k0 + a[2]); s1 = np.searchsorted(self.key, k0 + b[2], "right")
                if s1 > s0:
                    parts.append(self.order[s0:s1])
        if not parts:
            return np.zeros(0, np.int64)
        idx = np.concatenate(parts)
        q = self.p[idx]
        return np.sort(idx[((q >= lo) & (q <= hi)).all(axis=1)])


class RayIndex:
    """Which rays pass near a point: for parallel rays (a beam), their crossings with the plane perpendicular to the
    beam binned on a grid; otherwise all the rays (the shapes then test their bounding spheres themselves)."""

    def __init__(self, o, d, cell=None):
        self.n = len(o)
        self.parallel = self.n > 64 and np.allclose(d, d[0], atol=1e-12)
        if not self.parallel:
            return
        self.d = d[0] / np.linalg.norm(d[0])
        e1 = np.cross(self.d, [1.0, 0, 0] if abs(self.d[0]) < 0.9 else [0, 1.0, 0])
        self.e1 = e1 / np.linalg.norm(e1)
        self.e2 = np.cross(self.d, self.e1)
        u, v = o @ self.e1, o @ self.e2
        self.u, self.v = u, v
        span = max(np.ptp(u), np.ptp(v), 1e-9)
        self.cell = cell or span / max(1.0, np.sqrt(self.n) / 4)
        self.u0, self.v0 = u.min(), v.min()
        iu = ((u - self.u0) / self.cell).astype(np.int64)
        iv = ((v - self.v0) / self.cell).astype(np.int64)
        self.nv = int(iv.max()) + 1
        key = iu * self.nv + iv
        self.order = np.argsort(key, kind="stable")
        self.key = key[self.order]
        self.nu = int(iu.max()) + 1

    def near(self, center, radius):
        """Indices (sorted) of the rays within `radius` of `center`."""
        if not self.parallel or not np.isfinite(radius):
            return np.arange(self.n)
        cu, cv = center @ self.e1, center @ self.e2
        a0 = max(0, int((cu - radius - self.u0) / self.cell)); a1 = min(self.nu - 1, int((cu + radius - self.u0) / self.cell))
        b0 = max(0, int((cv - radius - self.v0) / self.cell)); b1 = min(self.nv - 1, int((cv + radius - self.v0) / self.cell))
        if a1 < a0 or b1 < b0:
            return np.zeros(0, np.int64)
        parts = []
        for a in range(a0, a1 + 1):
            lo = np.searchsorted(self.key, a * self.nv + b0)
            hi = np.searchsorted(self.key, a * self.nv + b1, "right")
            parts.append(self.order[lo:hi])
        idx = np.concatenate(parts) if parts else np.zeros(0, np.int64)
        du, dv = self.u[idx] - cu, self.v[idx] - cv
        return np.sort(idx[du * du + dv * dv <= radius * radius * (1 + 1e-9) + 1e-18])


def plain(x):
    """x with numpy numbers and arrays turned into Python ones (for YAML and JSON)."""
    if isinstance(x, dict):
        return {(plain(k) if not isinstance(k, str) else k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return plain(x.tolist())
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    return x


def sample_points(shape, n, rng):
    """n points drawn uniformly inside a shape (rejection in its bounding box)."""
    lo, hi = shape.bounds()
    out, tries = [], 0
    got = 0
    while got < n and tries < 30:
        p = rng.uniform(lo, hi, (max(4 * n, 1000), 3))
        p = p[shape.inside(p)]
        out.append(p); got += len(p); tries += 1
    return np.concatenate(out)[:n] if out else np.zeros((0, 3))


def body_from_dict(d, components, base_dir=None, depth=0):
    """A Body (or VoxelBody) from its description (components used; no fills: see generators.build_scene)."""
    if depth > 50:
        raise ValueError("bodies nested more than 50 deep (a component using itself?)")
    if "use" in d:
        comp = components[d["use"]]
        inst = scaled(comp, float(d.get("scale", 1.0)))
        inst = _moved(inst, d.get("position"), d.get("rotation"))
        inst["name"] = d.get("name", inst.get("name", d["use"]))
        for k in ("secret", "material"):
            if k in d:
                inst[k] = d[k]
        return body_from_dict(inst, components, base_dir, depth + 1)
    if "voxels" in d:
        v = d["voxels"]
        if "file" in v:
            import os
            f = v["file"] if os.path.isabs(v["file"]) or not base_dir else os.path.join(base_dir, v["file"])
            labels = load_labels(f)
        elif "packed" in v:
            labels = unpack_labels(v["packed"])
        else:
            labels = np.asarray(v["labels"])
        return VoxelBody(d.get("name", "voxels"), labels, v["voxel_mm"], v["materials"], d.get("position", (0, 0, 0)),
                         d.get("rotation"), v.get("file"), d.get("secret", False))
    shape_spec = d["shape"]
    if shape_spec.get("type") == "mesh" and shape_spec.get("file") and base_dir:
        import os
        if not os.path.isabs(shape_spec["file"]):
            shape_spec = dict(shape_spec, file=os.path.join(base_dir, shape_spec["file"]))
    shape = make(shape_spec)
    kids = [body_from_dict(c, components, base_dir, depth + 1) for c in d.get("children", [])]
    return Body(d.get("name", ""), d.get("material"), shape, kids, d.get("secret", False), d.get("holder", False),
                d.get("note"))


def _moved(body, position, rot):
    """A body description moved as a whole (its shape and those of all its children, by the same pose)."""
    if position is None and not rot:
        return body
    b = dict(body)
    if "shape" in b:
        b["shape"] = placed(b["shape"], position, rot)
    if "voxels" in b:
        R = rotation(rot)
        b["position"] = (R @ np.asarray(b.get("position", (0, 0, 0)), float) +
                         (np.asarray(position, float) if position is not None else 0)).tolist()
        b["rotation"] = {"matrix": (R @ rotation(b.get("rotation"))).tolist()}
    b["children"] = [_moved(c, position, rot) for c in b.get("children", [])]
    return b


__all__ = ["Scene", "Body", "VoxelBody", "Union"]
