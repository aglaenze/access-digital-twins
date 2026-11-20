"""Compiled ray kernels (numba). Each one works in the local frame of its shape, on N rays (origins o, unit directions
d, both [N, 3], mm), and returns the intervals crossed: an array [N, K, 2] (t entry, t exit) and the number of
intervals of each ray [N] (at most K; more is an error, reported by the caller).

* implicit shapes (f(p) < 0 inside): f sampled along the part of the ray inside a bounding sphere, every sign change
  refined by bisection to machine precision. A feature thinner than the sampling step could be missed: the callers
  choose the step from the smallest feature of the shape (documented with each shape).
* prism: a polygon (local x, y) extruded along local z: exact crossings with the edges.
* mesh: closed triangle mesh, bounding volume hierarchy, Möller–Trumbore; the hits sorted and paired.
* voxels: exact traversal of the grid (Amanatides & Woo 1987): the length in each label.
"""
import numpy as np
from numba import njit, prange

EPS = 1e-12

# ----------------------------------------------------------------------------------------------- implicit shapes
# kind 0: lumpy ellipsoid ("blob"): p0..p2 semi-axes, p3 wobble, lumps = (k [6, 3], phase [6], weight [6]);
#         f = |p / a| − (1 + w Σ_j c_j sin(u·k_j + φ_j)), u = (p/a)/|p/a|
# kind 1: torus about the local y axis: p0 = R (center of the tube), p1 = r (radius of the tube)
# kind 2: superellipsoid: p0..p2 semi-axes, p3 = e (exponent: 2 an ellipsoid, large: a box with rounded edges)


@njit(cache=True)
def _f(kind, x, y, z, p, lk, lph, la):
    if kind == 0:
        qx, qy, qz = x / p[0], y / p[1], z / p[2]
        rho = np.sqrt(qx * qx + qy * qy + qz * qz)
        if rho == 0.0:
            return -1.0
        ux, uy, uz = qx / rho, qy / rho, qz / rho
        s = 0.0
        for j in range(lk.shape[0]):
            s += la[j] * np.sin(ux * lk[j, 0] + uy * lk[j, 1] + uz * lk[j, 2] + lph[j])
        return rho - (1.0 + p[3] * s)
    elif kind == 1:
        a = np.sqrt(x * x + z * z) - p[0]
        return a * a + y * y - p[1] * p[1]
    else:
        e = p[3]
        return (abs(x / p[0]) ** e + abs(y / p[1]) ** e + abs(z / p[2]) ** e) ** (1.0 / e) - 1.0


