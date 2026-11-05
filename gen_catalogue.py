"""Generates twin/Catalogue.ipynb: the start page of the digital twins (Voilà), a catalogue of exercises.

    python gen_catalogue.py
    voila Catalogue.ipynb       (or, in JupyterLab: right-click > Open with > Voilà)

First the ESS instrument, then the exercises on it. Each exercise has up to three ways in:
  * BSc, guided web page (Voilà, no code);
  * MSc, notebook with tasks (JupyterLab, code open, automatic checks);
  * beamtime, as at ESS: a proposal sheet, NICOS (in the Desktop of JupyterLab), a starter notebook.

The page reads the exercises when it is shown: one folder <instrument>/exercises/<name>/ with an exercise.yml per
exercise (see odin/exercises/iron_bragg_edges/exercise.yml), and catalogue_planned.yml for those not built yet.
Adding an exercise = adding a folder; this page does not need to be generated again.
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# ESS digital twins: exercises

Virtual versions of instruments of the **European Spallation Source**: the instrument is simulated with McStas (from
the official ESS model), the files have the format of the real instrument, and they are reduced with the official ESS
software. Choose an instrument, then an exercise and the way you want to work on it.
""")

code(r"""
import glob, html, os
import yaml
from IPython.display import display, HTML

ROOT = os.path.abspath(".")
INSTRUMENTS = {
    "odin": dict(name="ODIN", kind="Imaging", text="Radiography and tomography with neutrons, wavelength by wavelength"),
    "loki": dict(name="LoKI", kind="Small-angle scattering", text="Sizes and shapes of nanostructures, 1-100 nm"),
    "dream": dict(name="DREAM", kind="Powder diffraction", text="Not available yet: no official McStas model"),
    "bifrost": dict(name="BIFROST", kind="Spectroscopy", text="Not available yet: no official McStas model"),
}
MODES = {"bsc": ("BSc", "#2a7d6f"), "msc": ("MSc", "#b4562b"), "beamtime": ("Beamtime", "#33415c")}

def load():
    ex = []
    for f in sorted(glob.glob(os.path.join(ROOT, "*", "exercises", "*", "exercise.yml"))):
        with open(f, encoding="utf-8") as fh:
            ex.append(yaml.safe_load(fh))
    planned = os.path.join(ROOT, "catalogue_planned.yml")
    if os.path.isfile(planned):
        with open(planned, encoding="utf-8") as fh:
            ex += [dict(e, status="planned") for e in yaml.safe_load(fh) or []]
    return ex

def link(m):
    # links from the root of the Jupyter server: work in Voilà and in JupyterLab
    route = "voila/render" if m.get("open") == "voila" else "lab/tree"
    return f"../../{route}/{m['file']}"
""")

