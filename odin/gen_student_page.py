"""Generates twin/odin/ODIN_virtual.ipynb: the "Virtual ODIN" student page for Voilà (Bachelor level).

    python gen_student_page.py                  # writes the notebook
    voila ODIN_virtual.ipynb                    # serves it in the browser (code hidden)

At Master level, the same notebook is opened in JupyterLab, code visible.
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Virtual ODIN: wavelength-resolved radiography

You are operating the ODIN imaging instrument at ESS. Behind this page, a McStas simulation of the instrument produces
your measurements. The files are in the ESS NeXus format, and the reduction uses the official `essimaging` code, the
same one that will be used for real ODIN data.

**Your mission.** You are a materials engineer at a company that builds parts for research facilities. A supplier
has delivered steel plates sold as *ferritic* steel: α-iron, whose atoms sit on a body-centered cubic lattice. A mix-up
with *austenitic* steel (γ-iron, face-centered cubic) would matter: austenitic steel is not magnetic and expands more
when heated. You may not cut the plates. Neutrons go through centimeters of steel, and the wavelengths at which the
transmission jumps, the **Bragg edges**, are set by the distances between the planes of atoms: they reveal the
crystal structure. Your job: measure the transmission of a plate as a function of the neutron wavelength λ, find its
Bragg edges, and give your verdict to the supplier (part 4): α-iron or not, and with which lattice parameter?

**You need three measurements**:
1. the **dark** run: shutter closed. The detector still records a few counts (gamma rays, fast neutrons): the background;
2. the **open beam**: shutter open, sample moved **out** of the beam (stage moved);
3. the **sample**: shutter open, sample in the beam.
""")

