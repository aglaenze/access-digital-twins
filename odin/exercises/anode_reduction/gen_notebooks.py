"""Generates the MSc and beamtime notebooks of the exercise "Where has the fuel-cell anode been reduced?":

  * ODIN_anode_msc.ipynb       MSc, "develop the method": measure (NICOS or the panel), read the files, Σ(λ) of the
                               bars, the edges, the calibration (which edges: a choice), or the whole spectrum fitted
                               (a choice), the size of the cells of the map (noise against resolution), the result
                               against the weighing;
  * ODIN_anode_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only (beamtime.md).

    python gen_notebooks.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from nbgen import code, distribute, md, nicos_step, stop, write  # noqa: E402

PROPOSAL = "1280"
SETUP = r'''
import sys, os, json, datetime, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
import odin_reduction as red, odin_phases as ph
import live_view                  # figures that follow the sliders
import quiz
q = quiz.Quiz("odin_anode_msc")       # the questions of this notebook
'''
FILES = r'''
from odin_paths import TWIN_RUN_ROOT
import sample_library as sl
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/@@PROPOSAL@@/raw"
LIB = sl.load("odin")
NAMES = {LIB[k]["name"]: k for k in ("anode_standards_a", "anode_standards_b", "anode_loaded_700C")}
rows = [r for r in red.measurements(FOLDER) if r.get("detector") == "tof histogram"]
if not rows:
    raise SystemExit("No file yet in " + FOLDER + ": measure first (part 0).")
for r in rows:
    print(f"{r['file']:20s} {r['kind']:10s} {r.get('title', '')[:40]:40s} t = {r.get('t_s', 0):4.0f} s  "
          f"{r.get('choppers')} {r.get('wfm_delta_m', '')}  pinhole {r.get('pinhole_m')}")
'''
PICK = r'''
import h5py
path = lambda r: os.path.join(FOLDER, r["file"])
def sample_of(p):
    with h5py.File(p, "r") as f:
        n = f["entry/sample/name"][()] if "entry/sample/name" in f else b""
    n = n.decode() if isinstance(n, bytes) else str(n)
    return NAMES.get(n, n)
DARK = next((path(r) for r in reversed(rows) if r["kind"] == "dark"), None)
OPEN = [path(r) for r in rows if r["kind"] == "open beam"]
BY = {}
for r in rows:
    if r["kind"] == "sample":
        BY.setdefault(sample_of(path(r)), []).append(path(r))
print("dark:", DARK and os.path.basename(DARK), "| open beam:", len(OPEN), "counts")
print({k: len(v) for k, v in BY.items()}, "counts per holder")
KNOWN = {("anode_standards_a", "top"): 0.0, ("anode_standards_a", "bottom"): 0.52,
         ("anode_standards_b", "top"): 0.11, ("anode_standards_b", "bottom"): 0.92}
'''
SPECTRA = r'''
if not OPEN or "anode_standards_a" not in BY or "anode_standards_b" not in BY:
    raise SystemExit("Measure the open beam and the two holders of standards first (part 0).")
CUBES = {k: ph.Cube(v, OPEN, DARK) for k, v in BY.items()}
lam = next(iter(CUBES.values())).lam
STD = {}                                            # r -> (Σ, dΣ) of each standard bar
for (key, bar), r in KNOWN.items():
    STD[r] = CUBES[key].region_sigma(ph.BARS[bar])
fig, ax = plt.subplots(figsize=(11, 4.2))
for r in sorted(STD):
    ax.errorbar(lam, STD[r][0], STD[r][1], fmt="-", lw=0.8, elinewidth=0.3, color=plt.cm.viridis(r), label=f"{r:.0%}")
for k, l in ph.EDGES.items():
    ax.axvline(l, color="0.5", ls=":", lw=0.8); ax.text(l, ax.get_ylim()[1], k, rotation=90, va="top", fontsize=8)
ax.set(xlabel="λ (Å)", ylabel="Σ (cm⁻¹)", title="Σ(λ) of the four standards (whole bars inside the field)")
ax.legend(title="r (weighing)"); ax.grid(alpha=0.3); plt.show()
print(f"noise of Σ per bin of 0.01 Å: {np.nanmedian(STD[0.0][1]):.3f} cm⁻¹")
'''
CAL = r'''
edges = w.SelectMultiple(options=list(ph.EDGES), value=("NiO(220)", "Ni(200)"), description="Edges used",
                         rows=4, layout=w.Layout(width="320px"))
img_c, txt_c = live_view.FigureImage(), w.HTML()
H = {r: ph.edge_heights(lam, s) for r, (s, ds) in STD.items()}
R = sorted(H)
CALIB = ph.calibrate(R, [H[r] for r in R])
def draw_cal(_=None):
    use = edges.value or ("NiO(220)",)
    with img_c:
        fig, ax = plt.subplots(1, 4, figsize=(15, 3.6), sharex=True)
        for a, k in zip(ax, ph.EDGES):
            a.plot(R, [H[r][k] for r in R], "o", color="k")
            c0, c1 = CALIB[k]
            a.plot([0, 1], [c0, c0 + c1], color="tab:red" if k in use else "0.7")
            a.set(title=f"{k}{' (used)' if k in use else ''}", xlabel="r (weighing)")
            a.grid(alpha=0.3)
        ax[0].set_ylabel("edge height (cm⁻¹)")
        plt.tight_layout()
    # leave-one-out: each standard computed from the line of the other three, with the edges chosen
    err = []
    for r0 in R:
        others = [r for r in R if r != r0]
        cal = ph.calibrate(others, [H[r] for r in others])
        err.append(float(ph.reduction(H[r0], cal, use)[0]) - r0)
    txt_c.value = ("Each standard computed from the line of the other three (leave one out): "
                   + ", ".join(f"{r:.0%} → {r + e:.1%}" for r, e in zip(R, err))
                   + f"; rms error <b>{100 * np.sqrt(np.mean(np.square(err))):.1f} %</b>")
edges.observe(live_view.throttled(draw_cal), "value")
display(w.VBox([edges, img_c, txt_c])); draw_cal()
'''
AREAS = r'''
if "anode_loaded_700C" not in CUBES:
    raise SystemExit("Measure the holder 'reduced at 700 °C' first (part 0).")
method = w.ToggleButtons(options=[("edge heights", "edges"), ("whole spectrum", "unmix")], value="edges",
                         description="Method")
txt_a = w.HTML()
AREA = {"A (bent part)": (-6.75, 2.75, 0.75, 6.25), "B (beyond the load)": (3.25, 6.75, 0.75, 6.25),
        "reference": ph.BARS["bottom"], "A top (stretched)": (-6.75, 2.75, 4.75, 6.25),
        "A middle": (-6.75, 2.75, 2.75, 4.25), "A bottom (compressed)": (-6.75, 2.75, 0.75, 2.25)}
C700 = CUBES["anode_loaded_700C"]
RES = {}
def r_of(sigma):
    if method.value == "edges":
        return ph.reduction(ph.edge_heights(lam, sigma), CALIB, edges.value or ("NiO(220)",))[0]
    return ph.unmix(lam, sigma, STD[0.0][0], STD[0.92][0], 0.92)
def show_areas(_=None):
    lines = []
    for name, rect in AREA.items():
        s, ds = C700.region_sigma(rect)
        # uncertainty: the same with Σ redrawn within its error bars (50 times)
        rng = np.random.default_rng(1)
        draws = [float(r_of(s + rng.normal(0, 1, s.shape) * np.nan_to_num(ds))) for _ in range(50)]
        RES[name] = (float(r_of(s)), float(np.std(draws)))
        lines.append(f"<tr><td style='padding:2px 12px'>{name}</td><td>{100 * RES[name][0]:.1f} ± "
                     f"{100 * RES[name][1]:.1f} %</td></tr>")
    txt_a.value = f"<p>Method: <b>{method.value}</b>, edges {', '.join(edges.value)}</p><table>{''.join(lines)}</table>"
method.observe(live_view.throttled(show_areas), "value")
display(w.VBox([method, txt_a])); show_areas()
'''
MAP = r'''
cell = w.ToggleButtons(options=[("0.5 mm", 1), ("1.5 mm", 3), ("3.5 mm", 7)], value=3, description="Cells")
img_m, txt_m = live_view.FigureImage(), w.HTML()
def draw_map(_=None):
    S = C700.sigma(block=cell.value)
    r = r_of(S)
    n = r.shape[0]
    cx = -ph.FIELD + 2 * ph.FIELD * (np.arange(n) + 0.5) / n
    ref = (cx[:, None] < -0.75) & (cx[:, None] > -6.25) & (np.abs(cx[None, :]) < 6.5)
    with img_m:
        fig, ax = plt.subplots(figsize=(8, 6.2))
        im = ax.imshow(100 * r, origin="lower", extent=(-ph.FIELD, ph.FIELD, -ph.FIELD, ph.FIELD), cmap="inferno",
                       vmin=0, vmax=80)
        fig.colorbar(im, ax=ax, label="r (%)")
        for x in (-7, 3):
            ax.plot([x, x], [0.5, 6.5], color="w", lw=1.5)
        ax.set(xlabel="x (mm)", ylabel="y (mm)", title=f"{method.value}, cells of {0.5 * cell.value:g} mm")
    txt_m.value = (f"scatter of the cells of the reference bar (uniform, 27 %): <b>{100 * np.nanstd(r[ref]):.1f} %</b> "
                   f"(the noise of one cell)")
cell.observe(live_view.throttled(draw_map), "value")
method.observe(live_view.throttled(draw_map), "value")
display(w.VBox([cell, img_m, txt_m])); draw_map()
'''
QUESTIONS = r'''
q.choice("Part 3: the edges Ni(111) (4.07 Å) and NiO(200) (4.18 Å) give the worst calibration lines. Why?",
         ["They are only 0.11 Å apart: the band read above Ni(111) is the band read below NiO(200), so each height "
          "picks up the other edge (Makowska et al. used their ratio instead).",
          "Ni(111) is a weak edge.", "Neutrons of 4 Å are absorbed by Ni.", "The resolution is worse at 4 Å."],
         answer=0, why={1: "It is one of the strongest of Ni.", 2: "Absorption is smooth: no edge.",
                        3: "The relative resolution of WFM is about the same over the band."},
         explanation="Overlapping edges must be separated by a model (a fit of both), or used as a ratio.",
         hints=["Look at the bands of each edge (ph.SIDES)."], title="Q1. Overlapping edges")
q.number("Part 4: the reduction degree in area A (bent part), %:", value=39, tol=6, unit="%",
         hints=["Part 4, either method."], explanation="39 % in the paper (ECS Trans. 2015).", title="Q2. Area A")
q.number("Part 4: the reduction degree of the reference bar, %:", value=27, tol=6, unit="%", hints=["Part 4."],
         explanation="27 % in the paper.", title="Q3. The reference")
q.choice("Part 4: 'whole spectrum' against 'edge heights':",
         ["The whole spectrum uses every wavelength bin: a smaller uncertainty for the same neutrons, but it assumes "
          "that Σ(λ) changes with r exactly as between the standards (same porosity, texture).",
          "Edge heights are always better.", "They measure different things.", "The whole spectrum needs no standards."],
         answer=0, why={1: "Compare the uncertainties printed.", 2: "Both give r.",
                        3: "It needs two standards: Σ0 and Σ at 92 %."},
         explanation="A linear combination fit of reference spectra (unmixing) is the usual next step.",
         hints=["Compare the ± of the two methods."], title="Q4. The method")
q.choice("Part 5: cells of 0.5 mm against 3.5 mm:",
         ["49 times fewer neutrons per cell of 0.5 mm than of 3.5 mm: 7 times the noise; 3.5 mm cells are quiet but "
          "blur the gradient across the 6 mm height of the bar (tension at the top, compression at the bottom).",
          "The smaller cells are always better.", "The size of the cells does not change the noise.",
          "The 2 mm cells are biased."],
         answer=0, why={1: "Look at the scatter printed.", 2: "Look at the scatter printed.",
                        3: "They average; they do not bias a uniform bar."},
         explanation="Noise ∝ 1/√N: the cell size trades noise against resolution, as the counting time does.",
         hints=["Compare the scatter of the reference bar."], title="Q5. Cells")
q.report()
'''


def msc():
    cells = [md(r"""
