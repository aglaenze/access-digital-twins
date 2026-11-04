"""Generates twin/loki/LoKI_analysis.ipynb: analysis of the data of a virtual LoKI session, step by step.

    python gen_analysis_notebook.py          # writes the notebook (no outputs: the student runs it)

The notebook works on any folder of the twin: a session of Python or of the console (TWIN_RUN_ROOT/loki/<session>) or
a NICOS proposal (TWIN_RUN_ROOT/data/loki/<year>/<proposal>/raw). Without a folder, it measures the silica spheres for
10 min first (~2 min of computing, ~15 min the very first time).
"""
import os

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Analyzing your LoKI data

You have measured with the virtual LoKI (Python, console or NICOS). LoKI is a **small-angle neutron scattering**
(SANS) instrument: neutrons are deflected by a few degrees at most by objects of 1 to 100 nm dispersed in the sample,
and the way the scattered intensity falls with the angle tells their **size and shape**.

This notebook takes your files and goes, step by step, from the scattering curve to the size of the particles:
1. find your files and the logbook of the session;
2. look inside a file;
3. plot the scattering curve $I(Q)$ of the three detector banks;
4. **Guinier analysis**: the radius of gyration from the lowest $Q$;
5. **model fit**: radius, concentration and background from the whole curve.

Run the cells one after the other (*Shift + Enter*). Only the next cell needs your input.
""")

md(r"""
## 1. Your folder

Write in `FOLDER` the folder of your measurements:
- Python or console: `f"{TWIN_RUN_ROOT}/loki/<session>"`, e.g. `f"{TWIN_RUN_ROOT}/loki/my_first_sans"`;
- NICOS: the folder of your proposal, `f"{TWIN_RUN_ROOT}/data/loki/<year>/<proposal>/raw"`,
  e.g. `f"{TWIN_RUN_ROOT}/data/loki/2026/3001/raw"`.

`TWIN_RUN_ROOT` is the root of the results of the twin (`C:\Users\<you>\McStas_runs\twin` on Windows). Leave
`FOLDER = None` to measure the silica spheres for 10 min first: about 2 min of computing, ~15 min the very first time
(McStas simulation of the beamline, then kept).
""")

code(r"""
FOLDER = None
""")

code(r"""
import sys, os, json, glob, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("."))
import numpy as np
import h5py
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from loki_paths import TWIN_RUN_ROOT
from virtual_loki import read
import loki_samples as ls

if FOLDER is None:                                     # demonstration session
    FOLDER = f"{TWIN_RUN_ROOT}/loki/analysis_demo"
    if not glob.glob(f"{FOLDER}/loki_*.h5"):
        from virtual_loki import VirtualLoki
        loki = VirtualLoki(session="analysis_demo", seed=1)
        loki.move(sample="silica_spheres", collimation="3m", heavy_shutter="open", shutter="open")
        loki.count(600, title="silica spheres, 10 min")
print("folder:", FOLDER)
print("files :", sorted(os.path.basename(f) for f in glob.glob(f"{FOLDER}/loki_*.h5")))
""")

md(r"""
## 2. The logbook

Each measurement (*count*) wrote one file `loki_000001.h5`, `loki_000002.h5`, ... and one line in the logbook
`log.jsonl`, with the state of the instrument during the count. A measurement with a shutter closed contains no
scattering curve.
""")

code(r"""
rows = []
with open(f"{FOLDER}/log.jsonl", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line)
        d = entry["details"]
        if entry["action"] != "count" or not d.get("file"):
            continue
        rows.append(dict(file=os.path.basename(d["file"]), title=d["title"], t_s=d["t"], **d["state"]))
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
The cell below takes the **last** file with both shutters open. To analyze another one, write its name, e.g.
`FILE = "loki_000002.h5"`.
""")

code(r"""
beam = [r for r in rows if r.get("heavy_shutter", "open") == "open" and r.get("shutter") == "open"]
FILE = beam[-1]["file"] if beam else None
if FILE is None:
    print("No measurement with both shutters open in this folder: measure one, then run this notebook again.")
print("file analyzed:", FILE)
""")

md(r"""
## 3. Inside the file