code(r"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
import scipp as sc
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display, clear_output
sys.path.insert(0, os.path.abspath("."))
from odin_virtual import VirtualOdin, LAM_RANGE
import odin_reduction as red, odin_viz as viz, odin_games as games

odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
""")

md(r"""
## 0. Your sample

Choose the sample to mount on the stage. The drawing shows it as the neutrons see it (left: the 14 mm field of view
of the camera, dashed) and from above (right: its thickness along the beam). The exercise of this page uses the
**iron plate**; the other samples are there to compare.
""")

code(r"""
import sample_library as sl
smp = w.Dropdown(options=[(odin.sample_spec(n).get("name", n), n) for n in odin.samples()],
                 value=odin.status()["sample"], description="Sample", layout=w.Layout(width="420px"))
smp_out = w.Output()

def show_sample(_=None):
    with smp_out:
        clear_output(wait=True)
        spec = odin.sample_spec(smp.value)
        print(sl.describe("odin", spec))
        sl.draw("odin", spec, fig=plt.figure(figsize=(10, 4)))
        sl.show()

smp.observe(show_sample, "value")
show_sample()
display(w.VBox([smp, smp_out]))
""")

md(r"""
## 1. Operate the instrument

After each count, a replay shows the detector filling up neutron by neutron, as on a live display; the
"chopper diagram" button shows the flight of the neutrons through the choppers for the selected mode.
The detector field of view is 14 mm × 14 mm. The iron plate (10 mm × 10 mm, 5 mm thick) is centered when the stage
is at 0. The first count with a new configuration (chopper mode, pinhole, diffuser) starts a McStas simulation and
can take a few minutes. The following ones are fast.

**Chopper modes**: *WFM* (wavelength frame multiplication) cuts the long ESS pulse into short sub-pulses: good
wavelength resolution; the separation δ of the two WFM discs sets the resolution. *Natural*: only the band-pass
choppers turn: the resolution is set by the long ESS pulse (2.86 ms). *White*: no chopper at all.

**Your three measurements, setting by setting** (set the controls below, then click *Count*; one count per row):

| Measurement | Choppers | Shutter | Pinhole D | Diffuser | Stage x (mm) | Time (s) | Title |
|---|---|---|---|---|---|---|---|
| 1. dark | WFM, δ = 0.30 m | **closed** | 3 cm | in | 0 | 30 | dark |
| 2. open beam | WFM, δ = 0.30 m | **open** | 3 cm | in | **500** | 60 | open beam |
| 3. sample | WFM, δ = 0.30 m | **open** | 3 cm | in | **0** | 60 | iron plate |

Only the shutter and the stage change from one row to the next (in bold). Why:
- **choppers, pinhole and diffuser stay the same** for the three measurements: they set the beam (its wavelengths,
  its size, its homogeneity), and the open beam is used to divide the sample measurement: both must see *the same*
  beam, otherwise the ratio means nothing;
- **stage x = 500 mm** for the open beam: the plate is moved 50 cm aside, far out of the 14 mm field of view (any
  value beyond 20 mm works); **0 mm** puts it back in the middle of the beam;
- **times**: the dark run contains very few counts, 30 s are enough (it is scaled to the duration of the other
  measurements). For the open beam and the sample, 60 s give error bars of about 1 % on the transmission; longer
  counts give smaller error bars (÷2 for 4 times longer);
- the **title** is free, but a clear title helps you find your files later.
""")

code(r"""
st = odin.status()
CHOP = [("WFM, δ = 0.30 m (reference)", ("wfm", 0.30)), ("WFM, δ = 0.10 m", ("wfm", 0.10)),
        ("WFM, δ = 0.45 m", ("wfm", 0.45)), ("natural (band-pass only)", ("natural", 0.30)), ("white (no chopper)", ("white", 0.30))]
chop = w.Dropdown(options=CHOP, value=("wfm", 0.30), description="Choppers", layout=w.Layout(width="420px"))
shut = w.ToggleButtons(options=[("closed", "closed"), ("open", "open")], value=st["shutter"], description="Shutter")
pinh = w.Dropdown(options=[("1 cm", 0.01), ("2 cm", 0.02), ("3 cm", 0.03), ("4 cm", 0.04)], value=st["pinhole"],
                  description="Pinhole D")
diff = w.ToggleButtons(options=[("in", "in"), ("out", "out")], value=st["diffuser"], description="Diffuser")
stage = w.BoundedFloatText(value=st["stage_x"] * 1000, min=-500, max=500, step=1, description="Stage x (mm)")
ttime = w.Dropdown(options=[2, 5, 10, 30, 60, 90], value=30, description="Time (s)")
title = w.Text(value="", placeholder="e.g. open beam", description="Title")
button = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
out = w.Output()

def do_count(_):
    button.disabled = True
    with out:
        clear_output()
        try:
            mode, delta = chop.value
            odin.move(choppers=mode, wfm_delta=delta, shutter=shut.value, pinhole=pinh.value, diffuser=diff.value,
                      stage_x=stage.value / 1000, sample=smp.value)
            print("Measuring...")
            f = odin.count(ttime.value, title=title.value)
            clear_output()
            print(f"File written: {os.path.basename(f)}  (replay of the measurement below)")
            viz.show_live(f, n_frames=16)
        except Exception as e:
            print("Error:", e)
    button.disabled = False
    refresh_list()

diag_button = w.Button(description="Show chopper diagram", icon="clock", layout=w.Layout(width="auto"))
diag_out = w.Output()

def show_diagram(_):
    with diag_out:
        clear_output()
        mode, delta = chop.value
        fig, ax = plt.subplots(figsize=(8, 5)); viz.chopper_diagram(mode, delta, ax=ax, neutrons=30_000); plt.show()

button.on_click(do_count); diag_button.on_click(show_diagram)
display(w.VBox([chop, shut, pinh, diff, stage, ttime, title, w.HBox([button, diag_button]), out, diag_out]))
""")

md(r"""
## 2. Your measurements

Each count produces a numbered file, as on the real instrument. The table recalls the state of the instrument during
each measurement: this is your logbook.
""")

code(r"""
listing = w.Output()

def measurements():
    out = []
    if os.path.isfile(odin.log_file):
        for l in open(odin.log_file, encoding="utf-8"):
            e = json.loads(l)
            if e["action"] == "count":
                out.append(e)
    return out

def refresh_list():
    ms = measurements()
    opts = [(f"{m['details']['file']}: {m['details']['title'] or '(no title)'}",
             os.path.join(odin.folder, m["details"]["file"])) for m in ms]
    for dd in (pick_E, pick_O, pick_N):
        dd.options = opts
    with listing:
        clear_output()
        if not ms:
            print("No measurement yet.")
        for m in ms:
            d = m["details"]; s = d["state"]
            chop_txt = s["choppers"] + (f" δ={s['wfm_delta']:.2f}" if s["choppers"] == "wfm" else "")
            print(f"{d['file']}  {d['title'] or '(no title)':20s} t = {d['t']:4g} s  {chop_txt:12s} shutter {s['shutter']:6s} "
                  f"D = {s['pinhole']*100:.0f} cm  diffuser {s['diffuser']:3s} stage x = {s['stage_x']*1000:+.0f} mm "
                  f"-> {d['n_counts']:,} counts"
                  + (f"  (simulation quality: error bars ×{d['mc_factor']:.1f} too small)" if d.get('mc_factor', 1) > 1.2 else ""))

review_button = w.Button(description="Review my logbook", icon="list", layout=w.Layout(width="auto"))
review_out = w.Output()

def do_review(_):
    with review_out:
        clear_output()
        if not os.path.isfile(odin.log_file):
            print("No measurement yet."); return
        checks, badges = games.review_log(odin.log_file)
        for ok, msg in checks:
            print(("OK   " if ok else "!!   ") + msg)
        print("Badges:", ", ".join(badges) if badges else "none yet")

review_button.on_click(do_review)
pick_E = w.Dropdown(description="Sample", layout=w.Layout(width="480px"))
pick_O = w.Dropdown(description="Open beam", layout=w.Layout(width="480px"))
pick_N = w.Dropdown(description="Dark", layout=w.Layout(width="480px"))
refresh_list()
display(w.VBox([listing, review_button, review_out]))
""")

md(r"""
## 3. Reduce: from the raw image to the transmission

For each pixel and each λ, the transmission is

$$T = \frac{E - N}{O - N}$$

with $E$, $O$ and $N$ the counts of the sample, open-beam and dark runs. The dark run is first scaled to the duration
of each measurement and subtracted. Then each measurement is divided by the **proton charge** received by the target
during the measurement (it is recorded in the file): the number of neutrons produced by the source is proportional to
it, and the source power is never perfectly constant. The λ of each neutron is computed from its arrival time, with
the chopper settings and distances written in the file.

The spectrum $T(\lambda)$ is computed in the central 6 mm × 6 mm square (red on the image).
""")

code(r"""
button_red = w.Button(description="Compute transmission", button_style="success", icon="calculator", layout=w.Layout(width="auto"))
out_red = w.Output()
ROI = (-3, 3, -3, 3)                                     # mm

def reduce_runs(_):
    with out_red:
        clear_output()
        if not (pick_E.value and pick_O.value):
            print("Choose at least a sample run and an open-beam run."); return
        print("Reducing...")
        N = pick_N.value if pick_N.value not in (pick_E.value, pick_O.value) else None
        lo, hi = LAM_RANGE[chop.value[0]]
        lam = sc.linspace("wavelength", lo, hi, 201, unit="angstrom")
        r = red.reduce(pick_E.value, pick_O.value, N, lam=lam, roi=ROI, n_pixels=64)
        img, spec = r["image"], r["spectrum"]
        clear_output()
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw=dict(width_ratios=[1, 1.5]))
        im = ax[0].pcolormesh(img.coords["x"].values, img.coords["y"].values, img.values, vmin=0, vmax=1.2, cmap="gray")
        ax[0].add_patch(plt.Rectangle((ROI[0], ROI[2]), ROI[1] - ROI[0], ROI[3] - ROI[2], fill=False, ec="r", lw=1.5))
        ax[0].set(aspect="equal", xlabel="x (mm)", ylabel="y (mm)", title="Transmission (all λ)")
        fig.colorbar(im, ax=ax[0], label="T")
        lc = sc.midpoints(spec.coords["wavelength"]).values
        ax[1].errorbar(lc, spec.values, yerr=np.sqrt(spec.variances), fmt=".", ms=3, lw=0.6)
        ax[1].set(xlabel="λ (Å)", ylabel="T", title="Transmission at the center of the sample", ylim=(0, 1.1))
        ax[1].grid(alpha=0.3)
        plt.tight_layout(); plt.show()
        if N is None:
            print("Note: no dark run chosen, the background is not subtracted.")
        print("Use the same chopper mode for the three runs and select that mode above before reducing.")

