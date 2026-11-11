"""Generates twin/loki/LoKI_analysis.ipynb: analysis of the data of a virtual LoKI session, step by step.

    python gen_analysis_notebook.py          # writes the notebook (keeps the outputs of the unchanged code cells)

The notebook works on any folder of the twin: a session of Python or of the console (TWIN_RUN_ROOT/loki/<session>) or
a NICOS proposal (TWIN_RUN_ROOT/data/loki/<year>/<proposal>/raw). Without a folder, it measures an empty beam, the
solvent and the silica spheres first (a few minutes; ~20 min the very first time: McStas simulations, then kept).
"""
import os

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Analyzing your LoKI data

You have measured with the virtual LoKI (web page, console or NICOS). LoKI is a **small-angle neutron scattering**
(SANS) instrument: neutrons are deflected by a few degrees at most by objects of 1 to 100 nm dispersed in the sample,
and the way the scattered intensity falls with the angle tells their **size and shape**.

This notebook takes your files and goes, step by step, from the detected neutrons to the size of the particles:
1. find your files and the logbook of the session;
2. look inside a NeXus file: what the detectors and the monitors really record;
3. reduce the data with the official ESS software (`esssans`): the scattering curve $I(Q)$ in absolute units;
4. **Guinier analysis**: the radius of gyration from the lowest $Q$;
5. **model fit** with `sasmodels`, the computing engine of SasView: radius and concentration of the particles.

Run the cells one after the other (*Shift + Enter*). Only the next cell needs your input.
""")

md(r"""
## 1. Your folder

Write in `FOLDER` the folder of your measurements:
- web page, Python or console: `f"{TWIN_RUN_ROOT}/loki/<session>"`, e.g. `f"{TWIN_RUN_ROOT}/loki/student"`;
- NICOS: the folder of your proposal, `f"{TWIN_RUN_ROOT}/data/loki/<year>/<proposal>/raw"`,
  e.g. `f"{TWIN_RUN_ROOT}/data/loki/2026/3001/raw"`.

`TWIN_RUN_ROOT` is the root of the results of the twin (`/data/twin` in the container,
`C:\Users\<you>\McStas_runs\twin` on Windows). Leave `FOLDER = None` to measure first, 10 min each, an empty beam,
the solvent and the silica spheres: a few minutes of computing (~20 min the very first time: McStas simulations of
the beamline and of the samples, then kept).
""")

code(r"""
from loki_paths import TWIN_RUN_ROOT          # root of the results of the twins
FOLDER = None                                  # or e.g. f"{TWIN_RUN_ROOT}/data/loki/2026/3001/raw"
""")

code(r"""
import sys, os, json, glob, datetime, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import scipp as sc
import h5py
import matplotlib.pyplot as plt
from loki_paths import TWIN_RUN_ROOT
import loki_reduction as red
import loki_analysis as la
import loki_samples as ls

if FOLDER is None:                                     # demonstration session
    FOLDER = f"{TWIN_RUN_ROOT}/loki/analysis_demo"
    if not red.data_files(FOLDER):
        from virtual_loki import VirtualLoki
        loki = VirtualLoki(session="analysis_demo", seed=1)
        loki.move(collimation="3m", detector_distance=5.0, heavy_shutter="open", shutter="open")
        for sample, title in (("empty_beam", "empty beam"), ("d2o", "D2O, 1 mm cell"),
                              ("silica_spheres", "silica spheres in D2O")):
            loki.move(sample=sample)
            loki.count(600, title=title)
print("folder:", FOLDER)
print("files :", [os.path.basename(f) for f in red.data_files(FOLDER)])
""")

md(r"""
## 2. The logbook: which file is what?