The file is in HDF5 (organized like folders and sub-folders, as the NeXus files of ESS). It contains the title, the
duration, the state of the instrument and, for each of the three detector banks, the scattering curve: $Q$, $I(Q)$
and its uncertainty.

**A word of honesty.** The real LoKI records each detected neutron (pixel, arrival time), and the ESS software
(`esssans`) turns these events into $I(Q)$. The twin does not write these events yet: its file already contains the
reduced curve, in absolute units. The step "events → $I(Q)$" will come with the next version of the twin.
""")

code(r"""
with h5py.File(f"{FOLDER}/{FILE}", "r") as f:
    e = f["entry"]
    txt = lambda x: x.decode() if isinstance(x, bytes) else x
    print("title   :", txt(e["title"][()]))
    print("duration:", e["duration"][()], "s")
    print("state   :", {k: txt(v[()]) for k, v in e["instrument_state"].items()})
    for g in e:
        if g.startswith("data_"):
            columns = [f"{k} [{txt(e[g][k].attrs.get('units', ''))}]" for k in e[g]]
            print(f"{g:12s}: {', '.join(columns)}, {len(e[g]['Q'])} points")
data = read(f"{FOLDER}/{FILE}")
""")

md(r"""
## 4. The scattering curve

**The scattering vector $Q$.** A neutron of wavelength $\lambda$ deflected by an angle $2\theta$ has
$Q = 4\pi\sin\theta/\lambda$ (in Å⁻¹). Small $Q$ = small angle or long wavelength. $Q$ is the natural variable because
it is linked to distances in the sample: a structure of size $D$ scatters mostly around $Q \approx 2\pi/D$.

**The three banks.** LoKI has detectors at three distances: the *rear* bank, far away (5 m here) and around the
direct beam, sees the smallest angles, hence the lowest $Q$; the *middle* and *front* banks, closer and to the side,
see larger angles. Together they cover $Q$ from 0.01 to 0.5 Å⁻¹.

**Absolute units.** $I(Q)$ is the differential scattering cross-section per unit volume $d\Sigma/d\Omega$ in
cm⁻¹ sr⁻¹: the fraction of neutrons scattered per cm of sample and per unit of solid angle. It does not depend on the
instrument or on the counting time, so it can be compared with a model.
""")

code(r"""
COLORS = {"rear": "tab:blue", "middle": "tab:green", "front": "tab:red"}
fig, ax = plt.subplots(figsize=(8, 5.5))
for bank, (q, I, dI) in data.items():
    ax.errorbar(q, I, dI, fmt="o", ms=3, lw=0.8, color=COLORS.get(bank), label=f"{bank} bank")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Q [Å⁻¹]"); ax.set_ylabel("dΣ/dΩ [cm⁻¹ sr⁻¹]")
ax.set_title(f"{FILE}: scattering curve"); ax.legend(); ax.grid(alpha=0.3, which="both")
plt.show()

# from now on: the three banks together, sorted by Q
q = np.concatenate([d[0] for d in data.values()]); I = np.concatenate([d[1] for d in data.values()])
dI = np.concatenate([d[2] for d in data.values()])
o = np.argsort(q); q, I, dI = q[o], I[o], dI[o]
""")

md(r"""
**Reading the curve.** The three banks join up: they measure the same sample. From low to high $Q$:
- a **plateau** at low $Q$: at these large distances, each particle scatters like a point; its height $I(0)$ is
  proportional to the number of particles and to the square of their volume;
- a **steep fall** with **oscillations**: the minima are the signature of particles that all have the same size
  (here spheres); their position gives the size;
- a **flat background** at high $Q$ (~0.05 cm⁻¹): the incoherent scattering of the solvent, which does not depend on
  $Q$.

Count the minima you see, and note their $Q$: you will compare them with the model in part 6.
""")

md(r"""
## 5. Guinier analysis: the radius of gyration

At low $Q$, the scattering of **any** particle, whatever its shape, follows the Guinier law:

$$I(Q) \simeq I(0)\,\exp\!\left(-\frac{Q^2 R_g^2}{3}\right) \qquad \text{for } Q R_g \lesssim 1.3$$

$R_g$, the **radius of gyration**, is the root-mean-square distance of the scattering matter from the center of the
particle. Taking the logarithm, $\ln I = \ln I(0) - (R_g^2/3)\,Q^2$: a **straight line** when $\ln I$ is plotted
against $Q^2$. Its slope gives $R_g$, its intercept $I(0)$.