button_red.on_click(reduce_runs)
display(w.VBox([pick_E, pick_O, pick_N, button_red, out_red]))
""")

md(r"""
**How the twin produces your measurements (and its limit).** The real ODIN counts hundreds of thousands of neutrons per
second on this small detector: no simulation can follow it neutron by neutron. The twin therefore simulates with
McStas the whole path of the neutrons up to the sample (source, choppers, guides, pinhole, diffuser), then computes
the attenuation by the sample with the Beer-Lambert law and the NCrystal cross-sections. What it neglects: neutrons
**scattered** by the sample that still reach the detector (here less than 0.3 % of the signal, checked with a full
McStas simulation).

## 4. Questions: your verdict, and the instrument

Answer in the boxes, then click *Check*. A wrong answer is explained; after a try you can also show the answer.
Your answers are kept, and *My results* (at the end) gives your score and a report to download.
""")

code(r"""
import quiz
q = quiz.Quiz("odin_iron_bsc")
q.number("On your transmission $T(\\lambda)$ of the iron plate, at which wavelength is the **last** Bragg edge (the "
         "jump at the largest λ)?", value=4.054, tol=0.05, unit="Å",
         mistakes=[(2.867, "an edge too, the (200) one; look for the last jump, at the largest λ"),
                   (2.340, "an edge too, the (211) one; look for the last jump, at the largest λ")],
         hints=["Look at the reduced spectrum of part 3: beyond the last edge the transmission is high and smooth.",
                "The last edge of iron is between 3.5 and 4.5 Å."],
         explanation="Beyond 4.05 Å no family of planes can diffract any more, so the neutrons go straight through: "
                     "the transmission jumps up.", title="Q1. The last edge")