@njit(cache=True)
def _root(kind, ox, oy, oz, dx, dy, dz, p, lk, lph, la, lo, hi, flo):
    """The crossing of f = 0 between lo and hi (f changes sign), by bisection to the last bit."""
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if mid == lo or mid == hi:
            break
        fm = _f(kind, ox + mid * dx, oy + mid * dy, oz + mid * dz, p, lk, lph, la)
        if (fm < 0.0) == (flo < 0.0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


@njit(cache=True)
def _scan(kind, ox, oy, oz, dx, dy, dz, p, lk, lph, la, ta, tb, step, buf):
    """Intervals where f < 0 on [ta, tb] (f > 0 at both ends) into buf [K, 2]; returns their number (may exceed K:
    the caller enlarges buf). f sampled every `step` at most; where three samples show a positive local minimum, the
    minimum is searched (golden section): if f < 0 there, the ray grazes a thin part between two samples, and its
    two crossings are found too."""
    K = buf.shape[0]
    m = int(np.ceil((tb - ta) / step)) + 1
    if m < 8:
        m = 8
    dt = (tb - ta) / (m - 1)
    t0 = ta
    f0 = _f(kind, ox + ta * dx, oy + ta * dy, oz + ta * dz, p, lk, lph, la)
    fprev = 1e300
    tin = ta
    k = 0
    for j in range(1, m):
        t1 = ta + j * dt
        f1 = _f(kind, ox + t1 * dx, oy + t1 * dy, oz + t1 * dz, p, lk, lph, la)
        if (f0 < 0.0) != (f1 < 0.0):
            tr = _root(kind, ox, oy, oz, dx, dy, dz, p, lk, lph, la, t0, t1, f0)
            if f1 < 0.0:
                tin = tr
            else:
                if k < K:
                    buf[k, 0] = tin
                    buf[k, 1] = tr
                k += 1
        elif f0 > 0.0 and f1 > 0.0 and fprev > f0 and f1 > f0:
            # a positive local minimum near t0: golden-section search on [t0 - dt, t0 + dt]
            a, b = t0 - dt, t0 + dt
            g = 0.3819660112501051
            c1, c2 = a + g * (b - a), b - g * (b - a)
            fc1 = _f(kind, ox + c1 * dx, oy + c1 * dy, oz + c1 * dz, p, lk, lph, la)
            fc2 = _f(kind, ox + c2 * dx, oy + c2 * dy, oz + c2 * dz, p, lk, lph, la)
            for _ in range(60):
                if fc1 < 0.0 or fc2 < 0.0:
                    break
                if fc1 < fc2:
                    b, c2, fc2 = c2, c1, fc1
                    c1 = a + g * (b - a)
                    fc1 = _f(kind, ox + c1 * dx, oy + c1 * dy, oz + c1 * dz, p, lk, lph, la)
                else:
                    a, c1, fc1 = c1, c2, fc2
                    c2 = b - g * (b - a)
                    fc2 = _f(kind, ox + c2 * dx, oy + c2 * dy, oz + c2 * dz, p, lk, lph, la)
                if b - a < 1e-12 * (1.0 + abs(a)):
                    break
            tm, fmn = (c1, fc1) if fc1 < fc2 else (c2, fc2)
            if fmn < 0.0:
                fa = _f(kind, ox + (t0 - dt) * dx, oy + (t0 - dt) * dy, oz + (t0 - dt) * dz, p, lk, lph, la)
                r0 = _root(kind, ox, oy, oz, dx, dy, dz, p, lk, lph, la, t0 - dt, tm, fa)
                r1 = _root(kind, ox, oy, oz, dx, dy, dz, p, lk, lph, la, tm, t1, fmn)
                if k < K:
                    buf[k, 0] = r0
                    buf[k, 1] = r1
                k += 1
        fprev = f0
        t0, f0 = t1, f1
    return k


@njit(cache=True, parallel=True)
def implicit_chords(kind, o, d, p, lk, lph, la, radius, step, K):
    n = o.shape[0]
    out = np.zeros((n, K, 2))
    cnt = np.zeros(n, np.int64)
    for i in prange(n):
        ox, oy, oz = o[i, 0], o[i, 1], o[i, 2]
        dx, dy, dz = d[i, 0], d[i, 1], d[i, 2]
        tc = -(ox * dx + oy * dy + oz * dz)
        cx, cy, cz = ox + tc * dx, oy + tc * dy, oz + tc * dz
        q = radius * radius - (cx * cx + cy * cy + cz * cz)
        if q <= 0.0:
            continue
        h = np.sqrt(q)
        cnt[i] = _scan(kind, ox, oy, oz, dx, dy, dz, p, lk, lph, la, tc - h, tc + h, step, out[i])
    return out, cnt


# ----------------------------------------------------------------------------------------------- prism
@njit(cache=True, parallel=True)
def prism_chords(o, d, poly, hz, K):
    """poly [n, 2]: closed polygon (local x, y; not repeated at the end), extruded over |z| <= hz."""
    n = o.shape[0]
    nv = poly.shape[0]
    out = np.zeros((n, K, 2))
    cnt = np.zeros(n, np.int64)
    for i in prange(n):
        ox, oy, oz = o[i, 0], o[i, 1], o[i, 2]
        dx, dy, dz = d[i, 0], d[i, 1], d[i, 2]
        # the slab |z| <= hz
        if abs(dz) < EPS:
            if abs(oz) > hz:
                continue
            za, zb = -np.inf, np.inf
        else:
            ta_ = (-hz - oz) / dz
            tb_ = (hz - oz) / dz
            za, zb = min(ta_, tb_), max(ta_, tb_)
        dxy = np.sqrt(dx * dx + dy * dy)
        if dxy < EPS:                                    # along z: is (ox, oy) in the polygon?
            c = False
            for e in range(nv):
                ax, ay = poly[e, 0], poly[e, 1]
                bx, by = poly[(e + 1) % nv, 0], poly[(e + 1) % nv, 1]
                if (ay > oy) != (by > oy):
                    xc = ax + (oy - ay) * (bx - ax) / (by - ay)
                    if xc > ox:
                        c = not c
            if c:
                out[i, 0, 0] = za
                out[i, 0, 1] = zb
                cnt[i] = 1
            continue
        ts = np.empty(nv)
        m = 0
        for e in range(nv):
            ax, ay = poly[e, 0], poly[e, 1]
            ex, ey = poly[(e + 1) % nv, 0] - ax, poly[(e + 1) % nv, 1] - ay
            den = dx * ey - dy * ex
            if abs(den) < EPS:
                continue
            wx, wy = ax - ox, ay - oy
            t = (wx * ey - wy * ex) / den
            s = (wx * dy - wy * dx) / den
            if s >= 0.0 and s < 1.0:
                ts[m] = t
                m += 1
        ts = np.sort(ts[:m])
        k = 0
        for j in range(0, m - 1, 2):
            a, b = max(ts[j], za), min(ts[j + 1], zb)
            if b > a:
                if k < K:
                    out[i, k, 0] = a
                    out[i, k, 1] = b
                k += 1
        cnt[i] = k
    return out, cnt


# ----------------------------------------------------------------------------------------------- mesh
@njit(cache=True, parallel=True)
def mesh_chords(o, d, tri, node_lo, node_hi, node_left, node_right, node_first, node_count, order, K):
    """tri [m, 3, 3]: triangles; BVH nodes (box lo/hi, children, or a leaf: first/count in `order`)."""
    n = o.shape[0]
    out = np.zeros((n, K, 2))
    cnt = np.zeros(n, np.int64)
    for i in prange(n):
        ox, oy, oz = o[i, 0], o[i, 1], o[i, 2]
        dx, dy, dz = d[i, 0], d[i, 1], d[i, 2]
        ix = 1.0 / dx if abs(dx) > EPS else 1e300
        iy = 1.0 / dy if abs(dy) > EPS else 1e300
        iz = 1.0 / dz if abs(dz) > EPS else 1e300
        hits = np.empty(4 * K)
        nh = 0
        stack = np.empty(128, np.int64)
        sp = 0
        stack[0] = 0
        sp = 1
        while sp > 0:
            sp -= 1
            nd = stack[sp]
            # slab test of the node's box (the whole line: t in (-inf, inf))
            t0x, t1x = (node_lo[nd, 0] - ox) * ix, (node_hi[nd, 0] - ox) * ix
            t0y, t1y = (node_lo[nd, 1] - oy) * iy, (node_hi[nd, 1] - oy) * iy
            t0z, t1z = (node_lo[nd, 2] - oz) * iz, (node_hi[nd, 2] - oz) * iz
            if abs(dx) <= EPS and (ox < node_lo[nd, 0] or ox > node_hi[nd, 0]):
                continue
            if abs(dy) <= EPS and (oy < node_lo[nd, 1] or oy > node_hi[nd, 1]):
                continue
            if abs(dz) <= EPS and (oz < node_lo[nd, 2] or oz > node_hi[nd, 2]):
                continue
            tmin, tmax = -1e300, 1e300
            if abs(dx) > EPS:
                tmin = max(tmin, min(t0x, t1x)); tmax = min(tmax, max(t0x, t1x))
            if abs(dy) > EPS:
                tmin = max(tmin, min(t0y, t1y)); tmax = min(tmax, max(t0y, t1y))
            if abs(dz) > EPS:
                tmin = max(tmin, min(t0z, t1z)); tmax = min(tmax, max(t0z, t1z))
            if tmax < tmin:
                continue
            if node_count[nd] > 0:
                for q in range(node_first[nd], node_first[nd] + node_count[nd]):
                    f = order[q]
                    v0x, v0y, v0z = tri[f, 0, 0], tri[f, 0, 1], tri[f, 0, 2]
                    e1x, e1y, e1z = tri[f, 1, 0] - v0x, tri[f, 1, 1] - v0y, tri[f, 1, 2] - v0z
                    e2x, e2y, e2z = tri[f, 2, 0] - v0x, tri[f, 2, 1] - v0y, tri[f, 2, 2] - v0z
                    px, py, pz = dy * e2z - dz * e2y, dz * e2x - dx * e2z, dx * e2y - dy * e2x
                    det = e1x * px + e1y * py + e1z * pz
                    if abs(det) < 1e-300:
                        continue
                    inv = 1.0 / det
                    sx, sy, sz = ox - v0x, oy - v0y, oz - v0z
                    u = (sx * px + sy * py + sz * pz) * inv
                    if u < 0.0 or u > 1.0:
                        continue
                    qx, qy, qz = sy * e1z - sz * e1y, sz * e1x - sx * e1z, sx * e1y - sy * e1x
                    v = (dx * qx + dy * qy + dz * qz) * inv
                    if v < 0.0 or u + v > 1.0:
                        continue
                    t = (e2x * qx + e2y * qy + e2z * qz) * inv
                    if nh < hits.shape[0]:
                        hits[nh] = t
                    nh += 1
            else:
                if sp + 2 <= stack.shape[0]:
                    stack[sp] = node_left[nd]
                    stack[sp + 1] = node_right[nd]
                    sp += 2
        m = min(nh, hits.shape[0])
        h = np.sort(hits[:m])
        # a hit on a shared edge or vertex is found twice: merge hits closer than 1e-9 mm
        u_ = np.empty(m)
        nu = 0
        for j in range(m):
            if nu == 0 or h[j] - u_[nu - 1] > 1e-9:
                u_[nu] = h[j]
                nu += 1
        if nu % 2 == 1:                                  # grazing a vertex or an edge: drop that ray's last hit
            nu -= 1
        k = 0
        for j in range(0, nu, 2):
            if k < K:
                out[i, k, 0] = u_[j]
                out[i, k, 1] = u_[j + 1]
            k += 1
        cnt[i] = k
    return out, cnt


def build_bvh(tri, leaf=8):
    """Bounding volume hierarchy of triangles [m, 3, 3] (median split on the longest axis of the centroids)."""
    m = len(tri)
    cen = tri.mean(axis=1)
    lo_t, hi_t = tri.min(axis=1), tri.max(axis=1)
    order = np.arange(m)
    nodes = []                                           # [lo, hi, left, right, first, count]

    def make(first, count):
        idx = order[first:first + count]
        lo, hi = lo_t[idx].min(axis=0), hi_t[idx].max(axis=0)
        k = len(nodes)
        nodes.append([lo, hi, -1, -1, first, count])
        if count > leaf:
            c = cen[idx]
            ax = int(np.argmax(c.max(axis=0) - c.min(axis=0)))
            srt = idx[np.argsort(c[:, ax], kind="stable")]
            order[first:first + count] = srt
            half = count // 2
            nodes[k][4], nodes[k][5] = 0, 0
            nodes[k][2] = make(first, half)
            nodes[k][3] = make(first + half, count - half)
        return k

    import sys
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    make(0, m)
    lo = np.array([n[0] for n in nodes]); hi = np.array([n[1] for n in nodes])
    left = np.array([n[2] for n in nodes], np.int64); right = np.array([n[3] for n in nodes], np.int64)
    first = np.array([n[4] for n in nodes], np.int64); count = np.array([n[5] for n in nodes], np.int64)
    return lo, hi, left, right, first, count, order


# ----------------------------------------------------------------------------------------------- voxels
@njit(cache=True, parallel=True)
def voxel_lengths(o, d, labels, vsize, n_labels):
    """Lengths [N, n_labels] crossed in each label of a grid labels[nx, ny, nz] of voxels vsize [3] (mm), its corner
    at the origin of the local frame (label 0 counts too: the caller ignores it if it is empty space)."""
    n = o.shape[0]
    nx, ny, nz = labels.shape
    out = np.zeros((n, n_labels))
    size = np.array([nx * vsize[0], ny * vsize[1], nz * vsize[2]])
    dims = np.array([nx, ny, nz])
    for i in prange(n):
        t_enter, t_exit = -1e300, 1e300
        ok = True
        for a in range(3):
            if abs(d[i, a]) < EPS:
                if o[i, a] < 0.0 or o[i, a] > size[a]:
                    ok = False
            else:
                ta, tb = (0.0 - o[i, a]) / d[i, a], (size[a] - o[i, a]) / d[i, a]
                t_enter = max(t_enter, min(ta, tb))
                t_exit = min(t_exit, max(ta, tb))
        if not ok or t_exit <= t_enter:
            continue
        cell = np.empty(3, np.int64)
        step = np.empty(3, np.int64)
        tmax = np.empty(3)
        tdel = np.empty(3)
        t = t_enter
        for a in range(3):
            pa = o[i, a] + (t + 1e-12 * max(1.0, abs(t))) * d[i, a]
            c = int(np.floor(pa / vsize[a]))
            c = min(max(c, 0), dims[a] - 1)
            cell[a] = c
            if d[i, a] > EPS:
                step[a] = 1
                tmax[a] = ((c + 1) * vsize[a] - o[i, a]) / d[i, a]
                tdel[a] = vsize[a] / d[i, a]
            elif d[i, a] < -EPS:
                step[a] = -1
                tmax[a] = (c * vsize[a] - o[i, a]) / d[i, a]
                tdel[a] = -vsize[a] / d[i, a]
            else:
                step[a] = 0
                tmax[a] = 1e300
                tdel[a] = 1e300
        while t < t_exit:
            a = 0
            if tmax[1] < tmax[a]:
                a = 1
            if tmax[2] < tmax[a]:
                a = 2
            t_next = min(tmax[a], t_exit)
            out[i, labels[cell[0], cell[1], cell[2]]] += t_next - t
            t = t_next
            cell[a] += step[a]
            if cell[a] < 0 or cell[a] >= dims[a]:
                break
            tmax[a] += tdel[a]
    return out


# the same kernels compiled without threads: for a few rays, starting the threads costs more than the work
_SERIAL = {}


def pick(name, n, threshold=4096):
    """The kernel `name`, parallel for many rays, serial for few."""
    f = globals()[name]
    if n >= threshold:
        return f
    if name not in _SERIAL:
        _SERIAL[name] = njit(cache=True)(f.py_func)
    return _SERIAL[name]


@njit(cache=True, parallel=True)
def voxel_segments(o, d, labels, vsize, K):
    """The stretches of each ray through voxels of label != 0 (consecutive voxels of a label merged): [N, K, 2] (t0,
    t1), their labels [N, K], their number [N]."""
    n = o.shape[0]
    nx, ny, nz = labels.shape
    out = np.zeros((n, K, 2))
    lab = np.zeros((n, K), np.int64)
    cnt = np.zeros(n, np.int64)
    size = np.array([nx * vsize[0], ny * vsize[1], nz * vsize[2]])
    dims = np.array([nx, ny, nz])
    for i in prange(n):
        t_enter, t_exit = -1e300, 1e300
        ok = True
        for a in range(3):
            if abs(d[i, a]) < EPS:
                if o[i, a] < 0.0 or o[i, a] > size[a]:
                    ok = False
            else:
                ta, tb = (0.0 - o[i, a]) / d[i, a], (size[a] - o[i, a]) / d[i, a]
                t_enter = max(t_enter, min(ta, tb))
                t_exit = min(t_exit, max(ta, tb))
        if not ok or t_exit <= t_enter:
            continue
        cell = np.empty(3, np.int64)
        step = np.empty(3, np.int64)
        tmax = np.empty(3)
        tdel = np.empty(3)
        t = t_enter
        for a in range(3):
            pa = o[i, a] + (t + 1e-12 * max(1.0, abs(t))) * d[i, a]
            c = int(np.floor(pa / vsize[a]))
            c = min(max(c, 0), dims[a] - 1)
            cell[a] = c
            if d[i, a] > EPS:
                step[a] = 1
                tmax[a] = ((c + 1) * vsize[a] - o[i, a]) / d[i, a]
                tdel[a] = vsize[a] / d[i, a]
            elif d[i, a] < -EPS:
                step[a] = -1
                tmax[a] = (c * vsize[a] - o[i, a]) / d[i, a]
                tdel[a] = -vsize[a] / d[i, a]
            else:
                step[a] = 0
                tmax[a] = 1e300
                tdel[a] = 1e300
        k = 0
        cur = 0
        start = 0.0
        while t < t_exit:
            a = 0
            if tmax[1] < tmax[a]:
                a = 1
            if tmax[2] < tmax[a]:
                a = 2
            t_next = min(tmax[a], t_exit)
            l = labels[cell[0], cell[1], cell[2]]
            if l != cur:
                if cur != 0:
                    if k < K:
                        out[i, k, 0] = start
                        out[i, k, 1] = t
                        lab[i, k] = cur
                    k += 1
                cur = l
                start = t
            t = t_next
            cell[a] += step[a]
            if cell[a] < 0 or cell[a] >= dims[a]:
                break
            tmax[a] += tdel[a]
        if cur != 0:
            if k < K:
                out[i, k, 0] = start
                out[i, k, 1] = t
                lab[i, k] = cur
            k += 1
        cnt[i] = k
    return out, lab, cnt


@njit(cache=True, parallel=True)
def blob_pairs(o, d, ray, body, cen, rot, semi, wob, lk, lph, la, step, isbox):
    """Length of ray ray[q] inside blob body[q] (an ellipsoid if its wobble is 0: exact; else f sampled every
    step[b] along the chord of the ellipsoid inflated by the largest lump, sign changes refined by bisection), for
    many (ray, blob) pairs at once."""
    m = ray.shape[0]
    out = np.zeros(m)
    for q in prange(m):
        i, b = ray[q], body[q]
        # the ray in the blob's frame, scaled to the unit sphere
        px, py, pz = o[i, 0] - cen[b, 0], o[i, 1] - cen[b, 1], o[i, 2] - cen[b, 2]
        ox = (px * rot[b, 0, 0] + py * rot[b, 1, 0] + pz * rot[b, 2, 0])
        oy = (px * rot[b, 0, 1] + py * rot[b, 1, 1] + pz * rot[b, 2, 1])
        oz = (px * rot[b, 0, 2] + py * rot[b, 1, 2] + pz * rot[b, 2, 2])
        dx = (d[i, 0] * rot[b, 0, 0] + d[i, 1] * rot[b, 1, 0] + d[i, 2] * rot[b, 2, 0])
        dy = (d[i, 0] * rot[b, 0, 1] + d[i, 1] * rot[b, 1, 1] + d[i, 2] * rot[b, 2, 1])
        dz = (d[i, 0] * rot[b, 0, 2] + d[i, 1] * rot[b, 1, 2] + d[i, 2] * rot[b, 2, 2])
        ax, ay, az = semi[b, 0], semi[b, 1], semi[b, 2]
        if isbox[b]:                                     # a box: slab method
            t0, t1 = -1e300, 1e300
            ok = True
            for (oo, dd, hh) in ((ox, dx, ax), (oy, dy, ay), (oz, dz, az)):
                if abs(dd) < EPS:
                    if abs(oo) > hh:
                        ok = False
                else:
                    u0, u1 = (-hh - oo) / dd, (hh - oo) / dd
                    t0 = max(t0, min(u0, u1))
                    t1 = min(t1, max(u0, u1))
            if ok and t1 > t0:
                out[q] = t1 - t0
            continue
        A = (dx / ax) ** 2 + (dy / ay) ** 2 + (dz / az) ** 2
        B = 2.0 * (ox * dx / (ax * ax) + oy * dy / (ay * ay) + oz * dz / (az * az))
        C = (ox / ax) ** 2 + (oy / ay) ** 2 + (oz / az) ** 2
        w = wob[b]
        if w == 0.0:
            disc = B * B - 4.0 * A * (C - 1.0)
            if disc > 0.0:
                out[q] = np.sqrt(disc) / A
            continue
        kmax = 1.0 + abs(w)
        disc = B * B - 4.0 * A * (C - kmax * kmax)
        if disc <= 0.0:
            continue
        s = np.sqrt(disc)
        ta, tb = (-B - s) / (2.0 * A), (-B + s) / (2.0 * A)
        p = np.array([ax, ay, az, w])
        buf = np.zeros((16, 2))
        k = _scan(0, ox, oy, oz, dx, dy, dz, p, lk[b], lph[b], la[b], ta, tb, step[b], buf)
        total = 0.0
        for j in range(min(k, 16)):
            total += buf[j, 1] - buf[j, 0]
        out[q] = total
    return out
