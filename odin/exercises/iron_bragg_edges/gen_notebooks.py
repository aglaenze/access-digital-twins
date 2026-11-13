"""Generates the notebooks of the exercise "How far apart are the atoms in iron?" from the guided analysis notebook
odin/ODIN_analysis.ipynb (one source: a correction there reaches every level when this script is run again):

  * ODIN_iron_msc.ipynb       MSc, "develop the method": parts 1-5 of the guided notebook (files, NeXus, raw counts,
                              reduction with the ESS software), then the model of a Bragg edge developed with the
                              model builder (model_builder.py: no code to write), checked automatically; then a
                              systematic error to investigate;
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


def lock(c, all_code=False):
    """all_code (MSc): every code cell locked, the student writes no code; beamtime: the cells to fill stay free."""
    free = (c.cell_type == "code" and not all_code and (not c.source.strip() or any(k in c.source for k in FREE_CODE))) or \
           (c.cell_type == "markdown" and c.source.startswith(FREE_TEXT))
    if not free:
        c.metadata["editable"] = False
        c.metadata["deletable"] = False


HIDDEN_START = ("q.", "q_.", "import submit", "nb_tools.", "import measure_panel", "import nb_tools" + chr(10) + "nb_tools.nicos(")


def write(cells, name, all_code_locked=False):
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
            if c.source.lstrip().startswith(("q.", "q_.", "import submit")):   # a question or the Submit button: no
                c.metadata["twin"] = {"run_at_open": "always"}    # measurement needed, the app runs it at opening
        out.append(c)
    # the cells that read the measurements do not run at opening (nothing measured yet): the app runs the cells above
    # the stop mark only. MSc: the mark is set above (part 1); beamtime: on the first code cell after the NICOS button
    if not any(c.metadata.get("twin", {}).get("run_at_open") == "stop" for c in out):
        k = next((i for i, c in enumerate(out) if c.cell_type == "code" and "nb_tools.nicos(" in c.source), None)
        nxt = next((i for i in range(k + 1, len(out)) if out[i].cell_type == "code"), None) if k is not None else None
        if nxt is not None:
            out[nxt].metadata["twin"] = {"run_at_open": "stop"}
    for c in out:
        lock(c, all_code_locked)
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
official ESS reduction. Part 6 is yours: **you develop the analysis with a model builder** (choose the model, the
range and the start values, fit, compare; no code to write), and a check cell tells you whether your result is right
(the twin knows the true sample). Part 7 is about the method itself: a systematic error to track down.

You start by measuring, in NICOS (part 0), as a user of ESS would.
"""), code(PATH_CELL), md("**Your sample** (from the sample library):"),
       code(SAMPLE_CELL)]
for c in src[i1:i6]:
    msc.append(FOLDER_CELL if c.cell_type == "code" and c.source.lstrip().startswith("from odin_paths import TWIN_RUN_ROOT")
               and "FOLDER" in c.source else clean(c))
