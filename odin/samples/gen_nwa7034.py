"""Writes meteorite_nwa7034.yml: the piece of the Martian meteorite NWA 7034 studied by Naver et al. (2026), as a
samplecraft scene (its recipe, editable in the sample builder, and the scene as built), for the hybrid model of ODIN
(camera images, tomography, time of flight).

    python gen_nwa7034.py

Two sources, followed as closely as they allow:
  [N] E. B. Naver, K. W. Nikolajsen et al., "Direct detection of hydrogen reveals a new macroscopic crustal water
      reservoir on early Mars", arXiv:2601.08390 (2026), CC BY 4.0: the measurements on this very piece (neutron
      tomography at ICON, X-ray tomography at ESRF BM05, XRD-CT at MAX IV DanMAX). Its tomograms are not published yet
      ("Data will be uploaded to data.dtu.dk"): the positions of the clasts in the piece are not known.
  [P] the model of the same piece in the user's ODIN beamtime proposal (NNSP/Beamtime_proposal/simulations/
      meteorite_twin.py, tomo_slice_nwa7034): a horizontal slice of it, with what the publications on NWA 7034 say
      about its texture; here extended to 3D.

Taken from [N] (section):
  * the piece: 12 × 8 × 2 mm³, glued on a stick on the rotation stage (IV.1); one face polished by hand (IV.1);
  * the matrix: fine-grained (grains below the 6.2 µm voxels), Σ(25 meV) = 0.45 cm⁻¹ measured on "an area of
    matrix without highly attenuating phases" (Table S2); its mineralogy (S2, from Agee et al. 2013): 38 %
    plagioclase, 25.4 % pyroxene, 18.2 % clinopyroxene, 9.7 % Fe oxides, 4.9 % alkali feldspar, 3.7 % apatite;
  * Fe-Ti oxides: "predominantly as small grains dispersed throughout the meteorite", 3 vol% (II);
  * the H-rich Fe-oxyhydroxides: "localised macroscopic clusters totalling 0.4 vol%", in H-Fe-ox clasts (II);
  * the three largest H-Fe-ox clasts (II, Fig. 2): lithic clasts from 120 × 270 × 150 to 300 × 380 × 330 µm³, made
    of Fe-Ti oxides ("including an euhedral grain at 170 × 180 × 170 µm³"), Fe-oxyhydroxides with no defined grains
    ("cover volumes up to 120 × 350 × 230 µm³") and feldspars, "subhedral interlocking grains up to 100 × 440 × 150
    µm³ that surround the Fe-Ti oxides"; no apatite nor pyroxene in them (Discussion);
  * their attenuation, measured (Table S2, 25 meV = 1.8 Å): clast 1: 0.56 cm⁻¹ without H, 1.9 with H; clast 2:
    0.57 / 1.7; clast 3: 0.58 / 2.0; the other clasts here: the average, 0.57 / 1.9.
Taken from [P] (assumptions of the proposal, from the literature on NWA 7034, not measured on this piece):
  * the outline: a sawn piece, its edges slightly irregular and rounded, one corner broken (a closed mesh);
  * mineral clasts of plagioclase and pyroxene, 0.1 to 0.5 mm, about 5 % of the volume each;
  * one basaltic lithic clast (1.1 × 0.9 × 0.7 mm), pyroxene with plagioclase laths;
  * the visible Fe-Ti oxide grains, 16 to 80 µm (log-normal), a few apatite and pyrite grains;
  * small H-rich fragments broken off the clasts into the matrix;
  * a few pores and one thin crack.
Assumed here: where the clusters and clasts are (random, fixed seed); the sizes of clasts 2 and 3 and of their
oxide grain and H-rich region within the ranges of [N]; three shapes of smaller clasts (components of the scene, each
copy scaled and turned at random); the lumpy shapes; the composition of the clasts (plagioclase, maghemite, ilmenite:
the phases of the XRD-CT of [N], Fig. 3). The Fe-Ti oxide grains below 16 µm (most of the 3 vol%) stay in the matrix,
whose Σ is the measured one.
Materials: NCrystal "solid::" compositions (no Bragg edges: fine-grained rock) plus a fraction of liquid water
standing for the hydrogen ([N]: "we assume that all excess measured neutron attenuation results from the presence of
hydrogen"), calibrated (samplecraft) so that Σ(1.8 Å) is the value measured at ICON. In a clast, the body (the fine
intergrowth around the grains drawn one by one) is set so that the clast without its H-rich region has the measured
Σ "without H" (from the exact volumes of its parts).
"""
import os
import sys
import time

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))          # twin/: samplecraft
import samplecraft as sc  # noqa: E402
from samplecraft import materials as scm  # noqa: E402
from samplecraft import shapes as S  # noqa: E402
from samplecraft.scene import sample_points  # noqa: E402

