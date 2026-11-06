"""A figure of twin/figures/ as a markdown cell, the image embedded in the notebook (an <img> with the PNG data): it
shows in the Voila pages, in the notebooks and in the students' own copies (no path to follow). Used by the generators.
(Not a markdown image ![](...) nor an attachment: Voila 0.5 fails on them when it runs as a server extension.)"""
import base64
import html
import os

import nbformat as nbf

FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")


def figure_cell(name, caption=""):
    with open(os.path.join(FIG, name), "rb") as f:
        data = base64.b64encode(f.read()).decode()
    img = (f'<img src="data:image/png;base64,{data}" alt="{html.escape(caption or name)}" '
           f'style="max-width: 100%; height: auto;">')
    return nbf.v4.new_markdown_cell(img + (f"\n\n*{caption}*" if caption else ""))


def insert_after_mission(cells, fig):
    """Puts the figure right after the paragraph "Your mission" (the cell is split there if it goes on)."""
    k = next((i for i, c in enumerate(cells) if c.cell_type == "markdown" and "Your mission" in c.source), None)
    if k is None:
        cells.insert(1, fig)
        return
    src = cells[k].source
    start = src.index("Your mission")
    end = src.find("\n\n", start)
    if end < 0 or not src[end:].strip():
        cells.insert(k + 1, fig)
        return
    first, rest = src[:end].rstrip(), src[end:].strip()
    cells[k] = nbf.v4.new_markdown_cell(first)
    cells[k + 1:k + 1] = [fig, nbf.v4.new_markdown_cell(rest)]
