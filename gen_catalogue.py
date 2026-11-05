"""Generates twin/Catalogue.ipynb: the start page of the digital twins (Voilà), a catalogue of exercises.

    python gen_catalogue.py
    voila Catalogue.ipynb       (or, in JupyterLab: right-click > Open with > Voilà)

First the ESS instrument, then the exercises on it. Each exercise has up to three ways in:
  * BSc, guided web page (Voilà, no code);
  * MSc, notebook with tasks (JupyterLab, code open, automatic checks);
  * beamtime, as at ESS: a proposal sheet, NICOS (the control room, opened by a button), a starter notebook.

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
# Open NICOS: in the container, the control room (remote screen, /desktop/); in the local app (twins installed by
# hand, container/run_app_local.ps1), a page that opens the control room as windows of the computer
NICOS_URL = "../../voila/render/container/open_nicos.ipynb" if os.environ.get("TWIN_APP_LOCAL") else "../../desktop/"
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
            e = yaml.safe_load(fh)
        e["_dir"] = os.path.relpath(os.path.dirname(f), ROOT).replace(os.sep, "/")
        ex.append(e)
    planned = os.path.join(ROOT, "catalogue_planned.yml")
    if os.path.isfile(planned):
        with open(planned, encoding="utf-8") as fh:
            ex += [dict(e, status="planned") for e in yaml.safe_load(fh) or []]
    return ex

def personal_copy(rel):
    # a notebook of an exercise copied once into work/ (the student's own, kept between sessions: work/ is in the
    # data volume of the container); its relative paths are made absolute. Returns the path of the copy.
    import nbformat
    src = os.path.join(ROOT, rel)
    ex_dir = os.path.dirname(src)
    instr_dir = os.path.dirname(os.path.dirname(ex_dir))
    dst_rel = f"work/{os.path.basename(instr_dir)}_{os.path.basename(ex_dir)}/{os.path.basename(rel)}"
    dst = os.path.join(ROOT, dst_rel)
    if not os.path.isfile(dst):
        nb = nbformat.read(src, as_version=4)
        for c in nb.cells:
            c.source = (c.source.replace('os.path.abspath("../../..")', repr(ROOT))
                        .replace('os.path.abspath("../..")', repr(instr_dir))
                        .replace('"exercise.yml"', repr(os.path.join(ex_dir, "exercise.yml"))))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        nbformat.write(nb, dst)
    return dst_rel


def link(m, file=None):
    # from the root of the server: pages in Voilà; notebooks alone (Jupyter Notebook view, no file browser), on the
    # student's own copy
    file = file or m["file"]
    if file.endswith(".ipynb") and m.get("open") != "voila":
        return f"../../notebooks/{personal_copy(file)}"
    return f"../../voila/render/{file}"


def sheet(rel):
    import mistune
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return mistune.html(fh.read())
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
.btns {margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap}
.btn {display: inline-block; padding: 7px 12px; border-radius: 7px; font-size: 13px; font-weight: 600;
  text-decoration: none !important; border: 1px solid #c9cfda; color: #1d2433 !important; background: #fff}
.btn.nicos {background: #1d2433; color: #fff !important; border-color: #1d2433}
.btn:hover {filter: brightness(0.96)}
details.sheet {margin-top: 8px; font-size: 13px; background: #fff; border: 1px solid #d9dde5; border-radius: 8px;
  padding: 6px 12px} details.sheet summary {cursor: pointer; font-weight: 600}
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
        head = (f'<span class="badge">{label} · {esc(m.get("duration", ""))}</span><b>{esc(m["label"])}</b>'
                f'<span>{esc(m.get("what", ""))}</span>')
        if key == "bsc":                      # BSc: the guided page only (no NICOS at this level)
            modes.append(f'<div style="flex:1 1 280px"><a class="mode" style="background:{color};display:block" '
                         f'href="{link(m)}" target="_blank">{head}</a></div>')
            continue
        nicos = f'<a class="btn nicos" href="{NICOS_URL}" target="_blank">Open NICOS</a>' if m.get("nicos") or key == "msc" else ""
        if key == "msc":
            btns = f'<a class="btn" href="{link(m)}" target="_blank">Open the notebook</a>{nicos}'
            extra = ""
        else:                                 # beamtime: the proposal sheet here, NICOS, the starter notebook
            btns = (nicos + f'<a class="btn" href="{link(m, m["analysis"])}" target="_blank">Starter notebook</a>'
                    f'<a class="btn" href="../../voila/render/Sample_builder.ipynb" target="_blank">Sample builder</a>')
            extra = f'<details class="sheet"><summary>Your proposal</summary>{sheet(m["file"])}</details>'
        modes.append(f'<div style="flex:1 1 280px"><div class="mode" style="background:{color}">{head}</div>'
                     f'<div class="btns">{btns}</div>{extra}</div>')
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
display(HTML("<script>document.title = \"ESS digital twins\"</script>" + CSS + TABS + " ".join(css) + "</style>" + '<div class="cat tabs"><h3>1. Choose an instrument</h3>'
             + "".join(parts) + "".join(panels) + "</div>"))
""")

md(r"""
**How the three ways in differ.** **BSc**: a guided page; the settings are given and explained, you measure with a
button and answer questions. **MSc**: you measure in NICOS (*Open NICOS*; the commands are given in the notebook),
then you analyze in your notebook (*Open the notebook*): the reduction with the ESS software is given, you write the
analysis, automatic checks tell you if you are right. **Beamtime**: the real thing: a proposal, a budget, NICOS, a
starter notebook, and your own decisions; you can also design your own sample (*Sample builder*). Your notebooks are
yours: they are kept between sessions.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, os.path.join(HERE, "Catalogue.ipynb"))
print("written Catalogue.ipynb")
