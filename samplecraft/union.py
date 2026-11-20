"""Export of a scene to McStas Union (Bertelsen et al.): the same sample simulated by a full Monte Carlo transport
(scattering, multiple scattering, absorption from NCrystal) to check, or go beyond, the path-length model.

    from samplecraft import union
    out = union.export(scene, "C:/runs/union_check")       # no spaces in the path (McStas)
    out["instrument"]          # a test instrument: a parallel beam through the sample, the transmission measured
    out["sample_part"]         # the materials and volumes alone, to paste into any instrument (TRACE section)
    out["as_exported"]         # the scene with the shapes exactly as Union sees them (to compare like with like)
    out["shapes"]              # per body: how it was exported, and the volume of the export against the exact one
    out["union_lib"]           # with meshes: a copy of McStas union-lib.c without its memory leak (see _LEAK), or None

How each shape goes to Union (each body: one Union volume, plus masks; a child has a higher priority than its
parent, so it replaces the parent's material on its part, as in samplecraft):
* sphere, box, cylinder, cone (any rotation: ROTATED): Union_sphere, _box, _cylinder, _cone (exact);
* mesh, sawn piece: Union_mesh of their own triangles (exact);
* intersection of boxes and half-spaces (a convex polyhedron: a Voronoi cell, a chamfered block): the mesh of the
  polyhedron, its faces 100 nm inside (CELL_INSET_MM: neighboring cells share faces, which Union cannot trace);
* intersection A ∩ B ∩ ...: A, restricted by Union masks B, ... (mask_setting "All": exact if each is exact);
* difference A − B − ...: A, and inside it (masked by a copy of A) B, ... made of the material around the body (its
  parent's, or vacuum), above A in priority (exact if each is exact);
* a half-space (in a difference or an intersection): a box of 1 m, one face on its plane (exact);
* ellipsoid, blob, superellipsoid (shapes seen whole from their center): a mesh whose vertices are exact points of
  the surface along the directions of a subdivided icosahedron, scaled about the center so that the volume is
  exact (the scale is in `shapes`);
* torus, prism, unions, nested constructions: a mesh by marching cubes on a fine grid (the volume error printed);
* voxel bodies: not exported (a tomogram has millions of voxels; Union would need one volume per region).
Materials: Union_NCrystal_material with the scene's NCrystal configuration (the void: Vacuum).
McStas ROTATED (a, b, c) is the matrix T (lab -> local) of mccode-r.c rot_set_rotation; samplecraft's R maps
local -> parent, so T = Rᵀ.
"""
import copy
import os
import re

import numpy as np

from . import shapes as S
from .scene import Body, Scene, VoxelBody

MAX_VOLUMES = 1000         # Union slows down with many volumes: beyond, export a simpler scene (fewer, larger grains)
MASK_PAD_MM = 1e-4         # masks 100 nm larger than the body they copy: no surfaces on top of each other (Union
                           # loses rays on coinciding surfaces); what they let through is the material around anyway
CELL_INSET_MM = 1e-4       # convex polyhedra 100 nm inside on every face: the cells of a polycrystal share their faces
                           # with each other and with their host, and Union stops after 100 rays lost on such faces
                           # (the 200 nm left between two cells keep the host's material; the volume error is printed)
HOLDER_INSET_MM = 1e-4     # holders (sphere, box, cylinder, cone) 100 nm smaller on every face: a holder touches the
                           # sample (a plate on its base), and on that shared face Union lost 1 scattered ray in 200
                           # (duplex steel, 2026-11-20); the exact smaller holder is in as_exported


def _shrunk(shape, d):
    """A sphere, box, cylinder or cone `d` mm smaller on every face (same pose); None for other shapes."""
    pose = dict(position=shape.t, rotation_=shape.R)
    if isinstance(shape, S.Sphere):
        return S.Sphere(shape.diameter - 2 * d, **pose)
    if isinstance(shape, S.Box):
        return S.Box(shape.size - 2 * d, **pose)
    if isinstance(shape, S.Cylinder):
        return S.Cylinder(shape.diameter - 2 * d, shape.height - 2 * d, **pose)
    if isinstance(shape, S.Cone):    # radius r(z) = r0 + βz; the side moved by d along its normal: r - d√(1+β²);
        b = (shape.d1 - shape.d0) / 2 / shape.height    # the bases moved by d: r0 + βd at the bottom, r1 − βd at the top
        k = 2 * d * np.sqrt(1 + b * b)
        return S.Cone(shape.d0 + 2 * b * d - k, shape.d1 - 2 * b * d - k, shape.height - 2 * d, **pose)
    return None