Two practical points:
- the flat background is subtracted first; it is measured where the particles no longer scatter ($Q > 0.3$ Å⁻¹);
- the range $Q R_g < 1.3$ depends on $R_g$, which is not known yet: we start with $Q < 0.02$ Å⁻¹, fit, recompute the
  limit $1.3/R_g$, and repeat until it no longer changes.
""")

code(r"""
high = q > 0.3
bg = np.average(I[high], weights=1 / dI[high] ** 2)
print(f"background (Q > 0.3 Å⁻¹, {high.sum()} points): {bg:.4f} cm⁻¹")

def guinier(q_max):
    m = (q < q_max) & (I - bg > 0)
    y, w = np.log(I[m] - bg), ((I[m] - bg) / dI[m]) ** 2           # weights: 1 / (uncertainty of ln I)²
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

m = g["m"]; show = q < 2 * q_max
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.errorbar(q[show] ** 2, np.log(np.clip(I[show] - bg, 1e-6, None)), dI[show] / (I[show] - bg), fmt="o", ms=3,
            color="0.6", lw=0.8, label="measured (not used)")
ax.errorbar(q[m] ** 2, np.log(I[m] - bg), dI[m] / (I[m] - bg), fmt="o", ms=3, color="tab:blue", lw=0.8,
            label=f"used: Q Rg < 1.3 ({m.sum()} points)")
qq = np.linspace(0, q[show].max(), 100)
ax.plot(qq ** 2, g["a"] + g["b"] * qq ** 2, "r-", label=f"Guinier line: Rg = {g['rg']:.1f} Å")
ax.set_xlabel("Q² [Å⁻²]"); ax.set_ylabel("ln (I − background)")
ax.set_title("Guinier plot"); ax.legend(); ax.grid(alpha=0.3)
plt.show()
""")

md(r"""
**Reading the figure.** In the blue range the points follow the straight line; beyond it (gray) they bend down: the
Guinier law is only an approximation for small $Q$.

The Guinier analysis needs **no assumption on the shape**. If we know the particles are homogeneous spheres,
$R_g = \sqrt{3/5}\,R$ gives the radius. But here it gives a radius about 2 % too large. The instrument does not
measure each $Q$ exactly: the spread of wavelengths and the size of the beam blur the curve a little (the
**resolution**), which flattens its top and makes $R_g$ look larger. Correcting for it needs a model of the resolution.
""")

md(r"""
## 6. Fitting a model: spheres

If the particles are known to be spheres of radius $R$, the whole curve can be fitted:

$$\frac{d\Sigma}{d\Omega}(Q) = I(0)\,P(Q) + \text{background}, \qquad
P(Q) = \left[\frac{3\,(\sin x - x\cos x)}{x^3}\right]^2,\; x = QR$$

$P(Q)$, the **form factor** of a sphere, is 1 at $Q = 0$ and is zero when $\tan x = x$, i.e. $x = 4.493$, $7.725$...:
the minima of the curve are at $Q = 4.493/R$, $7.725/R$... The fit adjusts $I(0)$, $R$ and the background to the
whole curve (all banks), each point weighted by its uncertainty.
""")

code(r"""
def spheres(q, i0, R, bg):
    return i0 * ls.sphere_form_factor(q, R) + bg

p, cov = curve_fit(spheres, q, I, p0=[g["i0"], g["rg"] / np.sqrt(0.6), bg], sigma=dI, absolute_sigma=True)
err = np.sqrt(np.diag(cov))
chi2 = np.sum(((I - spheres(q, *p)) / dI) ** 2) / (len(q) - 3)
R = p[1]
print(f"R = {R:.2f} ± {err[1]:.2f} Å,  I(0) = {p[0]:.3f} ± {err[0]:.3f} cm⁻¹,  background = {p[2]:.4f} ± {err[2]:.4f} cm⁻¹")
print(f"minima expected at Q = {4.493 / R:.3f} and {7.725 / R:.3f} Å⁻¹;  reduced χ² = {chi2:.1f}")

