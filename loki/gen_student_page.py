"""Generates twin/loki/LoKI_virtual.ipynb: the "Virtual LoKI" student page for Voilà (Bachelor level).

    python gen_student_page.py                  # writes the notebook
    voila LoKI_virtual.ipynb                    # serves it in the browser (code hidden)

Same organization as the ODIN page (../odin/gen_student_page.py): operate the instrument, logbook, analysis, questions.
At Master level, the same notebook is opened in JupyterLab, code visible; the step-by-step analysis is in
LoKI_analysis.ipynb.
"""
import os

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Virtual LoKI: small-angle neutron scattering

You are operating the LoKI instrument at ESS. Behind this page, a McStas simulation of the instrument (the official
ESS model) produces your measurements. LoKI measures **small-angle neutron scattering** (SANS): neutrons deflected by
a few degrees at most by objects of 1 to 100 nm dispersed in the sample. The way the scattered intensity falls with the
angle tells their **size and shape**.

**Goal**: measure the size of silica nanoparticles dispersed in heavy water, then choose the instrument configuration
that measures it best. Your files have the format of the real LoKI and are reduced with the official ESS software.

**The instrument, from the source to the detector**: the **choppers** select a band of wavelengths; the
**collimation** (3, 5 or 8 m long) makes the beam parallel; the **sample** scatters a small fraction of the neutrons;
three **detector banks** (front, middle, rear) record where each neutron arrives and when, which gives its scattering
angle and its wavelength.
""")

code(r"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display, clear_output
sys.path.insert(0, os.path.abspath("."))
from virtual_loki import VirtualLoki
import loki_reduction as red
import loki_analysis as la

loki = VirtualLoki(session=os.environ.get("LOKI_SESSION", "student"))
""")

md(r"""
## 1. Operate the instrument

**Your measurements, setting by setting** (set the controls below, then click *Count*):

| Measurement | Sample | Main shutter | Fast shutter | Collimation | Pulse skipping | Detector distance | Time (s) |
|---|---|---|---|---|---|---|---|
| 1. empty beam | empty beam | open | open | 3m | off | 5 m | 60 |
| 2. solvent | D2O | open | open | 3m | off | 5 m | 300 |
| 3. sample | silica spheres | open | open | 3m | off | 5 m | 300 |
| 4.-6. lower Q | the same three | open | open | **8m** | off | **10 m** | 60, 600, 600 |

Why:
- **three measurements per configuration**, as in every SANS experiment: the **sample** (particles in D₂O, in a
  cell), the **solvent** alone in the same cell (its scattering is subtracted from the sample's, leaving the
  particles), and the **empty beam** (nothing in the beam: the reference for the transmission of the two others).
  All three must be measured with the same collimation, pulse skipping and detector distance; the empty beam needs
  only the monitors, so it can be short;
- **both shutters open**: the main shutter (far upstream) and the fast shutter (just before the sample) must both be
  open for neutrons to reach the sample;
- **collimation**: a longer collimation makes the beam more parallel. Small angles can then be measured closer to the
  direct beam (lower $Q$, larger objects), with a better resolution, but the flux drops: count longer;
- **detector distance**: at 10 m the same pixel sees a smaller angle (lower $Q$). Only with the 8 m collimation: with
  its wider wavelength band, the slowest neutrons of one pulse would reach the far detector after the fastest of the
  next pulse ("frame overlap"), and the twin refuses it, as an instrument scientist would;
- **pulse skipping**: the choppers turn at 7 Hz instead of 14 Hz and let one source pulse in two through. The time
  between two pulses doubles, so the wavelength band can be twice as wide (3–21.4 Å): a wider $Q$ range in one
  measurement, with half of the pulses.

The first count with a new sample or configuration starts a McStas simulation (about 1 minute; up to 15 minutes for a
configuration never used on this computer); the following ones take about a minute (writing the events). After each
count, the image of the rear detector panel is shown.
""")