# McStas 3.9.2 (union-lib.c, r_within_mesh) allocates two arrays it never uses nor frees, at every "is this point
# inside the mesh?" test: Union makes this test for every mesh at every neutron, about 200 kB per neutron with 400
# grains (20 GB per process for 10⁵ neutrons: the computer stopped, 2026-11-20). McStas reads the files of the
# instrument's folder before its own: a corrected copy is written there. Fixed upstream in McStas 3.10.0
# (r_within_mesh rewritten): with it, the pattern is not found and nothing is written.
_LEAK = re.compile(r"(int r_within_mesh\(.*?)\n\s*double \*t_intersect=malloc\(n_facets\*sizeof\(double\)\);\s*\n"
                   r"\s*int \*facet_index = malloc\(n_facets\*sizeof\(int\)\);\s*\n\s*if \(!t_intersect \|\| "
                   r"!facet_index\) \{.*?\n\s*\}\n", re.S)


def _union_lib_fixed(out_dir):
    """Writes <out_dir>/union-lib.c without the memory leak of r_within_mesh, if the installed one has it. Returns
    the path written, or None (library not found, or already corrected)."""
    import shutil
    import sys
    roots = [os.path.join(sys.prefix, "share", "mcstas")]
    exe = shutil.which("mcrun")
    if exe:
        roots.append(os.path.join(os.path.dirname(os.path.dirname(exe)), "share", "mcstas"))
    for r in roots:
        src = os.path.join(r, "resources", "share", "union-lib.c")
        if os.path.isfile(src):
            with open(src, encoding="utf-8", errors="surrogateescape") as f:
                code = f.read()
            fixed, n = _LEAK.subn(r"\1\n  // samplecraft: two unused arrays (malloc, never freed) removed here\n", code, 1)
            if not n:
                return None
            dst = os.path.join(out_dir, "union-lib.c")
            with open(dst, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                f.write("/* Copy of McStas union-lib.c written by samplecraft.union: the memory leak of r_within_mesh "
                        "removed. */\n" + fixed)
            return dst
    return None


# --------------------------------------------------------------------------------------------- geometry helpers
def mcstas_angles(R):
    """(φx, φy, φz) [deg] of McStas ROTATED for a samplecraft rotation R (local -> parent)."""
    T = np.asarray(R, float).T
    phy = np.arcsin(np.clip(T[2, 0], -1, 1))
    if abs(np.cos(phy)) > 1e-9:
        phx = np.arctan2(-T[2, 1], T[2, 2])
        phz = np.arctan2(-T[1, 0], T[0, 0])
    else:                                              # gimbal lock: φz = 0
        phz = 0.0
        phx = np.arctan2(T[1, 2], T[1, 1])
    return np.degrees([phx, phy, phz])


def mcstas_matrix(phx, phy, phz):
    """T (lab -> local) of McStas rot_set_rotation (degrees), for the tests."""
    cx, sx, cy, sy, cz, sz = (f(np.radians(a)) for a in (phx, phy, phz) for f in (np.cos, np.sin))
    return np.array([[cy * cz, sx * sy * cz + cx * sz, sx * sz - cx * sy * cz],
                     [-cy * sz, cx * cz - sx * sy * sz, sx * cz + cx * sy * sz],
                     [sy, -sx * cy, cx * cy]])


def _posed(shape, R, t):
    """A copy of a shape placed in the parent frame of its CSG (pose R, t of the CSG)."""
    s = copy.copy(shape)
    s.R = R @ shape.R
    s.t = R @ shape.t + t
    if hasattr(s, "_lb"):
        s._lb = None
    return s


def _box_mesh(size):
    h = 0.5 * np.asarray(size, float)
    v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float) * h
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                  [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    return v, f


def _halfspace_box(hs, big):
    """The cube of side `big` standing for a half-space n·p <= offset (one face on its plane): (size, R, t) in the
    parent frame."""
    n = hs.R @ hs.n
    off = hs.offset + n @ hs.t
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(n, a); e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    R = np.c_[e1, e2, n]                               # local z along the normal
    p0 = hs.t + hs.R @ (hs.n * hs.offset)               # a point of the plane
    return np.full(3, big), R, p0 - n * big / 2 + (np.eye(3) - np.outer(n, n)) @ (hs.big_center - p0)


def _polytope(shapes, inset=0.0):
    """Mesh (v, f) of the intersection of boxes and half-spaces (all in the same frame), each face moved `inset`
    inward, or None if empty."""
    from scipy.optimize import linprog
    from scipy.spatial import ConvexHull, HalfspaceIntersection
    A, b = [], []
    for s in shapes:
        if isinstance(s, S.HalfSpace):
            n = s.R @ s.n
            A.append(n); b.append(s.offset + n @ s.t)
        else:                                          # a box: six half-spaces
            for k in range(3):
                ax = s.R[:, k]
                A += [ax, -ax]; b += [ax @ s.t + s.h[k], -ax @ s.t + s.h[k]]
    A, b = np.array(A), np.array(b)
    nrm = np.linalg.norm(A, axis=1)
    b = b - inset * nrm
    # an interior point: the center of the largest ball inside (Chebyshev center)
    r = linprog(np.r_[0, 0, 0, -1.0], A_ub=np.c_[A, nrm], b_ub=b, bounds=[(None, None)] * 3 + [(0, None)],
                method="highs")
    if r.status != 0 or r.x[3] <= 1e-9:
        return None
    hs = HalfspaceIntersection(np.c_[A, -b], r.x[:3])
    pts = hs.intersections
    hull = ConvexHull(pts)
    f = hull.simplices.copy()
    c = pts.mean(axis=0)
    for i, tri in enumerate(f):                        # outward normals
        nn = np.cross(pts[tri[1]] - pts[tri[0]], pts[tri[2]] - pts[tri[0]])
        if nn @ (pts[tri[0]] - c) < 0:
            f[i] = tri[::-1]
    used = np.unique(f)
    remap = -np.ones(len(pts), int); remap[used] = np.arange(len(used))
    return pts[used], remap[f]


def _frustum_mesh(r0, r1, height, n=256):
    """Cylinder or cone (axis y) of n sides, radii scaled so that its volume is the exact one (for the marching
    cubes fallback only; the primitives go to Union as they are)."""
    k = np.sqrt((2 * np.pi / n) / np.sin(2 * np.pi / n))
    a = 2 * np.pi * np.arange(n) / n
    ring = lambda r, y: np.c_[k * r * np.cos(a), np.full(n, y), k * r * np.sin(a)]
    v = np.vstack([ring(r0, -height / 2), ring(r1, height / 2), [[0, -height / 2, 0], [0, height / 2, 0]]])
    f = []
    for i in range(n):
        j = (i + 1) % n
        f += [[i, n + i, n + j], [i, n + j, j], [2 * n, i, j], [2 * n + 1, n + j, n + i]]
    return v, np.array(f)


def _star_mesh(shape, subdivisions):
    """Exact surface points of a shape seen whole from its center (local origin), along icosphere directions; the
    mesh scaled about the center to the exact volume. Returns (v, f, scale) in the parent frame, or None."""
    import trimesh
    ico = trimesh.creation.icosphere(subdivisions)
    u = np.asarray(ico.vertices) @ shape.R.T
    o = np.tile(shape.t, (len(u), 1))
    iv = shape.intervals(o, u)
    r = np.full(len(u), np.nan)
    ok = (iv.t0 <= 1e-12) & (iv.t1 > 0)
    r[iv.ray[ok]] = iv.t1[ok]
    if np.isnan(r).any():
        return None
    v = o + u * r[:, None]
    f = np.asarray(ico.faces)
    scale = ((shape.volume() or _volume(shape)) / _mesh_volume(v - shape.t, f)) ** (1 / 3)
    return shape.t + (v - shape.t) * scale, f, scale


def _mc_mesh(shape, cells=128):
    """Marching cubes on the inside of a shape (a grid of `cells` along its longest side)."""
    from scipy.ndimage import gaussian_filter
    from skimage.measure import marching_cubes
    lo, hi = shape.bounds()
    h = float(np.max(hi - lo)) / cells
    lo, hi = lo - 2 * h, hi + 2 * h
    g = [np.arange(lo[a], hi[a] + h, h) for a in range(3)]
    P = np.stack(np.meshgrid(*g, indexing="ij"), axis=-1).reshape(-1, 3)
    f = shape.inside(P).reshape([len(x) for x in g]).astype(float)
    f = gaussian_filter(f, 0.6)
    verts, faces, _, _ = marching_cubes(f, 0.5, spacing=(h, h, h))
    return verts + lo, faces[:, ::-1].astype(np.int64)


def _mesh_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)


