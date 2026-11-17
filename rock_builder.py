"""Builds samples for the ODIN twin: a piece of any shape (a sawn piece, a lumpy pebble, a block, a cylinder) filled
with grains, clasts, pores, objects placed by hand, inclusions in inclusions, as volumes of sample_library (format of
the samples/*.yml files). Used by the generators of the library samples (odin/samples/gen_nwa7034.py: the Martian
meteorite) and by the sample builder (Sample_builder.ipynb: build_sample, from a recipe).

    rock = Rock(dict(material="matrix", shape="slab", size_mm=[8, 12, 2], seed=11), seed=7)
    rock.fill([dict(material="plagioclase", fraction=0.05, size_mm=(0.1, 0.5), wobble=0.12),
               dict(material="pyroxene", fraction=0.05, size_mm=(0.1, 0.5), wobble=0.12)])
    rock.population("Fe-Ti oxide", count=2500, median_mm=0.04, sigma=0.5, size_lim_mm=(0.016, 0.08))
    spec_volumes = rock.vols

Placement: each object is held as an oriented ellipsoid around it (its lumps included) and put where it touches
nothing placed before in the same host (a few µm apart) and stays inside its host (40 µm from its surface); positions
drawn at random (fixed seed), uniformly or around the centers of clusters. Objects are best placed from the largest
down (fill() does it): small ones always find room between large ones, not the reverse.
Units: mm and degrees (as in the .yml files); rock_shapes works in m.
"""
import numpy as np

import rock_shapes as rs

GAP_MM = 0.008             # space left between two objects
MARGIN_MM = 0.04           # space left between an object and the surface of its host

# --------------------------------------------------------------------------- minerals
ELEM = {"H": 1.008, "C": 12.011, "O": 15.999, "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974,
        "S": 32.06, "Cl": 35.45, "K": 39.098, "Ca": 40.078, "Ti": 47.867, "Fe": 55.845}
# atoms per formula unit, density [g/cm³] (common values of mineralogy handbooks)
MINERALS = {
    "plag": (dict(Na=0.5, Ca=0.5, Al=1.5, Si=2.5, O=8.0), 2.69),       # plagioclase An50
    "opx": (dict(Mg=1.2, Fe=0.8, Si=2.0, O=6.0), 3.55),                # orthopyroxene
    "cpx": (dict(Ca=0.9, Mg=0.7, Fe=0.4, Si=2.0, O=6.0), 3.40),        # clinopyroxene
    "ol": (dict(Mg=1.6, Fe=0.4, Si=1.0, O=4.0), 3.32),                 # olivine Fo80
    "mag": (dict(Fe=3.0, O=4.0), 5.15),                                # magnetite
    "magh": (dict(Fe=2.0, O=3.0), 4.90),                               # maghemite
    "hem": (dict(Fe=2.0, O=3.0), 5.26),                                # hematite
    "ilm": (dict(Fe=1.0, Ti=1.0, O=3.0), 4.72),                        # ilmenite
    "afs": (dict(Na=1.0, Al=1.0, Si=3.0, O=8.0), 2.62),                # alkali feldspar (albite)
    "ap": (dict(Ca=5.0, P=3.0, O=12.0, Cl=1.0), 3.15),                 # chlorapatite
    "py": (dict(Fe=1.0, S=2.0), 5.01),                                 # pyrite
    "qz": (dict(Si=1.0, O=2.0), 2.65),                                 # quartz
    "cc": (dict(Ca=1.0, C=1.0, O=3.0), 2.71),                          # calcite
    "gt": (dict(Fe=1.0, O=2.0, H=1.0), 4.27),                          # goethite FeO(OH): holds hydrogen
    "srp": (dict(Mg=3.0, Si=2.0, O=9.0, H=4.0), 2.55),                 # serpentine Mg3Si2O5(OH)4: holds hydrogen
    "gyp": (dict(Ca=1.0, S=1.0, O=6.0, H=4.0), 2.32),                  # gypsum CaSO4·2H2O: holds hydrogen
    "kln": (dict(Al=2.0, Si=2.0, O=9.0, H=4.0), 2.60),                 # kaolinite (clay) Al2Si2O5(OH)4: holds hydrogen
}


