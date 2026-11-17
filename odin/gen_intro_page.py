"""Generates twin/odin/ODIN_intro.ipynb: the introduction to ODIN (all levels), shown by Voila as the first card of
ODIN in the catalogue of the app (odin/exercises/introduction/exercise.yml).

    python gen_intro_page.py

How the instrument works (source, guide, pinhole, time of flight, choppers) and what it is used for, with pictures to
try and questions all along. No code to read or write, no measurement: about 40 minutes. The figures come from
gen_intro_figures.py (twin/figures/), the interactive pictures from intro_widgets.py.
Numbers: distances of the official McStas model (odin_mcstas.py); λ[Å] = 3956 / v[m/s]; 14 pulses per second of
2.86 ms; flux of the WFM mode = 3 % of the white beam (measured on the model).
"""
import os
import sys

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from nbfig import figure_cell  # noqa: E402

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))
fig = lambda name, caption: cells.append(figure_cell(name, caption))

md(r"""
# Introduction to ODIN

**Welcome to the Neutron Solutions Team of ESS.** This is your first day. Requests will soon arrive from Fyrø Energy
Island, from the Mars team and from the team itself; before that, Maja, the instrument scientist of ODIN, shows you
the instrument.

ODIN is the **neutron imaging** instrument of the European Spallation Source (ESS). It takes pictures *through*
objects, as an X-ray machine does, but with neutrons. This page explains how it works and what it is used for, before
you measure with it. There is nothing to compute by hand and no code: read, try the pictures, answer the questions.
About 40 minutes.

**What you will know at the end**
1. what a neutron picture shows that an X-ray picture does not;
2. the parts of ODIN, from the source to the camera;
3. how the size of a hole sets the sharpness of the picture;
4. how ODIN knows the wavelength of each neutron: the time of flight;
5. what the choppers are for;
6. how the neutrons are detected, and how sharp the pictures can be;
7. which exercises of the catalogue use which capability;
8. everything that sets the instrument, in one table: what you choose, what is fixed.
""")