def _volume(shape):
    from .generators import volume_of
    return volume_of(shape)


def _watertight(v, f, name):
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    if (c != 2).any():
        raise ValueError(f"{name}: the exported mesh is not closed ({(c != 2).sum()} edges not in two triangles)")


PRIMITIVES = (S.Sphere, S.Box, S.Cylinder, S.Cone)


def _csg_parts(sh):
    """The children of a construction placed in its parent frame; a half-space gets the size and center of the
    box that stands for it (4 times the extent of the bounded children, around them)."""
    parts = [_posed(c, sh.R, sh.t) for c in sh.children]
    b = [p.bounds() for p in parts if not isinstance(p, S.HalfSpace)]
    lo, hi = np.min([x[0] for x in b], axis=0), np.max([x[1] for x in b], axis=0)
    for p in parts:
        if isinstance(p, S.HalfSpace):
            p.big, p.big_center = 4 * float(np.max(hi - lo)), 0.5 * (lo + hi)
    return parts


def _padded(geo, pad=MASK_PAD_MM):
    """The same geometry, `pad` larger on every side (a mask)."""
    kind, par, R, t, how = geo
    if kind == "mesh":
        import trimesh
        v, f = par
        nrm = trimesh.Trimesh(v, f, process=False).vertex_normals
        return kind, (v + pad * nrm, f), R, t, how
    par = dict(par)
    for k in par:
        par[k] += 2 * pad if k in ("xwidth", "yheight", "zdepth") else pad
    return kind, par, R, t, how