q.number("Bragg's law: $\\lambda = 2d\\sin\\theta$. Which distance $d$ between the planes of atoms gives this last "
         "edge?", value=2.027, tol=0.03, unit="Å",
         mistakes=[(4.054, "λ itself. At the edge the neutrons are scattered straight back, sin θ = 1, so λ = 2d"),
                   (2.867, "the lattice parameter a, not the distance d of the planes (next question)")],
         hints=["The largest λ that can still be diffracted is reached for θ = 90°.", "d = λ_edge / 2."],
         explanation="At the edge sin θ = 1, so $d = \\lambda_\\mathrm{edge}/2$ = 2.027 Å: the (110) planes, the most widely "
                     "spaced planes of a body-centered cubic lattice.", title="Q2. The distance between the planes")
q.number("In a cubic lattice the (110) planes are $d_{110} = a/\\sqrt{2}$ apart. Which lattice parameter $a$ "
         "do you deduce?", value=2.867, tol=0.04, unit="Å",
         mistakes=[(2.027, "d itself; multiply by √2"), (1.433, "you divided by √2; d_110 = a/√2, so a = d_110·√2"),
                   (4.054, "λ_edge; a = (λ_edge/2)·√2")],
         explanation="$a = d_{110}\\sqrt{2}$ = 2.867 Å: the lattice parameter of α-iron (2.8665 Å).",
         hints=['Start from d_110 = a/√2 and solve for a.', 'a = d_110 × √2, with the d of question 2 (about 2.03 Å).'],
         title="Q3. The lattice parameter")
q.choice("**Your verdict for the supplier.** α-iron (body-centered cubic, a = 2.87 Å) has its edges at 4.05, 2.87 and "
         "2.34 Å; γ-iron (face-centered cubic, a = 3.59 Å) would have its last edges at 4.15 and 3.59 Å. What do you "
         "write?", ["The plates are α-iron (ferritic): edges at 4.05, 2.87 and 2.34 Å, a = 2.87 Å.",
                    "The plates are γ-iron (austenitic).",
                    "Neutrons cannot tell: both are iron.",
                    "We would have to cut a plate to know."],
         answer=0, why={1: "γ-iron would show an edge at 3.59 Å and its last edge at 4.15 Å, not at 4.05 Å.",
                        2: "The atoms are the same, but not their arrangement: the edges come from the distances "
                           "between the planes, which differ between the two structures.",
                        3: "No need: the neutrons went through 5 mm of steel, the measurement is non-destructive."},
         explanation="The edges of your plate are those of a body-centered cubic lattice with a = 2.87 Å: the supplier "
                     "delivered ferritic steel, as ordered. Neutrons saw it without cutting the plate.",
         hints=['Compare the edges you measured with the two lists given in the question.', 'Your last edge is at 4.05 Å, not 4.15 Å; do you see an edge at 3.59 Å?'],
         title="Q4. The verdict")
q.choice("You measure the sample again but forget to open the shutter. How can you notice it **without** reducing the "
         "data?", ["The logbook (part 2) shows only a few hundred counts, like the dark run, instead of tens of millions.",
                   "The transmission is larger than 1.",
                   "Nothing shows it before the reduction.",
                   "The Bragg edges move to shorter wavelengths."],
         answer=0, why={1: "The transmission would rather be close to 0: almost no neutrons reach the detector.",
                        2: "The number of counts of each file is in the logbook: a closed shutter divides it by about "
                           "10⁵.",
                        3: "The edges are set by the iron, not by the shutter; here there is simply no beam."},
         explanation="With the shutter closed the detector only sees the background, like the dark run. Always look at "
                     "the number of counts of a file before analyzing it.", hints=['What does the detector receive when no neutron beam comes in? Which of your runs looks like that?', 'Look at the column of counts of the logbook (part 2): the dark run has a few hundred, the others millions.'],
         title="Q5. A forgotten shutter")
