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
    sl.draw("loki", spec, hidden=hidden, fig=plt.figure(figsize=(10, 3.5))); sl.show()"""
md = lambda s: nbf.v4.new_markdown_cell(s.strip())
code = lambda s: nbf.v4.new_code_cell(s.strip())
src = nbf.read(SOURCE, as_version=4).cells

# --------------------------------------------------------------------------- MSc
i1, i5 = section(src, "## 1."), section(src, "## 5.")
msc = [md(r"""
# How big are these nanoparticles? (MSc)

**Your mission.** You work in a laboratory that makes silica nanoparticles for medical imaging. A new batch must
have a radius between 4.5 and 5.5 nm: the size decides how long the particles stay in the blood and where they end
up. An electron microscope shows a few hundred dried particles; small-angle neutron scattering gives the average over
the billions of particles of the batch, in the liquid. You measure the batch on LoKI, develop the analysis, and
decide whether the batch can be released (end of part 6).

Silica nanoparticles dispersed in heavy water, measured on the virtual LoKI. Parts 1 to 4 are guided: they take your
files (sample, solvent, empty beam) to the scattering curve $I(Q)$ in absolute units, with the official ESS reduction
(`esssans`). Parts 5 and 6 are yours: **you write the Guinier analysis and the model fit**, and check cells tell you
whether your results are right (the twin knows the true sample). Part 7 is about the method.

Measure first in NICOS (empty beam, D₂O, silica spheres, same configuration; your files are in the folder of your
proposal, `f"{TWIN_RUN_ROOT}/data/loki/<year>/<proposal>/raw"`), or leave `FOLDER = None` below to start with a
demonstration session.

**The measurements in NICOS** (click *Open NICOS* in the app: NICOS of LoKI opens, ready; give a proposal
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
"""), code(PATH_CELL), md("**Your sample** (from the sample library):"),
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
"""), md("**Check.** If it is wrong, read the explanation and try again; the solution is behind the button "
         "(opening it is noted in your results)."), code(r"""
import loki_exercises as ex, quiz
q_ = quiz.Quiz("loki_silica_msc")
ex.check_guinier(rg, drg, i0)
q_.solution("tasks 5.1 and 5.2", explanation="$\\ln I = \\ln I(0) - (R_g^2/3)\\,Q^2$: a straight line in $Q^2$ "
            "with slope $-R_g^2/3$. The valid range depends on $R_g$: start from a guess, fit, recompute the range "
            "$Q R_g < 1.3$, and repeat until $R_g$ no longer changes.", code=chr(10).join([
    'rg = 40.0                                                # a first guess [Å], improved below',
    'for _ in range(6):',
    '    m = (q * rg < 1.3) & (I > 0) & np.isfinite(dI) & (dI > 0)',
    '    p, cov = np.polyfit(q[m] ** 2, np.log(I[m]), 1, w=I[m] / dI[m], cov="unscaled")   # w = 1 / sigma(ln I)',
    '    rg = np.sqrt(-3 * p[0])',
    'drg = 1.5 * np.sqrt(cov[0, 0]) / rg                      # rg = sqrt(-3 s): d rg = 1.5 ds / rg',
    'i0 = np.exp(p[1])']))
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
q_.solution("task 6.1", explanation="Residuals weighted by the error bars; the covariance of the parameters is "
            "$(J^TJ)^{-1}$ with the Jacobian of these residuals. `x_scale` tells the fit the size of each parameter.",
            code=chr(10).join([
    'from scipy.optimize import least_squares',
    'from sasmodels.core import load_model',
    'from sasmodels.direct_model import call_kernel',
    'm = np.isfinite(I) & np.isfinite(dI) & (dI > 0)',
    'kernel = load_model("sphere").make_kernel([q[m]])',
    '',
    'def residuals(x):',
    '    phi_, r_, bg_ = x',
    '    model = call_kernel(kernel, dict(scale=phi_, radius=r_, sld=3.47, sld_solvent=6.36, background=bg_))',
    '    return (model - I[m]) / dI[m]',
    '',
    'fit = least_squares(residuals, [0.01, rg * np.sqrt(5 / 3), 0.0], x_scale=[0.01, 10.0, 0.01])',
    'cov = np.linalg.inv(fit.jac.T @ fit.jac)',
    'phi, radius = fit.x[0], fit.x[1]',
    'dphi, dradius = np.sqrt(cov[0, 0]), np.sqrt(cov[1, 1])']))
"""), md("**Your verdict.**"), code(r"""
q_.choice("The batch must have a radius between 4.5 and 5.5 nm. With your results, what do you write?",
          ["Released: R = 5.0 nm, within the specification (its uncertainty is far smaller than the margin).",
           "Rejected: R = 3.9 nm.", "Rejected: R = 50 nm.", "Cannot be decided: the uncertainty is too large."],
          answer=0, why={1: "3.9 nm is Rg; for a sphere R = √(5/3)·Rg ≈ 5.0 nm.",
                         2: "50 Å = 5.0 nm (1 nm = 10 Å).",
                         3: "Your uncertainty on R is a fraction of an Å, the margin is ±5 Å."},
          explanation="R ≈ 50 Å = 5.0 nm, in the 4.5-5.5 nm window, with an uncertainty much smaller than the margin.",
          hints=['Convert your radius R to nm (1 nm = 10 Å) and compare with 4.5-5.5 nm.', 'Compare your uncertainty on R with the margin of the specification (±0.5 nm = ±5 Å).'],
         title="Verdict")
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

Then check your understanding:
"""), code(r"""
q_.choice("A new batch has particles 4 times larger (R = 200 Å, Rg = 155 Å). The Guinier range needs Q < 1.3/Rg. "
          "Which configuration of LoKI do you choose?",
          ["8 m collimation, detector at 10 m (rear bank from 0.0082 Å⁻¹), and count longer: fewer neutrons.",
           "3 m collimation, detector at 5 m: the most neutrons.",
           "The same as for the 5 nm particles.",
           "Pulse skipping with the detector at 5 m: it reaches the lowest Q."],
          answer=0, why={1: "It starts at 0.0115 Å⁻¹, above 1.3/155 = 0.0084 Å⁻¹: no Guinier range left.",
                         2: "The same configuration starts at 0.0115 Å⁻¹, above the 0.0084 Å⁻¹ needed.",
                         3: "Pulse skipping at 5 m starts at 0.0106 Å⁻¹: better, but still above 0.0084 Å⁻¹."},
          explanation="1.3/155 Å = 0.0084 Å⁻¹: only the 8 m collimation with the detector at 10 m reaches it (0.0082 "
                      "Å⁻¹), at the edge. Its beam is more parallel, with fewer neutrons: count longer.",
          hints=['Compute the largest Q of the Guinier range: 1.3/Rg with Rg = 155 Å.', '1.3/155 = 0.0084 Å⁻¹: which configuration starts below it?'],
         title="Larger particles")
q_.report()
""")]
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
      md("## Results for the committee\n\n($I(Q)$, $R_g$, $R$, $\\phi$, with uncertainties; logbook of your choices)"),
      md("## Check your results (after writing them)\n\nThe twin knows the true sample: put your final numbers below "
         "and run the cell. A wrong result is explained."),
      code("import loki_exercises as ex\n"
           "rg, drg, i0 = None, None, None                     # Guinier [Å, Å, cm⁻¹]\n"
           "radius, dradius, phi, dphi = None, None, None, None  # sphere model [Å, Å, -, -]\n"
           "ex.check_guinier(rg, drg, i0)\nex.check_sphere(radius, dradius, phi, dphi)")]
write(bt, "LoKI_silica_beamtime.ipynb")
