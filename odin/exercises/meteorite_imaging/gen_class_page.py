"""Generates ODIN_meteorite_class.ipynb: a 30-minute session for a class (first use: DTU, MSc course "Advanced X-ray
imaging", 23 November 2026, after a lecture on neutron imaging). ODIN in short for X-ray imagers, then the meteorite
NWA 7034 in a condensed form: one high-resolution radiograph, a tomography, the hydrogen-rich clasts, how much water.
Not an exercise of the catalogue of the app: the start page of the online version shows it on top.

    python gen_class_page.py
"""
import os
import sys

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
| 5–10 min | take the three images, look at the radiograph (parts 1–2) |
| 10–20 min | run the tomography, find the bright clasts in the slices (parts 3–4) |
| 20–27 min | measure Σ, estimate the water, answer the questions (parts 5–6) |
| 27–30 min | your comment, and *Submit* (part 8) |
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

1. **The contrast is the other way round.** Neutrons interact with the **nuclei**, not with the electrons.
   **Hydrogen** removes neutrons more than any other element (it scatters them strongly), and lithium, boron, cadmium,
   gadolinium absorb them; but iron, aluminum, silicon, lead let most of them through. A neutron image shows the
   water inside a metal or a rock, where X-rays see the heavy elements.
2. **A pulsed source and the time of flight.** At ESS, protons hit a tungsten target 14 times per second; each pulse
   (2.86 ms) makes neutrons, slowed down by a moderator. ODIN is 60 m long: the arrival time of a neutron at the camera
   gives its speed, so its wavelength. Today you use the **white beam**: all the wavelengths together, like a
   polychromatic X-ray beam (and with a similar "beam hardening").
3. **No lens, no magnification.** The beam is shaped by a **pinhole** of D = 1 to 4 cm, L = 10.5 m before the sample:
   an almost parallel beam (L/D up to 1050). Each point of the sample becomes a spot of size $l \cdot D / L$ on the
   camera, $l$ being the distance from the sample to the camera: the camera sits 5 cm behind the sample. Best blur here
   about 0.05 mm, not the micrometers of a laboratory micro-CT with a small focal spot.
4. **Few particles.** Even at ESS there are far fewer neutrons than photons from an X-ray tube: about 10 neutrons per
   pixel and second in the high-resolution setup. Exposures last minutes, a tomography hours of beam.
5. **The detector.** A scintillator containing lithium-6 turns each neutron into a flash of light, filmed by a camera
   through a mirror, out of the beam: an indirect detector, as in many X-ray setups.

Then radiography and tomography work as you know them: $T = I/I_0 = e^{-\Sigma x}$ through a thickness $x$, with
$\Sigma$ the attenuation coefficient in cm⁻¹ (the $\mu$ of the lecture: absorption plus scattering), and a filtered
back-projection of parallel projections over 180°.
""")
fig("odin_beamline.png", "ODIN from the source to the camera (distances of the official McStas model of ODIN).")

md(r"""
## The mission

**Who asks.** Planetary scientists studying the **water of early Mars**. Part of it was taken into the rocks of the
crust, bound in their minerals. The meteorite **NWA 7034** ("Black Beauty"), a piece of that crust 4.4 billion years
old, is the Martian meteorite richest in water: about 6 000 ppm. **Where is this water held?** Spread in the whole
rock, or concentrated in some of the rock fragments (clasts) that make it up, a reservoir of its own? A gram is worth
more than a gram of gold: answer **without cutting it**.

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

The instrument is set for you: white beam, 1 cm pinhole, high-resolution camera (512 × 512 pixels of 27.5 µm, thin
scintillator).
""" + transmission_md("sample out: stage at 500 mm") + r"""
One click takes the three, with the exposures used on ODIN for such a sample: **dark 300 s, open beam 1500 s,
sample 300 s** (the twin computes them in a few seconds). The open beam is long on purpose: it divides every
projection, so its own noise would be printed in all of them, as rings in the tomography.
""")

code(r"""
button = w.Button(description="Take the three images", button_style="primary", icon="camera", layout=w.Layout(width="auto"))
img_T = live_view.FigureImage()
FILES = {}

