"""Generates the MSc and beamtime notebooks of the exercise "What is hidden inside a Martian meteorite?" (the piece of
NWA 7034 studied by Naver et al., arXiv:2601.08390, 2026):

  * ODIN_meteorite_msc.ipynb       MSc, "develop the method": measure (NICOS or the panel) with the high-resolution
                                   camera, radiograph, sinogram, the reconstruction (filter and number of angles
                                   compared), the clasts in 3D, Σ in a region, the argument of the paper for hydrogen
                                   and the water content;
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
    if not r.get("title", "").startswith("tomography"):
        print(f"{r['file']:20s} {r.get('detector', 'timepix3'):9s} {r.get('pixels', '-')!s:4s} {r['kind']:10s} "
              f"{r.get('title', '')[:26]:26s} t = {r.get('t_s', 0):5.0f} s  {r.get('choppers')}  pinhole {r.get('pinhole_m')}")
print(sum(r.get("title", "").startswith("tomography") for r in rows), "images of tomography")
'''
PICK = r'''
path = lambda r: os.path.join(FOLDER, r["file"])
hr = [r for r in rows if r.get("detector") == "camera" and r.get("pixels") == 512]      # the high-resolution images
single = [r for r in hr if not r.get("title", "").startswith("tomography")]
DARK = next((path(r) for r in reversed(single) if r["kind"] == "dark"), None)
OPEN = next((path(r) for r in reversed(single) if r["kind"] == "open beam"), None)
RADIO = next((path(r) for r in reversed(single) if r["kind"] == "sample"), None)
TOMO = []                                  # the last tomography: its images from the one at 0° on
for r in hr:
    if r.get("title", "").startswith("tomography") and r["kind"] == "sample":
        if r["stage_rot_deg"] == 0:
            TOMO = []
        TOMO.append(path(r))
name = lambda f: f and os.path.basename(f)
print(f"high resolution: dark {name(DARK)}, open beam {name(OPEN)}, radiograph {name(RADIO)}, tomography {len(TOMO)} images")
'''

msc = [md(r"""
# What is hidden inside a Martian meteorite? (MSc: develop the method)

**Your mission.** The team of planetary scientists wants a method it can trust to find water inside precious
meteorites without cutting them: where it is (3D), and how much. You develop it on the piece of the Martian meteorite
NWA 7034 imaged by E. B. Naver, K. W. Nikolajsen *et al.*, *Direct detection of hydrogen reveals a new macroscopic
crustal water reservoir on early Mars*, arXiv:2601.08390 (2026): 12 × 8 × 2 mm³, with hydrogen-rich clasts of 0.1 to
0.4 mm (0.4 % of the volume). The twin's model of the piece follows their numbers (sizes, amounts, the neutron
attenuations they measured at ICON); the positions of the clasts are random.

