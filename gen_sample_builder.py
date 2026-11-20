"""Generates twin/Sample_builder.ipynb: the sample builder of the beamtimes (Voilà page).

    python gen_sample_builder.py
    voila Sample_builder.ipynb

Opened from a beamtime notebook (button Sample builder, nb_tools.sample_builder): the address gives the instrument and
the proposal (?instrument=odin&proposal=1234), so nothing to choose; opened alone, the page asks for the instrument.
ODIN: a samplecraft recipe edited with widgets (scene_builder.Editor): a tree of bodies of any shape (primitives,
constructive solid geometry, meshes from files, lumpy grains, sawn pieces), each turned in 3D, inside one another;
fills (grains of any shape or copies of components, with sizes, aspects, textures, clusters; Voronoi polycrystals;
pores from Gaussian random fields); materials (crystals, minerals, formulas, mixtures, calibrated on a measured Σ,
with their sources); the whole recipe as YAML. Built (seeded), checked, drawn, its radiograph and a 3D view
computed; saved with the
proposal (on the sample changer of NICOS: move(sample_holder, '<name>')) or as a model. LoKI: kinds of particles in
a H2O/D2O solvent.
Start from an example (odin/templates), a model saved by a user (<TWIN_RUN_ROOT>/templates/<instrument>/), or any
sample of the library (the Martian meteorite included: its recipe).
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
`sample_info()` describes it. You can also save it as a **model**, to start from it again later.
""")

code(r"""
import sys, os, re, glob, base64, datetime, warnings
from urllib.parse import parse_qs
warnings.filterwarnings("ignore")
import numpy as np
import yaml
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("odin"))
sys.path.insert(0, os.path.abspath("loki"))
import sample_library as sl
import scene_builder as sb

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

def data_folder():
    p = proposal.value.strip()
    return f"{ROOT}/data/{instr.value}/{datetime.date.today().year}/{p}/raw" if p else None
""")

md(r"""
## Start from

An example, a model saved by a user, or any sample of the library (the Martian meteorite of the exercise too: its
whole recipe). Everything can then be changed. Or start from scratch.
""")

code(r"""
def starts(ins):
    out = [("— from scratch —", ("", None))]
    for folder, kind in ((os.path.join(os.path.abspath("."), ins, "templates"), "example"), (f"{ROOT}/templates/{ins}", "model")):
        for f in sorted(glob.glob(os.path.join(folder, "*.yml"))):
            try:
                t = yaml.safe_load(open(f, encoding="utf-8")) or {}
            except Exception:
                continue
            if ins == "odin" and "bodies" not in (t.get("recipe") or {}):
                continue                                   # (a model of an older version of the builder)
            who = f" (by {t['author']})" if t.get("author") else ""
            out.append((f"{kind}: {t.get('title') or t.get('name')}{who}", (kind, f)))
    for n, s in sl.load(ins, data_folder()).items():
        out.append((f"{'library' if s['source'] == 'built-in' else 'your sample'}: {s.get('name') or n}", ("sample", n)))
    return out

start = w.Dropdown(layout=w.Layout(width="560px"), description="Start from")
b_start = w.Button(description="Load it", icon="folder-open", layout=w.Layout(width="auto"))
out_start = w.Output()

def refresh_starts(_=None):
    start.options = starts(instr.value)

refresh_starts()
instr.observe(refresh_starts, "value")
proposal.observe(refresh_starts, "value")
display(w.HBox([start, b_start]), out_start)
""")

md(r"""
## Your sample

**Bodies**: the tree of the sample. Each body has a shape (block, sphere, ellipsoid, cylinder, cone, torus, rounded
block, lumpy grain or pebble, sawn piece of rock, prism, a mesh from a file, or a combination of shapes: union,
intersection, difference), a position and a rotation in 3D, and a material; a body inside another one replaces its
material there (an inclusion, a pore, a grain; inclusions in inclusions too). Bodies of the same parent must not
overlap. A **fill** adds many grains at random (an amount, sizes, a grain shape, lumps, orientations or a texture,
clusters; or copies of a component), a Voronoi polycrystal, or pores. **Materials**: crystals, minerals, formulas,
mixtures, or calibrated so that Σ is a measured value; give the source of each. **Recipe (YAML)**: the whole sample,
to change anything. x is horizontal, y vertical (mm, from the center of the beam), z along the beam; the camera
sees 14 mm × 14 mm.
""")