def show_T():
    T = tomo.transmission(FILES["sample"], FILES["open"], FILES["dark"])
    n = T.shape[0]
    row = int(np.clip(round(@Y1@ / tomo.pixel_mm(n) + (n - 1) / 2), 0, n - 1))
    with img_T:
        fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw=dict(width_ratios=[1, 1.25]))
        im = a.imshow(T, origin="lower", extent=EXT, cmap="gray", vmin=0.8, vmax=1.0)
        fig.colorbar(im, ax=a, label="transmission T")
        a.axhline(@Y1@, color="tab:orange", lw=1)
        a.set(xlabel="x (mm)", ylabel="y (mm)", title="Radiograph: transmission T")
        b.plot(np.linspace(EXT[0], EXT[1], n), T[row], color="tab:orange", lw=0.8)
        b.set(xlabel="x (mm)", ylabel="transmission T", title=f"Profile along the orange line (y = @Y1@ mm)",
              ylim=(0.75, 1.05), xlim=(-5, 5))
        b.grid(alpha=0.3)
        plt.tight_layout()

def take(_):
    # runs in a thread (measure_control): Stop cancels; prints go to ctl.status
    try:
        odin.move(choppers="white", pinhole=PINHOLE, diffuser="in", stage_rot=0.0, sample=SAMPLE)
        for kind, shutter, x, t, title in (("dark", "closed", 0.0, 300, "dark"), ("open", "open", 0.5, 1500, "open beam"),
                                           ("sample", "open", 0.0, 300, "meteorite 0°")):
            odin.move(shutter=shutter, stage_x=x)
            print(f"{title}: {t} s ...")
            FILES[kind] = odin.camera(float(t), title=title, pixels=PX)
        odin.move(shutter="open", stage_x=0.0)
        ctl.clear()
        print("Written: " + ", ".join(os.path.basename(FILES[k]) for k in ("dark", "open", "sample")) +
              ". The radiograph is below.")
        show_T()
    except Cancelled:
        pass
    except Exception as e:
        print("Error:", e)

ctl = mc.Control(odin, button)
ctl.on_click(take)
display(w.VBox([w.HBox([button, ctl.stop]), ctl.status, img_T]))
""")

md(r"""
## 2. The radiograph

About 89 % of the neutrons cross the 2 mm of rock: almost transparent. Small darker and brighter specks appear, but a
radiograph adds up the whole 2 mm along the beam: a speck can be one grain or several, near the front or the back.
Hence the tomography.
""")
fig("meteorite_tomography.png", "One horizontal slice of the piece (8 mm × 2 mm), seen from above. A radiograph adds "
    "up everything along the beam (left): two clasts one behind the other make one peak. Turning the sample over 180° "
    "(middle) and back-projecting gives the slice back (right). The H-rich clasts, about 0.3 mm, drawn 3 times larger.")

md(r"""
## 3. The tomography

*Run the tomography* turns the sample in steps of 3° over 180° and takes one image of 300 s at each angle: 60 images,
**5 hours of beam** on ODIN (a few minutes here). For each row of pixels, the projections $-\ln T$ are filtered (ramp)
and back-projected: $\Sigma$ at every point of the slice. For comparison, Naver *et al.* took 1125 images of 4 minutes
at ICON (75 hours), with pixels of 6.2 µm.
""")

code(r"""
button_tomo = w.Button(description="Run the tomography", button_style="primary", icon="sync", layout=w.Layout(width="auto"))
bar = viz.Progress(60, "Images")
REC = {}

def run_tomo(_):
    try:
        if not FILES:
            print("Take the three images first (part 1)."); return
        angles = np.arange(0, 180, 3.0)
        bar.start(len(angles))
        odin.move(choppers="white", pinhole=PINHOLE, diffuser="in", shutter="open", stage_x=0.0, sample=SAMPLE)
        files = odin.tomography(angles, 300.0, title="tomography", pixels=PX, progress=bar.update)
        print("Filtering and back-projecting...")
        REC["rec"] = tomo.Reconstruction(files, FILES["open"], FILES["dark"])
        ctl_tomo.clear()
        print(f"{len(angles)} projections reconstructed: explore the slices below.")
        show_slices()
    except Cancelled:
        print("Tomography stopped: no reconstruction.")
    except Exception as err:
        print("Not possible yet:", err)
    finally:
        odin.move(stage_rot=0.0)

