"""Generates ODIN_meteorite_class.ipynb: a session of about 45 minutes for a class (first use: DTU, MSc course "Advanced X-ray
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

import sample_library as _sl  # noqa: E402
_Y1 = _sl.body_center(_sl.load("odin")["meteorite_nwa7034"], "H-rich region 1")[1]   # the H-rich core of the largest clast
Y1S = f"{round(_Y1 / 0.0275) * 0.0275:.2f}"
WHERE = "near the top" if _Y1 > 2 else ("in the lower part" if _Y1 < -2 else "around the middle")
_sub = lambda s: s.replace("@Y1@", Y1S).replace("@WHERE@", WHERE)

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(_sub(s).strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(_sub(s).strip()))
fig = lambda name, caption: cells.append(figure_cell(name, caption))

md(r"""
# ODIN: what is hidden inside a Martian meteorite?

You know X-ray imaging well. Today you image with **neutrons**, on the digital twin of **ODIN**, the imaging
instrument of the European Spallation Source (ESS). The twin simulates the real instrument and writes its data in the
formats of ESS. Everything happens in this page: no code to write.

**What you will learn**

- why neutrons and X-rays see different things in the same sample;
- how ODIN takes an image: a pulsed source, a pinhole, a camera very close to the sample;
- the whole chain of a measurement: raw files, data reduction, radiograph, tomography;
- how to use an attenuation coefficient to find out what a hidden region is made of.

**The steps, one after the other**

1. Read *ODIN for X-ray imagers* and the mission.
2. Take three images and reduce them: a radiograph (parts 1–2).
3. Run a tomography and find the bright spots inside the rock (parts 3–4).
4. Measure Σ in a bright spot and estimate its water (parts 5–6).
5. Write a comment and click ***Submit*** (part 7).

Each step unlocks the next one. Short questions check each step: answer, then *Check*. A wrong answer is explained;
after a try you can show the answer.

**Two quantities used everywhere in this page**

- The **transmission** $T = I / I_0$: the fraction of the neutrons that cross the sample (1 = nothing removed).
- The **attenuation coefficient** $\Sigma$, in cm⁻¹: how strongly a material removes neutrons, by absorption and by
  scattering. It is the $\mu$ of X-ray imaging. Through a thickness $x$: $T = e^{-\Sigma x}$. Each material has its
  own $\Sigma$, so measuring $\Sigma$ tells you what a region is made of.
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
odin.move(sample=SAMPLE, detector_distance=0.006)   # the cameras 6 mm from the rotation axis (room to turn)
EXT = tomo.extent()
PX, PINHOLE = 512, 0.01                      # the high-resolution setup: 512 x 512 pixels of 27.5 µm
PINHOLE_TOMO, T_TOMO = 0.03, 30.0            # tomography: 3 cm pinhole (blur 17 µm at 6 mm), 30 s per image
""")

md(r"""
## ODIN for X-ray imagers, in five points

The lecture showed the principles (Beer-Lambert, the pinhole camera, the contrasts); here is what they mean on ODIN.
First the whole instrument, 60 m long:
""")
fig("odin_beamline_line.png", "ODIN from the source to the camera (distances of the official McStas model of ODIN).")

md(r"""
**1. Compared with X-rays, the contrast is different.** X-rays interact with the electrons, so the heavy elements
stand out; neutrons interact with the **nuclei**. **Hydrogen** removes neutrons more than any other element (it
scatters them strongly), and lithium, boron, cadmium, gadolinium absorb them; but iron, aluminum, silicon, lead let
most of them through. A neutron image shows the water inside a metal or a rock, where X-rays see the heavy elements.
""")
fig("contrast_xray_neutron.png", "The attenuation coefficient of a few materials: X-rays of 100 keV (NIST) and neutrons "
    "of 1.8 Å (NCrystal, absorption plus scattering). Water is almost transparent to the X-rays and dark for the "
    "neutrons; lead is the opposite.")

md(r"""
**2. A pulsed source and the time of flight.** At ESS, protons hit a tungsten target 14 times per second. Each pulse
makes neutrons, slowed down by a moderator. ODIN is 60 m long, so the arrival time of a neutron at the camera gives
its speed, and so its wavelength.
""")
fig("odin_tof.png", "Distance against time for neutrons of one pulse: the slow ones (long wavelength) arrive later. "
    "The arrival time at the camera gives the wavelength.")

md(r"""
Today you use the **white beam**: no chopper selects the neutrons, all the wavelengths arrive together, like a
polychromatic X-ray beam. The images add up all the neutrons, whatever their wavelength.