code(r"""
st = loki.status()
heavy = w.ToggleButtons(options=["closed", "open"], value=st["heavy_shutter"], description="Main shutter")
fast = w.ToggleButtons(options=["closed", "open"], value=st["shutter"], description="Fast shutter")
coll = w.ToggleButtons(options=["3m", "5m", "8m"], value=st["collimation"], description="Collimation")
skip = w.ToggleButtons(options=["off", "on"], value=st["pulse_skipping"], description="Pulse skipping")
dist = w.ToggleButtons(options=[("5 m", 5.0), ("10 m", 10.0)], value=st["detector_distance"], description="Detector")
smp = w.ToggleButtons(options=[("silica spheres", "silica_spheres"), ("D2O", "d2o"), ("empty beam", "empty_beam")],
                      value=st["sample"], description="Sample")
ttime = w.Dropdown(options=[10, 30, 60, 120, 300, 600, 1800], value=60, description="Time (s)")
title = w.Text(value="", placeholder="e.g. silica 3m", description="Title")
button = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
info = w.Output()
out = w.Output()

def show_readings():
    with info:
        clear_output()
        r = loki.readings()
        print(f"Choppers: {r['ch1_speed']:g} Hz, wavelength band {r['wavelength_band']}; "
              f"bandwidth chopper opens {r['ch1a_delay']:.1f} ms after the pulse, "
              f"frame-overlap chopper {r['ch2a_delay']:.1f} ms")

def do_count(_):
    button.disabled = True
    with out:
        clear_output()
        try:
            loki.move(heavy_shutter=heavy.value, shutter=fast.value, collimation=coll.value,
                      pulse_skipping=skip.value, detector_distance=dist.value, sample=smp.value)
            show_readings()
            print("Measuring (the first count of a configuration takes about 1 minute)...")
            f = loki.count(ttime.value, title=title.value)
            clear_output()
            print(f"File written: {os.path.basename(f)}  ({loki.last_n_counts:,} neutrons on the detectors)")
            fig, ax = plt.subplots(figsize=(6, 5))
            m = ax.imshow(np.log10(loki.last_image + 1), origin="lower", cmap="viridis", aspect="auto")
            fig.colorbar(m, ax=ax, label="log10(counts + 1)")
            ax.set(title="Rear detector panel", xlabel="tube / pixel", ylabel="pixel / tube")
            plt.show()
        except Exception as e:
            clear_output()
            print("Refused:", e)
    button.disabled = False
    refresh_list()

button.on_click(do_count)
show_readings()
display(w.VBox([smp, heavy, fast, coll, skip, dist, ttime, title, button, info, out]))
""")

md(r"""
**Reading the image.** The direct beam is stopped by the **beam stop** (the dark rectangle in the middle): it would
blind the detector. Around it, the scattered neutrons: the closer to the beam stop, the smaller the angle. With the
detector at 5 m, the sides of the rear panel are hidden by the middle bank, which sits closer to the sample.

## 2. Your measurements

Each count produces a numbered file, as on the real instrument. The table recalls the configuration of each
measurement: this is your logbook.
""")

code(r"""
listing = w.Output()

def measurements():
    out = []
    if os.path.isfile(loki.log_file):
        for l in open(loki.log_file, encoding="utf-8"):
            e = json.loads(l)
            if e["action"] == "count" and e["details"].get("file"):
                out.append(e)
    return out

def refresh_list():
    ms = measurements()
    pick.options = [(f"{os.path.basename(m['details']['file'])}: {m['details']['title'] or '(no title)'}",
                     m["details"]["file"]) for m in ms if red.kind(m["details"]["state"]) == "sample"]
    with listing:
        clear_output()
        if not ms:
            print("No measurement yet.")
        for m in ms:
            d = m["details"]; s = d["state"]
            print(f"{os.path.basename(d['file'])}  {red.kind(s):14s} {d['title'] or '(no title)':22s} "
                  f"t = {d['t']:5g} s  {s['collimation']:3s} skip {s.get('pulse_skipping', 'off'):3s} "
                  f"detector {s['detector_distance']:g} m  -> {d.get('n_counts', 0):,} neutrons")

pick = w.Dropdown(description="Sample file", layout=w.Layout(width="480px"))
refresh_list()
display(listing)
""")