As at ESS, each `nexusfile_open` block in NICOS wrote **one file**, written by the ESS file writer
(`loki_job_000001.hdf`, ...; on a computer without the file writer, the twin writes them itself, one per count:
`loki_000001.nxs`, ...). Everything is in the file: its title, the sample, and the configuration of the instrument;
the table below is read from the files themselves. A SANS experiment needs three kinds of measurement,
**in the same configuration** (collimation, pulse skipping, detector distance):
- **sample**: the particles in their solvent, in a cell;
- **solvent** (the "background"): the same cell with the solvent only. Its scattering is subtracted from the sample's,
  which leaves the scattering of the particles alone;
- **empty beam**: nothing in the beam. The transmission monitor behind the sample position then counts the full beam:
  the reference for the transmission of the sample and of the solvent (the fraction of neutrons that cross them).
""")

code(r"""
rows = red.measurements(FOLDER)                         # the logbook, read from the files
def show_table(rows):                                  # a list of dicts, printed as a table
    if not rows:
        print("no measurement in the logbook"); return
    cols = list(rows[0])
    width = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(width[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(width[c]) for c in cols))

show_table(rows)
""")

md(r"""
The cell below takes the **last** sample measurement and the last solvent and empty beam measured in the same
configuration. To choose other files, write their names, e.g. `SAMPLE = "loki_job_000003.hdf"`.
""")

code(r"""
def config(r):
    return (r["collimation"], r["pulse_skipping"], r["detector_m"])

samples = [r for r in rows if r["kind"] == "sample"]
SAMPLE = samples[-1]["file"] if samples else None
same = [r for r in rows if SAMPLE and config(r) == config(samples[-1])]
last = lambda k: ([r["file"] for r in same if r["kind"] == k] or [None])[-1]
SOLVENT, EMPTY = last("solvent"), last("empty beam")
print(f"sample: {SAMPLE}   solvent: {SOLVENT}   empty beam: {EMPTY}")
if None in (SAMPLE, SOLVENT, EMPTY):
    print("A sample, a solvent and an empty beam measured in the same configuration are needed: measure the missing "
          "one(s), then run this notebook again.")
path = lambda name: f"{FOLDER}/{name}" if name else None
""")

md(r"""
## 3. Inside a NeXus file

The files have the format of the real LoKI at ESS: the twin starts from a file written by the ESS file writer at LoKI
and replaces the measured data by its own. LoKI has **9 detector banks** (`loki_detector_0` is the rear bank, 1-4 the
middle banks, 5-8 the front banks), made of tubes, each tube of 7 thin "straws", in 4 layers: about 2.8 million
pixels. Like ODIN, the detectors record **each neutron** as an *event*:
- `event_id`: the pixel hit (its position is in the file: `x_pixel_offset`, ...);
- `event_time_offset`: the arrival time, counted from the start of its source pulse (14 pulses per second);
- `event_time_zero` / `event_index`: when each pulse happened and which events belong to it.

