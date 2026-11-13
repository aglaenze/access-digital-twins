"""Generates ODIN_anode.ipynb: the guided page (Voila, no code shown) of the exercise
"Where has the fuel-cell anode been reduced?" (Bragg-edge phase mapping of NiO -> Ni in solid-oxide-cell anode
supports, after Makowska et al., ECS Trans. 68, 1103, 2015, and J. Appl. Cryst. 49, 1674, 2016).

    python gen_page.py
"""
import os
import sys

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from nbgen import distribute  # noqa: E402

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Where has the fuel-cell anode been reduced?

You are operating the ODIN imaging instrument at ESS. Behind this page, a simulation of the instrument produces your
measurements; the files are in the ESS NeXus format, and the wavelength of each neutron is computed with the official
ESS software.

**Your mission.** You work for a company that builds stacks of solid-oxide cells: they turn hydrogen into electricity
(fuel cells) or electricity into hydrogen (electrolysis). Each cell sits on a porous plate, the **anode support**, made
of nickel oxide (NiO) and zirconia (YSZ). Before the stack runs for the first time, hydrogen turns the NiO into metallic
nickel, which conducts the electrons: the **reduction**, NiO + H₂ → Ni + H₂O. It happens inside the stack, where the
cells are pressed and bent. If some parts reduce faster than others, the support shrinks unevenly and the cells may
crack. The team wants to know: **does a load make the reduction faster, and where?** Map the reduction inside the
supports, without cutting them, and tell the team (the last questions).

**The samples are real.** M. G. Makowska, M. Strobl, L. Theil Kuhn *et al.* (DTU) did exactly this: *Phase Transition
Mapping by Means of Neutron Imaging in SOFC Anode Supports During Reduction Under Applied Stress*, ECS Trans. **68**,
1103 (2015), at NOBORU (J-PARC, Japan), then in situ at Engin-X (ISIS, UK), J. Appl. Cryst. **49**, 1674 (2016). The twin
uses their bars, their reduction degrees and their results. Its composition (56 % NiO, 44 % zirconia by mass, 15 %
pores) is an assumption.

**Why neutrons.** A neutron passes through the bar (0.9 mm of ceramic and metal) and sees the **crystal** of each
phase: NiO and Ni have different distances between their planes of atoms, so different **Bragg edges** (part 1). The
height of the edges of each phase tells how much of it is there, pixel by pixel.

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
import odin_viz as viz, odin_phases as ph, odin_mcstas as tw
import sample_library as sl
import live_view
from page_output import into
import quiz
q = quiz.Quiz("odin_anode_bsc")          # the questions, along the page

HOLDERS = {"standards 0 % and 52 %": "anode_standards_a", "standards 11 % and 92 %": "anode_standards_b",
           "reduced at 700 °C for 5 min: loaded and reference": "anode_loaded_700C"}
KNOWN = {("anode_standards_a", "top"): 0.0, ("anode_standards_a", "bottom"): 0.52,
         ("anode_standards_b", "top"): 0.11, ("anode_standards_b", "bottom"): 0.92}
odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
odin.move(sample="anode_standards_a")
LIB = sl.load("odin")
""")

md(r"""
## 1. Two crystals, two sets of edges

NiO has the structure of table salt (cubic, $a$ = 4.18 Å); Ni is face-centered cubic ($a$ = 3.52 Å). A Bragg edge
appears at $\lambda = 2d$ for each family of planes $d$ apart: beyond it, the neutrons are too slow to be reflected by
these planes, and more of them pass. The four edges Makowska *et al.* used:

| Edge | Phase | Planes | $\lambda = 2d$ |
|---|---|---|---|
| NiO(220) | NiO | (220) | 2.95 Å |
| Ni(200) | Ni | (200) | 3.52 Å |
| Ni(111) | Ni | (111) | 4.07 Å |
| NiO(200) | NiO | (200) | 4.18 Å |

