"""Writes battery_graphite.yml: the lithium half-cell with an ultra-thick graphite electrode of M. Strobl et al.,
"Concurrent operando neutron imaging and diffraction analysis revealing spatial lithiation phase evolution in an
ultra-thick graphite electrode" (Adv. Energy Mater., 2025; measured at SENJU, J-PARC), the cell of M.-E. Lăcătuşu,
L. Theil Kuhn et al., arXiv:2104.03564 (2021). Operando: the lithium content of the electrode changes along the
charge cycle (device cycle_time of the twin, in hours).

    python gen_battery.py

What is taken from the papers:
  * a cylindrical cell, the layers horizontal, seen edge-on by the beam: Al casing of inner diameter 18 mm with an
    inner PTFE layer 1 mm thick; electrodes 16 mm in diameter: graphite 400 µm thick (above the separator), a glass
    fiber separator (Whatman GF/A) 260 µm, metallic Li 750 µm; stainless steel (316) current collectors; electrolyte
    1 M LiPF6 in EC/DMC 1:1 (hydrogenated) in the pores;
  * one cycle at C/35 (1.37 mA), lithiation then delithiation; theoretical capacity 372 mAh/g (LiC6); about
    100 mAh/g irreversible (SEI and dead Li: x ≈ 0.27 of LiC6), most of it near the separator;
  * lithium enters from the separator side (a gradient that fades as the lithiation goes on), the end of the
    lithiation is nearly homogeneous; the delithiation is delayed far from the separator;
  * the attenuation of the electrode changes about linearly with its Li content (Li: 70.5 b of absorption at 1.8 Å).
What is assumed: the wall of the Al casing (2 mm), the collectors (1 mm each), the porosity of the electrode (35 %,
filled with electrolyte) and of the separator (90 %), the length of the lithiation (30 h), and
the shape of the profiles (below, lithium()). The cycle: lithiation 30 h at C/35 (x = 30/35 = 0.86 passed),
then delithiation until the reversible lithium is out (0.59, 20.5 h), then rest.
"""
import os

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
D_STACK, D_PTFE_OUT, D_AL_OUT = 16.0, 18.0, 22.0         # mm
T_LI, T_SEP, T_GR, T_SS = 0.75, 0.26, 0.40, 1.0          # mm
N_SLICES = 20                                            # slices of 20 µm in the graphite electrode
PORE_GR, PORE_SEP = 0.35, 0.90
T_LITH = 30.0                                            # h: lithiation, at C/35 (x grows by 1/35 per hour)
X_IRR = 0.27                                             # LixC6: irreversible (SEI, dead Li), 100 mAh/g
X_REV = T_LITH / 35 - X_IRR                              # reversible: what the charge passed leaves
T_DELITH = X_REV * 35                                    # h: delithiation, until the reversible part is out
TIMES = np.round(np.arange(0, 55.0 + 0.01, 0.5), 2)      # h: the states written in the file (rest after the end)
QUANT = 0.01                                             # x rounded (one material per value)
ELECTROLYTE = "solid::Li1P1F6C40H66O40/1.29gcm3"         # 1 M LiPF6 in EC/DMC 1:1 by volume


def lithium(t):
    """x in LixC6 of each slice (from the separator up), at time t [h] of the cycle."""
    z = (np.arange(N_SLICES) + 0.5) / N_SLICES                              # 0 at the separator, 1 at the collector
    w_irr = (1.6 - 1.2 * z) / np.mean(1.6 - 1.2 * z)                       # SEI: more at the separator side
    if t <= T_LITH:
        x_irr = X_IRR * min(1.0, t / 8.0)                                  # formed early (0.9 to 0.7 V)
        mean_rev = max(0.0, (X_IRR + X_REV) * t / T_LITH - x_irr)
        g = 0.8 * (1 - mean_rev / X_REV)                                   # gradient, fading toward the end
        rev = mean_rev * (1 + g * (1 - 2 * z))
    else:
        x_irr = X_IRR
        mean_rev = X_REV * max(0.0, 1 - (t - T_LITH) / T_DELITH)
        g = 0.8 * (1 - mean_rev / X_REV)                                   # emptied from the separator side first
        rev = mean_rev * (1 - g * (1 - 2 * z))
    return np.clip(rev, 0, None) + x_irr * w_irr


def electrode(x):
    """The graphite electrode with x Li per C6, its pores filled with electrolyte."""
    li = int(round(100 * x))
    solid = f"solid::C600Li{li}/2.26gcm3" if li else "solid::C/2.26gcm3"
    return f"phases<{1 - PORE_GR:.2f}*{solid}&{PORE_GR:.2f}*{ELECTROLYTE}>"


