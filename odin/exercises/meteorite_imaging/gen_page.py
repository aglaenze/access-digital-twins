"""Generates ODIN_meteorite.ipynb: the guided page (Voila, no code shown) of the exercise
"What is hidden inside a Martian meteorite?" (white-beam radiography and tomography, then time of flight).

    python gen_page.py
"""
import os
import sys

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from nbfig import figure_cell, insert_after_mission  # noqa: E402
from nbgen import distribute  # noqa: E402

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# What is hidden inside a Martian meteorite?

You are operating the ODIN imaging instrument at ESS. Behind this page, a simulation of the instrument produces your
measurements, in the formats of the real instrument.

**Your mission.** You work for a team of planetary scientists. The meteorite NWA 7034 ("Black Beauty"), found in the
Sahara in 2011, is a piece of the Martian crust 4.4 billion years old, and it contains more water than any other
Martian meteorite: water bound in its minerals, a record of the water of early Mars. The team wants to know **where
the water is**: spread evenly, or concentrated in some of the rock fragments (clasts) that make up the meteorite? A
gram of this meteorite is worth more than a gram of gold, and the team will drill a sample out of the richest clast
for a chemical analysis: you must find it **without cutting the meteorite**, and tell the team how much water it
holds (part 6).

**Why neutrons.** X-rays are stopped by heavy atoms (iron, calcium) and hardly see hydrogen. Neutrons do the
opposite: **hydrogen** scatters them more than any other element, while silicon, oxygen, magnesium or aluminum let
them through. In a neutron image, the hydrogen of the water is dark.

**What you will measure.** A beam goes through the sample; the fraction that comes out, the **transmission**, is

$$T = \frac{I}{I_0} = e^{-\Sigma L}$$

with $L$ the thickness crossed and $\Sigma$ the **attenuation coefficient** of the material (in cm⁻¹: the fraction of
neutrons removed per cm). The camera records $T$ for each pixel: a **radiograph** (part 1 to 3). A radiograph adds up
everything along the beam; turning the sample and taking a radiograph at many angles gives back $\Sigma$ at every
point inside: a **tomography** (part 4). Finally the time of flight of the neutrons gives their wavelength, and the
way $\Sigma$ changes with the wavelength tells which element attenuates (part 5).

**Questions along the page** check each step: answer in the box, then click *Check*. A wrong answer is explained;
after a try you can also show the answer. Your answers are kept.
""")

code(r"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import web_user
web_user.sign_in()            # the online version: the anonymous student of the start page (nothing to do in the app)
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display, clear_output
from odin_virtual import VirtualOdin
import odin_viz as viz, odin_radiography as tomo
import live_view
from page_output import into
import quiz
q = quiz.Quiz("odin_meteorite_bsc")      # the questions, along the page

SAMPLE = "meteorite_nwa7034"
odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
odin.move(sample=SAMPLE)
EXT = tomo.extent()
""")

md(r"""
## 0. Your sample

A cylinder **12 mm across and 12 mm high**, cut from the meteorite, standing on the rotation stage of ODIN. The beam
comes horizontally along $z$; the camera (14 mm × 14 mm, 128 × 128 pixels of 0.11 mm) is just behind the sample and
looks at it along the beam: horizontal axis $x$, vertical axis $y$. The rotation stage turns the sample about the
vertical axis $y$.

## 1. Operate the instrument: radiographs

ODIN is set for **white-beam imaging**: the choppers are stopped (all the wavelengths of the ESS pulse go through,
the highest flux), and the images are taken with a camera that integrates the light of a scintillator screen (no
time of flight). The pinhole is 3 cm wide. Take three images, one per row:

| Image | Shutter | Sample | Exposure (s) | Title |
|---|---|---|---|---|
| 1. dark | **closed** | in | 2 | dark |
| 2. open beam | **open** | **out** | 2 | open beam |
| 3. radiograph | open | **in** | 2 | meteorite 0° |

Why these images: the camera gives a small signal even without neutrons (the **dark**), and the beam is not exactly
uniform over the field (the **open beam**, sample moved 50 cm aside). The transmission of each pixel is

$$T = \frac{I - D}{O - D}$$

with $I$, $O$, $D$ the counts per second of the radiograph, the open beam and the dark in that pixel. In a white
beam, 2 s give about 1800 neutrons per pixel: a noise of about 2 %. The first image takes about 20 s (the beam
is prepared), the next ones about 1 s.
""")

