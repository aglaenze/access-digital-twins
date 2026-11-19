"""Generates ODIN_meteorite_class.ipynb: a 30-minute session for a class (first use: DTU, MSc course "Advanced X-ray
imaging", 23 November 2026, after a lecture on neutron imaging). ODIN in short for X-ray imagers, then the meteorite
NWA 7034 in a condensed form: one high-resolution radiograph, a tomography, the hydrogen-rich clasts, how much water.
Not an exercise of the catalogue of the app: the start page of the online version shows it on top.

    python gen_class_page.py
"""
import os
import sys

import re

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from nbfig import figure_cell  # noqa: E402
from page_texts import transmission_md  # noqa: E402

import yaml  # noqa: E402
with open(os.path.join(HERE, "..", "..", "samples", "meteorite_nwa7034.yml"), encoding="utf-8") as _f:
    _Y1 = next(v["center_mm"][1] for v in yaml.safe_load(_f)["volumes"] if v["material"] == "H-Fe-ox clast 1")
Y1S = f"{round(_Y1 / 0.0275) * 0.0275:.2f}"
WHERE = "near the top" if _Y1 > 2 else ("in the lower part" if _Y1 < -2 else "around the middle")
_sub = lambda s: s.replace("@Y1@", Y1S).replace("@WHERE@", WHERE)

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(_sub(s).strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(_sub(s).strip()))
fig = lambda name, caption: cells.append(figure_cell(name, caption))

md(r"""
# ODIN in 30 minutes: what is hidden inside a Martian meteorite?

You know X-ray imaging well. Today you image with **neutrons**, on the digital twin of **ODIN**, the imaging
instrument of the European Spallation Source (ESS): a simulation of the real instrument, which writes its data in the
formats of ESS. Everything happens in this page: no code to write.

**Plan of the 30 minutes**

| Time | What you do |
|---|---|
| 0–5 min | read *ODIN for X-ray imagers* and the mission |
| 5–12 min | take the three images with the Timepix3 camera, reduce them: the radiograph (parts 1–2) |
| 12–20 min | run the tomography, find the bright clasts in the slices (parts 3–4) |
| 20–27 min | measure Σ, estimate the water (parts 5–6) |
| 27–30 min | your comment, and *Submit* (part 7) |

Short questions along the way check each step: answer, then *Check*; a wrong answer is explained, and after a try you
can show the answer.
""")

