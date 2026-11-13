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


def distribute(cells, plan):
    """The questions along the exercise, not all at the end: the code cell holding them (q.choice(...), q.number(...),
    then q.report()) is split into one cell per question, each put right after the cell whose source contains its
    anchor; the titles "Qn." are renumbered in the order of the page; q.report() stays where the questions were.

    plan: [(anchor, [old numbers]), ...], e.g. [("button.on_click(do_count)", [7, 9]), ...]; a question not in the
    plan stays at the end. The quiz (q = quiz.Quiz(...)) must be created in a cell before the first anchor."""
    import re
    has_q = [i for i, c in enumerate(cells) if c.cell_type == "code" and re.search(r"(?m)^q\.(choice|number)\(", c.source)]
    k = next((i for i in has_q if "q.report()" in cells[i].source), has_q[0])
    src = cells[k].source
    starts = [m.start() for m in re.finditer(r"(?m)^q\.(choice|number)\(", src)]
    head = src[:starts[0]]
    end = src.find("\nq.report()")
    blocks = [src[a:b].rstrip() for a, b in zip(starts, starts[1:] + [end if end > 0 else len(src)])]
    tail = src[end:].strip() if end > 0 else ""
    by_num = {}
    for b in blocks:
        m = re.search(r'title="Q(\d+)\. ', b)
        by_num[int(m.group(1))] = b
    placed = [n for _, ns in plan for n in ns]
    cells[k].source = "\n".join(x for x in [head.strip(), *[by_num[n] for n in sorted(by_num) if n not in placed], tail] if x)
    # insert, from the last anchor to the first (indices stay valid)
    inserts = []
    for anchor, ns in plan:
        j = next(i for i, c in enumerate(cells) if anchor in c.source)
        inserts.append((j, ns))
    for j, ns in sorted(inserts, key=lambda x: -x[0]):
        for n in reversed(ns):
            cells.insert(j + 1, code(by_num[n]))
    # renumber in the order of the page
    order = []
    for c in cells:
        if c.cell_type == "code":
            order += [int(m) for m in re.findall(r'title="Q(\d+)\. ', c.source)]
    new = {old: i + 1 for i, old in enumerate(order)}
    for c in cells:                       # every mention: titles, and "(Q3)", "question Q7" in texts and hints
        c.source = re.sub(r"\bQ(\d+)\b", lambda m: f"Q{new.get(int(m.group(1)), int(m.group(1)))}", c.source)
    return cells
