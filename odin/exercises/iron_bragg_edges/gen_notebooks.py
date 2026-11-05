"""Generates the notebooks of the exercise "How far apart are the atoms in iron?" from the guided analysis notebook
odin/ODIN_analysis.ipynb (one source: a correction there reaches every level when this script is run again):

  * ODIN_iron_msc.ipynb       MSc, "develop the method": parts 1-5 of the guided notebook (files, NeXus, raw counts,
                              reduction with the ESS software), then tasks: write the Bragg-edge model and the fit
                              yourself, checked automatically; then a systematic error to investigate;
  * ODIN_iron_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only, no guidance.

    python gen_notebooks.py
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "..", "ODIN_analysis.ipynb")
PATH_CELL = ('import sys, os\n'
             'sys.path.insert(0, os.path.abspath("../.."))     # the modules of the ODIN twin (folder odin/)')


def section(cells, title):
    """Index of the markdown cell starting with `title`."""
    return next(k for k, c in enumerate(cells) if c.cell_type == "markdown" and c.source.startswith(title))


def clean(c):
    c = nbf.v4.new_code_cell(c.source) if c.cell_type == "code" else nbf.v4.new_markdown_cell(c.source)
    c.source = c.source.replace('sys.path.insert(0, os.path.abspath("."))', 'sys.path.insert(0, os.path.abspath("../.."))')
    return c


def write(cells, name):
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                      "language_info": {"name": "python"}}
    nbf.write(nb, os.path.join(HERE, name))
    print("written", name, len(cells), "cells")


SAMPLE_CELL = r"""sys.path.insert(0, os.path.abspath("../../.."))  # the sample library (twin/sample_library.py)
import sample_library as sl, matplotlib.pyplot as plt
for name, hidden in sl.exercise_hidden("exercise.yml").items():
    spec = sl.load("odin")[name]
    print(sl.describe("odin", spec, hidden))
    sl.draw("odin", spec, hidden=hidden, fig=plt.figure(figsize=(10, 3.5))); plt.show()"""
md = lambda s: nbf.v4.new_markdown_cell(s.strip())
code = lambda s: nbf.v4.new_code_cell(s.strip())
src = nbf.read(SOURCE, as_version=4).cells
FOLDER_CELL = code(
    'from odin_paths import TWIN_RUN_ROOT          # root of the results of the twins\n'
    'FOLDER = None                                  # your folder, e.g. f"{TWIN_RUN_ROOT}/odin/<session>";\n'
    '                                               # None: a demonstration session is measured first (about 1 min)')

# --------------------------------------------------------------------------- MSc
i1, i6 = section(src, "## 1."), section(src, "## 6.")
msc = [md(r"""
# How far apart are the atoms in iron? (MSc)

You will measure the **Bragg edges** of an iron plate with the virtual ODIN and deduce the spacing of its atomic planes.
Parts 1 to 5 are guided: they take your files from the raw neutrons to the transmission $T(\lambda)$, with the
official ESS reduction. Part 6 is yours: **you write the model and the fit**, and a check cell tells you whether your
result is right (the twin knows the true sample). Part 7 is about the method itself: a systematic error to track down.

Measure first in NICOS (a dark, an open beam and the iron plate; your files are in the folder of your proposal,
`f"{TWIN_RUN_ROOT}/data/odin/<year>/<proposal>/raw"`), or leave `FOLDER = None` below to start with a short
demonstration session.

**The measurements in NICOS** (click *Open NICOS* in the app: NICOS of ODIN opens, ready; give a proposal
number in the *Experiment* panel, then type in the command line or the *Scripting* tab):
```
move(shutter, 'closed')
with nexusfile_open('dark'):
    count(t=30)
move(shutter, 'open', stage_x, 500)
with nexusfile_open('open beam'):
    count(t=60)
move(stage_x, 0)
with nexusfile_open('iron plate'):
    count(t=60)
```
Why these settings: the choppers (WFM, δ = 0.30 m) and the pinhole stay the same for the three runs, so that the
open beam can divide the sample run; the stage is moved 500 mm aside for the open beam (the field of view is 14 mm).
"""), code(PATH_CELL), md("**Your sample** (from the sample library):"),
       code(SAMPLE_CELL)]
for c in src[i1:i6]:
    msc.append(FOLDER_CELL if c.cell_type == "code" and c.source.lstrip().startswith("from odin_paths import TWIN_RUN_ROOT")
               and "FOLDER" in c.source else clean(c))
msc += [md(r"""
## 6. Your turn: measure the (110) Bragg edge

