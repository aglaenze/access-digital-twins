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
    spec = sl.load("odin")[name]
    print(sl.describe("odin", spec, hidden))
    sl.draw("odin", spec, hidden=hidden, fig=plt.figure(figsize=(10, 3.5))); sl.show()"""
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

**Your mission.** You are a materials engineer. A supplier has delivered steel plates sold as *ferritic* steel
(α-iron, body-centered cubic); a mix-up with *austenitic* steel (γ-iron, face-centered cubic: not magnetic, expands
more when heated) would matter for the parts you build, and you may not cut the plates. The Bragg edges of the
neutron transmission reveal the crystal structure through centimeters of steel. You measure a plate with ODIN,
develop the analysis, and give your verdict with its uncertainty (end of part 6).

You will measure the **Bragg edges** of an iron plate with the virtual ODIN and deduce the spacing of its atomic planes.
Parts 1 to 5 are guided: they take your files from the raw neutrons to the transmission $T(\lambda)$, with the
official ESS reduction. Part 6 is yours: **you write the model and the fit**, and a check cell tells you whether your
result is right (the twin knows the true sample). Part 7 is about the method itself: a systematic error to track down.

You start by measuring, in NICOS (part 0), as a user of ESS would.
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
"""), md("**Check.** Run the cell below. If it is wrong, read the explanation, try again; the solution is behind the "
         "button (opening it is noted in your results)."), code(r"""
import odin_exercises as ex, quiz
q = quiz.Quiz("odin_iron_msc")
ex.check_edge(lam_edge, dlam_edge)
q.solution("tasks 6.1 and 6.2", explanation="A step smoothed by a Gaussian resolution of width $w$ is an error "
           "function: $T = A + C(\\lambda-\\lambda_e) + \\frac{B}{2}\\,\\mathrm{erfc}(-(\\lambda-\\lambda_e)/(\\sqrt2\\,w))$, "
           "on a sloped baseline. The fit window is ±0.35 Å around the expected edge, with bounds that keep the fit "
           "on the edge.", code=chr(10).join([
    'def edge(lam, lam_edge, width, base, slope, jump):',
    '    return base + slope * (lam - lam_edge) + 0.5 * jump * erfc(-(lam - lam_edge) / (np.sqrt(2) * width))',
    '',
    'expected = 2 * 2.8665 / np.sqrt(2)                      # (110) edge: 2 d_110 = a √2',
    'm = (lam > expected - 0.35) & (lam < expected + 0.35) & np.isfinite(T) & (dT > 0)',
    'p, cov = curve_fit(edge, lam[m], T[m], sigma=dT[m], absolute_sigma=True,',
    '                   p0=[expected, 0.03, T[m].min(), 0.0, 0.1],',
    '                   bounds=([expected - 0.3, 0.005, 0, -2, 0], [expected + 0.3, 0.3, 2, 2, 1]))',
    'lam_edge, dlam_edge = p[0], np.sqrt(cov[0, 0])']))
"""), md(r"""
**Task 6.3.** Deduce $d_{110}$ and the lattice parameter $a$, with their uncertainties, and compare with 2.8665 Å.
Store $a$ and its uncertainty in `a_fe`, `da_fe`.
"""), code(r"""
a_fe, da_fe = None, None     # your result [Å]
ex.check_lattice(a_fe, da_fe)
q.solution("task 6.3", explanation="At the edge $\\lambda = 2d_{110}$ and $d_{110} = a/\\sqrt2$, so "
           "$a = \\lambda_\\mathrm{edge}/\\sqrt2$; the uncertainty is divided by the same factor.", code=chr(10).join([
    'd110, dd110 = lam_edge / 2, dlam_edge / 2',
    'a_fe, da_fe = d110 * np.sqrt(2), dd110 * np.sqrt(2)']))
"""), md(r"""
**Your verdict for the supplier.**
"""), code(r"""
q.choice("γ-iron (face-centered cubic, a = 3.59 Å) would have its (111) edge at 4.15 Å and a (200) edge at 3.59 Å. "
         "Your plate has its last edge at about 4.06 Å and a lattice parameter of about 2.87 Å. What do you write?",
         ["Ferritic steel (α-iron), a = 2.87 Å: as ordered.", "Austenitic steel (γ-iron): send it back.",
          "Cannot be decided from the transmission.", "A mixture of both, half and half."],
         answer=0, why={1: "γ-iron would put its last edge at 4.15 Å, 0.09 Å away from yours: about a hundred times "
                           "your uncertainty.",
                        2: "The positions of the edges are set by the crystal lattice: they decide.",
                        3: "A mixture would show the edges of both lattices (4.15 and 3.59 Å as well): your spectrum "
                           "has only those of a body-centered cubic lattice."},
         explanation="The edges are those of a body-centered cubic lattice with a = 2.87 Å: ferritic steel. The "
                     "difference to γ-iron is far larger than your uncertainty.", hints=['Compare your last edge (about 4.06 Å) with that of γ-iron (4.15 Å): how many uncertainties apart?', 'Your lattice parameter is about 2.87 Å; γ-iron has 3.59 Å.'],
         title="Verdict")
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
instrument? Then check your understanding:
"""), code(r"""
q.choice("You count 4 times longer. What happens to the uncertainty `dlam_edge` and to the distance between your edge "
         "and the truth?", ["dlam_edge is halved; the distance to the truth stays about the same.",
                            "Both are halved.", "Both stay the same.", "dlam_edge is divided by 4."],
         answer=0, why={1: "The distance to the truth is a systematic error: it does not depend on the number of "
                           "neutrons.",
                        2: "More neutrons always shrink the statistical uncertainty: as 1/√N.",
                        3: "The uncertainty goes as 1/√N: √4 = 2, not 4."},
         explanation="Statistical errors shrink as 1/√N (halved for 4 times more counts); a systematic error does "
                     "not. When the distance to the truth is several times the uncertainty, the error is systematic.",
         hints=['Which of the two depends on the number of neutrons counted?', 'A statistical uncertainty goes as 1/√N; an offset of the wavelength scale does not depend on N.'],
         title="Statistical or systematic?")
q.choice("How is such a systematic error corrected at a real instrument?",
         ["By measuring a reference sample whose plane spacings are known, and correcting the wavelength scale.",
          "By counting longer.", "By using a wider fit window.", "It cannot be corrected."],
         answer=0, why={1: "Counting longer only shrinks the statistical error.",
                        2: "The window changes the fit a little but does not remove an error of the wavelength scale.",
                        3: "It can: the wavelength scale is calibrated."},
         explanation="The error comes from the conversion of the arrival time into a wavelength (flight distances, "
                     "chopper timings, shape of the ESS pulse). Instruments calibrate it with a reference powder of "
                     "known lattice parameter.", hints=['The offset comes from the wavelength scale. How would you check a scale?', 'Measure something whose answer you know already.'],
         title="Calibration")
q.report()
""")]
msc += [md("## Submit your work\n\nWhen you are done: save this notebook (*Save*), then submit. The file for your teacher is made from your answers, your measurements and your notebook."),
        code("import submit\n_ = submit.Submit(\"odin/exercises/iron_bragg_edges\", \"msc\", quiz=q)")]
