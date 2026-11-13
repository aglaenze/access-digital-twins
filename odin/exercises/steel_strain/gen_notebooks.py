"""Generates the MSc and beamtime notebooks of the exercise "Where is a loaded steel part strained?":

  * ODIN_steel_msc.ipynb       MSc, "develop the method": measure (NICOS or the panel), read the files, compute the
                               transmission in a region, build the model of the (110) edge with the model builder
                               (no code to write), deduce the strain, then all regions and loads, Poisson's ratio, and
                               the systematic error of a textbook reference;
  * ODIN_steel_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only, no guidance (beamtime.md).

    python gen_notebooks.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from nbgen import code, distribute, md, nicos_step, stop, write  # noqa: E402

PROPOSAL = "1240"
SETUP = r'''
import sys, os, json, datetime, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
import odin_reduction as red, odin_strain as strain
import model_builder as mb
import quiz
q = quiz.Quiz("odin_steel_msc")       # the questions of this notebook
'''
SAMPLE = r'''
import sample_library as sl
for name, hidden in sl.exercise_hidden("exercise.yml").items():
    spec = sl.load("odin")[name]
    print(sl.describe("odin", spec, hidden))
    sl.draw("odin", spec, hidden=hidden, fig=plt.figure(figsize=(10, 3.5))); sl.show()
'''

msc = [md(r"""
# Where is a loaded steel part strained? (MSc: develop the method)

**Your mission.** You are the engineer of a team that designs steel parts for a wind turbine. The team wants a method
it can trust to measure, inside the steel, the strain of its crystal lattice under load. You develop it on a tensile
specimen in a load frame: from the raw files to a strain with its uncertainty, in each part of the specimen, then
Poisson's ratio of the steel; and you find out how large the systematic errors are.

**The physics.** A Bragg edge sits at $\lambda_\text{edge} = 2d$: the planes **facing the beam**, $d$ apart, scatter
the neutrons straight back. Under load $d \to d(1+\varepsilon)$, so the edge moves:
$\varepsilon = (\lambda - \lambda_0)/\lambda_0$, the strain of the lattice **along the beam**. Pulled along the force,
the steel gets thinner across it (Poisson): $\varepsilon_\text{beam} = -\nu\,\sigma/E$, about $-10^{-3}$ here.

The code of each step is given (and locked): read it, run it, and make the decisions; the model of the edge is built
with the model builder, without writing code.
"""), code(SETUP), md("## The specimen"), code(SAMPLE), md(r"""
## Before you measure: five measurements, and why

1. **dark** (shutter closed): the background of the camera, in every measurement;
2. **open beam** (shutter open, stage x = 500 mm: the specimen and its frame out of the beam);
3. the specimen **without load** (0 kN): the reference $\lambda_0$, measured on the specimen itself;
4. the specimen at **8 kN**, 5. at **16 kN** (800 MPa in the gauge, below the elastic limit, about 900 MPa).

All with the **same beam**: choppers in WFM mode with the discs 0.30 m apart (sharp edges: the resolution a shift of
$10^{-3}$ needs) and the 3 cm pinhole; **60 s** each (the edge to about ± 0.0005 Å).
"""), code(r'''
q.choice("Why must the open beam, the reference and the loaded measurements all use the same choppers and pinhole?",
         ["The transmission is a ratio: both terms must see the same beam (spectrum, resolution); and the shape of "
          "the pulses shifts the fitted edge, by the same amount only if the beam is the same.",
          "Because NICOS refuses other settings.",
          "It does not matter for a strain, only for a transmission."],
         answer=0, why={1: "NICOS would accept them; the ratio would then mix two different beams.",
                        2: "The strain is a difference of two edge positions of 10⁻³: any change of the beam shifts them."},
         explanation="A strain of 10⁻³ is a shift of 0.004 Å. The resolution and the pulse shape change the fitted "
                     "position by as much: they cancel in the difference only if they are identical.",
         hints=["What does a ratio cancel, and what does it not cancel?"], title="Q1. The same beam")
'''), md(r"""
## 0. Your measurements

As at ESS, the measurements are yours: if a file is wrong (shutter forgotten, specimen out of the beam), you will see
it in part 1 and measure again. Choose how:

- **in NICOS**, the control software of ESS: you type the commands below, one at a time;
- **here, with a panel**: the same devices (and the load frame), set with buttons, and a *Count* button.