code(r"""
st = odin.status()
shut = w.ToggleButtons(options=[("closed", "closed"), ("open", "open")], value=st["shutter"], description="Shutter")
inout = w.ToggleButtons(options=[("in", 0.0), ("out", 0.5)], value=0.0 if abs(st["stage_x"]) < 0.02 else 0.5,
                        description="Sample")
expo = w.Dropdown(options=[1, 2, 5, 10], value=2, description="Exposure (s)")
title = w.Text(value="", placeholder="e.g. open beam", description="Title")
button = w.Button(description="Take image", button_style="primary", icon="camera", layout=w.Layout(width="auto"))
out = w.Output()

def default_title():
    if shut.value == "closed":
        return "dark"
    return "open beam" if inout.value > 0.02 else "meteorite 0°"

def take(_):
    button.disabled = True
    with out:
        clear_output()
        try:
            odin.move(choppers="white", pinhole=0.03, diffuser="in", shutter=shut.value, stage_x=inout.value,
                      stage_rot=0.0, sample=SAMPLE)
            f = odin.camera(float(expo.value), title=title.value or default_title())
            fig, ax = plt.subplots(figsize=(5.2, 4.4))
            im = ax.imshow(odin.last_image, origin="lower", extent=EXT, cmap="gray")
            fig.colorbar(im, ax=ax, label="counts per pixel")
            ax.set(xlabel="x (mm)", ylabel="y (mm)", title=f"{os.path.basename(f)}: {title.value or default_title()}")
            plt.tight_layout(); plt.show()
        except Exception as e:
            print("Error:", e)
    button.disabled = False
    refresh_list()

button.on_click(take)
display(w.VBox([shut, inout, expo, title, button, out]))
""")

md(r"""
## 2. Your measurements

Each image is a numbered file, as on the real instrument; the table is your logbook.
""")

code(r"""
listing = w.Output()

def measurements(kind_of_file="camera"):
    ms = []
    if os.path.isfile(odin.log_file):
        for l in open(odin.log_file, encoding="utf-8"):
            e = json.loads(l)
            if e["action"] != kind_of_file or not e["details"].get("file"):
                continue
            d = e["details"]; s = d["state"]
            if s.get("sample") != SAMPLE:
                continue
            kind = "dark" if s["shutter"] == "closed" else ("open beam" if abs(s["stage_x"]) > 0.02 else "sample")
            ms.append(dict(file=d["file"], path=os.path.join(odin.folder, d["file"]), title=d["title"], t=d["t"],
                           kind=kind, rot=float(s["stage_rot"]), counts=d["n_counts"], choppers=s["choppers"]))
    return ms

def label(m):
    return f"{m['file']}: {m['title'] or '(no title)'}"

def refresh_list():
    ms = measurements()
    of = lambda kind: [(label(m), m["path"]) for m in reversed(ms) if m["kind"] == kind and m["choppers"] == "white"
                       and "tomography" not in m["title"]]
    for dd, opts in ((pick_S, of("sample")), (pick_O, of("open beam")), (pick_D, of("dark"))):
        dd.options = opts
        if opts:
            dd.value = opts[0][1]
    with into(listing):
        n_tomo = sum("tomography" in m["title"] for m in ms)
        if not ms:
            print("No image yet.")
        for m in ms:
            if "tomography" not in m["title"]:
                print(f"{m['file']}  {m['title'] or '(no title)':16s} {m['kind']:10s} t = {m['t']:3g} s  "
                      f"rotation {m['rot']:5.1f}°  -> {m['counts']:,} counts")
        if n_tomo:
            print(f"... and {n_tomo} images of tomography (part 4)")

wide = w.Layout(width="520px")
pick_S = w.Dropdown(description="Radiograph", layout=wide)
pick_O = w.Dropdown(description="Open beam", layout=wide)
pick_D = w.Dropdown(description="Dark", layout=wide)
refresh_list()
display(listing)
""")