*To use the wavelength* (other exercises, e.g. Bragg edges), there is a catch. The next pulse comes 71 ms later, and
neutrons slower than 4.7 Å need more than 71 ms to reach the camera: they mix with the fast neutrons of the next
pulse. ODIN's choppers then let **only one pulse in two** through, which gives the slow neutrons 143 ms. In white beam
this does not matter, since we do not sort the neutrons.
""")

md(r"""
**3. No lens, no magnification.** The **magnification** is the size of the image on the detector divided by the size
of the object. In a lab micro-CT, the X-rays leave a focal spot of a few µm and spread out (a cone beam). An object
close to the source casts a larger shadow on a far detector: the magnification is often 10 or more.

Neutrons have no small focal spot. On ODIN the beam comes through a **pinhole** of diameter D (1 to 4 cm), at
L = 10.5 m before the sample: an almost parallel beam. The image on the scintillator screen has the size of the object (no lens can bend neutrons into an
enlarged image; the lens of the camera only films the light of the screen), so the resolution is set by the camera pixel (27.5 µm here) and by the blur.

Each point of the sample becomes a spot of size $l \cdot D / L$ on the camera, $l$ being the distance from the sample
to the camera. So the camera is put **as close as possible**: 6 mm from the rotation axis. Then the blur stays below
the pixel, even with a wide pinhole that lets more neutrons through.
""")
fig("odin_pinhole.png", "The pinhole camera: a point of the sample sees the whole pinhole, so it becomes a spot of "
    "size l·D/L on the camera.")

md(r"""
**4. Few particles.** Even at ESS there are far fewer neutrons than photons from an X-ray tube. A pixel of the camera
receives about 55 neutrons per second with the 3 cm pinhole. An image of a rock takes tens of seconds; a tomography
takes about half an hour of beam.

**5. The detector.** A scintillator containing lithium-6 turns each neutron into a flash of light, filmed by a camera
through a mirror, out of the beam: an indirect detector, as in many X-ray setups.
""")
fig("odin_detector_6mm.png", "Side view of the detection: the scintillator glows where a neutron is absorbed; a mirror "
    "sends the light to the camera, out of the beam.")

md(r"""
Then radiography and tomography work as you know them: $T = e^{-\Sigma x}$ in each pixel, and a filtered
back-projection of parallel projections over 180°.
""")

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

Two seconds are enough: some 5 million neutrons reach the camera. A count takes 10 to 25 s here: the twin draws the
neutrons one by one and writes each of them to the file. *Stop* cancels a count: nothing of it is recorded.

**The power of the source.** ESS starts at **2 MW** and is designed for **5 MW**. The power sets the number of
protons per pulse (71 µC at 2 MW), and the number of neutrons is proportional to it. Try another power: more neutrons
in the same time, so less noise. The reduction (part 2) divides each file by its own proton charge, so files taken at
different powers can be combined. At 5 MW the twin warns you: about 6 million neutrons per second reach the camera, more
than a real Timepix3 can record without losses. On the instrument you would then close the pinhole a little.

**See a measurement again.** The menu *Show again* lists your files: choose one to see its image and its arrival
times again, without measuring again.
""")

