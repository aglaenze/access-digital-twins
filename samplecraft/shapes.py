"""Shapes: primitives, constructive solid geometry, meshes, implicit surfaces. Units: mm, degrees.

Every shape has a pose (position of its local origin, rotation local -> parent frame) and can
  * intervals(o, d): the intervals of t crossed by the rays o + t d (exact; see each shape),
  * inside(p): which points are inside,
  * bounds(): an axis-aligned box around it (parent frame),
  * volume(): exact if known, else None (estimated by the scene, with its uncertainty).
The local frame of each primitive is centered on it; cylinders, cones and tori have their axis along local y (the
vertical axis of the instruments' rotation stages); a prism is a polygon of the local x-y plane extruded along local z
(the beam at 0°).
"""
import numpy as np

from . import kernels
from .intervals import IntervalSet, combine

EPS = 1e-12
REGISTRY = {}


def register(cls):
    REGISTRY[cls.kind] = cls
    return cls


# --------------------------------------------------------------------------------------------- orientations
def rotation(spec):
    """Rotation matrix (local -> parent) from:
       None / {} : none;
       {"euler_deg": [a_z, a_x, a_y]}: about z by a_z, then about x by a_x, then about y by a_y (fixed axes);
       {"axis": [x, y, z], "angle_deg": a}: about an axis;
       {"matrix": 3 × 3}."""
    if spec is None or (isinstance(spec, dict) and not spec):
        return np.eye(3)
    if isinstance(spec, np.ndarray):
        return np.asarray(spec, float)
    if "matrix" in spec:
        R = np.asarray(spec["matrix"], float)
        if not np.allclose(R @ R.T, np.eye(3), atol=1e-9) or np.linalg.det(R) < 0:
            raise ValueError("rotation matrix: not a rotation (orthonormal, determinant +1)")
        return R
    if "euler_deg" in spec:
        a, b, c = np.radians(spec["euler_deg"])
        Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
        Ry = np.array([[np.cos(c), 0, np.sin(c)], [0, 1, 0], [-np.sin(c), 0, np.cos(c)]])
        return Ry @ Rx @ Rz
    if "axis" in spec:
        k = np.asarray(spec["axis"], float)
        k = k / np.linalg.norm(k)
        a = np.radians(spec["angle_deg"])
        K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K
    raise ValueError(f"rotation: unknown form {spec!r}")


def _rot_spec(R):
    return None if np.allclose(R, np.eye(3)) else {"matrix": np.round(R, 12).tolist()}


# --------------------------------------------------------------------------------------------- base
class Shape:
    kind = "shape"

    def __init__(self, position=(0.0, 0.0, 0.0), rotation_=None):
        self.t = np.asarray(position, float).reshape(3)
        self.R = rotation(rotation_)

    # parent frame <-> local frame
    def to_local(self, p):
        return (np.asarray(p, float) - self.t) @ self.R

    def intervals(self, o, d):
        """Intervals of the rays o + t d (parent frame; d unit vectors) inside the shape."""
        o = np.atleast_2d(np.asarray(o, float)); d = np.atleast_2d(np.asarray(d, float))
        n = len(o)
        c, r = self.bounding_sphere()
        tc = np.einsum("ij,ij->i", c - o, d)
        dist2 = np.einsum("ij,ij->i", o + tc[:, None] * d - c, o + tc[:, None] * d - c)
        hit = np.flatnonzero(dist2 <= r * r * (1 + 1e-9) + 1e-18) if np.isfinite(r) else np.arange(n)
        if not len(hit):
            return IntervalSet.empty(n)
        sub = self._local(self.to_local(o[hit]), d[hit] @ self.R)
        return sub.put(hit, n)

    def inside(self, p):
        return self._inside_local(self.to_local(np.atleast_2d(p)))

    def bounds(self):
        lo, hi = self._local_bounds()
        if not (np.isfinite(lo).all() and np.isfinite(hi).all()):
            return lo, hi
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        w = corners @ self.R.T + self.t
        return w.min(axis=0), w.max(axis=0)

    def bounding_sphere(self):
        """Center (parent frame) and radius of a sphere around the shape."""
        lo, hi = self._local_bounds()
        if not (np.isfinite(lo).all() and np.isfinite(hi).all()):
            return self.t, np.inf
        c = 0.5 * (lo + hi)
        return self.t + self.R @ c, 0.5 * float(np.linalg.norm(hi - lo))

    def volume(self):
        return None

    def pose_dict(self):
        d = {}
        if np.any(self.t):
            d["position"] = [float(x) for x in np.round(self.t, 9)]
        r = _rot_spec(self.R)
        if r:
            d["rotation"] = r
        return d

    # to override
    def _local(self, o, d):
        raise NotImplementedError

    def _inside_local(self, p):
        """Default: a line through each point (along a direction not parallel to any face) and its intervals."""
        dirn = np.array([0.6247, 0.4567, 0.6331]); dirn /= np.linalg.norm(dirn)
        n = len(p)
        iv = self._local(p, np.tile(dirn, (n, 1)))
        hit = (iv.t0 <= 0) & (iv.t1 >= 0)
        out = np.zeros(n, bool)
        out[iv.ray[hit]] = True
        return out

    def _local_bounds(self):
        raise NotImplementedError