code(r"""
editor = sb.Editor(files_dir=f"{ROOT}/sample_files/{proposal.value.strip() or 'anonymous'}")

# ---------------------------------------------------------------- LoKI: kinds of particles in a solvent
def num(d, v, width="118px", dw="52px"):
    return w.FloatText(value=v, description=d, layout=w.Layout(width=width), style={"description_width": dw})

loki_items = w.VBox()
MODELS = {"sphere": ("Spheres", (("radius [Å]", 50.0),)),
          "cylinder": ("Cylinders", (("radius [Å]", 20.0), ("length [Å]", 400.0))),
          "core_shell_sphere": ("Core-shell spheres", (("radius [Å]", 50.0), ("shell [Å]", 20.0)))}
PARAMS = {"sphere": ("radius",), "cylinder": ("radius", "length"), "core_shell_sphere": ("radius", "thickness")}

def add_loki(model, particle="silica", values=None, phi=0.5):
    mat = w.Dropdown(options=list(sl.SLD), value=particle, layout=w.Layout(width="170px"))
    pars = [num(d, v if values is None else values[k]) for k, (d, v) in enumerate(MODELS[model][1])]
    phi_w = w.BoundedFloatText(value=phi, min=0.01, max=10, step=0.1, description="vol. %", layout=w.Layout(width="140px"),
                               style={"description_width": "62px"})
    row = w.HBox()
    rm = w.Button(description="", icon="trash", layout=w.Layout(width="40px"))
    rm.on_click(lambda _: setattr(loki_items, "children", tuple(r for r in loki_items.children if r is not row)))
    row.children = [w.HTML(f"<b style='display:inline-block;width:140px'>{MODELS[model][0]}</b>"), mat] + pars + [phi_w, rm]
    row.layout = w.Layout(flex_flow="row wrap", align_items="center")
    row.model, row.mat, row.pars, row.phi = model, mat, pars, phi_w
    loki_items.children += (row,)

d2o = w.FloatSlider(value=1.0, min=0.0, max=1.0, step=0.05, description="D2O fraction")
thick = w.FloatSlider(value=1.0, min=0.1, max=5.0, step=0.1, description="cell [mm]")

def loki_spec():
    pp = [dict(model=r.model, particle=r.mat.value, volume_fraction=round(r.phi.value / 100, 5),
               parameters={p: v.value for p, v in zip(PARAMS[r.model], r.pars)}) for r in loki_items.children]
    spec = dict(model="none", solvent=dict(d2o_fraction=round(d2o.value, 3)), thickness_mm=round(thick.value, 2))
    if pp:
        spec.update(populations=pp)
        spec.pop("model")
    return spec

def load_loki(spec):
    loki_items.children = ()
    d2o.value = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
    thick.value = float(spec.get("thickness_mm", 1.0))
    for p in sl.populations(spec):
        add_loki(p["model"], p.get("particle", "silica"), [p["parameters"][q] for q in PARAMS[p["model"]]],
                 100 * float(p.get("volume_fraction", 0.005)))

add_loki("sphere")
loki_buttons = [w.Button(description=f"Add {MODELS[m][0].lower()}", icon="plus", layout=w.Layout(width="auto")) for m in MODELS]
for b, m in zip(loki_buttons, MODELS):
    b.on_click(lambda _, m=m: add_loki(m))
loki_box = w.VBox([w.HTML("Particles dispersed in water, dilute (no interaction between them): as many kinds as you "
                          "want (remove them all for the solvent alone). The solvent is a mixture of light (H2O) and heavy "
                          "water (D2O): it sets the <b>contrast</b> and the incoherent background (H2O scatters much more)."),
                   d2o, thick, loki_items, w.HBox(loki_buttons)])
odin_box = editor.widget

def show_part(_=None):
    odin_box.layout.display = "" if instr.value == "odin" else "none"
    loki_box.layout.display = "" if instr.value == "loki" else "none"

instr.observe(show_part, "value")
show_part()
display(odin_box, loki_box)

def load_start(_):
    out_start.clear_output(wait=True)
    with out_start:
        kind, ref = start.value
        try:
            if not kind:
                if instr.value == "odin":
                    editor.recipe = sb.new_recipe(); editor.sel = (0,); editor.refresh()
                else:
                    load_loki(dict(populations=[dict(model="sphere", particle="silica", parameters=dict(radius=50),
                                                     volume_fraction=0.005)]))
                print("A new sample: change it as you like."); return
            if kind == "sample":
                s = sl.load(instr.value, data_folder())[ref]
                t = dict(title=s.get("name", ref), description=s.get("description", ""), spec=s)
                if instr.value == "odin":
                    t["recipe"] = sb.recipe_of(s)
            else:
                t = yaml.safe_load(open(ref, encoding="utf-8"))
            title.value = t.get("title") or title.value
            description.value = t.get("description") or ""
            if instr.value == "odin":
                editor.recipe = t["recipe"]; editor.sel = (0,); editor.refresh()
            else:
                load_loki(t.get("spec") or t)
            print(f"Loaded: {t.get('title') or ref}. Change it, then build it (below).")
        except Exception as e:
            print("Could not load it:", e)

b_start.on_click(load_start)
""")