md(r"""
## 3. The radiograph

*Show the transmission* computes $T$ for each pixel from your three images. The profile below the image follows one
horizontal line of pixels (choose its height): through the matrix of the meteorite, and through a dark spot.
""")

code(r"""
height = w.FloatSlider(value=2.0, min=-6.5, max=6.5, step=0.1, description="Line y (mm)", continuous_update=True,
                       layout=w.Layout(width="420px"))
button_T = w.Button(description="Show the transmission", button_style="success", icon="image", layout=w.Layout(width="auto"))
out_T = w.Output()
img_T = live_view.FigureImage()          # follows the slider while it moves

def chosen():
    if not (pick_S.value and pick_O.value):
        raise ValueError("Take first an open beam and a radiograph of the meteorite (part 1).")
    return pick_S.value, pick_O.value, pick_D.value

def show_T(_=None):
    with out_T:
        clear_output()
        try:
            S, O, D = chosen()
            T = tomo.transmission(S, O, D)
            with img_T:
                fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw=dict(width_ratios=[1, 1.25]))
                im = a.imshow(T, origin="lower", extent=EXT, cmap="gray", vmin=0.5, vmax=1.05)
                fig.colorbar(im, ax=a, label="transmission T")
                a.axhline(height.value, color="tab:orange", lw=1)
                a.set(xlabel="x (mm)", ylabel="y (mm)", title="Transmission of the meteorite")
                row = int(np.clip(round(height.value / tomo.PIXEL_MM + 63.5), 0, 127))
                x = np.linspace(EXT[0], EXT[1], 128)
                b.plot(x, T[row], color="tab:orange")
                b.set(xlabel="x (mm)", ylabel="transmission T", title=f"Profile at y = {height.value:.1f} mm", ylim=(0.5, 1.1))
                b.grid(alpha=0.3)
                plt.tight_layout()
            if D is None:
                print("Note: no dark image, the dark signal of the camera is not subtracted.")
        except Exception as err:
            clear_output()
            print("Not possible yet:", err)

button_T.on_click(show_T)
height.observe(live_view.throttled(lambda: show_T() if img_T.value else None), "value")
display(w.VBox([pick_S, pick_O, pick_D, w.HBox([button_T, height]), out_T, img_T]))
""")

md(r"""
**Reading the radiograph.** The cylinder looks like a rectangle (seen from the side). It is not black: through 12 mm
of rock about 75 % of the neutrons go through, rocks are almost transparent to neutrons. Some round spots are
**darker**: there, something attenuates far more than the rock around it. One spot is **brighter**: there, less
material is in the way. But a radiograph adds up everything along the beam: a spot can be one clast or several, one
behind the other, near the front or near the back. To know, the sample must be seen from many directions.

## 4. The tomography

*Run the tomography* turns the sample in steps over 180° and takes one image at each angle (1 s each, with the
open beam and dark of part 3). A beam of parallel lines sees the same thing from opposite directions, so 180° is
enough. Then, for each horizontal row of pixels, the projections $-\ln T$ at all the angles (the **sinogram**) are
**filtered** and **smeared back** along the direction they were taken in: this is the filtered back-projection, which
gives $\Sigma$ at each point of that slice. All the slices together are the sample in 3D.
""")