code(r"""
st = odin.status()
shut = w.ToggleButtons(options=[("closed", "closed"), ("open", "open")], value=st["shutter"], description="Shutter")
inout = w.ToggleButtons(options=[("in", 0.0), ("out", 0.5)], value=0.0 if abs(st["stage_x"]) < 0.02 else 0.5,
                        description="Sample")
tcount = w.Dropdown(options=[2, 5], value=2, description="Counting time (s)", style={"description_width": "130px"})
import source_power                          # the power of the source (fixed by the teacher, or chosen here)
power = source_power.control(odin)
title = w.Text(value="", placeholder="dark, open beam, sample", description="Title")
button = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
live = viz.LiveView()
TPX = {}                                      # the last file of each kind: dark, open, sample
TAKEN = []                                    # every file taken: (label, path), for "Show again"
again = w.Dropdown(options=[("(no file yet)", "")], value="", description="Show again",
                   style={"description_width": "130px"}, layout=w.Layout(width="460px"))

def kind():
    return "dark" if shut.value == "closed" else ("open" if inout.value > 0.02 else "sample")

def count(_):
    # runs in a thread (measure_control): the settings are locked, Stop cancels; prints go to ctl.status
    k = kind()
    name = title.value.strip() or {"dark": "dark", "open": "open beam", "sample": "meteorite 0°"}[k]
    try:
        odin.power_mw = float(power.value)
        odin.move(choppers="white", pinhole=PINHOLE, diffuser="in", shutter=shut.value, stage_x=inout.value,
                  stage_rot=0.0, sample=SAMPLE)
        live.reset()
        f = odin.count(float(tcount.value), title=name, progress=live.update)
        TPX[k] = f
        live.done(f)
        TAKEN.append((f"{os.path.basename(f)}: {name}, {tcount.value} s at {odin.power_mw:g} MW", f))
        again.options = [("(choose a file)", "")] + TAKEN
        print(f"Written: {os.path.basename(f)} ({name}, {odin.last_n_counts:,} neutrons). Taken so far: "
              + ", ".join(x for x in ("dark", "open", "sample") if x in TPX) + ".")
        import odin_reduction
        odin_reduction.prepare(f, n_pixels=128)       # its reduction starts now, in the background (part 2)
    except Cancelled:
        pass
    except Exception as e:
        print("Error:", e)

def show_again(ch):
    if ch["new"]:
        live.done(ch["new"])
        live.status.value = f"Shown again: {os.path.basename(ch['new'])}  (Play or the slider: replay the count)"

again.observe(show_again, names="value")
ctl = mc.Control(odin, button, lock=[shut, inout, tcount, title, again] + source_power.lockable(power))
ctl.on_click(count)
display(w.VBox([shut, inout, tcount, power, title, w.HBox([button, ctl.stop]), ctl.status, again, live.box]))
""")

code(r"""
q.number("The histogram of the arrival times: a neutron reaches the camera, about 60.5 m from the source, **61.2 ms** after "
         "the pulse. Which wavelength does it have (Å)? (λ [Å] = 3956 / v [m/s])", value=4.0, tol=0.1, unit="Å",
         mistakes=[(989, "that is its speed in m/s; then λ = 3956 / v"),
                   (64.6, "3956 divided by the time: first compute the speed, v = distance / time (in m/s)")],
         hints=["v = 60.5 m / 0.0612 s.", "v ≈ 989 m/s, λ = 3956 / 989."],
         explanation="v = 60.5 / 0.0612 = 989 m/s, λ = 3956 / 989 = 4.0 Å. The arrival time is proportional to λ: this "
                     "is how ODIN knows the wavelength of every neutron (here we sum them all: a white-beam radiograph).",
         title="Q3. From the time of flight to the wavelength")
""")