# --- part 0: the student measures in NICOS (step by step), as at ESS; no demonstration session
PART0 = [md("\n## 0. Your measurements, in NICOS\n\nAs at ESS, you measure with **NICOS**, the control software of the instrument: you type the commands, NICOS moves\nthe devices, counts and writes the data files. Nobody measures for you: if a file is wrong (shutter forgotten, sample\nin the wrong place), you will see it in part 2 and measure again.\n\n1. **Open NICOS** with the button below. After about a minute the NICOS window of ODIN is there, logged in.\n2. **Your proposal.** Tab *Experiment*: **Query**, choose proposal `1234` (the proposal of this exercise, in the\n   user office of the twin), then **Apply**: its number, title, users and sample are filled in, as at ESS, and the\n   iron plate is mounted on the sample changer (`sample_info()` describes it). Without a proposal NICOS refuses to\n   record data, as at ESS.\n3. **The dark.** Tab *Instrument interaction*, in the command line (one line, then Enter):\n   `move(shutter, 'closed')`, then `with nexusfile_open('dark'): count(t=30)`.\n   The *Detector image* stays almost empty: a few counts of background.\n4. **The open beam.** `move(shutter, 'open', stage_x, 500)`: the stage goes 500 mm aside, so the plate is out of the\n   14 mm field of view. Then `with nexusfile_open('open beam'): count(t=60)`.\n5. **The iron plate.** `move(stage_x, 0)`, then `with nexusfile_open('iron plate'): count(t=60)`. The image now shows\n   the plate: a darker square.\n6. **Check.** `list_filewriting_jobs()` lists your three files. Come back here and run the notebook:\n   menu *Run > Run All Cells*.\n\nSeveral lines at once: tab *Scripting*, then *Run*. Why these settings: the choppers (WFM, δ = 0.30 m) and the pinhole\nstay the same for the three runs, so that the open beam can divide the sample run.\n"), code('import nb_tools\nnb_tools.nicos("odin")')]
_k0 = next(k for k, c in enumerate(msc) if c.cell_type == "code" and "exercise_hidden" in c.source) + 1
msc[_k0:_k0] = PART0
for c in msc:
    if c.cell_type == "markdown" and c.source.startswith("## 1."):
        c.source = '## 1. Your files\n\nYour files are in the folder of your proposal, `data/<instrument>/<year>/<proposal>/raw`, as at ESS. Write in\n`PROPOSAL` the number of the proposal applied in NICOS (part 0). If there is no file yet, the notebook stops here and tells you.'
    if c.cell_type == "code" and c.source.lstrip().startswith("from odin_paths import TWIN_RUN_ROOT") and "FOLDER" in c.source:
        c.source = ('from odin_paths import TWIN_RUN_ROOT          # root of the results of the twins\n'
                    'import datetime\n'
                    'PROPOSAL = "1234"                              # the proposal applied in NICOS (part 0)\n'
                    'FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/{PROPOSAL}/raw"')
    if c.cell_type == "code" and "if FOLDER is None:" in c.source:
        _a, _b = c.source.index("if FOLDER is None:"), c.source.index('print("folder:"')
        c.source = (c.source[:_a] + 'import nb_tools\nnb_tools.need_measurements(FOLDER, "odin")   '
                    '# stops here, with a message, while there is no file\n' + c.source[_b:])