msc += [md(r"""
## 6. Your turn: model the (110) Bragg edge

α-iron is body-centered cubic, $a = 2.8665$ Å. The planes that can diffract are (110), (200), (211)... with spacings
$d_{hkl} = a/\sqrt{h^2+k^2+l^2}$, and each family gives an edge at $\lambda = 2d_{hkl}$: by Bragg's law,
$\lambda = 2d\sin\theta$, a wavelength longer than $2d$ cannot be diffracted by these planes at any angle, so the
neutrons go through and the transmission jumps up.

You develop the analysis with the **model builder** below; nothing has to be typed.

1. **Choose the shape of the edge.** Start with the simplest, a sharp step, and look at the residuals.
2. **Choose the range** of the data: the edge, with some baseline on each side.
3. **Start values**: move the sliders until the dashed curve is close to the data, then press **Fit**.

Try the three shapes, and different ranges. For each fit the builder gives $\lambda_\text{edge}$ with its uncertainty,
the residuals (data − model, in units of the error bar) and the **reduced χ²**: about 1 when the model describes the
data within their error bars, larger when it misses something (the residuals then show a pattern instead of noise).
Every fit is kept in a table, so you can compare them. Under *See the code*: the Python lines your choices wrote.
"""), code(r"""
import model_builder as mb
expected = 2 * 2.8665 / np.sqrt(2)          # (110) edge: λ = 2 d_110 = a √2
edge_builder = mb.EdgeBuilder(lam, T, dT, expected=expected, name="(110)")
"""), code(r"""
q.choice("Which shape describes the (110) edge best, and why?",
         ["The smoothed step on a sloping baseline: reduced χ² close to 1 and residuals without a pattern.",
          "The sharp step: it is the ideal edge of a perfect crystal.",
          "The step smoothed by the resolution, on a flat baseline: the baseline cannot vary over 0.7 Å.",
          "Any of them: they all give the edge within 0.01 Å."],
         answer=0, why={1: "The measured edge is not sharp: the wavelength resolution of the instrument smooths it. "
                           "Look at the residuals of the sharp step near the edge.",
                        2: "Fit both and compare: the χ² of the flat baseline stays above 1, and the residuals rise "
                           "and fall on each side of the edge. The other planes and the absorption make the baseline "
                           "vary with λ.",
                        3: "The positions differ by more than their uncertainties, and a sharp step gives no "
                           "uncertainty at all. The model matters."},
         explanation="The resolution smooths the edge (an error function) and the baseline varies slowly with λ: "
                     "only the third model leaves residuals that look like noise (χ²/n ≈ 1).",
         hints=["Compare the reduced χ² of your fits in the table.", "Look at the residuals: noise, or a pattern?"],
         title="Choice of the model")
"""), md("**Check your edge.** The twin knows the true sample. If it is wrong, change the model, the range or the "
         "start values, fit again and run this cell again."), code(r"""
ex.check_edge(edge_builder.lam_edge, edge_builder.dlam_edge)
q.solution("part 6", explanation="A step smoothed by a Gaussian resolution of width $w$ is an error function, "
           "$T = A + C(\\lambda-\\lambda_e) + \\frac{B}{2}\\,\\mathrm{erfc}(-(\\lambda-\\lambda_e)/(\\sqrt2\\,w))$, on a "
           "sloping baseline: the third shape, in a range of about ±0.35 Å around the expected edge.")
"""), md(r"""
**From the edge to the lattice.** At the edge $\lambda = 2d_{110}$, and for a cubic lattice $d_{110} = a/\sqrt2$.
"""), code(r"""
q.number("With your edge, what is the lattice parameter $a$ of the plate, in Å?", value=2.8665, tol=0.006, unit="Å",
         mistakes=[(4.054, "the wavelength of the edge itself, not a"), (2.027, "d₁₁₀ = λ/2; a is √2 times larger"),
                   (1.433, "λ/(2√2): one factor √2 too many")],
         hints=["λ = 2 d₁₁₀, so d₁₁₀ = λ/2.", "a = √2 · d₁₁₀ = λ/√2."],
         explanation="a = λ_edge/√2 ≈ 4.06/1.414 = 2.87 Å; its uncertainty is that of λ_edge divided by √2.",
         title="Lattice parameter")
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
fluctuation would shrink if you counted longer; this does not. Find where it comes from (nothing to type: use the
builders and run the cells):

1. **The range.** In the builder of part 6, fit with a 2× wider and a 2× narrower range. Does $\lambda_\text{edge}$
   move by more than its uncertainty?
2. **The time → wavelength conversion.** The ESS reduction converts the arrival time into λ with a lookup table. The
   default table (`"simulation"`) uses a realistic ESS pulse; the other (`"analytical"`) assumes a simple pulse. The
   cell below reduces your files again with the other table and opens a second builder: fit the same model and
   compare the two edges with the truth (the check cell after it). Which table is closer, and why (the shape of the
   ESS pulse)?
3. **Counting statistics.** Measure the sample and the open beam 4 times longer in NICOS, run the notebook again: by
   how much do the uncertainty and the distance to the truth change?
"""), code(r"""
r_analytical = red.reduce(path(SAMPLE), path(OPEN), dark=path(DARK), lam=LAM, roi=ROI, wavelength_from="analytical")
T_an, dT_an = r_analytical["spectrum"].values, np.sqrt(r_analytical["spectrum"].variances)
edge_builder_analytical = mb.EdgeBuilder(lam, T_an, dT_an, expected=expected, name="(110), analytical table")
"""), code(r"""
print("default table (simulation):"); ex.check_edge(edge_builder.lam_edge, edge_builder.dlam_edge)
print("analytical table:");           ex.check_edge(edge_builder_analytical.lam_edge, edge_builder_analytical.dlam_edge)
"""), md(r"""
Write your conclusion below: what limits the accuracy of a Bragg-edge measurement, and how would you calibrate it at a
real instrument? Then check your understanding.
"""), md("## My answer\n\n(your conclusion)"), code(r"""
q.choice("You count 4 times longer. What happens to the uncertainty of the edge and to the distance between your edge "
         "and the truth?", ["The uncertainty is halved; the distance to the truth stays about the same.",
                            "Both are halved.", "Both stay the same.", "The uncertainty is divided by 4."],
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
          "By counting longer.", "By using a wider fit range.", "It cannot be corrected."],
         answer=0, why={1: "Counting longer only shrinks the statistical error.",
                        2: "The range changes the fit a little but does not remove an error of the wavelength scale.",
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
# --- before measuring, and part 0: the student measures in NICOS, one command at a time, each explained
QUIZ_CELL = code('import quiz, odin_exercises as ex\nq = quiz.Quiz("odin_iron_msc")       # the questions of this notebook')
PREP = [md(r"""
## Before you measure: three measurements, and why

A transmission is a ratio: what crosses the sample divided by what arrives without it. ODIN only counts neutrons, so you
need **three measurements**, with the same chopper settings and the same pinhole:

1. **the dark**: shutter closed, no beam at all. The camera still records a few counts (gamma rays, electronic noise):
   this background is in every measurement and has to be subtracted from the two others;
2. **the open beam**: shutter open, sample moved out of the beam. It tells how many neutrons of each wavelength arrive
   *without* the sample. The camera sees only 14 mm × 14 mm, so moving the plate 500 mm aside is more than enough;
3. **the sample**: shutter open, the iron plate in the beam.

The transmission is then $T(\lambda) = \dfrac{\text{sample} - \text{dark}}{\text{open beam} - \text{dark}}$, wavelength by
wavelength (part 5 adds the corrections).
"""), code(r"""
q.choice("Why is the open beam measured with exactly the same chopper settings and pinhole as the sample?",
         ["Because the transmission divides the two: they must see the same beam, so that only the sample makes the "
          "difference.",
          "To save time: the instrument does not have to move.",
          "Because NICOS refuses other settings.",
          "It does not matter: the reduction corrects any change of settings."],
         answer=0, why={1: "Moving the choppers takes a few seconds; the reason is the physics of the ratio.",
                        2: "NICOS would accept them; the ratio would then mix two different beams.",
                        3: "The reduction cannot correct a different beam: it only divides."},
         explanation="The ratio sample / open beam removes everything that is the same in both (the shape of the beam, "
                     "the efficiency of the camera). A different setting changes the beam itself, and the ratio would "
                     "no longer be the transmission of the sample.",
         hints=["What does a ratio cancel?"], title="Q1. Same settings")
""")]

PART0 = [md(r"""
## 0. Your measurements, in NICOS

As at ESS, you measure with **NICOS**, the control software of the instrument: you type a command, NICOS moves the
devices, counts and writes the data files. Nobody measures for you: if a file is wrong (shutter forgotten, sample in the
wrong place), you will see it in part 2 and measure again.

**Open NICOS** with the button below: it opens in its own window, logged in, in about a minute.
"""), code('import nb_tools\nnb_tools.nicos("odin")'), md(r"""
### Step 1. Your proposal

At ESS nothing is recorded without an accepted **proposal**: it gives the number of the experiment, the team and the
samples, and the files go to its folder. The proposal of this exercise is **1234**.

In NICOS, tab **Experiment**, click **Find my proposal**. NICOS asks the user office for your proposals. If you have
only one, NICOS fills in the form at once (number 1234, title, users, sample); if you have several, it lets you choose.
Check that the number is 1234, then click **Apply**: the proposal becomes the current experiment, and its sample, the
iron plate, is mounted on the sample changer.

Then go to the tab **Instrument interaction**. Type each command below in the command line at the top, then press
*Enter*, one at a time; the *Output* tab shows what NICOS does.
"""), md(r"""
### Step 2. The instrument

```
sample_info()
```
describes the sample mounted on the instrument: an iron plate of 10 mm × 10 mm, 5 mm thick. Check it before measuring.

```
move(choppers, 'wfm')
```
sets the choppers to **WFM** mode (*wavelength frame multiplication*): the wavelength of each neutron is then known
to better than 1 %, which is needed to see the sharp jumps of a Bragg edge.

```
move(wfm_delta, 0.3)
```
sets the distance between the two WFM discs to 0.3 m: a good resolution with enough neutrons (a smaller distance gives
a finer resolution, but fewer neutrons).

```
move(pinhole, 0.03)
```
chooses the pinhole of 3 cm: a sharp enough image of the plate, with many neutrons.
"""), md(r"""
### Step 3. The dark

```
move(shutter, 'closed')
```
closes the shutter just before the sample: no neutron reaches the camera.

```
with nexusfile_open('dark'): count(t=30)
```
counts for 30 s and writes **one file**, titled *dark*. `nexusfile_open` is the ESS command that records everything
measured inside it in one NeXus file, in the folder of your proposal. The *Detector image* stays almost empty: only the
background.
"""), md(r"""
### Step 4. The open beam

```
move(shutter, 'open')
```
opens the shutter: the beam reaches the sample position.

```
move(stage_x, 500)
```
moves the sample stage 500 mm to the side: the plate is out of the beam, the camera sees the beam alone.

```
with nexusfile_open('open beam'): count(t=60)
```
counts for 60 s: a file titled *open beam*. The *Detector image* fills up evenly.
"""), md(r"""
### Step 5. The iron plate

```
move(stage_x, 0)
```
brings the plate back in the beam, at the center of the camera.

```
with nexusfile_open('iron plate'): count(t=60)
```
counts for 60 s, as long as the open beam, so that both have the same statistics. The *Detector image* now shows the
plate: a darker square, because the iron stops some of the neutrons.

```
list_filewriting_jobs()
```
lists your three files: dark, open beam, iron plate.
"""), code(r"""
q.choice("In step 4, why is the plate moved 500 mm away rather than taken off the instrument?",
         ["The camera sees only 14 mm × 14 mm: 500 mm aside, the plate is far out of the beam, and the stage brings it "
          "back exactly to the same place for step 5.",
          "Because 500 mm is the length of the plate.",
          "To protect the plate from the neutrons.",
          "Because the open beam must be measured through the plate."],
         answer=0, why={1: "The plate is 10 mm wide; 500 mm is the travel of the stage.",
                        2: "The plate is not damaged by the beam; the open beam is a measurement without it.",
                        3: "The open beam is measured without the sample: it is the reference."},
         explanation="Moving the stage is what an instrument scientist does: the sample leaves the 14 mm field of view, "
                     "and the motor brings it back to the same position to the micrometer.",
         hints=["How large is the field of view of the camera?"], title="Q2. The open beam")
q.choice("You forgot `move(shutter, 'open')` before the open beam. What will your open-beam file look like?",
         ["Like a second dark: almost no neutrons, so the transmission cannot be computed.",
          "Like the sample: the plate is still in the beam.",
          "Normal: the shutter only protects the camera.",
          "NICOS refuses to count."],
         answer=0, why={1: "The plate was moved away; with the shutter closed no neutron arrives at all.",
                        2: "A closed shutter stops the beam before the sample: nothing reaches the camera.",
                        3: "NICOS counts: it does not know what you meant to measure. You will see it in the logbook."},
         explanation="Part 2 reads the logbook from your files: a file with almost no neutrons and the shutter closed is "
                     "a dark, whatever its title. Measure the open beam again.",
         hints=["What does a closed shutter stop?"], title="Q3. A forgotten shutter")
"""), md(r"""
**When the three files are written**, come back here and run the whole notebook: menu *Run > Run All Cells*. The
notebook reads your files from part 1 on.
""")]

PART1_TEXT = (
    "## 1. Your files\n\n"
    "As at ESS, NICOS has written your files in the folder of your proposal, `data/<instrument>/<year>/<proposal>/raw`. "
    "The cell below goes to the folder of proposal 1234, this year, and lists the files it finds there. If there is no "
    "file yet, it stops with a message: measure first (part 0).")
PART1_CODE = ('from odin_paths import TWIN_RUN_ROOT          # root of the results of the twins\n'
              'import datetime\n'
              'PROPOSAL = "1234"                              # the proposal of this exercise (part 0)\n'
              'FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/{PROPOSAL}/raw"')
# part 2: the three kinds of measurement are explained before part 0; here only how the logbook is read
PART2_TEXT = (
    "## 2. The logbook: which file is what?\n\n"
    "Each `nexusfile_open` block wrote **one file**, as at ESS (`odin_job_000001.hdf`, `odin_job_000002.hdf`, ...). "
    "Everything is in the file: its title, and the state of the instrument during the measurement (shutter, sample stage, "
    "pinhole, choppers). The table below is read from the files themselves.\n\n"
    "The column `kind` is deduced from the state of the instrument, not from the title: shutter closed = dark; shutter "
    "open and stage far from 0 = open beam; shutter open and stage at 0 = sample. Check it against what you did.")
Q_PART = {
    "## 3.": r"""
q.choice("What does the camera record for each neutron?",
         ["Which pixel it hit and when it arrived after the source pulse.",
          "Its wavelength, measured directly.",
          "An image, one per second.",
          "Its energy, measured by the pixel."],
         answer=0, why={1: "The wavelength is computed later, from the arrival time (part 4).",
                        2: "The file holds events, one per neutron; images are made from them.",
                        3: "A pixel only says that a neutron arrived, and when."},
         explanation="Two numbers per neutron: event_id (the pixel) and event_time_offset (the arrival time). Images, "
                     "spectra and transmissions are all computed from these lists.",
         hints=["Look at the two columns printed by the cell above."], title="Q4. What is in the file?")
""",
    "## 4.": r"""
q.choice("The sample spectrum is lower than the open-beam spectrum. Why can the transmission not simply be the ratio "
         "of these two raw spectra?",
         ["Both contain the background of the dark, and the source may not have sent the same number of protons "
          "during the two counts.",
          "Because the two spectra have different wavelengths.",
          "It can: the raw ratio is the transmission.",
          "Because the plate is not in the ROI."],
         answer=0, why={1: "Both are computed on the same wavelength bins.",
                        2: "The background and the power of the source would bias it (part 5 corrects both).",
                        3: "The ROI (white square) is on the plate."},
         explanation="The dark is subtracted from both, and each count is divided by its proton charge (the number of "
                     "neutrons produced is proportional to it): this is the reduction of part 5.",
         hints=["What else than the plate is in both measurements?"], title="Q5. Raw counts")
""",
    "## 5.": r"""
q.choice("On the plate, T ≈ 0.6 at many wavelengths. What does it mean?",
         ["60 % of the neutrons of that wavelength cross the 5 mm of iron without being stopped or deflected.",
          "60 % of the neutrons are absorbed.",
          "The plate is 60 % iron.",
          "The camera detects 60 % of the neutrons."],
         answer=0, why={1: "T is the fraction that comes through; 40 % are stopped or deflected.",
                        2: "The plate is pure iron; T depends on its thickness and on λ.",
                        3: "The efficiency of the camera cancels in the ratio sample / open beam."},
         explanation="T = 1 means nothing in the beam, T = 0 an opaque sample. The jumps of T with λ are the Bragg "
                     "edges: part 6 models them.", hints=["T is a ratio: of what to what?"], title="Q6. Transmission")
""",
}

# part 0 measured in NICOS (as at ESS) or with a panel in the notebook (as on the BSc page): the student chooses, the
# steps of NICOS are hidden with the panel (measure_panel.py), the files go to the folder of the proposal either way
PART0[0] = md(r"""
## 0. Your measurements

As at ESS, the measurements are yours: nobody measures for you, and if a file is wrong (shutter forgotten, sample in
the wrong place), you will see it in part 2 and measure again. Choose how:

- **in NICOS**, the control software of the instrument at ESS: you type commands, one at a time, each explained below.
  This is how you will work at a real beamtime;
- **here, with a panel**: the same devices, set with buttons, and a *Count* button (as on the BSc page).

Either way your files go to the folder of proposal 1234, and parts 1 to 7 read them. You can change at any time.
""")
PART0[1] = code('import measure_panel\nmeasure_panel.Panel("odin", proposal="1234", samples=["iron_plate"])')
for _c in PART0[2:]:
    if _c.cell_type == "markdown":
        _c.source = '<span class="twin-nicos"></span>\n\n' + _c.source

_k0 = next(k for k, c in enumerate(msc) if c.cell_type == "code" and "exercise_hidden" in c.source) + 1
msc[_k0:_k0] = [QUIZ_CELL] + PREP + PART0
out = []
for c in msc:
    if c.cell_type == "markdown" and c.source.startswith("## 1."):
        c.source = PART1_TEXT
        c.metadata["twin"] = {"run_at_open": "stop"}      # the app runs the cells above this one at opening
    if c.cell_type == "markdown" and c.source.startswith("## 2."):
        c.source = PART2_TEXT
    if c.cell_type == "markdown" and c.source.startswith("The cell below picks the **last** dark"):
        c.source = ("The cell below takes the **last** dark, open beam and sample of the logbook: those you have just "
                    "measured. It also checks that the three were measured with the same chopper mode and pinhole: "
                    "otherwise the ratio would mix two different beams and mean nothing (question Q1).")
    if c.cell_type == "code" and c.source.lstrip().startswith("from odin_paths import TWIN_RUN_ROOT") and "FOLDER" in c.source:
        c.source = PART1_CODE
    if c.cell_type == "code" and "if FOLDER is None:" in c.source:
        _a, _b = c.source.index("if FOLDER is None:"), c.source.index('print("folder:"')
        c.source = (c.source[:_a] + 'import nb_tools\nnb_tools.need_measurements(FOLDER, "odin")   '
                    '# stops here, with a message, while there is no file\n' + c.source[_b:])
    for head, qsrc in Q_PART.items():          # a question at the end of parts 3, 4 and 5 (before the next part)
        nxt = {"## 3.": "## 4.", "## 4.": "## 5.", "## 5.": "## 6."}[head]
        if c.cell_type == "markdown" and c.source.startswith(nxt):
            out.append(code(qsrc))
    out.append(c)
msc = out
import sys as _sys
_sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
from nbfig import figure_cell, insert_after_mission
insert_after_mission(msc, figure_cell('iron_structures.png', 'What you have to decide: α-iron (left) or γ-iron (middle)? Each structure has its own atomic planes, hence its own Bragg edges (right).'))
write(msc, "ODIN_iron_msc.ipynb", all_code_locked=True)

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
           md("## 2. Your measurements, in NICOS\n\n1. Tab *Experiment*: **Find my proposal**, choose your proposal, then **Apply** (first: as at ESS its number, title, users and samples are filled in and its first sample is mounted; your own samples are kept with your proposal, NICOS finds them only then).\n2. **Mount your sample** (tab *Instrument interaction*, command line): `move(sample_holder, 'its_name')`, the short name of a sample of the library (e.g. `iron_plate`) or of the one you made in part 1. `sample_info()` describes the sample mounted; for a name NICOS does not know, it lists the samples available. Every count measures the sample mounted at that moment.\n3. **Record**: `with nexusfile_open('my title'): count(t=60)`; your files go to the folder of your proposal (below). The measurements and their counting times are your decisions: your budget is in your proposal."),
           code('nb_tools.nicos("odin")')]
bt += [md("## Submit your work\n\nWhen you are done: save this notebook (*Save*), then submit. The file for your teacher is made from your measurements and your notebook."),
       code("import submit\n_ = submit.Submit(\"odin/exercises/iron_bragg_edges\", \"beamtime\")")]
write(bt, "ODIN_iron_beamtime.ipynb")