def solid(vol):
    """NCrystal configuration (solid::, no Bragg edge: a fine-grained mineral or mixture of minerals) of the minerals
    `vol` {key of MINERALS: volume fraction}."""
    vt = sum(vol.values())
    mass, rho = {}, 0.0
    for k, v in vol.items():
        at, d = MINERALS[k]
        f = v / vt
        rho += f * d
        m = {el: n * ELEM[el] for el, n in at.items()}
        tot = sum(m.values())
        for el, w in m.items():
            mass[el] = mass.get(el, 0.0) + f * d * w / tot
    tot = sum(mass.values())
    at = {el: w / tot / ELEM[el] for el, w in mass.items()}
    mn = min(at.values())
    return "solid::" + "".join(f"{el}{max(1, int(round(v / mn * 10)))}" for el, v in at.items()) + f"/{rho:.3f}gcm3"


# the rock-forming minerals offered by the sample builder: {label: mineral volume fractions}
ROCK_MINERALS = {
    "plagioclase (feldspar)": dict(plag=85, afs=15),
    "pyroxene": dict(opx=58, cpx=42),
    "olivine": dict(ol=100),
    "quartz (fine-grained)": dict(qz=100),
    "calcite": dict(cc=100),
    "Fe-Ti oxide (magnetite + ilmenite)": dict(mag=65, ilm=35),
    "hematite": dict(hem=100),
    "apatite": dict(ap=100),
    "pyrite": dict(py=100),
    "goethite FeO(OH) (holds H)": dict(gt=100),
    "serpentine (holds H)": dict(srp=100),
    "gypsum (holds H)": dict(gyp=100),
    "clay: kaolinite (holds H)": dict(kln=100),
    "basalt (fine-grained)": dict(plag=50, cpx=35, ol=8, mag=7),
}


def rock_mineral(label):
    """NCrystal configuration of a mineral of ROCK_MINERALS."""
    return solid(ROCK_MINERALS[label])


def _r(x, n=4):
    return [round(float(v), n) for v in x]


# --------------------------------------------------------------------------- volumes
def bounding_ellipsoid(v):
    """(center, semi-axes, rotation) [mm] of an ellipsoid holding the volume v (sample_library format)."""
    c = np.asarray(v.get("center_mm", (0, 0, 0)), float)
    s = 0.5 * np.asarray(v["size_mm"][:3], float)
    shape = v.get("shape", "box")
    if shape == "blob":
        return c, s * (1 + abs(float(v.get("wobble", 0)))), rs._rot(*(v.get("angles_deg") or (0, 0, 0)))
    if shape in ("box", "ellipsoid"):
        R = rs._rot(0, 0, float(v["size_mm"][3])) if len(v["size_mm"]) > 3 else np.eye(3)
        return c, s * (np.sqrt(3) if shape == "box" else 1.0), R
    if shape == "cylinder":                           # vertical: (r, h) corners on x²/2r² + y²/2h² = 1
        return c, s * np.sqrt(2), np.eye(3)
    if shape == "slab":
        return c, (s + 0.3) * np.sqrt(3), np.eye(3)
    return c, s, np.eye(3)                            # sphere


def volume_mm3(v):
    """Volume [mm³] of a volume v (counted on a grid of 20 µm for a sawn piece)."""
    s = np.asarray(v["size_mm"][:3], float)
    shape = v.get("shape", "box")
    if shape == "slab":
        dims = tuple(s * 1e-3) + (v.get("seed", 0),)
        h = 0.55 * float(max(s[0], s[1])) * 1e-3
        g = np.arange(-h, h, 20e-6)
        X, Y = np.meshgrid(g, g)
        return float(rs.slab_path_length(X.ravel(), Y.ravel(), (0, 0, 0), dims, 0).sum() * 400e-12 * 1e9)
    if shape == "blob":
        return rs.blob_volume(Rock.dims(v)) * 1e9
    if shape in ("sphere", "ellipsoid"):
        return float(np.pi / 6 * np.prod(s))
    if shape == "cylinder":
        return float(np.pi / 4 * s[0] * s[2] * s[1])
    return float(np.prod(s))