α-iron is body-centered cubic, $a = 2.8665$ Å. The planes that can diffract are (110), (200), (211)... with spacings
$d_{hkl} = a/\sqrt{h^2+k^2+l^2}$, and each family gives an edge at $\lambda = 2d_{hkl}$ (why? write it in one sentence
with Bragg's law, $\lambda = 2d\sin\theta$).

**Task 6.1.** An ideal edge is a sharp step. The measured one is smoothed by the wavelength resolution of the
instrument (roughly Gaussian), and sits on a slowly varying baseline. Write a function `edge(lam, ...)` that models
this: what is the convolution of a step with a Gaussian? Which parameters do you need?
"""), code(r"""
from scipy.special import erfc

def edge(lam, lam_edge, width, base, slope, jump):
    # your model of the transmission near an edge
    raise NotImplementedError("write the model of a smoothed Bragg edge")
"""), md(r"""
**Task 6.2.** Fit your model to $T(\lambda)$ (arrays `lam`, `T`, `dT` from part 5) in a window around the expected
(110) edge. Use the error bars (`sigma=dT, absolute_sigma=True`) so that the uncertainties of the parameters mean
something. Store the result in `lam_edge` and its uncertainty in `dlam_edge` (Å).
"""), code(r"""
from scipy.optimize import curve_fit

lam_edge, dlam_edge = None, None     # your result [Å]
"""), md("**Check.** Run the cell below."), code(r"""
import odin_exercises as ex
ex.check_edge(lam_edge, dlam_edge)
"""), md(r"""
**Task 6.3.** Deduce $d_{110}$ and the lattice parameter $a$, with their uncertainties, and compare with 2.8665 Å.
Store $a$ and its uncertainty in `a_fe`, `da_fe`.
"""), code(r"""
a_fe, da_fe = None, None     # your result [Å]
ex.check_lattice(a_fe, da_fe)
"""), md(r"""
## 7. Developing the method: a systematic error

Your edge is probably a few thousandths of an ångström away from the true value, more than its uncertainty. A counting
fluctuation would shrink if you counted longer; this does not. Find where it comes from:

1. **The fit window.** Fit with a 2× wider and a 2× narrower window. Does `lam_edge` move by more than `dlam_edge`?
2. **The time → wavelength conversion.** The ESS reduction converts the arrival time into λ with a lookup table.
   `red.reduce(..., wavelength_from="analytical")` builds it assuming a simple source pulse, the default
   (`"simulation"`) with a realistic ESS pulse. Reduce again with the other table and fit again. Which one is closer
   to the truth? Explain why with the shape of the ESS pulse.
3. **Counting statistics.** Count 4 times longer: by how much do `dlam_edge` and the distance to the truth change?

Write your conclusion: what limits the accuracy of a Bragg-edge measurement, and how would you calibrate it at a real
instrument?
"""), code("")]
write(msc, "ODIN_iron_msc.ipynb")

# --------------------------------------------------------------------------- beamtime starter
i2, i3 = section(src, "## 2."), section(src, "## 3.")
imports = next(c for c in src if c.cell_type == "code" and "import odin_reduction as red" in c.source)
logbook = next(c for c in src[i2:i3] if c.cell_type == "code" and "show_table" in c.source)
starter_imports = clean(imports)
starter_imports.source = starter_imports.source.split("if FOLDER is None:")[0].rstrip()   # no demonstration session
bt = [md(r"""
# Beamtime on ODIN: starter notebook

Your proposal is in `beamtime.md`. This notebook only gives you the tools; what to measure and how to analyze it is
up to you. Keep notes of your choices: they are part of your report.

**Tools**
- `rows`: your logbook (one line per count: file, title, settings);
- `red.histograms(file, LAM, ROI)`: image and spectrum of one file, λ from the ESS reduction;
- `red.reduce(sample, open_beam, dark=..., lam=LAM, roi=ROI)`: transmission image and spectrum (official ESS code);
- `curve_fit` (scipy) for fits, `erfc` for smoothed steps; `h5py` to look inside a NeXus file.
"""), code(PATH_CELL), code(
    'from odin_paths import TWIN_RUN_ROOT\n'
    'FOLDER = f"{TWIN_RUN_ROOT}/data/odin/2026/1234/raw"     # the folder of your proposal (NICOS)'),
      starter_imports, clean(logbook), md("## Your analysis"), code(""), code(""), code(""),
      md("## Results for the committee\n\n(edge position, $d_{110}$, $a$, with uncertainties; logbook of your choices)")]
write(bt, "ODIN_iron_beamtime.ipynb")