md(r"""
## 3. Analyze: the size of the particles

Choose a sample file: the page finds the last solvent and empty beam measured in the same configuration, reduces the
three files with the ESS software (`esssans`: wavelength from the arrival time, $Q$ from the pixel, normalization by
the monitors, transmission, solid angle, subtraction of the solvent) and gives the **scattering curve** $I(Q)$ of the
particles in absolute units (cm⁻¹ sr⁻¹). About 1 minute (a few minutes the first time for a configuration).
$Q = 4\pi\sin\theta/\lambda$ combines the scattering angle $2\theta$ and the wavelength $\lambda$: a structure of size
$D$ scatters mostly around $Q \approx 2\pi/D$.

Then two analyses:
- **Guinier**: at small $Q$, $\ln I = \ln I(0) - (R_g^2/3)\,Q^2$ for any particle shape. The slope of $\ln I$ against
  $Q^2$ gives the **radius of gyration** $R_g$; for a sphere, $R = \sqrt{5/3}\,R_g$;
- **sphere model** of SasView (`sasmodels`): the whole curve fitted with the scattering of spheres of radius $R$
  (minima at $Q = 4.49/R$, $7.73/R$...), which also gives their volume fraction $\phi$.
""")

code(r"""
button_an = w.Button(description="Analyze", button_style="success", icon="calculator", layout=w.Layout(width="auto"))
out_an = w.Output()
COLORS = {"rear": "tab:blue", "middle": "tab:green", "front": "tab:red"}

def partners(sample_file):
    # last solvent and empty beam measured in the configuration of the sample file
    ms = measurements()
    me = next(m for m in ms if m["details"]["file"] == sample_file)
    cfg = lambda m: tuple(m["details"]["state"][k] for k in ("collimation", "pulse_skipping", "detector_distance"))
    found = {}
    for m in ms:
        if cfg(m) == cfg(me):
            found[red.kind(m["details"]["state"])] = m["details"]["file"]
    return found.get("solvent"), found.get("empty beam")

def analyze(_):
    button_an.disabled = True
    with out_an:
        clear_output()
        try:
            if not pick.value:
                print("Measure a sample first (with both shutters open)."); return
            sample = pick.value if os.path.isabs(pick.value) else os.path.join(loki.folder, pick.value)
            solvent, empty = partners(pick.value)
            if solvent is None or empty is None:
                print("Missing in this configuration:", ", ".join(n for n, f in (("the solvent (D2O)", solvent),
                      ("the empty beam", empty)) if f is None) + ". Measure it, then click Analyze again."); return
            full = lambda f: f if os.path.isabs(f) else os.path.join(loki.folder, f)
            print(f"Reducing {os.path.basename(sample)} - {os.path.basename(solvent)} "
                  f"(empty beam {os.path.basename(empty)}) with esssans...")
            iq = red.reduce(full(sample), background=full(solvent), empty_beam=full(empty),
                            banks=[f"loki_detector_{i}" for i in range(9)])
            thickness_cm = float(red.lnx.read_twin(full(sample))["sample_thickness_m"]) * 100
            groups = red.combine(iq, thickness_cm)
            q = np.concatenate([v[0] for v in groups.values()]); I = np.concatenate([v[1] for v in groups.values()])
            dI = np.concatenate([v[2] for v in groups.values()])
            o = np.argsort(q); q, I, dI = q[o], I[o], dI[o]
            g = la.guinier(q, I, dI)
            fit = la.sphere_fit(q, I, dI, radius0=g["rg"] / np.sqrt(0.6) if g else 50.0)
            clear_output()
            fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
            for gname, (qb, Ib, dIb) in groups.items():
                ax[0].errorbar(qb, Ib, dIb, fmt="o", ms=3, lw=0.8, color=COLORS[gname], label=f"{gname} bank(s)")
            qq = np.logspace(np.log10(q.min()), np.log10(q.max()), 500)
            ax[0].plot(qq, la.sphere_intensity(fit["model"], qq, *fit["p"]), "k-", lw=1.2,
                       label=f"spheres, R = {fit['radius']:.1f} Å")
            ax[0].set(xscale="log", yscale="log", xlabel="Q (Å⁻¹)", ylabel="I (cm⁻¹ sr⁻¹)",
                      ylim=(max(I[I > 0].min() / 3, 1e-4), I.max() * 3), title="Scattering curve of the particles")
            ax[0].legend(); ax[0].grid(alpha=0.3, which="both")
            if g:
                m = g["mask"]; show = (q < 2.5 * g["q_max"]) & (I > 0)
                ax[1].errorbar(q[show] ** 2, np.log(I[show]), dI[show] / I[show], fmt="o", ms=3, color="0.6", lw=0.8,
                               label="measured")
                ax[1].errorbar(q[m] ** 2, np.log(I[m]), dI[m] / I[m], fmt="o", ms=3, color="tab:blue", lw=0.8,
                               label="used: Q Rg < 1.3")
                x2 = np.linspace(0, (q[show] ** 2).max(), 50)
                ax[1].plot(x2, g["a"] + g["b"] * x2, "r-", label=f"Rg = {g['rg']:.1f} Å")
                ax[1].set(xlabel="Q² (Å⁻²)", ylabel="ln I", title="Guinier plot"); ax[1].legend()
                ax[1].grid(alpha=0.3)
            plt.tight_layout(); plt.show()
            if g:
                print(f"Guinier: Rg = {g['rg']:.1f} ± {g['drg']:.1f} Å ({g['mask'].sum()} points, Q < {g['q_max']:.4f} Å⁻¹)"
                      f" -> sphere radius R = {g['rg'] / np.sqrt(0.6):.1f} Å")
            else:
                print("Guinier: not enough points at small Q (choose a configuration that reaches lower Q).")
            print(f"Sphere model (sasmodels): R = {fit['radius']:.1f} ± {fit['dradius']:.1f} Å, "
                  f"volume fraction φ = {100 * fit['phi']:.2f} %, reduced χ² = {fit['chi2']:.1f}")
        except Exception as e:
            print("Analysis failed:", e)
        finally:
            button_an.disabled = False

button_an.on_click(analyze)
display(w.VBox([pick, button_an, out_an]))
""")