def _simple(shape, subdivisions):
    """One Union geometry for a shape that is not a construction: (kind, params, R, t, how) with kind a primitive
    or 'mesh' (params = (v, f) in the parent frame, R = I, t = 0); None if it needs marching cubes."""
    I3, z3 = np.eye(3), np.zeros(3)
    if isinstance(shape, S.Sphere):
        return "sphere", dict(radius=shape.size[0] / 2), I3, shape.t, "Union_sphere (exact)"
    if isinstance(shape, S.Box):
        return "box", dict(xwidth=shape.size[0], yheight=shape.size[1], zdepth=shape.size[2]), shape.R, shape.t, \
            "Union_box (exact)"
    if isinstance(shape, S.Cylinder):
        return "cylinder", dict(radius=shape.r, yheight=shape.height), shape.R, shape.t, "Union_cylinder (exact)"
    if isinstance(shape, S.Cone):
        return "cone", dict(radius_bottom=shape.d0 / 2, radius_top=shape.d1 / 2, yheight=shape.height), shape.R, \
            shape.t, "Union_cone (exact)"
    if isinstance(shape, S.HalfSpace):
        size, R, t = _halfspace_box(shape, shape.big)
        return "box", dict(xwidth=size[0], yheight=size[1], zdepth=size[2]), R, t, "a large box (exact)"
    if isinstance(shape, S.Mesh):
        return "mesh", (shape.v @ shape.R.T + shape.t, shape.f), I3, z3, "its own triangles (exact)"
    if isinstance(shape, (S.Ellipsoid, S.Blob, S.Superellipsoid)):
        m = _star_mesh(shape, subdivisions)
        if m is not None:
            return "mesh", (m[0], m[1]), I3, z3, f"surface points, {len(m[1])} triangles, scaled by {m[2]:.6f} " \
                                                 f"(volume exact)"
    if isinstance(shape, S.Intersection) and all(isinstance(c, (S.Box, S.HalfSpace)) for c in shape.children):
        m = _polytope([_posed(c, shape.R, shape.t) for c in shape.children], CELL_INSET_MM)
        if m is not None:
            return "mesh", m, I3, z3, f"convex polyhedron, faces {CELL_INSET_MM * 1e6:.0f} nm inside"
    return None