Move the slider: the attenuation coefficient $\Sigma(\lambda)$ of a support reduced to the degree $r$ (the share of its
NiO turned into Ni), computed from the crystal structures (NCrystal). The zirconia has edges too, but weaker ones.
""")

code(r"""
mats = LIB["anode_standards_a"]["materials"]
LAM = np.linspace(2.7, 4.5, 721)
S0 = tw.sigma_tot(mats["reduced 0 %"], LAM)
S52 = tw.sigma_tot(mats["reduced 52 %"], LAM)
sigma_r = lambda r: S0 + (S52 - S0) * r / 0.52           # Σ is a straight line in r (part 4)
r_s = w.IntSlider(value=0, min=0, max=100, step=1, description="r (%)", continuous_update=True)
view_r = live_view.FigureImage()

def draw_r(_=None):
    with view_r:
        fig, ax = plt.subplots(figsize=(10, 3.8))
        ax.plot(LAM, S0, color="0.75", lw=1, label="r = 0 % (as sintered)")
        ax.plot(LAM, sigma_r(r_s.value / 100), color="tab:red", lw=2, label=f"r = {r_s.value} %")
        for k, l in ph.EDGES.items():
            ax.axvline(l, color="tab:blue" if k.startswith("NiO") else "tab:orange", ls=":", lw=1)
            ax.text(l, 1.32, k, rotation=90, va="top", ha="right", fontsize=8,
                    color="tab:blue" if k.startswith("NiO") else "tab:orange")
        ax.set(xlabel="wavelength λ (Å)", ylabel="Σ (cm⁻¹)", ylim=(0.35, 1.35), xlim=(2.7, 4.5),
               title="Attenuation of the anode support (blue: NiO edges, orange: Ni edges)")
        ax.legend(loc="lower left"); ax.grid(alpha=0.3)
        plt.tight_layout()

r_s.observe(live_view.throttled(draw_r), "value")
draw_r()
display(w.VBox([r_s, view_r]))
""")

md(r"""
## 2. Your samples

Bars of anode support, **20 × 6 × 0.9 mm³**, standing on their edge in a holder (0.9 mm along the beam), two per
holder, one above the other; the camera sees 14 mm of their 20 mm length. Three holders:

| Holder | Top bar | Bottom bar |
|---|---|---|
| standards 0 % and 52 % | as sintered (0 %) | 52 % reduced |
| standards 11 % and 92 % | 11 % | 92 % |
| reduced at 700 °C for 5 min | **under load**: clamped at its left end ($x$ < −7 mm), pushed down at $x$ = +3 mm | **reference**, no load |

The **standards** were reduced evenly, and their reduction degree was measured by weighing them: NiO loses its oxygen,
so the bar gets lighter. They calibrate the edges. The **loaded bar** is a small cantilever: between the clamp and the
load point it bends, stretched along its top edge and compressed along its bottom edge; beyond the load point
($x$ > 3 mm) it carries no stress. Both bars of this holder were reduced **together**, 5 minutes at 700 °C in 9 % H₂,
then frozen by cooling in nitrogen.
""")

code(r"""
smp_out = w.Output()
with into(smp_out):
    for key in ("anode_standards_a", "anode_loaded_700C"):
        spec = odin.sample_spec(key)
        sl.draw("odin", spec, hidden=spec.get("hidden", []), fig=plt.figure(figsize=(10, 3.4)))
        sl.show()
display(smp_out)
""")

md(r"""
## 3. Operate the instrument

Choose a holder, set the controls, then click *Measure*. The Timepix3 camera counts the neutrons of each pixel by
wavelength (time of flight). The edges are only 1 to 3 % of the transmission, and a reduction degree to a few % needs
the edge heights to a few thousandths: **one hour** for the open beam and for each holder.

| Measurement | Shutter | Stage x (mm) | Time |
|---|---|---|---|
| 1. dark | **closed** | 0 | 1 min |
| 2. open beam | **open** | **500** | **1 h** |
| 3. each of the three holders | open | **0** | **1 h** |