md(r"""
## 2. Data reduction: from the files to the transmission

Your three files hold **events** (one per neutron: its pixel, its pulse, its time of flight), not images.
*Reduce* processes them with the data-reduction software of ESS (the open-source Python packages that will reduce
the real data of ODIN), in five steps:

1. **read** the events of each file (`scippnexus`, into `scipp` arrays with units and uncertainties);
2. **time of flight to wavelength** for each neutron (`essreduce`, in the ESS imaging package `essimaging`, workflow
   `OdinBraggEdgeWorkflow`, from the chopper settings and distances read in the file);
3. **histogram** the neutrons in 128 × 128 pixels (here all the wavelengths together);
4. **normalize** each run by its **proton charge** (the number of protons that hit the target during the count,
   written in the file: it sets how many neutrons were made) and subtract the dark, scaled to its duration;
5. **divide** by the open beam: $T = (S - D)/(O - D)$, with its uncertainty from the counting noise.

Reading some 10 million neutrons one by one takes time, so, as the live reduction of ESS does during a measurement,
each file started to be reduced in the background as soon as it was written: *Reduce* then takes a few seconds (up
to half a minute if you click right after your last count). The rest of the page appears when it is done.
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
**Reading the radiograph.** About 90 % of the neutrons cross the 2 mm of rock: almost transparent. With 2 s and
pixels of 110 µm, the clasts (0.1–0.4 mm, a few % of contrast) are lost in the noise and the blur; and a radiograph
adds up the whole 2 mm along the beam: a speck can be one grain or several, near the front or the back. Hence the
tomography.
""")

code(r"""
q.number("The rock lets through T ≈ 0.90 of the neutrons over its 2 mm thickness. What is its attenuation coefficient "
         "Σ (cm⁻¹)?", value=0.53, tol=0.05, unit="cm⁻¹",
         mistakes=[(0.053, "right, but per mm: the answer is asked in cm⁻¹"), (0.10, "this is 1 − T, not −ln T / x")],
         hints=["T = exp(−Σ x): Σ = −ln T / x.", "x = 0.2 cm; −ln 0.90 = 0.105."],
         explanation="Σ = −ln 0.90 / 0.2 cm = 0.53 cm⁻¹: the matrix of the meteorite in ODIN's white beam (Naver et al.: "
                     "0.45 cm⁻¹, taken by the twin at 1.8 Å; the neutrons counted on ODIN have a mean wavelength of "
                     "3.2 Å, and these minerals attenuate slower neutrons more).",
         title="Q4. Σ of the rock")
""")
fig("meteorite_tomography.png", "One horizontal slice of the piece (8 mm × 2 mm), seen from above. A radiograph adds "
    "up everything along the beam (left): two clasts one behind the other make one peak. Turning the sample over 180° "
    "(middle) and back-projecting gives the slice back (right). The H-rich clasts, about 0.3 mm, drawn 3 times larger.")

md(r"""
## 3. The tomography

For the tomography ODIN uses another camera, the **integrating camera**: finer pixels (27.5 µm) than the Timepix3,
but no time of flight, which we do not need here. The pinhole is opened to 3 cm: 6 times more neutrons (not 9: the beam is brightest at the center of the hole), and the blur
stays below the pixel.

The camera first takes its own dark and open beam. Then it turns the sample over 180°, in steps of 3°, with one image
of 30 s at each angle: 60 images, **half an hour of beam** on ODIN. For each row of pixels, the projections $-\ln T$
are filtered and back-projected: this gives $\Sigma$ at every point of the slice. (Naver *et al.* took 1125 images at
ICON: 75 hours of beam.)

**While it runs (about 2 minutes here)**, read the guide below: it tells you what to do with the slices. You can also
open the optional section on the raw data.

**Guide to the slices (part 4).** You will get two slices through the rock, colored by $\Sigma$:
- left, a **horizontal slice** at a height $y$, seen from above;
- right, a **vertical slice** at a depth $z$.

Three sliders move the slices and a cross (+). The matrix of the rock is purple. **Look for small yellow-white spots**:
regions that attenuate much more than the matrix. The largest ones are @WHERE@. Put the cross on the brightest spot:
part 5 measures $\Sigma$ there.
""")

md(r"""
**Optional, if you are curious:** what your files contain (the raw data of the NeXus files, event by event or image by
image) and how they become a radiograph and a tomography, step by step, with the software used. Click to open; you can
skip it.
""")