# Where has the fuel-cell anode been reduced? (MSc: develop the method)

**Your mission.** You work for a company that builds stacks of solid-oxide cells. Before a stack runs, hydrogen
reduces the NiO of the anode supports to Ni, inside the stack, under load. The team needs a method it can trust to map
the reduction degree $r$ inside a support, with its uncertainty, and to know whether a load speeds the reduction up.
You develop it on the bars of M. G. Makowska *et al.*, ECS Trans. **68**, 1103 (2015) (NOBORU, J-PARC) and J. Appl.
Cryst. **49**, 1674 (2016) (Engin-X, ISIS): 20 × 6 × 0.9 mm³ bars of NiO-YSZ, standards reduced to 0, 11, 52 and 92 %
(weighed), and a bar reduced 5 min at 700 °C under a bending load with its reference. The composition of the twin's bars
(56 wt% NiO, 44 wt% 3YSZ, 15 % pores) is an assumption.

**The physics.** $\Sigma(\lambda) = -\ln T / d$ is the sum of the contributions of the phases: NiO in proportion to
$1 - r$, Ni to $r$, YSZ constant. So at each wavelength $\Sigma$ is a straight line in $r$, and so is the height of
every Bragg edge: NiO(220) 2.95 Å, Ni(200) 3.52 Å, Ni(111) 4.07 Å, NiO(200) 4.18 Å. Standards give the lines; a measured
spectrum then gives $r$ (from chosen edges, or from the whole spectrum).

