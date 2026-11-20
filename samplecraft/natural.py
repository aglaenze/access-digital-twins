"""Shapes of natural samples, as meshes: a sawn piece of rock (wavy sides and faces, rounded edges, a corner broken
off: the model of rock_shapes, lofted into a closed triangle mesh, which is then its exact definition)."""
import numpy as np

from .shapes import Mesh, register

_CACHE = {}


def _resample(poly, n):
    """A closed polygon resampled to n points evenly spaced along its perimeter (starting at its first point)."""
    p = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    u = np.linspace(0, s[-1], n, endpoint=False)
    return np.c_[np.interp(u, s, p[:, 0]), np.interp(u, s, p[:, 1])]


def sawn_piece(size_mm, seed, rows=480, n=160, **pose):
    return SawnPiece(size_mm, seed, rows, n, **pose)


def _sawn_mesh(size_mm, seed, rows, n):
    """A sawn piece of rock (width x, height y, thickness z [mm]) as a closed mesh: its cross-sections (x, z) at
    `rows` heights (denser near the rounded top and bottom), each resampled to n points, joined by triangles, the
    ends closed by fans."""
    import rock_shapes as rs
    w, h, t = (float(v) for v in size_mm)
    dims = (w * 1e-3, h * 1e-3, t * 1e-3, int(seed))
    # the heights where the piece exists
    ys = np.linspace(-0.6 * h, 0.6 * h, 4001) * 1e-3
    have = np.array([rs.slab_polygon(dims, y) is not None for y in ys])
    y0, y1 = ys[have][0], ys[have][-1]
    # rows: uniform in an angle (denser at both ends, where the section changes fast)
    u = np.linspace(0, np.pi, rows)
    yr = y0 + (y1 - y0) * (1 - np.cos(u)) / 2
    yr[0] += 1e-9; yr[-1] -= 1e-9
    secs = []
    for y in yr:
        poly = rs.slab_polygon(dims, y)
        if poly is None:
            continue
        secs.append((y, _resample(np.asarray(poly), n)))
    V = np.concatenate([np.c_[s[:, 0], np.full(n, y), s[:, 1]] for y, s in secs]) * 1e3
    nr = len(secs)
    F = []
    for r in range(nr - 1):
        a, b = r * n, (r + 1) * n
        for k in range(n):
            k1 = (k + 1) % n
            F.append([a + k, a + k1, b + k1])
            F.append([a + k, b + k1, b + k])
    c0, c1 = len(V), len(V) + 1                         # the ends: a fan from the center of the first/last section
    V = np.vstack([V, V[:n].mean(axis=0), V[(nr - 1) * n:].mean(axis=0)])
    for k in range(n):
        k1 = (k + 1) % n
        F.append([c0, k1, k])
        F.append([c1, (nr - 1) * n + k, (nr - 1) * n + k1])
    return V, np.array(F)


@register
class SawnPiece(Mesh):
    """A sawn piece of rock: width x, height y, thickness z [mm], a seed for its irregularities (wavy sides and faces,
    rounded edges, a corner broken off at the top). A closed mesh (exact), made once per size and seed."""
    kind = "sawn_piece"

    def __init__(self, size, seed=0, rows=480, n=160, **pose):
        key = (tuple(float(v) for v in size), int(seed), int(rows), int(n))
        if key not in _CACHE:
            _CACHE[key] = _sawn_mesh(size, seed, rows, n)
        V, F = _CACHE[key]
        super().__init__(V, F, **pose)
        self.size_mm, self.seed_, self.rows, self.n = [float(v) for v in size], int(seed), int(rows), int(n)

    def to_dict(self):
        return dict(type=self.kind, size=self.size_mm, seed=self.seed_, **self.pose_dict())
