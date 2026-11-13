"""Helpers of the generators of the MSc and beamtime notebooks (the conventions the app relies on).

    from nbgen import md, code, stop, write
    cells = [md("# Title"), code("..."), stop(md("## 1. Your files")), ...]
    write(cells, "path/notebook.ipynb", all_code_locked=True)       # MSc: the student writes no code

* code cells of the questions (q.), of Submit, of the measuring panel and of the buttons (nb_tools.) show their
  widgets only (source hidden), and run at opening ({"twin": {"run_at_open": "always"}});
* stop(cell): the app runs the cells above this one at opening (the cells that read the measurements wait);
* every cell is locked (not editable, not deletable): MSc all of them; beamtime all but the cells to fill
  (FREE_CODE, FREE_TEXT, empty cells); the student can always add cells of their own.
"""
import os

import nbformat as nbf

HIDDEN_START = ("q.", "q_.", "import submit", "nb_tools.", "import nb_tools", "import measure_panel")
RUN_ALWAYS = ("q.", "q_.", "import submit")
FREE_CODE = ("# your", "= None", "PROPOSAL =", "FOLDER =", "SAMPLE = ", "ROI =")
FREE_TEXT = ("## Results for the committee", "## My question", "## My answer", "## Your analysis")


def md(s):
    return nbf.v4.new_markdown_cell(s.strip())


def code(s):
    return nbf.v4.new_code_cell(s.strip())


def stop(cell):
    cell.metadata["twin"] = {"run_at_open": "stop"}
    return cell


def nicos_step(cell):
    """A text cell of the steps in NICOS: hidden when the student measures with the panel (measure_panel.py)."""
    cell.source = '<span class="twin-nicos"></span>\n\n' + cell.source
    return cell


def write(cells, path, all_code_locked=True):
    out = []
    for c in cells:
        if c.cell_type == "code":
            s = c.source.lstrip()
            if s.startswith(HIDDEN_START) or "nb_tools.proposal(" in s:
                c.metadata["jupyter"] = {"source_hidden": True}
            if s.startswith(RUN_ALWAYS) and "twin" not in c.metadata:
                c.metadata["twin"] = {"run_at_open": "always"}
        free = (c.cell_type == "code" and not all_code_locked
                and (not c.source.strip() or any(k in c.source for k in FREE_CODE))) or \
               (c.cell_type == "markdown" and c.source.startswith(FREE_TEXT))
        if not free:
            c.metadata["editable"] = False
            c.metadata["deletable"] = False
        out.append(c)
    nb = nbf.v4.new_notebook()
    nb["cells"] = out
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                      "language_info": {"name": "python"}}
    nbf.write(nb, path)
    print("written", os.path.basename(path), len(out), "cells")