ctl_tomo = mc.Control(odin, button_tomo, stopped=None)
ctl_tomo.on_click(run_tomo)
display(w.VBox([w.HBox([button_tomo, ctl_tomo.stop]), bar.box, ctl_tomo.status]))
""")

md(r"""
## 4. Look inside

Left: a **horizontal slice** at the height $y$ you choose, seen from above ($x$ across, $z$ along the beam at 0°).
Right: a **vertical slice** at the depth $z$. The color is $\Sigma$ in cm⁻¹. The rings around the rotation axis are the
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

def show_slices(_=None):
    if "rec" not in REC:
        return
    r = REC["rec"]
    h, v = r.horizontal(ys.value), r.vertical(zs.value)
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
        RES.update(spot=spot, matrix=mat)
        print(f"spot:   Σ = {spot:.2f} cm⁻¹")
        print(f"matrix: Σ = {mat:.2f} cm⁻¹")
        print(f"ratio spot / matrix = {spot / mat:.1f}")

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
## 7. Questions: neutrons and X-rays

Six questions, about 5 minutes. A wrong answer is explained; after a try you can show the answer.
""")

code(r"""
q.number("1 mm of water in the beam. With neutrons of 1.8 Å, Σ = 3.6 cm⁻¹ (hydrogen); with X-rays of 60 keV, "
         "μ = 0.21 cm⁻¹. Which fraction of the **neutrons** does it remove, 1 − T (%)?",
         value=30.4, tol=1.5, unit="%",
         mistakes=[(2.0, "that is the X-ray value (μ = 0.21 cm⁻¹); the question is about neutrons"),
                   (36, "3.6 cm⁻¹ × 0.1 cm = 0.36 is −ln T, not 1 − T: T = e^(−0.36)")],
         hints=["T = exp(−Σ d), with d = 0.1 cm.", "1 − exp(−0.36)."],
         explanation="1 − e^(−0.36) = 30 % with neutrons, 1 − e^(−0.021) = 2 % with X-rays. And 1 mm of iron: neutrons "
                     "11 % (Σ = 1.2 cm⁻¹), X-rays of 60 keV 61 % (μ = 9.5 cm⁻¹). The contrasts are reversed.",
         title="Q1. Water, for neutrons and X-rays")
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
q.number("The water by mass in the brightest spot you found (part 6, %):", value=8, tol=6, unit="%",
         hints=["Part 6 computes it from your Σ of part 5."],
         explanation="The model holds about 14 % (Naver et al.: up to 15 wt% OH). The blur lowers Σ in the middle of a "
                     "small region, so the estimate is lower: a few % to about 12 %.", title="Q4. How much water?")
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
q.choice("**Your report to the Mars team.**",
         ["The water is concentrated in small clasts (0.1–0.4 mm) grouped in clusters; their attenuation can only be "
          "explained by hydrogen, about 10 % water by mass; the tomography gives their positions for sampling.",
          "The water is spread evenly in the meteorite.",
          "There is no water: the bright spots are magnetite.",
          "Neutrons cannot answer: X-rays are needed."],
         answer=0, why={1: "The bright spots are local.", 2: "Magnetite reaches 1.8 times the matrix, not 4.",
                        3: "Neutrons are the right probe for hydrogen; X-rays see the Fe-Ti oxides."},
         explanation="Your conclusion is that of Naver et al. (2026): a new macroscopic crustal water reservoir on early "
                     "Mars, found without cutting the meteorite.", hints=["Q2, Q3 and Q4 together."], title="Q6. The report")
""")

md(r"""
Curious about what your files contain and how the images become a tomography? Open the section below (optional).
""")

code(r"""
analysis_chain.section("odin_camera", odin)
""")

md(r"""
**Limits of the twin.** The piece is a model built from the published numbers (sizes, amounts and attenuations of
the clasts); where the clasts sit is drawn at random. The minerals are mixed at the scale of each region (no
crystal). The camera is modeled by its mean signal, its noise and its blur.

## 8. Your results, your comment

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

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_meteorite_class.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