class Rock:
    """Volumes (sample_library format) and the placing of new ones in them. Rock(outline): the piece is volume 0 and
    things go in it by default; Rock(None): no piece (objects placed by hand, add())."""

    def __init__(self, outline=None, seed=7, first_seed=100):
        self.rng = np.random.default_rng(seed)
        self.vols = [dict(outline)] if outline else []
        # what has been placed, as oriented ellipsoids: centers, bounding radii, semi-axes, rotations, hosts
        self.c = np.zeros((0, 3)); self.r = np.zeros(0); self.semi = np.zeros((0, 3)); self.R = np.zeros((0, 3, 3))
        self.host = np.zeros(0, int)
        self.seed = first_seed
        i = np.arange(96) + 0.5                           # points spread evenly on the unit sphere (Fibonacci)
        th, ph = np.arccos(1 - 2 * i / 96), np.pi * (1 + 5 ** 0.5) * i
        self.U = np.c_[np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)]

    # ------------------------------------------------------------------ hosts
    def _box(self, host):
        """Center and half-extents [mm] of a box around volume `host` (a sawn piece: its nominal size; its wavy
        sides, a fraction of a mm, are left to the exact test)."""
        v = self.vols[host]
        if v.get("shape") == "slab":
            return np.asarray(v.get("center_mm", (0, 0, 0)), float), 0.5 * np.asarray(v["size_mm"][:3], float)
        c, semi, R = bounding_ellipsoid(v)
        return c, np.abs(R) @ semi

    def volume_mm3(self, host=0):
        """Volume of the piece (or of volume `host`) [mm³]."""
        return volume_mm3(self.vols[host])

    def random_point(self, host=0):
        c, half = self._box(host)
        return c + self.rng.uniform(-1, 1, 3) * half

    def outline_inside(self, pts, host=0):
        """Whether points [mm] are inside volume `host` (the piece by default)."""
        from sample_library import odin_inside
        return odin_inside(self.vols[host], pts)

    # ------------------------------------------------------------------ geometry of the objects
    def surface(self, c, semi, R, pad=0.0):
        """Points [mm] on the surface of an ellipsoid (center c, semi-axes semi, rotation R), pushed out by pad."""
        return np.asarray(c) + ((self.U * (np.asarray(semi) + pad)) @ np.asarray(R).T)

    def fits(self, c, semi, R, host=0):
        """An ellipsoid inside volume `host`, MARGIN_MM from its surface."""
        hc, hh = self._box(host)
        ext = np.abs(np.asarray(R)) @ np.asarray(semi)              # half-extent of its bounding box
        if (np.abs(np.asarray(c) - hc) + ext > hh + 0.2).any():
            return False
        return bool(self.outline_inside(self.surface(c, semi, R, MARGIN_MM), host).all())

    @staticmethod
    def _q(p, c, semi, R):
        """Quadratic form of an ellipsoid at points p (< 1 inside)."""
        loc = (p - c) @ R / semi
        return (loc * loc).sum(axis=-1)

    def touches(self, c, semi, R, host=0, gap=GAP_MM):
        """Whether an ellipsoid touches one already placed in the same host."""
        if not len(self.r):
            return False
        r = float(np.max(semi))
        close = np.where((self.host == host) & (np.linalg.norm(self.c - c, axis=1) < self.r + r + gap))[0]
        if not len(close):
            return False
        mine = self.surface(c, semi, R, gap)
        for j in close:                                  # its surface in a neighbor, or the neighbor's in it
            if (self._q(mine, self.c[j], self.semi[j], self.R[j]) < 1).any() or \
                    (self._q(self.surface(self.c[j], self.semi[j], self.R[j]), c, np.asarray(semi) + gap, R) < 1).any():
                return True
        return False

    def take(self, c, semi, R, host=0):
        """Registers an ellipsoid as placed."""
        self.c = np.vstack([self.c, c]); self.r = np.r_[self.r, float(np.max(semi))]
        self.semi = np.vstack([self.semi, semi]); self.R = np.concatenate([self.R, np.asarray(R, float)[None]])
        self.host = np.r_[self.host, host]

    def free(self, r, near=None, spread=None, tries=300, semi=None, R=None, gap=GAP_MM, host=0):
        """A place [mm] for an ellipsoid (semi-axes semi, rotation R; a sphere of radius r if semi is None) inside
        volume `host` that touches nothing placed before in it (gap apart), drawn uniformly or around `near` (normal
        law of width spread); None if none found in `tries` draws. The place is then taken."""
        if semi is None:
            semi, R = np.array([r, r, r], float), np.eye(3)
        semi, R = np.asarray(semi, float), np.asarray(R, float)
        for _ in range(tries):
            c = self.random_point(host) if near is None else near + self.rng.normal(0, spread, 3)
            if self.touches(c, semi, R, host, gap) or not self.fits(c, semi, R, host):
                continue
            self.take(c, semi, R, host)
            return c
        return None

    def free_blob(self, size, angles, wobble, **kw):
        """free() for a blob of this size, angles and wobble (its lumps reach 1 + wobble times the ellipsoid)."""
        return self.free(0, semi=0.5 * np.asarray(size, float) * (1 + abs(wobble)), R=rs._rot(*angles), **kw)

    def angles(self):
        """A random orientation (uniform over the directions)."""
        return [round(float(a), 1) for a in (self.rng.uniform(0, 360), np.degrees(np.arccos(self.rng.uniform(-1, 1))),
                                              self.rng.uniform(0, 360))]

    def next_seed(self):
        self.seed += 1
        return self.seed

    def blob(self, material, c, size, angles, wobble, inside=0, secret=False):
        """Adds a blob (a grain, a clast, a pore); returns its index."""
        v = dict(material=material, shape="blob", inside=inside, center_mm=_r(c), size_mm=_r(size),
                 angles_deg=list(angles), wobble=round(float(wobble), 3), seed=self.next_seed())
        if secret:
            v["secret"] = True
        self.vols.append(v)
        return len(self.vols) - 1

    def add(self, v):
        """Adds a volume placed by hand (sample_library format; "inside": its host, if any) and registers it, so that
        what is placed later in the same host avoids it; returns its index. Not checked here: see check_added."""
        self.vols.append(dict(v))
        c, semi, R = bounding_ellipsoid(v)
        self.take(c, semi, R, v.get("inside", -1))
        return len(self.vols) - 1

    def check_added(self, k, name):
        """Problems of a volume placed by hand: outside its host, or touching another one of the same host."""
        v = self.vols[k]
        out = []
        if "inside" in v:
            pts = self.points_in(k, 400)
            if len(pts) and not self.contains(v["inside"], pts).all():
                out.append(f"{name} is not entirely inside what holds it")
        for j in range(len(self.vols)):
            w = self.vols[j]
            if j != k and w.get("inside", -1) == v.get("inside", -1) and not w.get("holder") and self.overlap(k, j):
                out.append(f"{name} overlaps another object")
                break
        return out

    @staticmethod
    def dims(v):
        """dims of rock_shapes [m] of a blob."""
        return tuple(s * 1e-3 for s in v["size_mm"][:3]) + tuple(v["angles_deg"]) + (v["wobble"], v["seed"])

    def blob_volume(self, k):
        return rs.blob_volume(self.dims(self.vols[k])) * 1e9

    def points_in(self, k, n=400):
        """Points [mm, sample frame] spread inside volume k."""
        v = self.vols[k]
        c = np.asarray(v["center_mm"], float)
        if v.get("shape") == "blob":
            r = rs.blob_bound(self.dims(v)) * 1e3
            p = self.rng.uniform(-r, r, (n * 4, 3))
            p = p[rs.inside("blob", self.dims(v), p * 1e-3)][:n]
            return c + p
        if v.get("shape", "box") == "box":
            s = np.asarray(v["size_mm"][:3], float)
            p = self.rng.uniform(-0.5, 0.5, (n, 3)) * s
            t = np.radians(v["size_mm"][3]) if len(v["size_mm"]) > 3 else 0.0
            return c + np.c_[np.cos(t) * p[:, 0] + np.sin(t) * p[:, 2], p[:, 1],
                             -np.sin(t) * p[:, 0] + np.cos(t) * p[:, 2]]
        bc, semi, R = bounding_ellipsoid(v)                # other shapes: draw in a box around, keep those inside
        half = np.abs(R) @ semi
        p = bc + self.rng.uniform(-1, 1, (n * 8, 3)) * half
        return p[self.contains(k, p)][:n]

    def contains(self, host, pts):
        from sample_library import odin_inside
        return odin_inside(self.vols[host], pts)

    def overlap(self, i, j, n=24):
        """Whether volumes i and j share a point: tested on a grid of their common bounding box (the test of
        sample_library.validate, finer)."""
        from sample_library import odin_inside
        a, b = self.vols[i], self.vols[j]
        (ca, sa, Ra), (cb, sb, Rb) = bounding_ellipsoid(a), bounding_ellipsoid(b)
        ha, hb = np.abs(Ra) @ sa, np.abs(Rb) @ sb
        lo, hi = np.maximum(ca - ha, cb - hb), np.minimum(ca + ha, cb + hb)
        if not (hi > lo).all():
            return False
        g = [np.linspace(p, q, n) for p, q in zip(lo, hi)]
        pts = np.stack(np.meshgrid(*g, indexing="ij"), axis=-1).reshape(-1, 3)
        return bool((odin_inside(a, pts) & odin_inside(b, pts)).any())

    def fit_inside(self, host, make, scales=np.linspace(1.0, 0.35, 14), avoid=(), n_pts=300):
        """Adds the volume make(scale) inside volume `host`, shrunk (scales) until it fits there without touching the
        volumes `avoid`; returns its index or None."""
        for scale in scales:
            self.vols.append(make(scale))
            k = len(self.vols) - 1
            pts = self.points_in(k, n_pts)
            if len(pts) > 20 and self.contains(host, pts).all() and not any(self.overlap(k, p) for p in avoid):
                return k
            self.vols.pop()
        return None

    # ------------------------------------------------------------------ populations
    def clusters(self, n, keep_mm=0.3, host=0):
        """n centers of clusters [mm], anywhere in volume `host` (keep_mm from its surface)."""
        out = []
        for _ in range(200 * max(n, 1)):
            if len(out) >= n:
                break
            c = self.random_point(host)
            if self.fits(c, (keep_mm,) * 3, np.eye(3), host):
                out.append(c)
        return out

    def _sizes(self, pop, host_mm3):
        """The sizes [mm] of the grains of a population (see fill)."""
        rng = self.rng
        sizes, vol = [], 0.0
        count, fraction = pop.get("count"), pop.get("fraction")
        target = fraction * host_mm3 if fraction is not None else None
        aspect = pop.get("aspect", ((0.45, 0.9), (0.5, 0.95)))
        while ((len(sizes) < count) if count is not None else (vol < target)) and len(sizes) < 200_000:
            if pop.get("median_mm") is None:
                a = rng.uniform(*pop.get("size_mm", (0.1, 0.5)))
            else:
                a = float(pop["median_mm"] * np.exp(pop.get("sigma", 0.5) * rng.standard_normal()))
                if pop.get("size_lim_mm"):
                    a = float(np.clip(a, *pop["size_lim_mm"]))
            d = np.array([a, a * rng.uniform(*aspect[0]), a * rng.uniform(*aspect[1])])
            sizes.append(d)
            vol += np.pi / 6 * np.prod(d)
        return sizes

    def fill(self, pops):
        """Grains of several populations, placed together from the largest down (best packing). Each population: a
        dict with material; either fraction (of the volume of its host) or count; sizes [mm]: the longest axis
        uniform in size_mm (default 0.1 to 0.5), or log-normal (median_mm, sigma) clipped to size_lim_mm; the two
        other axes `aspect` times it (two ranges); lumps `wobble` (only from the size wobble_from_mm up, if given);
        clusters: centers to gather them around (spread_mm); inside (host index, default 0), secret. Returns, for each
        population, (indices placed, volume placed [mm³], volume wanted [mm³] or None)."""
        vol_of = {}
        for p in pops:
            h = p.get("inside", 0)
            if p.get("fraction") is not None and h not in vol_of:
                vol_of[h] = self.volume_mm3(h)
        todo = []
        for i, p in enumerate(pops):
            todo += [(i, d) for d in self._sizes(p, vol_of.get(p.get("inside", 0), 0.0))]
        todo.sort(key=lambda t: -t[1].max())
        out = [([], 0.0, (p["fraction"] * vol_of[p.get("inside", 0)] if p.get("fraction") is not None else None))
               for p in pops]
        n_in = [0] * len(pops)
        for i, d in todo:
            p = pops[i]
            ang = self.angles()
            wf = p.get("wobble_from_mm")
            wob = p.get("wobble", 0.0) if wf is None or d.max() >= wf else 0.0
            cl = p.get("clusters")
            near = None if cl is None or not len(cl) else cl[n_in[i] % len(cl)]
            n_in[i] += 1
            host = p.get("inside", 0)
            c = self.free_blob(d, ang, wob, near=near, spread=p.get("spread_mm", 0.35), tries=p.get("tries", 300),
                               host=host)
            if c is None:
                continue
            k = self.blob(p["material"], c, d, ang, wob, inside=host, secret=p.get("secret", False))
            ks, v, want = out[i]
            out[i] = (ks + [k], v + self.blob_volume(k), want)
        return out

    def population(self, material, **kw):
        """Grains of one material (the arguments of a population of fill); returns (indices, volume placed [mm³],
        volume wanted [mm³])."""
        return self.fill([dict(material=material, **kw)])[0]


