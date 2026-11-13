"""Writes meteorite_nwa7034.yml: the piece of the Martian meteorite NWA 7034 studied by Naver et al. (2026), in 3D,
for the hybrid model of ODIN (camera images, tomography, time of flight).

    python gen_nwa7034.py

Source: E. B. Naver, K. W. Nikolajsen et al., "Direct detection of hydrogen reveals a new macroscopic crustal water
reservoir on early Mars", arXiv:2601.08390 (2026), CC BY 4.0. What is taken from it (section of the paper):
  * the piece: 12 × 8 × 2 mm³ (IV.1); how it was mounted is not said: here the 12 mm side is vertical (the rotation
    axis) and the 2 mm thickness along the beam at 0°;
  * four categories (II): feldspars, Fe-Ti oxides (3 vol%), H-rich Fe-oxyhydroxides (0.4 vol%, "localised
    macroscopic clusters"), a fine-grained matrix (grains below 6.2 µm: pyroxene, plagioclase, phosphate, Fe-Ti oxides);
  * the H-Fe-ox clasts: lithic clasts from 120 × 270 × 150 to 300 × 380 × 330 µm³, H-rich volumes up to
    120 × 350 × 230 µm³, a euhedral Fe-Ti oxide grain of 170 × 180 × 170 µm³ (II); feldspar grains up to
    100 × 440 × 150 µm³ (II);
  * the neutron attenuation measured at ICON (25 meV, 1.8 Å; Table S2): matrix 0.45 cm⁻¹, clasts without H 0.57 cm⁻¹,
    H-rich regions 1.9 cm⁻¹; the matrix mineralogy (S2, from Agee et al. 2013, Science 339, 780): 38 % plagioclase,
    25.4 % pyroxene, 18.2 % clinopyroxene, 9.7 % Fe oxides, 4.9 % alkali feldspar, 3.7 % apatite.
What is assumed (not in the paper): the number of clasts and clusters and where they are (random, fixed seed), their
ellipsoidal shapes, the composition of the clasts (plagioclase, magnetite/maghemite, ilmenite: the phases of the
paper's diffraction, II), the Fe-Ti oxide grains large enough to be seen (most of the 3 vol% are fine, in the matrix).
Materials: NCrystal "solid::" mixtures of the elements of each phase (no Bragg edges: fine-grained rock), plus a
fraction of liquid water standing for the hydrogen (the paper: "we assume that all excess measured neutron attenuation
results from the presence of hydrogen"); that fraction is set so that Σ(1.8 Å) is the value measured at ICON.
"""
import os

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ELEM = {"H": 1.008, "O": 15.999, "P": 30.974, "S": 32.06, "Cl": 35.45, "Fe": 55.845, "Mg": 24.305, "Si": 28.085,
        "Na": 22.990, "Al": 26.982, "Ca": 40.078, "Ti": 47.867}
MINERALS = {                                                         # atoms per formula unit, density [g/cm³]
    "plag": (dict(Na=0.5, Ca=0.5, Al=1.5, Si=2.5, O=8.0), 2.69),     # An50
    "opx": (dict(Mg=1.2, Fe=0.8, Si=2.0, O=6.0), 3.55),
    "cpx": (dict(Ca=0.9, Mg=0.7, Fe=0.4, Si=2.0, O=6.0), 3.40),
    "mag": (dict(Fe=3.0, O=4.0), 5.15),
    "magh": (dict(Fe=2.0, O=3.0), 4.90),
    "ilm": (dict(Fe=1.0, Ti=1.0, O=3.0), 4.72),
    "afs": (dict(Na=1.0, Al=1.0, Si=3.0, O=8.0), 2.62),
    "ap": (dict(Ca=5.0, P=3.0, O=12.0, Cl=1.0), 3.15),
}
# mineral volume fractions; target: Σ(1.8 Å) measured at ICON [cm⁻¹] (None: the minerals alone, no hydrogen)
PHASES = {
    "matrix": dict(vol=dict(plag=38, opx=25.4, cpx=18.2, mag=9.7, afs=4.9, ap=3.7), target=0.45),
    "clast (low H)": dict(vol=dict(plag=50, magh=25, ilm=25), target=0.57),
    "H-rich Fe-oxyhydroxide": dict(vol=dict(magh=65, ilm=20, plag=15), target=1.9),
    "feldspar": dict(vol=dict(plag=85, afs=15), target=None),
    "Fe-Ti oxide": dict(vol=dict(mag=65, ilm=35), target=None),
}
WATER = "stdlib::LiquidWaterH2O_T293.6K.ncmat"


