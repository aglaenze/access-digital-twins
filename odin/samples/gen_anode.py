"""Writes the samples of the exercise "Where has the fuel-cell anode been reduced?" (Bragg-edge phase mapping of
NiO -> Ni in solid-oxide-cell anode supports):

    python gen_anode.py

  * anode_standards_a.yml   two bars, reduced to 0 % (as sintered, top) and 52 % (bottom), uniformly;
  * anode_standards_b.yml   two bars, 11 % (top) and 92 % (bottom);
  * anode_loaded_700C.yml   two bars reduced together at 700 °C for 5 min: the top one under a bending load (its
                            reduction degree changes along it and across it), the bottom one without load (reference).

Source: M. G. Makowska, M. Strobl, E. M. Lauridsen, H. L. Frandsen, A. S. Tremsin, T. Shinohara, L. Theil Kuhn,
"Phase Transition Mapping by Means of Neutron Imaging in SOFC Anode Supports During Reduction Under Applied Stress",
ECS Trans. 68(1), 1103-1114 (2015), measured at NOBORU (J-PARC); and M. G. Makowska et al., J. Appl. Cryst. 49,
1674-1681 (2016), measured at Engin-X (ISIS). What is taken from them:
  * bars of hot-pressed, sintered NiO-YSZ tape, 20 x 6 x 0.9 mm3 (ECS 2015), standing on their edge: 20 mm along x,
    6 mm high (y), 0.9 mm along the beam; held side by side in a holder;
  * reduction degrees (NiO turned into Ni, from the weight loss) of whole bars: 11 %, 52 %, 92 % (the reference
    patterns of their figure 3), and 0 % (as sintered);
  * the bars reduced together at 700 °C for 5 min (their figure 5): bent bar 33 % on average, 39 % in its bent part
    (area A), 28 % behind the load point (area B); the reference bar 27 %; compressed and tensed sides both reduced
    faster than the middle (their figure 8);
  * the Bragg edges used: NiO(220) 2.95 A, Ni(200) 3.52 A, Ni(111) 4.06 A, NiO(200) 4.17 A.
What is assumed (not in these two papers; given in Makowska et al., J. Appl. Cryst. 48, 401 (2015), not read):
  * the composition: 56 wt% NiO and 44 wt% 3YSZ (a usual anode support; 3 mol% yttria-stabilized zirconia, tetragonal,
    modeled by tetragonal ZrO2 of NCrystal), a porosity of 15 % as sintered;
  * NiO -> Ni keeps the outer size of the bar: the Ni takes 60 % of the volume of its NiO, the rest becomes pores;
  * the cantilever: clamped at x < -7 mm, loaded at x = +3 mm; the bending moment falls linearly from the clamp to
    the load point and is zero beyond; the extra reduction is proportional to |stress|, scaled to give the 39 % and
    28 % of the paper.
"""
import os

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
W_NIO = 0.56                                  # mass fraction of NiO in the sintered support (assumed)
RHO_NIO, RHO_YSZ, RHO_NI = 6.807, 6.112, 8.908          # g/cm3 (NCrystal)
M_NIO, M_NI = 74.69, 58.69                    # g/mol
P0 = 0.15                                     # porosity as sintered (assumed)
V_NIO = (W_NIO / RHO_NIO) / (W_NIO / RHO_NIO + (1 - W_NIO) / RHO_YSZ)   # NiO share of the solid volume
NI_PER_NIO = (M_NI / RHO_NI) / (M_NIO / RHO_NIO)         # volume of Ni per volume of NiO reduced: 0.60
LENGTH, HEIGHT, THICK = 20.0, 6.0, 0.9        # mm
Y_TOP, Y_BOTTOM = 3.5, -3.5                   # centers of the two bars in the holder [mm]
CLAMP, LOAD = -7.0, 3.0                       # [mm] end of the clamp, load point
R_FREE, R_BENT = 0.28, 0.39                   # the paper: area B (no stress), area A (bent part)
STEP = 0.5                                    # [mm] cells of the bent bar
QUANT = 0.02                                  # reduction degrees rounded to 2 % (one material each)


def material(r):
    """NCrystal multiphase of a support reduced to the degree r (volume fractions: NiO, Ni, YSZ, pores)."""
    solid = 1 - P0
    f_nio = solid * V_NIO * (1 - r)
    f_ni = solid * V_NIO * r * NI_PER_NIO
    f_ysz = solid * (1 - V_NIO)
    f_nio, f_ni, f_ysz = (round(f, 4) for f in (f_nio, f_ni, f_ysz))
    f_void = round(1 - f_nio - f_ni - f_ysz, 4)                 # the rest: pores (the fractions must add up to 1)
    parts = [(f_nio, "NiO_sg225.ncmat"), (f_ni, "Ni_sg225.ncmat"), (f_ysz, "ZrO2_sg137_Zirconia.ncmat"),
             (f_void, "void.ncmat")]
    return "phases<" + "&".join(f"{f:.4f}*{c}" for f, c in parts if f > 1e-6) + ">"


