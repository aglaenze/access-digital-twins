"""Explanatory figures of the introductions to the instruments (twin/figures/), embedded in ODIN_intro and LoKI_intro
by their generators (odin/gen_intro_page.py, loki/gen_intro_page.py).

    python gen_intro_figures.py

odin_beamline.png   ODIN from the source to the camera: moderator, choppers, guide, pinhole, sample, detector
                    (distances of the official McStas model and of the ODIN NeXus file).
odin_beamline_line.png  ODIN on one line, for the class page (white beam, camera 6 mm behind the sample).
contrast_xray_neutron.png  Attenuation coefficients of a few materials, X-rays (100 keV) and neutrons (1.8 Å).
odin_detector_6mm.png  odin_detector.png with the camera 6 mm behind the sample (class page).
odin_tof.png        Time of flight: distance against time for neutrons of several wavelengths leaving in one ESS
                    pulse; the arrival time at the detector gives the wavelength; the next pulse and frame overlap.
odin_pinhole.png    The pinhole camera: collimation ratio L/D and the blur l·D/L of a point of the sample.
loki_beamline.png   LoKI from the source to the detectors: choppers, collimation, sample, the three groups of banks.
loki_q.png          The scattering angle 2θ, the scattering vector Q = 4π sin θ / λ and the sizes it corresponds to.
loki_tof.png        Time of flight on LoKI: the band 3-11.5 Å fits between two pulses with the rear bank at 5 m,
                    not at 10 m.
odin_choppers.png   The band choppers (one pulse in two) and the blur of the long pulse.
odin_detector.png   Side view of the detection: scintillator (lithium-6), mirror at 45°, camera out of the beam.
odin_scintillator.png  Thick and thin screens (light spread), and the detection efficiency ε(λ) of the twin.
odin_cameras.png    The two cameras: events (x, y, t) sorted into pictures per wavelength, or one summed picture.

All numbers are computed here from the constants below (the same as odin/odin_mcstas.py and loki/loki_mcstas.py).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
INK, TEAL, ORANGE, GREY, RED, BLUE = "#142033", "#0E7C70", "#C7711A", "#8A94A6", "#B4562B", "#2F5FB3"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#5B6779",
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

H_OVER_M = 3956.034        # m·Å/s: λ[Å] = 3956 / v[m/s]
PERIOD = 1 / 14            # s between two ESS pulses
TAU = 2.86e-3              # s, length of an ESS pulse
# ODIN (odin_mcstas.py; chopper positions: the ODIN NeXus file, distances from the moderator)
ODIN_PINHOLE, ODIN_SAMPLE, ODIN_DET = 50.0, 60.5, 60.55
ODIN_SAMPLE_2 = 64.0       # second measuring position of the real ODIN (L = 14 m, 20 cm x 20 cm field)
ODIN_GUIDE_END = 49.01
ODIN_WFM = (6.85, 7.15)    # the two WFM discs, δ = 0.30 m apart around 7 m
ODIN_CHOPPERS = (8.4, 12.2, 13.6, 17.0, 23.69, 33.0)     # frame-overlap, band-pass and T0 choppers
# Every chopper of the official model (ODIN_instr: guide.py for the positions, choppers.py for the speeds):
# (name, distance from the moderator [m], turns per second, family)
ODIN_CHOPPER_LIST = (("WFM 1–2", 7.0, 56, "wfm"), ("FO 1", 8.392, 42, "fo"), ("BP 1", 8.442, 7, "bp"),
                     ("FO 2", 12.2, 42, "fo"), ("BP 2", 12.25, 7, "bp"), ("T0", 13.603, 28, "t0"),
                     ("FO 3", 16.987, 28, "fo"), ("FO 4", 23.686, 14, "fo"), ("FO 5", 33.005, 14, "fo"))
# LoKI (loki_mcstas.py, virtual_loki.py)
LOKI_SAMPLE = 23.52
LOKI_CHOPPERS = (6.5, 15.21)
LOKI_BANKS = (("front banks", 1.5, 0.75), ("middle banks", 3.1, 0.42), ("rear bank", 5.0, 0.8))   # distance, half-size



def _save(fig, name):
    """The figure as PNG (dpi 150) and as SVG (vectors: what the pages show, sharp at every size; nbfig.figure_cell)."""
    fig.savefig(os.path.join(OUT, name), dpi=150)
    fig.savefig(os.path.join(OUT, os.path.splitext(name)[0] + ".svg"))

def _clean(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_yticks([])


CHOPPER_COLORS = {"wfm": TEAL, "fo": BLUE, "bp": "#7A3FB0", "t0": INK}


def odin_beamline():
    """Top: the whole beamline, with the two measuring positions. Bottom: the chopper section, every chopper named."""
    fig, (ax, az) = plt.subplots(2, 1, figsize=(13, 7.4), gridspec_kw=dict(height_ratios=[1.05, 1]))
    # ---- top: source to camera
    ax.plot([0, ODIN_GUIDE_END], [0, 0], color="#E8C9A0", lw=12, solid_capstyle="butt", zorder=1)
    ax.plot([ODIN_PINHOLE, ODIN_SAMPLE_2 + 0.6], [0, 0], color="#F3E2C6", lw=12, solid_capstyle="butt", zorder=1)
    ax.add_patch(Rectangle((-1.2, -0.55), 1.2, 1.1, color=RED, zorder=3))
    ax.text(-0.6, 1.02, "source\n(moderator)", ha="center", va="bottom", fontsize=10.5, color=INK)
    for _, z, _, fam in ODIN_CHOPPER_LIST:
        ax.add_patch(Rectangle((z - 0.12, -0.55), 0.24, 1.1, color=CHOPPER_COLORS[fam], zorder=3))
    ax.annotate("", (34, 0.95), (6.5, 0.95), arrowprops=dict(arrowstyle="-", color=INK, lw=1))
    ax.text(20.2, 1.02, "choppers, 7 to 33 m (enlarged below)", ha="center", va="bottom", fontsize=10.5, color=INK)
    ax.text(30, -0.62, "neutron guide: mirrors that carry the beam", ha="center", va="top", fontsize=10.5, color=ORANGE)
    ax.add_patch(Rectangle((ODIN_PINHOLE - 0.12, -0.9), 0.24, 0.72, color=INK, zorder=3))
    ax.add_patch(Rectangle((ODIN_PINHOLE - 0.12, 0.18), 0.24, 0.72, color=INK, zorder=3))
    ax.text(ODIN_PINHOLE - 1, 1.02, "pinhole\n(50 m)", ha="center", va="bottom", fontsize=10.5, color=INK)
    for k, (zs, txt, xt) in enumerate(((ODIN_SAMPLE, "position 1: 60.5 m\nfield 10 × 10 cm²", 57.5),
                                       (ODIN_SAMPLE_2, "position 2: 64 m\nfield 20 × 20 cm²", 69.0))):
        ax.add_patch(Rectangle((zs - 0.35, -0.4), 0.3, 0.8, color=GREY, ec=INK, zorder=3))
        ax.add_patch(Rectangle((zs + 0.1, -0.7), 0.25, 1.4, color=TEAL, zorder=3))
        ax.annotate(txt, (zs, 0.75), (xt, 1.35), ha="center", va="bottom", fontsize=10, color=TEAL,
                    arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=1.1, shrinkA=2, shrinkB=2))
    for zs, L, y in ((ODIN_SAMPLE, 10.5, -1.2), (ODIN_SAMPLE_2, 14.0, -1.9)):
        ax.annotate("", (zs - 0.2, y), (ODIN_PINHOLE, y), arrowprops=dict(arrowstyle="<->", color=INK))
        ax.text(ODIN_PINHOLE - 0.5, y, f"L = {L:g} m", ha="right", va="center", fontsize=10.5, color=INK)
    ax.text(66, -0.95, "at each position: the sample\n(gray), the camera (teal)\njust behind it", ha="left",
            va="center", fontsize=9.5, color=INK)
    ax.set_xlim(-3, 75); ax.set_ylim(-2.4, 2.6)
    ax.set_xlabel("distance from the source (m)")
    _clean(ax)
    # ---- bottom: the chopper section. Choppers 5 cm apart (FO 1 and BP 1, FO 2 and BP 2) drawn side by side.
    az.plot([5.3, 35], [0, 0], color="#E8C9A0", lw=10, solid_capstyle="butt", zorder=1)
    shift = {"FO 1": -0.17, "BP 1": 0.17, "FO 2": -0.17, "BP 2": 0.17}
    # label tier (y of the text) for each chopper, chosen so that no two labels overlap
    tier = {"WFM 1–2": 1.0, "FO 1": 2.35, "BP 1": -1.0, "FO 2": 1.0, "BP 2": -1.0, "T0": 2.35, "FO 3": 1.0,
            "FO 4": 1.0, "FO 5": 1.0}
    for name, z, nu, fam in ODIN_CHOPPER_LIST:
        c = CHOPPER_COLORS[fam]
        zz = z + shift.get(name, 0.0)
        if fam == "wfm":
            for zw in ODIN_WFM:
                az.add_patch(Rectangle((zw - 0.07, -0.6), 0.14, 1.2, color=c, zorder=3))
        else:
            w = 0.3 if fam == "t0" else 0.16                 # T0: a heavy 20 cm block
            az.add_patch(Rectangle((zz - w / 2, -0.6), w, 1.2, color=c, zorder=3))
        y = tier[name]
        va = "bottom" if y > 0 else "top"
        az.plot([zz, zz], [0.62 if y > 0 else -0.62, y - 0.08 if y > 0 else y + 0.08], color=c, lw=0.8)
        az.text(zz, y, f"{name}\n{z:.1f} m, {nu} Hz", ha="center", va=va, fontsize=9.5, color=c)
    legend = [("WFM: cut the long pulse into six short ones (WFM mode)", "wfm"),
              ("FO (frame overlap): keep the six short pulses apart (WFM mode)", "fo"),
              ("BP (band-pass): one pulse in two, 1 to 9 Å (natural and WFM modes)", "bp"),
              ("T0: closed at the proton impact: stops the flash of fast neutrons and γ (natural and WFM)", "t0")]
    for k, (txt, fam) in enumerate(legend):
        az.add_patch(Rectangle((18.2, -1.55 - 0.62 * k - 0.17), 0.45, 0.34, color=CHOPPER_COLORS[fam]))
        az.text(18.9, -1.55 - 0.62 * k, txt, ha="left", va="center", fontsize=9.5, color=INK)
    az.set_xlim(5, 36); az.set_ylim(-4.2, 3.6)
    az.set_xlabel("distance from the source (m)   (FO 1 / BP 1 and FO 2 / BP 2 are 5 cm apart: drawn side by side)")
    _clean(az)
    fig.tight_layout()
    _save(fig, "odin_beamline.png")
    plt.close(fig)


def odin_tof():
    """Distance against time: neutrons of several wavelengths leaving in one pulse; arrival at the camera."""
    L = ODIN_DET
    fig, ax = plt.subplots(figsize=(12, 5.2))
    lams = [(1.0, "#7A3FB0"), (2.0, BLUE), (4.0, TEAL), (6.0, ORANGE), (8.0, RED)]
    tmax = 150.0
    for k in range(3):                                        # three source pulses
        t0 = k * PERIOD * 1e3
        ax.add_patch(Rectangle((t0, -1.5), TAU * 1e3, 1.5, color=RED if k == 0 else "#D9A7A0", zorder=3))
        ax.text(t0 + 1.4, -3.9, f"pulse {k + 1}", ha="center", va="top", fontsize=10, color=INK)
    for lam, c in lams:                                        # pulse 1: one line per wavelength
        t = lam * L / H_OVER_M * 1e3                           # ms to reach the camera
        ax.plot([0, t], [0, L], color=c, lw=2)
        if t < tmax - 4:
            ax.plot(t, L, "o", color=c, ms=6, zorder=4)
            ax.text(t, L + 1.6, f"{lam:g} Å\n{t:.0f} ms", ha="center", va="bottom", fontsize=10, color=c)
    t2 = PERIOD * 1e3                                          # pulse 2: its fastest neutrons (1 Å), dashed
    ta = 1.0 * L / H_OVER_M * 1e3
    ax.plot([t2, t2 + ta], [0, L], color="#7A3FB0", lw=1.6, ls="--")
    ax.plot(t2 + ta, L, "o", color="#7A3FB0", ms=6, mfc="white", zorder=4)
    ax.annotate("the 1 Å neutrons of pulse 2\narrive before the 6 Å neutrons\nof pulse 1: frame overlap",
                (t2 + ta, L), (98, 22), fontsize=10, color="#7A3FB0", ha="left", va="center",
                arrowprops=dict(arrowstyle="->", color="#7A3FB0"))
    ax.axhline(L, color=INK, lw=1.2)
    ax.text(tmax - 1, L - 1.5, "camera, 60.55 m", ha="right", va="top", fontsize=10.5, color=INK)
    ax.annotate("", (PERIOD * 1e3, -8.5), (0, -8.5), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text(PERIOD * 1e3 / 2, -9.3, "71.4 ms between two pulses (14 per second)", ha="center", va="top", fontsize=10,
            color=INK)
    ax.set_xlim(-3, tmax); ax.set_ylim(-14, 74)
    ax.set_xlabel("time (ms)"); ax.set_ylabel("distance from the source (m)")
    ax.set_yticks([0, 20, 40, 60])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.text(98, 5, "slow neutrons = long wavelength\n= flatter line", fontsize=10.5, color=INK, va="center")
    fig.tight_layout()
    _save(fig, "odin_tof.png")
    plt.close(fig)


def odin_choppers():
    """Left: one pulse in two (band choppers), a band of 1-9 Å without overlap. Right: the long pulse blurs the
    wavelength; a short opening (WFM) sharpens it."""
    L = ODIN_DET
    fig = plt.figure(figsize=(13, 5.0))
    ax = fig.add_axes([0.06, 0.16, 0.5, 0.72])
    per = PERIOD * 1e3
    for k in range(3):
        kept = k != 1
        ax.add_patch(Rectangle((k * per, -1.5), TAU * 1e3, 1.5, color=RED if kept else "#D9DDE5"))
        ax.text(k * per + 1.4, -4.2, f"pulse {k + 1}" + ("" if kept else "\n(stopped)"), ha="center", va="top",
                fontsize=9.5, color=INK if kept else GREY)
    for k in (0, 2):                                           # the band 1-9 Å of the pulses kept
        t0 = k * per
        for lam, c in ((1.0, "#7A3FB0"), (9.0, RED)):
            t = t0 + lam * L / H_OVER_M * 1e3
            ax.plot([t0, t], [0, L], color=c, lw=2)
        ax.fill_between([t0 + 1.0 * L / H_OVER_M * 1e3, t0 + 9.0 * L / H_OVER_M * 1e3], L - 1.2, L + 1.2,
                        color=TEAL, alpha=0.35, lw=0)
    ax.plot([per, per + 1.0 * L / H_OVER_M * 1e3], [0, 8.4], color=GREY, lw=1.5, ls=":")
    ax.plot([0, 180], [8.4, 8.4], color=BLUE, lw=1, ls="--")
    ax.text(178, 9.5, "band chopper (7 turns/s)", ha="right", va="bottom", fontsize=9.5, color=BLUE)
    ax.axhline(L, color=INK, lw=1)
    ax.text(178, L + 2, "camera: 1 Å to 9 Å of pulse 1 arrive before those of pulse 3", ha="right", va="bottom",
            fontsize=9.5, color=TEAL)
    ax.set_xlim(-3, 180); ax.set_ylim(-11, 70)
    ax.set_xlabel("time (ms)"); ax.set_ylabel("distance from the source (m)")
    ax.set_title("Problem 1: one pulse in two, so the pulses never mix", color=INK, fontsize=12, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax2 = fig.add_axes([0.64, 0.22, 0.34, 0.66])               # the long pulse: two 4 Å neutrons, zoom on the arrival
    t4 = 4.0 * L / H_OVER_M * 1e3
    for t0, ls, lab in ((0.0, "-", "left at the start of the pulse"), (TAU * 1e3, "--", "left at its end (2.86 ms later)")):
        ax2.plot([t0, t0 + t4], [0, L], color=TEAL, lw=2.2, ls=ls, label=lab)
    ax2.axhline(L, color=INK, lw=1)
    ax2.text(t4 - 4.6, L + 0.5, "camera", ha="left", va="bottom", fontsize=9.5, color=INK)
    ax2.annotate("", (t4 + TAU * 1e3, L - 4), (t4, L - 4), arrowprops=dict(arrowstyle="<->", color=RED))
    ax2.text(t4 + 1.43, L - 5, "2.86 ms", ha="center", va="top", fontsize=10, color=RED)
    ax2.text(t4 + 4.2, L - 1.2, "read as\n4.19 Å", ha="left", va="top", fontsize=10, color=RED)
    ax2.text(t4 - 4.6, L - 1.2, "read as\n4.00 Å", ha="left", va="top", fontsize=10, color=TEAL)
    ax2.set_xlim(t4 - 5, t4 + 7.5); ax2.set_ylim(L - 14, L + 3)
    ax2.set_xlabel("time (ms), zoom on the arrival at the camera"); ax2.set_ylabel("distance (m)")
    ax2.legend(loc="lower right", fontsize=9, frameon=False, title="two neutrons of 4 Å", title_fontsize=9.5)
    ax2.set_title("Problem 2: the long pulse blurs λ", color=INK, fontsize=12, fontweight="bold")
    for s_ in ("top", "right"):
        ax2.spines[s_].set_visible(False)
    fig.text(0.64, 0.015, "WFM choppers: six short openings instead of one long pulse,\nso λ is known to 0.2 to 0.8 %",
             fontsize=9.5, color=TEAL, va="bottom")
    _save(fig, "odin_choppers.png")
    plt.close(fig)


def odin_pinhole():
    fig, ax = plt.subplots(figsize=(12, 3.9))
    D, zs, zd = 1.8, 6.5, 10.5                                # drawing units (not to scale: the blur is exaggerated)
    ax.add_patch(Rectangle((-0.12, D / 2), 0.24, 0.8, color=INK)); ax.add_patch(Rectangle((-0.12, -D / 2 - 0.8), 0.24, 0.8, color=INK))
    ax.annotate("", (-0.5, D / 2), (-0.5, -D / 2), arrowprops=dict(arrowstyle="<->", color=RED))
    ax.text(-0.7, 0, "D", color=RED, fontsize=13, ha="right", va="center", fontweight="bold")
    ax.text(0, 2.05, "pinhole", ha="center", fontsize=10.5, color=INK)
    y = 0.0                                                    # a point of the sample
    for y0 in (D / 2, -D / 2):                                 # rays from the two edges of the pinhole through the point
        slope = (y - y0) / zs
        ax.plot([0, zd], [y0, y0 + slope * zd], color=ORANGE, lw=1.4)
    ax.add_patch(Rectangle((zs - 0.08, -1.4), 0.16, 2.8, color=GREY, alpha=0.55))
    ax.plot(zs, y, "o", color=INK, ms=6, zorder=4)
    ax.text(zs, 2.05, "sample", ha="center", fontsize=10.5, color=INK)
    ax.text(zs - 0.3, y + 0.75, "one point\nof the sample", ha="right", va="bottom", fontsize=10, color=INK)
    ax.text(5.25, -3.0, "(not to scale: the blur is exaggerated)", ha="center", va="top", fontsize=9.5, color=GREY)
    ax.plot([zd, zd], [-1.7, 1.7], color=TEAL, lw=5)
    ax.text(zd, 2.05, "camera", ha="center", fontsize=10.5, color=TEAL)
    ya = D / 2 + (y - D / 2) / zs * zd
    yb = -D / 2 + (y + D / 2) / zs * zd
    ax.annotate("", (zd + 0.35, max(ya, yb)), (zd + 0.35, min(ya, yb)), arrowprops=dict(arrowstyle="<->", color=RED))
    ax.text(zd + 0.5, (ya + yb) / 2, "blur\n= l × D / L", color=RED, fontsize=11, ha="left", va="center")
    ax.annotate("", (zs, -2.25), (0, -2.25), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text(zs / 2, -2.35, "L = 10.5 m (pinhole to sample)", ha="center", va="top", fontsize=10.5, color=INK)
    ax.annotate("", (zd, -2.25), (zs, -2.25), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text((zs + zd) / 2, -2.35, "l", ha="center", va="top", fontsize=11, color=INK)
    ax.set_xlim(-1.6, 13.2); ax.set_ylim(-3.6, 2.6); ax.axis("off")
    fig.tight_layout()
    _save(fig, "odin_pinhole.png")
    plt.close(fig)


def odin_beamline_line():
    """ODIN on one line, for the class page: source, choppers (all open in white beam), guide, pinhole, the sample and\n    the camera 6 mm behind it (position 1)."""
    fig, ax = plt.subplots(figsize=(13, 3.3))
    ax.plot([0, ODIN_GUIDE_END], [0, 0], color="#E8C9A0", lw=12, solid_capstyle="butt", zorder=1)
    ax.plot([ODIN_PINHOLE, ODIN_SAMPLE + 0.4], [0, 0], color="#F3E2C6", lw=12, solid_capstyle="butt", zorder=1)
    ax.add_patch(Rectangle((-1.2, -0.55), 1.2, 1.1, color=RED, zorder=3))
    ax.text(-0.6, 0.75, "source\n(moderator)\n0 m", ha="center", va="bottom", fontsize=10.5, color=INK)
    for _, z, _, fam in ODIN_CHOPPER_LIST:
        ax.add_patch(Rectangle((z - 0.12, -0.55), 0.24, 1.1, color=BLUE, zorder=3))
    ax.annotate("", (34, 0.75), (6.5, 0.75), arrowprops=dict(arrowstyle="-", color=BLUE, lw=1))
    ax.text(20.2, 0.85, "choppers, 7 to 33 m: they select wavelengths\n(today all open: the white beam)", ha="center",
            va="bottom", fontsize=10.5, color=BLUE)
    ax.text(25, -0.62, "neutron guide (0 to 49 m): mirrors that carry the beam", ha="center", va="top", fontsize=10.5,
            color=ORANGE)
    ax.add_patch(Rectangle((ODIN_PINHOLE - 0.15, -0.95), 0.3, 0.75, color=INK, zorder=3))
    ax.add_patch(Rectangle((ODIN_PINHOLE - 0.15, 0.2), 0.3, 0.75, color=INK, zorder=3))
    ax.text(ODIN_PINHOLE, 1.05, "pinhole D\n50 m", ha="center", va="bottom", fontsize=10.5, color=INK)
    ax.add_patch(Rectangle((ODIN_SAMPLE - 0.45, -0.35), 0.35, 0.7, color=GREY, ec=INK, zorder=3))
    ax.add_patch(Rectangle((ODIN_SAMPLE + 0.05, -0.7), 0.25, 1.4, color=TEAL, zorder=3))
    ax.text(ODIN_SAMPLE + 0.9, 0.0, "sample (60.5 m)\nand the camera,\n6 mm behind it", ha="left", va="center",
            fontsize=10.5, color=TEAL)
    ax.annotate("", (ODIN_SAMPLE - 0.3, -1.25), (ODIN_PINHOLE, -1.25), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text((ODIN_PINHOLE + ODIN_SAMPLE) / 2, -1.35, "L = 10.5 m", ha="center", va="top", fontsize=10.5, color=INK)
    ax.set_xlim(-3, 70); ax.set_ylim(-1.9, 1.9)
    ax.set_xlabel("distance from the source (m)")
    _clean(ax)
    fig.tight_layout()
    _save(fig, "odin_beamline_line.png")
    plt.close(fig)


# Attenuation coefficients for the contrast figure. Neutrons: NCrystal at 1.8 Å (water: LiquidWaterH2O_T293.6K, metals:
# their ncmat crystals), absorption + scattering. X-rays: 100 keV, NIST XCOM mass attenuation coefficients (with
# coherent scattering) times the density.
CONTRAST = (("water (H₂O)", 0.171, 3.62), ("aluminum", 0.460, 0.101), ("silicon", 0.428, 0.111),
            ("iron", 2.93, 1.20), ("copper", 4.11, 0.93), ("lead", 63.0, 0.354))


def contrast_xray_neutron():
    """The attenuation coefficient of a few materials for X-rays (100 keV) and neutrons (1.8 Å): bars on a log scale,\n    and what 1 cm of each lets through."""
    fig, ax = plt.subplots(figsize=(12, 4.2))
    y = np.arange(len(CONTRAST))[::-1]
    for k, (name, mx, mn) in enumerate(CONTRAST):
        ax.barh(y[k] + 0.19, mx, height=0.36, color=GREY, left=0.0)
        ax.barh(y[k] - 0.19, mn, height=0.36, color=TEAL)
        ax.text(mx * 1.12, y[k] + 0.19, f"{mx:g} cm⁻¹: 1 cm lets {100 * np.exp(-mx):.0f} % through"
                if np.exp(-mx) > 0.005 else f"{mx:g} cm⁻¹: 1 cm stops everything", va="center", fontsize=9.5,
                color="#5B6779")
        ax.text(mn * 1.12, y[k] - 0.19, f"{mn:g} cm⁻¹: 1 cm lets {100 * np.exp(-mn):.0f} % through", va="center",
                fontsize=9.5, color=TEAL)
    ax.set_xscale("log"); ax.set_xlim(0.05, 400)
    ax.set_xticks([0.1, 1, 10, 100]); ax.set_xticklabels(["0.1", "1", "10", "100"])
    ax.set_yticks(y); ax.set_yticklabels([c[0] for c in CONTRAST], fontsize=11)
    ax.set_xlabel("attenuation coefficient Σ (cm⁻¹, log scale)")
    from matplotlib.patches import Patch
    ax.legend([Patch(color=GREY), Patch(color=TEAL)],
              ["X-rays, 100 keV: grows with the number of electrons (heavy elements)",
               "neutrons, 1.8 Å: hydrogen first; the metals let most of them through"],
              loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=10, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    _save(fig, "contrast_xray_neutron.png")
    plt.close(fig)


def odin_detector(gap="5 cm", name="odin_detector.png"):
    """Side view of the detection: the neutron is absorbed in the scintillator (lithium-6), which glows; a mirror at\n    45° sends the light up to the camera, out of the beam; the neutrons go on through the mirror."""
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.plot([-0.4, 1.0], [0, 0], color=TEAL, lw=6, solid_capstyle="butt")
    ax.text(0.25, 0.22, "neutrons", ha="center", va="bottom", fontsize=10.5, color=TEAL)
    ax.add_patch(Rectangle((1.0, -0.45), 0.35, 0.9, color=GREY, ec=INK))
    ax.text(1.175, -0.6, "sample", ha="center", va="top", fontsize=10.5, color=INK)
    ax.plot([1.35, 2.5], [0, 0], color=TEAL, lw=4, solid_capstyle="butt", alpha=0.8)
    ax.add_patch(Rectangle((2.5, -0.8), 0.1, 1.6, color="#7BC8A4", ec=TEAL))     # the scintillator screen
    ax.text(2.55, 0.95, "scintillator\n(lithium-6)", ha="center", va="bottom", fontsize=10.5, color=TEAL)
    ax.annotate("", (2.5, -1.05), (1.35, -1.05), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text(1.92, -1.13, gap, ha="center", va="top", fontsize=10, color=INK)
    ax.plot(2.55, 0.12, "*", color="#F2B544", ms=17, mec=ORANGE, zorder=5)       # one flash
    for dy in (-0.25, 0.0, 0.25):                                                # its light toward the mirror
        ax.annotate("", (4.0 - 0.05, dy * 0.6), (2.62, 0.12 + dy * 0.2),
                    arrowprops=dict(arrowstyle="-|>", color="#E0A030", lw=1.3))
    ax.plot([3.6, 4.4], [-0.6, 0.6], color=INK, lw=3)                             # mirror at 45°
    ax.text(4.55, -0.55, "mirror at 45°\n(neutrons go\nthrough it)", ha="left", va="top", fontsize=10, color=INK)
    ax.annotate("", (4.0, 1.75), (4.0, 0.05), arrowprops=dict(arrowstyle="-|>", color="#E0A030", lw=2))
    ax.add_patch(Rectangle((3.75, 1.75), 0.5, 0.18, color=BLUE))                  # lens
    ax.add_patch(Rectangle((3.6, 1.95), 0.8, 0.45, color=INK))                    # camera body
    ax.text(4.5, 2.15, "camera, out of the beam: films the screen", ha="left", va="center", fontsize=10.5, color=INK)
    ax.plot([2.6, 6.2], [0, 0], color=TEAL, lw=3, alpha=0.5, ls="--", zorder=0)   # the neutrons not absorbed
    ax.add_patch(Rectangle((6.2, -0.5), 0.3, 1.0, color="#5B6779"))
    ax.text(6.35, -0.62, "beam stop", ha="center", va="top", fontsize=10, color=INK)
    ax.text(2.75, 0.32, "1", fontsize=12, fontweight="bold", color=ORANGE)
    ax.text(3.2, -0.42, "2", fontsize=12, fontweight="bold", color=ORANGE)
    ax.text(4.12, 1.0, "3", fontsize=12, fontweight="bold", color=ORANGE)
    steps = ("1  The neutron is absorbed by a lithium-6 nucleus of the screen:\n"
             "    n + ⁶Li → ³H + ⁴He. The two fast particles make the screen glow:\n"
             "    a flash of light, at the place where the neutron arrived.\n"
             "2  The light of the flash leaves the screen…\n"
             "3  …and the mirror sends it up to the camera. The camera stays out of\n"
             "    the beam, where the neutrons cannot damage it.")
    ax.text(7.0, 1.7, steps, ha="left", va="top", fontsize=10.5, color=INK, linespacing=1.45)
    ax.set_xlim(-0.5, 12.4); ax.set_ylim(-1.5, 2.6); ax.axis("off")
    fig.tight_layout()
    _save(fig, name)
    plt.close(fig)


def odin_scintillator():
    """Left: a thick and a thin screen; the light of a flash spreads on its way out of the screen. Right: the share of
    the neutrons detected in the twin, ε(λ) = 1 − exp(−λ / 8 Å)."""
    fig = plt.figure(figsize=(13, 4.4))
    rng = np.random.default_rng(3)
    for k, (x0, thick, title, note) in enumerate((
            (0.04, 0.6, "Thick screen", "more neutrons stopped (bright)\nlight spreads: blur 0.1 mm"),
            (0.27, 0.15, "Thin screen", "fewer neutrons stopped\nlittle spread: blur 0.02 mm"))):
        ax = fig.add_axes([x0, 0.12, 0.2, 0.74])
        ax.add_patch(Rectangle((0, -1.6), thick, 3.2, color="#BFE5D1", ec=TEAL))
        for y in np.linspace(-1.1, 1.1, 5):
            depth = rng.uniform(0.15, 0.85) * thick
            ax.annotate("", (depth, y), (-0.9, y), arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=1.2))
            ax.plot(depth, y, "*", color="#F2B544", mec=ORANGE, ms=11, zorder=5)
            spread = (thick - depth) * 0.45 + 0.03            # half-width of the light spot at the exit face
            ax.fill([depth, thick, thick], [y, y - spread, y + spread], color="#F2B544", alpha=0.45, lw=0)
            ax.plot([thick, thick], [y - spread, y + spread], color=ORANGE, lw=3)
        ax.text(thick + 0.08, 1.75, "light spot\nseen by the camera", ha="left", va="bottom", fontsize=9, color=ORANGE)
        ax.set_title(title, fontsize=12, fontweight="bold", color=INK)
        ax.text(0.0, -1.85, note, ha="left", va="top", fontsize=9.5, color=INK)
        ax.set_xlim(-1.0, 1.6); ax.set_ylim(-2.7, 2.5); ax.axis("off")
    ax = fig.add_axes([0.6, 0.17, 0.37, 0.7])
    lam = np.linspace(0.5, 12, 200)
    ax.plot(lam, 100 * (1 - np.exp(-lam / 8)), color=TEAL, lw=2.2)
    for l in (2, 4, 8):
        e = 100 * (1 - np.exp(-l / 8))
        ax.plot(l, e, "o", color=ORANGE, ms=7, zorder=4)
        ax.text(l + 0.25, e - 2, f"{l} Å: {e:.0f} %", ha="left", va="top", fontsize=10, color=ORANGE)
    ax.set_xlabel("wavelength λ (Å)"); ax.set_ylabel("neutrons detected (%)")
    ax.set_ylim(0, 85); ax.set_xlim(0, 12)
    ax.set_title("Slow neutrons are caught more easily", fontsize=12, fontweight="bold", color=INK)
    ax.text(11.8, 6, "ε(λ) = 1 − exp(−λ / 8 Å)\n(the twin)", ha="right", va="bottom", fontsize=10, color=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    _save(fig, "odin_scintillator.png")
    plt.close(fig)


def odin_cameras():
    """The same neutrons through an iron disc seen by the two cameras: the Timepix3 camera notes each neutron (x, y, t),
    so the time gives λ and the neutrons can be sorted into pictures per wavelength (the iron lets more through above
    its Bragg edge at 4.05 Å); the integrating camera adds up the light: one picture, all wavelengths mixed."""
    fig = plt.figure(figsize=(13, 4.8))
    rng = np.random.default_rng(7)
    n = 64
    yy, xx = np.mgrid[:n, :n]
    disc = (xx - n / 2) ** 2 + (yy - n / 2) ** 2 < (n * 0.3) ** 2

    def picture(trans, counts):
        img = np.where(disc, trans, 1.0)
        return rng.poisson(img * counts) / counts

    fig.text(0.02, 0.93, "Timepix3 camera (event mode): one line per neutron", fontsize=12, fontweight="bold", color=INK)
    rows = [("x (mm)", "y (mm)", "t (ms)", "→ λ (Å)")]
    for x, y, t in ((3.21, 9.80, 45.9), (7.04, 6.62, 68.9), (11.56, 2.37, 91.8), (5.48, 12.90, 52.1)):
        rows.append((f"{x:.2f}", f"{y:.2f}", f"{t:.1f}", f"{H_OVER_M * t * 1e-3 / ODIN_DET:.2f}"))
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            fig.text(0.03 + j * 0.06, 0.8 - i * 0.065, c, fontsize=10.5, color=ORANGE if j == 3 else INK,
                     fontweight="bold" if i == 0 else "normal", family="DejaVu Sans Mono")
    fig.text(0.03, 0.8 - len(rows) * 0.065, "… millions of lines", fontsize=10, color=GREY)
    fig.text(0.03, 0.27, "λ = 3956 × t / 60.55 m: the time gives\nthe wavelength (part 4), so the neutrons\n"
             "can be sorted into pictures per wavelength →", fontsize=10.5, color=INK, va="top")
    for k, (lam, tr) in enumerate(((3.0, 0.45), (4.5, 0.75), (6.0, 0.78))):
        ax = fig.add_axes([0.30 + k * 0.125, 0.2, 0.115, 0.55])
        ax.imshow(picture(tr, 150), cmap="gray", vmin=0.2, vmax=1.2)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{lam:g} Å", fontsize=11, color=ORANGE)
    fig.text(0.30, 0.1, "an iron disc: it lets more neutrons through above 4.05 Å\n(its Bragg edge): seen only "
             "in the pictures per wavelength", fontsize=10, color=INK)
    fig.add_artist(plt.Line2D([0.705, 0.705], [0.05, 0.95], color="#D9DDE5", lw=1.5))
    fig.text(0.725, 0.93, "Integrating camera", fontsize=12, fontweight="bold", color=INK)
    ax = fig.add_axes([0.74, 0.2, 0.18, 0.6])
    ax.imshow(picture(0.62, 450), cmap="gray", vmin=0.2, vmax=1.2)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("all wavelengths added", fontsize=11, color=INK)
    fig.text(0.725, 0.1, "no time, no λ: one picture, smoother\n(all the neutrons in it), but no Bragg edge",
             fontsize=10, color=INK)
    _save(fig, "odin_cameras.png")
    plt.close(fig)


def loki_beamline():
    fig = plt.figure(figsize=(13, 4.0))
    ax = fig.add_axes([0.04, 0.2, 0.52, 0.72])                 # source -> sample
    L = LOKI_SAMPLE
    ax.plot([0, L - 8], [0, 0], color="#E8C9A0", lw=12, solid_capstyle="butt")
    ax.add_patch(Rectangle((-0.9, -0.55), 0.9, 1.1, color=RED))
    ax.text(-0.45, 1.0, "source", ha="center", va="bottom", fontsize=10.5, color=INK)
    for z in LOKI_CHOPPERS:
        for dz in (-0.14, 0.14):
            ax.add_patch(Rectangle((z + dz - 0.07, -0.55), 0.14, 1.1, color=BLUE))
    ax.text(LOKI_CHOPPERS[0], 1.0, "choppers\n(6.5 m)", ha="center", va="bottom", fontsize=10.5, color=BLUE)
    ax.text(LOKI_CHOPPERS[1], 1.0, "choppers\n(15.2 m)", ha="center", va="bottom", fontsize=10.5, color=BLUE)
    ax.text(10.8, -0.62, "guide", ha="center", va="top", fontsize=10.5, color=ORANGE)
    for z, name in ((L - 8, "8 m"), (L - 5, "5 m"), (L - 3, "3 m")):       # source aperture positions
        ax.add_patch(Rectangle((z - 0.07, 0.2), 0.14, 0.55, color=INK)); ax.add_patch(Rectangle((z - 0.07, -0.75), 0.14, 0.55, color=INK))
        ax.text(z, -0.88, name, ha="center", va="top", fontsize=9.5, color=INK)
    ax.text(L - 5.3, -1.38, "collimation: an aperture 3, 5 or 8 m before the sample", ha="center", va="top", fontsize=10,
            color=INK)
    ax.plot([L - 8, L], [0, 0], color=TEAL, lw=3)
    ax.add_patch(Rectangle((L - 0.07, 0.1), 0.14, 0.45, color=INK)); ax.add_patch(Rectangle((L - 0.07, -0.55), 0.14, 0.45, color=INK))
    ax.add_patch(Rectangle((L + 0.15, -0.35), 0.3, 0.7, color=GREY, ec=INK))
    ax.text(L + 0.2, 1.0, "sample\n(23.5 m)", ha="center", va="bottom", fontsize=10.5, color=INK)
    ax.set_xlim(-2, L + 1.6); ax.set_ylim(-2.0, 2.1)
    ax.set_xlabel("distance from the source (m)")
    _clean(ax)
    ax2 = fig.add_axes([0.62, 0.2, 0.36, 0.72])                # sample -> detectors
    ax2.add_patch(Rectangle((-0.12, -0.12), 0.24, 0.24, color=GREY, ec=INK))
    ax2.text(0, -0.2, "sample", ha="center", va="top", fontsize=10, color=INK)
    cols = (BLUE, ORANGE, TEAL)
    for (name, z, half), c in zip(LOKI_BANKS, cols):
        inner = {"front banks": 0.36, "middle banks": 0.2, "rear bank": 0.035}[name]
        for sgn in (1, -1):
            ax2.plot([z, z], [sgn * inner, sgn * half], color=c, lw=5, solid_capstyle="butt")
            ax2.plot([0, z], [0, sgn * (inner + half) / 2], color=c, lw=0.9, ls="--")
        ax2.text(z, half + 0.07, f"{name}\n{'1 to 2' if name.startswith('front') else '3' if name.startswith('mid') else '5 or 10'} m",
                 ha="center", va="bottom", fontsize=10, color=c)
    ax2.plot([0, 5.0], [0, 0], color=TEAL, lw=1.2)
    ax2.add_patch(Rectangle((4.9, -0.035), 0.08, 0.07, color="k"))
    ax2.text(5.12, 0, "beam\nstop", ha="left", va="center", fontsize=9.5, color=INK)
    ax2.set_xlim(-0.4, 5.9); ax2.set_ylim(-1.0, 1.3)
    ax2.set_xlabel("distance from the sample (m)")
    _clean(ax2)
    _save(fig, "loki_beamline.png")
    plt.close(fig)


def loki_q():
    fig = plt.figure(figsize=(13, 4.2))
    ax = fig.add_axes([0.02, 0.06, 0.5, 0.86])
    ax.plot([0, 3.0], [0, 0], color=TEAL, lw=4, solid_capstyle="butt")
    ax.add_patch(Rectangle((3.0, -0.45), 0.3, 0.9, color=GREY, ec=INK))
    ax.plot([3.15, 9.4], [0, 0], color=TEAL, lw=1.2, ls=":")
    ang = 0.2
    ax.plot([3.15, 9.4], [0, (9.4 - 3.15) * np.tan(ang)], color=ORANGE, lw=2)
    ax.plot([9.5, 9.5], [-1.6, 1.9], color=INK, lw=4)
    th = np.linspace(0, ang, 30)
    ax.plot(3.15 + 2.2 * np.cos(th), 2.2 * np.sin(th), color=INK, lw=1)
    ax.text(5.55, 0.2, "2θ", fontsize=12, color=INK)
    r = (9.4 - 3.15) * np.tan(ang)
    ax.annotate("", (9.85, r), (9.85, 0), arrowprops=dict(arrowstyle="<->", color=RED))
    ax.text(10.0, r / 2, "r", color=RED, fontsize=13, va="center", fontweight="bold")
    ax.annotate("", (9.4, -1.95), (3.15, -1.95), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text(6.3, -2.05, "distance sample to detector", ha="center", va="top", fontsize=10.5, color=INK)
    ax.text(1.5, 0.28, "neutrons, wavelength λ", ha="center", fontsize=10.5, color=TEAL)
    ax.text(3.15, -0.62, "sample", ha="center", va="top", fontsize=10.5, color=INK)
    ax.text(9.5, 2.05, "detector", ha="center", fontsize=10.5, color=INK)
    ax.text(6.9, 1.35, "scattered\nneutron", ha="right", fontsize=10.5, color=ORANGE)
    ax.set_xlim(-0.3, 10.6); ax.set_ylim(-2.7, 2.5); ax.axis("off")
    ax.set_title("The pixel gives the angle 2θ, the arrival time gives λ", color=INK, fontsize=12.5, fontweight="bold")
    ax2 = fig.add_axes([0.6, 0.2, 0.37, 0.66])
    q = np.logspace(-2.3, -0.2, 200)
    ax2.loglog(q, 2 * np.pi / q / 10, color=INK, lw=2)
    for d_nm, name, c in ((50, "50 nm", RED), (10, "10 nm", ORANGE), (2, "2 nm", TEAL)):
        qq = 2 * np.pi / (d_nm * 10)
        ax2.plot(qq, d_nm, "o", color=c, ms=8, zorder=4)
        left = qq > 0.2                                        # the last label on the left of its point
        ax2.text(qq / 1.18 if left else qq * 1.18, d_nm / 1.15 if left else d_nm * 1.12, f"{name}: Q = {qq:.3f} Å⁻¹",
                 color=c, fontsize=10, va="top" if left else "bottom", ha="right" if left else "left")
    ax2.set_xlabel("Q = 4π sin θ / λ  (Å⁻¹)"); ax2.set_ylabel("size d = 2π / Q  (nm)")
    ax2.set_title("Small Q = large objects", color=INK, fontsize=12.5, fontweight="bold")
    ax2.grid(alpha=0.3, which="both")
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    _save(fig, "loki_q.png")
    plt.close(fig)


def loki_tof():
    """Distance against time on LoKI: the band 3-11.5 Å of one pulse, to the rear bank at 5 m and at 10 m; the
    fastest neutrons of the next pulse."""
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
    per = PERIOD * 1e3
    for ax, det, band, title in ((axs[0], 5.0, (3.0, 11.5), "Rear bank at 5 m: the band fits"),
                                 (axs[1], 10.0, (3.0, 11.5), "Rear bank at 10 m: the same band would not fit")):
        L = LOKI_SAMPLE + det
        for k in range(2):
            ax.add_patch(Rectangle((k * per, -1.0), TAU * 1e3, 1.0, color=RED if k == 0 else "#D9A7A0"))
            ax.text(k * per + 1.4, -2.0, f"pulse {k + 1}", ha="center", va="top", fontsize=9.5, color=INK)
        times = []
        for lam, c in ((band[0], "#7A3FB0"), (band[1], RED)):
            t = lam * L / H_OVER_M * 1e3
            times.append(t)
            ax.plot([0, t], [0, L], color=c, lw=2)
            ax.text(t, L + 0.8, f"{lam:g} Å\n{t:.0f} ms", ha="center", va="bottom", fontsize=9.5, color=c)
        t2 = per + band[0] * L / H_OVER_M * 1e3
        ax.plot([per, t2], [0, L], color="#7A3FB0", lw=1.6, ls="--")
        ax.text(t2 + 1, L - 1.2, f"3 Å of pulse 2\n{t2:.0f} ms", ha="left", va="top", fontsize=9.5, color="#7A3FB0")
        ax.fill_between(times, L - 0.5, L + 0.5, color=TEAL, alpha=0.35, lw=0)
        ok = times[1] < t2
        ax.text(124, 3, f"pulse 1 arrives over {times[1] - times[0]:.0f} ms:\n"
                + ("all of it before pulse 2" if ok else f"its slowest neutrons arrive after\nthe fastest of pulse 2: they mix"),
                fontsize=10, color=TEAL if ok else RED, va="bottom", ha="right",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.9))
        ax.axhline(L, color=INK, lw=1)
        ax.set_xlim(-3, 125); ax.set_ylim(-5, 40)
        ax.set_xlabel("time (ms)")
        ax.set_title(title, color=INK, fontsize=12, fontweight="bold")
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
    axs[0].set_ylabel("distance from the source (m)")
    fig.tight_layout()
    _save(fig, "loki_tof.png")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for lam in (1, 2, 4, 6, 8):
        print(f"ODIN: {lam} Å reaches the camera ({ODIN_DET} m) after {lam * ODIN_DET / H_OVER_M * 1e3:.1f} ms")
    print(f"ODIN: band between two pulses {H_OVER_M * PERIOD / ODIN_DET:.2f} Å; with one pulse in two "
          f"{2 * H_OVER_M * PERIOD / ODIN_DET:.2f} Å; natural resolution {H_OVER_M * TAU / ODIN_DET:.3f} Å")
    odin_beamline(); odin_beamline_line(); contrast_xray_neutron(); odin_detector("6 mm (not to scale)", "odin_detector_6mm.png")
    odin_tof(); odin_choppers(); odin_pinhole(); odin_detector(); odin_scintillator(); odin_cameras()
    loki_beamline(); loki_q(); loki_tof()
    print("written", OUT)