Either way your files go to the folder of proposal 1240, and the rest of the notebook reads them.
"""), code(f'import measure_panel\nmeasure_panel.Panel("odin", proposal="{PROPOSAL}", samples=["steel_tensile"])'),
    nicos_step(md(r"""
### Step 1. Your proposal

In NICOS, tab **Experiment**, **Find my proposal**, choose **1240** (*Lattice strain of a steel specimen under load*),
then **Apply**: the specimen is mounted in the load frame. Then tab **Instrument interaction**: type each command
below in the command line, then *Enter*.
""")), nicos_step(md(r"""
### Step 2. The beam

```
move(choppers, 'wfm', wfm_delta, 0.3, pinhole, 0.03, diffuser, 'in')
```
""")), nicos_step(md(r"""
### Step 3. The dark and the open beam

```
move(shutter, 'closed')
with nexusfile_open('dark'):
    count(t=30)
move(shutter, 'open', stage_x, 500)
with nexusfile_open('open beam'):
    count(t=60)
```
""")), nicos_step(md(r"""
### Step 4. The specimen, without load and under load

The load frame is the device `load` (kN):

```
move(stage_x, 0, load, 0)
with nexusfile_open('steel 0 kN'):
    count(t=60)
move(load, 8)
with nexusfile_open('steel 8 kN'):
    count(t=60)
move(load, 16)
with nexusfile_open('steel 16 kN'):
    count(t=60)
move(load, 0)
```
""")),
    stop(md(r"""
## 1. Your files

The files of proposal 1240 are in `data/odin/<year>/1240/raw`. The logbook below is read from the files themselves:
the state of the instrument during each measurement, and the force of the load frame (`load_kN`, written by the
frame in `entry/sample/applied_force`).
""")), code(r'''
from odin_paths import TWIN_RUN_ROOT
PROPOSAL = "1240"
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/{PROPOSAL}/raw"
rows = red.measurements(FOLDER)
if not rows:
    raise SystemExit("No file yet in " + FOLDER + ": measure first (part 0).")
for r in rows:
    print(f"{r['file']:22s} {r['kind']:10s} {r.get('title', '')[:22]:22s} t = {r.get('t_s', 0):5.0f} s  "
          f"{r.get('choppers')} δ = {r.get('wfm_delta_m')}  pinhole {r.get('pinhole_m')}  load {r.get('load_kN', '-')}")
'''), md(r"""
## 2. Which file is what?

The cell picks the last dark and the last open beam, and for each force the last measurement of the specimen; only
the files measured with the beam of part 0 (WFM, δ = 0.30 m, pinhole 3 cm).
"""), code(r'''
same = [r for r in rows if r.get("choppers") == "wfm" and r.get("wfm_delta_m") == 0.3 and r.get("pinhole_m") == 0.03]
path = lambda r: os.path.join(FOLDER, r["file"])
DARK = next((path(r) for r in reversed(same) if r["kind"] == "dark"), None)
OPEN = next((path(r) for r in reversed(same) if r["kind"] == "open beam"), None)
BY_LOAD = {}
for r in same:
    if r["kind"] == "sample" and "load_kN" in r:
        BY_LOAD[r["load_kN"]] = path(r)
print("dark:", DARK and os.path.basename(DARK), "| open beam:", OPEN and os.path.basename(OPEN))
print("specimen:", {k: os.path.basename(v) for k, v in sorted(BY_LOAD.items())})
if OPEN is None or 0.0 not in BY_LOAD or len(BY_LOAD) < 2:
    raise SystemExit("Needed: an open beam, the specimen at 0 kN and under load (part 0).")
LMAX = max(BY_LOAD)
'''), md(r"""
## 3. The transmission around the edge

In a region of the specimen (here the gauge, its narrow part: 4 mm × 6 mm), for each wavelength bin of 0.01 Å:

$$T = \frac{(E - N)/Q_E}{(O - N)/Q_O}$$

