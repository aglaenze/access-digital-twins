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


# The cells where the student works stay free; all the others are locked (they still run): a student cannot break
# the notebook by mistake, and can always add cells of their own.
FREE_CODE = ("# your", "= None", "PROPOSAL =", "FOLDER =", "DARK, OPEN, SAMPLE =", "SAMPLE = ", "ROI =")
FREE_TEXT = ("## Results for the committee", "## My question", "## My answer", "## Your analysis")


def lock(c):
    free = (c.cell_type == "code" and (not c.source.strip() or any(k in c.source for k in FREE_CODE))) or \
           (c.cell_type == "markdown" and c.source.startswith(FREE_TEXT))
    if not free:
        c.metadata["editable"] = False
        c.metadata["deletable"] = False


HIDDEN_START = ("q.", "q_.", "import submit", "nb_tools.", "import nb_tools" + chr(10) + "nb_tools.nicos(")


def write(cells, name):
    """The code of the questions and of the solutions (the answers are in it), of Submit and of the NICOS button is
    hidden: only their widgets show. A solution (q.solution) after a check gets its own hidden cell."""
    nb = nbf.v4.new_notebook()
    out = []
    for c in cells:
        if c.cell_type == "code":
            for key in ("q.solution(", "q_.solution("):
                i = c.source.find(key)
                if i > 0:
                    head, tail = c.source[:i].rstrip(), c.source[i:]
                    c.source = head
                    out.append(c)
                    c = nbf.v4.new_code_cell(tail)
                    break
            if c.source.lstrip().startswith(HIDDEN_START) or "nb_tools.proposal(" in c.source:
                c.metadata["jupyter"] = {"source_hidden": True}
        out.append(c)
    for c in out:
        lock(c)
    cells = out
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

You start by measuring, in NICOS (part 0), as a user of ESS would.
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
msc += [md("## Submit your work\n\nWhen you are done: save this notebook (*Save*), then submit. The file for your teacher is made from your answers, your measurements and your notebook."),
        code("import submit\n_ = submit.Submit(\"loki/exercises/silica_spheres\", \"msc\", quiz=q_)")]
# --- part 0: the student measures in NICOS (step by step), as at ESS; no demonstration session
PART0 = [md("\n## 0. Your measurements, in NICOS\n\nAs at ESS, you measure with **NICOS**, the control software of the instrument: you type the commands, NICOS moves\nthe devices, counts and writes the data files. Nobody measures for you: if a file is wrong, you will see it in the\nlogbook (part 1) and measure again.\n\n1. **Open NICOS** with the button below. After about a minute the NICOS window of LoKI is there, logged in.\n2. **Your proposal.** Tab *Experiment*: write a *Proposal ID* (`3001`, or the number your teacher gives you), a title,\n   your name in *Users*, then **Apply**. Without a proposal NICOS refuses to record data, as at ESS. Another number?\n   Write it in `PROPOSAL` (part 1).\n3. **The configuration.** Tab *Instrument interaction*, in the command line (one line, then Enter):\n   `move(heavy_shutter, 'Open', fast_shutter, 'Open')`, then `move(collimation, '3m', detector_distance, 5)`:\n   3 m collimation, detector at 5 m, Q from 0.006 to 0.5 Å⁻¹, enough for particles of a few nm.\n4. **The empty beam** (the reference of the transmission): `move(sample_holder, 'empty_beam')`, then\n   `with nexusfile_open('empty beam'): count(t=60)`.\n5. **The solvent**: `move(sample_holder, 'd2o')`, then `with nexusfile_open('D2O'): count(t=600)`.\n6. **The sample**: `move(sample_holder, 'silica_spheres')`, then `with nexusfile_open('silica spheres'): count(t=600)`.\n   Watch the *Detector image*: the scattering around the beam stop.\n7. **Check.** `list_filewriting_jobs()` lists your three files. Come back here and run the notebook:\n   menu *Run > Run All Cells*.\n\nThe first count of a new configuration takes about a minute (the twin simulates it). Several lines at once: tab\n*Scripting*, then *Run*. Why three measurements: the solvent is subtracted from the sample, the empty beam is the\nreference of the transmission; all three in the same configuration.\n"), code('import nb_tools\nnb_tools.nicos("loki")')]
_k0 = next(k for k, c in enumerate(msc) if c.cell_type == "code" and "exercise_hidden" in c.source) + 1
msc[_k0:_k0] = PART0
for c in msc:
    if c.cell_type == "markdown" and c.source.startswith("## 1."):
        c.source = '## 1. Your files\n\nYour files are in the folder of your proposal, `data/<instrument>/<year>/<proposal>/raw`, as at ESS. Write in\n`PROPOSAL` the *Proposal ID* you gave in NICOS (part 0). If there is no file yet, the notebook stops here and tells you.'
    if c.cell_type == "code" and c.source.lstrip().startswith("from loki_paths import TWIN_RUN_ROOT") and "FOLDER" in c.source:
        c.source = ('from loki_paths import TWIN_RUN_ROOT          # root of the results of the twins\n'
                    'import datetime\n'
                    'PROPOSAL = "3001"                              # the Proposal ID you gave in NICOS (part 0)\n'
                    'FOLDER = f"{TWIN_RUN_ROOT}/data/loki/{datetime.date.today().year}/{PROPOSAL}/raw"')
    if c.cell_type == "code" and "if FOLDER is None:" in c.source:
        _a, _b = c.source.index("if FOLDER is None:"), c.source.index('print("folder:"')
        c.source = (c.source[:_a] + 'import nb_tools\nnb_tools.need_measurements(FOLDER, "loki")   '
                    '# stops here, with a message, while there is no file\n' + c.source[_b:])