Why these settings:
- the **choppers** in WFM mode (discs 0.30 m apart) give a wavelength resolution of about 0.5 %: the edges of Ni(111)
  (4.07 Å) and NiO(200) (4.18 Å) are only 0.11 Å apart; the **pinhole** is 3 cm wide. Both are fixed here, the same for
  all the measurements;
- **stage x = 500 mm** moves the holder out of the field of view: the open beam;
- the camera is used in its **histogram mode**: the counts are summed per pixel and per wavelength bin of 0.01 Å
  (2.7 to 4.5 Å) instead of being stored neutron by neutron; the twin then computes an hour of beam in a few seconds.
  Makowska *et al.* counted 4 to 5 hours per holder at NOBORU (J-PARC).
""")

code(r"""
st = odin.status()
holder = w.Dropdown(options=list(HOLDERS.items()), value=st["sample"] if st["sample"] in HOLDERS.values() else
                    "anode_standards_a", description="Holder", layout=w.Layout(width="520px"))
shut = w.ToggleButtons(options=[("closed", "closed"), ("open", "open")], value=st["shutter"], description="Shutter")
stage = w.BoundedFloatText(value=st["stage_x"] * 1000, min=-500, max=500, step=1, description="Stage x (mm)")
ttime = w.Dropdown(options=[("1 min", 60), ("10 min", 600), ("1 h", 3600)], value=3600, description="Time")
button = w.Button(description="Measure", button_style="primary", icon="play", layout=w.Layout(width="auto"))
out = w.Output()

def default_title():
    if shut.value == "closed":
        return "dark"
    return "open beam" if abs(stage.value) > 20 else holder.label

def do_count(_):
    button.disabled = True
    with out:
        clear_output()
        try:
            odin.move(choppers="wfm", wfm_delta=0.30, pinhole=0.03, diffuser="in", shutter=shut.value,
                      stage_x=stage.value / 1000, sample=holder.value)
            f = odin.tof_image(float(ttime.value), title=default_title())
            print(f"{os.path.basename(f)}: {default_title()}, {ttime.label}, {odin.last_n_counts:,} neutrons")
            with img_m:
                fig, ax = plt.subplots(figsize=(5.4, 4.4))
                im = ax.imshow(odin.last_image, origin="lower", extent=(-7.05, 7.05, -7.05, 7.05), cmap="gray")
                fig.colorbar(im, ax=ax, label="counts (2.7 to 4.5 Å)")
                ax.set(xlabel="x (mm)", ylabel="y (mm)", title=default_title()); plt.tight_layout()
        except Exception as e:
            print("Error:", e)
    button.disabled = False
    refresh_list()

button.on_click(do_count)
img_m = live_view.FigureImage()
display(w.VBox([holder, shut, stage, ttime, button, out, img_m]))
""")

md(r"""
## 4. Your measurements

Each count produces a numbered file, as on the real instrument. The analysis groups them: the open beams together, and
the counts of each holder together.
""")

code(r"""
listing = w.Output()

def measurements():
    ms = []
    if os.path.isfile(odin.log_file):
        for l in open(odin.log_file, encoding="utf-8"):
            e = json.loads(l)
            if e["action"] == "tof_image" and e["details"].get("file"):
                d = e["details"]; s = d["state"]
                if s.get("sample") not in HOLDERS.values() or not (s["choppers"] == "wfm" and abs(s["wfm_delta"] - 0.30) < 1e-6):
                    continue
                kind = "dark" if s["shutter"] == "closed" else ("open beam" if abs(s["stage_x"]) > 0.02 else "holder")
                ms.append(dict(file=d["file"], path=os.path.join(odin.folder, d["file"]), title=d["title"], t=d["t"],
                               kind=kind, sample=s["sample"], counts=d["n_counts"]))
    return ms

def groups():
    ms = measurements()
    dark = [m["path"] for m in ms if m["kind"] == "dark"][-1:]
    ob = [m["path"] for m in ms if m["kind"] == "open beam"]
    by = {}
    for m in ms:
        if m["kind"] == "holder":
            by.setdefault(m["sample"], []).append(m["path"])
    return (dark[0] if dark else None), ob, by