code(r"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display, clear_output
from odin_virtual import VirtualOdin, Cancelled
import odin_radiography as tomo
import odin_viz as viz
import live_view
import measure_control as mc
import analysis_chain
from page_output import into
import web_user
web_user.sign_in()            # the online version: the anonymous student of the start page
import quiz
q = quiz.Quiz("odin_meteorite_class")

SAMPLE = "meteorite_nwa7034"
odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
odin.move(sample=SAMPLE)
EXT = tomo.extent()
PX, PINHOLE = 512, 0.01                      # the high-resolution setup: 512 x 512 pixels of 27.5 µm, 1 cm pinhole
""")

md(r"""
## ODIN for X-ray imagers, in five points

The lecture showed the principles (Beer-Lambert, the pinhole camera, the contrasts); here is what they mean on ODIN.

1. **Compared with X-rays, the contrast is reversed.** X-rays interact with the electrons, so the heavy elements
   stand out; neutrons interact with the **nuclei**. **Hydrogen** removes neutrons more than any other element (it
   scatters them strongly), and lithium, boron, cadmium, gadolinium absorb them; but iron, aluminum, silicon, lead let
   most of them through. A neutron image shows the water inside a metal or a rock, where X-rays see the heavy
   elements.
2. **A pulsed source and the time of flight.** At ESS, protons hit a tungsten target 14 times per second; each pulse
   (2.86 ms) makes neutrons, slowed down by a moderator. ODIN is 60 m long: the arrival time of a neutron at the camera
   gives its speed, so its wavelength. Today you use the **white beam**: all the wavelengths together, like a
   polychromatic X-ray beam (and with a similar "beam hardening").
3. **No lens, no magnification.** The beam is shaped by a **pinhole** of D = 1 to 4 cm, L = 10.5 m before the sample:
   an almost parallel beam (L/D up to 1050). Each point of the sample becomes a spot of size $l \cdot D / L$ on the
   camera, $l$ being the distance from the sample to the camera: the camera sits 5 cm behind the sample. Best blur here
   about 0.05 mm, not the micrometers of a laboratory micro-CT with a small focal spot.
4. **Few particles.** Even at ESS there are far fewer neutrons than photons from an X-ray tube: about 10 neutrons per
   pixel (27.5 µm × 27.5 µm) and second in the high-resolution setup. Exposures last minutes, a tomography hours of beam.
5. **The detector.** A scintillator containing lithium-6 turns each neutron into a flash of light, filmed by a camera
   through a mirror, out of the beam: an indirect detector, as in many X-ray setups.

Then radiography and tomography work as you know them: $T = I/I_0 = e^{-\Sigma x}$ through a thickness $x$, with
$\Sigma$ the attenuation coefficient in cm⁻¹ (the $\mu$ of the lecture: absorption plus scattering), and a filtered
back-projection of parallel projections over 180°.
""")
fig("odin_beamline.png", "ODIN from the source to the camera (distances of the official McStas model of ODIN).")

md(r"""
## The mission

**Why the water of a meteorite matters.** About 4 billion years ago Mars had rivers and lakes; today its surface is
a frozen desert. Where did the water go? Part escaped to space, but part was taken into the rocks of the crust, bound
in their minerals, where it can still be today. How much water the crust stored, and in which minerals, bears on three
questions: how much water young Mars had at all; whether liquid water stayed long enough somewhere for the planet to be
habitable; and what to look for in the samples that future missions will bring back from Mars, which will have to be
analyzed without being destroyed. Water bound in a mineral also keeps a record of its origin, in the isotopes of its
hydrogen.

**Who asks.** Planetary scientists of the Mars team. The meteorite **NWA 7034** ("Black Beauty") is a piece of the
Martian crust of that time, 4.4 billion years old, and the Martian meteorite richest in water: about 6 000 ppm.
**Where is this water held?** Spread in the whole rock (as if water had soaked it everywhere), or concentrated in some
of the rock fragments (clasts) that make it up? In the second case these clasts carried their water with them: a
reservoir of its own in the budget of the crust, and the grains to pick for a chemical analysis of their hydrogen. A
gram of the meteorite is worth more than a gram of gold: answer **without cutting it**.

**The sample is real.** A piece of 12 × 8 × 2 mm³ was imaged with neutrons at ICON (PSI) and with X-rays at the ESRF
by E. B. Naver, K. W. Nikolajsen *et al.*, *Geophysical Research Letters* (2026), doi:10.1029/2026GL121841 (the
example shown in the lecture). The twin's piece is built from their numbers (size, phases, sizes
and amounts of the clasts, measured attenuations); where the clasts sit is drawn at random.

Below: the piece on the rotation stage of ODIN, cut through its middle (the clasts that hold hydrogen are hidden).
""")

code(r"""
spec = odin.sample_spec(SAMPLE)
smp_out = w.Output()
import sample_library as sl
with into(smp_out):
    sl.draw("odin", spec, hidden=["inclusions"], fig=plt.figure(figsize=(10, 3.6)))
    sl.show()
display(smp_out)
""")

md(r"""
## 1. Take the three images

The instrument is set for you: white beam, 1 cm pinhole. You measure with the **Timepix3 camera**, which records
**each neutron**: where it arrived and when. Watch the detector image fill up, and the histogram of the arrival times
after each pulse (the time of flight: the slow neutrons, of long wavelength, arrive late).
""" + transmission_md("sample out: stage at 500 mm") + r"""
**The measurements to take**, in this order (set the controls, then *Count*):

| Step | Image | Shutter | Sample | Counting time |
|---|---|---|---|---|
| 1 | dark | closed | in | 2 s |
| 2 | open beam | open | out | 2 s |
| 3 | sample | open | in | 2 s |

