"""Explanatory figures of the introductions to the instruments (twin/figures/), embedded in ODIN_intro and LoKI_intro
by their generators (odin/gen_intro_page.py, loki/gen_intro_page.py).

    python gen_intro_figures.py

odin_beamline.png   ODIN from the source to the camera: moderator, choppers, guide, pinhole, sample, detector
                    (distances of the official McStas model and of the ODIN NeXus file).
odin_tof.png        Time of flight: distance against time for neutrons of several wavelengths leaving in one ESS
                    pulse; the arrival time at the detector gives the wavelength; the next pulse and frame overlap.
odin_pinhole.png    The pinhole camera: collimation ratio L/D and the blur l·D/L of a point of the sample.
loki_beamline.png   LoKI from the source to the detectors: choppers, collimation, sample, the three groups of banks.
loki_q.png          The scattering angle 2θ, the scattering vector Q = 4π sin θ / λ and the sizes it corresponds to.
loki_tof.png        Time of flight on LoKI: the band 3-11.5 Å fits between two pulses with the rear bank at 5 m,
                    not at 10 m.
odin_choppers.png   The band choppers (one pulse in two) and the blur of the long pulse.

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
ODIN_GUIDE_END = 49.01
ODIN_WFM = (6.775, 7.225)
ODIN_CHOPPERS = (8.4, 12.2, 13.6, 17.0, 23.69, 33.0)     # frame-overlap, band-pass and T0 choppers
# LoKI (loki_mcstas.py, virtual_loki.py)
LOKI_SAMPLE = 23.52
LOKI_CHOPPERS = (6.5, 15.21)
LOKI_BANKS = (("front banks", 1.5, 0.75), ("middle banks", 3.1, 0.42), ("rear bank", 5.0, 0.8))   # distance, half-size


def _clean(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_yticks([])


def odin_beamline():
    fig, ax = plt.subplots(figsize=(13, 3.6))
    ax.plot([0, ODIN_GUIDE_END], [0, 0], color="#E8C9A0", lw=12, solid_capstyle="butt", zorder=1)
    ax.plot([ODIN_PINHOLE, ODIN_DET], [0, 0], color="#F3E2C6", lw=12, solid_capstyle="butt", zorder=1)
    ax.add_patch(Rectangle((-1.2, -0.55), 1.2, 1.1, color=RED, zorder=3))
    ax.text(-0.6, 1.02, "source\n(moderator)", ha="center", va="bottom", fontsize=10.5, color=INK)
    for z in ODIN_WFM:
        ax.add_patch(Rectangle((z - 0.12, -0.6), 0.24, 1.2, color=TEAL, zorder=3))
    ax.text(7.0, 1.02, "WFM choppers\n(7 m)", ha="center", va="bottom", fontsize=10.5, color=TEAL)
    for z in ODIN_CHOPPERS:
        ax.add_patch(Rectangle((z - 0.12, -0.5), 0.24, 1.0, color=BLUE, zorder=3))
    ax.text(20.7, 1.02, "band choppers (8 to 33 m)", ha="center", va="bottom", fontsize=10.5, color=BLUE)
    ax.text(40, -0.62, "neutron guide: mirrors that carry the beam", ha="center", va="top", fontsize=10.5, color=ORANGE)
    ax.add_patch(Rectangle((ODIN_PINHOLE - 0.12, -0.9), 0.24, 0.72, color=INK, zorder=3))
    ax.add_patch(Rectangle((ODIN_PINHOLE - 0.12, 0.18), 0.24, 0.72, color=INK, zorder=3))
    ax.text(ODIN_PINHOLE, 1.02, "pinhole\n(50 m)", ha="center", va="bottom", fontsize=10.5, color=INK)
    ax.add_patch(Rectangle((ODIN_SAMPLE - 0.35, -0.4), 0.3, 0.8, color=GREY, ec=INK, zorder=3))
    ax.add_patch(Rectangle((ODIN_DET + 0.25, -0.7), 0.25, 1.4, color=TEAL, zorder=3))
    # sample and camera are 5 cm apart (drawn wider apart): one label each, with an arrow
    ax.annotate("sample\n(60.5 m)", (ODIN_SAMPLE - 0.2, 0.42), (56.6, 1.35), ha="center", va="bottom", fontsize=10.5,
                color=INK, arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.1, shrinkA=2, shrinkB=2))
    ax.annotate("camera\n(5 cm behind)", (ODIN_DET + 0.38, 0.72), (63.8, 1.35), ha="center", va="bottom", fontsize=10.5,
                color=TEAL, arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=1.1, shrinkA=2, shrinkB=2))
    ax.annotate("", (ODIN_SAMPLE - 0.4, -1.25), (ODIN_PINHOLE, -1.25), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text((ODIN_PINHOLE + ODIN_SAMPLE) / 2, -1.33, "L = 10.5 m", ha="center", va="top", fontsize=10.5, color=INK)
    ax.set_xlim(-3, 67); ax.set_ylim(-1.9, 2.4)
    ax.set_xlabel("distance from the source (m)")
    _clean(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "odin_beamline.png"), dpi=150)
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
    fig.savefig(os.path.join(OUT, "odin_tof.png"), dpi=150)
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
    fig.savefig(os.path.join(OUT, "odin_choppers.png"), dpi=150)
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
    fig.savefig(os.path.join(OUT, "odin_pinhole.png"), dpi=150)
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
    fig.savefig(os.path.join(OUT, "loki_beamline.png"), dpi=150)
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
    fig.savefig(os.path.join(OUT, "loki_q.png"), dpi=150)
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
    fig.savefig(os.path.join(OUT, "loki_tof.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for lam in (1, 2, 4, 6, 8):
        print(f"ODIN: {lam} Å reaches the camera ({ODIN_DET} m) after {lam * ODIN_DET / H_OVER_M * 1e3:.1f} ms")
    print(f"ODIN: band between two pulses {H_OVER_M * PERIOD / ODIN_DET:.2f} Å; with one pulse in two "
          f"{2 * H_OVER_M * PERIOD / ODIN_DET:.2f} Å; natural resolution {H_OVER_M * TAU / ODIN_DET:.3f} Å")
    odin_beamline(); odin_tof(); odin_choppers(); odin_pinhole(); loki_beamline(); loki_q(); loki_tof()
    print("written", OUT)