def name(r):
    return f"reduced {round(100 * r):d} %"


def bar(r, yc):
    return dict(material=name(r), center_mm=[0, yc, 0], size_mm=[LENGTH, HEIGHT, THICK])


def bent_map():
    """Reduction degree of the bent bar on its cells (x, y): R_FREE + k |σ| / σmax, σ ∝ M(x) × (y − yc)."""
    xs = np.arange(-LENGTH / 2 + STEP / 2, LENGTH / 2, STEP)
    ys = np.arange(-HEIGHT / 2 + STEP / 2, HEIGHT / 2, STEP)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    moment = np.clip((LOAD - X) / (LOAD - CLAMP), 0, None) * (X >= CLAMP)        # 1 at the clamp, 0 at the load
    s = moment * np.abs(Y) / (HEIGHT / 2)
    area_a = (X >= CLAMP) & (X < LOAD)
    k = (R_BENT - R_FREE) / s[area_a].mean()
    return xs, ys, R_FREE + k * s


def main():
    out = {}
    for key, (top, bottom) in (("anode_standards_a", (0.0, 0.52)), ("anode_standards_b", (0.11, 0.92))):
        out[key] = {
            "name": f"Anode supports, standards {round(100 * top)} % and {round(100 * bottom)} %",
            "description": (
                f"Two bars of a solid-oxide-cell anode support (NiO-YSZ), 20 x 6 x 0.9 mm3, on their edge in a holder "
                f"(0.9 mm along the beam): the top one reduced to {round(100 * top)} %, the bottom one to "
                f"{round(100 * bottom)} % (NiO turned into Ni, measured by weighing). Uniform: standards to calibrate "
                f"the Bragg edges against the reduction degree."),
            "formula": "NiO + Ni + 3YSZ, porous",
            "materials": {name(top): material(top), name(bottom): material(bottom)},
            "volumes": [bar(top, Y_TOP), bar(bottom, Y_BOTTOM)],
        }
    xs, ys, R = bent_map()
    Rq = np.round(R / QUANT) * QUANT
    mats = {name(r): material(r) for r in sorted(set(Rq.ravel().tolist()) | {0.27})}
    vols = [dict(material=name(Rq[i, j]), center_mm=[round(float(x), 3), round(float(Y_TOP + y), 3), 0],
                 size_mm=[STEP, STEP, THICK]) for i, x in enumerate(xs) for j, y in enumerate(ys)]
    vols.append(bar(0.27, Y_BOTTOM))
    out["anode_loaded_700C"] = {
        "name": "Anode supports reduced at 700 °C for 5 min: loaded (top) and reference (bottom)",
        "description": (
            "Two bars of a solid-oxide-cell anode support (NiO-YSZ), 20 x 6 x 0.9 mm3, on their edge in a holder, reduced "
            "together for 5 minutes at 700 °C in 9 % H2: the top one clamped at its left end and loaded at x = +3 mm "
            "(bent: stretched at its top edge, compressed at its bottom edge, between the clamp and the load point), "
            "the bottom one without load. The reaction was then stopped (frozen by cooling in N2)."),
        "formula": "NiO + Ni + 3YSZ, porous",
        "hidden": ["materials"],
        "hidden_answer": (f"bent bar: area A (x -7 to 3 mm) {R[(xs >= CLAMP) & (xs < LOAD)].mean():.0%}, area B (x > 3) "
                          f"{R_FREE:.0%}, whole bar {R.mean():.0%}; "
                          "reference 27 %"),
        "materials": mats,
        "volumes": vols,
    }
    ref = ("M. G. Makowska et al., ECS Trans. 68(1), 1103 (2015) (NOBORU, J-PARC); M. G. Makowska et al., J. Appl. "
           "Cryst. 49, 1674 (2016) (Engin-X, ISIS). Generated by odin/samples/gen_anode.py (what is taken from the "
           "papers, what is assumed: see that file).")
    for key, spec in out.items():
        spec["hybrid_only"] = True
        spec["reference"] = ref
        with open(os.path.join(HERE, key + ".yml"), "w", encoding="utf-8") as f:
            f.write("# Generated by gen_anode.py (do not edit by hand).\n")
            yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True, width=120)
        print(key, len(spec["volumes"]), "volumes,", len(spec["materials"]), "materials")
    a = (xs >= CLAMP) & (xs < LOAD)
    print(f"bent bar: area A {R[a].mean():.3f}, area B {R[xs >= LOAD].mean():.3f}, max {R.max():.2f}; "
          f"whole bar {R.mean():.3f}")


if __name__ == "__main__":
    main()