The code of each step is given (and locked): read it, run it, and make the decisions with the widgets.
"""), code(SETUP), md("## The samples"), code(r'''
import sample_library as sl
for name in ("anode_standards_a", "anode_standards_b", "anode_loaded_700C"):
    spec = sl.load("odin")[name]
    print(sl.describe("odin", spec, spec.get("hidden", [])))
    sl.draw("odin", spec, hidden=spec.get("hidden", []), fig=plt.figure(figsize=(10, 3.2))); sl.show()
'''), md(r"""
## Before you measure

The edges are 1 to 3 % of the transmission through 0.9 mm: WFM (discs 0.30 m apart) to separate Ni(111) and
NiO(200), pinhole 3 cm; the Timepix3 in **histogram mode** (counts per pixel and wavelength bin of 0.01 Å, 2.7 to
4.5 Å); a dark (1 min), then **1 hour** of open beam and of each holder (Makowska *et al.*: 4 to 5 h at NOBORU).
"""), code(r'''
q.number("The edges NiO(200) and Ni(111) are 0.11 Å apart. What relative wavelength resolution Δλ/λ separates them, "
         "at the least (%)?", value=2.7, tol=0.4, unit="%", hints=["0.11 / 4.1."],
         explanation="0.11 / 4.1 = 2.7 %: the natural pulse of ESS (about 5 % at 4 Å on ODIN) blurs them together; WFM "
                     "(about 0.5 %) separates them.", title="Q0. Resolution")
'''), md(f"""
## 0. Your measurements

