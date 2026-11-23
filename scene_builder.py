"""Recipes of ODIN samples for the sample builder (the page builder/, its server builder_api.py).

A recipe (samplecraft scene description) holds materials, components and a tree of bodies; each body has a shape
(any samplecraft shape, its position and 3D rotation), a material, children, and fills (populations of grains,
Voronoi polycrystals, pores). Here: a new recipe, the recipe of a library sample, building a recipe (generated from
its seed, checked), the sample file of a built recipe, and the surfaces of a scene for a 3D view. Everything a
scientist needs to state in a paper is in the recipe (sources, assumptions, seed) and is saved with the sample.
"""
import copy

import numpy as np


def new_recipe():
    return dict(samplecraft=1, name="", description="", seed=7,
                provenance=dict(sources=[], assumptions=[]),
                materials={"steel": {"ncrystal": "Fe_sg229_Iron-alpha.ncmat", "source": "NCrystal library"},
                           "aluminium": {"ncrystal": "Al_sg225.ncmat"}},
                components={},
                bodies=[dict(name="the sample", material="steel", shape={"type": "box", "size": [10.0, 10.0, 4.0]}),
                        dict(name="holder", material="aluminium", holder=True,
                             shape={"type": "box", "size": [12.0, 3.0, 6.0], "position": [0.0, -6.5, 0.0]})])


def recipe_of(spec):
    """The recipe of a sample: its own (scene samples keep it), else its volumes turned into a scene."""
    import sample_library as sl
    if sl.is_scene(spec):
        sc = spec["scene"]
        return copy.deepcopy(sc.get("recipe") or {k: v for k, v in sc.items() if k != "recipe"})
    return sl.scene_from_volumes(spec)


def _walk(bodies, path=()):
    """(path, body) of every body of a tree of bodies (recipe["bodies"]), depth first."""
    for i, b in enumerate(bodies):
        p = path + (i,)
        yield p, b
        yield from _walk(b.get("children", []), p)


def build(recipe, check=True):
    """(scene, report lines, problems) of a recipe; check=False: the problems of the tree are not looked for (a
    thumbnail)."""
    import samplecraft as sc
    scene = sc.Scene.from_dict(recipe)
    lines = []
    for r in getattr(scene, "report", []):
        line = f"{r['population']} in {r['body']}: {r['placed']} placed (asked {r['asked']})"
        if r.get("target_mm3"):
            line += f", {100 * r['volume_mm3'] / r['target_mm3']:.0f} % of the volume asked"
        lines.append(line)
    problems = scene.check(n=800) if check else []
    for r in getattr(scene, "report", []):
        if r.get("target_mm3") and r["volume_mm3"] < 0.9 * r["target_mm3"]:
            problems.append(f"{r['population']} in {r['body']}: only {100 * r['volume_mm3'] / r['target_mm3']:.0f} % "
                            f"of the volume asked found room (smaller grains, or less)")
        elif isinstance(r.get("asked"), int) and isinstance(r.get("placed"), int) and r["placed"] < r["asked"]:
            problems.append(f"{r['population']} in {r['body']}: {r['placed']} of {r['asked']} found room")
    return scene, lines, problems


def sample_spec(recipe, scene, name="", title="", description=""):
    """The sample file of a built recipe (sample_library format: metadata + the scene as built, with its recipe)."""
    d = scene.to_dict()
    d["recipe"] = recipe
    spec = dict(name=title or name or recipe.get("name", ""), description=description or recipe.get("description", ""),
                scene=d)
    if any(b.get("secret") for _, b in _walk(recipe["bodies"])):
        spec["hidden"] = ["inclusions"]
    return spec


# --------------------------------------------------------------------------- 3D view
def surfaces(scene, n=72):
    """The surfaces of a built scene for a 3D view: the material at each point of a grid of about n points along the
    longest side (the bounds of the sample and its holders), then one surface per material (marching cubes on its
    mask, smoothed a little). Returns [(material, vertices (k, 3) [mm], faces (m, 3), is a holder, volume share)].
    A view, not the model: details smaller than the grid step are lost (the exact model is the scene itself)."""
    from scipy.ndimage import gaussian_filter
    from skimage.measure import marching_cubes
    holders = [b for b in scene.bodies if getattr(b, "holder", False)]
    bodies = [b for b in scene.bodies if not getattr(b, "holder", False)]
    allb = bodies + holders
    lo = np.min([b.shape.bounds()[0] for b in allb], axis=0)
    hi = np.max([b.shape.bounds()[1] for b in allb], axis=0)
    step = float(np.max(hi - lo)) / n
    lo, hi = lo - 1.5 * step, hi + 1.5 * step
    axes = [np.arange(lo[k], hi[k] + step / 2, step) for k in range(3)]
    P = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    shape = tuple(len(a) for a in axes)
    out = []
    for part, is_holder in ((bodies, False), (holders, True)):
        if not part:
            continue
        m = type(scene)(part, scene.materials).material_at(P).reshape(shape)
        names = [x for x in dict.fromkeys(m.ravel()) if x is not None]
        total = max(1, sum(int((m == x).sum()) for x in names))
        for name in names:
            mask = gaussian_filter((m == name).astype(float), 0.6)
            if mask.max() < 0.5:
                continue                                  # thinner than the grid: not drawn
            v, f, _, _ = marching_cubes(mask, 0.5)
            out.append((name, v * step + lo, f, is_holder, int((m == name).sum()) / total))
    return out
