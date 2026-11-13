"""Generates the MSc and beamtime notebooks of the exercise "How does lithium enter a battery electrode?":

  * ODIN_battery_msc.ipynb       MSc, "develop the method": measure (NICOS or the panel), read the files, the reference
                                 (pristine cell or open beam: a choice), the width averaged (noise against what is
                                 averaged), the conversion of Δμ into lithium (white beam: effective Σ or a single
                                 wavelength, a choice), the lithium against the charge passed, the irreversible
                                 capacity;
  * ODIN_battery_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only (beamtime.md).

    python gen_notebooks.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from nbgen import code, distribute, md, nicos_step, stop, write  # noqa: E402

PROPOSAL = "1260"
SETUP = r'''
import sys, os, json, datetime, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
import odin_reduction as red, odin_radiography as tomo, odin_mcstas as tw
import sample_library as sl
import live_view                  # figures that follow the sliders
import quiz
q = quiz.Quiz("odin_battery_msc")       # the questions of this notebook
EXT = tomo.extent()
CHORD_CM = 1.6                  # the beam crosses the electrode along its diameter
MATS = sl.load("odin")["battery_graphite"]["materials"]
'''
FILES = r'''
from odin_paths import TWIN_RUN_ROOT
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/@@PROPOSAL@@/raw"
rows = [r for r in red.measurements(FOLDER) if r.get("detector") == "camera"]
if not rows:
    raise SystemExit("No camera image yet in " + FOLDER + ": measure first (part 0).")
for r in rows:
    print(f"{r['file']:20s} {r['kind']:10s} {r.get('pixels')!s:4s} px  t = {r['t_s']:4.0f} s  pinhole {r['pinhole_m']}  "
          f"cycle {r.get('cycle_time_h', '-')} h  {r['title'][:30]}")
'''
PICK = r'''
path = lambda r: os.path.join(FOLDER, r["file"])
hr = [r for r in rows if r.get("pixels") == 512]
DARK = next((path(r) for r in reversed(hr) if r["kind"] == "dark"), None)
OPEN = next((path(r) for r in reversed(hr) if r["kind"] == "open beam"), None)
CELL = {}
for r in hr:
    if r["kind"] == "sample" and "cycle_time_h" in r:
        CELL[r["cycle_time_h"]] = path(r)                # the newest image at each time of the cycle
CELL = dict(sorted(CELL.items()))
print(f"dark {DARK and os.path.basename(DARK)}, open beam {OPEN and os.path.basename(OPEN)}, cell at {len(CELL)} times:",
      ", ".join(f"{t:g}" for t in CELL), "h")
'''
PROFILES = r'''
if not (DARK and OPEN and 0.0 in CELL):
    raise SystemExit("Needed: a dark, an open beam and the cell at 0 h (part 0).")
img = lambda f: tomo.image(f)["data"] / tomo.image(f)["t"]           # counts per second
D, O = img(DARK), img(OPEN)
n = D.shape[0]
xc = np.linspace(EXT[0], EXT[1], n + 1)[:-1] + (EXT[1] - EXT[0]) / (2 * n)
y = xc.copy()
IMG = {t: img(p) for t, p in CELL.items()}
reference = w.ToggleButtons(options=[("the pristine cell (0 h)", "pristine"), ("the open beam", "open")],
                            value="pristine", description="Reference")
half = w.FloatSlider(value=2.75, min=0.25, max=6.5, step=0.25, description="± x (mm)", continuous_update=True)
t_pick = w.SelectionSlider(options=list(CELL), value=list(CELL)[min(2, len(CELL) - 1)], description="time (h)",
                           continuous_update=True, layout=w.Layout(width="520px"))
img_p, txt_p = live_view.FigureImage(), w.HTML()
def mu_profile(t):
    c = np.abs(xc) <= half.value
    T = np.clip((IMG[t] - D)[:, c].mean(1) / (O - D)[:, c].mean(1), 1e-6, None)
    if reference.value == "open":
        return -np.log(T) / CHORD_CM
    T0 = np.clip((IMG[0.0] - D)[:, c].mean(1) / (O - D)[:, c].mean(1), 1e-6, None)
    return -np.log(T / T0) / CHORD_CM
def draw_p(_=None):
    m = mu_profile(t_pick.value)
    with img_p:
        fig, ax = plt.subplots(figsize=(10, 3.8))
        ax.axvspan(0, 0.4, color="tab:orange", alpha=0.12); ax.axvspan(-0.26, 0, color="0.85", alpha=0.6)
        ax.plot(y, m, color="tab:red")
        ax.set(xlim=(-0.6, 0.6), xlabel="y (mm)", ylabel="μ (cm⁻¹)" if reference.value == "open" else "Δμ (cm⁻¹)",
               title=f"{t_pick.value:g} h, reference: {reference.value}, x within ±{half.value:g} mm")
        ax.grid(alpha=0.3); plt.tight_layout()
    e = (y > 0.03) & (y < 0.37)
    flat = (y > -0.2) & (y < -0.05)                 # in the separator, which does not change
    txt_p.value = (f"mean in the electrode <b>{m[e].mean():.3f}</b> cm⁻¹; scatter of the rows in the separator "
                   f"(noise) <b>{m[flat].std():.3f}</b> cm⁻¹")
for c in (reference, half, t_pick):
    c.observe(live_view.throttled(draw_p), "value")
display(w.VBox([reference, half, t_pick, img_p, txt_p])); draw_p()
'''
CONVERT = r'''
from odin_virtual import VirtualOdin
_o = VirtualOdin(session="spectrum"); _o.move(choppers="white", pinhole=0.01)
LAM, WGT = _o.camera_spectrum()                       # the spectrum the camera sees in the open beam
k1 = max(float(m.split("=")[1]) for m in MATS if m.startswith("graphite x="))
S0 = tw.sigma_tot(MATS["graphite x=0.00"], LAM)
DS = (tw.sigma_tot(MATS[f"graphite x={k1:.2f}"], LAM) - S0) / k1              # Σ added per unit of x
W_T = WGT * np.exp(-S0 * CHORD_CM - tw.sigma_tot(MATS["PTFE"], LAM) * 0.2 - tw.sigma_tot(MATS["aluminium"], LAM) * 0.4)
XS = np.linspace(0, 1.3, 131)
conv = w.ToggleButtons(options=[("open-beam spectrum (Δμ ∝ x)", "open"), ("spectrum transmitted by the cell", "hard")],
                       value="open", description="Δμ(x) with", style={"button_width": "260px"})
img_x, txt_x = live_view.FigureImage(), w.HTML()
RES = {}
def dmu_of_x():
    if conv.value == "open":
        return XS * np.sum(WGT * DS) / np.sum(WGT)
    return np.array([-np.log(np.sum(W_T * np.exp(-CHORD_CM * x * DS)) / np.sum(W_T)) / CHORD_CM for x in XS])
def draw_x(_=None):
    d = dmu_of_x()
    times = np.array(list(CELL))
    e = (y > 0.03) & (y < 0.37)
    old = reference.value
    reference.value = "pristine"
    x_img = np.interp(np.array([mu_profile(t)[e].mean() for t in times]), d, XS)
    reference.value = old
    x_charge = np.where(times <= 30, times / 35, np.maximum(30 / 35 - (times - 30) / 35, 0.27))
    RES.update(x=x_img, t=times)
    with img_x:
        fig, ax = plt.subplots(1, 2, figsize=(12, 3.8))
        ax[0].plot(XS, d, color="tab:blue"); ax[0].set(xlabel="x in LiₓC₆", ylabel="Δμ (cm⁻¹)", title="Δμ(x) used")
        ax[1].plot(times, x_img, "o-", label="from the images")
        ax[1].plot(times, x_charge, "--", color="0.4", label="from the charge (cycler)")
        ax[1].set(xlabel="time of the cycle (h)", ylabel="mean x in LiₓC₆"); ax[1].legend()
        for a_ in ax:
            a_.grid(alpha=0.3)
        plt.tight_layout()
    i30 = int(np.argmin(np.abs(times - 30)))
    txt_x.value = (f"Δμ for x = 1: <b>{np.interp(1, XS, d):.2f} cm⁻¹</b> ({conv.value}); x at 30 h: "
                   f"<b>{x_img[i30]:.2f}</b> (charge: {30 / 35:.2f}); after the cycle: <b>{x_img[-1]:.2f}</b> → "
                   f"irreversible capacity <b>{x_img[-1] * 372:.0f} mAh/g</b>")
conv.observe(live_view.throttled(draw_x), "value")
display(w.VBox([conv, img_x, txt_x])); draw_x()
'''
QUESTIONS = r'''
q.choice("Part 3: with the open beam as reference, the profile of the electrode is high from the start. Why use the "
         "pristine cell?",
         ["The open-beam reference gives μ of everything on the line (casing, PTFE, electrolyte, graphite); the pristine "
          "cell cancels what does not change and leaves the lithium that moved.",
          "The open beam is noisier.", "The pristine cell is brighter.", "The open beam includes the dark."],
         answer=0, why={1: "Both are images of 60 s.", 2: "It is darker than the open beam.",
                        3: "The dark is subtracted from both."},
         explanation="As Strobl et al.: μ integrates all phases on the path; only the change is the lithium.",
         hints=["Switch the reference and compare at 0 h."], title="Q1. The reference")
q.choice("Part 3: averaging the rows over ±6.5 mm instead of ±0.5 mm:",
         ["13 times more pixels: about 3.6 times less noise; it assumes the lithium is the same along x, which the "
          "electrode is built for (a flat disk), though the path through it gets shorter away from the center.",
          "Changes the mean value a lot.", "Blurs the profile in y.", "Has no effect on the noise."],
         answer=0, why={1: "Compare: it hardly changes.", 2: "It averages along x, not y.",
                        3: "Look at the noise printed."},
         explanation="Averaging along the layers trades lateral information for noise: √N. Near the edge of the disk "
                     "the path is shorter than 16 mm: a bias if D is taken as 16 mm everywhere.",
         hints=["Compare the noise printed for both widths."], title="Q2. Averaging")
q.choice("Part 4: the two conversions give different x. Which one is right, and why?",
         ["The transmitted spectrum: the white beam is hardened by 16 mm of cell (the slow neutrons, which lithium "
          "absorbs most, are already removed), so the open-beam spectrum overestimates Δμ per unit of x and "
          "underestimates x.", "The open-beam spectrum: it is simpler.", "They are equal.",
          "Neither: x cannot be measured."],
         answer=0, why={1: "Simpler, but biased.", 2: "Compare the values printed.",
                        3: "It can, within the accuracy of the conversion."},
         explanation="Beam hardening is the classic bias of white-beam quantification; wavelength-resolved imaging (as "
                     "Strobl et al. at SENJU) avoids it.", hints=["Compare with the charge at 30 h."],
         title="Q3. Beam hardening")
q.number("Part 4: x after the whole cycle (spectrum transmitted by the cell):", value=0.27, tol=0.1, hints=["Part 4 prints it."],
         explanation="About 0.27: the irreversible loss of the first cycle.", title="Q4. Lost lithium")
q.number("The irreversible capacity of the first cycle, in mAh/g (372 mAh/g for x = 1):", value=100, tol=35,
         unit="mAh/g", hints=["x × 372."], explanation="About 100 mAh/g, as in the paper (of which about 40 mAh/g "
                                                       "can be ascribed to the SEI).", title="Q5. In mAh/g")
q.report()
'''


def msc():
    cells = [md(r"""