def solid(name):
    ph = PHASES[name]
    vt = sum(ph["vol"].values())
    mass, rho = {}, 0.0
    for k, v in ph["vol"].items():
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


def sigma(cfg, wl=1.8):
    import NCrystal as NC
    m = NC.load(cfg)
    return float((m.scatter.xsect(wl=wl) + m.absorption.xsect(wl=wl)) * m.info.getNumberDensity())


def cfg(name):
    """NCrystal configuration of a phase, its water fraction set (bisection) to give the measured Σ(1.8 Å)."""
    s, target = solid(name), PHASES[name]["target"]
    if target is None or sigma(s) >= target:
        return s, sigma(s)
    mix = lambda w: f"phases<{1 - w:.4f}*{s}&{w:.4f}*{WATER}>"
    lo, hi = 0.0, 0.9
    for _ in range(25):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if sigma(mix(mid)) < target else (lo, mid)
    return mix(0.5 * (lo + hi)), sigma(mix(0.5 * (lo + hi)))


def build(seed=7):
    rng = np.random.default_rng(seed)
    W, H, T = 8.0, 12.0, 2.0                        # mm: across the beam (x), vertical (y), along the beam (z) at 0°
    vols = [dict(material="matrix", center_mm=[0, 0, 0], size_mm=[W, H, T])]
    placed = []

    def free(r, near=None, spread=None, margin=0.03):
        for _ in range(400):
            if near is None:
                c = np.array([rng.uniform(-W / 2 + r + margin, W / 2 - r - margin),
                              rng.uniform(-H / 2 + r + margin, H / 2 - r - margin),
                              rng.uniform(-T / 2 + r + margin, T / 2 - r - margin)])
            else:
                c = near + rng.normal(0, spread, 3)
                lim = np.array([W / 2, H / 2, T / 2]) - r - margin
                if np.any(np.abs(c) > lim):
                    continue
            if all(np.linalg.norm(c - c2) > r + r2 + 0.01 for c2, r2 in placed):
                placed.append((c, r))
                return c
        return None

    def ell(material, c, dims, ang, inside=0):
        vols.append(dict(material=material, shape="ellipsoid", inside=inside,
                         center_mm=[round(float(v), 4) for v in c],
                         size_mm=[round(float(d), 4) for d in dims] + [round(float(ang), 1)]))
        return len(vols) - 1

    # localised clusters of H-Fe-ox clasts (lithic clasts 120x270x150 to 300x380x330 µm³), each with a euhedral Fe-Ti
    # oxide grain and an H-rich region (up to 120x350x230 µm³); the three largest first, as in the paper
    n_clasts, h_vol = 0, 0.0
    big = [np.array([0.30, 0.38, 0.33]), np.array([0.25, 0.33, 0.28]), np.array([0.22, 0.30, 0.25])]
    center = None
    k = 0
    while h_vol < 0.004 * W * H * T and k < 2000:     # until the H-rich regions reach 0.4 vol%
        if k < 3:
            dims, near = big[k], None
        else:
            if (k - 3) % 5 == 0:                         # a new cluster every five clasts
                center = np.array([rng.uniform(-3.5, 3.5), rng.uniform(-5.5, 5.5), 0.0])
            dims = np.array([rng.uniform(0.12, 0.30), rng.uniform(0.27, 0.38), rng.uniform(0.15, 0.33)])
            near = center
        k += 1
        c = free(dims.max() / 2, near=near, spread=0.45 if near is not None else None)
        if c is None:
            continue
        ang = rng.uniform(0, 180)
        host = ell("clast (low H)", c, dims, ang)
        t = np.radians(ang)
        u = np.array([np.cos(t), 0, -np.sin(t)])
        ox = float(min(0.17, 0.45 * dims.min()))                     # euhedral Fe-Ti oxide grain (up to 170 µm)
        vols.append(dict(material="Fe-Ti oxide", shape="box", inside=host,
                         center_mm=[round(float(v), 4) for v in c - 0.22 * dims[0] * u],
                         size_mm=[round(ox, 4)] * 3 + [round(float(ang + 8), 1)]))
        hd = np.minimum([0.12, 0.35, 0.23], dims * [0.4, 0.8, 0.6])   # H-rich region, within the clast
        ell("H-rich Fe-oxyhydroxide", c + 0.25 * dims[0] * u, hd, ang, inside=host)
        h_vol += np.pi / 6 * hd.prod()
        n_clasts += 1
    # feldspar grains (up to 100 x 440 x 150 µm³): elongated
    for _ in range(400):
        dims = np.array([rng.uniform(0.04, 0.10), rng.uniform(0.12, 0.44), rng.uniform(0.05, 0.15)])
        c = free(dims.max() / 2)
        if c is not None:
            ell("feldspar", c, dims, rng.uniform(0, 180))
    # Fe-Ti oxide grains large enough to be seen at 25 µm (most of the 3 vol% are finer, in the matrix mixture)
    for _ in range(300):
        r = rng.uniform(0.02, 0.045)
        c = free(r)
        if c is not None:
            ell("Fe-Ti oxide", c, np.array([2 * r, 2 * r * rng.uniform(0.7, 1), 2 * r * rng.uniform(0.7, 1)]),
                rng.uniform(0, 180))
    return vols, n_clasts, h_vol / (W * H * T)