code(r"""
step = w.Dropdown(options=[("12° (15 images)", 12), ("6° (30 images)", 6), ("3° (60 images)", 3)], value=6,
                  description="Angle step", layout=w.Layout(width="320px"))
button_tomo = w.Button(description="Run the tomography", button_style="primary", icon="sync", layout=w.Layout(width="auto"))
bar = w.IntProgress(value=0, min=0, max=30, description="Images", layout=w.Layout(width="420px"))
out_tomo = w.Output()
VOL = {}

def run_tomo(_):
    button_tomo.disabled = True
    with out_tomo:
        clear_output()
        try:
            _, O, D = chosen()
            angles = np.arange(0, 180, step.value)
            bar.max, bar.value = len(angles), 0
            odin.move(choppers="white", pinhole=0.03, diffuser="in", shutter="open", stage_x=0.0, sample=SAMPLE)
            files = odin.tomography(angles, 1.0, title=f"tomography {step.value}°",
                                    progress=lambda k, n, f: setattr(bar, "value", k))
            odin.move(stage_rot=0.0)
            print("Reconstructing the slices...")
            VOL.update(vol=tomo.reconstruct(files, O, D), n=len(angles))
            clear_output()
            print(f"{len(angles)} images, reconstructed: {VOL['vol'].shape[0]} slices of {VOL['vol'].shape[1]} × "
                  f"{VOL['vol'].shape[2]} pixels. Look at them below.")
            show_slices()
        except Exception as err:
            clear_output()
            print("Not possible yet:", err)
    button_tomo.disabled = False
    refresh_list()

button_tomo.on_click(run_tomo)
display(w.VBox([w.HBox([step, button_tomo]), bar, out_tomo]))
""")

md(r"""
**Look inside.** The left image is a **horizontal slice** of the sample at the height you choose (seen from above:
the beam came from the bottom of the image at 0°, $z$ is the depth along it, toward the camera). The right image is a
**vertical slice** at the depth $z$ you choose (as on the radiograph, but only this slice of the sample). The colour is
$\Sigma$ in cm⁻¹. Move the two sliders through the whole sample: count the clasts, find their size and their depth.
""")

code(r"""
ys = w.FloatSlider(value=2.0, min=-6.5, max=6.5, step=0.11, description="Height y (mm)", continuous_update=True,
                   layout=w.Layout(width="420px"))
zs = w.FloatSlider(value=-1.5, min=-6.5, max=6.5, step=0.11, description="Depth z (mm)", continuous_update=True,
                   layout=w.Layout(width="420px"))
img_sl = live_view.FigureImage()          # follows the sliders while they move
txt_sl = w.HTML("Run the tomography first.")

def px(mm):
    return int(np.clip(round(mm / tomo.PIXEL_MM + 63.5), 0, 127))

def show_slices(_=None):
    if "vol" not in VOL:
        return
    v = VOL["vol"]
    with img_sl:
        fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.6))
        kw = dict(origin="lower", extent=EXT, cmap="magma", vmin=0, vmax=1.2)
        im = a.imshow(v[px(ys.value)], **kw)
        a.axhline(zs.value, color="w", lw=0.8, ls="--")
        a.set(xlabel="x (mm)", ylabel="depth z (mm)", title=f"Horizontal slice at y = {ys.value:.1f} mm")
        b.imshow(v[:, px(zs.value), :], **kw)
        b.axhline(ys.value, color="w", lw=0.8, ls="--")
        b.set(xlabel="x (mm)", ylabel="y (mm)", title=f"Vertical slice at depth z = {zs.value:.1f} mm")
        fig.colorbar(im, ax=[a, b], label="Σ (cm⁻¹)")
    c = v[px(ys.value)][54:74, 54:74]
    txt_sl.value = f"Σ in the center of the horizontal slice: <b>{np.median(c):.2f} cm⁻¹</b> (median of 20 × 20 pixels)"

ys.observe(live_view.throttled(show_slices), "value")
zs.observe(live_view.throttled(show_slices), "value")
display(w.VBox([w.HBox([ys, zs]), img_sl, txt_sl]))
show_slices()
""")