def _ivs(n, mask, t0, t1):
    k = np.flatnonzero(mask)
    return IntervalSet(k, t0[k], t1[k], n, normalized=True)


def _slab(n, o, d, lo, hi):
    """Interval of each ray inside lo <= x <= hi along one axis (o, d: that component)."""
    par = np.abs(d) < EPS
    with np.errstate(divide="ignore", invalid="ignore"):
        ta, tb = (lo - o) / d, (hi - o) / d
    t0 = np.where(par, -np.inf, np.minimum(ta, tb))
    t1 = np.where(par, np.inf, np.maximum(ta, tb))
    ok = ~par | ((o >= lo) & (o <= hi))
    return t0, t1, ok


# --------------------------------------------------------------------------------------------- primitives
@register
class Box(Shape):
    """A rectangular block of size [sx, sy, sz], centered. Exact (slab method)."""
    kind = "box"

    def __init__(self, size, **pose):
        super().__init__(**_pose(pose))
        self.size = np.asarray(size, float)
        self.h = 0.5 * self.size

    def _local(self, o, d):
        n = len(o)
        t0, t1, ok = np.full(n, -np.inf), np.full(n, np.inf), np.ones(n, bool)
        for a in range(3):
            a0, a1, k = _slab(n, o[:, a], d[:, a], -self.h[a], self.h[a])
            t0, t1, ok = np.maximum(t0, a0), np.minimum(t1, a1), ok & k
        return _ivs(n, ok & (t1 > t0), t0, t1)

    def _inside_local(self, p):
        return (np.abs(p) <= self.h).all(axis=1)

    def _local_bounds(self):
        return -self.h, self.h

    def volume(self):
        return float(np.prod(self.size))

    def to_dict(self):
        return dict(type=self.kind, size=self.size.tolist(), **self.pose_dict())


@register
class Ellipsoid(Shape):
    """An ellipsoid of axes [sx, sy, sz] (full lengths), centered. Exact (quadric)."""
    kind = "ellipsoid"

    def __init__(self, size, **pose):
        super().__init__(**_pose(pose))
        self.size = np.asarray(size, float).reshape(-1)
        if self.size.size == 1:
            self.size = np.repeat(self.size, 3)
        self.a = 0.5 * self.size

    def _local(self, o, d):
        n = len(o)
        oa, da = o / self.a, d / self.a
        A = (da * da).sum(axis=1)
        B = 2 * (oa * da).sum(axis=1)
        C = (oa * oa).sum(axis=1) - 1
        disc = B * B - 4 * A * C
        ok = disc > 0
        s = np.sqrt(np.where(ok, disc, 0))
        return _ivs(n, ok, (-B - s) / (2 * A), (-B + s) / (2 * A))

    def _inside_local(self, p):
        return ((p / self.a) ** 2).sum(axis=1) <= 1

    def _local_bounds(self):
        return -self.a, self.a

    def volume(self):
        return float(np.pi / 6 * np.prod(self.size))

    def to_dict(self):
        return dict(type=self.kind, size=self.size.tolist(), **self.pose_dict())


@register
class Sphere(Ellipsoid):
    kind = "sphere"

    def __init__(self, diameter, **pose):
        super().__init__([diameter] * 3, **pose)
        self.diameter = float(diameter)

    def to_dict(self):
        return dict(type=self.kind, diameter=self.diameter, **self.pose_dict())