code(r"""
analysis_chain.section("odin_camera", odin, title="Optional: the raw data and the analysis chain (click to open)")
""")

code(r"""
button_tomo = w.Button(description="Run the tomography", button_style="primary", icon="sync", layout=w.Layout(width="auto"))
bar = viz.Progress(60, "Images")
REC = {}
# while it runs: the last projection (transmission) and the sinogram of the orange row filling up, angle by angle;
# small images made directly from the arrays (a few ms each: the simulation is not slowed down)
proj_img = w.Image(format="png", layout=w.Layout(width="330px"))
sino_img = w.Image(format="png", layout=w.Layout(width="330px"))
proj_txt = w.HTML()
tomo_view = w.VBox([proj_txt, w.HBox([proj_img, sino_img], layout=w.Layout(gap="24px"))],
                   layout=w.Layout(display="none"))

def _png(a, lo, hi, size=None):
    import io
    from PIL import Image
    u8 = (np.clip((np.nan_to_num(a) - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(u8[::-1])                                       # row 0 at the bottom
    if size:
        im = im.resize(size, Image.NEAREST)
    b = io.BytesIO(); im.save(b, format="PNG", compress_level=1)
    return b.getvalue()

def run_tomo(_):
    try:
        odin.move(choppers="white", pinhole=PINHOLE_TOMO, diffuser="in", stage_rot=0.0, sample=SAMPLE)
        print("The camera's dark and open beam...")
        odin.move(shutter="closed", stage_x=0.0)
        cam_dark = odin.camera(T_TOMO, title="camera dark (tomography)", pixels=PX)
        D = odin.last_image.astype(float)
        odin.move(shutter="open", stage_x=0.5)
        cam_open = odin.camera(5 * T_TOMO, title="camera open beam (tomography)", pixels=PX)
        O = odin.last_image.astype(float)
        angles = np.arange(0, 180, 3.0)
        # per second, binned 2 x 2 (256 x 256 pixels: less noise on the screen)
        bin2 = lambda a: a.reshape(PX // 2, 2, PX // 2, 2).sum(axis=(1, 3))
        d2, o2 = bin2(D) / T_TOMO, bin2(O) / (5 * T_TOMO)
        row = int(np.clip(round(@Y1@ / (14.1 / (PX // 2)) + (PX // 2 - 1) / 2), 0, PX // 2 - 1))
        sino = np.full((len(angles), PX // 2), np.nan)

        def show(k, n, f):
            bar.update(k, n, f)
            T = (bin2(odin.last_image.astype(float)) / T_TOMO - d2) / np.maximum(o2 - d2, 1e-9)
            sino[k - 1] = -np.log(np.clip(T[row], 1e-3, None))
            proj_img.value = _png(T, 0.75, 1.05)
            sino_img.value = _png(sino, 0.0, 0.6, size=(PX // 2, 3 * len(angles)))
            proj_txt.value = (f"<b>Left:</b> projection {k} of {n}, at {angles[k - 1]:g}° (transmission T, white = "
                              f"1) &nbsp;·&nbsp; <b>Right:</b> the sinogram of the row at y = @Y1@ mm: "
                              f"−ln T of that row, one line per angle, from 0° (top) to 180°")
            tomo_view.layout.display = None

        bar.start(len(angles))
        odin.move(shutter="open", stage_x=0.0)
        files = odin.tomography(angles, T_TOMO, title="tomography", pixels=PX, progress=show)
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
display(w.VBox([w.HBox([button_tomo, ctl_tomo.stop]), bar.box, ctl_tomo.status, tomo_view, gate_tomo]))
""")

md(r"""
## 4. Look inside

The slices below follow the sliders ($x$ across, $z$ along the beam at 0°; the color is $\Sigma$ in cm⁻¹). The
largest bright spots are @WHERE@: move the cross (+) onto the brightest one. The rings around the rotation axis are
not in the rock: they come from the noise of the open beam, the same in every projection.
""")

