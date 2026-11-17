"""Writes meteorite_nwa7034.yml: the piece of the Martian meteorite NWA 7034 studied by Naver et al. (2026), in 3D,
for the hybrid model of ODIN (camera images, tomography, time of flight).

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
  * the outline: a sawn piece, its edges slightly irregular and rounded, one corner broken;
  * mineral clasts of plagioclase and pyroxene, 0.1 to 0.5 mm, about 5 % of the volume each;
  * one basaltic lithic clast (1.1 × 0.9 × 0.7 mm), pyroxene with plagioclase laths;
  * the visible Fe-Ti oxide grains, 10 to 80 µm (log-normal), a few apatite and pyrite grains;
  * small H-rich fragments broken off the clasts into the matrix;
  * a few pores and one thin crack.
Assumed here: where the clusters and clasts are (random, fixed seed); the sizes of clasts 2 and 3 and of their
oxide grain and H-rich region within the ranges of [N]; the lumpy shapes (rock_shapes.py "blob"); the composition of
the clasts (plagioclase, maghemite, ilmenite: the phases of the XRD-CT of [N], Fig. 3). The Fe-Ti oxide grains below
10 µm (most of the 3 vol%) stay in the matrix, whose Σ is the measured one.
Materials: NCrystal "solid::" mixtures of the elements of each phase (no Bragg edges: fine-grained rock), plus a
fraction of liquid water standing for the hydrogen ([N]: "we assume that all excess measured neutron attenuation
results from the presence of hydrogen"), set so that Σ(1.8 Å) is the value measured at ICON. In a clast, the body
(the fine intergrowth around the grains drawn one by one) is set so that the clast without its H-rich region has the
measured Σ "without H".
"""
import os
import sys
import time

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))          # twin/: rock_builder, rock_shapes
import rock_builder as rb  # noqa: E402
import rock_shapes as rs  # noqa: E402

MINERALS = rb.MINERALS                                               # minerals and solid(): rock_builder
solid = rb.solid

# mineral volume fractions; target: Σ(1.8 Å) measured at ICON [cm⁻¹] (None: the minerals alone, no hydrogen)
PHASES = {
    "matrix": dict(vol=dict(plag=38, opx=25.4, cpx=18.2, mag=9.7, afs=4.9, ap=3.7), target=0.45),
    "plagioclase": dict(vol=dict(plag=85, afs=15), target=None),
    "pyroxene": dict(vol=dict(opx=58, cpx=42), target=None),
    "Fe-Ti oxide": dict(vol=dict(mag=65, ilm=35), target=None),
    "apatite": dict(vol=dict(ap=100), target=None),
    "pyrite": dict(vol=dict(py=100), target=None),
}
CLAST_BODY = dict(plag=50, magh=25, ilm=25)            # the fine intergrowth of a clast (set to its measured Σ)
H_REGION = dict(magh=65, ilm=20, plag=15)             # the Fe-oxyhydroxides ([N]: 20-50 wt% maghemite in H-regions)
WATER = "stdlib::LiquidWaterH2O_T293.6K.ncmat"
# the three clasts of [N]: size of the clast, its euhedral oxide grain and its H-rich region [mm]; Σ measured
BIG = [dict(clast=(0.30, 0.38, 0.33), oxide=0.17, H=(0.12, 0.35, 0.23), no_h=0.56, with_h=1.9),
       dict(clast=(0.22, 0.33, 0.26), oxide=0.12, H=(0.10, 0.28, 0.18), no_h=0.57, with_h=1.7),
       dict(clast=(0.12, 0.27, 0.15), oxide=0.06, H=(0.06, 0.20, 0.10), no_h=0.58, with_h=2.0)]
AVG_NO_H, AVG_H = 0.57, 1.9
N_CLUSTERS, CLUSTER_SPREAD = 10, 0.35          # mm (assumed: the paper gives neither)
W, H, T = 8.0, 12.0, 2.0                    # mm: across the beam (x), vertical (y), along the beam (z) at 0°
SLAB = (W * 1e-3, H * 1e-3, T * 1e-3, 11)   # rock_shapes "slab" (seed 11)


def sigma(cfg, wl=1.8):
    import NCrystal as NC
    m = NC.load(cfg)
    return float((m.scatter.xsect(wl=wl) + m.absorption.xsect(wl=wl)) * m.info.getNumberDensity())