**The physics.** The transmission of a line through the sample is $T = e^{-\int \Sigma\, dl}$. A tomography measures
$p(\theta, x') = -\ln T$ for many angles $\theta$ (the sinogram) and recovers $\Sigma(x, z)$ of each horizontal slice
by filtered back-projection. Hydrogen has a huge (incoherent) scattering cross-section: a region with hydrogen has a
$\Sigma$ that no anhydrous mineral reaches. This is the argument of the paper, which you will reproduce.

The code of each step is given (and locked): read it, run it, and make the decisions with the widgets.
"""), code(SETUP), md("## The sample"), code(SAMPLE), md(r"""
## Before you measure

The clasts are 0.1 to 0.4 mm, their contrast a few % through 2 mm of rock: the **high-resolution** setup is needed,
512 × 512 pixels of 27.5 µm and the 1 cm pinhole (blur $l D / L$ = 48 µm), with the choppers stopped (white beam):
1. a **dark** (shutter closed) of 300 s and an **open beam** (sample out: stage x = 500 mm) of **1500 s** (it divides
   every image: its noise must be low, or it draws rings in the slices);
2. a **radiograph** at 0° of 300 s;
3. a **tomography**: one image of 300 s every 3° from 0 to 177° (60 images, 5 h of beam).

Naver *et al.* took 1125 images of 4 min at ICON (pixels of 6.2 µm, L/D = 350): 75 hours.
"""), code(r'''
q.choice("Why does a tomography with a parallel beam need 180° only, not 360°?",
         ["Turning by 180° shows the same lines through the sample, crossed in the other direction: the same "
          "projection, mirrored.", "To save time: 360° would be better but too long.",
          "Because the stage cannot turn further."],
         answer=0, why={1: "The extra 180° hold no new information (only less noise, as longer images would).",
                        2: "It can (−180° to 180°)."},
         explanation="With parallel rays, p(θ + 180°, x') = p(θ, −x'). A cone beam (X-ray tubes) needs 360°; the "
                     "beam of ODIN is nearly parallel (L/D large). Naver et al. turned the piece by 360° at ICON: more "
                     "images, less noise.", hints=["Draw the lines through the sample at θ and at θ + 180°."],
         title="Q1. 180°")
'''), md(r"""
## 0. Your measurements

Choose how: **in NICOS** (the commands below, one at a time), or **here, with a panel** (the same devices, with
*Camera image*, *Run the tomography* and the choice of the camera). Either way your files go to the folder of
proposal 1250.
"""), code(f'import measure_panel\nmeasure_panel.Panel("odin", proposal="{PROPOSAL}", samples=["meteorite_nwa7034"])'),
    nicos_step(md(r"""
### Step 1. Your proposal

In NICOS, tab **Experiment**, **Find my proposal**, choose **1250** (*Water in a Martian meteorite*), then **Apply**:
the piece is mounted on the rotation stage. Then tab **Instrument interaction**, one command at a time.
""")), nicos_step(md(r"""
### Step 2. White beam, high resolution: dark, open beam, radiograph

`radiograph(t, title, pixels)` takes one image with the integrating camera; `pixels=512`: the high-resolution camera.

```
move(choppers, 'white', pinhole, 0.01, diffuser, 'in')
move(shutter, 'closed')
radiograph(300, 'dark', 512)
move(shutter, 'open', stage_x, 500)
radiograph(1500, 'open beam', 512)
move(stage_x, 0, stage_rot, 0)
radiograph(300, 'meteorite 0 deg', 512)
```
""")), nicos_step(md(r"""
### Step 3. The tomography

`tomography(t, step, title, pixels)`: one image of t seconds every `step` degrees from 0 to 180° (excluded), then
back to 0°.

```
tomography(300, 3, 'tomography', 512)
```
""")),
    stop(md(r"""
## 1. Your files

Read from the files themselves: camera images (`camera`, with their number of pixels) and event files (`timepix3`).
""")), code(FILES), md("## 2. Which file is what?"), code(PICK), md(r"""
## 3. The radiograph

$T = (I - D)/(O - D)$, each image per second of exposure. At 0° the beam crosses the 2 mm thickness of the piece: in
the matrix, $T = e^{-\Sigma \cdot 0.2\,\text{cm}}$; the cell estimates $\Sigma$ of the matrix from a region of the
piece.
"""), code(r'''
T = tomo.transmission(RADIO, OPEN, DARK)
n = T.shape[0]
fig, ax = plt.subplots(figsize=(5.5, 4.6))
im = ax.imshow(T, origin="lower", extent=EXT, cmap="gray", vmin=0.8, vmax=1.0)
fig.colorbar(im, ax=ax, label="T"); ax.set(xlabel="x (mm)", ylabel="y (mm)", title=f"Radiograph at 0° ({n} px)"); plt.show()
c = T[n // 2 - 40:n // 2 + 40, n // 2 - 40:n // 2 + 40]          # 2.2 × 2.2 mm at the center
print(f"T at the center: {c.mean():.4f} ± {c.std() / np.sqrt(c.size):.4f}  ->  Σ = −ln T / 0.2 cm = "
      f"{-np.log(c.mean()) / 0.2:.3f} cm⁻¹ (mostly matrix on these lines)")
'''), md(r"""
## 4. The sinogram

For one row of pixels (height $y$), the projections $-\ln T$ of all the angles, one line per angle: each point of the
slice draws a sine curve $x' = x\cos\theta + z\sin\theta$ (hence the name). The piece (8 × 2 mm) makes a band whose
width swings between 2 and 8 mm.
"""), code(r'''
if not TOMO:
    raise SystemExit("No tomography yet (part 0, step 3).")
angles, P = tomo.sinogram(TOMO, OPEN, DARK)
n = P.shape[2]
row = int(round(4.6 / tomo.pixel_mm(n) + (n - 1) / 2))         # y = 4.6 mm
fig, ax = plt.subplots(figsize=(7, 4))
ax.imshow(P[:, row, :], aspect="auto", origin="lower", cmap="magma",
          extent=(EXT[0], EXT[1], angles[0], angles[-1] + np.median(np.diff(angles))))
ax.set(xlabel="x' on the camera (mm)", ylabel="angle θ (°)", title="Sinogram at y = 4.6 mm (−ln T)"); plt.show()
print(f"{len(angles)} angles from {angles[0]:g}° to {angles[-1]:g}°, images of {n} × {n} pixels")
'''), md(r"""
## 5. Develop the reconstruction

Back-projection smears each projection back across the slice along its direction: the sum gives the slice, but
blurred (each point becomes a 1/r star). Filtering each projection first with a **ramp** $|k|$ removes the blur
exactly; the ramp also amplifies the noise at high $k$, which a **window** (Hamming) rolls off. Fewer angles give
streaks. Try the combinations: the cell prints $\Sigma$ in the matrix (mean and noise) at the center of the slice.
"""), code(r'''
flt = w.ToggleButtons(options=list(tomo.FILTERS), value="none", description="Filter")
every = w.ToggleButtons(options=[("all angles", 1), ("1 in 2", 2), ("1 in 4", 4)], value=1, description="Angles")
ys = w.FloatSlider(value=4.6, min=-6.0, max=6.0, step=0.0275, description="Height y (mm)", continuous_update=True)
img_rec, txt_rec = live_view.FigureImage(), w.HTML()
def rec(_=None):
    r = int(round(ys.value / tomo.pixel_mm(n) + (n - 1) / 2))
    sl_ = tomo.fbp(angles[::every.value], P[::every.value, r, :], pixel_mm=tomo.pixel_mm(n), filter=flt.value)
    with img_rec:
        fig, ax = plt.subplots(figsize=(8, 3.6))
        im = ax.imshow(sl_, origin="lower", extent=EXT, cmap="magma",
                       **({} if flt.value == "none" else dict(vmin=0, vmax=2.0)))
        fig.colorbar(im, ax=ax, label="Σ (cm⁻¹)" if flt.value != "none" else "(not in cm⁻¹)")
        ax.set(xlim=(-4.6, 4.6), ylim=(-1.6, 1.6), xlabel="x (mm)", ylabel="depth z (mm)",
               title=f"{flt.value}, {len(angles[::every.value])} angles")
    m = sl_[n // 2 - 15:n // 2 + 15, n // 2 - 60:n // 2 + 60]
    txt_rec.value = (f"matrix at the center: Σ = <b>{m.mean():.3f}</b>, noise (std) <b>{m.std():.3f}</b>"
                     + ("  (no filter: not a Σ)" if flt.value == "none" else ""))
for c in (flt, every, ys):
    c.observe(live_view.throttled(rec), "value")
display(w.VBox([flt, every, ys, img_rec, txt_rec])); rec()
'''), md(r"""
## 6. The clasts in 3D, and Σ in a region

The reconstruction with ramp + Hamming and all angles, slice by slice on demand (`tomo.Reconstruction`). Move the
cross (+) onto a bright spot: the button gives $\Sigma$ in a ball of 0.06 mm radius around it, $\Sigma$ of the matrix
around (0.4 to 0.6 mm away, the median) and their ratio.
"""), code(r'''
REC = tomo.Reconstruction(TOMO, OPEN, DARK)
yv = w.FloatSlider(value=4.6, min=-6.0, max=6.0, step=0.0275, description="Height y (mm)", continuous_update=True, readout_format=".2f")
zv = w.FloatSlider(value=0.0, min=-1.0, max=1.0, step=0.0275, description="Depth z (mm)", continuous_update=True, readout_format=".2f")
xv = w.FloatSlider(value=0.0, min=-4.0, max=4.0, step=0.0275, description="Point x (mm)", continuous_update=True, readout_format=".2f")
img_3d, txt_3d = live_view.FigureImage(), w.HTML()
def show3d(_=None):
    h, v = REC.horizontal(yv.value), REC.vertical(zv.value)
    with img_3d:
        fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw=dict(width_ratios=[1.6, 1]))
        kw = dict(origin="lower", extent=EXT, cmap="magma", vmin=0, vmax=2.0)
        im = a.imshow(h, **kw); a.plot(xv.value, zv.value, "c+", ms=14, mew=1.5)
        a.set(xlim=(-4.6, 4.6), ylim=(-1.6, 1.6), xlabel="x (mm)", ylabel="depth z (mm)", title=f"y = {yv.value:.2f} mm")
        b.imshow(v, **kw); b.plot(xv.value, yv.value, "c+", ms=10, mew=1.5)
        b.set(xlim=(-4.6, 4.6), ylim=(-6.6, 6.6), xlabel="x (mm)", ylabel="y (mm)", title=f"z = {zv.value:.2f} mm")
        fig.colorbar(im, ax=[a, b], label="Σ (cm⁻¹)", shrink=0.8)
ROI = {}
def roi(_=None):
    spot = REC.value(xv.value, yv.value, zv.value, 0.06)
    ring = [REC.value(xv.value + d * np.cos(t), yv.value, float(np.clip(zv.value + d * np.sin(t), -0.85, 0.85)), 0.04)
            for d in (0.4, 0.6) for t in np.linspace(0, 2 * np.pi, 12, endpoint=False)]
    mat = float(np.median(ring))
    ROI.update(spot=spot, matrix=mat)
    txt_3d.value = (f"Σ at the cross: <b>{spot:.2f} cm⁻¹</b>; matrix around: <b>{mat:.2f} cm⁻¹</b>; "
                    f"ratio <b>{spot / mat:.1f}</b>")
for c in (yv, zv, xv):
    c.observe(live_view.throttled(show3d), "value")
button_roi = w.Button(description="Σ at the cross", button_style="success", icon="crosshairs", layout=w.Layout(width="auto"))
button_roi.on_click(roi)
display(w.VBox([yv, zv, xv, img_3d, button_roi, txt_3d])); show3d()
'''), md(r"""
## 7. Which element, how much?

Naver *et al.* computed $\Sigma$ of the minerals of NWA 7034 at 25 meV (their Table S1) and measured the matrix at
ICON (0.45 cm⁻¹): plagioclase 0.27–0.28, pyroxenes 0.34–0.38, chlorapatite 0.34, ilmenite 0.70, magnetite and
maghemite 0.80–0.82 cm⁻¹, that is at most **1.8 times** the matrix. Ratios hardly depend on the spectrum of the beam
(ODIN's white beam is colder than ICON's: all the values are higher here). Assuming, as the paper, that all the excess
attenuation is due to hydrogen, the fraction of the region that water would fill is
$f = (\Sigma_\text{spot} - \Sigma_\text{clast}) / \Sigma_\text{water}$, with $\Sigma_\text{clast}$ the clast without
hydrogen (0.57 cm⁻¹ at ICON) and $\Sigma_\text{water}$; the cell computes both in ODIN's beam (`effective_sigma`, the
spectrum of the camera), then the water by mass (region of 3.0 g/cm³).
"""), code(r'''
from odin_virtual import VirtualOdin
spec_cam = VirtualOdin(session="spectrum").camera_spectrum()
mats = sl.load("odin")["meteorite_nwa7034"]["materials"]
S_CLAST = tomo.effective_sigma(mats["clast (low H)"], spec_cam)
S_WATER = tomo.effective_sigma("stdlib::LiquidWaterH2O_T293.6K.ncmat", spec_cam)
print(f"in ODIN's white beam: Σ_clast = {S_CLAST:.2f} cm⁻¹, Σ_water = {S_WATER:.2f} cm⁻¹")
if ROI:
    f = (ROI["spot"] - S_CLAST) / S_WATER
    print(f"your spot: Σ = {ROI['spot']:.2f} cm⁻¹, ratio to the matrix {ROI['spot'] / ROI['matrix']:.1f}; "
          f"f = {f:.2f} -> water by mass = {100 * f / 3.0:.0f} %")
else:
    print("Measure Σ at a bright spot first (part 6), then run this cell again (Analyze my files).")
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
q.choice("Part 5: with 1 angle in 4 (15 angles), what happens?",
         ["Streaks: the slice is under-sampled in angle; large features remain, small clasts drown in artifacts.",
          "Nothing: 15 angles are enough for any slice.", "The slice gets brighter."],
         answer=0, why={1: "Look at the streaks around the piece.", 2: "The mean stays; the artifacts grow."},
         explanation="About (π/2) × (number of pixels across the object) angles are needed for a slice without streaks: "
                     "for 8 mm at 27.5 µm, about 450. Fewer angles trade time against artifacts; Naver et al. took 1125.",
         hints=["Compare all angles and 1 in 4."], title="Q3. The angles")
q.number("Σ of the matrix (part 3 or 6, cm⁻¹, in ODIN's white beam):", value=0.55, tol=0.08, unit="cm⁻¹",
         hints=["Part 3 prints it from the radiograph; part 6 around the cross."],
         explanation="About 0.53–0.56 cm⁻¹ here (0.45 cm⁻¹ at ICON, whose beam is warmer).", title="Q4. The matrix")
q.choice("Where is the hydrogen?",
         ["In small bright regions (0.1–0.4 mm) grouped in clusters.", "Evenly in the whole piece.",
          "Only at the surface.", "In the dark elongated grains."],
         answer=0, why={1: "Look at the bright spots.", 2: "The bright spots are inside, at all depths.",
                        3: "The dark elongated grains are feldspar: Σ smaller than the matrix."},
         explanation="Naver et al.: H-rich phases in localised macroscopic clusters, 0.4 vol%.",
         hints=["Move the height slider of part 6 through the piece."], title="Q5. Where?")
q.number("The ratio Σ(spot) / Σ(matrix) at the brightest spot you found (part 6):", value=4.0, tol=1.6,
         hints=["The largest clasts are near y = 4.6 mm; put the cross on the brightest pixels."],
         explanation="About 4 in the middle of a large H-rich region (Naver et al.: 1.9 / 0.45 = 4.2 at ICON).",
         title="Q6. The ratio")
q.choice("Part 7: what does the ratio tell?",
         ["No anhydrous mineral reaches 1.8 times the matrix: a ratio of 4 needs hydrogen.",
          "The spot is magnetite.", "The spot is a pore.", "Nothing: the ratio depends on the beam."],
         answer=0, why={1: "Magnetite is 1.8 times the matrix.", 2: "A pore would be darker than the matrix (Σ ≈ 0).",
                        3: "Ratios hardly depend on the spectrum: this is why they are used."},
         explanation="The argument of the paper: measured 1.9 cm⁻¹ against 0.61 cm⁻¹ computed for the same minerals "
                     "without hydrogen.", hints=["Compare with the minerals of Table S1."], title="Q7. The element")
q.number("Water by mass in the brightest spot (part 7, %):", value=10, tol=6, unit="%",
         hints=["Part 7 computes it from Σ at the cross."],
         explanation="The model holds about 14 % (the paper: up to 15 wt% OH); the blur lowers Σ in the middle of a "
                     "small region, so the estimate is lower.", title="Q8. How much water")
q.number("These clasts hold 635 ppm of the 6000 ppm of water of the meteorite (Naver et al.). What share (%)?",
         value=10.6, tol=1.0, unit="%", hints=["635 / 6000."], explanation="11 %, as in the paper.",
         title="Q9. Their share")
q.report()
'''), md(r"""
## Submit your work

