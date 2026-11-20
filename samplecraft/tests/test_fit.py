"""samplecraft.fit: a sample fitted to a noisy measurement made from it gives back its parameters (within their
errors, χ²/dof near 1)."""
import numpy as np

from samplecraft import fit
from samplecraft.scene import Scene


def _noisy(scene, o, d, lam, counts, rng):
    T = np.stack([scene.transmission(o, d, l) for l in lam], axis=1)
    dT = np.sqrt(T / counts)                      # counting statistics: N = counts × T, error √N
    return T + rng.normal(size=T.shape) * dT, dT


def test_spectrum_fit_phase_fraction():
    """Bragg-edge spectrum of a duplex steel plate: the ferrite fraction (the austenite tied to 1 − f) and the
    density factor, from 80 wavelengths through 3 mm."""
    recipe = dict(samplecraft=1, seed=1,
                  materials=dict(ferrite={"ncrystal": "Fe_sg229_Iron-alpha.ncmat"},
                                 austenite={"ncrystal": "Fe_sg225_Iron-gamma.ncmat"},
                                 duplex={"mix": {"ferrite": 0.35, "austenite": 0.65}, "density_factor": 0.97}),
                  bodies=[dict(name="plate", material="duplex", shape={"type": "box", "size": [10, 10, 3]})])
    o = np.array([[0.0, 0.0, -5.0]] * 4) + np.c_[np.linspace(-2, 2, 4), np.zeros(4), np.zeros(4)]
    d = np.tile([0.0, 0.0, 1.0], (4, 1))
    lam = np.linspace(2.0, 5.0, 80)
    T, dT = _noisy(Scene.from_dict(recipe), o, d, lam, 2e5, np.random.default_rng(4))
    start = fit.set_value  # the start values: away from the truth
    guess = __import__("copy").deepcopy(recipe)
    start(guess, "materials.duplex.mix.ferrite", 0.6)
    start(guess, "materials.duplex.mix.austenite", 0.4)
    start(guess, "materials.duplex.density_factor", 0.9)
    params = [fit.Parameter("materials.duplex.mix.ferrite", 0, 1, name="f"),
              fit.Parameter("materials.duplex.density_factor", 0.5, 1, name="rho")]
    r = fit.fit(guess, params, o, d, lam, T, dT, ties={"materials.duplex.mix.austenite": "1 - f"})
    assert r.success
    assert abs(r.values["f"] - 0.35) < 4 * r.errors["f"] and r.errors["f"] < 0.02
    assert abs(r.values["rho"] - 0.97) < 4 * r.errors["rho"]
    assert 0.6 < r.chi2_red < 1.5
    assert fit.get_value(r.recipe, "materials.duplex.mix.austenite") == 1 - r.values["f"]
    assert fit.get_value(guess, "materials.duplex.mix.ferrite") == 0.6        # the recipe given is not changed


def test_image_fit_geometry():
    """Image of an aluminium plate with a hole drilled through (a void cylinder): its thickness and the hole's
    diameter, from a 40 × 40 image at one wavelength (the scene rebuilt at every step)."""
    recipe = dict(samplecraft=1, seed=1,
                  materials=dict(al={"ncrystal": "Al_sg225.ncmat"}, steel={"ncrystal": "Fe_sg229_Iron-alpha.ncmat"},
                                 air={"ncrystal": "void.ncmat"}),
                  bodies=[dict(name="plate", material="steel", shape={"type": "box", "size": [8, 8, 2.5]},
                               children=[dict(name="hole", material="air",
                                              shape={"type": "cylinder", "diameter": 3.2, "height": 2.5,
                                                     "rotation": {"euler_deg": [0, 90, 0]}})])])
    # the measurement: pixels of 0.25 mm averaged over 64 rays; the fit: 16 other rays per pixel
    o, d = fit.image_rays(40, 40, (-5, 5, -5, 5), -5.0, rays_per_pixel=64, seed=11)
    s = Scene.from_dict(recipe)
    T = s.transmission(o.reshape(-1, 3), d.reshape(-1, 3), 3.0).reshape(1600, 64).mean(axis=1)[:, None]
    dT = np.sqrt(T / 1e4)
    T = T + np.random.default_rng(5).normal(size=T.shape) * dT
    o, d = fit.image_rays(40, 40, (-5, 5, -5, 5), -5.0, rays_per_pixel=16)
    guess = __import__("copy").deepcopy(recipe)
    fit.set_value(guess, "bodies.plate.shape.size.2", 2.0)
    fit.set_value(guess, "bodies.plate.children.hole.shape.diameter", 2.5)
    fit.set_value(guess, "bodies.plate.children.hole.shape.height", 2.0)
    params = [fit.Parameter("bodies.plate.shape.size.2", 0.5, 5, name="thickness"),
              fit.Parameter("bodies.plate.children.hole.shape.diameter", 0.5, 6, name="hole")]
    r = fit.fit(guess, params, o, d, 3.0, T, dT, ties={"bodies.plate.children.hole.shape.height": "thickness"})
    assert r.success, r.message
    assert abs(r.values["thickness"] - 2.5) < 4 * r.errors["thickness"]
    # 16 rays per pixel against 64 in the measurement: the model's own sampling error, a few µm on the diameter
    assert abs(r.values["hole"] - 3.2) < max(4 * r.errors["hole"], 0.02)
    assert 0.6 < r.chi2_red < 1.6