def main():
    mats, sig = {}, {}
    for k in PHASES:
        mats[k], sig[k] = cfg(k)
        print(f"{k:24s} Σ(1.8 Å) = {sig[k]:.3f} cm⁻¹   {mats[k][:70]}")
    vols, n_clasts, frac = build()
    for v in vols[1:]:
        v.setdefault("inside", 0)
    spec = {
        "name": "Martian meteorite NWA 7034 (piece of 12 × 8 × 2 mm)",
        "description": (
            "A flat piece of the Martian meteorite NWA 7034 (\"Black Beauty\"), 12 mm high, 8 mm wide and 2 mm thick, "
            "standing on the rotation stage (its 2 mm thickness along the beam at 0°): the piece studied by Naver et "
            "al. (2026). A breccia: feldspar grains, Fe-Ti oxides and lithic clasts in a fine-grained matrix; some "
            "clasts hold hydrogen (iron oxyhydroxides), which neutrons see very well."),
        "formula": "matrix (plagioclase, pyroxenes, Fe oxides, apatite); feldspar, Fe-Ti oxides; H in Fe-oxyhydroxides",
        "hidden": ["inclusions"],
        "hybrid_only": True,
        "reference": ("E. B. Naver, K. W. Nikolajsen et al., Direct detection of hydrogen reveals a new macroscopic "
                      "crustal water reservoir on early Mars, arXiv:2601.08390 (2026); C. B. Agee et al., Science 339, "
                      "780 (2013). Generated by odin/samples/gen_nwa7034.py (what is taken from the paper, what is "
                      "assumed: see that file)."),
        "hidden_answer": (f"{n_clasts} H-Fe-ox clasts in localised clusters (the three largest 300x380x330, "
                          f"250x330x280, 220x300x250 µm³); H-rich regions {100 * frac:.2f} % of the volume; "
                          f"Σ(1.8 Å): matrix {sig['matrix']:.2f}, clasts without H {sig['clast (low H)']:.2f}, "
                          f"H-rich {sig['H-rich Fe-oxyhydroxide']:.2f} cm⁻¹"),
        "materials": mats,
        "volumes": vols,
    }
    with open(os.path.join(HERE, "meteorite_nwa7034.yml"), "w", encoding="utf-8") as f:
        f.write("# Generated by gen_nwa7034.py (do not edit by hand): the piece of NWA 7034 of Naver et al. (2026).\n")
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True, width=120)
    print(f"{len(vols)} volumes, {n_clasts} H-Fe-ox clasts, H-rich regions {100 * frac:.2f} % of the volume")


if __name__ == "__main__":
    main()