md(r"""
**Limits.** The slices are noisy (the noise of each image is amplified by the ramp filter) and have rings and streaks
(too few angles); more images, or longer ones, reduce both. A real tomography of ODIN takes hundreds of images with
pixels of a few tens of micrometers. Each image here is computed from the attenuation of each volume of the model
(an approximate mineral composition, given at the end); the camera is modeled by its mean signal, its noise and its
blur.

## 5. Which element? The wavelength of the neutrons

A dark spot means a large $\Sigma$, but large because of what? Hydrogen has a signature: for most elements $\Sigma$
changes little with the wavelength (or falls, past the **Bragg edges** of the crystals), but for hydrogen bound in a
mineral or in water it **grows** with the wavelength: slow neutrons are scattered more by the light, vibrating
hydrogen atoms.

ODIN measures the wavelength of each neutron by its **time of flight** from the source (a neutron of 4 Å flies
60 m in 60 ms). This needs the choppers (WFM mode, discs 0.30 m apart) and the event camera (Timepix3), which records
the time of each neutron; the flux is lower than in white beam. Measure, at stage rotation 0°:

| Measurement | Sample | Time (s) |
|---|---|---|
| 6. open beam (time of flight) | **out** | 10 |
| 7. meteorite (time of flight) | **in** | 10 |

Each count lasts as long as on the instrument (10 s), plus the time to compute it: about 5 million neutrons each.
""")

code(r"""
inout2 = w.ToggleButtons(options=[("in", 0.0), ("out", 0.5)], value=0.5, description="Sample")
ttime = w.Dropdown(options=[10, 20], value=10, description="Time (s)")
button_tof = w.Button(description="Count (time of flight)", button_style="primary", icon="play", layout=w.Layout(width="auto"))
out_tof = w.Output()

def count_tof(_):
    button_tof.disabled = True
    with out_tof:
        clear_output()
        try:
            odin.move(choppers="wfm", wfm_delta=0.30, pinhole=0.03, diffuser="in", shutter="open", stage_x=inout2.value,
                      stage_rot=0.0, sample=SAMPLE)
            live = viz.LiveCount()
            f = odin.count(ttime.value, title="open beam TOF" if inout2.value > 0.02 else "meteorite TOF",
                           progress=live.update)
            live.done(f)
        except Exception as e:
            print("Error:", e)
    button_tof.disabled = False
    refresh_tof()

def tof_files():
    ms = measurements("count")
    return ([m["path"] for m in ms if m["kind"] == "sample" and abs(m["rot"]) < 0.01 and m["choppers"] == "wfm"],
            [m["path"] for m in ms if m["kind"] == "open beam" and m["choppers"] == "wfm"])

tof_status = w.HTML()
def refresh_tof():
    s, o = tof_files()
    tof_status.value = (f"Time-of-flight files: {len(s)} of the meteorite, {len(o)} open beam"
                        + (" (the newest of each is used)" if s and o else ""))

button_tof.on_click(count_tof)
refresh_tof()
display(w.VBox([inout2, ttime, button_tof, out_tof, tof_status]))
""")

md(r"""
*Compare spot and matrix* takes two small disks of the image (0.5 mm radius): one on the darkest spot of your
radiograph, one on the matrix below it. Both see the same 11 mm of meteorite; the spot has, in addition, the clasts
in its line of sight. The ratio of the two transmissions removes the matrix:

$$\frac{T_\text{spot}}{T_\text{matrix}} = e^{-\Delta\Sigma\, L_c}$$

with $L_c$ the thickness of clast crossed by the beam in the spot, and $\Delta\Sigma$ how much more a clast attenuates
than the matrix. Enter $L_c$ from your tomography (part 4: the clasts on the line of sight of the spot, at $x$ = 2.5 mm,
$y$ = 2.0 mm, and their diameters). If the extra attenuation is due to water, $\Delta\Sigma(\lambda)$ follows
$\Sigma$ of water, and the ratio $f = \Delta\Sigma / \Sigma_\text{water}$ is the same at all wavelengths: $f$ is the
**fraction of the volume of the clast that the water would fill**.
""")