$E$, $O$, $N$: the counts of the specimen, open-beam and dark files in the region ($N$ scaled to the duration of each
measurement), $Q$ the proton charge of each measurement (the number of neutrons produced is proportional to it).
Error bars: Poisson, propagated. Reading a file of 30 million neutrons takes about 20 s the first time.
"""), code(r'''
REGION = "gauge"
lam, T0, dT0 = strain.spectrum(BY_LOAD[0.0], OPEN, DARK, REGION)
lam, T1, dT1 = strain.spectrum(BY_LOAD[LMAX], OPEN, DARK, REGION)
fig, ax = plt.subplots(figsize=(9, 4))
ax.errorbar(lam, T0, dT0, fmt=".", ms=3, color="0.4", label="0 kN")
ax.errorbar(lam, T1, dT1, fmt=".", ms=3, color="tab:red", label=f"{LMAX:g} kN")
ax.set(xlabel="λ (Å)", ylabel="transmission", title=f"The {REGION}: the (110) edge of iron near 4.05 Å")
ax.legend(); ax.grid(alpha=0.3); plt.show()
'''), md(r"""
## 4. Your model of the edge

The two curves look the same: the shift (about 0.005 Å) is far smaller than the width of the edge. It is found by
**fitting a model** to all the points of the edge. Build it with the model builder: choose the shape (try the three),
the range of the data, the start values, then *Fit*. Compare the reduced χ² (about 1: the model describes the data
within their error bars) and the uncertainty of $\lambda_\text{edge}$. Fit the reference first, then the loaded
specimen **with the same model and the same range** (why? question Q3).
"""), code(r'''
b0 = mb.EdgeBuilder(lam, T0, dT0, expected=4.054, name="(110), 0 kN")
'''), code(r'''
b1 = mb.EdgeBuilder(lam, T1, dT1, expected=4.054, name=f"(110), {LMAX:g} kN")
'''), md(r"""
## 5. The strain from your two fits

$\varepsilon = (\lambda_1 - \lambda_0)/\lambda_0$, and its uncertainty from those of the two edges (independent
measurements: added in quadrature). The button reads your last fits (fit again, then click again).
"""), code(r'''
out_eps = w.Output()
def show_strain(_=None):
    out_eps.clear_output()
    with out_eps:
        if b0.lam_edge is None or b1.lam_edge is None:
            print("Fit both edges first (part 4)."); return
        l0, d0, l1, d1 = b0.lam_edge, b0.dlam_edge, b1.lam_edge, b1.dlam_edge
        eps, deps = (l1 - l0) / l0, np.hypot(d0, d1) / l0
        print(f"λ0 = {l0:.4f} ± {d0:.4f} Å,  λ1 = {l1:.4f} ± {d1:.4f} Å")
        print(f"ε = ({eps * 1e3:+.2f} ± {deps * 1e3:.2f}) × 10⁻³ in the {REGION} at {LMAX:g} kN "
              f"(stress {strain.stress_MPa(LMAX, REGION):.0f} MPa)")
button_eps = w.Button(description="Strain from my two fits", button_style="success", icon="calculator",
                      layout=w.Layout(width="auto"))
button_eps.on_click(show_strain)
display(w.VBox([button_eps, out_eps]))
'''), md(r"""
## 6. All the regions, all the loads