Two seconds are enough here: some 5 million neutrons reach the camera. A count lasts its counting time, as on the
instrument, plus the time the twin needs to draw these neutrons one by one and write them to the file (10 to 20 s;
on the real instrument the file is written while counting). *Stop* cancels a count: nothing of it is recorded.
""")

code(r"""
st = odin.status()
shut = w.ToggleButtons(options=[("closed", "closed"), ("open", "open")], value=st["shutter"], description="Shutter")
inout = w.ToggleButtons(options=[("in", 0.0), ("out", 0.5)], value=0.0 if abs(st["stage_x"]) < 0.02 else 0.5,
                        description="Sample")
tcount = w.Dropdown(options=[2, 5], value=2, description="Counting time (s)", style={"description_width": "130px"})
title = w.Text(value="", placeholder="dark, open beam, sample", description="Title")
button = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
live = viz.LiveView()
TPX = {}                                      # the last file of each kind: dark, open, sample

def kind():
    return "dark" if shut.value == "closed" else ("open" if inout.value > 0.02 else "sample")

def count(_):
    # runs in a thread (measure_control): the settings are locked, Stop cancels; prints go to ctl.status
    k = kind()
    name = title.value.strip() or {"dark": "dark", "open": "open beam", "sample": "meteorite 0°"}[k]
    try:
        odin.move(choppers="white", pinhole=PINHOLE, diffuser="in", shutter=shut.value, stage_x=inout.value,
                  stage_rot=0.0, sample=SAMPLE)
        live.reset()
        f = odin.count(float(tcount.value), title=name, progress=live.update)
        TPX[k] = f
        live.done(f)
        print(f"Written: {os.path.basename(f)} ({name}, {odin.last_n_counts:,} neutrons). Taken so far: "
              + ", ".join(x for x in ("dark", "open", "sample") if x in TPX) + ".")
    except Cancelled:
        pass
    except Exception as e:
        print("Error:", e)

ctl = mc.Control(odin, button, lock=[shut, inout, tcount, title])
ctl.on_click(count)
display(w.VBox([shut, inout, tcount, title, w.HBox([button, ctl.stop]), ctl.status, live.box]))
""")

code(r"""
q.number("The histogram of the arrival times: a neutron reaches the camera, 60.55 m from the source, **61.2 ms** after "
         "the pulse. Which wavelength does it have (Å)? (λ [Å] = 3956 / v [m/s])", value=4.0, tol=0.1, unit="Å",
         mistakes=[(989, "that is its speed in m/s; then λ = 3956 / v")],
         hints=["v = 60.55 m / 0.0612 s.", "v ≈ 989 m/s, λ = 3956 / 989."],
         explanation="v = 60.55 / 0.0612 = 989 m/s, λ = 3956 / 989 = 4.0 Å. The arrival time is proportional to λ: this "
                     "is how ODIN knows the wavelength of every neutron (here we sum them all: a white-beam radiograph).",
         title="Q3. From the time of flight to the wavelength")
""")

md(r"""
## 2. Data reduction: from the files to the transmission

Your three files hold **events** (one per neutron: its pixel, its pulse, its time of flight), not images.
*Reduce* runs the chain of ESS on them:

1. **read** the events of each file (`scippnexus`, into `scipp` arrays with units and uncertainties);
2. **time of flight to wavelength** for each neutron (`essreduce`, in the ESS imaging package `essimaging`, workflow
   `OdinBraggEdgeWorkflow`, from the chopper settings and distances read in the file);
3. **histogram** the neutrons in 128 × 128 pixels (here all the wavelengths together);
4. **normalize** each run by its **proton charge** (the number of protons that hit the target during the count,
   written in the file: it sets how many neutrons were made) and subtract the dark, scaled to its duration;
5. **divide** by the open beam: $T = (S - D)/(O - D)$, with its uncertainty from the counting noise.

This takes 10 to 30 seconds (some 10 million neutrons, one by one). The rest of the page appears when it is done.
""")

code(r"""
from page_output import gate, open_gate
button_red = w.Button(description="Reduce", button_style="success", icon="cogs", layout=w.Layout(width="auto"))
img_T = live_view.FigureImage()
RED = {}
gate_red = gate("The radiograph and the rest of the page appear once you have reduced your three files.")
XR = (-5.0, 5.0)                       # the x range of both plots: the piece is 8 mm wide