code(r"""
ys = w.FloatSlider(value=@Y1@, min=-6.0, max=6.0, step=0.0275, description="Height y (mm)", continuous_update=True,
                   readout_format=".2f", layout=w.Layout(width="460px"))
zs = w.FloatSlider(value=0.0, min=-1.0, max=1.0, step=0.0275, description="Depth z (mm)", continuous_update=True,
                   readout_format=".2f", layout=w.Layout(width="460px"))
xs = w.FloatSlider(value=0.0, min=-4.0, max=4.0, step=0.0275, description="Point x (mm)", continuous_update=True,
                   readout_format=".2f", layout=w.Layout(width="460px"))
txt_sl = w.HTML("Run the tomography first.")
head_sl = w.HTML()

def frame():
    # the axes, labels and colorbar drawn once; the slices are put in them at each move (live_view.FastFrame)
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw=dict(width_ratios=[1.6, 1]))
    a.set(xlim=(-4.6, 4.6), ylim=(-1.6, 1.6), xlabel="x (mm)", ylabel="depth z (mm)", title="Horizontal slice at height y")
    b.set(xlim=(-4.6, 4.6), ylim=(-6.6, 6.6), xlabel="x (mm)", ylabel="y (mm)", title="Vertical slice at depth z")
    for ax in (a, b):
        ax.set_aspect("equal"); ax.set_facecolor("black")
    fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 2.0), cmap="magma"), ax=[a, b], label="Σ (cm⁻¹)", shrink=0.8)
    return live_view.FastFrame(fig, [a, b], cmap="magma", vmin=0, vmax=2.0)

img_sl = frame()
img_sl.layout.display = "none"
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
    img_sl.draw([(h, EXT), (v, EXT)], marks=[[("hline", zs.value), ("cross", xs.value, zs.value)],
                                            [("hline", ys.value), ("cross", xs.value, ys.value)]])
    img_sl.layout.display = None
    head_sl.value = (f"<b>Left:</b> horizontal slice at height y = {ys.value:.2f} mm &nbsp;·&nbsp; <b>Right:</b> "
                     f"vertical slice at depth z = {zs.value:.2f} mm &nbsp;·&nbsp; cross at x = {xs.value:.2f} mm")
    txt_sl.value = "Cross (+) on a bright spot? Then part 5 measures Σ there."

for s_ in (ys, zs, xs):
    s_.observe(live_view.throttled(show_slices, delay=0.02), "value")
display(w.VBox([ys, zs, xs, head_sl, img_sl, txt_sl]))
show_slices()
""")

md(r"""
## 5. What is in the bright spots?

*Measure Σ* gives the mean $\Sigma$ in a small ball around the cross, and in the matrix around it. Then it divides
the two. This **ratio** hardly depends on the wavelengths of the beam, so you can compare it with the table below
(Naver *et al.*, measured at ICON; matrix: 0.45 cm⁻¹).

| Material | Formula | Σ (cm⁻¹) | ratio to the matrix |
|---|---|---|---|
| plagioclase (a feldspar) | (Na,Ca)(Al,Si)₄O₈ | 0.27 – 0.28 | 0.6 |
| pyroxenes, chlorapatite | (Ca,Mg,Fe)₂Si₂O₆, Ca₅(PO₄)₃Cl | 0.34 – 0.38 | 0.8 |
| ilmenite | FeTiO₃ | 0.70 | 1.6 |
| magnetite, maghemite | Fe₃O₄, γ-Fe₂O₃ | 0.80 – 0.82 | 1.8 |
| *for comparison:* liquid water | H₂O | 3.6 | 8 |
| *for comparison:* the H-rich regions found by Naver *et al.* | | 1.9 | 4.2 |

The minerals of the first four rows hold no hydrogen. Water, and minerals with hydrogen such as goethite FeO(OH),
attenuate much more.
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
Your values of $\Sigma$ are higher than the table's: ODIN's neutrons are slower than ICON's on average, and slower
neutrons are attenuated more. The ratios change much less. A small spot is also blurred with its surroundings, so the
value in its middle is a bit too low.

## 6. How much water?

As Naver *et al.*, assume that all the extra attenuation of the spot comes from hydrogen, held as water:

- without water, the spot would have $\Sigma_\text{clast}$ = 0.68 cm⁻¹ (in ODIN's beam);
- liquid water has $\Sigma_\text{water}$ = 4.9 cm⁻¹ (in ODIN's beam);
- the fraction of the volume filled by water is $f = (\Sigma_\text{spot} - \Sigma_\text{clast}) / \Sigma_\text{water}$;
- water is 3 times lighter than the rock (1.0 against 3.0 g/cm³), so the water by mass is $f / 3$.

*Water in the spot* does this calculation with your $\Sigma$.
""")