def calibrated(vol, target):
    """NCrystal configuration of minerals `vol` with the fraction of water that gives Σ(1.8 Å) = target (bisection);
    the dry minerals if they already attenuate more."""
    s = solid(vol)
    if target is None or sigma(s) >= target:
        return s, sigma(s)
    mix = lambda w: f"phases<{1 - w:.4f}*{s}&{w:.4f}*{WATER}>"
    lo, hi = 0.0, 0.9
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if sigma(mix(mid)) < target else (lo, mid)
    return mix(0.5 * (lo + hi)), sigma(mix(0.5 * (lo + hi)))


# --------------------------------------------------------------------------- geometry
class Piece(rb.Rock):
    """The piece of [N] (a sawn slab of matrix, rock_builder) and what [N] and [P] put in it."""

    def __init__(self, seed=7):
        super().__init__(dict(material="matrix", shape="slab", center_mm=[0, 0, 0], size_mm=[W, H, T], seed=SLAB[3]),
                         seed=seed)

    @staticmethod
    def clast_wobble(size):
        return 0.12 if max(size) >= 0.2 else 0.0

    def clast(self, spec, center, body_material, h_material, feldspars=0, frac_offset=0.28, ang=None):
        """An H-Fe-ox clast of [N]: a lumpy body, a euhedral Fe-Ti oxide grain on one side, the H-rich region on the
        other, interlocking feldspar grains around the oxide. Its parts are fitted inside (shrunk until they fit).
        Returns the index of the body and those of its parts."""
        size = np.asarray(spec["clast"], float)
        ang = ang or self.angles()
        body = self.blob(body_material, center, size, ang, self.clast_wobble(size), secret=True)
        R = rs._rot(*ang)
        ex = R[:, 0]                                     # the long axis of the oxide-H arrangement: x of the clast
        c_ox = np.asarray(center) - frac_offset * size[0] * ex
        c_h = np.asarray(center) + frac_offset * size[0] * ex

        def oxide(scale):                                # the euhedral oxide grain (a cube turned about y)
            s = spec["oxide"] * scale
            return dict(material="Fe-Ti oxide", shape="box", inside=body, secret=True, center_mm=rb._r(c_ox),
                        size_mm=[round(float(s), 4), round(float(s * 1.06), 4), round(float(s), 4),
                                 round(float(self.rng.uniform(0, 90)), 1)])

        def h_region(scale):                             # the Fe-oxyhydroxides, no defined grains
            hs = np.asarray(spec["H"], float) * scale
            return dict(material=h_material, shape="blob", inside=body, secret=True, center_mm=rb._r(c_h),
                        size_mm=rb._r(hs), angles_deg=[round(float(a), 1) for a in ang],
                        wobble=0.2 if hs.max() >= 0.15 else 0.0, seed=self.next_seed())

        def feldspar(scale):                             # an elongated feldspar grain next to the oxide
            fs = np.array([0.10, 0.44, 0.15]) * (size.max() / 0.38) * scale
            c = c_ox + R @ (self.rng.normal(0, 1, 3) * size * 0.25)
            return dict(material="plagioclase", shape="blob", inside=body, secret=True, center_mm=rb._r(c),
                        size_mm=rb._r(fs), angles_deg=self.angles(), wobble=0.1, seed=self.next_seed())

        parts = []
        for make in [oxide, h_region] + [feldspar] * feldspars:
            k = self.fit_inside(body, make, avoid=parts)
            if k is not None:
                parts.append(k)
        return body, parts

    def build(self):
        rng = self.rng
        t0 = time.time()
        report = {}
        piece_mm3 = report["piece_mm3"] = self.volume_mm3()
        # one basaltic lithic clast ([P]): pyroxene with plagioclase laths (the largest object: placed first)
        ang = self.angles()
        c = self.free_blob((1.1, 0.9, 0.7), ang, 0.08, near=np.array([-2.0, 2.5, 0.0]), spread=0.6, tries=5000)
        lith = self.blob("pyroxene", c, (1.1, 0.9, 0.7), ang, 0.08)
        laths = []

        def lath(scale):
            p = c + rng.uniform(-0.45, 0.45, 3) * np.array([1.1, 0.9, 0.7])
            return dict(material="plagioclase", shape="blob", inside=lith, center_mm=rb._r(p),
                        size_mm=[round(float(rng.uniform(0.22, 0.36)), 4), 0.05, round(float(rng.uniform(0.08, 0.14)), 4)],
                        angles_deg=self.angles(), wobble=0.0, seed=self.next_seed())
        for _ in range(300):
            if len(laths) >= 30:
                break
            k = self.fit_inside(lith, lath, scales=[1.0], avoid=laths, n_pts=800)
            if k is not None:
                laths.append(k)
        report["laths"] = len(laths)
        # mineral clasts of plagioclase and pyroxene, 0.1 to 0.5 mm, about 5 % of the volume each ([P]), anywhere
        minerals = [dict(material=m, fraction=0.05, size_mm=(0.1, 0.5), wobble=0.12, wobble_from_mm=0.25)
                    for m in ("plagioclase", "pyroxene")]
        for m, (ks, v, want) in zip(minerals, self.fill(minerals)):
            report[m["material"]] = len(ks)
            print(f"{m['material']} clasts: {len(ks)}, {100 * v / piece_mm3:.1f} %, {time.time() - t0:.0f} s", flush=True)
        # the clusters of H-Fe-ox clasts ([N]: "localised macroscopic clusters"), anywhere in the piece
        clusters = self.clusters(N_CLUSTERS)
        # the three clasts of [N], each in its own cluster, with their own measured Σ
        clasts = []
        for i, spec in enumerate(BIG):
            ang = self.angles()
            c = self.free_blob(spec["clast"], ang, self.clast_wobble(spec["clast"]), near=clusters[i], spread=0.3,
                               tries=5000)
            body, parts = self.clast(spec, c, f"H-Fe-ox clast {i + 1}", f"H-rich region {i + 1}", feldspars=4 - i,
                                     ang=ang)
            clasts.append((i, body, parts))
        h_vol = sum(self.blob_volume(k) for k, v in enumerate(self.vols) if v["material"].startswith("H-rich"))
        # the other clasts of the clusters, until the H-rich regions make 0.4 % of the volume
        n_small = k = 0
        while h_vol < 0.004 * piece_mm3 and k < 4000:
            k += 1
            size = np.array([rng.uniform(0.10, 0.26), rng.uniform(0.16, 0.34), rng.uniform(0.10, 0.28)])
            spec = dict(clast=size, oxide=float(rng.uniform(0.25, 0.45) * size.min()),
                        H=size * np.array([0.40, 0.80, 0.60]) * rng.uniform(0.7, 1.0))
            ang = self.angles()
            c = self.free_blob(size, ang, self.clast_wobble(size), near=clusters[k % len(clusters)],
                               spread=CLUSTER_SPREAD)
            if c is None:
                continue
            body, parts = self.clast(spec, c, "H-Fe-ox clast", "H-rich region", ang=ang)
            h_vol += sum(self.blob_volume(p) for p in parts if self.vols[p]["material"] == "H-rich region")
            n_small += 1
        # small H-rich fragments broken off into the matrix, near the clusters ([P])
        frags, v_frag, _ = self.population("H-rich region", count=90, size_mm=(0.04, 0.08), aspect=((0.6, 1), (0.6, 1)),
                                           clusters=clusters, spread_mm=0.5, secret=True)
        h_vol += v_frag
        report.update(n_small=n_small, n_frag=len(frags), h_mm3=h_vol)
        print(f"H-Fe-ox clasts: {3 + n_small}, H {100 * h_vol / piece_mm3:.2f} %, {len(self.vols)} volumes, "
              f"{time.time() - t0:.0f} s", flush=True)
        # dispersed grains ([N]: Fe-Ti oxides "dispersed throughout"; [P]: sizes, apatite, pyrite)
        grains = [dict(material="Fe-Ti oxide", count=2500, median_mm=0.040, size_lim_mm=(0.016, 0.080)),
                  dict(material="apatite", count=150, median_mm=0.050, size_lim_mm=(0.020, 0.100)),
                  dict(material="pyrite", count=60, median_mm=0.040, size_lim_mm=(0.016, 0.080))]
        for g in grains:
            g.update(sigma=0.5, aspect=((0.6, 1.0), (0.6, 1.0)))
        for g, (ks, v, want) in zip(grains, self.fill(grains)):
            report[g["material"]] = len(ks)
        print(f"grains: {time.time() - t0:.0f} s", flush=True)
        # a few pores and one thin crack ([P])
        pores, _, _ = self.population("void", count=40, size_mm=(0.06, 0.12), aspect=((0.7, 1), (0.7, 1)), wobble=0.15)
        report["pores"] = len(pores)
        for _ in range(200):
            ang = [round(float(rng.uniform(0, 180)), 1), 0.0, round(float(rng.uniform(60, 120)), 1)]
            c = self.free_blob((1.2, 1.0, 0.02), ang, 0.0)
            if c is not None:
                self.blob("void", c, (1.2, 1.0, 0.02), ang, 0.0)
                break
        report["volumes"] = len(self.vols)
        return clasts, report