def reduce(_):
    try:
        missing = [x for x in ("dark", "open", "sample") if x not in TPX]
        if missing:
            print("Take first: " + ", ".join(missing) + " (part 1)."); return
        import odin_reduction as reduction
        print("Reducing the three files with the ESS workflow...")
        r = reduction.reduce(TPX["sample"], TPX["open"], TPX["dark"], n_pixels=128)
        T = r["image"].values
        RED["T"] = T
        n = T.shape[0]
        row = int(np.clip(round(@Y1@ / (14.1 / n) + (n - 1) / 2), 0, n - 1))
        with img_T:
            fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw=dict(width_ratios=[1, 1.25]))
            im = a.imshow(T, origin="lower", extent=EXT, cmap="gray", vmin=0.75, vmax=1.05)
            fig.colorbar(im, ax=a, label="transmission T")
            a.plot(XR, [@Y1@, @Y1@], color="tab:orange", lw=1.2)
            a.set(xlabel="x (mm)", ylabel="y (mm)", xlim=XR, title="Radiograph: transmission T (128 × 128 pixels)")
            b.plot(np.linspace(EXT[0], EXT[1], n), T[row], color="tab:orange", lw=0.9)
            b.set(xlabel="x (mm)", ylabel="transmission T", title="Profile along the orange line (y = @Y1@ mm)",
                  ylim=(0.7, 1.1), xlim=XR)
            b.grid(alpha=0.3)
            plt.tight_layout()
        nm = r["normalization"]
        ctl_red.clear()
        open_gate(gate_red)
        print(f"Proton charge: sample {nm['E']['charge_uC'] / 1000:.1f} mC, open beam {nm['O']['charge_uC'] / 1000:.1f} mC "
              f"(the source varies a little from pulse to pulse: that is why each run is normalized by its own charge).")
    except Exception as e:
        print("Error:", e)

ctl_red = mc.Control(odin, button_red, stopped=None)
ctl_red.on_click(reduce)
display(w.VBox([w.HBox([button_red, ctl_red.stop]), ctl_red.status, img_T, gate_red]))
""")

md(r"""
**Reading the radiograph.** About 89 % of the neutrons cross the 2 mm of rock: almost transparent. With 2 s and
pixels of 110 µm, the clasts (0.1–0.4 mm, a few % of contrast) are lost in the noise and the blur; and a radiograph
adds up the whole 2 mm along the beam: a speck can be one grain or several, near the front or the back. Hence the
tomography.
""")

code(r"""
q.number("The rock lets through T ≈ 0.89 of the neutrons over its 2 mm thickness. What is its attenuation coefficient "
         "Σ (cm⁻¹)?", value=0.58, tol=0.06, unit="cm⁻¹",
         mistakes=[(0.058, "right, but per mm: the answer is asked in cm⁻¹"), (0.11, "this is 1 − T, not −ln T / x")],
         hints=["T = exp(−Σ x): Σ = −ln T / x.", "x = 0.2 cm; −ln 0.89 = 0.117."],
         explanation="Σ = −ln 0.89 / 0.2 cm = 0.58 cm⁻¹: the matrix of the meteorite in ODIN's white beam (0.45 cm⁻¹ at "
                     "ICON, whose beam is warmer: these minerals attenuate slow neutrons more).",
         title="Q4. Σ of the rock")
""")
fig("meteorite_tomography.png", "One horizontal slice of the piece (8 mm × 2 mm), seen from above. A radiograph adds "
    "up everything along the beam (left): two clasts one behind the other make one peak. Turning the sample over 180° "
    "(middle) and back-projecting gives the slice back (right). The H-rich clasts, about 0.3 mm, drawn 3 times larger.")

md(r"""
## 3. The tomography