code(r"""
button_w = w.Button(description="Water in the spot", button_style="success", icon="tint", layout=w.Layout(width="auto"))
out_w = w.Output()
SIG_CLAST, SIG_WATER, RHO = 0.68, 4.9, 3.0     # effective_sigma in the camera spectrum (white, 3 cm pinhole)

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



code(r"""
from page_output import collapsed
from IPython.display import Markdown
with collapsed("Going further: harder questions (click to open)"):
    display(Markdown("**Going further (harder, optional).** Three questions that go beyond the page: the noise of an image, the reduction of ESS, the number of angles of a tomography. They count in your score like the others."))
    q.number("**Noise.** In one image of the tomography, a pixel of the open beam collects about 56 neutrons per second; "
             "the rock lets 90 % of them through. Each image lasts 30 s and the open beam 150 s. Counting noise: "
             "N counted neutrons fluctuate by √N. What is the relative noise of T = S / O in one pixel (%)? (Neglect the dark.)",
             value=2.8, tol=0.1, unit="%",
             mistakes=[(2.6, "that is the noise of the sample image alone; the open beam is counted too, and its noise adds"),
                       (2.4, "the rock lets only 90 % through: the sample image has 0.9 × 56 × 30 neutrons"),
                       (1.1, "that is the open beam alone; the sample image is noisier")],
             hints=["The relative noise of N counts is 1/√N. For a ratio, the relative noises add in quadrature.",
                    "√(1/N_S + 1/N_O), with N_S = 0.9 × 56 × 30 and N_O = 56 × 150."],
             explanation="N_S = 1512, N_O = 8400: √(1/1512 + 1/8400) = 2.8 %. A clast of 0.3 mm lowers T by "
                         "about 6 % in ODIN's white beam: only 2.1 times the noise of one pixel, hardly visible. But it covers about 100 pixels: the "
                         "tomography, which combines all the pixels and all the angles, lowers the noise about 10 times. "
                         "This is why a long open beam matters: its noise is in every image.",
             title="X1. The noise of one pixel")
    q.number("**Reduction.** By mistake, the open beam was taken at 2 MW and the radiograph of the rock at 5 MW, with the "
             "same exposure. The rock lets 90 % through. If you divide each image by its exposure time only, which "
             "transmission do you find?",
             value=2.25, tol=0.05, unit="",
             mistakes=[(0.36, "the other way round: the sample image got 2.5 times more neutrons, not fewer"),
                       (0.9, "that is the true value, the one the ESS reduction finds: it divides by the proton charge, not "
                             "by the time. Here you divide by the time only")],
             hints=["At 5 MW each pulse carries 2.5 times more protons than at 2 MW, so 2.5 times more neutrons.",
                    "0.9 × 5 / 2."],
             explanation="0.9 × 2.5 = 2.25: a transmission above 1, impossible. The number of neutrons follows the protons on "
                         "the target, not the clock: the power changes, and even at constant power the pulses vary by about "
                         "1 % and the beam sometimes stops. So the ESS reduction (and the twin) divides each image by the "
                         "proton charge it received, written in the file: then T = 0.90 whatever the power.",
             title="X2. Per second or per proton?")
    q.number("**Tomography.** A rule of thumb: a tomography needs about (π/2) × N projections over 180°, N the number of "
             "pixels across the object, to sample the edge of the slices as finely as their middle. The piece is 8 mm wide "
             "and the pixels 27.5 µm. How many projections?",
             value=457, tol=15, unit="",
             mistakes=[(291, "that is N, the pixels across the piece; multiply by π/2"),
                       (914, "π × N: the rule is (π/2) × N over 180°"),
                       (60, "that is what you took; the question asks for the rule")],
             hints=["N = 8 mm / 27.5 µm.", "N = 291; then × π/2."],
             explanation="N = 8 / 0.0275 = 291, × π/2 = 457 projections. You took 60, to keep half an hour of beam; 457 would take "
                         "almost 4 hours. With too few angles the gaps between them show far from the rotation axis: streaks, "
                         "and fine details smeared at the edges of the slices, while the middle stays good. It is the usual "
                         "trade between beam time and quality; Naver et al. took 1125 images at ICON.",
             title="X3. How many angles?")
""")

md(r"""
**Limits of the twin.** The piece is a model built from the published numbers (sizes, amounts and attenuations of
the clasts); where the clasts sit is drawn at random. The minerals are mixed at the scale of each region (no
crystal). The camera is modeled by its mean signal, its noise and its blur.

## 7. Your results, your comment

Your score on the questions, then a few words on the session: what was clear, what was not, what you would change.
**Then click *Submit***: without it, your answers and your comment do not reach us.
""")

code(r"""
q.report()
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/meteorite_imaging", "class", quiz=q, title="ODIN: a Martian meteorite")
""")

QS = {
    'water': r'''
q.number("1 mm of water in the beam, with neutrons of 3 Å (the middle of ODIN's beam): Σ = 4.9 cm⁻¹ (mostly the "
         "scattering by hydrogen). "
         "Which fraction of the neutrons does it remove, 1 − T (%)? (For comparison after you answer: X-rays of "
         "60 keV see μ = 0.21 cm⁻¹ for water.)",
         value=39.0, tol=1.5, unit="%",
         mistakes=[(0.39, "a fraction: the answer is asked in % (multiply by 100)"),
                   (2.0, "that is the X-ray value (μ = 0.21 cm⁻¹); the question is about neutrons"),
                   (49, "4.9 cm⁻¹ × 0.1 cm = 0.49 is −ln T, not 1 − T: T = e^(−0.49)")],
         hints=["T = exp(−Σ d), with d = 0.1 cm.", "1 − exp(−0.49)."],
         explanation="1 − e^(−0.49) = 39 % with neutrons, 1 − e^(−0.021) = 2 % with X-rays. And 1 mm of iron: neutrons "
                     "10 % (Σ = 1.1 cm⁻¹ at 3 Å), X-rays of 60 keV 61 % (μ = 9.5 cm⁻¹). The contrasts are very "
                     "different: water stands out for neutrons, iron for X-rays.",
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
q.number("*Water in the spot* printed a line ending with \"water by mass = … %\". Type that number for your "
         "brightest spot.", value=8, tol=6, unit="%",
         mistakes=[(0.08, "below the range expected. Is it a fraction (then multiply by 100)? Is the cross on a bright spot?")],
         hints=["Click *Water in the spot* just above, after *Measure Σ* on a bright spot.",
                "Copy the number at the end of its line (in %)."],
         explanation="Every student finds a different spot, so a range is accepted: a few % to about 12 %. The model "
                     "holds about 14 % in the middle of the regions (Naver et al.: up to 15 %); the blur lowers the "
                     "value measured in a small spot.", title="Q4. How much water?")
''',
    'magnif': r'''
q.choice("A laboratory micro-CT magnifies by bringing the sample close to a small focal spot (a cone beam). Why does "
         "ODIN put the camera **6 mm** behind the sample instead, without magnification?",
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
PLACE = [("ODIN from the source to the camera", ["water", "magnif"]), ("display(w.VBox([ys, zs, xs, head_sl, img_sl, txt_sl]))", ["where"]),
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