def main():
    mats = {"aluminium": "Al_sg225.ncmat", "PTFE": "solid::C2F4/2.20gcm3",
            "stainless steel": "solid::Fe65Cr18Ni12Mo2Mn2Si1/8.00gcm3", "lithium": "solid::Li/0.534gcm3",
            "separator": f"phases<{1 - PORE_SEP:.2f}*solid::SiO2/2.20gcm3&{PORE_SEP:.2f}*{ELECTROLYTE}>"}
    # the stack from the bottom: collector, Li, separator, graphite (20 slices), collector; y = 0 at the separator /
    # graphite interface, as in the paper
    y0 = -(T_LI + T_SEP)
    h_stack = T_SS * 2 + T_LI + T_SEP + T_GR
    h_cell = h_stack + 2.0                                       # the casing goes beyond the stack
    yc_stack = -T_SS - T_LI - T_SEP + h_stack / 2
    vols = [dict(material="aluminium", shape="cylinder", center_mm=[0, round(yc_stack, 4), 0],
                 size_mm=[D_AL_OUT, h_cell, D_AL_OUT]),
            dict(material="PTFE", shape="cylinder", center_mm=[0, round(yc_stack, 4), 0],
                 size_mm=[D_PTFE_OUT, h_cell, D_PTFE_OUT], inside=0)]
    def layer(mat, y_bottom, h):
        vols.append(dict(material=mat, shape="cylinder", center_mm=[0, round(y_bottom + h / 2, 4), 0],
                         size_mm=[D_STACK, round(h, 4), D_STACK], inside=1))
    layer("stainless steel", y0 - T_SS, T_SS)
    layer("lithium", y0, T_LI)
    layer("separator", -T_SEP, T_SEP)
    first = len(vols)
    dz = T_GR / N_SLICES
    for k in range(N_SLICES):
        layer("graphite x=0.00", k * dz, dz)
    layer("stainless steel", T_GR, T_SS)
    slices = list(range(first, first + N_SLICES))
    states = {}
    for t in TIMES:
        xs = np.round(lithium(float(t)) / QUANT) * QUANT
        states[float(t)] = [f"graphite x={x:.2f}" for x in xs]
        for x in xs:
            mats.setdefault(f"graphite x={x:.2f}", electrode(float(x)))
    mats.setdefault("graphite x=0.00", electrode(0.0))
    spec = {
        "name": "Li half-cell with a 400 µm graphite electrode (Strobl et al. 2025), operando",
        "description": (
            "A cylindrical lithium half-cell seen edge-on: the electrodes are horizontal disks 16 mm in diameter, the "
            "beam crosses them along a diameter. From the bottom: a steel current collector, metallic lithium "
            "(0.75 mm), a glass-fiber separator (0.26 mm), the graphite electrode (0.40 mm), a steel collector; all in "
            "an aluminium casing (inner diameter 18 mm) lined with PTFE (1 mm), filled with a liquid electrolyte "
            "(LiPF6 in carbonates). y = 0: the interface between the separator and the graphite. A cycler charges it "
            "at C/35: lithium moves from the lithium metal into the graphite (lithiation, 30 h), then back "
            "(delithiation, about 20 h), then the cell rests."),
        "formula": "graphite (LixC6) | glass fiber + LiPF6 in EC/DMC | Li; Al, PTFE, steel",
        "hybrid_only": True,
        "hidden": ["materials"],
        "reference": ("M. Strobl, M. E. Baur, ..., L. Theil Kuhn, I. Gavish Segev, Y. Ein-Eli, Adv. Energy Mater. (2025), "
                      "SENJU (J-PARC); M.-E. Lăcătuşu, L. Theil Kuhn et al., arXiv:2104.03564 (2021). Generated by "
                      "odin/samples/gen_battery.py (what is taken from the papers, what is assumed: see that file)."),
        "operando": {"device": "cycle_time", "unit": "h", "slices": slices,
                     "states": {t: m for t, m in states.items()}},
        "materials": mats,
        "volumes": vols,
    }
    with open(os.path.join(HERE, "battery_graphite.yml"), "w", encoding="utf-8") as f:
        f.write("# Generated by gen_battery.py (do not edit by hand).\n")
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True, width=120)
    print(len(vols), "volumes,", len(mats), "materials,", len(states), "states")
    for t in (0, 2, 5, 10, 20, 30, 40, 50, 55):
        print(f"t = {t:4.1f} h  x: {np.round(lithium(t)[[0, 5, 10, 15, 19]], 2)}  mean {lithium(t).mean():.2f}")


if __name__ == "__main__":
    main()