def _exact_volume(shape):
    return shape.volume() or _volume(shape)


# --------------------------------------------------------------------------------------------- export
def _cname(s, used):
    c = re.sub(r"\W+", "_", s).strip("_") or "v"
    c = ("v_" + c) if c[0].isdigit() else c
    base, k = c, 1
    while c in used:
        k += 1
        c = f"{base}_{k}"
    used.add(c)
    return c


def _write_off(path, v, f):
    with open(path, "w") as fh:
        fh.write(f"OFF\n{len(v)} {len(f)} 0\n")
        np.savetxt(fh, v, fmt="%.10g")
        np.savetxt(fh, np.c_[np.full(len(f), 3), f], fmt="%d")


class _Writer:
    def __init__(self, out_dir, used):
        self.out_dir, self.used, self.lines = out_dir, used, []

    def volume(self, name, geo, material, priority, mask=None):
        """Writes one Union geometry; geo = (kind, params, R, t, how). mask: names of the volumes it masks."""
        kind, par, R, t, _ = geo
        cn = _cname(name, self.used)
        extra = (f'mask_string="{",".join(mask)}", mask_setting="All", priority=0' if mask is not None else
                 f'material_string="{material}", priority={priority:.6g}')
        if mask is not None:
            kind, par, R, t, _ = _padded(geo)
        if kind == "mesh":
            v, f = par
            fn = f"meshes/{cn}.off"
            _watertight(v, f, name)
            _write_off(os.path.join(self.out_dir, fn), v, f)
            # skip_convex_check: Union's test (Euler characteristic 2) refuses closed meshes with holes through them;
            # the mesh was checked closed here (each edge in two triangles)
            self.lines.append(f'COMPONENT {cn} = Union_mesh(filename="{fn}", coordinate_scale=1e-3, '
                              f'skip_convex_check=1, {extra})\nAT (0, 0, 0) RELATIVE sample_position\n')
        else:
            p = ", ".join(f"{k}={x * 1e-3:.10g}" for k, x in par.items())
            pos = ", ".join(f"{x * 1e-3:.10g}" for x in t)
            rot = "" if np.allclose(R, np.eye(3), atol=1e-14) else \
                " ROTATED ({:.10g}, {:.10g}, {:.10g}) RELATIVE sample_position".format(*mcstas_angles(R))
            self.lines.append(f"COMPONENT {cn} = Union_{kind}({p}, {extra})\n"
                              f"AT ({pos}) RELATIVE sample_position{rot}\n")
        return cn