PHASES = {                                             # minerals by volume (samplecraft.materials.MINERALS)
    "matrix": dict(plag=38, opx=25.4, cpx=18.2, mag=9.7, afs=4.9, ap=3.7),
    "plagioclase": dict(plag=85, afs=15),
    "pyroxene": dict(opx=58, cpx=42),
    "Fe-Ti oxide": dict(mag=65, ilm=35),
    "apatite": dict(ap=100),
    "pyrite": dict(py=100),
}
CLAST_BODY = dict(plag=50, magh=25, ilm=25)            # the fine intergrowth of a clast (set to its measured Σ)
H_REGION = dict(magh=65, ilm=20, plag=15)             # the Fe-oxyhydroxides ([N]: 20-50 wt% maghemite in H-regions)
# the three clasts of [N]: size of the clast, its euhedral oxide grain and its H-rich region [mm]; Σ measured
BIG = [dict(clast=(0.30, 0.38, 0.33), oxide=0.17, H=(0.12, 0.35, 0.23), no_h=0.56, with_h=1.9, feldspars=3),
       dict(clast=(0.22, 0.33, 0.26), oxide=0.12, H=(0.10, 0.28, 0.18), no_h=0.57, with_h=1.7, feldspars=2),
       dict(clast=(0.12, 0.27, 0.15), oxide=0.06, H=(0.06, 0.20, 0.10), no_h=0.58, with_h=2.0, feldspars=1)]
# three shapes of the smaller clasts (longest axis 0.25 mm before scaling; scaled 0.64 to 1.36: 0.16 to 0.34 mm)
SMALL = [dict(clast=(0.18, 0.25, 0.19), oxide=0.065, H=(0.072, 0.20, 0.115)),
         dict(clast=(0.25, 0.17, 0.21), oxide=0.06, H=(0.10, 0.13, 0.12)),
         dict(clast=(0.20, 0.21, 0.25), oxide=0.07, H=(0.08, 0.17, 0.15))]
SCALE = (0.64, 1.36)
AVG_NO_H, AVG_H = 0.57, 1.9
H_FRACTION = 0.004                                    # [N]: 0.4 vol%
N_CLUSTERS = 10
W, H, T = 8.0, 12.0, 2.0                              # mm: across the beam (x), vertical (y), along the beam (z)
SEED = 7


def fit(host, makes, rng, n=20000):
    """Shapes (descriptions) made by makes[k](scale), each shrunk until it lies in `host` (a shape) without touching
    the ones kept before (tested both ways on points drawn inside them); returns the descriptions kept."""
    kept, shapes = [], []
    for make in makes:
        for scale in np.linspace(1.0, 0.35, 14):
            d = make(scale)
            sh = S.make(d)
            pts = sample_points(sh, n, rng)
            if isinstance(sh, S.Box):                 # its corners and the middles of its edges too
                g = np.array([[x, y, z] for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)
                              if (x != 0) + (y != 0) + (z != 0) >= 2], float)
                pts = np.vstack([pts, sh.t + (g * sh.h) @ sh.R.T])
            if len(pts) > 50 and host.inside(pts).all() and not any(o.inside(pts).any() for o in shapes) and \
                    not any(sh.inside(sample_points(o, 400, rng)).any() for o in shapes):
                kept.append(d); shapes.append(sh)
                break
    return kept