Choose how: **in NICOS** (the commands below), or **here, with a panel** (*Histogram image*). Either way your files go
to the folder of proposal {PROPOSAL}.
"""), code(f'import measure_panel\nmeasure_panel.Panel("odin", proposal="{PROPOSAL}", samples=["anode_standards_a", '
           f'"anode_standards_b", "anode_loaded_700C"])'),
        nicos_step(md(f"""
### Step 1. Your proposal

In NICOS, tab **Experiment**, **Find my proposal**, choose **{PROPOSAL}**, then **Apply**. Then tab **Instrument
interaction**.
""")), nicos_step(md(r"""
### Step 2. Dark, open beam, the three holders

`tof_histogram(t, title)`: the Timepix3 in histogram mode for t seconds.

```
move(choppers, 'wfm', wfm_delta, 0.3, pinhole, 0.03, diffuser, 'in')
move(shutter, 'closed')
tof_histogram(60, 'dark')
move(shutter, 'open', stage_x, 500)
tof_histogram(3600, 'open beam')
move(stage_x, 0, sample_holder, 'anode_standards_a')
tof_histogram(3600, 'standards 0 and 52')
move(sample_holder, 'anode_standards_b')
tof_histogram(3600, 'standards 11 and 92')
move(sample_holder, 'anode_loaded_700C')
tof_histogram(3600, 'loaded and reference')
```
""")), stop(md("## 1. Your files")), code(FILES.replace("@@PROPOSAL@@", PROPOSAL)),
        md("## 2. Which file is what?"), code(PICK), md(r"""