md(r"""
**How the twin produces your measurements (and its limits).** The beamline up to the sample is the official McStas
model of LoKI, simulated once per configuration. The sample scatters with the exact cross-section of identical silica
spheres. Each detected neutron is written, with its pixel of the real LoKI and its arrival time, in a NeXus file of
the real instrument's format, then reduced by the ESS software. Simplifications: the files hold a random sample of
the neutrons (LoKI counts millions per second), the empty cell is not measured separately (the solvent run includes
the cell), and the transmission monitor always sees the beam.

## 4. Questions

1. From your first measurements, what is the radius of the particles? Do the Guinier analysis and the sphere model
   agree? Which one needs an assumption on the shape?
2. Measure the sample for 30 s and for 300 s in the same configuration: how do the error bars change? Is the radius
   more precise?
3. Compare the lowest $Q$ of the rear bank with the 3 m collimation (detector at 5 m) and with the 8 m collimation
   (detector at 10 m). Why does it matter for larger particles? What do you pay for it?
4. Try the 3 m collimation with the detector at 10 m. The twin refuses: explain with numbers. A 11.5 Å neutron flies
   $v = 3956/11.5$ m/s; how long does it take to travel 33.5 m from the source to the far detector, and how far apart
   are two ESS pulses?
5. With pulse skipping, which banks see a wider $Q$ range, and why?
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "LoKI_virtual.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