def clast_component(spec, body_mat, h_mat, seed, rng):
    """An H-Fe-ox clast of [N] centered at its origin: a lumpy body, a euhedral Fe-Ti oxide grain on one side (a
    cube turned at random), the H-rich region on the other, elongated feldspar grains next to the oxide."""
    size = np.asarray(spec["clast"], float)
    body = {"type": "blob", "size": size.tolist(), "wobble": 0.12 if size.max() >= 0.2 else 0.0, "seed": seed}
    host = S.make(body)
    off = 0.28 * size[0]
    rot = {"euler_deg": [float(a) for a in rng.uniform(0, 360, 3)]}
    ox, hs = float(spec["oxide"]), np.asarray(spec["H"], float)
    makes = [lambda s: {"type": "box", "size": [ox * s, ox * 1.06 * s, ox * s], "position": [-off, 0.0, 0.0],
                        "rotation": rot},
             lambda s: {"type": "blob", "size": (hs * s).tolist(), "wobble": 0.2 if hs.max() * s >= 0.15 else 0.0,
                        "seed": seed + 1, "position": [off, 0.0, 0.0]}]
    for k in range(spec.get("feldspars", 0)):
        p = [-off + float(x) for x in rng.normal(0, 1, 3) * size * 0.25]
        r = {"euler_deg": [float(a) for a in rng.uniform(0, 360, 3)]}
        fs = np.array([0.10, 0.44, 0.15]) * (size.max() / 0.38)
        makes.append(lambda s, p=p, r=r, k=k, fs=fs: {"type": "blob", "size": (fs * s).tolist(), "wobble": 0.1,
                                                      "seed": seed + 2 + k, "position": p, "rotation": r})
    parts = fit(host, makes, rng)
    if len(parts) < 2:
        raise RuntimeError(f"clast {spec}: its oxide grain and H-rich region do not fit in it")
    names = ["Fe-Ti oxide", h_mat] + ["plagioclase"] * (len(parts) - 2)
    labels = ["euhedral oxide", "H-rich region"] + ["feldspar"] * (len(parts) - 2)
    return dict(material=body_mat, shape=body,
                children=[dict(name=lb, material=m, shape=p) for lb, m, p in zip(labels, names, parts)])


def part_volumes(comp):
    """Exact volumes [mm³] of a component's body and of each of its parts."""
    return S.make(comp["shape"]).volume(), [(c["material"], S.make(c["shape"]).volume()) for c in comp["children"]]


def body_target(comps, no_h, sig):
    """Σ of the body of clasts such that, without their H-rich region, they have Σ = no_h (the mean over the clast
    without H: (Σ_body V_rest + Σ_i Σ_i V_i) / (V_body − V_H) = no_h)."""
    V = Vrest = known = 0.0
    for comp in comps:
        vb, parts = part_volumes(comp)
        vh = sum(v for m, v in parts if m.startswith("H-rich"))
        V += vb - vh
        known += sum(sig[m] * v for m, v in parts if not m.startswith("H-rich"))
        Vrest += vb - vh - sum(v for m, v in parts if not m.startswith("H-rich"))
    return (no_h * V - known) / Vrest