q.choice("You measure the plate for 10 s, then for 90 s. How do the error bars of the transmission change?",
         ["About 3 times smaller", "About 9 times smaller", "The same", "About 3 times larger"],
         answer=0, why={1: "The number of counts N is 9 times larger, but the error on N is √N: relative error ∝ 1/√N, "
                           "so 1/√9 = 1/3.",
                        2: "More neutrons, so a better relative precision: the error bars shrink.",
                        3: "Counting longer collects more neutrons and always improves the precision."},
         explanation="Counting statistics: N counts have an uncertainty √N, so the relative error goes as 1/√N. Nine "
                     "times longer gives errors 3 times smaller.", hints=['N counts have an uncertainty √N: what happens to √N/N when N is 9 times larger?', '√9 = 3.'],
         title="Q6. Counting time")
q.choice("Measure the edge with WFM δ = 0.10 m, δ = 0.45 m and in natural mode (same pinhole, same time). Which is "
         "true?", ["δ = 0.10 m gives the sharpest edge; natural mode gives the most counts.",
                   "Natural mode gives the sharpest edge and the most counts.",
                   "δ = 0.45 m gives the sharpest edge; δ = 0.10 m the most counts.",
                   "All three give the same edge: only the counting time matters."],
         answer=0, why={1: "In natural mode the wavelength resolution is set by the long ESS pulse (2.86 ms): many "
                           "neutrons, but a broad edge.",
                        2: "The other way round: the closer the two WFM discs (small δ), the shorter the sub-pulses, "
                           "the sharper the edge, and the fewer the neutrons.",
                        3: "The chopper setting changes the wavelength resolution, so the width of the edge."},
         explanation="Resolution and flux are a trade-off: δ = 0.10 m cuts the shortest sub-pulses (sharpest edge, "
                     "about 3 times fewer neutrons than δ = 0.30 m), natural mode lets the whole pulse through (about "
                     "15 times more neutrons than δ = 0.30 m, broad edge).", hints=['A sharper edge needs a better wavelength resolution, i.e. shorter neutron pulses. Shorter pulses: more or fewer neutrons?', 'In WFM mode the closer the two discs (small δ), the shorter the sub-pulses; natural mode keeps the whole 2.86 ms pulse.'],
         title="Q7. Resolution or flux?")
q.number("White mode (no chopper): how long does a 5 Å neutron take to fly the 60.5 m from the source to the "
         "detector? (speed $v$ = 3956/λ m/s, λ in Å)", value=76.5, tol=1.5, unit="ms",
         mistakes=[(0.0765, "in seconds; the answer is asked in ms"), (13.1, "the inverse; t = L / v")],
         hints=['First the speed: v = 3956/λ with λ = 5 Å.', 't = L / v = 60.5 m / 791 m/s, then convert seconds into milliseconds (× 1000).'],
         explanation="v = 791 m/s, t = 60.5/791 = 76.5 ms. Two ESS pulses are 1/14 s = 71.4 ms apart: this neutron "
                     "arrives after the next pulse has started, mixed with fast neutrons of that pulse.",
         title="Q8. Time of flight")
q.choice("So why does the wavelength spectrum make no sense in white mode?",
         ["Slow neutrons of one pulse arrive together with fast neutrons of the next one: the arrival time no longer "
          "gives a single λ. The choppers select a band of wavelengths to prevent it.",
          "Without choppers there are no neutrons.",
          "The detector cannot count that fast.",
          "The iron plate blocks the slow neutrons."],
         answer=0, why={1: "There are even more neutrons without choppers: the image is fine.",
                        2: "The image is fine, so the counting works; the problem is the wavelength.",
                        3: "The edges are still there; the problem is the conversion from time to λ."},
         explanation="Frame overlap: λ is computed from the arrival time, which only works if the neutrons of "
                     "successive pulses do not overlap. Beyond 4.7 Å (60.5 m in 71.4 ms) they do; the band-pass "
                     "choppers cut the band so that they never meet.", hints=['Compare your answer to Q8 (76.5 ms) with the time between two ESS pulses (1/14 s).', 'λ is computed from the arrival time, counted from the last pulse. What if the neutron arrives after the next pulse?'],
         title="Q9. Frame overlap")
q.report()
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_virtual.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