@register
class Cylinder(Shape):
    """A cylinder of diameter and height, its axis along local y, centered. Exact."""
    kind = "cylinder"

    def __init__(self, diameter, height, **pose):
        super().__init__(**_pose(pose))
        self.diameter, self.height = float(diameter), float(height)
        self.r, self.hh = 0.5 * self.diameter, 0.5 * self.height

    def _local(self, o, d):
        n = len(o)
        A = d[:, 0] ** 2 + d[:, 2] ** 2
        B = 2 * (o[:, 0] * d[:, 0] + o[:, 2] * d[:, 2])
        C = o[:, 0] ** 2 + o[:, 2] ** 2 - self.r ** 2
        par = A < EPS
        disc = B * B - 4 * A * C
        s = np.sqrt(np.clip(disc, 0, None))
        with np.errstate(divide="ignore", invalid="ignore"):
            r0 = np.where(par, -np.inf, (-B - s) / (2 * A))
            r1 = np.where(par, np.inf, (-B + s) / (2 * A))
        okr = np.where(par, C <= 0, disc > 0)
        y0, y1, oky = _slab(n, o[:, 1], d[:, 1], -self.hh, self.hh)
        t0, t1 = np.maximum(r0, y0), np.minimum(r1, y1)
        return _ivs(n, okr & oky & (t1 > t0), t0, t1)

    def _inside_local(self, p):
        return (p[:, 0] ** 2 + p[:, 2] ** 2 <= self.r ** 2) & (np.abs(p[:, 1]) <= self.hh)

    def _local_bounds(self):
        return np.array([-self.r, -self.hh, -self.r]), np.array([self.r, self.hh, self.r])

    def volume(self):
        return float(np.pi * self.r ** 2 * self.height)

    def to_dict(self):
        return dict(type=self.kind, diameter=self.diameter, height=self.height, **self.pose_dict())


@register
class Cone(Shape):
    """A truncated cone (frustum): diameter_bottom at y = −height/2, diameter_top at +height/2, axis along local y.
    Exact (quadric of the double cone, cut by the two planes)."""
    kind = "cone"

    def __init__(self, diameter_bottom, diameter_top, height, **pose):
        super().__init__(**_pose(pose))
        self.d0, self.d1, self.height = float(diameter_bottom), float(diameter_top), float(height)
        self.hh = 0.5 * self.height
        self.beta = (self.d1 - self.d0) / 2 / self.height
        self.alpha = (self.d0 + self.d1) / 4

    def _local(self, o, d):
        n = len(o)
        al, be = self.alpha, self.beta
        ry0 = al + be * o[:, 1]
        A = d[:, 0] ** 2 + d[:, 2] ** 2 - be * be * d[:, 1] ** 2
        B = 2 * (o[:, 0] * d[:, 0] + o[:, 2] * d[:, 2] - be * d[:, 1] * ry0)
        C = o[:, 0] ** 2 + o[:, 2] ** 2 - ry0 ** 2
        disc = B * B - 4 * A * C
        s = np.sqrt(np.clip(disc, 0, None))
        lin = np.abs(A) < EPS
        with np.errstate(divide="ignore", invalid="ignore"):
            q0, q1 = (-B - s) / (2 * A), (-B + s) / (2 * A)
            lo_, hi_ = np.minimum(q0, q1), np.maximum(q0, q1)
            tl = -C / B
        rays, a0, a1 = [], [], []
        # A > 0: between the roots; A < 0: outside them (two half-lines), or everywhere if no root
        m = ~lin & (A > 0) & (disc > 0)
        rays.append(np.flatnonzero(m)); a0.append(lo_[m]); a1.append(hi_[m])
        m = ~lin & (A < 0) & (disc > 0)
        rays += [np.flatnonzero(m)] * 2; a0 += [np.full(m.sum(), -np.inf), hi_[m]]; a1 += [lo_[m], np.full(m.sum(), np.inf)]
        m = ~lin & (A < 0) & (disc <= 0)
        rays.append(np.flatnonzero(m)); a0.append(np.full(m.sum(), -np.inf)); a1.append(np.full(m.sum(), np.inf))
        m = lin & (np.abs(B) > EPS)
        rays.append(np.flatnonzero(m))
        a0.append(np.where(B[m] > 0, -np.inf, tl[m])); a1.append(np.where(B[m] > 0, tl[m], np.inf))
        m = lin & (np.abs(B) <= EPS) & (C <= 0)
        rays.append(np.flatnonzero(m)); a0.append(np.full(m.sum(), -np.inf)); a1.append(np.full(m.sum(), np.inf))
        quad = IntervalSet(np.concatenate(rays), np.concatenate(a0), np.concatenate(a1), n)
        y0, y1, oky = _slab(n, o[:, 1], d[:, 1], -self.hh, self.hh)
        return quad & _ivs(n, oky, y0, y1)

    def _inside_local(self, p):
        r = self.alpha + self.beta * p[:, 1]
        return (p[:, 0] ** 2 + p[:, 2] ** 2 <= r * r) & (np.abs(p[:, 1]) <= self.hh) & (r >= 0)

    def _local_bounds(self):
        r = 0.5 * max(self.d0, self.d1)
        return np.array([-r, -self.hh, -r]), np.array([r, self.hh, r])

    def volume(self):
        r0, r1 = self.d0 / 2, self.d1 / 2
        return float(np.pi * self.height / 3 * (r0 * r0 + r0 * r1 + r1 * r1))

    def to_dict(self):
        return dict(type=self.kind, diameter_bottom=self.d0, diameter_top=self.d1, height=self.height,
                    **self.pose_dict())