code(r"""
Lc = w.BoundedFloatText(value=1.0, min=0.1, max=12, step=0.1, description="L_c (mm)")
button_cmp = w.Button(description="Compare spot and matrix", button_style="success", icon="chart-line", layout=w.Layout(width="auto"))
out_cmp = w.Output()
RHO_CLAST = 2.6           # g/cm³, density of the clasts (from their composition)

def compare(_=None):
    button_cmp.disabled = True
    with out_cmp:
        clear_output()
        try:
            s, o = tof_files()
            if not (s and o):
                raise ValueError("Count first the open beam and the meteorite with time of flight (above).")
            print("Reading the files (about 20 s the first time)...")
            lam, (Ts, Tm), (dTs, dTm) = tomo.region_transmission(s[-1], o[-1])
            r = Ts / Tm
            dr = r * np.sqrt((dTs / Ts) ** 2 + (dTm / Tm) ** 2)
            dS = -np.log(r) / (Lc.value / 10)                 # cm⁻¹
            ddS = dr / r / (Lc.value / 10)
            sw = tomo.sigma_water(lam)
            f, df = dS / sw, ddS / sw
            m = (lam > 1.5) & (lam < 7.5) & np.isfinite(f)
            wgt = 1 / df[m] ** 2
            fm, dfm = np.sum(wgt * f[m]) / np.sum(wgt), 1 / np.sqrt(np.sum(wgt))
            clear_output()
            fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
            ax[0].errorbar(lam, Tm, dTm, fmt=".", ms=3, color="0.4", label="matrix")
            ax[0].errorbar(lam, Ts, dTs, fmt=".", ms=3, color="tab:red", label="spot")
            ax[0].set(xlabel="λ (Å)", ylabel="transmission", title="Transmission of the two regions", ylim=(0.3, 1.0))
            ax[0].legend()
            ax[1].errorbar(lam, dS, ddS, fmt=".", ms=3, color="tab:red", label="ΔΣ of the clast (measured)")
            ax[1].plot(lam, sw * fm, "b-", label=f"{fm:.3f} × Σ of water")
            ax[1].set(xlabel="λ (Å)", ylabel="cm⁻¹", title=f"Extra attenuation of the clast (L_c = {Lc.value:.1f} mm)")
            ax[1].legend(fontsize=9)
            ax[2].errorbar(lam[m], f[m], df[m], fmt=".", ms=3, color="tab:purple")
            ax[2].axhline(fm, color="k", lw=1)
            ax[2].set(xlabel="λ (Å)", ylabel="f = ΔΣ / Σ_water", title="Water fraction (by volume)", ylim=(0, max(0.4, 2 * fm)))
            for a in ax:
                a.grid(alpha=0.3)
            plt.tight_layout(); plt.show()
            print(f"f = ΔΣ / Σ_water = {fm:.3f} ± {dfm:.3f}: the water would fill {100 * fm:.1f} % of the volume of the clast")
            print(f"water by mass = f × 1.0 g/cm³ / {RHO_CLAST} g/cm³ = {100 * fm / RHO_CLAST:.1f} ± {100 * dfm / RHO_CLAST:.1f} %")
        except Exception as err:
            clear_output()
            print("Not possible yet:", err)
    button_cmp.disabled = False

button_cmp.on_click(compare)
display(w.VBox([w.HBox([Lc, button_cmp]), out_cmp]))
""")

md(r"""
**Limits.** The model of the meteorite uses minerals that NCrystal describes: the matrix is quartz, olivine and
corundum (the real one: plagioclase, pyroxene and iron oxides), the water of the clasts is carried by a hydroxide
(brucite; in NWA 7034, mostly iron oxyhydroxides). The transmission depends on how much hydrogen there is, and
little on which mineral carries it, so the method and the orders of magnitude are those of a real measurement.
Water bound in a mineral does not scatter exactly as liquid water: comparing with $\Sigma$ of water gives an estimate,
good to about 10 %.

## 6. Your results

Your score on the questions of the page, and a report to download.
""")