import sys as _sys
_sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
from nbfig import figure_cell, insert_after_mission
insert_after_mission(msc, figure_cell('iron_structures.png', 'What you have to decide: α-iron (left) or γ-iron (middle)? Each structure has its own atomic planes, hence its own Bragg edges (right).'))
write(msc, "ODIN_iron_msc.ipynb")

# --------------------------------------------------------------------------- beamtime starter
i2, i3 = section(src, "## 2."), section(src, "## 3.")
imports = next(c for c in src if c.cell_type == "code" and "import odin_reduction as red" in c.source)
logbook = next(c for c in src[i2:i3] if c.cell_type == "code" and "show_table" in c.source)
starter_imports = clean(imports)
starter_imports.source = (starter_imports.source.split("if FOLDER is None:")[0].rstrip()   # no demonstration session
                          + "\nimport nb_tools\nnb_tools.need_measurements(FOLDER, \"odin\")   # stops here while there is no file")
bt = [md(r"""
# Beamtime on ODIN: starter notebook

Your proposal is just below (folded), with the buttons *Open NICOS* and *Sample builder*. This notebook only gives you the tools; what to measure and how to analyze it is
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
      md("## Results for the committee\n\n(edge position, $d_{110}$, $a$, with uncertainties; logbook of your choices)"),
      md("## Check your results (after writing them)\n\nThe twin knows the true sample: put your final numbers below "
         "and run the cell. A wrong result is explained."),
      code("import odin_exercises as ex\n"
           "lam_edge, dlam_edge = None, None     # your (110) edge and its uncertainty [Å]\n"
           "a_fe, da_fe = None, None             # your lattice parameter and its uncertainty [Å]\n"
           "ex.check_edge(lam_edge, dlam_edge)\nex.check_lattice(a_fe, da_fe)")]
bt[1:1] = [md('**Your proposal** (click to open it):'),
           code('import sys, os' + chr(10) + 'sys.path.insert(0, os.path.abspath("../../.."))' + chr(10) + 'import nb_tools' + chr(10) + 'nb_tools.proposal("odin/exercises/iron_bragg_edges/beamtime.md")'),
           md("## 1. Your sample\n\nThe sample changer of ODIN holds the samples of the library (in NICOS, `sample_info()` describes the one mounted). For your own question, design a sample with the sample builder: blocks, cylinders and spheres of the materials you choose, as many as you want. It is saved with your proposal and appears on the sample changer of NICOS: `move(sample_holder, 'its_name')`."),
           code('nb_tools.sample_builder("odin", "1234")'),
           md("## 2. Your measurements, in NICOS\n\n1. Tab *Experiment*: **Query**, choose your proposal, then **Apply** (first: as at ESS its number, title, users and samples are filled in and its first sample is mounted; your own samples are kept with your proposal, NICOS finds them only then).\n2. **Mount your sample** (tab *Instrument interaction*, command line): `move(sample_holder, 'its_name')`, the short name of a sample of the library (e.g. `iron_plate`) or of the one you made in part 1. `sample_info()` describes the sample mounted; for a name NICOS does not know, it lists the samples available. Every count measures the sample mounted at that moment.\n3. **Record**: `with nexusfile_open('my title'): count(t=60)`; your files go to the folder of your proposal (below). The measurements and their counting times are your decisions: your budget is in your proposal."),
           code('nb_tools.nicos("odin")')]
bt += [md("## Submit your work\n\nWhen you are done: save this notebook (*Save*), then submit. The file for your teacher is made from your measurements and your notebook."),
       code("import submit\n_ = submit.Submit(\"odin/exercises/iron_bragg_edges\", \"beamtime\")")]
write(bt, "ODIN_iron_beamtime.ipynb")