@register
class HalfSpace(Shape):
    """The points p with n·p <= offset (local frame). Unbounded: to cut other shapes (intersection, difference)."""
    kind = "halfspace"

    def __init__(self, normal, offset=0.0, **pose):
        super().__init__(**_pose(pose))
        self.n = np.asarray(normal, float) / np.linalg.norm(normal)
        self.offset = float(offset)

    def _local(self, o, d):
        n = len(o)
        s = d @ self.n
        v = o @ self.n - self.offset
        par = np.abs(s) < EPS
        with np.errstate(divide="ignore", invalid="ignore"):
            ts = -v / s
        t0 = np.where(par, -np.inf, np.where(s > 0, -np.inf, ts))
        t1 = np.where(par, np.inf, np.where(s > 0, ts, np.inf))
        return _ivs(n, np.where(par, v <= 0, True), t0, t1)

    def _inside_local(self, p):
        return p @ self.n <= self.offset

    def _local_bounds(self):
        return np.full(3, -np.inf), np.full(3, np.inf)

    def to_dict(self):
        return dict(type=self.kind, normal=self.n.tolist(), offset=self.offset, **self.pose_dict())


def _kernel_set(n, out, cnt):
    K = out.shape[1]
    j = np.arange(K)[None, :] < cnt[:, None]
    ray = np.broadcast_to(np.arange(n)[:, None], (n, K))[j]
    return IntervalSet(ray, out[..., 0][j], out[..., 1][j], n, normalized=True)


class _Implicit(Shape):
    """A shape f(p) < 0 computed by kernels.implicit_chords (sampling step: `step`, then bisection)."""
    code = None

    def _params(self):
        raise NotImplementedError

    def _local(self, o, d):
        n = len(o)
        p, lk, lph, la, radius, step = self._params()
        K = 8
        while True:
            out, cnt = kernels.pick('implicit_chords', len(o))(self.code, np.ascontiguousarray(o), np.ascontiguousarray(d), p, lk, lph,
                                               la, radius, step, K)
            if cnt.max(initial=0) <= K:
                return _kernel_set(n, out, cnt)
            K = int(cnt.max())


_NOLUMPS = (np.zeros((1, 3)), np.zeros(1), np.zeros(1))
_BLOB_VOL = {}