def refresh_list():
    ms = measurements()
    with into(listing):
        if not ms:
            print("No measurement yet.")
        for m in ms:
            print(f"{m['file']}  {m['title'][:44]:44s} {m['kind']:10s} t = {m['t']:5g} s  -> {m['counts']:,} counts")
        dk, ob, by = groups()
        if ms:
            print(f"\nanalysis: dark {'yes' if dk else 'no'}; open beam: {len(ob)} files; "
                  + "; ".join(f"{k}: {len(v)} files" for k, v in by.items()))

refresh_list()
display(listing)
""")

md(r"""
## 5. The edges of the standards, and the calibration

For each bar, at each wavelength, the transmission is $T = (E - N)/(O - N)$ (sample, open beam and dark counts in the
bar, the dark scaled to the duration, each measurement divided by its proton charge), and the attenuation coefficient
$\Sigma = -\ln T / 0.09\ \text{cm}$. The **height of an edge** is the drop of $\Sigma$ across it: its mean just
below the edge minus its mean just above (the shaded bands).

Since $\Sigma$ is the sum of the contributions of NiO (in proportion to $1 - r$), Ni (to $r$) and zirconia (constant),
each height is a **straight line** in $r$: the four standards give the line of each edge (Makowska *et al.*, their
figure 4). Then any height measured on another bar gives its $r$.
""")

code(r"""
button_cal = w.Button(description="Edges and calibration", button_style="success", icon="chart-line",
                      layout=w.Layout(width="auto"))
out_cal = w.Output()
CAL = {}

def calibrate(_=None):
    with into(out_cal):
        dk, ob, by = groups()
        if not ob or "anode_standards_a" not in by or "anode_standards_b" not in by:
            print("Measure first: the open beam and the two holders of standards (part 3)."); return
        print("Reading the files (about 20 s the first time)...")
        R, H, S = [], [], {}
        for key in ("anode_standards_a", "anode_standards_b"):
            c = ph.Cube(by[key], ob, dk)
            for bar in ("top", "bottom"):
                s, ds = c.region_sigma(ph.BARS[bar])
                r = KNOWN[(key, bar)]
                R.append(r); H.append(ph.edge_heights(c.lam, s)); S[r] = s
        lam = c.lam
        CAL.update(cal=ph.calibrate(R, H), R=R, H=H, lam=lam)
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2), gridspec_kw=dict(width_ratios=[1.6, 1, 1]))
        for r in sorted(S):
            ax[0].plot(lam, S[r], lw=1, color=plt.cm.viridis(r), label=f"{r:.0%}")
        for k, (lo, hi) in ph.SIDES.items():
            for a, b in (lo, hi):
                ax[0].axvspan(a, b, color="0.9", zorder=0)
        for k, l in ph.EDGES.items():
            ax[0].axvline(l, color="0.5", ls=":", lw=0.8)
        ax[0].set(xlabel="λ (Å)", ylabel="Σ (cm⁻¹)", title="The four standards"); ax[0].legend(title="r")
        rr = np.linspace(0, 1, 2)
        for a, k in zip(ax[1:], ("NiO(220)", "Ni(200)")):
            a.plot(R, [h[k] for h in H], "o", color="k")
            c0, c1 = CAL["cal"][k]
            a.plot(rr, c0 + c1 * rr, color="tab:red")
            a.set(xlabel="reduction degree r (weighing)", ylabel="edge height (cm⁻¹)",
                  title=f"{k}: height = {c0:.3f} {c1:+.3f} r")
            a.grid(alpha=0.3)
        ax[0].grid(alpha=0.3); plt.tight_layout(); plt.show()

button_cal.on_click(calibrate)
display(w.VBox([button_cal, out_cal]))
""")

md(r"""
## 6. The loaded bar and its reference

The calibration turns the heights of the NiO(220) and Ni(200) edges into two values of $r$; their mean is the
reduction degree (as in the paper). The areas: **A**, the bent part of the loaded bar between the clamp and the load
point ($x$ from −7 to 3 mm); **B**, its part beyond the load point ($x$ > 3 mm, no stress); and the **reference** bar.
""")

code(r"""
button_r = w.Button(description="Reduction in the areas", button_style="success", icon="crosshairs",
                    layout=w.Layout(width="auto"))