def main():
    pc = Piece()
    clasts, rep = pc.build()
    mats, sig = {}, {}
    for k, ph in PHASES.items():
        mats[k], sig[k] = calibrated(ph["vol"], ph["target"])
    mats["void"] = "void.ncmat"
    # the clasts: the H-rich region at its measured Σ; the body so that the clast without its H region has the
    # measured Σ "without H" (its oxide and feldspar grains drawn one by one)
    vols = pc.vols
    vol = lambda v: (rs.blob_volume(pc.dims(v)) if v["shape"] == "blob" else float(np.prod(v["size_mm"][:3])) * 1e-9) * 1e9

    def body_target(bodies, no_h):
        V = Vrest = 0.0
        known = 0.0
        for b in bodies:
            vb = vol(vols[b])
            parts = [w for w in vols if w.get("inside") == b]
            vh = sum(vol(w) for w in parts if w["material"].startswith("H-rich"))
            V += vb - vh
            for w in parts:
                if not w["material"].startswith("H-rich"):
                    known += sig[w["material"]] * vol(w)
            Vrest += vb - vh - sum(vol(w) for w in parts if not w["material"].startswith("H-rich"))
        return (no_h * V - known) / Vrest

    for i, spec in enumerate(BIG):
        b = clasts[i][1]
        t = body_target([b], spec["no_h"])
        mats[f"H-Fe-ox clast {i + 1}"], sig[f"H-Fe-ox clast {i + 1}"] = calibrated(CLAST_BODY, t)
        mats[f"H-rich region {i + 1}"], sig[f"H-rich region {i + 1}"] = calibrated(H_REGION, spec["with_h"])
    small = [k for k, v in enumerate(vols) if v["material"] == "H-Fe-ox clast"]
    t = body_target(small, AVG_NO_H)
    mats["H-Fe-ox clast"], sig["H-Fe-ox clast"] = calibrated(CLAST_BODY, t)
    mats["H-rich region"], sig["H-rich region"] = calibrated(H_REGION, AVG_H)
    for k in mats:
        print(f"{k:22s} Σ(1.8 Å) = {sig.get(k, 0):.3f} cm⁻¹   {mats[k][:70]}")
    # the holder (assumed): an aluminium pin, 3 mm in diameter, on the axis of the rotation stage, the piece glued on
    # its top ([N]: "glued to a stick"; the glue, a fraction of a millimeter, not modeled)
    vols.append(dict(material="aluminium", shape="cylinder", center_mm=[0, -9.0, 0], size_mm=[3.0, 6.0, 3.0],
                     holder=True))
    mats["aluminium"] = "Al_sg225.ncmat"
    big_txt = "; ".join(
        f"clast {i + 1} {' x '.join(f'{1e3 * s:.0f}' for s in vols[b]['size_mm'])} µm³ at "
        f"({', '.join(f'{x:.2f}' for x in vols[b]['center_mm'])}) mm, Σ {BIG[i]['no_h']} / {BIG[i]['with_h']} cm⁻¹"
        for i, b, _ in clasts)
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
        "hidden_answer": (f"{3 + rep['n_small']} H-Fe-ox clasts in {N_CLUSTERS} clusters, {rep['n_frag']} small H-rich "
                          f"fragments; H-rich regions {100 * rep['h_mm3'] / rep['piece_mm3']:.2f} % of the volume; "
                          f"the three largest: {big_txt}; Σ(1.8 Å): matrix {sig['matrix']:.2f}, other clasts "
                          f"{AVG_NO_H} without H, H-rich {AVG_H} cm⁻¹"),
        "materials": mats,
        "volumes": vols,
    }
    with open(os.path.join(HERE, "meteorite_nwa7034.yml"), "w", encoding="utf-8") as f:
        f.write("# Generated by gen_nwa7034.py (do not edit by hand): the piece of NWA 7034 of Naver et al. (2026).\n")
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)
    print(rep)
    print(spec["hidden_answer"])


if __name__ == "__main__":
    main()