# --------------------------------------------------------------------------- recipes (the sample builder)
# Shapes of the builder -> volumes: a block (turned about the vertical axis only), a vertical cylinder, a sphere, an
# ellipsoid or a lumpy grain/pebble (turned in 3D: blob), a sawn piece (slab: wavy sides, rounded edges, a corner
# broken off).
SHAPES = {"block": "box", "cylinder": "cylinder", "sphere": "sphere", "ellipsoid": "blob", "lumpy (pebble, grain)": "blob",
          "sawn piece (irregular edges)": "slab"}
# grain shapes of a population: ranges of the two shorter axes / the longest
GRAIN_SHAPES = {"round": ((0.8, 1.0), (0.8, 1.0)), "irregular": ((0.45, 0.9), (0.5, 0.95)),
                "elongated": ((0.2, 0.4), (0.3, 0.5)), "flat (plates)": ((0.6, 1.0), (0.08, 0.2))}


def recipe_volume(obj, seed):
    """The volume (sample_library format, without "inside") of an object of a recipe: {shape (a key of SHAPES),
    material, center_mm, size_mm, angles_deg, lumps}."""
    shape = SHAPES[obj["shape"]]
    size = [float(s) for s in obj["size_mm"]]
    ang = [float(a) for a in (obj.get("angles_deg") or (0, 0, 0))]
    v = dict(material=obj["material"], center_mm=[float(c) for c in obj.get("center_mm", (0, 0, 0))])
    if shape == "box":
        v["size_mm"] = size[:3] + ([ang[2]] if ang[2] else [])
    elif shape == "cylinder":
        v.update(shape="cylinder", size_mm=[size[0], size[1], size[0]])
    elif shape == "sphere":
        v.update(shape="sphere", size_mm=[size[0]] * 3)
    elif shape == "slab":
        v.update(shape="slab", size_mm=size[:3], seed=int(seed))
    else:
        lumps = float(obj.get("lumps", 0.0)) if obj["shape"].startswith("lumpy") else 0.0
        v.update(shape="blob", size_mm=size[:3], angles_deg=ang, wobble=lumps, seed=int(seed))
    return v