def export(scene, out_dir, name="sample", subdivisions=3, include_holders=True, max_volumes=MAX_VOLUMES,
           beam_margin_mm=1.0):
    """Writes <out_dir>/<name>_union.instr (a test instrument), <name>_sample_part.instr (materials and volumes for
    any instrument) and the meshes (meshes/*.off); returns what was written and how each shape was exported."""
    if " " in os.path.abspath(out_dir):
        raise ValueError("McStas does not accept spaces in paths: choose an output folder without spaces")
    bodies = [(b, parent, depth) for b, parent, depth in scene.walk()
              if include_holders or not getattr(_root(scene, b), "holder", False)]
    if any(isinstance(b, VoxelBody) for b, _, _ in bodies):
        raise NotImplementedError("voxel bodies cannot be exported to Union (one volume per region would be needed)")
    if len(bodies) > max_volumes:
        raise ValueError(f"{len(bodies)} bodies: Union becomes very slow beyond about {max_volumes} volumes. Export a "
                         "simpler version of the sample (fewer, larger grains), or raise max_volumes.")
    os.makedirs(os.path.join(out_dir, "meshes"), exist_ok=True)
    cfg = scene.cfg()
    used, mat_names, lines_m, report = set(), {}, [], []
    for m in dict.fromkeys(b.material for b, _, _ in bodies):
        c = cfg[m]
        if re.match(r"^\s*void\.ncmat", c):
            mat_names[m] = "Vacuum"
            continue
        mat_names[m] = _cname("mat_" + m, used)
        lines_m.append(f'COMPONENT {mat_names[m]} = Union_NCrystal_material(cfg="{c}")\n'
                       f'AT (0, 0, 0) ABSOLUTE      // {m}\n')
    w = _Writer(out_dir, used)
    exported = {}                                       # body -> its shape as Union sees it (for as_exported)
    for k, (b, parent, depth) in enumerate(bodies):
        prio = k + 1                                    # parents first: each child above its parent
        mat = mat_names[b.material]
        around = mat_names[parent.material] if parent is not None else "Vacuum"
        sh = b.shape
        exact = _exact_volume(sh)
        inset = None
        if getattr(b, "holder", False):
            inset = _shrunk(sh, HOLDER_INSET_MM)
            sh = inset or sh
        geo = _simple(sh, subdivisions)
        if geo is not None:
            w.volume(b.name, geo, mat, prio)
            how, kind = geo[4], geo[0]
            if inset is not None:
                how = how.replace("(exact)", f"(holder, {HOLDER_INSET_MM * 1e6:.0f} nm smaller on every face)")
            if geo[0] == "mesh":
                vol = abs(_mesh_volume(*geo[1]))
                exported[id(b)] = sh if "exact" in how and "scaled" not in how else S.Mesh(vertices=geo[1][0],
                                                                                         faces=geo[1][1])
            else:
                vol, exported[id(b)] = _exact_volume(sh), sh
        elif isinstance(sh, (S.Intersection, S.Difference)) and all(
                _simple(c, subdivisions) is not None for c in _csg_parts(sh)):
            parts = [_simple(c, subdivisions) for c in _csg_parts(sh)]
            main = w.volume(b.name, parts[0], mat, prio)
            if isinstance(sh, S.Intersection):          # the first child, inside all the others
                for j, g in enumerate(parts[1:]):
                    w.volume(f"{b.name} mask {j + 1}", g, None, None, mask=[main])
                how = "Union masks (intersection)"
            else:                                       # the others, made of the material around, inside the first
                cuts = [w.volume(f"{b.name} cut {j + 1}", g, around, prio + (j + 1) / (len(parts) + 1))
                        for j, g in enumerate(parts[1:])]
                w.volume(f"{b.name} mask", parts[0], None, None, mask=cuts)
                how = "Union masks (difference)"
            kind = parts[0][0]
            exact_parts = all("exact" in p[4] and "scaled" not in p[4] for p in parts)
            how += ", exact" if exact_parts else ", with meshed parts"
            vol = exact if exact_parts else None
            exported[id(b)] = sh if exact_parts else None
        else:
            v, f = _mc_mesh(sh)
            g = ("mesh", (v, f), np.eye(3), np.zeros(3), "marching cubes")
            w.volume(b.name, g, mat, prio)
            how, kind, vol = "marching cubes", "mesh", abs(_mesh_volume(v, f))
            exported[id(b)] = S.Mesh(vertices=v, faces=f)
        if exported[id(b)] is None:                     # constructions with meshed parts: the same, part by part
            ch = [S.Mesh(vertices=p[1][0], faces=p[1][1]) if p[0] == "mesh" and "scaled" in p[4] else
                  c for p, c in zip(parts, _csg_parts(sh))]
            exported[id(b)] = type(sh)(ch)
            vol = _volume(exported[id(b)])
        report.append(dict(body=b.name, union=f"Union_{kind}", how=how, priority=prio, volume_mm3=exact,
                           volume_error=(vol - exact) / exact if exact else 0.0))
    part = os.path.join(out_dir, f"{name}_sample_part.instr")
    with open(part, "w", encoding="utf-8") as fh:
        fh.write(f"// samplecraft {scene.name or name}: materials (before the source) then volumes (an Arm named "
                 f"sample_position first), then a Union_master.\n// Generated by samplecraft.union.export.\n\n")
        fh.write("".join(lines_m) + "\n" + "".join(w.lines))
    lo, hi = scene.bounds()
    wd, ht = (hi[0] - lo[0] + 2 * beam_margin_mm) * 1e-3, (hi[1] - lo[1] + 2 * beam_margin_mm) * 1e-3
    cx, cy = 0.5 * (lo[0] + hi[0]) * 1e-3, 0.5 * (lo[1] + hi[1]) * 1e-3
    z_after = (hi[2] + 1.0) * 1e-3
    z_source = (lo[2] - 10.0) * 1e-3
    nx, ny = max(10, int(round(wd / 2e-5))), max(10, int(round(ht / 2e-5)))
    instr = os.path.join(out_dir, f"{name}_union.instr")
    with open(instr, "w", encoding="utf-8") as fh:
        fh.write(f"""/* Test of the samplecraft scene "{scene.name or name}" in McStas Union: a parallel monochromatic
   beam through the sample; behind it, the neutrons that went through without scattering (transmission, to compare
   with exp(-sum Sigma L) of samplecraft) and all neutrons (with the scattered ones). Refraction and reflection off.
   Generated by samplecraft.union.export. Pixels of 20 um. */
DEFINE INSTRUMENT {_cname(name, set())}_union(lambda=3.0, dlambda=0.0)
DECLARE %{{
  double vx0, vy0, vz0;
  int unscattered;
%}}
TRACE
{"".join(lines_m)}
COMPONENT origin = Progress_bar()
AT (0, 0, 0) ABSOLUTE
COMPONENT source = Source_div(xwidth={wd:.9g}, yheight={ht:.9g}, focus_aw=1e-6, focus_ah=1e-6, lambda0=lambda,
                              dlambda=dlambda)
AT ({cx:.9g}, {cy:.9g}, {z_source:.9g}) RELATIVE origin
COMPONENT before = Arm()
AT (0, 0, 0) RELATIVE origin
EXTEND %{{
  vx0 = vx; vy0 = vy; vz0 = vz;
%}}
COMPONENT sample_position = Arm()
AT (0, 0, 0) RELATIVE origin
{"".join(w.lines)}
COMPONENT master = Union_master(enable_refraction=0, enable_reflection=0)
AT (0, 0, 0) RELATIVE sample_position
EXTEND %{{
  unscattered = (vx == vx0 && vy == vy0 && vz == vz0);
%}}
COMPONENT unscattered_psd = PSD_monitor(nx={nx}, ny={ny}, xwidth={wd:.9g}, yheight={ht:.9g}, filename="unscattered",
                                        restore_neutron=1)
WHEN (unscattered)
AT ({cx:.9g}, {cy:.9g}, {z_after:.9g}) RELATIVE origin
COMPONENT all_psd = PSD_monitor(nx={nx}, ny={ny}, xwidth={wd:.9g}, yheight={ht:.9g}, filename="all",
                                restore_neutron=1)
AT ({cx:.9g}, {cy:.9g}, {z_after:.9g}) RELATIVE origin
END
""")
    as_exported = Scene(_rebuilt(scene.bodies, exported, bodies), scene.materials, scene.name + " (as exported)",
                        scene.description, scene.provenance, scene.seed)
    union_lib = _union_lib_fixed(out_dir) if any(r["union"] == "Union_mesh" for r in report) else None
    return dict(instrument=instr, sample_part=part, shapes=report, as_exported=as_exported, union_lib=union_lib,
                beam=dict(xwidth_mm=wd * 1e3, yheight_mm=ht * 1e3, center_mm=(cx * 1e3, cy * 1e3), nx=nx, ny=ny))


def _root(scene, body):
    for top in scene.bodies:
        if any(b is body for b, _, _ in top.walk()):
            return top
    return None


def _rebuilt(bodies, exported, kept):
    keep = {id(b) for b, _, _ in kept}
    return [Body(b.name, b.material, exported[id(b)], _rebuilt(b.children, exported, kept), b.secret, b.holder,
                 b.note) for b in bodies if id(b) in keep]
