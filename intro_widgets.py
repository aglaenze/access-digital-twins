"""Interactive pictures of the introductions to the instruments (ODIN_intro, LoKI_intro): sliders and buttons that
redraw a small figure, to let the student try the relations instead of reading them.

    import intro_widgets as iw
    iw.odin_time_of_flight()      # wavelength -> speed, arrival time at the camera, next pulse
    iw.odin_pinhole()             # pinhole size, sample-camera distance -> blur and noise of a test pattern
    iw.loki_q()                   # position on the detector, wavelength, distance -> angle, Q, size
    iw.loki_collimation()         # collimation length -> neutrons per second and divergence (recorded beams of the twin)

The figures are drawn with matplotlib into an image widget (PNG bytes), not into an Output widget: on the Voila pages
this needs no output capture (see page_output.py) and redraws without flicker.
"""
import io

import ipywidgets as w
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from matplotlib.patches import Rectangle

INK, TEAL, ORANGE, GREY, RED, BLUE = "#142033", "#0E7C70", "#C7711A", "#8A94A6", "#B4562B", "#2F5FB3"
H_OVER_M = 3956.034            # m·Å/s
PERIOD_MS = 1000 / 14          # ms between two ESS pulses
ODIN_L = 60.55                 # m, source to camera (sample at 60.5 m, camera 5 cm behind)
ODIN_L_PINHOLE = 10.5          # m, pinhole to sample
STYLE = {"description_width": "230px"}
LAYOUT = w.Layout(width="560px")
# LoKI: neutrons per second on the sample and rms divergence (horizontal) of the recorded beams of the twin
# (official McStas model, measured on loki/front/*/beam_at_sample, 2026-11-11)
LOKI_BEAMS = {"3 m": (9.4e8, 0.170), "5 m": (1.9e8, 0.073), "8 m": (7.8e7, 0.046)}


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


def _show(controls, draw, text=None):
    """controls: widgets; draw(): returns (figure, html text). Redrawn at every change."""
    img, info = w.Image(format="png", layout=w.Layout(width="780px")), w.HTML()

    def update(_=None):
        fig, html = draw()
        img.value = _png(fig)
        info.value = f"<div style='font-size:14.5px;line-height:1.6;color:{INK}'>{html}</div>"

    for c in controls:
        c.observe(update, names="value")
    update()
    display(w.VBox([*controls, img, info]))


