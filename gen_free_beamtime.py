"""Generates the starter notebooks of the free beamtime (no exercise: your own question, your own samples), one per
instrument, from the beamtime starter of an exercise of that instrument (one source: the tools stay the same):

    odin/exercises/free_beamtime/ODIN_free_beamtime.ipynb   (from odin/exercises/iron_bragg_edges/ODIN_iron_beamtime.ipynb)
    loki/exercises/free_beamtime/LoKI_free_beamtime.ipynb   (from loki/exercises/silica_spheres/LoKI_silica_beamtime.ipynb)

The folder free_beamtime has no exercise.yml: the catalogue shows it as the card "Free beamtime" of the instrument.

    python gen_free_beamtime.py        (after the gen_notebooks.py of the exercises)
"""
import os
import nbformat as nbf

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES = {"odin": ("ODIN", "odin/exercises/iron_bragg_edges/ODIN_iron_beamtime.ipynb", "1234"),
           "loki": ("LoKI", "loki/exercises/silica_spheres/LoKI_silica_beamtime.ipynb", "3001")}

INTRO = r"""# Free beamtime on {name}: starter notebook

No exercise here: **your own question**. Write it down first (below), as in a beamtime proposal at ESS: what do you
want to learn, on which sample, and why neutrons and {name} can answer it. Then plan your measurements (which
references does your analysis need? how long? in which configuration?), measure in NICOS (button *Open NICOS*), and
analyze your files here. Your own samples can be designed with the *Sample builder*: they appear on the sample changer
of NICOS.

**Your proposal**: choose a proposal number (e.g. your group number, 1000-9999) and enter it in the *Experiment* panel
of NICOS; write it below in `PROPOSAL`. Your files are then in `data/{instr}/<year>/<proposal>/raw`.

"""


def main():
    for instr, (name, src, number) in SOURCES.items():
        nb = nbf.read(os.path.join(ROOT, src), as_version=4)
        cells = nb.cells
        k = next((i for i, c in enumerate(cells) if c.cell_type == "markdown"
                  and c.source.startswith("## Check your results")), len(cells))
        cells = nb.cells = cells[:k]                                   # no check: there is no true answer here
        first = cells[0].source
        tools = first[first.index("**Tools**"):]                     # the list of tools of the starter
        cells[0] = nbf.v4.new_markdown_cell(INTRO.format(name=name, instr=instr) + tools)
        cells.insert(1, nbf.v4.new_markdown_cell(
            "## My question\n\n(what, on which sample, why; what result would answer it)\n\n## My plan\n\n"
            "(measurements, references, configuration, counting times, and why)"))
        # no proposal sheet here: the question is the student's own; the proposal number is 1000 (PROPOSAL)
        cells = nb.cells = [c for c in cells if not (c.cell_type == "markdown" and c.source.startswith("**Your proposal**"))]
        for c in cells:
            if c.cell_type == "code" and "nb_tools.proposal(" in c.source:
                c.source = c.source.split("nb_tools.proposal(")[0].rstrip()
                c.metadata["jupyter"] = {"source_hidden": True}
            if c.cell_type == "code" and "nb_tools.sample_builder(" in c.source:
                c.source = f'nb_tools.sample_builder("{instr}", "1000")'
            if c.cell_type == "markdown" and c.source.startswith("## 2. Your measurements, in NICOS"):
                c.source = c.source.replace("the *Proposal ID* of your proposal", "your *Proposal ID* (the number of "
                                            "PROPOSAL below)").replace(" your budget is in your proposal.", " no budget.").replace(" (e.g. `iron_plate`)", "").replace(" (e.g. `silica_spheres`, `d2o`, `empty_beam`)", "").replace(
                                            "(e.g. `iron_plate`)", "(`sample_info()`)")
            if c.cell_type == "code" and "FOLDER = " in c.source and f"/{number}/raw" in c.source:
                c.source = (f"from {instr}_paths import TWIN_RUN_ROOT\nimport datetime\n"
                            f"PROPOSAL = \"1000\"          # your proposal number (the one entered in NICOS)\n"
                            f"FOLDER = f\"{{TWIN_RUN_ROOT}}/data/{instr}/{{datetime.date.today().year}}/{{PROPOSAL}}/raw\"")
            if c.cell_type == "markdown" and c.source.startswith("## Results for the committee"):
                c.source = "## My answer\n\n(the answer to your question, with uncertainties; what you would do next)"
        cells.append(nbf.v4.new_markdown_cell("## Submit your work" + chr(10) + chr(10) + "When you are done: save this "
                     "notebook (*Save*), then submit. The file for your teacher is made from your measurements and "
                     "your notebook."))
        cells.append(nbf.v4.new_code_cell(f"import submit" + chr(10) + f"_ = submit.Submit(\"{instr}/exercises/free_beamtime\", "
                                          f"\"free\", title=\"Free beamtime on {name}\")"))
        cells[-1].metadata["jupyter"] = {"source_hidden": True}
        for c in (cells[0], cells[-2], cells[-1]):        # the cells made here are locked too (they still run)
            c.metadata["editable"] = False
            c.metadata["deletable"] = False
        out = os.path.join(ROOT, instr, "exercises", "free_beamtime")
        os.makedirs(out, exist_ok=True)
        f = os.path.join(out, f"{name}_free_beamtime.ipynb")
        nbf.write(nb, f)
        print("written", os.path.relpath(f, ROOT))


if __name__ == "__main__":
    main()
