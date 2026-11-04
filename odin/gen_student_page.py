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

**Goal**: measure the transmission of an iron plate as a function of the neutron wavelength λ, and find a
**Bragg edge** in it.

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
## 1. Operate the instrument

After each count, a replay shows the detector filling up neutron by neutron, as on a live display; the
"chopper diagram" button shows the flight of the neutrons through the choppers for the selected mode.
The detector field of view is 14 mm × 14 mm. The iron plate (10 mm × 10 mm, 5 mm thick) is centered when the stage
is at 0. The first count with a new configuration (chopper mode, pinhole, diffuser) starts a McStas simulation and
can take a few minutes. The following ones are fast.

**Chopper modes**: *WFM* (wavelength frame multiplication) cuts the long ESS pulse into short sub-pulses: good
wavelength resolution; the separation δ of the two WFM discs sets the resolution. *Natural*: only the band-pass
choppers turn: the resolution is set by the long ESS pulse (2.86 ms). *White*: no chopper at all.
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
button = w.Button(description="Count", button_style="primary", icon="play")
out = w.Output()

def do_count(_):
    button.disabled = True
    with out:
        clear_output()
        try:
            mode, delta = chop.value
            odin.move(choppers=mode, wfm_delta=delta, shutter=shut.value, pinhole=pinh.value, diffuser=diff.value,
                      stage_x=stage.value / 1000)
            print("Measuring...")
            f = odin.count(ttime.value, title=title.value)
            clear_output()
            print(f"File written: {os.path.basename(f)}  (replay of the measurement below)")
            viz.show_live(f, n_frames=16)
        except Exception as e:
            print("Error:", e)
    button.disabled = False
    refresh_list()

diag_button = w.Button(description="Show chopper diagram", icon="clock")
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

review_button = w.Button(description="Review my logbook", icon="list")
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
button_red = w.Button(description="Compute transmission", button_style="success", icon="calculator")
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

## 4. Questions

1. At which λ does the transmission jump abruptly? Using Bragg's law ($\lambda = 2d\sin\theta$, at most $2d$),
   which distance $d$ between atomic planes do you deduce? Compare with the (110) planes of α-iron
   ($a$ = 2.867 Å, $d_{110} = a/\sqrt2$).
2. Repeat the sample measurement but forget to open the shutter. What do you see? How would you have noticed it
   without reducing the data?
3. Compare a 10 s and a 90 s measurement: how do the error bars change? Why?
4. Measure the Bragg edge with WFM δ = 0.10 m, δ = 0.45 m and in natural mode (same pinhole, same time). Which edge is
   the sharpest? Which measurement has the most counts? Explain the trade-off.
5. In white mode, the image is fine but the wavelength spectrum makes no sense. Hint: how long does a 5 Å neutron
   take to fly 60.5 m, and how far apart are two ESS pulses? What do the choppers do about it?
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_virtual.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
