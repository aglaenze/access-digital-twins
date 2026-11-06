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