When you are done: save this notebook (*Save*), write what you thought of the exercise, then submit.
"""), code('import submit\n_ = submit.Submit("odin/exercises/meteorite_imaging", "msc", quiz=q)')]

distribute(msc, [
    ("display(w.VBox([flt, every, ys, img_rec, txt_rec]))", [2, 3, 4]),
    ("display(w.VBox([yv, zv, xv, img_3d, button_roi, txt_3d]))", [5, 6]),
    ('print("Measure Σ at a bright spot first', [7, 8, 9]),
])
write(msc, os.path.join(HERE, "ODIN_meteorite_msc.ipynb"), all_code_locked=True)

bt = [md(r"""
# Beamtime on ODIN: water in a Martian meteorite (starter notebook)

Your proposal (**1250**) is below, with the button *Open NICOS*. This notebook only gives you the tools; what to
measure and how to analyze it is your decision, as at a real beamtime. The sample: the piece of NWA 7034 of Naver et
al., arXiv:2601.08390 (2026).
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

- camera images (`radiograph(t, title, pixels)`, `tomography(t, step, title, pixels)` in NICOS; pixels 128 or 512):
  `tomo.image(file)`, `tomo.transmission(sample, open, dark)`, `tomo.sinogram(files, open, dark)`,
  `tomo.fbp(angles, sinogram_of_a_row, pixel_mm=tomo.pixel_mm(n), filter=...)` (`tomo.FILTERS`),
  `rec = tomo.Reconstruction(files, open, dark)`: `rec.horizontal(y_mm)`, `rec.vertical(z_mm)`,
  `rec.value(x_mm, y_mm, z_mm, r_mm)`; `tomo.extent()` for `imshow`;
- `tomo.effective_sigma(ncrystal_cfg, spectrum)` with `VirtualOdin(session="s").camera_spectrum()`: Σ of a material
  in ODIN's white beam (to compare with Naver et al., Table S1, at 25 meV);
- `red.measurements(FOLDER)`, and the reduction of `odin_reduction` for time-of-flight files.
"""), code("# your analysis\n"), code(""), md("## Results for the committee\n\n(your answers, with uncertainties, and your logbook)")]
write(bt, os.path.join(HERE, "ODIN_meteorite_beamtime.ipynb"), all_code_locked=False)