# How does lithium enter a battery electrode? (MSc: develop the method)

**Your mission.** You work for a battery maker that tests ultra-thick electrodes. You need a method you can trust to
measure, inside a working cell, how much lithium is in the electrode at each depth and time, from the raw images to
numbers comparable with the charge counted by the cycler; and you find out what biases it. You develop it on the
half-cell of M. Strobl, M. E. Baur, L. Theil Kuhn *et al.*, Adv. Energy Mater. (2025) (SENJU, J-PARC; the cell of
M.-E. Lăcătuşu *et al.*, arXiv:2104.03564): a 0.4 mm graphite electrode, a glass-fiber separator and lithium metal,
16 mm in diameter, seen edge-on, cycled at C/35. The lithium profiles of the twin are a model built on their findings.

**The physics.** Lithium absorbs neutrons (70 b at 1.8 Å for natural Li, in proportion to λ). Through a line of length
$D$ the transmission is $T = e^{-\int\mu\,dl}$; divided by the pristine cell, $\Delta\mu = -\ln(T/T_0)/D$ is the change
due to the lithium, proportional to its amount: $x \approx \Delta\mu / \Delta\mu_1$, with $\Delta\mu_1$ the change for
one Li per C₆, which depends on the spectrum.

The code of each step is given (and locked): read it, run it, and make the decisions with the widgets.
"""), code(SETUP), md("## The sample"), code(r'''
spec = sl.load("odin")["battery_graphite"]
print(sl.describe("odin", spec, ["materials"]))
sl.draw("odin", spec, hidden=["materials"], fig=plt.figure(figsize=(10, 3.5))); sl.show()
'''), md(r"""
## Before you measure