Your method, applied everywhere: the model *smoothed step on a sloping baseline* (`strain.edge`, the same model as
the builder's) is fitted in the three regions of the specimen (gauge, upper and lower shoulders) for every load you
measured. The map shows the strain at the largest load; the line, the strain against the stress $\sigma = F/A$ of
each region: elastic steel gives one line through zero, of slope $-\nu/E$.
"""), code(r'''
E_GPA = 210.0
pts, res_max = [], {}
for kN, f in sorted(BY_LOAD.items()):
    if kN == 0:
        continue
    for r in strain.REGIONS:
        e, de = strain.strain(strain.edge(f, OPEN, DARK, r), strain.edge(BY_LOAD[0.0], OPEN, DARK, r))
        pts.append((strain.stress_MPa(kN, r), e, de, r))
        if kN == LMAX:
            res_max[r] = (e, de)
x, y, dy = (np.array([p[k] for p in pts]) for k in range(3))
a, da = strain.line_through_zero(x, y, dy)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
fig.colorbar(strain.plot_map(ax1, strain.transmission_image(BY_LOAD[LMAX], OPEN), res_max), ax=ax1, label="10⁻³")
for r, c in (("gauge", "tab:red"), ("upper shoulder", "tab:blue"), ("lower shoulder", "tab:cyan")):
    k = [i for i, p in enumerate(pts) if p[3] == r]
    ax2.errorbar(x[k], y[k] * 1e3, dy[k] * 1e3, fmt="o", color=c, capsize=3, label=r)
xs = np.array([0, x.max() * 1.08])
ax2.plot(xs, a * xs * 1e3, "k-", label="line through zero")
ax2.set(xlabel="stress σ (MPa)", ylabel="strain along the beam (10⁻³)"); ax2.grid(alpha=0.3); ax2.legend(fontsize=9)
plt.tight_layout(); plt.show()
print(f"slope −ν/E = ({a * 1e6:.2f} ± {da * 1e6:.2f}) × 10⁻⁶ per MPa  ->  ν = {-a * E_GPA * 1e3:.2f} ± {da * E_GPA * 1e3:.2f}")
'''), md(r"""
## 7. Investigate: a reference from the textbook?

Measuring the specimen without load takes beam time. Why not take $\lambda_0 = 2d_{110}$ = 4.054 Å from the
textbook (α-iron, $a$ = 2.8665 Å)? The cell computes the strain at the largest load both ways.
"""), code(r'''
r1, r0 = strain.edge(BY_LOAD[LMAX], OPEN, DARK, "gauge"), strain.edge(BY_LOAD[0.0], OPEN, DARK, "gauge")
print(f"fitted edge without load: {r0['lam_edge']:.4f} Å   (textbook: {strain.EDGE_110:.4f} Å)")
print(f"strain with the measured reference : {(r1['lam_edge'] - r0['lam_edge']) / r0['lam_edge'] * 1e3:+.2f} × 10⁻³")
print(f"strain with the textbook reference : {(r1['lam_edge'] - strain.EDGE_110) / strain.EDGE_110 * 1e3:+.2f} × 10⁻³")
'''), md("## Your results\n\nYour score on the questions of the notebook, and a report to download."), code(r'''
q.choice("Which shape of edge describes your data (reduced χ² close to 1, no structure in the residuals)?",
         ["The step smoothed by the resolution, on a sloping baseline.", "The sharp step.",
          "The step smoothed by the resolution, on a flat baseline."],
         answer=0, why={1: "A sharp step cannot follow the points of the edge: χ² far above 1.",
                        2: "Close, but the baseline is not flat (the other planes and absorption vary with λ): look at "
                           "the residuals far from the edge."},
         explanation="The edge is smoothed by the wavelength resolution (an error function of width ≈ 0.01–0.02 Å), "
                     "and the transmission varies slowly on either side.", hints=["Compare χ² in the history table."],
         title="Q2. The model")
q.choice("Why fit the reference and the loaded specimen with the same model and range?",
         ["The fitted position depends a little on the model and range; the same choices give the same bias, which "
          "cancels in the difference.", "To save time.", "Because the builder cannot change them."],
         answer=0, why={1: "It is about the result, not the time.", 2: "It can: try."},
         explanation="A change of model or range can move λ_edge by 0.001 Å or more: as much as the strain signal. "
                     "With the same choices the bias is the same and cancels.", hints=["What is the size of the shift?"],
         title="Q3. Same model, same range")
q.number("Your edge without load (part 4): λ0 =", value=4.057, tol=0.012, unit="Å",
         mistakes=[(2.027, "this is d; the edge is at 2d")], hints=["The builder prints λ_edge after the fit."],
         explanation="About 4.057 Å: a few 0.001 Å above 2d = 4.054 Å (the pulse shape shifts the fitted position).",
         title="Q4. The reference")
q.number("Your strain in the gauge at 16 kN (part 5), in units of 10⁻³, with its sign:", value=-1.10, tol=0.45,
         unit="× 10⁻³", mistakes=[(1.10, "the sign: the edge moved to a shorter wavelength")],
         hints=["Part 5 prints it."],
         explanation="Expected −ν σ/E = −0.29 × 800 / 210 000 = −1.10 × 10⁻³, measured to about ± 0.2 × 10⁻³.",
         title="Q5. The strain")
q.number("Poisson's ratio from all your points (part 6):", value=0.29, tol=0.09,
         hints=["Part 6 prints ν."], explanation="ν ≈ 0.29 for ferritic steel.", title="Q6. Poisson's ratio")
q.choice("Part 7: what does the textbook reference do to the strain?",
         ["It is off by about as much as the strain itself: the alloy and the instrument shift the edge by a few "
          "0.001 Å, which a measured reference cancels.",
          "Nothing: both give the same strain.",
          "It improves it: the textbook value has no error bar."],
         answer=0, why={1: "Look at the two numbers of part 7.",
                        2: "It has no statistical error, but a systematic one as large as the signal."},
         explanation="The difference between the fitted unloaded edge and 4.054 Å (≈ 0.003 Å, 7 × 10⁻⁴ in strain) is "
                     "a systematic error. Real strain measurements need a stress-free reference of the same material, "
                     "measured with the same instrument: often the hardest part of the experiment.",
         hints=["Compare the two strains of part 7 with your uncertainty."], title="Q7. The reference, again")
q.choice("Your uncertainty must be twice smaller. What do you change?",
         ["Count 4 times longer (both the reference and the loaded specimen).", "Count twice longer.",
          "Use bins of 0.001 Å.", "Fit a narrower range."],
         answer=0, why={1: "√2 only.", 2: "Narrower bins hold fewer neutrons each: same information.",
                        3: "Fewer points: a larger uncertainty."},
         explanation="Uncertainty ∝ 1/√N: 4 times the neutrons for half the error, on both measurements of the "
                     "difference.", hints=["1/√N"], title="Q8. Counting time")
q.report()
'''), md(r"""
## Submit your work

When you are done: save this notebook (*Save*), write what you thought of the exercise, then submit.
"""), code('import submit\n_ = submit.Submit("odin/exercises/steel_strain", "msc", quiz=q)')]

distribute(msc, [
    ("b1 = mb.EdgeBuilder", [2, 3, 4]),                       # the model, same choices, the reference
    ("button_eps.on_click(show_strain)", [5, 8]),             # the strain, the counting time
    ("ν = {-a * E_GPA", [6]),                                 # Poisson's ratio
    ("strain with the textbook reference", [7]),              # the textbook reference
])
write(msc, os.path.join(HERE, "ODIN_steel_msc.ipynb"), all_code_locked=True)

# --------------------------------------------------------------------------- beamtime: a starter notebook
bt = [md(r"""
# Beamtime on ODIN: lattice strain of a steel specimen under load (starter notebook)

Your proposal (**1240**) is below, with the button *Open NICOS*. This notebook only gives you the tools; what to
measure and how to analyze it is your decision, as at a real beamtime.
"""), md("**Your proposal** (click to open it):"),
    code('import sys, os\nsys.path.insert(0, os.path.abspath("../../.."))\nimport nb_tools\n'
         'nb_tools.proposal("odin/exercises/steel_strain/beamtime.md")'),
    code('nb_tools.nicos("odin")'),
    stop(md(r"""
## Your files

NICOS writes them to the folder of the proposal; the logbook is read from the files (state of the instrument, force of
the load frame `load_kN`).
""")), code(SETUP.replace('q = quiz.Quiz("odin_steel_msc")       # the questions of this notebook', "")), code(r'''
from odin_paths import TWIN_RUN_ROOT
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/1240/raw"     # the folder of your proposal
rows = red.measurements(FOLDER)
for r in rows:
    print(r)
'''), md(r"""
## Tools

- `strain.spectrum(sample, open_beam, dark, region)` → λ, T, dT in a region (`strain.REGIONS`: gauge, upper and lower
  shoulder; or add your own rectangle in mm: `strain.REGIONS["mine"] = (x0, x1, y0, y1)`);
- `strain.edge(sample, open_beam, dark, region)` → the fit of the (110) edge (`lam_edge`, `dlam_edge`, `chi2`, ...);
- `strain.strain(loaded, reference)` → (ε, dε); `strain.stress_MPa(kN, region)`; `strain.line_through_zero(x, y, dy)`;
- `mb.EdgeBuilder(lam, T, dT, expected=4.054)`: the model builder;
- `strain.plot_edges(ax, loaded, reference, kN, region)`, `strain.plot_map(ax, image, {region: (ε, dε)})`.
"""), code("# your analysis\n"), code(""), md("## Results for the committee\n\n(your answers, with uncertainties, and your logbook)")]
write(bt, os.path.join(HERE, "ODIN_steel_beamtime.ipynb"), all_code_locked=False)