code(r"""
CSS = '''<style>
.cat {font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #1d2433; max-width: 1100px}
.cat h3 {margin: 18px 0 8px; font-size: 17px}
.card {border: 1px solid #d9dde5; border-radius: 10px; padding: 14px 16px; margin: 10px 0; background: #fbfbfd}
.card.planned {opacity: .55; background: #f3f4f7}
.card .t {font-size: 16px; font-weight: 650}
.card .meta {font-size: 12.5px; color: #5a6475; margin: 2px 0 8px}
.card .q {font-size: 14px; margin-bottom: 10px}
.modes {display: flex; gap: 10px; flex-wrap: wrap}
.mode {flex: 1 1 280px; border-radius: 8px; padding: 10px 12px; color: white; text-decoration: none !important}
.mode, .mode * {color: #fff !important}
.mode b {font-size: 14px} .mode span {display: block; font-size: 12.5px; opacity: .92; margin-top: 3px}
.mode:hover {filter: brightness(1.08)}
.mode .badge {float: right; font-size: 11.5px; background: rgba(255,255,255,.22); border-radius: 10px; padding: 1px 8px}
.extra {font-size: 12.5px; margin-top: 6px} .extra a {margin-right: 14px}
</style>'''

def card(e):
    esc = html.escape
    if e.get("status") == "planned":
        return (f'<div class="card planned"><div class="t">{esc(e["title"])}</div>'
                f'<div class="meta">{esc(e["technique"])} · planned</div><div class="q">{esc(e["question"])}</div></div>')
    modes = []
    for key, (label, color) in MODES.items():
        m = e.get("modes", {}).get(key)
        if not m:
            continue
        extra = ""
        if key == "beamtime":
            extra = (f'<div class="extra"><a href="../../desktop/" target="_blank">Desktop (NICOS)</a>'
                     f'<a href="{link(dict(open="lab", file=m["analysis"]))}" target="_blank">starter notebook</a></div>'
                     if m.get("analysis") else "")
        modes.append(f'<div style="flex:1 1 280px"><a class="mode" style="background:{color};display:block" '
                     f'href="{link(m)}" target="_blank"><span class="badge">{label} · {esc(m.get("duration", ""))}</span>'
                     f'<b>{esc(m["label"])}</b><span>{esc(m.get("what", ""))}</span></a>{extra}</div>')
    return (f'<div class="card"><div class="t">{esc(e["title"])}</div>'
            f'<div class="meta">{esc(e["technique"])} · sample: {esc(e.get("sample", ""))}</div>'
            f'<div class="q">{esc(e["question"])}</div><div class="modes">{"".join(modes)}</div>'
            + (f'<div class="meta" style="margin-top:8px">You learn: {esc(e["learn"])}</div>' if e.get("learn") else "")
            + '</div>')

exercises = load()
TABS = '''<style>
.tabs input {display: none}
.tabs label.tab {display: inline-block; width: 235px; margin: 0 8px 8px 0; padding: 10px 14px; border-radius: 10px;
  border: 1px solid #c9cfda; background: #fff; cursor: pointer; vertical-align: top}
.tabs label.tab b {font-size: 15px; display: block} .tabs label.tab span {font-size: 12px; color: #5a6475}
.tabs label.tab.off {opacity: .45; cursor: default}
.tabs .panel {display: none}
'''
parts, css, keys = [], [], [k for k in INSTRUMENTS]
for n, key in enumerate(keys):
    i = INSTRUMENTS[key]
    ex = [e for e in exercises if e["instrument"] == key]
    ready = [e for e in ex if e.get("status") != "planned"]
    off = "" if ready else " off"
    parts.append(f'<input type="radio" name="instr" id="t_{key}" {"checked" if n == 0 else ""} {"disabled" if not ready else ""}>'
                 f'<label class="tab{off}" for="t_{key}"><b>{i["name"]}</b><span>{i["kind"]}: {html.escape(i["text"])}</span></label>')
    css.append(f'#t_{key}:checked ~ #p_{key} {{display: block}} #t_{key}:checked + label {{border: 2px solid #2a7d6f; background: #eef6f4}}')
panels = []
for key in keys:
    i = INSTRUMENTS[key]
    ex = [e for e in exercises if e["instrument"] == key]
    body = "".join(card(e) for e in [e for e in ex if e.get("status") != "planned"] + [e for e in ex if e.get("status") == "planned"])
    panels.append(f'<div class="panel" id="p_{key}"><h3>2. Choose an exercise on {i["name"]} ({i["kind"].lower()})</h3>{body}</div>')
display(HTML(CSS + TABS + " ".join(css) + "</style>" + '<div class="cat tabs"><h3>1. Choose an instrument</h3>'
             + "".join(parts) + "".join(panels) + "</div>"))
""")

md(r"""
**How the three ways in differ.** The **BSc** page gives the settings and explains them; you measure with a button
and answer questions. The **MSc** notebook shows the code: the reduction with the ESS software is given, and you write
the analysis yourself, with automatic checks. The **beamtime** is the real thing: a proposal, a budget, the NICOS
control program of the instrument (open it from the *Desktop* of JupyterLab), and your own decisions.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, os.path.join(HERE, "Catalogue.ipynb"))
print("written Catalogue.ipynb")