For the tomography ODIN uses the **integrating camera** in its high-resolution setup (512 × 512 pixels of 27.5 µm,
thin scintillator): finer pixels than the Timepix3, and no need for the time of flight. It takes its own dark (300 s)
and open beam (1500 s) first, then turns the sample in steps of 3° over 180° with one image of 300 s at each angle: 60
images, **5 hours of beam** on ODIN (two or three minutes here). For each row of pixels, the projections $-\ln T$ are filtered (ramp)
and back-projected: $\Sigma$ at every point of the slice. For comparison, Naver *et al.* took 1125 images of 4 minutes
at ICON (75 hours), with pixels of 6.2 µm.
""")

code(r"""
button_tomo = w.Button(description="Run the tomography", button_style="primary", icon="sync", layout=w.Layout(width="auto"))
bar = viz.Progress(60, "Images")
REC = {}

def run_tomo(_):
    try:
        odin.move(choppers="white", pinhole=PINHOLE, diffuser="in", stage_rot=0.0, sample=SAMPLE)
        print("The camera's dark and open beam...")
        odin.move(shutter="closed", stage_x=0.0)
        cam_dark = odin.camera(300.0, title="camera dark (tomography)", pixels=PX)
        odin.move(shutter="open", stage_x=0.5)
        cam_open = odin.camera(1500.0, title="camera open beam (tomography)", pixels=PX)
        angles = np.arange(0, 180, 3.0)
        bar.start(len(angles))
        odin.move(shutter="open", stage_x=0.0)
        files = odin.tomography(angles, 300.0, title="tomography", pixels=PX, progress=bar.update)
        print("Filtering and back-projecting...")
        REC["rec"] = tomo.Reconstruction(files, cam_open, cam_dark)
        ctl_tomo.clear()
        print(f"{len(angles)} projections reconstructed: explore the slices below.")
        show_slices()
        open_gate(gate_tomo)
    except Cancelled:
        print("Tomography stopped: no reconstruction.")
    except Exception as err:
        print("Not possible yet:", err)
    finally:
        odin.move(stage_rot=0.0)

gate_tomo = gate("The slices and the rest of the page appear once the tomography is done.")
ctl_tomo = mc.Control(odin, button_tomo, stopped=None)
ctl_tomo.on_click(run_tomo)
display(w.VBox([w.HBox([button_tomo, ctl_tomo.stop]), bar.box, ctl_tomo.status, gate_tomo]))
""")

md(r"""
**Optional, if you are curious:** what your files contain (the raw data of the NeXus files, event by event or image by
image) and how they become a radiograph and a tomography, step by step, with the software used. Click to open; you can
skip it.
""")

code(r"""
analysis_chain.section("odin_camera", odin, title="Optional: the raw data and the analysis chain (click to open)")
""")

md(r"""
## 4. Look inside

Left: a **horizontal slice** at the height $y$ you choose, seen from above ($x$ across, $z$ along the beam at 0°).
Right: a **vertical slice** at the depth $z$. The color is $\Sigma$ in cm⁻¹. The slices follow the sliders (computed on every
second pixel, 55 µm, to be quick). The rings around the rotation axis are the
noise of the open beam, the same in every projection. The largest clasts are @WHERE@: move the cross (+) onto the
brightest spot.
""")

code(r"""
ys = w.FloatSlider(value=@Y1@, min=-6.0, max=6.0, step=0.0275, description="Height y (mm)", continuous_update=True,
                   readout_format=".2f", layout=w.Layout(width="460px"))
zs = w.FloatSlider(value=0.0, min=-1.0, max=1.0, step=0.0275, description="Depth z (mm)", continuous_update=True,
                   readout_format=".2f", layout=w.Layout(width="460px"))
xs = w.FloatSlider(value=0.0, min=-4.0, max=4.0, step=0.0275, description="Point x (mm)", continuous_update=True,
                   readout_format=".2f", layout=w.Layout(width="460px"))
img_sl = live_view.FigureImage()
txt_sl = w.HTML("Run the tomography first.")

CACHE = {}

def slices(r):
    # the slices on every second pixel (55 µm, 4 times faster than all of them), kept while y or z do not change
    m = r.mm[::2]
    key_h, key_v = ("h", r._row(ys.value)), ("v", round(zs.value, 4))
    if key_h not in CACHE:
        X, Z = np.meshgrid(m, m)
        CACHE[key_h] = r._bp([r._row(ys.value)], X.ravel(), Z.ravel()).reshape(len(m), len(m))
    if key_v not in CACHE:
        CACHE[key_v] = r._bp(list(range(0, r.n, 2)), m, np.full(len(m), zs.value))
    return CACHE[key_h], CACHE[key_v]