def recipe():
    rng = np.random.default_rng(SEED)
    sig = {k: float(sc.sigma(scm.solid(v), [1.8])[0]) for k, v in PHASES.items()}
    sig["plagioclase"] = sig["plagioclase"]
    comps, mats = {}, {}
    for k, v in PHASES.items():
        mats[k] = {"minerals": v, "source": "[N] S2; [P]; densities of mineralogy handbooks"}
    mats["matrix"] = {"calibrate": {"base": {"minerals": PHASES["matrix"]}, "add": "water", "sigma_cm": 0.45,
                                    "wavelength_A": 1.8}, "source": "[N] Table S2: matrix, 0.45 cm⁻¹ at ICON"}
    mats["void"] = {"ncrystal": "void.ncmat"}
    mats["aluminium"] = {"ncrystal": "Al_sg225.ncmat"}
    for i, spec in enumerate(BIG):                    # the three clasts of [N], each with its own materials
        c = clast_component(spec, f"H-Fe-ox clast {i + 1}", f"H-rich region {i + 1}", 300 + 10 * i, rng)
        comps[f"clast {i + 1} of Naver et al."] = c
        mats[f"H-rich region {i + 1}"] = {"calibrate": {"base": {"minerals": H_REGION}, "add": "water",
                                                        "sigma_cm": spec["with_h"], "wavelength_A": 1.8},
                                          "source": f"[N] Table S2: clast {i + 1}, {spec['with_h']} cm⁻¹ with H"}
        t = body_target([c], spec["no_h"], sig)
        mats[f"H-Fe-ox clast {i + 1}"] = {"calibrate": {"base": {"minerals": CLAST_BODY}, "add": "water",
                                                        "sigma_cm": round(t, 5), "wavelength_A": 1.8},
                                          "source": f"[N] Table S2: clast {i + 1}, {spec['no_h']} cm⁻¹ without H (its "
                                                    f"body set to {t:.3f} cm⁻¹ around its oxide and feldspars)"}
    small = []
    for j, spec in enumerate(SMALL):                  # the smaller clasts: three shapes, the average Σ of [N]
        c = clast_component(spec, "H-Fe-ox clast", "H-rich region", 400 + 10 * j, rng)
        comps[f"small H-Fe-ox clast {'abc'[j]}"] = c
        small.append(c)
    mats["H-rich region"] = {"calibrate": {"base": {"minerals": H_REGION}, "add": "water", "sigma_cm": AVG_H,
                                           "wavelength_A": 1.8},
                             "source": "[N] Table S2: average of the clasts, 1.9 cm⁻¹ with H"}
    t = body_target(small, AVG_NO_H, sig)
    mats["H-Fe-ox clast"] = {"calibrate": {"base": {"minerals": CLAST_BODY}, "add": "water", "sigma_cm": round(t, 5),
                                           "wavelength_A": 1.8},
                             "source": f"[N] Table S2: average, {AVG_NO_H} cm⁻¹ without H (body {t:.3f} cm⁻¹)"}
    # how many smaller clasts make 0.4 % of H-rich regions, with the three large ones and the fragments
    v_piece = sc.make_shape({"type": "sawn_piece", "size": [W, H, T], "seed": 11}).volume()
    h_of = lambda c: sum(v for m, v in part_volumes(c)[1] if m.startswith("H-rich"))
    v_big = sum(h_of(comps[f"clast {i + 1} of Naver et al."]) for i in range(3))
    a, b = SCALE
    es3 = (b ** 4 - a ** 4) / (4 * (b - a))           # mean of scale³ (uniform scale)
    v_frag = 90 * np.pi / 6 * 0.06 ** 3 * 0.8 * 0.8
    v_small = np.mean([h_of(c) for c in small]) * es3
    n_small = int(round((H_FRACTION * v_piece - v_big - v_frag) / v_small / 3))
    cl = lambda spread: {"count": N_CLUSTERS, "spread_mm": spread, "group": "H-Fe-ox clasts"}
    fill = (
        [dict(use=f"clast {i + 1} of Naver et al.", count=1, scale=[1.0, 1.0], clusters=cl(0.3), secret=True,
              name=f"clast {i + 1} of Naver et al.") for i in range(3)] +
        [dict(use=f"small H-Fe-ox clast {x}", count=n_small, scale=list(SCALE), clusters=cl(0.4), secret=True,
              name="H-Fe-ox clast", tries=800) for x in "abc"] +
        [dict(material="H-rich region", count=90, size_mm=[0.04, 0.08], aspect=[[0.6, 1], [0.6, 1]],
              grain={"type": "blob", "wobble": 0.0}, clusters=cl(0.5), secret=True, name="H-rich fragment"),
         dict(material="plagioclase", fraction=0.05, size_mm=[0.1, 0.5], grain={"type": "blob", "wobble": 0.12},
              wobble_from_mm=0.25),
         dict(material="pyroxene", fraction=0.05, size_mm=[0.1, 0.5], grain={"type": "blob", "wobble": 0.12},
              wobble_from_mm=0.25),
         dict(material="Fe-Ti oxide", count=2500, size={"lognormal": {"median_mm": 0.040, "sigma": 0.5},
                                                        "min_mm": 0.016, "max_mm": 0.080},
              aspect=[[0.6, 1], [0.6, 1]], grain={"type": "blob", "wobble": 0.0}),
         dict(material="apatite", count=150, size={"lognormal": {"median_mm": 0.050, "sigma": 0.5},
                                                   "min_mm": 0.020, "max_mm": 0.100},
              aspect=[[0.6, 1], [0.6, 1]], grain={"type": "blob", "wobble": 0.0}),
         dict(material="pyrite", count=60, size={"lognormal": {"median_mm": 0.040, "sigma": 0.5},
                                                 "min_mm": 0.016, "max_mm": 0.080},
              aspect=[[0.6, 1], [0.6, 1]], grain={"type": "blob", "wobble": 0.0}),
         dict(material="void", count=40, size_mm=[0.06, 0.12], aspect=[[0.7, 1], [0.7, 1]],
              grain={"type": "blob", "wobble": 0.15}, name="pore")])
    lithic = dict(name="basaltic lithic clast", material="pyroxene",
                  shape={"type": "blob", "size": [1.1, 0.9, 0.7], "wobble": 0.08, "seed": 500,
                         "position": [-2.0, 2.5, 0.0], "rotation": {"euler_deg": [35.0, 20.0, 10.0]}},
                  fill=[dict(material="plagioclase", count=30, size_mm=[0.22, 0.36],
                             aspect=[[0.14, 0.23], [0.25, 0.45]], grain={"type": "blob", "wobble": 0.0},
                             margin_mm=0.01, gap_mm=0.004, name="plagioclase lath")])
    crack = dict(name="crack", material="void",
                 shape={"type": "ellipsoid", "size": [1.2, 1.0, 0.02], "position": [1.6, -3.6, 0.1],
                        "rotation": {"euler_deg": [40.0, 0.0, 75.0]}})
    return dict(
        samplecraft=1, name="Martian meteorite NWA 7034 (piece of 12 × 8 × 2 mm)", seed=SEED,
        description="The piece of NWA 7034 of Naver et al. (2026); sources: odin/samples/gen_nwa7034.py.",
        provenance=dict(
            sources=["[N] E. B. Naver, K. W. Nikolajsen et al., arXiv:2601.08390 (2026), CC BY 4.0",
                     "[P] the ODIN beamtime proposal (model tomo_slice_nwa7034)",
                     "C. B. Agee et al., Science 339, 780 (2013)"],
            assumptions=["positions of the clusters and clasts: random (seed 7)",
                         "sizes of clasts 2 and 3, of their oxide grains and H-rich regions: within the ranges of [N]",
                         "three shapes of smaller clasts, scaled 0.64 to 1.36 and turned at random",
                         "hydrogen represented by liquid water, calibrated on the Σ measured at ICON"]),
        materials=mats, components=comps,
        bodies=[dict(name="the piece", material="matrix", shape={"type": "sawn_piece", "size": [W, H, T], "seed": 11},
                     children=[lithic, crack], fill=fill),
                dict(name="aluminium pin", material="aluminium", holder=True,
                     shape={"type": "cylinder", "diameter": 3.0, "height": 6.0, "position": [0.0, -9.0, 0.0]})])


