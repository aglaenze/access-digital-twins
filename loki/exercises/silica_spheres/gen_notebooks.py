"""Generates the notebooks of the exercise "How big are these nanoparticles?" from the guided analysis notebook
loki/LoKI_analysis.ipynb (one source: a correction there reaches every level when this script is run again):

  * LoKI_silica_msc.ipynb       MSc, "develop the method": parts 1-4 of the guided notebook (files, NeXus, reduction
                                with esssans), then tasks: the Guinier analysis and a sasmodels fit written by the
                                student, checked automatically; then questions on the method;
  * LoKI_silica_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only, no guidance.

    python gen_notebooks.py
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "..", "LoKI_analysis.ipynb")
PATH_CELL = ('import sys, os\n'
             'sys.path.insert(0, os.path.abspath("../.."))     # the modules of the LoKI twin (folder loki/)')


def section(cells, title):
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
    spec = sl.load("loki")[name]
    print(sl.describe("loki", spec, hidden))
    sl.draw("loki", spec, hidden=hidden, fig=plt.figure(figsize=(10, 3.5))); plt.show()"""
md = lambda s: nbf.v4.new_markdown_cell(s.strip())
code = lambda s: nbf.v4.new_code_cell(s.strip())
src = nbf.read(SOURCE, as_version=4).cells

# --------------------------------------------------------------------------- MSc
i1, i5 = section(src, "## 1."), section(src, "## 5.")
msc = [md(r"""
# How big are these nanoparticles? (MSc)

Silica nanoparticles dispersed in heavy water, measured on the virtual LoKI. Parts 1 to 4 are guided: they take your
files (sample, solvent, empty beam) to the scattering curve $I(Q)$ in absolute units, with the official ESS reduction
(`esssans`). Parts 5 and 6 are yours: **you write the Guinier analysis and the model fit**, and check cells tell you
whether your results are right (the twin knows the true sample). Part 7 is about the method.

Measure first in NICOS (empty beam, D₂O, silica spheres, same configuration; your files are in the folder of your
proposal, `f"{TWIN_RUN_ROOT}/data/loki/<year>/<proposal>/raw"`), or leave `FOLDER = None` below to start with a
demonstration session.

**The measurements in NICOS** (click *Open NICOS* in the app and choose LoKI: NICOS opens, ready; give a proposal
number in the *Experiment* panel, then type in the command line or the *Scripting* tab):
```
move(heavy_shutter, 'Open', fast_shutter, 'Open')
move(collimation, '3m', detector_distance, 5)
move(sample_holder, 'empty_beam')
with nexusfile_open('empty beam'):
    count(t=60)
move(sample_holder, 'd2o')
with nexusfile_open('D2O'):
    count(t=600)
move(sample_holder, 'silica_spheres')
with nexusfile_open('silica spheres'):
    count(t=600)
```
Why: the solvent is subtracted from the sample, the empty beam is the reference of the transmission; all three in the
same configuration (3 m collimation, detector at 5 m: Q from 0.006 to 0.5 Å⁻¹, enough for particles of a few nm).
"""), code(PATH_CELL), md("**Your sample** (from the sample library; what you have to measure is shown as ?):"),
       code(SAMPLE_CELL)]