High-resolution camera (512 px of 27.5 µm), white beam, pinhole 1 cm, images of 60 s: a dark, an open beam, then the
cell every 2.5 h of the cycle from 0 to 55 h (the device `cycle_time`).
"""), code(r'''
q.number("Through 16 mm of electrode with Δμ = 1 cm⁻¹ of lithium, by what factor does the transmission drop?",
         value=0.20, tol=0.02, hints=["e^(−1 × 1.6)."], explanation="e^(−1.6) = 0.20: a strong contrast, which is why "
         "the cell is seen edge-on, along the layers.", title="Q0. Contrast")
'''), md(f"""
## 0. Your measurements

Choose how: **in NICOS** (the commands below), or **here, with a panel** (*Camera image*, the *Battery cycler* and
*Film the cycle*; set the camera to high resolution). Either way your files go to the folder of proposal {PROPOSAL}.
"""), code(f'import measure_panel\nmeasure_panel.Panel("odin", proposal="{PROPOSAL}", samples=["battery_graphite"])'),
        nicos_step(md(f"""
### Step 1. Your proposal

In NICOS, tab **Experiment**, **Find my proposal**, choose **{PROPOSAL}**, then **Apply**. Then tab **Instrument
interaction**.
""")), nicos_step(md(r"""
### Step 2. Dark, open beam, the film of the cycle