code(r"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath(".."))
import intro_widgets as iw
import web_user
web_user.sign_in()            # the online version: the anonymous student of the start page (nothing to do in the app)
import quiz
q = quiz.Quiz("odin_intro")
""")

md(r"""
## 1. A picture made with neutrons

In a **radiograph**, a beam crosses an object and a camera behind it records what comes through: the parts that stop
more of the beam look darker. X-rays are stopped by electrons, so heavy elements (metals) stop them most. Neutrons
are stopped by atomic nuclei, and the rule is different: **hydrogen and lithium stop neutrons strongly, while many
metals (aluminium, iron, lead) let most of them through**. A neutron picture therefore shows water inside a metal pipe, the
lithium moving in a battery, or the glue in a turbine blade.

The fraction of the beam that comes through is the **transmission** $T$, between 0 (everything stopped) and 1
(nothing stopped).
""")

code(r"""
q.choice("You want to see where the water is inside a running fuel cell with steel plates. Which beam do you choose, "
         "and why?",
         ["Neutrons: they cross the steel and are stopped by the hydrogen of the water.",
          "X-rays: they are stopped by the hydrogen of the water.",
          "Either: both give the same picture.",
          "Neutrons: they are stopped by the steel, which outlines the cell."],
         answer=0, why={1: "X-rays are stopped by electrons: the steel stops them far more than the water, which stays "
                           "invisible behind it.",
                        2: "The two beams are stopped by different things (electrons for X-rays, nuclei for neutrons): "
                           "the pictures differ.",
                        3: "Steel lets most neutrons through; it is the hydrogen that stops them."},
         explanation="Neutrons see light elements such as hydrogen through centimeters of metal: the classic use of "
                     "neutron imaging.", hints=["Which element stops neutrons strongly?"], title="Q1. Neutrons or X-rays?")
""")

md(r"""
## 2. ODIN, from the source to the camera

ESS makes neutrons in **pulses**: 14 times per second, for 2.86 ms, protons hit a tungsten target, and a
**moderator** (cold hydrogen and water) slows the neutrons down. ODIN is 60 m long:
""")
fig("odin_beamline.png", "ODIN from the source to the camera (distances of the official McStas model of ODIN).")
md(r"""
- the **choppers** (rotating discs with openings, between 7 and 33 m) let neutrons pass only at chosen times (part 5);
- the **neutron guide** (a tube of mirrors) carries the beam over 49 m without losing it;
- the **pinhole**, at 50 m, is a hole of 1 to 4 cm: seen from the sample, it is the source of the beam (part 3);
- the **sample** is at 60.5 m, on a stage that moves and turns it;
- the **camera** just behind it records each neutron: where it arrived (which pixel) and when (part 4).
""")

code(r"""
q.number("ESS sends 14 pulses per second. How many milliseconds are there between the starts of two pulses?",
         value=71.4, tol=0.6, unit="ms",
         mistakes=[(2.86, "the length of one pulse, not the time between two pulses"), (14, "the number of pulses per "
                   "second; the time between two is 1 s / 14")],
         hints=["One second holds 14 equal intervals.", "1000 ms / 14."],
         explanation="1000 ms / 14 = 71.4 ms. Keep this number: it comes back in part 5.", title="Q2. Between two pulses")
""")

md(r"""
## 3. The pinhole: sharp or bright?

ODIN works like a **pinhole camera**. Each point of the sample is lit by the whole opening of the pinhole, of side
$D$, at a distance $L$ = 10.5 m. Behind the sample, the rays from the two edges of the hole spread apart again: on a
camera at a distance $l$ behind the sample, a point becomes a spot of width
$$\text{blur} = l \times \frac{D}{L}.$$
""")
fig("odin_pinhole.png", "Why a point of the sample becomes a spot on the camera: the rays from the two edges of the "
    "pinhole cross at the point and spread apart behind it.")
md(r"""
The ratio $L/D$ is the **collimation ratio**: the larger, the sharper the picture. But the neutrons that reach the
sample are those that pass the hole: their number goes with its **area**, $D^2$. A small pinhole gives a sharp but
dark, hence noisy, picture. Try it: the picture below is a test pattern of bars of four widths.
""")

code(r"""
iw.odin_pinhole()
""")

code(r"""
q.number("With the 3 cm pinhole (L = 10.5 m), what is the collimation ratio L/D?", value=350, tol=5, unit="",
         mistakes=[(3.5, "mind the units: 10.5 m = 1050 cm"), (0.00286, "D/L, the inverse")],
         hints=["Use the same unit for both: L = 1050 cm.", "1050 / 3."],
         explanation="1050 cm / 3 cm = 350. With the camera 5 cm behind the sample the blur is 5 cm / 350 = 0.14 mm.",
         title="Q3. Collimation ratio")
q.choice("You change the pinhole from 3 cm to 1 cm, and count for the same time. What happens to the picture?",
         ["3 times sharper, with 9 times fewer neutrons: noisier.",
          "3 times sharper, with 3 times fewer neutrons.",
          "9 times sharper, with 3 times fewer neutrons.",
          "Sharper and brighter: a smaller hole concentrates the beam."],
         answer=0, why={1: "The blur goes with D (3 times), but the neutrons go with the area of the hole, D²: 9 times.",
                        2: "The other way round: the blur goes with D, the number of neutrons with D².",
                        3: "A hole only lets through what falls on it: a smaller hole means fewer neutrons."},
         explanation="Blur = l·D/L: 3 times smaller. Neutrons through the hole ∝ D²: 9 times fewer. To keep the same "
                     "noise you would have to count 9 times longer.",
         hints=["How does the blur depend on D?", "How does the area of a square hole depend on its side?"],
         title="Q4. Sharp or bright?")
""")

md(r"""
## 4. Time of flight: the clock that measures the wavelength

A neutron is also a wave. Its **wavelength** $\lambda$ depends only on its speed $v$: slow neutrons have a long
wavelength,
$$\lambda\,[\text{Å}] = \frac{3956}{v\,[\text{m/s}]}$$
(1 Å = 0.1 nm, about the distance between two atoms). The wavelength matters because it decides how a material stops
the neutron: the transmission of a crystal changes abruptly at certain wavelengths (the Bragg edges of the exercise
on iron).

All the neutrons of a pulse leave the source at almost the same time, but the slow ones arrive later. So the
**arrival time** at the camera, 60.55 m away, tells the speed, hence the wavelength. This is the **time of flight**:
""")
fig("odin_tof.png", "Distance against time. Each line is a neutron of pulse 1: the slower it is (the longer its "
    "wavelength), the flatter its line and the later it reaches the camera.")
md(r"""
Try it: choose a wavelength and see when the neutron arrives.
""")

code(r"""
iw.odin_time_of_flight()
""")

code(r"""
q.number("A neutron of 4 Å travels at 3956 / 4 = 989 m/s. How long does it take to reach the camera, 60.55 m away?",
         value=61.2, tol=1.0, unit="ms",
         mistakes=[(0.0612, "right, but in seconds: give it in milliseconds"), (16.3, "you divided the speed by the "
                   "distance; time = distance / speed")],
         hints=["time = distance / speed.", "60.55 m / 989 m/s = 0.0612 s."],
         explanation="60.55 / 989 = 0.0612 s = 61.2 ms. Twice the wavelength is half the speed, hence twice the time: "
                     "the arrival time is proportional to λ.", title="Q5. Arrival time")
q.choice("The camera records a neutron 30.6 ms after the pulse. Which wavelength does it have?",
         ["2 Å", "4 Å", "1 Å", "8 Å"], answer=0,
         why={1: "A 4 Å neutron needs 61.2 ms (Q5). This one arrived in half that time.",
              2: "A 1 Å neutron is 4 times faster than a 4 Å one: 15.3 ms.",
              3: "An 8 Å neutron is the slowest of the four: 122 ms."},
         explanation="The arrival time is proportional to λ: half the time of a 4 Å neutron means half the wavelength, "
                     "2 Å. This is exactly what the ESS software does for every neutron of your files.",
         hints=["Compare with the 61.2 ms of a 4 Å neutron."], title="Q6. From the time to the wavelength")
""")

md(r"""
## 5. The choppers: keeping the pulses apart, and sharpening them

**Two problems** with the simple picture of part 4.

**Problem 1: the pulses overlap.** A new pulse leaves every 71.4 ms. Look again at the figure of part 4: a 6 Å
neutron of pulse 1 needs 92 ms, so it arrives *after* the fast neutrons of pulse 2. The camera cannot tell them
apart: this is **frame overlap**. Between two pulses the camera can only sort a band of wavelengths
$3956 \times 0.0714 / 60.55$ = **4.7 Å** wide. ODIN's *band choppers* turn at 7 turns per second and let through
**one pulse in two**: the pulses are then 143 ms apart, and a band of about 9 Å (1 to 9 Å) fits without overlap.

*Try it*: choose a time at the camera with the slider. With the band choppers stopped, neutrons of two pulses (two
different wavelengths) can arrive at that same time; start the choppers: only one remains.
""")
code(r"""
iw.odin_band_choppers()
""")
md(r"""
**Problem 2: the pulse is long.** The neutrons do not leave at one instant but during 2.86 ms. Two neutrons of the
same wavelength can thus arrive 2.86 ms apart, and the clock mistakes this for a difference of wavelength of
$3956 \times 0.00286 / 60.55$ = **0.19 Å**. At 4 Å this is an uncertainty of about 5 %: too coarse to measure, for
instance, how much a metal is stretched (0.1 %). The *WFM choppers* (wavelength frame multiplication), 7 m from
the source, cut the long pulse into six short ones: the wavelength is then known to **0.2 to 0.8 %**, at a price:
only **3 % of the neutrons** are left.

*Try it*: with the WFM choppers stopped, all the neutrons of one wavelength that leave during the 2.86 ms reach the
camera spread over 2.86 ms. Start them: two discs a distance δ apart let through only those that left within a short
time, and the spread shrinks. Change δ and the wavelength: compare the resolution Δλ/λ and the share of neutrons kept.
""")
code(r"""
iw.odin_wfm()
""")
md(r"""
Hence the three chopper settings of the twin, which you will choose yourself in the exercises:

| Chopper mode | What turns | Wavelengths | Wavelength known to | Neutrons |
|---|---|---|---|---|
| `white` | nothing | all, mixed | not measured | all (100 %) |
| `natural` | band choppers | 1 to 9 Å | 0.19 Å (2 to 10 %) | about half (one pulse in two) |
| `wfm` | band + WFM choppers | 1 to 9 Å | 0.2 to 0.8 % | 3 % |
""")

code(r"""
q.choice("Why do the band choppers of ODIN let through only one pulse in two?",
         ["So that the slow neutrons of one pulse do not arrive mixed with the fast neutrons of the next.",
          "To protect the camera from too many neutrons.",
          "To make the neutrons slower.",
          "To make the picture sharper."],
         answer=0, why={1: "The camera stands the full beam; the point is to know which pulse each neutron comes from.",
                        2: "A chopper does not change the speed of a neutron: it only lets it pass or stops it.",
                        3: "The sharpness of the picture is set by the pinhole (part 3)."},
         explanation="With pulses 71.4 ms apart only a 4.7 Å band can be sorted by arrival time; with one pulse in two, "
                     "about 9 Å.", hints=["Look at the dashed line of the figure of part 4."], title="Q7. One pulse in two")
q.number("Without the WFM choppers, the wavelength is known to 0.19 Å. What is this uncertainty, in percent, for a "
         "neutron of 4 Å?", value=4.7, tol=0.4, unit="%",
         mistakes=[(0.047, "right, but as a fraction: multiply by 100"), (21, "you divided 4 by 0.19; the other way round")],
         hints=["Relative uncertainty = 0.19 / 4.", "0.19 / 4 = 0.047."],
         explanation="0.19 / 4 = 4.7 %. For 2 Å it is 9 %, for 9 Å 2 %: the long wavelengths are known best.",
         title="Q8. How well is the wavelength known?")
q.choice("You must measure how much a steel part is stretched: its Bragg edge moves by 0.1 % of its wavelength. "
         "Which chopper mode do you choose?",
         ["wfm: the only one that knows the wavelength well enough, even with fewer neutrons.",
          "white: the most neutrons, so the best measurement.",
          "natural: a good compromise.",
          "Any: the mode does not matter for an edge."],
         answer=0, why={1: "In white mode the wavelength is not measured at all: no edge can be seen.",
                        2: "Natural mode knows the wavelength to about 5 % at 4 Å: 50 times too coarse for 0.1 %.",
                        3: "It does: the edge is smeared by the uncertainty of the wavelength."},
         explanation="Only WFM reaches a fraction of a percent. The price is 3 % of the neutrons, so a longer count: "
                     "the trade-off between resolution and counting time comes back in every exercise.",
         hints=["Compare 0.1 % with the last-but-one column of the table."], title="Q9. Which mode?")
""")

md(r"""
## 6. Detecting the neutrons

A neutron has no electric charge: no camera sees it directly. ODIN turns each neutron into a flash of light in a
**scintillator**, a thin screen containing lithium-6 that absorbs the neutron and glows; a camera, out of the beam
behind a mirror, films the light.
""")
fig("odin_detector.png", "How a neutron becomes a picture: absorbed in the scintillator, it makes a flash of light, "
    "which a mirror sends to a camera out of the beam. The neutrons that are not absorbed go on to the beam stop.")
md(r"""
Two consequences you meet in every exercise:

- **Thick or thin screen.** A thick scintillator stops more neutrons (a bright picture) but the light spreads in it
  (a blurred picture); a thin one is sharp but stops fewer neutrons.
- **Not every neutron is counted.** The screen stops slow neutrons better than fast ones. In the twin the share of
  neutrons detected is $\varepsilon(\lambda) = 1 - e^{-\lambda / 8\,\text{Å}}$: 22 % at 2 Å, 39 % at 4 Å, 63 % at 8 Å.
  It cancels in a transmission (sample and open beam are detected the same way).
""")
fig("odin_scintillator.png", "Left: in a thick screen the neutrons are absorbed at different depths and the light of "
    "each flash spreads on its way out: a larger spot, so a blurred picture; a thin screen keeps the spot small but "
    "stops fewer neutrons. Right: the share of the neutrons detected in the twin, larger for slow neutrons.")
md(r"""
The twin's ODIN has **two cameras**, with the same field of view, **14 mm × 14 mm**, 5 cm behind the sample:

| | Timepix3 camera (event mode) | Integrating camera (scintillator + sCMOS) |
|---|---|---|
| What it records | **each neutron**: where it arrived and when, hence its wavelength (part 4) | the light summed over the exposure: a picture, **no time, no wavelength** |
| Pixels | positions kept on a grid of 4096 × 4096 (3.4 µm); the pictures are shown in 128 × 128 pixels of 110 µm (64 × 64 of 220 µm if you choose it for the pictures per wavelength, to keep more neutrons per pixel) | **standard**: 128 × 128 pixels of 110 µm, thick scintillator (blur 0.1 mm); **high resolution**: 512 × 512 pixels of 27.5 µm, thin scintillator (blur 0.02 mm), 16 times fewer neutrons per pixel |
| Used for | Bragg edges, strain, polarized imaging | radiography, tomography, battery |
""")
fig("odin_cameras.png", "The same neutrons through an iron disc, seen by the two cameras. The Timepix3 camera writes "
    "one line per neutron; its arrival time gives its wavelength, so the neutrons can be sorted into one picture per "
    "wavelength. The integrating camera only adds up the light: one picture, all wavelengths mixed.")
md(r"""
**How sharp is the picture?** Three blurs add up, and the largest one wins: the pinhole ($l / (L/D)$, part 3), the
scintillator, and the pixel. They combine as $\sqrt{a^2 + b^2 + c^2}$. Standard setup with the 3 cm pinhole: 0.14 mm,
0.1 mm and 0.11 mm, about **0.2 mm** in all. High resolution with the 1 cm pinhole: 0.05 mm, 0.02 mm and 0.03 mm, about
**0.06 mm**, but with far fewer neutrons per pixel: much longer exposures.

*Try it*: choose the camera and the pinhole, and look at the test pattern. Then choose the high resolution with the
1 cm pinhole: the 50 µm bars are no longer blurred, but the picture is lost in the noise (3 neutrons per pixel).
Count 100 times longer: they appear.
""")
code(r"""
iw.odin_resolution()
""")
md(r"""
The pixel size is **your choice** among these settings of the cameras; the field of view, the distance from the
sample to the camera and the efficiency are **fixed** in the twin. The real ODIN has more detectors and optics to
choose from (larger fields, other pixels). *Limits of the twin*: a real Timepix3 camera loses neutrons above a few
million per second (in the white beam with a large pinhole); the twin does not lose them, it warns you. And the
neutrons **scattered** by the sample that still reach the camera, 5 cm behind it, are left out: on the real
instrument they add a faint halo, which matters for thick samples rich in hydrogen (water, plastics) and makes their
transmission look a little higher.
""")

code(r"""
q.choice("You want to see details of 0.1 mm in a sample. Which setting do you choose?",
         ["The integrating camera in high resolution, with the 1 cm pinhole, and a long exposure.",
          "The integrating camera in standard resolution, with the 4 cm pinhole: the most neutrons.",
          "The high-resolution camera with the 4 cm pinhole.",
          "The Timepix3 camera: it keeps positions to 3.4 µm."],
         answer=0, why={1: "Its pixels (110 µm), its scintillator (0.1 mm) and the pinhole (0.19 mm with 4 cm) add up to about 0.24 mm: larger than the details.",
                        2: "The pinhole then blurs by 5 cm / 262 = 0.19 mm: the thin scintillator does not help.",
                        3: "The positions are written finely, but the light still spreads by about 0.1 mm in the "
                           "screen: the sharpness is that of the blur, not of the grid."},
         explanation="Every blur must be smaller than the details: 1 cm pinhole (0.05 mm), thin scintillator "
                     "(0.02 mm), pixels of 27.5 µm: about 0.06 mm in all. The price: 16 times fewer neutrons per "
                     "pixel, and 9 times fewer through the 1 cm pinhole than the 3 cm one: a much longer exposure.",
         hints=["Compare each blur with 0.05 mm.", "Part 3: blur = 5 cm / (L/D) = 5 cm × D / 10.5 m."], title="Q10. Sharp enough?")
""")

md(r"""
## 7. What ODIN is used for

Everything ODIN does combines the three ingredients of this page: a picture (part 3), a wavelength for every neutron
(part 4), and a choice of resolution (part 5). The catalogue of the app has, or will have, an exercise for each use:

| What you look at | What it tells | Typical question | In the catalogue |
|---|---|---|---|
| The picture itself, all wavelengths | where the material is | Where is the water in this fuel cell? | planned |
| Many pictures while the sample turns (**tomography**) | the object in 3D | What is inside this object? | **What is hidden inside a Martian meteorite?** |
| The transmission against the wavelength: **Bragg edges** | the crystal structure, the phases | How much of this anode is reduced? | **Where has the fuel-cell anode been reduced?** |
| The exact position of an edge (WFM mode) | how much the material is stretched | Where is this part under stress? | **Where is a loaded steel part strained?** |
| A sample that changes with time | what happens during operation | How does lithium enter a battery electrode? | **How does lithium enter a battery electrode?** |
| The spin of the neutrons (**polarized** imaging) | magnetic fields inside matter | What is the field inside this coil? | **Seeing a magnetic field with neutrons** |
""")

md(r"""
## 8. Summary: everything that sets the instrument

**NICOS** is the program with which the instrument is driven at ESS: from the control room, you type its commands (or
use its windows) to move the sample, choose the pinhole or the chopper mode, and start a measurement; it also writes
the data files. The twin's ODIN is driven with the same NICOS; in the guided exercises, a **panel** of buttons on the
page does the same for you.

What sets a measurement on the twin's ODIN, and who decides: **you** (a setting of NICOS or of the panel), **follows**
(it follows from another setting), or **fixed** (the instrument as built).

| Part | Setting | Values in the twin | Who | What it changes |
|---|---|---|---|---|
| Source | pulses | 14 per second, 2.86 ms long | fixed | the time-of-flight clock (part 4) |
| | distance source → sample | 60.5 m | fixed | arrival time of each wavelength |
| Choppers | mode | white (none), natural (band-pass + T0), WFM | you | resolution in wavelength against flux (part 5) |
| | WFM disc separation δ | 0.10, 0.30, 0.45 m | you (WFM) | smaller δ: finer resolution, fewer neutrons |
| | speeds and phases of the discs | read in NICOS | follows (mode, δ) | which neutrons pass, when |
| | wavelength band | 1 to 9 Å (WFM, natural); 0.5 to 15 Å (white) | follows (mode) | which Bragg edges are seen |
| Beam | experiment shutter | open, closed | you | closed: the dark picture |
| | pinhole side D | 1, 2, 3, 4 cm | you | sharpness against flux (part 3) |
| | distance pinhole → sample L | 10.5 m (L/D from 1050 to 262) | fixed | with D, the blur |
| | diffuser | in, out | you | a more even beam |
| Sample | sample mounted | the samples of your proposal; none | you | — |
| | stage translation x (across the beam) | −500 to +500 mm (beyond 20 mm: out of the field, open beam) | you | sample in or out of the beam |
| | stage rotation | −180° to +180° | you | the angle (tomography) |
| | load frame | 0 kN up to the limit of the sample (frame: 50 kN) | you (samples that can be loaded) | strain |
| | battery cycler | time in the cycle, 0 to 55 h | you (batteries) | state of charge |
| | polarizer and analyzer | in, out; spin in ±x, ±y, ±z; spin analyzed x, y, z | you | polarized imaging |
| Detection | distance sample → camera | 5 cm (the stage moves the sample across the beam, not along it; on a real instrument this distance can be changed) | fixed | with L/D, the blur |
| | field of view | 14 mm × 14 mm | fixed | the largest object seen at once |
| | Timepix3 camera | counting time; pictures per wavelength: range, bin (0.01 Å), 128 or 64 pixels | you | wavelength, statistics |
| | integrating camera | exposure (up to 3600 s); standard (110 µm) or high resolution (27.5 µm) | you | sharpness against neutrons per pixel |
| | efficiency of the scintillator | 1 − exp(−λ / 8 Å) | fixed | counts at short wavelengths |
""")

code(r"""
q.report()
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/introduction", "bsc", quiz=q)
""")

md(r"""
**Next.** Open your exercise: the first chapter of your thread on the map of the catalogue (online: the button
*← Missions* at the top of this page).
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_intro.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb, len(cells), "cells")