import sys as _sys
_sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
from nbfig import figure_cell, insert_after_mission
insert_after_mission(msc, figure_cell('sans_particles.png', 'What you measure: the particles in the liquid scatter at small angles, and their size sets the shape of the curve I(Q).'))
write(msc, "LoKI_silica_msc.ipynb")

# --------------------------------------------------------------------------- beamtime starter
i2, i3 = section(src, "## 2."), section(src, "## 3.")
imports = next(c for c in src if c.cell_type == "code" and "import loki_reduction as red" in c.source)
logbook = next(c for c in src[i2:i3] if c.cell_type == "code" and "show_table" in c.source)
imports = clean(imports)
imports.source = (imports.source.split("if FOLDER is None:")[0].rstrip()
                  + "\nimport nb_tools\nnb_tools.need_measurements(FOLDER, \"loki\")   # stops here while there is no file")
bt = [md(r"""
# Beamtime on LoKI: starter notebook

Your proposal is just below (folded), with the buttons *Open NICOS* and *Sample builder*. This notebook only gives you the tools; what to measure and how to analyze it is
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
bt[1:1] = [md('**Your proposal** (click to open it):'),
           code('import sys, os' + chr(10) + 'sys.path.insert(0, os.path.abspath("../../.."))' + chr(10) + 'import nb_tools' + chr(10) + 'nb_tools.proposal("loki/exercises/silica_spheres/beamtime.md")'),
           md("## 1. Your sample\n\nThe sample changer of LoKI holds the samples of the library (in NICOS, `sample_info()` describes the one mounted). For your own question, design a sample with the sample builder: particles of the kinds you choose (spheres, cylinders, core-shell spheres, as many kinds as you want) in a H2O/D2O solvent. It is saved with your proposal and appears on the sample changer of NICOS: `move(sample_holder, 'its_name')`."),
           code('nb_tools.sample_builder("loki", "3001")'),
           md("## 2. Your measurements, in NICOS\n\n1. Tab *Experiment*: give the *Proposal ID* of your proposal, then **Apply** (first: your own samples are kept with your proposal, NICOS finds them only then).\n2. **Mount your sample** (tab *Instrument interaction*, command line): `move(sample_holder, 'its_name')`, the short name of a sample of the library (e.g. `silica_spheres`, `d2o`, `empty_beam`) or of the one you made in part 1. `sample_info()` describes the sample mounted; for a name NICOS does not know, it lists the samples available. Every count measures the sample mounted at that moment.\n3. **Record**: `with nexusfile_open('my title'): count(t=60)`; your files go to the folder of your proposal (below). The measurements and their counting times are your decisions: your budget is in your proposal."),
           code('nb_tools.nicos("loki")')]
bt += [md("## Submit your work\n\nWhen you are done: save this notebook (*Save*), then submit. The file for your teacher is made from your measurements and your notebook."),
       code("import submit\n_ = submit.Submit(\"loki/exercises/silica_spheres\", \"beamtime\")")]
write(bt, "LoKI_silica_beamtime.ipynb")