def show_slices(_=None):
    if "rec" not in REC:
        return
    r = REC["rec"]
    if len(CACHE) > 40:
        CACHE.clear()
    h, v = slices(r)
    with img_sl:
        fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw=dict(width_ratios=[1.6, 1]))
        kw = dict(origin="lower", extent=EXT, cmap="magma", vmin=0, vmax=2.0)
        im = a.imshow(h, **kw)
        a.set(xlim=(-4.6, 4.6), ylim=(-1.6, 1.6), xlabel="x (mm)", ylabel="depth z (mm)",
              title=f"Horizontal slice at y = {ys.value:.2f} mm")
        a.axhline(zs.value, color="w", lw=0.6, ls="--"); a.plot(xs.value, zs.value, "c+", ms=14, mew=1.5)
        b.imshow(v, **kw)
        b.set(xlim=(-4.6, 4.6), ylim=(-6.6, 6.6), xlabel="x (mm)", ylabel="y (mm)",
              title=f"Vertical slice at depth z = {zs.value:.2f} mm")
        b.axhline(ys.value, color="w", lw=0.6, ls="--"); b.plot(xs.value, ys.value, "c+", ms=10, mew=1.5)
        fig.colorbar(im, ax=[a, b], label="Σ (cm⁻¹)", shrink=0.8)
    txt_sl.value = "Cross (+) on a bright spot? Then part 5 measures Σ there."

for s_ in (ys, zs, xs):
    s_.observe(live_view.throttled(show_slices), "value")
display(w.VBox([ys, zs, xs, img_sl, txt_sl]))
show_slices()
""")

md(r"""
## 5. What is in the bright spots?

*Measure Σ* gives the mean $\Sigma$ in a small ball (0.06 mm radius) around the cross, and in the matrix around it
(0.4 to 0.6 mm away). Their **ratio** hardly depends on the spectrum of the beam. Compare with the minerals of
NWA 7034 without hydrogen (Naver *et al.*, Table S1, at 25 meV; matrix measured at ICON: 0.45 cm⁻¹):

| Mineral | Σ (cm⁻¹) | ratio to the matrix |
|---|---|---|
| plagioclase | 0.27 – 0.28 | 0.6 |
| pyroxenes, chlorapatite | 0.34 – 0.38 | 0.8 |
| ilmenite | 0.70 | 1.6 |
| magnetite, maghemite | 0.80 – 0.82 | 1.8 |
""")

code(r"""
button_s = w.Button(description="Measure Σ", button_style="success", icon="crosshairs", layout=w.Layout(width="auto"))
out_s = w.Output()
RES = {}

def measure(_=None):
    with out_s:
        clear_output()
        if "rec" not in REC:
            print("Run the tomography first (part 3)."); return
        r = REC["rec"]
        spot = r.value(xs.value, ys.value, zs.value, 0.06)
        ang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
        ring = [r.value(xs.value + d * np.cos(a), ys.value, float(np.clip(zs.value + d * np.sin(a), -0.85, 0.85)), 0.04)
                for d in (0.4, 0.6) for a in ang]
        mat = float(np.median(ring))
        print(f"spot:   Σ = {spot:.2f} cm⁻¹")
        print(f"matrix: Σ = {mat:.2f} cm⁻¹")
        print(f"ratio spot / matrix = {spot / mat:.1f}")
        if spot / mat < 1.5:
            RES.clear()
            print("\nThe cross is not on a bright spot (the spot hardly differs from the matrix around it). Move it "
                  "onto a bright spot with the three sliders of part 4 (look for yellow-white in the slices), then "
                  "click Measure Σ again.")
        else:
            RES.update(spot=spot, matrix=mat)

button_s.on_click(measure)
display(w.VBox([button_s, out_s]))
""")

md(r"""
The twin's values are higher than the table's: ODIN's white beam is colder (mean wavelength 3.3 Å) than ICON's
(1.8 Å), and these materials attenuate slow neutrons more; ratios change much less. A spot of 0.1–0.3 mm is also
blurred with its surroundings: the value in its middle is lower than the true one.