```
move(choppers, 'white', pinhole, 0.01, diffuser, 'in')
move(shutter, 'closed')
radiograph(60, 'dark', 512)
move(shutter, 'open', stage_x, 500)
radiograph(60, 'open beam', 512)
move(stage_x, 0)
for k in range(23):
    move(cycle_time, 2.5 * k)
    radiograph(60, 'cell %g h' % (2.5 * k), 512)
```
""")), stop(md("## 1. Your files")), code(FILES.replace("@@PROPOSAL@@", PROPOSAL)), md("## 2. Which file is what?"),
        code(PICK), md(r"""
## 3. Profiles across the electrode

**Your decisions:** the reference (the pristine cell, or the open beam), and how wide a band along $x$ is averaged
(the noise is printed: the scatter of the rows in the separator, where nothing changes).
"""), code(PROFILES), md(r"""
## 4. From Δμ to lithium, and the charge

**Your decision:** how $\Delta\mu$ depends on $x$: computed with the spectrum of the open beam (then $\Delta\mu$ is
proportional to $x$), or with the spectrum transmitted by the pristine cell along the line of the electrode (16 mm of
electrode, 2 mm of PTFE, 4 mm of aluminium). The cycler passed $x = t/35$
during the lithiation (C/35), then removed it until only the irreversible part was left.
"""), code(CONVERT), md("## Your results\n\nYour score on the questions of the notebook, and a report to download."),
        code(QUESTIONS), md(r"""
## Submit your work

When you are done: save this notebook (*Save*), write what you thought of the exercise, then submit.
"""), code('import submit\n_ = submit.Submit("odin/exercises/battery_operando", "msc", quiz=q)')]
    distribute(cells, [
        ("display(w.VBox([reference, half, t_pick, img_p, txt_p]))", [1, 2]),
        ("display(w.VBox([conv, img_x, txt_x]))", [3, 4, 5]),
    ])
    write(cells, os.path.join(HERE, "ODIN_battery_msc.ipynb"), all_code_locked=True)


def beamtime():
    bt = [md(f"""
# Beamtime on ODIN: lithium in a thick battery electrode (starter notebook)

Your proposal (**{PROPOSAL}**) is below, with the button *Open NICOS*. This notebook only gives you the tools; what to
measure and how to analyze it is your decision, as at a real beamtime.
"""), md("**Your proposal** (click to open it):"),
        code('import sys, os\nsys.path.insert(0, os.path.abspath("../../.."))\nimport nb_tools\n'
             'nb_tools.proposal("odin/exercises/battery_operando/beamtime.md")'),
        code('nb_tools.nicos("odin")'),
        stop(md("## Your files\n\nNICOS writes them to the folder of the proposal; the logbook is read from the files.")),
        code(SETUP.replace('q = quiz.Quiz("odin_battery_msc")       # the questions of this notebook\n', "")),
        code(FILES.replace("@@PROPOSAL@@", PROPOSAL)), md(r"""
## Tools

- in NICOS: `cycle_time` (h, the state of the cell on its cycler), `radiograph(t, title, pixels)`, and the Timepix3
  for time of flight (`count(t=...)` in a `nexusfile_open` block);
- `tomo.image(file)`, `tomo.transmission(sample, open, dark)`, `tomo.extent()`; `red.measurements(FOLDER)` (the
  key `cycle_time_h` of the camera images);
- `tomo.effective_sigma(cfg, VirtualOdin(session="s").camera_spectrum())`, `tw.sigma_tot(cfg, λ)`: Σ of a material;
  `MATS`: the materials of the cell (`graphite x=...`: the electrode with x Li per C₆).
"""), code("# your analysis\n"), code(""), md("## Results for the committee\n\n(your answers, with uncertainties, and "
                                                 "your logbook)")]
    write(bt, os.path.join(HERE, "ODIN_battery_beamtime.ipynb"), all_code_locked=False)


if __name__ == "__main__":
    msc()
    beamtime()