## 3. The standards, and the calibration

$\Sigma(\lambda)$ of each standard bar, then the height of each edge against the weighed $r$. **Your decision:** which
edges to use. The quality of each choice is tested by leaving one standard out: its $r$ computed from the line of the
other three.
"""), code(SPECTRA), code(CAL), md(r"""
## 4. The loaded bar: areas

**Your decision:** the method. *Edge heights* (the edges chosen in part 3, as Makowska *et al.*) or *whole spectrum*:
$\Sigma(\lambda) = \Sigma_0(\lambda) + r\,[\Sigma_{92}(\lambda) - \Sigma_0(\lambda)]/0.92$ fitted over 2.8 to 4.4 Å. The
uncertainty: the same computation with $\Sigma$ redrawn 50 times within its error bars.
"""), code(AREAS), md(r"""
## 5. The map

**Your decision:** the size of the cells. The scatter of the cells of the reference bar (uniform) measures the noise of
one cell.
"""), code(MAP), md("## Your results\n\nYour score on the questions of the notebook, and a report to download."),
        code(QUESTIONS), md(r"""
## Submit your work

When you are done: save this notebook (*Save*), write what you thought of the exercise, then submit.
"""), code('import submit\n_ = submit.Submit("odin/exercises/anode_reduction", "msc", quiz=q)')]
    distribute(cells, [
        ("display(w.VBox([edges, img_c, txt_c]))", [1]),
        ("display(w.VBox([method, txt_a]))", [2, 3, 4]),
        ("display(w.VBox([cell, img_m, txt_m]))", [5]),
    ])
    write(cells, os.path.join(HERE, "ODIN_anode_msc.ipynb"), all_code_locked=True)


def beamtime():
    bt = [md(f"""
# Beamtime on ODIN: the reduction of SOC anode supports (starter notebook)

Your proposal (**{PROPOSAL}**) is below, with the button *Open NICOS*. This notebook only gives you the tools; what to
measure and how to analyze it is your decision, as at a real beamtime.
"""), md("**Your proposal** (click to open it):"),
        code('import sys, os\nsys.path.insert(0, os.path.abspath("../../.."))\nimport nb_tools\n'
             'nb_tools.proposal("odin/exercises/anode_reduction/beamtime.md")'),
        code('nb_tools.nicos("odin")'),
        stop(md("## Your files\n\nNICOS writes them to the folder of the proposal; the logbook is read from the files.")),
        code(SETUP.replace('q = quiz.Quiz("odin_anode_msc")       # the questions of this notebook\n', "")),
        code(FILES.replace("@@PROPOSAL@@", PROPOSAL)), md(r"""
## Tools

- `c = ph.Cube(sample_files, open_files, dark_file)`: Σ(λ) on cells of 0.5 mm; `c.region_sigma((x0, x1, y0, y1))` →
  Σ, dΣ of a rectangle [mm]; `c.sigma(block)` → Σ per cell (λ, y, x); `c.lam`; `ph.BARS` (the two bars of a holder);
- `ph.edge_heights(lam, sigma)`, `ph.EDGES`, `ph.SIDES`; `ph.calibrate(r_known, heights)`;
  `ph.reduction(heights, cal, use)`; `ph.unmix(lam, sigma, sigma_0, sigma_1, r_1)`;
- `red.measurements(FOLDER)` (`detector`: "tof histogram"); the sample of a file: `entry/sample/name`;
- in NICOS: `tof_histogram(t, title)` (the Timepix3 in histogram mode), or event files with `count(t=...)` in a
  `nexusfile_open` block (`ph.Cube` reads both).
"""), code("# your analysis\n"), code(""), md("## Results for the committee\n\n(your answers, with uncertainties, and "
                                                 "your logbook)")]
    write(bt, os.path.join(HERE, "ODIN_anode_beamtime.ipynb"), all_code_locked=False)


if __name__ == "__main__":
    msc()
    beamtime()