## 6. How much water?

As Naver *et al.*: all the excess attenuation is due to hydrogen. Without hydrogen the clasts would show
$\Sigma_\text{clast}$ = 0.71 cm⁻¹ in ODIN's beam (0.57 cm⁻¹ at ICON), and liquid water 5.4 cm⁻¹. The fraction of the
volume that water would fill is $f = (\Sigma_\text{spot} - \Sigma_\text{clast}) / \Sigma_\text{water}$, and the water by
mass $f \times 1.0 / 3.0$ (density of the region about 3.0 g/cm³).
""")

code(r"""
button_w = w.Button(description="Water in the spot", button_style="success", icon="tint", layout=w.Layout(width="auto"))
out_w = w.Output()
SIG_CLAST, SIG_WATER, RHO = 0.71, 5.4, 3.0

def water(_=None):
    with out_w:
        clear_output()
        if "spot" not in RES:
            print("Measure Σ in a bright spot first (part 5)."); return
        f = (RES["spot"] - SIG_CLAST) / SIG_WATER
        print(f"f = ({RES['spot']:.2f} − {SIG_CLAST}) / {SIG_WATER} = {f:.2f}  ->  water by mass = {100 * f / RHO:.0f} %")
        if f <= 0:
            print("No excess attenuation here: is the cross on a bright spot?")

button_w.on_click(water)
display(w.VBox([button_w, out_w]))
""")



md(r"""
**Limits of the twin.** The piece is a model built from the published numbers (sizes, amounts and attenuations of
the clasts); where the clasts sit is drawn at random. The minerals are mixed at the scale of each region (no
crystal). The camera is modeled by its mean signal, its noise and its blur.

## 7. Your results, your comment