# --------------------------------------------------------------------------------------------- ODIN
def odin_time_of_flight():
    lam = w.FloatSlider(value=4.0, min=1.0, max=9.0, step=0.1, description="wavelength λ (Å)", readout_format=".1f",
                        continuous_update=False, style=STYLE, layout=LAYOUT)

    def draw():
        l = lam.value
        v = H_OVER_M / l
        t = ODIN_L / v * 1e3
        fig, ax = plt.subplots(figsize=(8.2, 3.3))
        for k in range(3):
            ax.add_patch(Rectangle((k * PERIOD_MS, -2.5), 2.86, 2.5, color=RED if k == 0 else "#D9A7A0"))
            ax.axvline(k * PERIOD_MS, color="#D9A7A0", lw=0.8, ls=":")
            ax.text(k * PERIOD_MS + 1.4, -5, f"pulse {k + 1}", ha="center", va="top", fontsize=9, color=INK)
        ax.plot([0, t], [0, ODIN_L], color=TEAL, lw=2.5)
        ax.plot(t, ODIN_L, "o", color=TEAL, ms=8)
        ax.axhline(ODIN_L, color=INK, lw=1)
        ax.text(158, ODIN_L - 2, "camera", ha="right", va="top", fontsize=9.5, color=INK)
        ax.set_xlim(-3, 160); ax.set_ylim(-13, 70)
        ax.set_xlabel("time after pulse 1 (ms)"); ax.set_ylabel("distance (m)")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        late = int(t // PERIOD_MS)
        when = ("before pulse 2 leaves the source" if late == 0 else
                f"after pulse {late + 1} has left the source: it travels together with faster neutrons of a later pulse")
        return fig, (f"A neutron of <b>{l:.1f} Å</b> travels at <b>{v:.0f} m/s</b> and reaches the camera "
                     f"(60.55 m) after <b>{t:.1f} ms</b>, {when}.")

    _show([lam], draw)


def _pattern(blur_um, rel_flux, rng):
    """A test pattern of bars (400, 200, 100 and 50 µm wide) seen with a blur and a counting noise."""
    px = 10.0                                                  # µm per pixel
    row = np.ones(0)
    for width in (400, 200, 100, 50):
        n = int(width / px)
        row = np.r_[row, np.ones(3 * n), np.tile(np.r_[np.full(n, 0.35), np.ones(n)], 4)]
    row = np.r_[row, np.ones(30)]
    k = max(int(round(blur_um / px)), 1)
    row = np.convolve(np.pad(row, k, mode="edge"), np.ones(k) / k, mode="same")[k:-k]
    img = np.tile(row, (70, 1))
    counts = 400 * rel_flux                                     # counts per pixel in the open beam
    return rng.poisson(img * counts) / counts


def odin_pinhole():
    d = w.ToggleButtons(options=[("1 cm", 0.01), ("2 cm", 0.02), ("3 cm", 0.03), ("4 cm", 0.04)], value=0.03,
                        description="pinhole D", style={"button_width": "70px", "description_width": "230px"})
    l = w.FloatSlider(value=5.0, min=1.0, max=20.0, step=1.0, description="sample to camera distance l (cm)",
                      readout_format=".0f", continuous_update=False, style=STYLE, layout=LAYOUT)

    def draw():
        ratio = ODIN_L_PINHOLE / d.value
        blur = l.value * 1e-2 * d.value / ODIN_L_PINHOLE * 1e6          # µm
        flux = (d.value / 0.03) ** 2
        img = _pattern(blur, flux, np.random.default_rng(1))
        fig, ax = plt.subplots(figsize=(8.2, 2.4))
        ax.imshow(img, cmap="gray", vmin=0.1, vmax=1.25, aspect="auto", extent=(0, img.shape[1] * 0.01, 0, 1))
        ax.set_yticks([]); ax.set_xlabel("position on the camera (mm): bars 400, 200, 100 and 50 µm wide")
        fig.tight_layout()
        return fig, (f"L/D = 10.5 m / {d.value * 100:.0f} cm = <b>{ratio:.0f}</b>. Blur = l × D / L = "
                     f"<b>{blur:.0f} µm</b>. Neutrons through the pinhole: <b>{flux:.2f} ×</b> those of the 3 cm "
                     f"pinhole (the area of the hole), so the image is {'noisier' if flux < 1 else 'smoother' if flux > 1 else 'the reference'}"
                     f"{'' if flux == 1 else ' for the same counting time'}.")

    _show([d, l], draw)


# --------------------------------------------------------------------------------------------- LoKI
def loki_q():
    r = w.FloatSlider(value=10.0, min=2.0, max=75.0, step=1.0, description="distance r from the beam axis (cm)",
                      readout_format=".0f", continuous_update=False, style=STYLE, layout=LAYOUT)
    lam = w.FloatSlider(value=6.0, min=3.0, max=11.5, step=0.5, description="wavelength λ (Å)", readout_format=".1f",
                        continuous_update=False, style=STYLE, layout=LAYOUT)
    dist = w.ToggleButtons(options=[("5 m", 5.0), ("10 m", 10.0)], value=5.0, description="sample to rear detector",
                           style={"button_width": "70px", "description_width": "230px"})

    def draw():
        two_theta = np.arctan(r.value / 100 / dist.value)
        q = 4 * np.pi * np.sin(two_theta / 2) / lam.value
        size = 2 * np.pi / q
        fig, ax = plt.subplots(figsize=(8.2, 2.9))
        z = dist.value
        ax.plot([-1.5, 0], [0, 0], color=TEAL, lw=4, solid_capstyle="butt")
        ax.add_patch(Rectangle((-0.08, -0.07), 0.16, 0.14, color=GREY, ec=INK))
        ax.plot([0, 10.3], [0, 0], color=TEAL, lw=1, ls=":")
        ax.plot([z, z], [-0.8, 0.8], color=INK, lw=4)
        ax.plot([0, z], [0, r.value / 100], color=ORANGE, lw=2)
        ax.plot(z, r.value / 100, "o", color=ORANGE, ms=8)
        ax.text(z, 0.86, "rear detector", ha="center", fontsize=9.5, color=INK)
        ax.text(0, -0.16, "sample", ha="center", va="top", fontsize=9.5, color=INK)
        ax.set_xlim(-1.6, 10.6); ax.set_ylim(-0.95, 1.0)
        ax.set_xlabel("distance from the sample (m)"); ax.set_ylabel("height (m)")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout()
        return fig, (f"Angle 2θ = <b>{np.degrees(two_theta):.2f}°</b>. Q = 4π sin θ / λ = <b>{q:.4f} Å⁻¹</b>. "
                     f"Size seen: d = 2π / Q = <b>{size:.0f} Å = {size / 10:.1f} nm</b>.")

    _show([r, lam, dist], draw)


def loki_collimation():
    col = w.ToggleButtons(options=list(LOKI_BEAMS), value="3 m", description="collimation length",
                          style={"button_width": "70px", "description_width": "230px"})

    def draw():
        fig, axs = plt.subplots(1, 2, figsize=(8.2, 2.6))
        names = list(LOKI_BEAMS)
        for ax, k, title, unit in ((axs[0], 0, "neutrons per second on the sample", "×10⁸ n/s"),
                                   (axs[1], 1, "divergence of the beam (rms)", "degrees")):
            vals = [LOKI_BEAMS[n][k] / (1e8 if k == 0 else 1) for n in names]
            bars = ax.bar(names, vals, color=[TEAL if n == col.value else "#C9D3DE" for n in names])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2g}", ha="center", va="bottom", fontsize=9.5, color=INK)
            ax.set_title(title, fontsize=10.5, color=INK); ax.set_ylabel(unit)
            ax.set_ylim(0, max(vals) * 1.2)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
        fig.tight_layout()
        flux, div = LOKI_BEAMS[col.value]
        f3, d3 = LOKI_BEAMS["3 m"]
        return fig, (f"Collimation <b>{col.value}</b>: {flux:.1e} neutrons per second on the sample "
                     f"(<b>{f3 / flux:.0f} times fewer</b> than with 3 m), divergence {div:.3f}° "
                     f"(<b>{d3 / div:.1f} times more parallel</b>)." if col.value != "3 m" else
                     f"Collimation <b>3 m</b>: {flux:.1e} neutrons per second on the sample, divergence {div:.3f}°: "
                     "the most neutrons, the least parallel beam.")

    _show([col], draw)