msc += [clean(c) for c in src[i1:i5]]
msc += [md(r"""
## 5. Your turn: Guinier analysis

At small $Q$ the scattering of any particle follows $I(Q) \simeq I(0)\exp(-Q^2R_g^2/3)$, valid for $Q R_g \lesssim 1.3$.

**Task 5.1.** Turn this law into a straight line: what do you plot against what? Make the plot with the arrays `q`,
`I`, `dI` of part 4, for the lowest $Q$.

**Task 5.2.** Fit the line with weights (the uncertainty of $\ln I$ is $dI/I$), in the range $Q R_g < 1.3$. The range
depends on $R_g$, which you do not know yet: how do you proceed? Store $R_g$, its uncertainty and $I(0)$ (cm⁻¹).
"""), code(r"""
rg, drg, i0 = None, None, None     # your results [Å, Å, cm⁻¹]
"""), md("**Check.**"), code(r"""
import loki_exercises as ex
ex.check_guinier(rg, drg, i0)
"""), md(r"""
## 6. Your turn: a model fit with sasmodels (SasView)

`sasmodels` is the computing engine of SasView. Its `sphere` model gives $d\Sigma/d\Omega$ in cm⁻¹, with the
parameters `scale` (the volume fraction $\phi$), `radius` (Å), `sld` and `sld_solvent` (scattering length densities,
$10^{-6}$ Å⁻²: silica 3.47, D₂O 6.36) and `background` (cm⁻¹). How to compute it:

```python
from sasmodels.core import load_model
from sasmodels.direct_model import call_kernel
model = load_model("sphere")
kernel = model.make_kernel([q])
Iq = call_kernel(kernel, dict(scale=0.01, radius=50, sld=3.47, sld_solvent=6.36, background=0))
```

**Task 6.1.** Fit $\phi$, $R$ and a background to the whole curve (e.g. with `scipy.optimize.least_squares` on the
residuals $(I_\text{model} - I)/dI$). Use your Guinier result for the starting radius. Store the results and their
uncertainties (from the Jacobian: $\text{cov} = (J^TJ)^{-1}$).
"""), code(r"""
radius, dradius, phi, dphi = None, None, None, None     # your results [Å, Å, -, -]
"""), md("**Check.**"), code(r"""
ex.check_sphere(radius, dradius, phi, dphi)
"""), md(r"""
## 7. Developing the method

1. **Background.** Reduce the sample without subtracting the solvent (`red.reduce(path(SAMPLE), empty_beam=path(EMPTY))`)
   and fit again with and without a `background` parameter. What goes wrong, and why does it matter most for $R_g$?
2. **Resolution.** Plot your residuals: where is the model worse than the data, and why? Look at the `dq` (resolution)
   option of `make_kernel`/`call_kernel` in the sasmodels documentation: what would you need to know about the
   instrument to use it?
3. **Configuration.** Particles 4 times larger: which configuration of LoKI (collimation, detector distance) would you
   choose, and what would it cost in counting time? Check with the twin.
4. **Statistics.** Which banks dominate the uncertainty on $R$? On $\phi$? Fit with the rear bank only to see it.
"""), code("")]
write(msc, "LoKI_silica_msc.ipynb")

# --------------------------------------------------------------------------- beamtime starter
i2, i3 = section(src, "## 2."), section(src, "## 3.")
imports = next(c for c in src if c.cell_type == "code" and "import loki_reduction as red" in c.source)
logbook = next(c for c in src[i2:i3] if c.cell_type == "code" and "show_table" in c.source)
imports = clean(imports)
imports.source = imports.source.split("if FOLDER is None:")[0].rstrip()
bt = [md(r"""
# Beamtime on LoKI: starter notebook

Your proposal is in `beamtime.md`. This notebook only gives you the tools; what to measure and how to analyze it is
up to you. Keep notes of your choices: they are part of your report.

**Tools**
- `rows`: your logbook (one line per count: file, kind, title, settings);
- `red.reduce(sample, background=..., empty_beam=..., banks=[...])`: $I(Q)$ per detector bank, with the official ESS
  software (esssans); `red.combine(result, thickness_cm)`: banks merged into rear/middle/front, in cm⁻¹;
- `la.guinier(q, I, dI)`, `la.sphere_fit(q, I, dI)`: Guinier analysis and the sphere model of sasmodels (SasView);
- `h5py` to look inside a NeXus file; `scipy.optimize` for your own fits.
"""), code(PATH_CELL), code(
    'from loki_paths import TWIN_RUN_ROOT\n'
    'FOLDER = f"{TWIN_RUN_ROOT}/data/loki/2026/3001/raw"     # the folder of your proposal (NICOS)'),
      imports, clean(logbook), md("## Your analysis"), code(""), code(""), code(""),
      md("## Results for the committee\n\n($I(Q)$, $R_g$, $R$, $\\phi$, with uncertainties; logbook of your choices)")]
write(bt, "LoKI_silica_beamtime.ipynb")