@register
class Torus(_Implicit):
    """A torus about local y: major_diameter (of the circle through the center of the tube), minor_diameter (of the
    tube). Sampling step: a sixteenth of the tube's diameter, then bisection (exact to rounding)."""
    kind = "torus"
    code = 1

    def __init__(self, major_diameter, minor_diameter, **pose):
        super().__init__(**_pose(pose))
        self.D, self.dd = float(major_diameter), float(minor_diameter)

    def _params(self):
        R, r = self.D / 2, self.dd / 2
        return np.array([R, r, 0.0, 0.0]), *_NOLUMPS, R + r, self.dd / 16

    def _inside_local(self, p):
        R, r = self.D / 2, self.dd / 2
        return (np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2) - R) ** 2 + p[:, 1] ** 2 <= r * r

    def _local_bounds(self):
        R, r = self.D / 2, self.dd / 2
        return np.array([-R - r, -r, -R - r]), np.array([R + r, r, R + r])

    def volume(self):
        return float(2 * np.pi ** 2 * (self.D / 2) * (self.dd / 2) ** 2)

    def to_dict(self):
        return dict(type=self.kind, major_diameter=self.D, minor_diameter=self.dd, **self.pose_dict())


@register
class Superellipsoid(_Implicit):
    """|x/a|^e + |y/b|^e + |z/c|^e <= 1 (size = [2a, 2b, 2c]; e = 2: an ellipsoid; e → ∞: a box with sharper and
    sharper edges). Sampling step: a sixteenth of the smallest axis, then bisection."""
    kind = "superellipsoid"
    code = 2

    def __init__(self, size, exponent=4.0, **pose):
        super().__init__(**_pose(pose))
        self.size, self.e = np.asarray(size, float), float(exponent)

    def _params(self):
        a = self.size / 2
        return np.array([a[0], a[1], a[2], self.e]), *_NOLUMPS, float(np.linalg.norm(a)), float(a.min() / 16)

    def _inside_local(self, p):
        a = self.size / 2
        return (np.abs(p / a) ** self.e).sum(axis=1) <= 1

    def _local_bounds(self):
        return -self.size / 2, self.size / 2

    def volume(self):
        from math import gamma
        e = self.e
        return float(np.prod(self.size) * gamma(1 + 1 / e) ** 3 / gamma(1 + 3 / e))

    def to_dict(self):
        return dict(type=self.kind, size=self.size.tolist(), exponent=self.e, **self.pose_dict())


def lumps(seed):
    """The lumps of a blob: six plane waves on the unit sphere (directions, frequencies 1.5 to 3.5, phases, weights
    summing to 1) drawn from the seed (the same as rock_shapes, for the samples made before)."""
    rng = np.random.default_rng(int(seed))
    k = rng.normal(size=(6, 3))
    k = k / np.linalg.norm(k, axis=1)[:, None] * rng.uniform(1.5, 3.5, (6, 1))
    a = rng.uniform(0.5, 1.0, 6)
    return k, rng.uniform(0, 2 * np.pi, 6), a / a.sum()


@register
class Blob(_Implicit):
    """A lumpy grain or pebble: the ellipsoid of axes `size` whose radius is multiplied by 1 + w f(u), f a sum of six
    plane waves on the sphere (lumps(seed)); wobble w = 0: the ellipsoid, exact. Sampling step: a sixteenth of the
    smallest semi-axis, then bisection."""
    kind = "blob"
    code = 0

    def __init__(self, size, wobble=0.0, seed=0, **pose):
        super().__init__(**_pose(pose))
        self.size, self.w, self.seed = np.asarray(size, float), float(wobble), int(seed)
        self._ell = Ellipsoid(self.size) if not self.w else None
        self._lumps = lumps(self.seed)

    def _local(self, o, d):
        return self._ell._local(o, d) if self._ell else super()._local(o, d)

    def _params(self):
        a = self.size / 2
        return np.array([a[0], a[1], a[2], self.w]), *self._lumps, float(a.max() * (1 + abs(self.w))), float(a.min() / 16)

    def _inside_local(self, p):
        a = self.size / 2
        q = p / a
        rho = np.sqrt((q * q).sum(axis=1))
        u = q / np.where(rho > 0, rho, 1)[:, None]
        k, ph, w = self._lumps
        return rho < 1 + self.w * (np.sin(u @ k.T + ph) * w).sum(axis=1)

    def _local_bounds(self):
        h = self.size / 2 * (1 + abs(self.w))
        return -h, h

    def volume(self):
        v = np.pi / 6 * float(np.prod(self.size))
        if not self.w:
            return v
        # the mean of (1 + w f)³ over the directions of the unit sphere (Fibonacci grid of 20 000 points: 1e-6)
        key = (self.seed, self.w)
        if key not in _BLOB_VOL:
            i = np.arange(20000) + 0.5
            th, ph = np.arccos(1 - 2 * i / 20000), np.pi * (1 + 5 ** 0.5) * i
            u = np.c_[np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)]
            k, phs, w = self._lumps
            _BLOB_VOL[key] = float(np.mean((1 + self.w * (np.sin(u @ k.T + phs) * w).sum(axis=1)) ** 3))
        return v * _BLOB_VOL[key]

    def to_dict(self):
        return dict(type=self.kind, size=self.size.tolist(), wobble=self.w, seed=self.seed, **self.pose_dict())


