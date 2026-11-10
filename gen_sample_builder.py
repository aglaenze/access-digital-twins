"""Generates twin/Sample_builder.ipynb: the sample builder of the beamtimes (Voilà page).

    python gen_sample_builder.py
    voila Sample_builder.ipynb

Opened from a beamtime notebook (button Sample builder, nb_tools.sample_builder): the address gives the instrument and
the proposal (?instrument=odin&proposal=1234), so nothing to choose; opened alone, the page asks for the instrument.
ODIN: as many blocks, cylinders (vertical) and spheres of crystalline materials as wanted; LoKI: as many kinds of
particles as wanted, in a H2O/D2O solvent. The student sees the sample, then saves it in the samples folder of the
proposal: it is on the sample changer of NICOS (move(sample_holder, '<name>')), simulated by McStas on its first count.
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Sample builder

Design your sample, look at it, and put it on the sample changer of the instrument. As at ESS, the sample is declared
with your proposal: it is saved with it, and in NICOS you mount it with `move(sample_holder, 'its_name')`;
`sample_info()` describes it. Its first measurement starts a McStas simulation (a few minutes), the next ones are fast.
""")

code(r"""
import sys, os, datetime, warnings
from urllib.parse import parse_qs
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("loki"))
import sample_library as sl

ROOT = os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin")).replace(os.sep, "/")
QS = parse_qs(os.environ.get("QUERY_STRING", ""))         # ?instrument=odin&proposal=1234 (from the notebook;
#                                                          an imported proposal also gives &name=...&title=...)
GIVEN = QS.get("instrument", [""])[0].lower()
NAMES = {"odin": "ODIN (imaging)", "loki": "LoKI (small-angle scattering)"}
instr = w.ToggleButtons(options=[(v, k) for k, v in NAMES.items()], value=GIVEN if GIVEN in NAMES else "odin",
                        description="Instrument")
proposal = w.Text(value=QS.get("proposal", [""])[0], placeholder="e.g. 1234", description="Proposal")
name = w.Text(value=QS.get("name", [""])[0], placeholder="e.g. my_steel_wedge", description="Short name")
title = w.Text(value=QS.get("title", [""])[0], placeholder="e.g. Steel wedge with a copper insert", description="Title",
               layout=w.Layout(width="520px"))
description = w.Textarea(value="", placeholder="what it is, why you made it", description="Description",
                         layout=w.Layout(width="520px", height="60px"))
head = [instr] if GIVEN not in NAMES else [w.HTML(f"<b>Instrument: {NAMES[GIVEN]}</b>")]
display(w.VBox(head + [proposal, name, title, description]))
""")

md(r"""
## Your sample
""")

