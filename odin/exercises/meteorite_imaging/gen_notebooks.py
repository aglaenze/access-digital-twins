"""Generates the MSc and beamtime notebooks of the exercise "What is hidden inside a Martian meteorite?":

  * ODIN_meteorite_msc.ipynb       MSc, "develop the method": measure (NICOS or the panel), radiograph, sinogram,
                                   reconstruction (filter and number of angles compared), the clasts in 3D, then the
                                   element by its wavelength dependence (two models compared) and the water content;
  * ODIN_meteorite_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only (beamtime.md).

    python gen_notebooks.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from nbgen import code, distribute, md, nicos_step, stop, write  # noqa: E402

PROPOSAL = "1250"
SETUP = r'''
import sys, os, json, datetime, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
import odin_reduction as red, odin_radiography as tomo
import live_view                  # figures that follow the sliders
import quiz
q = quiz.Quiz("odin_meteorite_msc")       # the questions of this notebook
EXT = tomo.extent()
'''
SAMPLE = r'''
import sample_library as sl
for name, hidden in sl.exercise_hidden("exercise.yml").items():
    spec = sl.load("odin")[name]
    print(sl.describe("odin", spec, hidden))
    sl.draw("odin", spec, hidden=hidden, fig=plt.figure(figsize=(10, 3.5))); sl.show()
'''
FILES = r'''
from odin_paths import TWIN_RUN_ROOT
PROPOSAL = "1250"
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/{PROPOSAL}/raw"
rows = red.measurements(FOLDER)
if not rows:
    raise SystemExit("No file yet in " + FOLDER + ": measure first (part 0).")
for r in rows:
    print(f"{r['file']:20s} {r.get('detector', 'timepix3'):9s} {r['kind']:10s} {r.get('title', '')[:24]:24s} "
          f"t = {r.get('t_s', 0):4.0f} s  {r.get('choppers')}  rot {r.get('stage_rot_deg', 0):6.1f}°")
'''
PICK = r'''
path = lambda r: os.path.join(FOLDER, r["file"])
cam = [r for r in rows if r.get("detector") == "camera"]
tof = [r for r in rows if r.get("detector") != "camera" and r.get("choppers") == "wfm"]
single = [r for r in cam if not r.get("title", "").startswith("tomography")]
DARK = next((path(r) for r in reversed(single) if r["kind"] == "dark"), None)
OPEN = next((path(r) for r in reversed(single) if r["kind"] == "open beam"), None)
RADIO = next((path(r) for r in reversed(single) if r["kind"] == "sample"), None)
TOMO = []                                  # the last tomography: its images from the one at 0° on
for r in cam:
    if r.get("title", "").startswith("tomography") and r["kind"] == "sample":
        if r["stage_rot_deg"] == 0:
            TOMO = []
        TOMO.append(path(r))
TOF_OPEN = next((path(r) for r in reversed(tof) if r["kind"] == "open beam"), None)
TOF_SAMPLE = next((path(r) for r in reversed(tof) if r["kind"] == "sample" and r["stage_rot_deg"] == 0), None)
name = lambda f: f and os.path.basename(f)
print(f"camera: dark {name(DARK)}, open beam {name(OPEN)}, radiograph {name(RADIO)}, tomography {len(TOMO)} images")
print(f"time of flight: open beam {name(TOF_OPEN)}, meteorite {name(TOF_SAMPLE)}")
'''

msc = [md(r"""
# What is hidden inside a Martian meteorite? (MSc: develop the method)

**Your mission.** The team of planetary scientists wants a method it can trust to find water inside precious
meteorites without cutting them: where it is (3D), and how much. You develop it on a cylinder of the Martian
meteorite NWA 7034, 12 mm across: radiography, then tomography (you choose how to reconstruct), then the time of
flight to show that the attenuation is due to hydrogen, and how much water there is.