fig, ax = plt.subplots(2, 1, figsize=(8, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
for bank, (qb, Ib, dIb) in data.items():
    ax[0].errorbar(qb, Ib, dIb, fmt="o", ms=3, lw=0.8, color=COLORS.get(bank), label=f"{bank} bank")
qq = np.logspace(np.log10(q.min()), np.log10(q.max()), 600)
ax[0].plot(qq, spheres(qq, *p), "k-", lw=1.2, label=f"sphere fit: R = {R:.1f} Å")
for x0 in (4.493, 7.725):
    ax[0].axvline(x0 / R, color="0.5", ls=":", lw=1)
ax[0].set_xscale("log"); ax[0].set_yscale("log"); ax[0].set_ylabel("dΣ/dΩ [cm⁻¹ sr⁻¹]")
ax[0].set_title("fit of the whole curve (dotted: minima of the form factor)"); ax[0].legend(); ax[0].grid(alpha=0.3, which="both")
ax[1].plot(q, (I - spheres(q, *p)) / dI, "o", ms=3, color="k")
ax[1].axhline(0, color="r", lw=1); ax[1].set_ylabel("(data − fit) / σ"); ax[1].set_xlabel("Q [Å⁻¹]")
ax[1].grid(alpha=0.3, which="both")
plt.tight_layout(); plt.show()
""")

md(r"""
**Reading the figure.** The model follows the data over two decades of intensity, and the radius is now measured
directly: with the demonstration session, R = 49.6 Å for simulated spheres of 50 Å, 1 % too small (the Guinier
analysis gave 2 % too large). The lower panel shows the **residuals**: the difference
between data and fit, in units of the uncertainty. For a perfect model they would scatter between −2 and +2 around 0,
and the reduced χ² would be close to 1. Here they are larger near the minima, where the measured curve does not go
down as deep as the model: this is again the **resolution** of the instrument, which fills in the minima. A
professional fit (e.g. with SasView) convolves the model with the resolution of the instrument.
""")

md(r"""
### What $I(0)$ tells: the concentration

For dilute particles, $I(0) = \phi\,V\,\Delta\rho^2$: $\phi$ is the volume fraction of particles, $V = \frac43\pi R^3$
their volume, and $\Delta\rho$ the **contrast**, the difference of scattering length density between particles and
solvent. For silica ($3.47\times10^{-6}$ Å⁻²) in heavy water D₂O ($6.36\times10^{-6}$ Å⁻²),
$\Delta\rho = 2.89\times10^{-6}$ Å⁻² $= 2.89\times10^{10}$ cm⁻². Knowing $R$ and $\Delta\rho$, $I(0)$ gives the
concentration:
""")

code(r"""
drho = (ls.SLD["D2O"] - ls.SLD["silica"]) * 1e10            # cm⁻²
V = 4 / 3 * np.pi * (R * 1e-8) ** 3                           # cm³
phi = p[0] / (V * drho ** 2)
print(f"volume fraction φ = {100 * phi:.2f} %  (the simulated sample: 1 %)")
""")

md(r"""
This works only because the data are in **absolute units**: an arbitrary scale would give the size, but not the
amount of matter.

**A word of honesty.** These data come from a simulation (McStas, with the official model of LoKI), not from a real
instrument, and the sample is ideal: identical spheres, no interaction between them. Real particles have a spread of
sizes, which also smooths the minima.
""")

md(r"""
## 7. Going further

1. Measure the same sample for 1 min instead of 10 min. How do the uncertainties on $R_g$ and on $R$ change? Compare
   with the $\sqrt{10}$ predicted by Poisson statistics.
2. Do the Guinier fit with $Q R_g < 0.8$ and $Q R_g < 2$. How does $R_g$ change, and why should the limit not be too
   high? Too low?
3. Fit the model to the rear bank only, then to the front bank only. Which bank is the most important for $R$? For the
   background?
4. (Master) The minima of a sphere curve are at $QR = 4.493$ and $7.725$. Read the $Q$ of the first measured minimum
   on the plot and deduce $R$ without any fit. Is it compatible with the fit?
5. (Master) Why does the resolution make $R_g$ look *larger*? Hint: average $\exp(-Q^2R_g^2/3)$ over a small spread of
   $Q$ and compare with the value at the mean $Q$.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
out = os.path.join(HERE, "LoKI_analysis.ipynb")
nbf.write(nb, out)
print("written", out)