out_r = w.Output()
AREAS = {"A: bent part of the loaded bar": (-6.75, 2.75, 0.75, 6.25),
         "B: loaded bar beyond the load point": (3.25, 6.75, 0.75, 6.25),
         "reference bar (no load)": ph.BARS["bottom"],
         "A, top slice (stretched)": (-6.75, 2.75, 4.75, 6.25),
         "A, middle slice": (-6.75, 2.75, 2.75, 4.25),
         "A, bottom slice (compressed)": (-6.75, 2.75, 0.75, 2.25)}
RES = {}

def areas(_=None):
    with into(out_r):
        dk, ob, by = groups()
        if "cal" not in CAL:
            print("Calibrate first (part 5)."); return
        if "anode_loaded_700C" not in by:
            print("Measure the holder 'reduced at 700 °C for 5 min' first (part 3)."); return
        c = ph.Cube(by["anode_loaded_700C"], ob, dk)
        RES["cube"] = c
        for name, rect in AREAS.items():
            s, _ = c.region_sigma(rect)
            r, parts = ph.reduction(ph.edge_heights(c.lam, s), CAL["cal"])
            RES[name] = float(r)
            print(f"{name:38s} r = {r:5.1%}   (NiO(220): {parts['NiO(220)']:5.1%}, Ni(200): {parts['Ni(200)']:5.1%})")

button_r.on_click(areas)
display(w.VBox([button_r, out_r]))
""")

md(r"""
## 7. The map

The same, cell by cell: cells of 1.5 × 1.5 mm (fewer neutrons per cell than in an area: noisier values, about ± 8 % after
an hour). The white lines: the clamp ($x$ = −7 mm) and the load point ($x$ = 3 mm).
""")

code(r"""
button_map = w.Button(description="Map the reduction", button_style="success", icon="map", layout=w.Layout(width="auto"))
out_map = w.Output()

def do_map(_=None):
    with into(out_map):
        if "cube" not in RES:
            print("Run part 6 first."); return
        c = RES["cube"]
        r, _ = ph.reduction(ph.edge_heights(c.lam, c.sigma(block=3)), CAL["cal"])
        fig, ax = plt.subplots(figsize=(8, 6.4))
        im = ax.imshow(100 * r, origin="lower", extent=(-ph.FIELD, ph.FIELD, -ph.FIELD, ph.FIELD), cmap="inferno",
                       vmin=0, vmax=80)
        fig.colorbar(im, ax=ax, label="reduction degree r (%)")
        for x in (-7, 3):
            ax.plot([x, x], [0.5, 6.5], color="w", lw=1.5)
        ax.text(3.2, 6.0, "load", color="w"); ax.text(-6.8, 6.0, "clamp", color="w")
        ax.set(xlabel="x (mm)", ylabel="y (mm)", title="Reduction degree: loaded bar (top), reference (bottom)")
        plt.tight_layout(); plt.show()

button_map.on_click(do_map)
display(w.VBox([button_map, out_map]))
""")

md(r"""
## 8. Your results

Your score on the questions of the page, and a report to download.
""")

code(r"""
q.choice("Part 1: when the reduction goes on (r from 0 to 100 %), the edges...",
         ["NiO(220) and NiO(200) shrink, Ni(200) and Ni(111) grow: each edge follows the amount of its phase.",
          "All the edges grow: the bar gets denser.",
          "All the edges move to longer wavelengths.",
          "Nothing changes: the zirconia dominates."],
         answer=0, why={1: "The NiO edges shrink: NiO is used up.", 2: "They stay at 2d of their phase; only "
                        "their heights change.", 3: "Move the slider: the edges of NiO and Ni change a lot."},
         explanation="The height of an edge is proportional to the amount of the phase that makes it.",
         hints=["Move the slider from 0 to 100 % and watch each edge."], title="Q1. The edges")