The **monitors** (`beam_monitor_m1` before the sample, `beam_monitor_m3` after it) count the beam itself: they say how
many neutrons of each wavelength were sent, and how many crossed the sample.
""")

code(r"""
with h5py.File(path(SAMPLE), "r") as f:
    e = f["entry"]
    txt = lambda x: x.decode() if isinstance(x, bytes) else x
    print("title       :", txt(e["title"][()]), "  sample:", txt(e["sample/name"][()]))
    print("start / end :", txt(e["start_time"][()]), "/", txt(e["end_time"][()]))
    det = e["instrument/loki_detector_0"]
    ev = det["detector_events"]
    t_zero, index = ev["event_time_zero"][:3], ev["event_index"][:3]
    ids, toa = ev["event_id"][:5], ev["event_time_offset"][:5]
    numbers = det["detector_number"][()]
    pos = np.stack([det[c][()] for c in ("x_pixel_offset", "y_pixel_offset", "z_pixel_offset")], 1)
    print("\nrear bank: source pulses")
    print("  pulse   event_time_zero [ns]   = date and time (UTC)            event_index")
    for k, (tz, i0) in enumerate(zip(t_zero, index)):
        date = datetime.datetime.fromtimestamp(tz / 1e9, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        print(f"  {k:5d}   {tz:20d}   {date}   {i0:10d}")
    print("\nrear bank: first neutrons")
    print("  event   event_id (pixel)   pixel position relative to the bank [mm]   event_time_offset [ms]")
    for k, (pix, t) in enumerate(zip(ids, toa)):
        x, y, z = pos[np.searchsorted(numbers, pix)] * 1e3
        print(f"  {k:5d}   {pix:16d}   ({x:+7.1f}, {y:+7.1f}, {z:+6.1f})              {t / 1e6:9.3f}")
    print("\nevents per bank:", {b: len(e[f"instrument/{b}/detector_events/event_id"]) for b in red.BANK_GROUPS["rear"]
                                 + red.BANK_GROUPS["middle"] + red.BANK_GROUPS["front"]})
    print("monitor events:", {m: len(e[f"instrument/{m}/monitor_events/event_time_offset"])
                              for m in ("beam_monitor_m1", "beam_monitor_m3")})
    tw = e.get("twin")
    if tw is not None and "event_sampling" in tw:
        print(f"\nfraction of the neutrons written as events: {tw['event_sampling'][()]:.2e}")
""")

md(r"""
**Reading the extract.** Each neutron is a pixel number and an arrival time, nothing more: its scattering angle comes
from the position of the pixel, its wavelength from the arrival time. The pulses are 71.4 ms apart (1/14 s).

**Why only a fraction of the neutrons?** LoKI counts millions of neutrons per second; a 10-minute measurement would
give tens of GB of events. The twin writes a random sample of them (the fraction above), the **same fraction** for the
detectors and the monitors, so everything normalized by the monitors (the intensity in absolute units, the
transmission) is unchanged; only the counting noise is that of the events in the file. The group `entry/twin` holds
the settings of the twin (and, in the files the twin writes itself, this fraction): it does not exist in a real file.
The truth about the sample is not in the file: the twin keeps it apart.
""")

md(r"""
## 4. Reduction with the ESS software: $I(Q)$

**The scattering vector $Q$.** A neutron of wavelength $\lambda$ deflected by an angle $2\theta$ has
$Q = 4\pi\sin\theta/\lambda$ (Å⁻¹). A structure of size $D$ scatters mostly around $Q \approx 2\pi/D$.

The ESS workflow (`esssans`, `LokiWorkflow`, the same code as for the real LoKI) does, for each bank:
1. **arrival time → wavelength**, with a lookup table of the chopper configuration (built from the McStas beam);
2. **pixel → angle → $Q$**, from the pixel positions in the file (with the small fall of the neutrons by gravity);
3. **normalization** by the incident monitor: per wavelength, how many neutrons were sent;
4. **transmission** $T(\lambda)$: the transmission monitor of the sample (or solvent) run divided by that of the empty
   beam, each normalized by its incident monitor;
5. **solid angle** of each pixel times its efficiency (the **flat field**: not all pixels detect equally well; the
   instrument team measures it with a flat scatterer), and the **direct-beam function** $D(\lambda)$, the calibration
   that makes the result absolute (measured with a standard of known cross-section);
6. **background subtraction**: $I_\text{sample} - I_\text{solvent}$, each normalized as above.

The result, divided by the thickness of the sample (1 mm), is the differential scattering cross-section per unit
volume $d\Sigma/d\Omega$ in cm⁻¹ sr⁻¹: the fraction of neutrons scattered per cm of sample and per unit of solid angle.
It does not depend on the instrument or the counting time. About 1 min for the 9 banks (a few minutes the first time
for a configuration: the twin measures its calibration).
""")

code(r"""
BANKS = [f"loki_detector_{i}" for i in range(9)]
iq = red.reduce(path(SAMPLE), background=path(SOLVENT), empty_beam=path(EMPTY), banks=BANKS)
thickness_cm = float(red.lnx.read_twin(path(SAMPLE))["sample_thickness_m"]) * 100
groups = red.combine(iq, thickness_cm)                 # rear, middle, front: banks merged

COLORS = {"rear": "tab:blue", "middle": "tab:green", "front": "tab:red"}
fig, ax = plt.subplots(1, 2, figsize=(14, 5))
for g, (q, I, dI) in groups.items():
    ax[0].errorbar(q, I, dI, fmt="o", ms=3, lw=0.8, color=COLORS[g], label=f"{g} bank(s)")
ax[0].set(xscale="log", yscale="log", xlabel="Q [Å⁻¹]", ylabel="dΣ/dΩ [cm⁻¹ sr⁻¹]",
          title=f"{SAMPLE} − {SOLVENT}: scattering of the particles")
ax[0].legend(); ax[0].grid(alpha=0.3, which="both")

from ess.sans.types import Filename, SampleRun, TransmissionRun, EmptyBeamRun, TransmissionFraction
wf = red.workflow(path(SAMPLE))
wf[Filename[SampleRun]] = wf[Filename[TransmissionRun[SampleRun]]] = path(SAMPLE)
wf[Filename[EmptyBeamRun]] = path(EMPTY)
tf = wf.compute(TransmissionFraction[SampleRun])
ax[1].plot(tf.coords["wavelength"].values if tf.coords["wavelength"].sizes == tf.sizes else
           sc.midpoints(tf.coords["wavelength"]).values, tf.values, "k.")
ax[1].set(xlabel="wavelength λ [Å]", ylabel="transmission T", ylim=(0.5, 1.2), title="transmission of the sample")
ax[1].grid(alpha=0.3)
plt.tight_layout(); plt.show()

# from now on: the three groups of banks together, sorted by Q
q = np.concatenate([v[0] for v in groups.values()]); I = np.concatenate([v[1] for v in groups.values()])
dI = np.concatenate([v[2] for v in groups.values()])
o = np.argsort(q); q, I, dI = q[o], I[o], dI[o]
""")

md(r"""
**Reading the curve.** The three groups of banks join up: they measure the same sample at different angles. From low
to high $Q$:
- a **plateau** at low $Q$: at these large distances each particle scatters like a point; its height $I(0)$ is
  proportional to the number of particles and to the square of their volume;
- a **steep fall** with **oscillations**: the minima are the signature of particles that all have the same size
  (here spheres); their position gives the size;
- at high $Q$ the curve goes down to **zero** within the error bars: the flat scattering of the solvent has been
  subtracted (without the solvent run it would stay at about 0.05 cm⁻¹).

The transmission (right) is close to 1: a 1 mm layer of D₂O with 1 % of silica lets almost all neutrons through. Its
points scatter by a few %: the monitors count few neutrons. Count the minima on the left, and note their $Q$.
""")

md(r"""
## 5. Guinier analysis: the radius of gyration

At low $Q$, the scattering of **any** particle, whatever its shape, follows the Guinier law:

$$I(Q) \simeq I(0)\,\exp\!\left(-\frac{Q^2 R_g^2}{3}\right) \qquad \text{for } Q R_g \lesssim 1.3$$

$R_g$, the **radius of gyration**, is the root-mean-square distance of the scattering matter from the center of the
particle. Taking the logarithm, $\ln I = \ln I(0) - (R_g^2/3)\,Q^2$: a **straight line** when $\ln I$ is plotted
against $Q^2$. Its slope gives $R_g$, its intercept $I(0)$. The range $Q R_g < 1.3$ depends on $R_g$, which is not
known yet: we start with $Q < 0.02$ Å⁻¹, fit, recompute the limit $1.3/R_g$, and repeat until it no longer changes.
""")

code(r"""
def guinier(q_max):
    m = (q < q_max) & (I > 0)
    y, w = np.log(I[m]), (I[m] / dI[m]) ** 2                       # weights: 1 / (uncertainty of ln I)²
    A = np.column_stack([np.ones(m.sum()), q[m] ** 2])
    cov = np.linalg.inv(A.T @ (A * w[:, None]))                     # weighted least squares
    a, b = cov @ (A.T @ (w * y))
    rg = np.sqrt(-3 * b)
    return dict(m=m, a=a, b=b, rg=rg, drg=1.5 / rg * np.sqrt(cov[1, 1]), i0=np.exp(a), di0=np.exp(a) * np.sqrt(cov[0, 0]))

q_max = 0.02
for step in range(10):
    g = guinier(q_max)
    print(f"Q < {q_max:.4f} Å⁻¹ ({g['m'].sum()} points): Rg = {g['rg']:.2f} Å")
    if abs(1.3 / g["rg"] - q_max) < 1e-4:
        break
    q_max = 1.3 / g["rg"]
print(f"\nRg = {g['rg']:.1f} ± {g['drg']:.1f} Å,  I(0) = {g['i0']:.3f} ± {g['di0']:.3f} cm⁻¹")
print(f"for a homogeneous sphere Rg = √(3/5) R, so R = {g['rg'] / np.sqrt(0.6):.1f} Å")

m = g["m"]; show = (q < 2 * q_max) & (I > 0)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.errorbar(q[show] ** 2, np.log(I[show]), dI[show] / I[show], fmt="o", ms=3, color="0.6", lw=0.8,
            label="measured (not used)")
ax.errorbar(q[m] ** 2, np.log(I[m]), dI[m] / I[m], fmt="o", ms=3, color="tab:blue", lw=0.8,
            label=f"used: Q Rg < 1.3 ({m.sum()} points)")
qq = np.linspace(0, q[show].max(), 100)
ax.plot(qq ** 2, g["a"] + g["b"] * qq ** 2, "r-", label=f"Guinier line: Rg = {g['rg']:.1f} Å")
ax.set_xlabel("Q² [Å⁻²]"); ax.set_ylabel("ln I"); ax.set_title("Guinier plot"); ax.legend(); ax.grid(alpha=0.3)
plt.show()
""")

md(r"""
**Reading the figure.** In the blue range the points follow the straight line; beyond it (gray) they bend down: the
Guinier law is only an approximation for small $Q$. The Guinier analysis needs **no assumption on the shape**. If we
know the particles are homogeneous spheres, $R_g = \sqrt{3/5}\,R$ gives the radius.
""")

md(r"""
## 6. Fitting a model with sasmodels (SasView)

If the particles are known to be spheres, the whole curve can be fitted with their **form factor**. We use
`sasmodels`, the computing engine of **SasView**, the reference program of the SANS community: its `sphere` model
gives the cross-section in absolute units,

$$\frac{d\Sigma}{d\Omega}(Q) = \phi\,V\,\Delta\rho^2\,\left[\frac{3\,(\sin x - x\cos x)}{x^3}\right]^2 + \text{background},
\qquad x = QR,\; V = \tfrac43\pi R^3$$

with $\phi$ the volume fraction of particles (`scale` in SasView) and $\Delta\rho$ the **contrast**: the difference of
scattering length density between particles and solvent, silica ($3.47\times10^{-6}$ Å⁻²) in heavy water
($6.36\times10^{-6}$ Å⁻²). The fit adjusts $\phi$, $R$ and a small residual background to the whole curve, each point
weighted by its uncertainty. The same model, with the same parameters, can be used in the SasView program itself.
""")

code(r"""
fit = la.sphere_fit(q, I, dI, radius0=g["rg"] / np.sqrt(0.6), scale0=0.01)
R = fit["radius"]
print(f"R = {R:.2f} ± {fit['dradius']:.2f} Å,  φ = {100 * fit['phi']:.3f} ± {100 * fit['dphi']:.3f} %,  "
      f"background = {fit['background']:.4f} ± {fit['dbackground']:.4f} cm⁻¹,  reduced χ² = {fit['chi2']:.1f}")
print(f"minima of the form factor at Q = {4.493 / R:.3f} and {7.725 / R:.3f} Å⁻¹")

fig, ax = plt.subplots(2, 1, figsize=(8, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
for gname, (qb, Ib, dIb) in groups.items():
    ax[0].errorbar(qb, Ib, dIb, fmt="o", ms=3, lw=0.8, color=COLORS[gname], label=f"{gname} bank(s)")
qq = np.logspace(np.log10(q.min()), np.log10(q.max()), 600)
ax[0].plot(qq, la.sphere_intensity(fit["model"], qq, *fit["p"]), "k-", lw=1.2, label=f"sasmodels sphere: R = {R:.1f} Å")
for x0 in (4.493, 7.725):
    ax[0].axvline(x0 / R, color="0.5", ls=":", lw=1)
ax[0].set_xscale("log"); ax[0].set_yscale("log"); ax[0].set_ylim(max(I[I > 0].min() / 3, 1e-4), I.max() * 3)
ax[0].set_ylabel("dΣ/dΩ [cm⁻¹ sr⁻¹]"); ax[0].legend(); ax[0].grid(alpha=0.3, which="both")
ax[0].set_title("fit of the whole curve (dotted: minima of the form factor)")
ax[1].plot(q, (I - la.sphere_intensity(fit["model"], q, *fit["p"])) / dI, "o", ms=3, color="k")
ax[1].axhline(0, color="r", lw=1); ax[1].set_ylabel("(data − fit) / σ"); ax[1].set_xlabel("Q [Å⁻¹]")
ax[1].grid(alpha=0.3, which="both")
plt.tight_layout(); plt.show()
""")

md(r"""
**Reading the figure.** The model follows the data over several decades of intensity, and both the size and the
amount of matter come out: $\phi$ is a concentration, measured only because the data are in **absolute units** (an
arbitrary scale would give the size, but not the amount). The lower panel shows the **residuals**: the difference
between data and fit, in units of the uncertainty. For a perfect model they scatter between −2 and +2 around 0 and
the reduced χ² is close to 1. Near the minima the measured curve does not go down as deep as the model: the
instrument does not measure each $Q$ exactly (spread of wavelengths, size of the beam), which fills in the minima.
SasView can convolve the model with this **resolution** of the instrument; the twin does not provide it yet.

**A word of honesty.** These data come from a simulation (McStas, with the official model of LoKI), not from a real
instrument, and the sample is ideal: identical spheres, no interaction between them. Real particles have a spread of
sizes, which also smooths the minima. The reduction and the model, however, are those you would use at ESS.
""")

md(r"""
## 7. Going further

1. Measure the same sample for 1 min instead of 10 min (and the solvent too). How do the uncertainties on $R_g$ and
   on $R$ change? Compare with the $\sqrt{10}$ predicted by Poisson statistics.
2. Reduce the sample **without** subtracting the solvent (`red.reduce(path(SAMPLE), empty_beam=path(EMPTY))`). What
   happens at high $Q$, and to the fitted radius if you forget the background term?
3. Fit the model to the rear bank only, then to the front banks only. Which banks matter for $R$? For $\phi$?
4. (Master) Do the Guinier fit with $Q R_g < 0.8$ and $Q R_g < 2$. How does $R_g$ change, and why should the limit
   not be too high? Too low?
5. (Master) Load the curve in the SasView program (save `q, I, dI` as a text file) and fit the `sphere` model there,
   then try `sphere` with a polydispersity of the radius. Does the fit improve? Is it physically justified here?
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
out = os.path.join(HERE, "LoKI_analysis.ipynb")
kept = 0
if os.path.isfile(out):              # keep the outputs (and cell ids) of the code cells whose code is unchanged
    old = nbf.read(out, as_version=4)
    previous = {c.source: c for c in old.cells if c.cell_type == "code"}
    for c in nb.cells:
        if c.cell_type == "code" and c.source in previous:
            p = previous[c.source]
            c.outputs, c.execution_count, c["id"] = p.outputs, p.execution_count, p.get("id", c.get("id"))
            kept += bool(p.outputs)
    nb["metadata"] = old.metadata or nb["metadata"]
nbf.write(nb, out)
print("written", out, f"({kept} cells with their outputs kept)")