@register
class Prism(Shape):
    """A polygon of the local x-y plane (vertices [[x, y], ...], in order, not closed) extruded over `thickness` along
    local z, centered. Exact (crossings with the edges)."""
    kind = "prism"

    def __init__(self, polygon, thickness, **pose):
        super().__init__(**_pose(pose))
        self.poly = np.ascontiguousarray(np.asarray(polygon, float))
        self.thickness = float(thickness)

    def _local(self, o, d):
        n = len(o)
        K = 8
        while True:
            out, cnt = kernels.pick('prism_chords', len(o))(np.ascontiguousarray(o), np.ascontiguousarray(d), self.poly,
                                            self.thickness / 2, K)
            if cnt.max(initial=0) <= K:
                return _kernel_set(n, out, cnt)
            K = int(cnt.max())

    def _inside_local(self, p):
        from matplotlib.path import Path
        return Path(self.poly).contains_points(p[:, :2]) & (np.abs(p[:, 2]) <= self.thickness / 2)

    def _local_bounds(self):
        lo, hi = self.poly.min(axis=0), self.poly.max(axis=0)
        return np.r_[lo, -self.thickness / 2], np.r_[hi, self.thickness / 2]

    def volume(self):
        x, y = self.poly[:, 0], self.poly[:, 1]
        return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) * self.thickness)

    def to_dict(self):
        return dict(type=self.kind, polygon=self.poly.tolist(), thickness=self.thickness, **self.pose_dict())


@register
class Mesh(Shape):
    """A closed triangle mesh (vertices [n, 3], faces [m, 3]; or a file: STL, OBJ, OFF, PLY, read by trimesh), in
    `unit` (mm by default). Exact to the triangles (bounding volume hierarchy, Möller–Trumbore). The mesh must be
    watertight (checked)."""
    kind = "mesh"

    def __init__(self, vertices=None, faces=None, file=None, unit_mm=1.0, center=False, **pose):
        super().__init__(**_pose(pose))
        self.file, self.unit_mm, self.center = file, float(unit_mm), bool(center)
        if file is not None:
            import trimesh
            m = trimesh.load_mesh(file, force="mesh")
            vertices, faces = np.asarray(m.vertices), np.asarray(m.faces)
        self.v = np.asarray(vertices, float) * self.unit_mm
        self.f = np.asarray(faces, np.int64)
        if self.center:
            self.v = self.v - self.v.mean(axis=0)
        self._check()
        self.tri = np.ascontiguousarray(self.v[self.f])
        self.bvh = kernels.build_bvh(self.tri)

    def _check(self):
        e = np.sort(np.concatenate([self.f[:, [0, 1]], self.f[:, [1, 2]], self.f[:, [2, 0]]]), axis=1)
        _, c = np.unique(e, axis=0, return_counts=True)
        if (c != 2).any():
            raise ValueError(f"mesh{' ' + self.file if self.file else ''}: not watertight ({(c != 2).sum()} edges not "
                             f"shared by exactly two faces)")
        if self.volume() <= 0:
            self.f = self.f[:, ::-1].copy()              # faces inward: turned outward

    def _local(self, o, d):
        n = len(o)
        K = 16
        lo, hi, left, right, first, count, order = self.bvh
        while True:
            out, cnt = kernels.pick('mesh_chords', len(o))(np.ascontiguousarray(o), np.ascontiguousarray(d), self.tri, lo, hi, left,
                                           right, first, count, order, K)
            if cnt.max(initial=0) <= K:
                return _kernel_set(n, out, cnt)
            K = int(cnt.max())

    def _local_bounds(self):
        return self.v.min(axis=0), self.v.max(axis=0)

    def volume(self):
        a, b, c = self.v[self.f[:, 0]], self.v[self.f[:, 1]], self.v[self.f[:, 2]]
        return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)

    def to_dict(self):
        if self.file:
            return dict(type=self.kind, file=self.file, unit_mm=self.unit_mm, center=self.center, **self.pose_dict())
        return dict(type=self.kind, vertices=self.v.tolist(), faces=self.f.tolist(), **self.pose_dict())


