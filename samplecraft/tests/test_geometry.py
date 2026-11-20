"""Validation of the geometry of samplecraft against exact results.

    python -m pytest samplecraft/tests -q

1. Chords against closed forms (sphere, box, cylinder): to 1e-12 mm.
2. Volumes: the integral of the chords over a grid of parallel rays equals the exact volume of every shape (to the
   quadrature error of the grid, < 3e-4), in two directions, with rotations.
3. CSG against closed forms (napkin ring, lens, hemisphere).
4. Meshes: a triangulated sphere gives the volume of its triangles.
5. Lumpy shapes: the batched kernel and the single-shape kernel agree with a reference sampled 1000 times finer, to
   machine precision (grazing rays included).
6. Voxels: the traversal gives exact lengths in a checkerboard.
7. Scenes: children replace their parent's material (lengths per material add up to the outer chord); voxels lie
   under their sibling bodies; build is reproducible from the seed; save and load give the same lengths.
8. Export to McStas Union: rotations, polyhedra set inside, transmission of the scene as exported.
"""
import os

import numpy as np
import pytest

import samplecraft as sc
from samplecraft import kernels
from samplecraft import shapes as S
from samplecraft.generators import random_rotation, volume_of
from samplecraft.scene import Body, Scene, VoxelBody


def grid_rays(shape, h, direction):
    lo, hi = shape.bounds()
    d = np.asarray(direction, float); d /= np.linalg.norm(d)
    c = 0.5 * (lo + hi); R = 0.5 * np.linalg.norm(hi - lo) * 1.01
    e1 = np.cross(d, [1, 0, 0] if abs(d[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(d, e1)
    g = np.arange(-R, R, h) + h / 2
    A, B = np.meshgrid(g, g)
    o = c + A.ravel()[:, None] * e1 + B.ravel()[:, None] * e2 - 3 * R * d
    return o, np.tile(d, (len(o), 1))


def test_chords_closed_forms():
    rng = np.random.default_rng(0)
    b = rng.uniform(-0.99, 0.99, 2000)                  # impact parameters
    o = np.c_[b, np.zeros_like(b), np.full_like(b, -5)]
    d = np.tile([0, 0, 1.0], (len(b), 1))
    L = S.Sphere(2.0).intervals(o, d).lengths()
    assert np.abs(L - 2 * np.sqrt(1 - b * b)).max() < 1e-12
    R = random_rotation(rng)
    box = S.Box([1, 2, 3], rotation_=R)
    # along each of its own axes through its center: its size
    for a, s in enumerate([1, 2, 3]):
        L = box.intervals(-10 * R[:, a][None], R[:, a][None]).lengths()
        assert abs(L[0] - s) < 1e-12
    cyl = S.Cylinder(2.0, 4.0)
    L = cyl.intervals(np.c_[b, np.zeros_like(b), np.full_like(b, -5)], d).lengths()
    assert np.abs(L - 2 * np.sqrt(1 - b * b)).max() < 1e-12


SHAPES = [
    S.Box([3, 2, 1], rotation_={"euler_deg": [30, 20, 10]}, position=[1, 2, 3]),
    S.Sphere(2.0),
    S.Ellipsoid([3, 1, 2], rotation_={"axis": [1, 1, 0], "angle_deg": 40}),
    S.Cylinder(1.5, 3.0, rotation_={"euler_deg": [0, 60, 0]}),
    S.Cone(2.0, 0.5, 3.0, rotation_={"euler_deg": [20, 30, 0]}),
    S.Torus(4.0, 1.0, rotation_={"euler_deg": [0, 70, 0]}),
    S.Superellipsoid([2, 3, 1.5], 6.0),
    S.Blob([2, 1.5, 1], 0.15, seed=5, rotation_={"euler_deg": [10, 50, 30]}),
    S.Prism([[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]], 1.0, rotation_={"euler_deg": [0, 30, 15]}),
]


@pytest.mark.parametrize("shape", SHAPES, ids=[type(s).__name__ for s in SHAPES])
def test_volume_by_chords(shape):
    for direction in ([0.3, 0.5, 0.8], [-0.7, 0.1, 0.2]):
        o, d = grid_rays(shape, 0.01, direction)
        v = shape.intervals(o, d).lengths().sum() * 1e-4
        assert abs(v / shape.volume() - 1) < 3e-4, (v, shape.volume())


def test_csg_closed_forms():
    R, r = 1.0, 0.6
    ring = S.Difference([S.Sphere(2 * R), S.Cylinder(2 * r, 5.0)])
    h = 2 * np.sqrt(R * R - r * r)
    lens = S.Intersection([S.Sphere(2.0, position=[0.5, 0, 0]), S.Sphere(2.0, position=[-0.5, 0, 0])])
    half = S.Intersection([S.Sphere(2.0), S.HalfSpace([0, 0, 1], 0.0)])
    for shape, exact in ((ring, np.pi * h ** 3 / 6), (lens, np.pi * 5 * 1 / 12), (half, 2 / 3 * np.pi)):
        o, d = grid_rays(shape, 0.005, [0.2, 0.3, 0.93])
        v = shape.intervals(o, d).lengths().sum() * 0.005 ** 2
        assert abs(v / exact - 1) < 1e-4


def test_mesh_sphere():
    trimesh = pytest.importorskip("trimesh")
    ico = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    m = S.Mesh(ico.vertices, ico.faces, rotation_={"euler_deg": [10, 20, 30]})
    o, d = grid_rays(m, 0.005, [0.3, 0.5, 0.8])
    v = m.intervals(o, d).lengths().sum() * 0.005 ** 2
    assert abs(v / m.volume() - 1) < 2e-5


def test_lumpy_kernels_machine_precision():
    rng = np.random.default_rng(1)
    bodies = []
    for k in range(40):
        a = rng.uniform(0.1, 0.6)
        bodies.append(Body(f"g{k}", "a", S.Blob([a, a * rng.uniform(0.3, 1), a * rng.uniform(0.2, 1)],
                                                wobble=rng.uniform(0.05, 0.25), seed=k, position=rng.uniform(-2, 2, 3),
                                                rotation_=random_rotation(rng))))
    scene = Scene(bodies, {})
    d = np.array([0.3, -0.4, 0.866]); d /= np.linalg.norm(d)
    e1 = np.cross(d, [1, 0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(d, e1)
    g = np.linspace(-3.5, 3.5, 250)
    A, B = np.meshgrid(g, g)
    o = A.ravel()[:, None] * e1 + B.ravel()[:, None] * e2 - 10 * d
    D = np.tile(d, (len(o), 1))
    batched = scene.path_lengths(o, D)[("a", None)]
    single = sum(b.shape.intervals(o, D).lengths() for b in bodies)
    ref = 0
    for b in bodies:
        p, lk, lph, la, radius, step = b.shape._params()
        out, cnt = kernels.implicit_chords(0, np.ascontiguousarray(b.shape.to_local(o)),
                                           np.ascontiguousarray(D @ b.shape.R), p, lk, lph, la, radius, step / 1000, 32)
        ref = ref + np.where(np.arange(32)[None, :] < cnt[:, None], out[..., 1] - out[..., 0], 0).sum(axis=1)
    assert np.abs(batched - ref).max() < 1e-9
    assert np.abs(single - ref).max() < 1e-9


def test_voxels_exact():
    lab = (np.indices((4, 4, 4)).sum(axis=0) % 2 + 1).astype(np.int64)        # checkerboard of labels 1 and 2
    vb = VoxelBody("v", lab, 0.5, {1: "a", 2: "b"})
    o = np.array([[-0.75, -0.75, -5.0], [0.3, -0.2, -5.0]])
    d = np.tile([0, 0, 1.0], (2, 1))
    L = vb.label_lengths(o, d)
    assert np.allclose(L[1] + L[2], 2.0) and np.allclose(L[1], 1.0)
    sets = vb.label_sets(o, d)
    assert np.allclose(sets[1].lengths(), L[1]) and np.allclose(sets[2].lengths(), L[2])


def test_scene_materials_and_voxels_under_siblings():
    inner = Body("in", "b", S.Sphere(1.0))
    outer = Body("out", "a", S.Sphere(3.0), [inner])
    scene = Scene([outer], {"a": {"ncrystal": "Al_sg225.ncmat"}, "b": {"ncrystal": "Cu_sg225.ncmat"}})
    o = np.array([[0.0, 0.0, -5.0], [0.0, 1.2, -5.0]]); d = np.tile([0, 0, 1.0], (2, 1))
    L = scene.material_lengths(o, d)
    assert np.allclose(L["a"] + L["b"], 2 * np.sqrt(2.25 - np.array([0, 1.44])))
    assert np.allclose(L["b"], [1.0, 0.0])
    # a voxel body of pores (label 1) beside a grain: the grain keeps its part
    grain = Body("grain", "b", S.Sphere(1.0))
    pores = VoxelBody("pores", np.ones((6, 6, 6), np.int64), 0.5, {1: "void"})
    host = Body("host", "a", S.Box([4, 4, 4]), [grain, pores])
    L = Scene([host], {}).material_lengths(o, d)
    assert np.allclose(L["b"], [1.0, 0.0]) and np.allclose(L["void"], [2.0, 3.0])


def test_build_reproducible_and_roundtrip(tmp_path):
    d = dict(samplecraft=1, seed=5, materials={"m": {"minerals": {"plag": 100}}, "g": {"minerals": {"cpx": 100}}},
             bodies=[dict(name="host", material="m", shape={"type": "box", "size": [3, 3, 1]},
                          fill=[{"material": "g", "count": 60, "size_mm": [0.1, 0.3], "grain": {"type": "blob", "wobble": 0.1}}])])
    s1, s2 = Scene.from_dict(d), Scene.from_dict(d)
    o, dd = grid_rays(s1.bodies[0].shape, 0.05, [0, 0, 1])
    L1, L2 = s1.material_lengths(o, dd), s2.material_lengths(o, dd)
    assert all(np.array_equal(L1[k], L2[k]) for k in L1)
    assert not s1.check(n=500)
    f = os.path.join(tmp_path, "s.yml")
    s1.save(f)
    L3 = Scene.load(f).material_lengths(o, dd)
    assert all(np.allclose(L1[k], L3[k]) for k in L1)


def test_calibrated_material():
    cfg, notes = sc.resolve_materials({"x": {"calibrate": {"base": {"minerals": {"plag": 100}}, "add": "water",
                                                           "sigma_cm": 1.0, "wavelength_A": 1.8}}})
    assert abs(sc.sigma(cfg["x"], [1.8])[0] - 1.0) < 1e-4


def test_voronoi_cells_tile_host_with_tight_bounds():
    d = dict(samplecraft=1, seed=2, materials={"a": {"minerals": {"plag": 100}}, "b": {"minerals": {"cpx": 100}}},
             bodies=[dict(name="plate", material="a", shape={"type": "box", "size": [4, 4, 1]},
                          fill=[{"voronoi": {"count": 40, "phases": {"a": 0.5, "b": 0.5}}}])])
    s = Scene.from_dict(d)
    cells = s.bodies[0].children
    # the cells' volumes add up to the plate, and each cell's bounds are tight (smaller than the plate)
    assert abs(sum(volume_of(c.shape, 0.01) for c in cells) - 16.0) < 0.02
    assert all(np.prod(c.shape.bounds()[1] - c.shape.bounds()[0]) < 0.6 * 16 for c in cells)
    pts = np.random.default_rng(0).uniform([-2, -2, -0.5], [2, 2, 0.5], (2000, 3))
    for c in cells:            # every point of a cell's shape is inside its bounds
        lo, hi = c.shape.bounds()
        p = pts[c.shape.inside(pts)]
        assert ((p >= lo - 1e-9) & (p <= hi + 1e-9)).all()


def test_union_export(tmp_path):
    """8. Export to McStas Union: the angles of ROTATED give back the rotation; the Voronoi cells become polyhedra
    set 100 nm inside (no shared faces, which Union cannot trace) whose volumes add up to the plate minus that skin;
    the scene as exported has the transmission of the scene to that skin."""
    from samplecraft import union
    R = random_rotation(np.random.default_rng(3))
    assert np.abs(union.mcstas_matrix(*union.mcstas_angles(R)) - R.T).max() < 1e-12
    d = dict(samplecraft=1, seed=2, materials={"a": {"minerals": {"plag": 100}}, "b": {"minerals": {"cpx": 100}}},
             bodies=[dict(name="plate", material="a", shape={"type": "box", "size": [4, 4, 1]},
                          fill=[{"voronoi": {"count": 20, "phases": {"a": 0.5, "b": 0.5}}}])])
    s = Scene.from_dict(d)
    out = union.export(s, str(tmp_path), "plate")
    assert os.path.isfile(out["instrument"]) and len(os.listdir(tmp_path / "meshes")) == 20
    cells = out["as_exported"].bodies[0].children
    v = sum(abs(union._mesh_volume(c.shape.v, c.shape.f)) for c in cells)
    # a skin of 100 nm on every face of every cell: about half the total face area × 2 × 1e-4 mm of volume
    assert 0 < 16.0 - v < 0.05
    rng = np.random.default_rng(1)
    o = np.c_[rng.uniform(-1.9, 1.9, (500, 2)), np.full(500, -2.0)]
    dd = np.tile([0.0, 0.0, 1.0], (500, 1))
    T, T0 = out["as_exported"].transmission(o, dd, 3.0), s.transmission(o, dd, 3.0)
    assert np.abs(T / T0 - 1).max() < 1e-4


def test_union_holder_inset_and_leak_fix(tmp_path):
    """Holders go to Union 100 nm smaller on every face (no face shared with the sample): every point of the smaller
    surface is 100 nm inside the exact one. The memory leak of McStas union-lib.c (r_within_mesh) is removed."""
    from samplecraft import union
    d = 1e-4
    rot = dict(rotation={"euler_deg": [20, 30, 40]}, position=[1, 2, 3])
    for sh in (S.Box([3, 2, 1], **rot), S.Cylinder(2, 3, **rot), S.Cone(1, 3, 2, **rot), S.Cone(3, 0.5, 2, **rot),
               S.Sphere(2, **rot)):
        small = union._shrunk(sh, d)
        rng = np.random.default_rng(0)
        o = sh.t + rng.normal(size=(400, 3)) * 0.2
        u = rng.normal(size=(400, 3)); u /= np.linalg.norm(u, axis=1)[:, None]
        # from points inside, along random directions: the exit of the small shape is d before the exit of the big
        # one along the surface normal, so the exit distances differ by at least d (d / cos of the incidence)
        t_small = np.array([small.intervals(o[i:i + 1], u[i:i + 1]).t1.max() for i in range(400)])
        t_big = np.array([sh.intervals(o[i:i + 1], u[i:i + 1]).t1.max() for i in range(400)])
        assert (t_big - t_small > d * (1 - 1e-6)).all(), type(sh).__name__
        assert np.isclose((t_big - t_small).min(), d, rtol=0.2), type(sh).__name__
    leaky = ("int r_within_mesh(Coords pos) {\n  int n_facets = 3;\n"
             "  double *t_intersect=malloc(n_facets*sizeof(double));\n"
             "  int *facet_index = malloc(n_facets*sizeof(int));\n"
             "  if (!t_intersect || !facet_index) {\n    exit(EXIT_FAILURE);\n  }\n  return 0;\n}\n")
    fixed, n = union._LEAK.subn(r"\1\n  // removed\n", leaky)
    assert n == 1 and "malloc" not in fixed and "return 0;" in fixed