code(r"""
small = lambda d, v: w.FloatText(value=v, description=d, layout=w.Layout(width="118px"), style={"description_width": "52px"})

# ---------------------------------------------------------------- ODIN: blocks, cylinders, spheres
MATS = list(sl.ODIN_MATERIALS.items())
odin_items = w.VBox()
SIZES = {"box": (("width", 10.0), ("height", 10.0), ("thick", 5.0)),
         "cylinder": (("diameter", 4.0), ("height", 10.0)),
         "sphere": (("diameter", 4.0),)}
LABEL = {"box": "Block", "cylinder": "Cylinder", "sphere": "Sphere"}

def add_odin(shape):
    mat = w.Dropdown(options=MATS, value=MATS[0][1], layout=w.Layout(width="170px"))
    pos = [small(d, 0.0) for d in ("x [mm]", "y [mm]", "z [mm]")]
    size = [small(d, v) for d, v in SIZES[shape]]
    rm = w.Button(description="", icon="trash", tooltip="remove", layout=w.Layout(width="44px"))
    row = w.HBox([w.HTML(f"<b style='display:inline-block;width:64px'>{LABEL[shape]}</b>"), mat] + pos + size + [rm],
                 layout=w.Layout(flex_flow="row wrap", align_items="center"))
    row.shape, row.mat, row.pos, row.size = shape, mat, pos, size
    rm.on_click(lambda _: setattr(odin_items, "children", tuple(r for r in odin_items.children if r is not row)))
    odin_items.children = odin_items.children + (row,)

def odin_spec():
    vols = []
    for r in odin_items.children:
        s = [v.value for v in r.size]
        size = s if r.shape == "box" else [s[0], s[1], s[0]] if r.shape == "cylinder" else [s[0]] * 3
        vols.append(dict(material=r.mat.value, center_mm=[p.value for p in r.pos], size_mm=size,
                         **({"shape": r.shape} if r.shape != "box" else {})))
    return dict(name=title.value or name.value, description=description.value, volumes=vols)

add_odin("box")
odin_buttons = [w.Button(description=f"Add a {LABEL[s].lower()}", icon="plus", layout=w.Layout(width="auto")) for s in SIZES]
for b, s in zip(odin_buttons, SIZES):
    b.on_click(lambda _, s=s: add_odin(s))
odin_box = w.VBox([w.HTML("As many volumes as you want, each of one crystalline material; they must not overlap. "
                          "x is horizontal, y vertical (mm, from the center of the beam), z along the beam; cylinders "
                          "stand vertically (the axis of the rotation stage). The camera sees 14 mm × 14 mm."),
                   odin_items, w.HBox(odin_buttons)])

# ---------------------------------------------------------------- LoKI: kinds of particles in a solvent
loki_items = w.VBox()
MODELS = {"sphere": ("Spheres", (("radius [Å]", 50.0),)),
          "cylinder": ("Cylinders", (("radius [Å]", 20.0), ("length [Å]", 400.0))),
          "core_shell_sphere": ("Core-shell spheres", (("radius [Å]", 50.0), ("shell [Å]", 20.0)))}
PARAMS = {"sphere": ("radius",), "cylinder": ("radius", "length"), "core_shell_sphere": ("radius", "thickness")}

def add_loki(model):
    mat = w.Dropdown(options=list(sl.SLD), value="silica", layout=w.Layout(width="170px"))
    pars = [small(d, v) for d, v in MODELS[model][1]]
    phi = w.BoundedFloatText(value=0.5, min=0.01, max=10, step=0.1, description="vol. %", layout=w.Layout(width="140px"),
                             style={"description_width": "62px"})
    rm = w.Button(description="", icon="trash", tooltip="remove", layout=w.Layout(width="44px"))
    row = w.HBox([w.HTML(f"<b style='display:inline-block;width:140px'>{MODELS[model][0]}</b>"), mat] + pars + [phi, rm],
                 layout=w.Layout(flex_flow="row wrap", align_items="center"))
    row.model, row.mat, row.pars, row.phi = model, mat, pars, phi
    rm.on_click(lambda _: setattr(loki_items, "children", tuple(r for r in loki_items.children if r is not row)))
    loki_items.children = loki_items.children + (row,)

d2o = w.FloatSlider(value=1.0, min=0.0, max=1.0, step=0.05, description="D2O fraction")
thick = w.FloatSlider(value=1.0, min=0.1, max=5.0, step=0.1, description="cell [mm]")

def loki_spec():
    pops = [dict(model=r.model, particle=r.mat.value, volume_fraction=round(r.phi.value / 100, 5),
                 parameters={p: v.value for p, v in zip(PARAMS[r.model], r.pars)}) for r in loki_items.children]
    spec = dict(name=title.value or name.value, description=description.value, model="none",
                solvent=dict(d2o_fraction=round(d2o.value, 3)), thickness_mm=round(thick.value, 2))
    if pops:
        spec.update(populations=pops)
        spec.pop("model")
    return spec

add_loki("sphere")
loki_buttons = [w.Button(description=f"Add {MODELS[m][0].lower()}", icon="plus", layout=w.Layout(width="auto")) for m in MODELS]
for b, m in zip(loki_buttons, MODELS):
    b.on_click(lambda _, m=m: add_loki(m))
loki_box = w.VBox([w.HTML("Particles dispersed in water, dilute (no interaction between them): as many kinds as you "
                          "want (remove them all for the solvent alone). The solvent is a mixture of light (H2O) and heavy "
                          "water (D2O): it sets the <b>contrast</b> and the incoherent background (H2O scatters much more)."),
                   d2o, thick, loki_items, w.HBox(loki_buttons)])

def show_part(_=None):
    odin_box.layout.display = "" if instr.value == "odin" else "none"
    loki_box.layout.display = "" if instr.value == "loki" else "none"

instr.observe(show_part, "value")
show_part()
display(odin_box, loki_box)
""")

md(r"""
## Look at it, then save it
""")

code(r"""
out = w.Output()
b_view = w.Button(description="Show my sample", icon="eye", layout=w.Layout(width="auto"))
b_save = w.Button(description="Save it with my proposal", icon="save", button_style="success", layout=w.Layout(width="auto"))

def spec_now():
    return odin_spec() if instr.value == "odin" else loki_spec()

def view(_):
    out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    with out:
        spec = spec_now()
        errors = sl.validate(instr.value, spec)
        if errors:
            print("To fix:", *errors, sep="\n  ")
            return
        print(sl.describe(instr.value, spec))
        sl.draw(instr.value, spec, fig=plt.figure(figsize=(10, 4)))
        sl.show()
        if instr.value == "loki":
            q, I, truth = sl.loki_cross_section(spec)
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.loglog(q, I, "k-")
            ax.set(xlim=(3e-3, 0.6), ylim=(max(I.min() / 2, 1e-4), I.max() * 2), xlabel="Q [1/Å]",
                   ylabel="dΣ/dΩ [1/cm]", title="what your sample scatters (exact, no instrument)")
            ax.grid(alpha=0.3, which="both"); sl.show(fig)

def save(_):
    out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    with out:
        if not proposal.value.strip().isdigit():
            print("Give your proposal number (the one entered in NICOS, Experiment panel)."); return
        folder = f"{ROOT}/data/{instr.value}/{datetime.date.today().year}/{proposal.value.strip()}/raw"
        try:
            path = sl.save(instr.value, spec_now(), folder, name.value.strip())
        except ValueError as e:
            print("Not saved:", e); return
        print(f"Saved: {path}")
        print(f"In NICOS ({instr.value.upper()}):   move(sample_holder, '{name.value.strip()}')   then   sample_info()")

b_view.on_click(view); b_save.on_click(save)
display(w.HBox([b_view, b_save]), out)
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, os.path.join(HERE, "Sample_builder.ipynb"))
print("written Sample_builder.ipynb")