# --------------------------------------------------------------------------------------------- CSG
class _CSG(Shape):
    def __init__(self, children, **pose):
        super().__init__(**_pose(pose))
        self.children = [make(c) if isinstance(c, dict) else c for c in children]

    def _sets(self, o, d):
        return [c.intervals(o, d) for c in self.children]

    def to_dict(self):
        return dict(type=self.kind, of=[c.to_dict() for c in self.children], **self.pose_dict())


@register
class Union(_CSG):
    kind = "union"

    def _local(self, o, d):
        return combine(self._sets(o, d), lambda c: np.logical_or.reduce(c))

    def _inside_local(self, p):
        return np.logical_or.reduce([c.inside(p) for c in self.children])

    def _local_bounds(self):
        b = [c.bounds() for c in self.children]
        return np.min([x[0] for x in b], axis=0), np.max([x[1] for x in b], axis=0)


@register
class Intersection(_CSG):
    kind = "intersection"

    def _local(self, o, d):
        return combine(self._sets(o, d), lambda c: np.logical_and.reduce(c))

    def _inside_local(self, p):
        return np.logical_and.reduce([c.inside(p) for c in self.children])

    def _local_bounds(self):
        if getattr(self, "_lb", None) is None:
            b = [c.bounds() for c in self.children]
            lo, hi = np.max([x[0] for x in b], axis=0), np.min([x[1] for x in b], axis=0)
            half = [c for c in self.children if isinstance(c, HalfSpace)]
            if half and np.isfinite(lo).all() and np.isfinite(hi).all():
                # the box of the bounded children cut by the half-spaces (a convex polytope, e.g. a Voronoi cell):
                # its exact extent along x, y, z from 6 linear programs
                from scipy.optimize import linprog
                A = np.array([c.R @ c.n for c in half])
                b_ = np.array([c.offset + c.t @ (c.R @ c.n) for c in half])
                ext = []
                for a in range(3):
                    for sgn in (1, -1):
                        r = linprog(sgn * np.eye(3)[a], A_ub=A, b_ub=b_, bounds=list(zip(lo, hi)), method="highs")
                        ext.append(r.x[a] if r.status == 0 else (lo[a] if sgn > 0 else hi[a]))
                if all(np.isfinite(ext)):
                    lo, hi = np.array(ext[0::2]), np.array(ext[1::2])
                    hi = np.maximum(hi, lo)
            self._lb = (lo, hi)
        return self._lb


@register
class Difference(_CSG):
    """The first shape minus all the others."""
    kind = "difference"

    def _local(self, o, d):
        return combine(self._sets(o, d), lambda c: c[0] & ~np.logical_or.reduce(c[1:]))

    def _inside_local(self, p):
        return self.children[0].inside(p) & ~np.logical_or.reduce([c.inside(p) for c in self.children[1:]])

    def _local_bounds(self):
        return self.children[0].bounds()


# --------------------------------------------------------------------------------------------- from dicts
def _pose(kw):
    unknown = set(kw) - {"position", "rotation", "rotation_"}
    if unknown:
        raise TypeError(f"unknown parameters {sorted(unknown)}")
    return dict(position=kw.get("position", (0.0, 0.0, 0.0)),
                rotation_=kw["rotation"] if kw.get("rotation") is not None else kw.get("rotation_"))


def make(spec):
    """A shape from its description (as in the scene files): {type, ..., position, rotation}."""
    spec = dict(spec)
    kind = spec.pop("type")
    if kind not in REGISTRY:
        raise ValueError(f"unknown shape {kind!r}; shapes: {sorted(REGISTRY)}")
    cls = REGISTRY[kind]
    if kind in ("union", "intersection", "difference"):
        return cls(spec.pop("of"), **spec)
    return cls(**spec)


from . import natural  # noqa: E402,F401  (registers the shapes of natural samples)