def main(out_dir=HERE):
    t0 = time.time()
    r = recipe()
    scene = sc.Scene.from_dict(r)
    print(f"built in {time.time() - t0:.0f} s, {sum(1 for _ in scene.walk())} bodies", flush=True)
    for x in scene.report:
        print("  ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()}, flush=True)
    problems = scene.check(n=600)
    print("check:", problems[:10] or "no problem", flush=True)
    cfg = scene.cfg()
    for k in cfg:
        print(f"  {k:28s} Σ(1.8 Å) = {sc.sigma(cfg[k], [1.8])[0]:.3f} cm⁻¹", flush=True)
    vols = scene.volumes(h=0.01)
    v_piece = scene.bodies[0].shape.volume()
    h_frac = sum(v for m, v in vols.items() if m.startswith("H-rich")) / v_piece
    big = []
    for b, _, _ in scene.walk():
        if b.name.endswith("of Naver et al. 1"):
            size = r["components"][b.name[:-2]]["shape"]["size"]
            c = b.shape.bounding_sphere()[0]
            big.append(f"{b.name[:-2]}: {' x '.join(f'{1e3 * s:.0f}' for s in size)} µm³ at "
                       f"({', '.join(f'{x:.2f}' for x in c)}) mm")
    n_clasts = sum(1 for b, _, _ in scene.walk() if (getattr(b, "material", None) or "").startswith("H-Fe-ox clast"))
    spec = {
        "name": "Martian meteorite NWA 7034 (piece of 12 × 8 × 2 mm)",
        "description": (
            "A sawn piece of the Martian meteorite NWA 7034 (\"Black Beauty\"), 12 mm high, 8 mm wide and 2 mm thick, "
            "its edges slightly irregular and one corner broken, standing on the rotation stage (its 2 mm thickness "
            "along the beam at 0°): the piece studied by Naver et al. (2026). A breccia: clasts of plagioclase and "
            "pyroxene, a basaltic lithic clast, Fe-Ti oxide grains, a few pores and a crack in a fine-grained matrix; "
            "some small clasts hold hydrogen (iron oxyhydroxides), which neutrons see very well. It is glued on an "
            "aluminium pin (3 mm in diameter) on the axis of the rotation stage."),
        "formula": "matrix (plagioclase, pyroxenes, Fe oxides, apatite); plagioclase, pyroxene, Fe-Ti oxides, apatite, "
                   "pyrite; H in Fe-oxyhydroxides",
        "hidden": ["inclusions"],
        "hybrid_only": True,
        "reference": ("E. B. Naver, K. W. Nikolajsen et al., Direct detection of hydrogen reveals a new macroscopic "
                      "crustal water reservoir on early Mars, arXiv:2601.08390 (2026); C. B. Agee et al., Science 339, "
                      "780 (2013). Generated by odin/samples/gen_nwa7034.py (what is taken from the paper, from the "
                      "model of the beamtime proposal, and what is assumed: see that file)."),
        "hidden_answer": (f"{n_clasts} H-Fe-ox clasts in {N_CLUSTERS} clusters, 90 small H-rich fragments; H-rich "
                          f"regions {100 * h_frac:.2f} % of the volume; the three largest: {'; '.join(big)}; Σ(1.8 Å): "
                          f"matrix 0.45, other clasts {AVG_NO_H} without H, H-rich {AVG_H} cm⁻¹"),
        "scene": scene.to_dict(),
    }
    with open(os.path.join(out_dir, "meteorite_nwa7034.yml"), "w", encoding="utf-8") as f:
        f.write("# Generated by gen_nwa7034.py (do not edit by hand): the piece of NWA 7034 of Naver et al. (2026), "
                "a samplecraft scene.\n")
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)
    print(spec["hidden_answer"])
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HERE)