q.choice("Why measure standards of known reduction instead of computing the heights from the crystal structures?",
         ["The real heights also depend on the porosity, the texture, the size of the grains and the resolution of "
          "the instrument; standards made and measured the same way include all that.",
          "The crystal structures of NiO and Ni are unknown.",
          "To save beamtime.",
          "The standards are needed to find the positions of the edges."],
         answer=0, why={1: "They are well known.", 2: "They cost beamtime.", 3: "The positions are 2d: known."},
         explanation="This is why Makowska et al. calibrated on whole bars weighed before and after reduction.",
         hints=["What else, besides the amount of a phase, changes the height of an edge?"], title="Q2. Why standards")
q.number("The reduction degree of the reference bar (part 6, %):", value=27, tol=6, unit="%",
         hints=["The line 'reference bar' of part 6."],
         explanation="27 % in the paper (5 min at 700 °C without load).", title="Q3. The reference")
q.number("The reduction degree in area A, the bent part of the loaded bar (%):", value=39, tol=6, unit="%",
         hints=["Part 6."], explanation="39 % in the paper.", title="Q4. The bent part")
q.number("The reduction degree in area B, beyond the load point (%):", value=28, tol=6, unit="%",
         hints=["Part 6."], explanation="28 % in the paper: the same as the reference, as it carries no stress.",
         title="Q5. Beyond the load")
q.choice("Part 6 and the map: across the bent part (top, middle, bottom slices), where is the reduction fastest?",
         ["At the top and the bottom edges, stretched and compressed: both tension and compression speed it up; the "
          "middle line, without stress, follows the reference.",
          "Only at the top (tension).", "Only at the bottom (compression).", "Evenly across the height."],
         answer=0, why={1: "Look at the bottom slice.", 2: "Look at the top slice.",
                        3: "The middle slice is lower than both edges."},
         explanation="Makowska et al. (their figure 8): both compressed and tensed slices reduced faster than the "
                     "center; the difference between them was not obvious.", hints=["Compare the three slices."],
         title="Q6. Tension and compression")
q.choice("The map shows the strongest reduction near the clamp. Why there?",
         ["The bending moment is largest at the clamp and falls to zero at the load point: so does the stress.",
          "The clamp heats the bar.", "The gas reaches the clamp first.", "It is noise."],
         answer=0, why={1: "The whole bar is at 700 °C.", 2: "The gas surrounds the whole bar.",
                        3: "It is seen in all the cells near the clamp, far above the noise."},
         explanation="For a cantilever loaded at one point, M(x) ∝ (x_load − x): largest at the clamp.",
         hints=["Where does a cantilever bend most?"], title="Q7. Near the clamp")
q.choice("**Your report to the team.**",
         ["A load speeds up the reduction where it creates stress (39 % against 28 % in 5 min at 700 °C), both in "
          "tension and in compression: the reduction of a stack under load will be uneven, which must be planned "
          "for (load, temperature, time).",
          "The load has no effect: the two bars reduce alike.",
          "The load slows down the reduction.",
          "Neutrons cannot tell NiO from Ni."],
         answer=0, why={1: "Area A of the loaded bar is well above the reference.", 2: "It speeds it up.",
                        3: "Their edges are at different wavelengths."},
         explanation="The conclusion of Makowska et al. (2015, 2016): stress enhances the reduction rate of NiO-YSZ "
                     "anode supports.", hints=["Q3, Q4 and Q6 together."], title="Q8. The report")
q.report()
""")

md(r"""
## 9. Submit your work

When you are done, tell what you thought of the exercise and submit your work.
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/anode_reduction", "bsc", quiz=q)
""")

distribute(cells, [
    ("display(w.VBox([r_s, view_r]))", [1]),
    ("display(w.VBox([button_cal, out_cal]))", [2]),
    ("display(w.VBox([button_r, out_r]))", [3, 4, 5, 6]),
    ("display(w.VBox([button_map, out_map]))", [7, 8]),
])
nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_anode.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