Your score on the questions, then a few words on the session (what was clear, what was not, what you would change)
and *Submit*: it helps us improve it.
""")

code(r"""
q.report()
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/meteorite_imaging", "class", quiz=q, title="ODIN in 30 minutes: a Martian meteorite")
""")

QS = {
    'water': r'''
q.number("1 mm of water in the beam, with neutrons of 1.8 Å: Σ = 3.6 cm⁻¹ (mostly the scattering by hydrogen). "
         "Which fraction of the neutrons does it remove, 1 − T (%)? (For comparison after you answer: X-rays of "
         "60 keV see μ = 0.21 cm⁻¹ for water.)",
         value=30.4, tol=1.5, unit="%",
         mistakes=[(2.0, "that is the X-ray value (μ = 0.21 cm⁻¹); the question is about neutrons"),
                   (36, "3.6 cm⁻¹ × 0.1 cm = 0.36 is −ln T, not 1 − T: T = e^(−0.36)")],
         hints=["T = exp(−Σ d), with d = 0.1 cm.", "1 − exp(−0.36)."],
         explanation="1 − e^(−0.36) = 30 % with neutrons, 1 − e^(−0.021) = 2 % with X-rays. And 1 mm of iron: neutrons "
                     "11 % (Σ = 1.2 cm⁻¹), X-rays of 60 keV 61 % (μ = 9.5 cm⁻¹). The contrasts are reversed.",
         title="Q1. Water, for neutrons and X-rays")
''',
    'where': r'''
q.choice("Where is the hydrogen of the piece?",
         ["In small bright regions (0.1–0.4 mm) grouped in clusters, not spread evenly.",
          "Evenly in the whole piece.",
          "Only at the surface.",
          "In the large dark regions."],
         answer=0, why={1: "The matrix is uniform, but look at the bright spots.",
                        2: "The bright spots are inside, at all depths.",
                        3: "Dark means a small Σ: little attenuation (feldspar)."},
         explanation="Naver et al. found the H-rich phases in localised macroscopic clusters, 0.4 % of the volume: a new "
                     "kind of water reservoir in the Martian crust.", hints=["Move the height slider through the piece."],
         title="Q2. Where?")
''',
    'element': r'''
q.choice("Which material can attenuate **3 to 4 times** more than the matrix?",
         ["Only a hydrogen-bearing one: no anhydrous mineral of the table reaches twice the matrix.",
          "Magnetite: it is the densest.",
          "Feldspar.",
          "Any mineral, if the grain is large enough."],
         answer=0, why={1: "Magnetite is at 1.8 times the matrix, not 3 or 4.",
                        2: "Feldspar attenuates less than the matrix (0.6 times).",
                        3: "Σ does not depend on the size of the grain: it is a property of the material."},
         explanation="The argument of Naver et al.: the H-rich regions attenuate 1.9 cm⁻¹, their minerals without hydrogen "
                     "0.61 cm⁻¹; only hydrogen explains the difference.",
         hints=["Compare your ratio of part 5 with the last column of the table."], title="Q3. Which element?")
''',
    'howmuch': r'''
q.number("The water by mass in the brightest spot you found (part 6, %):", value=8, tol=6, unit="%",
         hints=["Part 6 computes it from your Σ of part 5."],
         explanation="The model holds about 14 % (Naver et al.: up to 15 wt% OH). The blur lowers Σ in the middle of a "
                     "small region, so the estimate is lower: a few % to about 12 %.", title="Q4. How much water?")
''',
    'magnif': r'''
q.choice("A laboratory micro-CT magnifies by bringing the sample close to a small focal spot (a cone beam). Why does "
         "ODIN put the camera **5 cm** behind the sample instead, without magnification?",
         ["The neutron source seen by the sample is the pinhole, 1 to 4 cm wide: a magnifying geometry would multiply "
          "its blur (l · D / L). ODIN keeps the camera close and the beam almost parallel.",
          "Neutrons have no charge, so they cannot be magnified.",
          "There is no room behind the sample on ODIN.",
          "The camera pixels are small enough: magnification would not help."],
         answer=0, why={1: "Micro-CT magnification is geometric (cone beam), not by lenses: neutrons would follow the same "
                           "geometry. The problem is the size of the source.",
                        2: "Room is not the reason: the blur is.",
                        3: "With the camera 1 m away, the 1 cm pinhole would blur by 1 mm."},
         explanation="Geometric blur = l · D / L: with D = 1 cm and L = 10.5 m, every cm of l adds 10 µm of blur. The "
                     "camera stays close, and the parallel-beam reconstruction (180°) applies.",
         title="Q5. No magnification")
''',
    'report': r'''
q.choice("**Your report to the Mars team.**",
         ["The water is concentrated in small clasts (0.1–0.4 mm) grouped in clusters; their attenuation can only be "
          "explained by hydrogen, about 10 % water by mass; the tomography gives their positions for sampling.",
          "The water is spread evenly in the meteorite.",
          "There is no water: the bright spots are magnetite.",
          "Neutrons cannot answer: X-rays are needed."],
         answer=0, why={1: "The bright spots are local.", 2: "Magnetite reaches 1.8 times the matrix, not 4.",
                        3: "Neutrons are the right probe for hydrogen; X-rays see the Fe-Ti oxides."},
         explanation="Your conclusion is that of Naver et al. (2026): a new macroscopic crustal water reservoir on early "
                     "Mars, found without cutting the meteorite.", hints=["Your answers on where the hydrogen is, which element, and how much water."], title="Q6. The report")
''',
}


# the questions along the page, each right after the step it checks: (anchor in a code or figure cell, questions)
PLACE = [("ODIN from the source to the camera", ["water", "magnif"]), ("display(w.VBox([ys, zs, xs, img_sl, txt_sl]))", ["where"]),
         ("display(w.VBox([button_s, out_s]))", ["element"]), ("display(w.VBox([button_w, out_w]))", ["howmuch", "report"])]
for anchor, names_ in reversed(PLACE):
    k = next(i for i, c in enumerate(cells) if anchor in c.source)
    for n_ in reversed(names_):
        cells.insert(k + 1, nbf.v4.new_code_cell(QS[n_].strip()))
# number the questions in the order of the page
qn = iter(range(1, 100))
for c in cells:
    if c.cell_type == "code":
        c.source = re.sub(r'title="Q\d+\. ', lambda m: f'title="Q{next(qn)}. ', c.source)

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_meteorite_class.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