**The physics.** The transmission of a line through the sample is $T = e^{-\int \Sigma\, dl}$; hydrogen has a huge
(incoherent) scattering cross-section, so water makes a rock dark for neutrons. A tomography measures
$p(\theta, x') = -\ln T$ for many angles $\theta$ of the sample (the sinogram), and recovers $\Sigma(x, z)$ of each
horizontal slice by filtered back-projection.

The code of each step is given (and locked): read it, run it, and make the decisions with the widgets.
"""), code(SETUP), md("## The sample"), code(SAMPLE), md(r"""
## Before you measure

With the **integrating camera** (white beam: choppers stopped, the highest flux; one image, no time of flight):
1. a **dark** (shutter closed) and an **open beam** (sample out of the beam: stage x = 500 mm), 2 s each;
2. a **radiograph** of the meteorite at 0°, 2 s;
3. a **tomography**: one image of 1 s every 6° from 0 to 174° (30 images).

With the **event camera** (Timepix3: time of flight; choppers in WFM mode, δ = 0.30 m), at 0°:
4. an **open beam** and the **meteorite**, 10 s each.
"""), code(r'''
q.choice("Why does a tomography with a parallel beam need 180° only, not 360°?",
         ["Turning by 180° shows the same lines through the sample, crossed in the other direction: the same "
          "projection, mirrored.", "To save time: 360° would be better but too long.",
          "Because the stage cannot turn further."],
         answer=0, why={1: "The extra 180° hold no new information (only less noise, as longer images would).",
                        2: "It can (−180° to 180°)."},
         explanation="With parallel rays, p(θ + 180°, x') = p(θ, −x'). A cone beam (X-ray tubes) needs 360°; the "
                     "beam of ODIN is nearly parallel (L/D large).", hints=["Draw the lines through the sample at θ and at θ + 180°."],
         title="Q1. 180°")
'''), md(r"""
## 0. Your measurements

Choose how: **in NICOS** (the commands below, one at a time), or **here, with a panel** (the same devices, with
*Camera image*, *Run the tomography* and *Count* buttons). Either way your files go to the folder of proposal 1250.
"""), code(f'import measure_panel\nmeasure_panel.Panel("odin", proposal="{PROPOSAL}", samples=["meteorite_nwa7034"])'),
    nicos_step(md(r"""
### Step 1. Your proposal

In NICOS, tab **Experiment**, **Find my proposal**, choose **1250** (*Water in a Martian meteorite*), then **Apply**:
the meteorite is mounted on the rotation stage. Then tab **Instrument interaction**, one command at a time.
""")), nicos_step(md(r"""
### Step 2. White beam: dark, open beam, radiograph

`radiograph(t, title)` takes one image with the integrating camera.

```
move(choppers, 'white', pinhole, 0.03, diffuser, 'in')
move(shutter, 'closed')
radiograph(2, 'dark')
move(shutter, 'open', stage_x, 500)
radiograph(2, 'open beam')
move(stage_x, 0, stage_rot, 0)
radiograph(2, 'meteorite 0 deg')
```
""")), nicos_step(md(r"""
### Step 3. The tomography

`tomography(t, step)`: one image of t seconds every `step` degrees from 0 to 180° (excluded), then back to 0°.

```
tomography(1, 6)
```
""")), nicos_step(md(r"""
### Step 4. Time of flight

```
move(choppers, 'wfm', wfm_delta, 0.3, stage_x, 500)
with nexusfile_open('open beam TOF'):
    count(t=10)
move(stage_x, 0)
with nexusfile_open('meteorite TOF'):
    count(t=10)
```
""")),
    stop(md(r"""
## 1. Your files

Read from the files themselves: camera images (`camera`) and event files (`timepix3`), with the state of the
instrument during each.
""")), code(FILES), md("## 2. Which file is what?"), code(PICK), md(r"""
## 3. The radiograph

$T = (I - D)/(O - D)$, each image per second of exposure. Along a line through the matrix only, $T = e^{-\Sigma L}$
with $L$ the chord of the cylinder (12 mm at its center): the cell estimates $\Sigma$ of the matrix there.
"""), code(r'''
T = tomo.transmission(RADIO, OPEN, DARK)
fig, ax = plt.subplots(figsize=(5.5, 4.6))
im = ax.imshow(T, origin="lower", extent=EXT, cmap="gray", vmin=0.5, vmax=1.05)
fig.colorbar(im, ax=ax, label="T"); ax.set(xlabel="x (mm)", ylabel="y (mm)", title="Radiograph at 0°"); plt.show()
c = T[60:68, 56:64]                       # 8 x 8 pixels at the center (x ≈ −0.5 mm, y ≈ 0)
print(f"T at the center: {c.mean():.3f} ± {c.std() / np.sqrt(c.size):.3f}  ->  Σ = −ln T / 1.2 cm = "
      f"{-np.log(c.mean()) / 1.2:.3f} cm⁻¹ (if only matrix is on these lines)")
'''), md(r"""
## 4. The sinogram

For one row of pixels (height $y$), the projections $p = -\ln T$ of all the angles, one line per angle: each point
of the slice draws a sine curve $x' = x\cos\theta + z\sin\theta$ (hence the name). A clast makes a dark band that
swings from side to side.
"""), code(r'''
if not TOMO:
    raise SystemExit("No tomography yet (part 0, step 3).")
angles, P = tomo.sinogram(TOMO, OPEN, DARK)
row = int(round(2.0 / tomo.PIXEL_MM + 63.5))         # y = 2 mm: through the darkest spot
fig, ax = plt.subplots(figsize=(7, 4))
ax.imshow(P[:, row, :], aspect="auto", origin="lower", cmap="magma",
          extent=(EXT[0], EXT[1], angles[0], angles[-1] + np.median(np.diff(angles))))
ax.set(xlabel="x' on the camera (mm)", ylabel="angle θ (°)", title="Sinogram at y = 2 mm (−ln T)"); plt.show()
print(f"{len(angles)} angles from {angles[0]:g}° to {angles[-1]:g}°")
'''), md(r"""
## 5. Develop the reconstruction

Back-projection smears each projection back across the slice along its direction: the sum gives the slice, but
blurred (each point becomes a 1/r star). Filtering each projection first with a **ramp** $|k|$ removes the blur
exactly; the ramp also amplifies the noise at high $k$, which a **window** (Hamming) rolls off. Fewer angles give
streaks. Try the combinations: the cell prints $\Sigma$ in the matrix (mean and noise, 20 × 20 pixels at the center).
"""), code(r'''
flt = w.ToggleButtons(options=list(tomo.FILTERS), value="none", description="Filter")
every = w.ToggleButtons(options=[("all angles", 1), ("1 in 2", 2), ("1 in 4", 4)], value=1, description="Angles")
ys = w.FloatSlider(value=2.0, min=-6.5, max=6.5, step=0.11, description="Height y (mm)", continuous_update=True)
img_rec, txt_rec = live_view.FigureImage(), w.HTML()
def rec(_=None):
    r = int(round(ys.value / tomo.PIXEL_MM + 63.5))
    sl_ = tomo.fbp(angles[::every.value], P[::every.value, r, :], filter=flt.value)
    with img_rec:
        fig, ax = plt.subplots(figsize=(5.4, 4.6))
        im = ax.imshow(sl_, origin="lower", extent=EXT, cmap="magma",
                       **({} if flt.value == "none" else dict(vmin=0, vmax=1.2)))
        fig.colorbar(im, ax=ax, label="Σ (cm⁻¹)" if flt.value != "none" else "(not in cm⁻¹)")
        ax.set(xlabel="x (mm)", ylabel="depth z (mm)", title=f"{flt.value}, {len(angles[::every.value])} angles")
    m = sl_[54:74, 54:74]
    txt_rec.value = (f"matrix: Σ = <b>{m.mean():.3f}</b>, noise (std) <b>{m.std():.3f}</b>"
                     + ("  (no filter: not a Σ)" if flt.value == "none" else ""))
for c in (flt, every, ys):
    c.observe(live_view.throttled(rec), "value")
display(w.VBox([flt, every, ys, img_rec, txt_rec])); rec()
'''), md(r"""
## 6. The clasts in 3D

The reconstruction of all the rows with your choice (here: ramp + Hamming, all angles): move through the volume,
count the clasts rich in water, measure their size and depth.
"""), code(r'''
VOL = tomo.reconstruct(TOMO, OPEN, DARK)
px = lambda mm: int(np.clip(round(mm / tomo.PIXEL_MM + 63.5), 0, 127))
yv = w.FloatSlider(value=2.0, min=-6.5, max=6.5, step=0.11, description="Height y (mm)", continuous_update=True)
zv = w.FloatSlider(value=-1.5, min=-6.5, max=6.5, step=0.11, description="Depth z (mm)", continuous_update=True)
img_3d = live_view.FigureImage()
def show3d(_=None):
    with img_3d:
        fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.6))
        kw = dict(origin="lower", extent=EXT, cmap="magma", vmin=0, vmax=1.2)
        im = a.imshow(VOL[px(yv.value)], **kw); a.axhline(zv.value, color="w", lw=0.8, ls="--")
        a.set(xlabel="x (mm)", ylabel="depth z (mm)", title=f"horizontal slice, y = {yv.value:.1f} mm")
        b.imshow(VOL[:, px(zv.value), :], **kw); b.axhline(yv.value, color="w", lw=0.8, ls="--")
        b.set(xlabel="x (mm)", ylabel="y (mm)", title=f"vertical slice, z = {zv.value:.1f} mm")
        fig.colorbar(im, ax=[a, b], label="Σ (cm⁻¹)")
yv.observe(live_view.throttled(show3d), "value"); zv.observe(live_view.throttled(show3d), "value")
display(w.VBox([w.HBox([yv, zv]), img_3d])); show3d()
'''), md(r"""
## 7. Which element, how much?

Two disks of 0.5 mm radius at 0°: the darkest spot (x = 2.5, y = 2.0 mm) and the matrix below it (same chord of the
cylinder). $T_\text{spot}/T_\text{matrix} = e^{-\Delta\Sigma\,L_c}$, with $L_c$ the thickness of clast on the line
of sight (from part 6). Two models of $\Delta\Sigma(\lambda)$ are compared:

- **hydrogen**: $\Delta\Sigma = f\,\Sigma_\text{water}(\lambda)$, $f$ the fraction of the clast's volume that water
  would fill;
- **a denser mineral**: $\Delta\Sigma = c$, the same at all wavelengths.

The reduced χ² tells which describes the data.
"""), code(r'''
Lc = w.BoundedFloatText(value=1.0, min=0.1, max=12, step=0.1, description="L_c (mm)")
img_h, txt_h = live_view.FigureImage(), w.HTML()
lam, (Ts, Tm), (dTs, dTm) = tomo.region_transmission(TOF_SAMPLE, TOF_OPEN)
def hydrogen(_=None):
    with img_h:
        r = Ts / Tm; dr = r * np.hypot(dTs / Ts, dTm / Tm)
        dS, ddS = -np.log(r) / (Lc.value / 10), dr / r / (Lc.value / 10)
        sw = tomo.sigma_water(lam)
        m = (lam > 1.5) & (lam < 7.5) & np.isfinite(dS) & (ddS > 0)
        wgt = 1 / ddS[m] ** 2
        f = np.sum(wgt * dS[m] * sw[m]) / np.sum(wgt * sw[m] ** 2); df = 1 / np.sqrt(np.sum(wgt * sw[m] ** 2))
        c = np.sum(wgt * dS[m]) / np.sum(wgt)
        chi_h = np.sum(((dS[m] - f * sw[m]) / ddS[m]) ** 2) / (m.sum() - 1)
        chi_c = np.sum(((dS[m] - c) / ddS[m]) ** 2) / (m.sum() - 1)
        fig, ax = plt.subplots(figsize=(8.5, 4.4))
        ax.errorbar(lam[m], dS[m], ddS[m], fmt=".", ms=3, color="tab:red", label="ΔΣ measured")
        ax.plot(lam[m], f * sw[m], "b-", label=f"hydrogen: f Σ_water, χ²/ν = {chi_h:.2f}")
        ax.plot(lam[m], np.full(m.sum(), c), "k--", label=f"denser mineral: constant, χ²/ν = {chi_c:.2f}")
        ax.set(xlabel="λ (Å)", ylabel="ΔΣ (cm⁻¹)", title=f"Extra attenuation of the clast (L_c = {Lc.value:.1f} mm)")
        ax.legend(fontsize=9); ax.grid(alpha=0.3)
    txt_h.value = (f"f = <b>{f:.3f} ± {df:.3f}</b>  →  water by mass = f × 1.0 / 2.6 = "
                   f"<b>{100 * f / 2.6:.1f} ± {100 * df / 2.6:.1f} %</b>")
Lc.observe(live_view.throttled(hydrogen), "value")
display(w.VBox([Lc, img_h, txt_h])); hydrogen()
'''), md("## Your results\n\nYour score on the questions of the notebook, and a report to download."), code(r'''
q.choice("Part 5: what does the ramp filter do, and what does the window add?",
         ["The ramp removes the blur of plain back-projection (Σ in cm⁻¹, sharp edges) but amplifies the noise; the "
          "window reduces the noise at the cost of a little sharpness.",
          "The ramp reduces the noise; the window sharpens.", "Both only change the colors."],
         answer=0, why={1: "The other way round: compare the noise printed for 'ramp' and for the window.",
                        2: "Compare the values of Σ printed: without a filter they are not Σ at all."},
         explanation="Back-projection weights low spatial frequencies too much (1/r blur); |k| restores them exactly. "
                     "High k is mostly noise: the Hamming window rolls it off.",
         hints=["Compare the noise and the sharpness of the three filters at the same height."], title="Q2. The filter")
q.choice("Part 5: with 1 angle in 4 (8 angles), what happens?",
         ["Streaks: the slice is under-sampled in angle; the clasts are still there but the matrix gets artifacts.",
          "Nothing: 8 angles are enough for any slice.", "The slice gets brighter."],
         answer=0, why={1: "Look at the streaks around the clasts.", 2: "The mean stays; the artifacts grow."},
         explanation="About (π/2) × (number of pixels across) angles are needed for a slice without streaks; fewer "
                     "angles are a choice of time against artifacts.", hints=["Compare all angles and 1 in 4."],
         title="Q3. The angles")
q.number("Σ of the matrix (part 5 or 6, cm⁻¹):", value=0.24, tol=0.06, unit="cm⁻¹",
         hints=["Ramp + Hamming, a slice without clast at its center."],
         explanation="About 0.24 cm⁻¹ (average over the white beam), consistent with the radiograph (part 3).",
         title="Q4. The matrix")
q.number("How many clasts rich in water (part 6)?", value=5, tol=0.1,
         mistakes=[(4, "two clasts lie one behind the other at 0°: look at the slice y = 2 mm")],
         hints=["Move the height slider through the whole sample."], explanation="Five; two of them make one spot at 0°.",
         title="Q5. The clasts")
q.number("L_c, the thickness of clast on the line of sight of the spot (mm):", value=4.8, tol=0.8, unit="mm",
         hints=["At x = 2.5 mm, y = 2 mm: two clasts, add their diameters."],
         explanation="3.0 + 1.8 = 4.8 mm (the disk of 0.5 mm also sees thinner chords: an effective 4.3–4.5 mm).",
         title="Q6. The thickness")
q.choice("Part 7: which model describes ΔΣ(λ)?",
         ["Hydrogen: χ²/ν near 1, the constant far above.", "The denser mineral.", "Both equally."],
         answer=0, why={1: "ΔΣ grows by a factor 2 from 2 to 6 Å: not a constant.", 2: "Compare the two χ²/ν."},
         explanation="The wavelength dependence identifies hydrogen: its scattering grows at long wavelengths "
                     "(slow neutrons exchange energy with the light, vibrating H atoms).",
         hints=["Compare the χ²/ν in the legend."], title="Q7. The element")
q.number("Water by mass in the clast (part 7, %):", value=5.2, tol=1.6, unit="%",
         hints=["With L_c from Q6."],
         explanation="About 5 % (the model holds 5.7 %: water bound in a mineral scatters a little less than liquid "
                     "water, and the disk sees thinner chords: the estimate is a little low).", title="Q8. How much water")
q.report()
'''), md(r"""
## Submit your work

When you are done: save this notebook (*Save*), write what you thought of the exercise, then submit.
"""), code('import submit\n_ = submit.Submit("odin/exercises/meteorite_imaging", "msc", quiz=q)')]

distribute(msc, [
    ("display(w.VBox([flt, every, ys, img_rec, txt_rec]))", [2, 3, 4]),      # the filter, the angles, the matrix
    ("display(w.VBox([w.HBox([yv, zv]), img_3d]))", [5, 6]),                # the clasts, the thickness
    ("display(w.VBox([Lc, img_h, txt_h]))", [7, 8]),                        # the element, the water
])
write(msc, os.path.join(HERE, "ODIN_meteorite_msc.ipynb"), all_code_locked=True)

bt = [md(r"""
# Beamtime on ODIN: water in a Martian meteorite (starter notebook)

Your proposal (**1250**) is below, with the button *Open NICOS*. This notebook only gives you the tools; what to
measure and how to analyze it is your decision, as at a real beamtime.
"""), md("**Your proposal** (click to open it):"),
    code('import sys, os\nsys.path.insert(0, os.path.abspath("../../.."))\nimport nb_tools\n'
         'nb_tools.proposal("odin/exercises/meteorite_imaging/beamtime.md")'),
    code('nb_tools.nicos("odin")'),
    stop(md("## Your files\n\nNICOS writes them to the folder of the proposal; the logbook is read from the files.")),
    code(SETUP.replace('q = quiz.Quiz("odin_meteorite_msc")       # the questions of this notebook', "")),
    code(r'''
from odin_paths import TWIN_RUN_ROOT
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/1250/raw"     # the folder of your proposal
rows = red.measurements(FOLDER)
for r in rows:
    print(r)
'''), md(r"""
## Tools

- camera images (`radiograph()`, `tomography()` in NICOS): `tomo.image(file)`, `tomo.transmission(sample, open, dark)`,
  `tomo.sinogram(files, open, dark)`, `tomo.fbp(angles, sinogram_of_a_row, filter=...)` (`tomo.FILTERS`),
  `tomo.reconstruct(files, open, dark)` → Σ(y, z, x) in cm⁻¹; `tomo.extent()` for `imshow`;
- event files (time of flight): `tomo.region_transmission(sample, open, dark, regions=[(x, y, r), ...])` → λ, [T], [dT];
  `tomo.sigma_water(lam)`; `red.measurements(FOLDER)`, and the reduction of `odin_reduction`.
"""), code("# your analysis\n"), code(""), md("## Results for the committee\n\n(your answers, with uncertainties, and your logbook)")]
write(bt, os.path.join(HERE, "ODIN_meteorite_beamtime.ipynb"), all_code_locked=False)