code(r"""
q.choice("Why are some spots of the radiograph **darker** than the rest of the meteorite?",
         ["They contain hydrogen (water), which scatters neutrons far more than the other elements of the rock.",
          "They contain heavy elements such as iron, which stop the neutrons.",
          "They are thicker parts of the cylinder.",
          "The camera has dead pixels there."],
         answer=0, why={1: "Heavy elements stop X-rays; for neutrons, iron attenuates about as much as the rock. "
                           "Hydrogen is the exception.",
                        2: "The cylinder has the same thickness at a given x: the spots are round, not bands.",
                        3: "The open beam is divided out, and the spots move when the sample turns (part 4)."},
         explanation="Hydrogen has a scattering cross-section of about 80 barns, ten to twenty times that of Si, O, Mg "
                     "or Al: a little water makes a rock dark for neutrons. This is why neutrons are used to find water "
                     "in rocks, soils, plants or fuel cells.",
         hints=["Read the paragraph 'Why neutrons' at the top of the page."], title="Q1. Dark spots")
q.number("How many **dark spots** do you see on the radiograph at 0°?", value=4, tol=0.1,
         mistakes=[(5, "count the spots of the radiograph (part 3), not the clasts of the tomography"),
                   (6, "the bright spot is not a dark one")],
         hints=["Look at the transmission image of part 3: round spots darker than the matrix."],
         explanation="Four dark spots, and one bright spot. The tomography will tell how many clasts there really are.",
         title="Q2. The radiograph")
q.number("How many **clasts** rich in water does the tomography show?", value=5, tol=0.1,
         mistakes=[(4, "one spot of the radiograph hides two clasts, one behind the other: move the depth slider through "
                       "the dark spot at the top right"),
                   (6, "the bright region is not a clast with water: its Σ is lower than the matrix")],
         hints=["Move the height slider from bottom to top, and count the clasts of each slice.",
                "Look at the slice at y = 2 mm: how many clasts at x ≈ 2.5 mm?"],
         explanation="Five clasts: at y = 2 mm two of them lie one behind the other along the beam (z = −1.5 mm and "
                     "z = +3 mm), and make one spot on the radiograph at 0°. This is what a tomography is for.",
         title="Q3. The tomography")
q.number("What is the **diameter** of the largest clast (mm)?", value=3.0, tol=0.45, unit="mm",
         hints=["Find the slice where the largest clast is widest, and read its width on the x axis."],
         explanation="3.0 mm (the clast at x = 2.5 mm, y = 2 mm, z = −1.5 mm). The blur of the images (about 0.2 mm) "
                     "and the noise make the edge uncertain by a pixel or two.", title="Q4. The largest clast")
q.number("The two clasts in the line of sight of the darkest spot: how far apart are they **along the beam** "
         "(between their centers, in mm)?", value=4.5, tol=0.7, unit="mm",
         hints=["Horizontal slice at y = 2 mm: the two clasts at x ≈ 2.5 mm; read their depths z."],
         explanation="z = −1.5 mm and z = +3.0 mm: 4.5 mm apart. On the radiograph they were one spot.",
         title="Q5. One behind the other")
q.number("What attenuation coefficient Σ does the tomography give for the **matrix** of the meteorite (cm⁻¹)?",
         value=0.24, tol=0.06, unit="cm⁻¹",
         hints=["The slices print Σ at their center, where there is only matrix (choose a slice without clast there)."],
         explanation="About 0.24 cm⁻¹ (white-beam average): 12 mm of matrix let e^(−0.24 × 1.2) = 75 % of the neutrons "
                     "through, as the radiograph showed.", title="Q6. The matrix")
q.choice("What is the **bright** spot?", ["A void (a vesicle or a crack): less material in the way.",
                                          "A clast very rich in water.", "A metal grain.",
                                          "A reflection of the beam."],
         answer=0, why={1: "Water would make it darker, not brighter.",
                        2: "A metal would attenuate about as much as the rock, or more: not brighter.",
                        3: "Neutrons are not reflected by a rock in a way that would make a spot."},
         explanation="Its Σ in the tomography is about zero: empty space, 1.5 mm across. Martian breccias have such "
                     "pores and cracks.", hints=["Look at it in the tomography: what is its Σ?"], title="Q7. The bright spot")
q.choice("How does the extra attenuation of the clast, ΔΣ, change with the wavelength (part 5)?",
         ["It grows with the wavelength, like Σ of water: the attenuation is due to hydrogen.",
          "It is the same at all wavelengths: the clast is just denser.",
          "It falls at Bragg edges: the clast is a crystal of a heavy mineral.",
          "It falls with the wavelength."],
         answer=0, why={1: "Look at the middle plot of part 5: ΔΣ doubles from 2 to 6 Å.",
                        2: "The matrix shows small Bragg edges, the ratio spot / matrix does not.",
                        3: "Look at the middle plot of part 5."},
         explanation="ΔΣ about doubles between 2 and 6 Å and follows the curve of water: the ratio f is the same at "
                     "all wavelengths. This is the signature of hydrogen; a denser or heavier mineral would give an "
                     "extra attenuation almost independent of the wavelength.",
         hints=["Middle plot of part 5: is ΔΣ flat, or does it follow the blue curve of water?"],
         title="Q8. The signature of hydrogen")
q.number("How much **water by mass** does the darkest clast hold (part 5, in %)?", value=5.2, tol=1.6, unit="%",
         mistakes=[(13.0, "this is the fraction by volume f; by mass, divide by the density of the clast, 2.6 g/cm³")],
         hints=["L_c is the sum of the diameters of the two clasts on the line of sight (Q4, Q5): about 3.0 + 1.8 mm.",
                "Part 5 prints the water by mass once L_c is right."],
         explanation="With L_c = 4.8 mm, f ≈ 0.12 to 0.14: about 5 % of water by mass (the model holds 5.7 %: the disk "
                     "of the spot also sees the thinner edges of the clasts, and water bound in a mineral scatters a "
                     "little less than liquid water, so the estimate is a little low). With a wrong L_c the result "
                     "changes in proportion: the tomography is needed for the thickness, the time of flight for the "
                     "element.", title="Q9. How much water?")
q.choice("**Your report to the team.** Where should they drill?",
         ["In the large clast at x = 2.5 mm, y = 2 mm, z = −1.5 mm: the largest of the five clasts rich in water "
          "(about 5 % water by mass), whose position is known in 3D.",
          "Anywhere: the water is spread evenly in the meteorite.",
          "In the bright spot: it is where the water was.",
          "At the darkest spot of the radiograph, from the front face: the depth does not matter."],
         answer=0, why={1: "The matrix has little hydrogen: the water is in the clasts.",
                        2: "The bright spot is a void.",
                        3: "The darkest spot is two clasts at different depths: drilling from the front would reach "
                           "the large one first, but you must know how deep to go."},
         explanation="The water is concentrated in five clasts; the tomography gives the position and the size of "
                     "each, the time of flight shows that the attenuation is due to hydrogen and how much. The team can "
                     "drill out the 3 mm clast at the right depth without destroying the rest.",
         hints=["Q3, Q4, Q5 and Q9 together."], title="Q10. The report")
q.report()
""")

md(r"""
## 7. Submit your work

When you are done, tell what you thought of the exercise and submit your work.
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/meteorite_imaging", "bsc", quiz=q)
""")

distribute(cells, [
    ("button_T.on_click(show_T)", [1, 2]),                            # the radiograph
    ("display(w.VBox([w.HBox([ys, zs]), img_sl, txt_sl]))", [3, 4, 5, 6, 7]),   # the tomography
    ("button_cmp.on_click(compare)", [8, 9, 10]),                     # the element, the water, the report
])
insert_after_mission(cells, figure_cell(
    "meteorite_tomography.png", "A radiograph adds up everything along the beam (left): two clasts one behind the "
    "other make one spot. Turning the sample and taking radiographs over 180° (middle) gives back each slice by "
    "filtered back-projection (right)."))
nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_meteorite.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