def build_sample(recipe, progress=None):
    """A sample (sample_library spec: volumes, materials) from a recipe of the sample builder:
        piece: an object (or None): what holds the rest;
        objects: [{name, shape, material, center_mm, size_mm, angles_deg, lumps, inside: "piece" | another object's
                   name | None}], placed by hand;
        populations: [{material, fraction_pct | count, size_mm: [min, max], grain_shape (GRAIN_SHAPES), lumps,
                       clusters (number, 0: spread), spread_mm, inside: "piece" | an object's name}], placed at random;
        holders: [{shape, material, center_mm, size_mm}];
        materials: {name: NCrystal configuration} (named materials used above); seed.
    Returns (spec, report lines, problems)."""
    seed = int(recipe.get("seed", 7))
    piece = recipe.get("piece")
    rock = Rock(None, seed=seed)
    problems, report = [], []
    index = {}
    if piece:
        rock.add(recipe_volume(piece, seed + 1))
        index["piece"] = 0
    for k, obj in enumerate(recipe.get("objects") or []):
        name = obj.get("name") or f"object {k + 1}"
        v = recipe_volume(obj, seed + 10 + k)
        host = obj.get("inside")
        if host:
            if host not in index:
                problems.append(f"{name}: inside {host!r}, which is not defined above it")
                continue
            v["inside"] = index[host]
        index[name] = rock.add(v)
        problems += rock.check_added(index[name], name)
    pops = []
    for k, p in enumerate(recipe.get("populations") or []):
        host = p.get("inside") or "piece"
        if host not in index:
            problems.append(f"grains {k + 1} ({p['material']}): inside {host!r}, which does not exist")
            continue
        lo, hi = sorted(float(s) for s in p.get("size_mm", (0.1, 0.5)))
        if lo <= 0:
            problems.append(f"grains {k + 1} ({p['material']}): sizes must be above 0")
            continue
        q = dict(material=p["material"], size_mm=(lo, hi), aspect=GRAIN_SHAPES[p.get("grain_shape", "irregular")],
                 wobble=float(p.get("lumps", 0.0)), inside=index[host])
        if p.get("count"):
            q["count"] = int(p["count"])
        else:
            q["fraction"] = float(p.get("fraction_pct", 1.0)) / 100
        if int(p.get("clusters") or 0) > 0:
            q["clusters"] = rock.clusters(int(p["clusters"]), keep_mm=min(0.3, hi), host=index[host])
            q["spread_mm"] = float(p.get("spread_mm", 0.4))
        pops.append((k, q))
    if progress:
        progress("placing the grains...")
    for (k, q), (ks, vol, want) in zip(pops, rock.fill([q for _, q in pops])):
        n_want = q.get("count")
        got = f"{len(ks)} grains of {q['material']}"
        if want:
            got += f", {100 * vol / rock.volume_mm3(q['inside']):.2f} % of the volume (asked: {100 * q['fraction']:g} %)"
            if vol < 0.9 * want:
                problems.append(f"grains {k + 1} ({q['material']}): only {100 * vol / want:.0f} % of the amount asked "
                                f"found room (smaller grains, or less of them)")
        elif n_want and len(ks) < n_want:
            problems.append(f"grains {k + 1} ({q['material']}): {len(ks)} of the {n_want} asked found room")
        report.append(got)
    for h in recipe.get("holders") or []:
        v = recipe_volume(h, 0)
        v["holder"] = True
        rock.vols.append(v)
    spec = dict(volumes=rock.vols)
    if recipe.get("materials"):
        used = {v["material"] for v in rock.vols}
        spec["materials"] = {k: c for k, c in recipe["materials"].items() if k in used}
    if any(v.get("shape") in ("blob", "slab") for v in rock.vols):
        spec["hybrid_only"] = True                     # McStas has no such shapes: the hybrid model of the twin
    return spec, report, problems