md(r"""
## Build it, look at it, then save it

*Build and show* generates the sample from its recipe (the grains of the fills placed at random, from the seed: the
same recipe gives the same sample), checks it (every body inside its parent, no two neighbors overlapping), and shows
two cuts through it, a radiograph (the transmission at the wavelength you choose, no noise, no blur), the
attenuation of each material, and a 3D view that you can turn (the main material see-through, so that what is inside
shows). A sample of thousands of grains takes a minute or more.
""")

code(r"""
out = w.Output()
BUILT = {}
b_view = w.Button(description="Build and show", icon="eye", button_style="primary", layout=w.Layout(width="auto"))
b_save = w.Button(description="Save it with my proposal", icon="save", button_style="success", layout=w.Layout(width="auto"))
model_name = w.Text(placeholder="e.g. wet_sandstone", description="Model name", style={"description_width": "86px"})
b_model = w.Button(description="Save as a model", icon="bookmark", layout=w.Layout(width="auto"))
lam = w.FloatSlider(value=3.0, min=1.0, max=9.0, step=0.1, description="λ [Å]", continuous_update=False)
download = w.HTML()

class _Mem:                                            # a sample built here, for the hybrid model of the twin
    def __init__(self, scene):
        self.scene, self.key = scene, f"mem:{id(scene)}"

def build_now():
    if instr.value == "loki":
        return None
    r = editor.recipe_copy()
    if BUILT.get("recipe") != r:
        print("Building the sample...", flush=True)
        scene, lines, problems = sb.build(r)
        BUILT.update(recipe=r, scene=scene, lines=lines, problems=problems, T=None, surf=None)
    return BUILT

def spec_now():
    if instr.value == "loki":
        return dict(name=title.value or name.value, description=description.value, **loki_spec())
    b = build_now()
    return sb.sample_spec(b["recipe"], b["scene"], name.value, title.value, description.value)

def radiograph(ax):
    import odin_hybrid as oh
    if BUILT.get("T") is None:
        BUILT["T"] = oh.scene_transmission(_Mem(BUILT["scene"]), 0.0, 0.0)
    g = np.linspace(-7e-3, 7e-3, 351)
    X, Y = np.meshgrid(g, g)
    t = BUILT["T"](X.ravel(), Y.ravel(), np.full(X.size, lam.value)).reshape(X.shape)
    im = ax.imshow(t, origin="lower", extent=(-7, 7, -7, 7), cmap="gray",
                   vmin=max(0.0, float(np.percentile(t, 1)) - 0.02), vmax=1.0)
    ax.set(xlabel="x [mm]", ylabel="y [mm]", title=f"Radiograph at {lam.value:.1f} Å (no noise, no blur)")
    plt.colorbar(im, ax=ax, label="transmission T", shrink=0.85)

img = w.Output()

def show_radiograph(_=None):
    if "scene" not in BUILT:
        return
    img.clear_output(wait=True)
    with img:
        fig, ax = plt.subplots(figsize=(6.2, 5))
        radiograph(ax)
        sl.show(fig)

lam.observe(show_radiograph, "value")

img3d = w.Output()
azim = w.IntSlider(value=-60, min=-180, max=180, step=15, description="turn [°]", continuous_update=False)
elev = w.IntSlider(value=20, min=-10, max=90, step=10, description="tilt [°]", continuous_update=False)

def show_3d(_=None):
    if "scene" not in BUILT:
        return
    img3d.clear_output(wait=True)
    with img3d:
        try:
            if BUILT.get("surf") is None:
                BUILT["surf"] = sb.surfaces(BUILT["scene"])
            sb.draw_3d(BUILT["scene"], dict(name=name.value), azim=azim.value, elev=elev.value,
                       fig=plt.figure(figsize=(7.5, 6.5)), surf=BUILT["surf"])
            sl.show()
        except Exception as e:
            print("No 3D view:", e)

azim.observe(show_3d, "value"); elev.observe(show_3d, "value")

def view(_):
    out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    img.clear_output()
    img3d.clear_output()
    with out:
        try:
            if instr.value == "loki":
                spec = spec_now()
                errors = sl.validate("loki", spec)
                if errors:
                    print("To fix:", *errors, sep="\n  "); return
                print(sl.describe("loki", spec))
                q, I, truth = sl.loki_cross_section(spec)
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.loglog(q, I, "k-")
                ax.set(xlim=(3e-3, 0.6), ylim=(max(I.min() / 2, 1e-4), I.max() * 2), xlabel="Q [1/Å]",
                       ylabel="dΣ/dΩ [1/cm]", title="what your sample scatters (exact, no instrument)")
                ax.grid(alpha=0.3, which="both"); sl.show(fig)
                return
            b = build_now()
            spec = spec_now()
            for l in b["lines"]:
                print("  placed:", l)
            if b["problems"]:
                print("To fix:", *b["problems"], sep="\n  ")
            print(sl.describe("odin", dict(spec, id=name.value or "sample")))
            sl.draw("odin", spec, hidden=["nothing"], fig=plt.figure(figsize=(11, 5.6)))
            sl.show()
            display(w.HTML(editor.sigma_table()))
            txt = yaml.safe_dump(b["recipe"], sort_keys=False, allow_unicode=True, width=110, default_flow_style=None)
            download.value = (f"<a download='{name.value.strip() or 'sample'}_recipe.yml' href='data:text/yaml;base64,"
                              f"{base64.b64encode(txt.encode()).decode()}'>Download the recipe (YAML)</a>")
        except Exception as e:
            print("Could not build it:", e)
            return
    show_radiograph()
    if instr.value != "loki":
        show_3d()

def save(_):
    out.clear_output(wait=True)
    with out:
        if not proposal.value.strip().isdigit():
            print("Give your proposal number (the one entered in NICOS, Experiment panel)."); return
        try:
            if instr.value == "odin" and (build_now() or {}).get("problems"):
                print("To fix first:", *BUILT["problems"], sep="\n  "); return
            path = sl.save(instr.value, spec_now(), data_folder(), name.value.strip())
        except ValueError as e:
            print("Not saved:", e); return
        print(f"Saved: {path}")
        print(f"In NICOS ({instr.value.upper()}):   move(sample_holder, '{name.value.strip()}')   then   sample_info()")
        refresh_starts()

def save_model(_):
    out.clear_output(wait=True)
    with out:
        n = model_name.value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", n):
            print("Model name: lowercase letters, digits and _, starting with a letter (e.g. wet_sandstone)."); return
        folder = f"{ROOT}/templates/{instr.value}"
        path = os.path.join(folder, n + ".yml")
        author = f"proposal {proposal.value.strip()}" if proposal.value.strip() else "anonymous"
        if os.path.exists(path) and (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("author") != author:
            print(f"A model {n} already exists (made by someone else): choose another name."); return
        t = dict(name=n, instrument=instr.value, title=title.value or n, description=description.value, author=author,
                 saved=datetime.datetime.now().isoformat(timespec="minutes"))
        if instr.value == "odin":
            t["recipe"] = editor.recipe_copy()
        else:
            t["spec"] = loki_spec()
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(t, f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)
        refresh_starts()
        print(f"Saved as a model: {t['title']} ({path}). Anyone can now start from it (Start from, at the top).")

b_view.on_click(view); b_save.on_click(save); b_model.on_click(save_model)
display(w.HBox([b_view, b_save]), w.HBox([model_name, b_model]), out, lam, img, w.HBox([azim, elev]), img3d,
        download)
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, os.path.join(HERE, "Sample_builder.ipynb"))
print("written Sample_builder.ipynb")