def recipe_from_spec(spec):
    """A recipe for the sample builder from a sample (a library sample, a student's): its own recipe if it has one,
    else its volumes as objects placed by hand (None if it has too many to edit by hand)."""
    if spec.get("recipe"):
        return dict(spec["recipe"])
    vols = spec.get("volumes") or []
    if len([v for v in vols if not v.get("holder")]) > 60:
        return None
    inv = {"box": "block", "cylinder": "cylinder", "sphere": "sphere", "slab": "sawn piece (irregular edges)"}
    objects, holders, names = [], [], {}
    for k, v in enumerate(vols):
        shape = v.get("shape", "box")
        size = list(v["size_mm"][:3])
        o = dict(material=v["material"], center_mm=list(v.get("center_mm", (0, 0, 0))), size_mm=size)
        if shape == "blob":
            o["shape"] = "lumpy (pebble, grain)" if v.get("wobble") else "ellipsoid"
            o["angles_deg"] = list(v.get("angles_deg") or (0, 0, 0))
            o["lumps"] = float(v.get("wobble", 0))
        elif shape == "ellipsoid":
            o["shape"] = "ellipsoid"
            o["angles_deg"] = [0, 0, float(v["size_mm"][3]) if len(v["size_mm"]) > 3 else 0]
        else:
            o["shape"] = inv[shape]
            if shape == "box" and len(v["size_mm"]) > 3:
                o["angles_deg"] = [0, 0, float(v["size_mm"][3])]
        if v.get("holder"):
            holders.append(o)
            continue
        o["name"] = names[k] = f"object {len(objects) + 1}"
        if "inside" in v:
            o["inside"] = names.get(int(v["inside"]))
        objects.append(o)
    return dict(piece=None, objects=objects, populations=[], holders=holders,
                materials=dict(spec.get("materials") or {}), seed=7)
