"""Generates twin/Sample_builder.ipynb: the sample builder of the beamtimes (Voilà page).

    python gen_sample_builder.py
    voila Sample_builder.ipynb

Opened from a beamtime notebook (button Sample builder, nb_tools.sample_builder): the address gives the instrument and
the proposal (?instrument=odin&proposal=1234), so nothing to choose; opened alone, the page asks for the instrument.
ODIN: a recipe (rock_builder.build_sample): a piece of any shape (block, cylinder, sphere, ellipsoid, lumpy pebble,
sawn piece with irregular edges), objects placed by hand (inclusions in it, or in each other), populations of grains
placed at random without overlapping (an amount, sizes, a grain shape, lumps, clusters), holders; materials: crystals,
rock-forming minerals, mixtures. LoKI: as many kinds of particles as wanted, in a H2O/D2O solvent.
Start from an example (odin/templates), a model saved by a user (<TWIN_RUN_ROOT>/templates/<instrument>/), or a sample
of the library; build, look at it (cuts, a radiograph, the attenuation of each material), save it in the samples
folder of the proposal (on the sample changer of NICOS: move(sample_holder, '<name>')), and save it as a model.
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
import sys, os, re, glob, datetime, warnings
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
import rock_builder as rb

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
## Start from

An example, one of the models saved by users, or a sample of the library: everything can then be changed. Or start
from scratch.
""")

code(r"""
def template_folders(ins):
    # the examples (in the twin), then the models saved by the users
    return [(os.path.join(os.path.abspath("."), ins, "templates"), "example"), (f"{ROOT}/templates/{ins}", "model")]

def starts(ins):
    out = [("— from scratch —", ("", None))]
    for folder, kind in template_folders(ins):
        for f in sorted(glob.glob(os.path.join(folder, "*.yml"))):
            try:
                t = yaml.safe_load(open(f, encoding="utf-8")) or {}
            except Exception:
                continue
            who = f" (by {t['author']})" if t.get("author") else ""
            out.append((f"{kind}: {t.get('title') or t.get('name')}{who}", (kind, f)))
    data = f"{ROOT}/data/{ins}/{datetime.date.today().year}/{proposal.value.strip()}/raw" if proposal.value.strip() else None
    for n, s in sl.load(ins, data).items():
        if ins == "odin" and rb.recipe_from_spec(s) is None:
            continue                               # thousands of volumes made by a program: not editable here
        out.append((f"{'library' if s['source'] == 'built-in' else 'your sample'}: {s.get('name') or n}", ("sample", n)))
    return out

start = w.Dropdown(layout=w.Layout(width="520px"), description="Start from")
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
""")

code(r"""
def num(d, v, width="104px", dw="44px"):
    return w.FloatText(value=v, description=d, layout=w.Layout(width=width), style={"description_width": dw})

def remover(box, row):
    b = w.Button(description="", icon="trash", tooltip="remove", layout=w.Layout(width="40px"))
    b.on_click(lambda _: (setattr(box, "children", tuple(r for r in box.children if r is not row)), refresh_hosts()))
    return b

# ---------------------------------------------------------------- ODIN: materials
CRYSTALS = {k: v for k, v in sl.ODIN_MATERIALS.items()}
MINERALS = list(rb.ROCK_MINERALS)
PARTS = {**sl.MIX_PARTS, **{m: rb.rock_mineral(m) for m in MINERALS}}       # components of a mixture
NAMED = {}                                       # materials of the sample loaded: {name: NCrystal configuration}
MIX = "mix|"

def mat_options():
    return ([(f"crystal: {k}", f"c|{v}") for k, v in CRYSTALS.items()] +
            [(f"mineral: {m}", f"m|{m}") for m in MINERALS] +
            [(f"this sample: {n}", f"n|{n}") for n in NAMED] + [("Mixture…", MIX)])

class Material:
    # a material: a crystal, a rock-forming mineral, a material of the sample loaded, or a mixture (its components
    # and their volume fractions); a density in % of the compact material (pores: less)
    def __init__(self, value="c|Fe_sg229_Iron-alpha.ncmat"):
        self.pick = w.Dropdown(options=mat_options(), value=value, layout=w.Layout(width="300px"))
        self.dens = w.BoundedFloatText(value=100.0, min=5, max=100, step=1, description="density %",
                                       layout=w.Layout(width="140px"), style={"description_width": "66px"})
        self.mixname = w.Text(placeholder="its name, e.g. wet sand", layout=w.Layout(width="200px"))
        self.parts = w.VBox()
        more = w.Button(description="Add a component", icon="plus", layout=w.Layout(width="auto"))
        more.on_click(lambda _: self.add_part())
        self.mix = w.VBox([w.HBox([w.HTML("<i>Mixture, its name:</i>&nbsp;"), self.mixname]),
                           w.HTML("<i>the volume fraction of each component (they add up to 100 %)</i>"),
                           self.parts, more], layout=w.Layout(margin="2px 0 6px 40px", display="none"))
        self.pick.observe(lambda c: setattr(self.mix.layout, "display", "" if c["new"] == MIX else "none"), "value")
        self.line = w.HBox([self.pick, self.dens])

    def add_part(self, label=None, pct=50.0):
        m = w.Dropdown(options=list(PARTS), value=label or list(PARTS)[0], layout=w.Layout(width="290px"))
        f = w.BoundedFloatText(value=pct, min=0, max=100, step=1, description="%", layout=w.Layout(width="110px"),
                               style={"description_width": "20px"})
        r = w.HBox([m, f])
        r.part, r.pct = m, f
        b = w.Button(description="", icon="trash", layout=w.Layout(width="40px"))
        b.on_click(lambda _: setattr(self.parts, "children", tuple(x for x in self.parts.children if x is not r)))
        r.children += (b,)
        self.parts.children += (r,)

    def get(self, named, k):
        # (the name of the material in the sample, adding its configuration to `named` when needed)
        kind, _, val = self.pick.value.partition("|")
        d = self.dens.value
        if kind == "c":
            return sl.odin_material(val, d)
        if kind == "m":
            n = val if abs(d - 100) < 1e-9 else f"{val} ({d:g} %)"
            named[n] = sl.odin_material(rb.rock_mineral(val), d)
            return n
        if kind == "n":
            n = val if abs(d - 100) < 1e-9 else f"{val} ({d:g} %)"
            named[n] = sl.odin_material(NAMED[val], d)
            return n
        parts = [(x.part.value, x.pct.value) for x in self.parts.children if x.pct.value > 0]
        n = self.mixname.value.strip() or f"mixture {k}"
        tot = sum(p for _, p in parts)
        named[n] = sl.odin_material("phases<" + "&".join(f"{p / tot:.4g}*{PARTS[l]}" for l, p in parts) + ">", d) \
            if parts else "phases<>"
        return n

    def set(self, matname, named):
        cfg = named.get(matname, matname)
        base, dens = sl._split_density(cfg)
        self.dens.value = dens
        if base in CRYSTALS.values():
            self.pick.value = f"c|{base}"; return
        for m in MINERALS:
            if base == rb.rock_mineral(m):
                self.pick.value = f"m|{m}"; return
        mm = re.match(r"^phases<(.*)>$", base)
        inv = {v: k for k, v in PARTS.items()}
        inv.update({"stdlib::" + v: k for k, v in PARTS.items()})
        if mm and all(p.partition("*")[2] in inv for p in mm.group(1).split("&")):
            self.pick.value = MIX
            self.mixname.value = re.sub(r" \(\d+(\.\d+)? %\)$", "", matname)
            self.parts.children = ()
            for p in mm.group(1).split("&"):
                f, _, c = p.partition("*")
                self.add_part(inv[c], round(100 * float(f), 2))
            return
        n = re.sub(r" \(\d+(\.\d+)? %\)$", "", matname)
        NAMED.setdefault(n, base)
        refresh_materials()
        self.pick.value = f"n|{n}"

MATERIALS = []                                   # every Material on the page (their lists follow NAMED)

def material(value="c|Fe_sg229_Iron-alpha.ncmat"):
    m = Material(value)
    MATERIALS.append(m)
    return m

def refresh_materials():
    opts = mat_options()
    for m in MATERIALS:
        v = m.pick.value
        m.pick.options = opts
        m.pick.value = v if v in [o[1] for o in opts] else opts[0][1]

# ---------------------------------------------------------------- ODIN: shapes
SHAPES = list(rb.SHAPES)
SIZE_LABELS = {"block": ("width", "height", "thick"), "cylinder": ("diam.", "height"), "sphere": ("diam.",),
               "ellipsoid": ("x", "y", "z"), "lumpy (pebble, grain)": ("x", "y", "z"),
               "sawn piece (irregular edges)": ("width", "height", "thick")}

class Shape:
    # a shape, its size [mm], its orientation (degrees: about z, then x, then the vertical axis y; a block turns
    # about y only, a cylinder stays vertical, a sawn piece faces the beam) and its lumps
    def __init__(self, shape="block", size=(10.0, 10.0, 4.0), angles=(0.0, 0.0, 0.0), lumps=0.12):
        self.shape = w.Dropdown(options=SHAPES, value=shape, layout=w.Layout(width="190px"))
        self.size = [num("x", float(v)) for v in list(size) + [size[-1]] * (3 - len(size))]
        self.angles = [num(d, float(a), "112px", "52px") for d, a in zip(("turn z°", "turn x°", "turn y°"), angles)]
        self.lumps = w.BoundedFloatText(value=lumps, min=0, max=0.3, step=0.02, description="lumps",
                                        layout=w.Layout(width="112px"), style={"description_width": "44px"})
        self.shape.observe(lambda c: self.show(), "value")
        self.show()

    def show(self):
        s = self.shape.value
        labels = SIZE_LABELS[s]
        for k, f in enumerate(self.size):
            f.layout.display = "" if k < len(labels) else "none"
            if k < len(labels):
                f.description = labels[k]
        for k, f in enumerate(self.angles):
            f.layout.display = "" if (s in ("ellipsoid", "lumpy (pebble, grain)") or (s == "block" and k == 2)) else "none"
        self.lumps.layout.display = "" if s.startswith("lumpy") else "none"

    def widgets(self):
        return [self.shape] + self.size + self.angles + [self.lumps]

    def get(self):
        n = len(SIZE_LABELS[self.shape.value])
        return dict(shape=self.shape.value, size_mm=[f.value for f in self.size[:n]],
                    angles_deg=[f.value for f in self.angles], lumps=self.lumps.value)

    def set(self, d):
        self.shape.value = d["shape"]
        for f, v in zip(self.size, d["size_mm"]):
            f.value = float(v)
        for f, v in zip(self.angles, d.get("angles_deg") or (0, 0, 0)):
            f.value = float(v)
        self.lumps.value = float(d.get("lumps", 0.12 if d["shape"].startswith("lumpy") else 0.0))
        self.show()

def position(c=(0.0, 0.0, 0.0)):
    return [num(d, float(v)) for d, v in zip(("x", "y", "z"), c)]

# ---------------------------------------------------------------- ODIN: the piece
piece_on = w.Checkbox(value=True, description="a piece that holds the rest (a rock, a block of metal...)",
                      layout=w.Layout(width="auto"), indent=False)
piece_mat = material("c|Fe_sg229_Iron-alpha.ncmat")
piece_shape = Shape("block", (10.0, 10.0, 4.0))
piece_pos = position()
piece_box = w.VBox([w.HBox([w.HTML("<b style='display:inline-block;width:80px'>The piece</b>"), piece_mat.line],
                           layout=w.Layout(flex_flow="row wrap")), piece_mat.mix,
                    w.HBox([w.HTML("<span style='display:inline-block;width:80px'></span>")] + piece_shape.widgets(),
                           layout=w.Layout(flex_flow="row wrap")),
                    w.HBox([w.HTML("<span style='display:inline-block;width:80px'>center [mm]</span>")] + piece_pos)])
piece_on.observe(lambda c: (setattr(piece_box.layout, "display", "" if c["new"] else "none"), refresh_hosts()), "value")

# ---------------------------------------------------------------- ODIN: objects placed by hand
objects = w.VBox()
pops = w.VBox()

def host_options(before=None):
    # what can hold an object or grains: the piece, the objects (above this one)
    opts = [("the piece", "piece")] if piece_on.value else []
    for r in objects.children:
        if r is before:
            break
        opts.append((r.oname.value or "(unnamed object)", r.oname.value))
    return opts

def refresh_hosts():
    for r in objects.children:
        opts = [("nothing (it stands alone)", "")] + host_options(r)
        v = r.inside.value
        r.inside.options = opts
        r.inside.value = v if v in [o[1] for o in opts] else ("piece" if piece_on.value else "")
    for r in pops.children:
        opts = host_options() or [("(add a piece or an object first)", "")]
        v = r.inside.value
        r.inside.options = opts
        r.inside.value = v if v in [o[1] for o in opts] else opts[0][1]

def add_object(d=None):
    d = d or dict(name=f"object {len(objects.children) + 1}", shape="sphere", material="Cu_sg225.ncmat",
                  center_mm=[0, 0, 0], size_mm=[2.0], inside="piece")
    oname = w.Text(value=d.get("name", ""), layout=w.Layout(width="150px"))
    mat = material()
    shp = Shape(d["shape"], d["size_mm"], d.get("angles_deg") or (0, 0, 0), d.get("lumps", 0.12))
    pos = position(d.get("center_mm", (0, 0, 0)))
    inside = w.Dropdown(layout=w.Layout(width="190px"), description="in", style={"description_width": "20px"})
    row = w.VBox()
    row.children = [w.HBox([oname, mat.line, inside, remover(objects, row)], layout=w.Layout(flex_flow="row wrap")),
                    mat.mix,
                    w.HBox(shp.widgets(), layout=w.Layout(flex_flow="row wrap", margin="0 0 0 20px")),
                    w.HBox([w.HTML("center [mm]&nbsp;")] + pos, layout=w.Layout(margin="0 0 8px 20px"))]
    row.oname, row.mat, row.shp, row.pos, row.inside = oname, mat, shp, pos, inside
    objects.children += (row,)
    oname.observe(lambda c: refresh_hosts(), "value")
    refresh_hosts()
    want = d.get("inside") or ""
    inside.value = want if want in [o[1] for o in inside.options] else inside.options[0][1]
    return row

# ---------------------------------------------------------------- ODIN: grains placed at random
def add_population(d=None):
    d = d or dict(material="plagioclase (feldspar)", fraction_pct=5.0, size_mm=[0.1, 0.5], grain_shape="irregular",
                  lumps=0.1, clusters=0, spread_mm=0.4, inside="piece")
    mat = material("m|plagioclase (feldspar)")
    how = w.Dropdown(options=[("% of the volume", "fraction"), ("number of grains", "count")],
                     value="count" if d.get("count") else "fraction", layout=w.Layout(width="150px"))
    amount = w.FloatText(value=float(d.get("count") or d.get("fraction_pct", 5.0)), layout=w.Layout(width="80px"))
    smin = num("from", float(d["size_mm"][0]), "112px", "40px")
    smax = num("to", float(d["size_mm"][1]), "100px", "24px")
    gshape = w.Dropdown(options=list(rb.GRAIN_SHAPES), value=d.get("grain_shape", "irregular"),
                        layout=w.Layout(width="120px"))
    lumps = w.BoundedFloatText(value=float(d.get("lumps", 0.0)), min=0, max=0.3, step=0.02, description="lumps",
                               layout=w.Layout(width="112px"), style={"description_width": "44px"})
    clusters = w.BoundedIntText(value=int(d.get("clusters") or 0), min=0, max=100, description="clusters",
                                layout=w.Layout(width="124px"), style={"description_width": "56px"})
    spread = num("spread", float(d.get("spread_mm", 0.4)), "118px", "48px")
    inside = w.Dropdown(layout=w.Layout(width="190px"), description="in", style={"description_width": "20px"})
    row = w.VBox()
    row.children = [w.HBox([w.HTML("<b>Grains of</b>&nbsp;"), mat.line, inside, remover(pops, row)],
                           layout=w.Layout(flex_flow="row wrap")), mat.mix,
                    w.HBox([amount, how, w.HTML("&nbsp;sizes [mm]"), smin, smax, gshape, lumps, clusters, spread],
                           layout=w.Layout(flex_flow="row wrap", margin="0 0 8px 20px"))]
    row.mat, row.how, row.amount, row.smin, row.smax, row.gshape, row.lumps = mat, how, amount, smin, smax, gshape, lumps
    row.clusters, row.spread, row.inside = clusters, spread, inside
    spread.layout.display = "" if clusters.value else "none"
    clusters.observe(lambda c: setattr(spread.layout, "display", "" if c["new"] else "none"), "value")
    pops.children += (row,)
    refresh_hosts()
    inside.value = d.get("inside") if d.get("inside") in [o[1] for o in inside.options] else inside.options[0][1]
    return row

# ---------------------------------------------------------------- ODIN: holders
holders = w.VBox()

def add_holder(d=None):
    d = d or dict(shape="block", material="Al_sg225.ncmat", center_mm=[0.0, -7.5, 0.0], size_mm=[12.0, 5.0, 7.0])
    mat = material()
    shp = w.Dropdown(options=["block", "cylinder"], value=d["shape"], layout=w.Layout(width="100px"))
    size = [num(l, float(v)) for l, v in zip(("width", "height", "thick"), list(d["size_mm"]) + [d["size_mm"][0]])]
    pos = position(d["center_mm"])
    row = w.VBox()
    row.children = [w.HBox([w.HTML("<b style='color:#64748B'>Holder</b>&nbsp;"), mat.line, shp, remover(holders, row)],
                           layout=w.Layout(flex_flow="row wrap")), mat.mix,
                    w.HBox(size + [w.HTML("&nbsp;center [mm]")] + pos,
                           layout=w.Layout(flex_flow="row wrap", margin="0 0 8px 20px"))]

    def show(_=None):
        size[0].description = "diam." if shp.value == "cylinder" else "width"
        size[2].layout.display = "none" if shp.value == "cylinder" else ""
    shp.observe(show, "value"); show()
    row.mat, row.shp, row.size, row.pos = mat, shp, size, pos
    holders.children += (row,)
    return row

seed = w.BoundedIntText(value=7, min=0, max=10**6, description="random seed", style={"description_width": "86px"},
                        layout=w.Layout(width="190px"))

def recipe():
    named = {}
    r = dict(seed=seed.value, piece=None, objects=[], populations=[], holders=[])
    if piece_on.value:
        r["piece"] = dict(material=piece_mat.get(named, 0), center_mm=[f.value for f in piece_pos], **piece_shape.get())
    for k, o in enumerate(objects.children):
        r["objects"].append(dict(name=o.oname.value or f"object {k + 1}", material=o.mat.get(named, f"o{k + 1}"),
                                 center_mm=[f.value for f in o.pos], inside=o.inside.value or None, **o.shp.get()))
    for k, p in enumerate(pops.children):
        d = dict(material=p.mat.get(named, f"g{k + 1}"), size_mm=[p.smin.value, p.smax.value],
                 grain_shape=p.gshape.value, lumps=p.lumps.value, clusters=p.clusters.value,
                 spread_mm=p.spread.value, inside=p.inside.value or "piece")
        d.update({"count": int(p.amount.value)} if p.how.value == "count" else {"fraction_pct": p.amount.value})
        r["populations"].append(d)
    for h in holders.children:
        s = [f.value for f in h.size]
        r["holders"].append(dict(shape=h.shp.value, material=h.mat.get(named, "h"), center_mm=[f.value for f in h.pos],
                                 size_mm=s[:2] if h.shp.value == "cylinder" else s))
    r["materials"] = named
    return r

def load_recipe(r):
    named = dict(r.get("materials") or {})        # (what is not a crystal, a mineral or a mixture of them: NAMED)
    MATERIALS.clear()
    MATERIALS.append(piece_mat)
    seed.value = int(r.get("seed", 7))
    p = r.get("piece")
    piece_on.value = bool(p)
    if p:
        piece_mat.set(p["material"], named)
        piece_shape.set(p)
        for f, v in zip(piece_pos, p.get("center_mm", (0, 0, 0))):
            f.value = float(v)
    objects.children, pops.children, holders.children = (), (), ()
    for o in r.get("objects") or []:
        row = add_object(o)
        row.mat.set(o["material"], named)
    for q in r.get("populations") or []:
        row = add_population(q)
        row.mat.set(q["material"], named)
    for h in r.get("holders") or []:
        row = add_holder(dict(h, size_mm=list(h["size_mm"]) + ([h["size_mm"][0]] if len(h["size_mm"]) == 2 else [])))
        row.mat.set(h["material"], named)
    refresh_hosts()

add_holder()
b_obj = w.Button(description="Add an object", icon="plus", layout=w.Layout(width="auto"))
b_pop = w.Button(description="Add grains", icon="plus", layout=w.Layout(width="auto"))
b_hold = w.Button(description="Add a holder", icon="plus", layout=w.Layout(width="auto"))
b_obj.on_click(lambda _: add_object()); b_pop.on_click(lambda _: add_population()); b_hold.on_click(lambda _: add_holder())
odin_box = w.VBox([
    w.HTML("<p>x is horizontal, y vertical (mm, from the center of the beam), z along the beam; the camera sees "
           "14 mm × 14 mm. Materials: crystals, rock-forming minerals (fine-grained: no Bragg edge), or a mixture of "
           "them (choose <i>Mixture…</i>); the density in % of the compact material (less with pores).</p>"),
    piece_on, piece_box,
    w.HTML("<h4>Objects placed by hand</h4><p>Each one where you put it: in the piece, in another object (an "
           "inclusion in an inclusion), or standing alone. They must not overlap. An ellipsoid or a lumpy grain can "
           "be turned in 3D.</p>"), objects, b_obj,
    w.HTML("<h4>Grains placed at random</h4><p>An amount (a % of the volume of what holds them, or a number of "
           "grains), their sizes (the longest axis), their shape, lumps (0: smooth), and clusters: 0 spreads them "
           "evenly, N gathers them around N points (spread: the size of a cluster). They are placed from the largest "
           "down, never overlapping: if the amount asked does not fit, you are told.</p>"), pops, b_pop,
    w.HTML("<h4>Holder</h4><p>What the sample stands on (an aluminium base by default): it must touch the sample "
           "without overlapping it.</p>"), holders, b_hold, seed])

# ---------------------------------------------------------------- LoKI: kinds of particles in a solvent
loki_items = w.VBox()
MODELS = {"sphere": ("Spheres", (("radius [Å]", 50.0),)),
          "cylinder": ("Cylinders", (("radius [Å]", 20.0), ("length [Å]", 400.0))),
          "core_shell_sphere": ("Core-shell spheres", (("radius [Å]", 50.0), ("shell [Å]", 20.0)))}
PARAMS = {"sphere": ("radius",), "cylinder": ("radius", "length"), "core_shell_sphere": ("radius", "thickness")}

def add_loki(model, particle="silica", values=None, phi=0.5):
    mat = w.Dropdown(options=list(sl.SLD), value=particle, layout=w.Layout(width="170px"))
    pars = [num(d, v if values is None else values[k], "118px", "52px") for k, (d, v) in enumerate(MODELS[model][1])]
    phi_w = w.BoundedFloatText(value=phi, min=0.01, max=10, step=0.1, description="vol. %", layout=w.Layout(width="140px"),
                               style={"description_width": "62px"})
    row = w.HBox()
    row.children = [w.HTML(f"<b style='display:inline-block;width:140px'>{MODELS[model][0]}</b>"), mat] + pars + \
                   [phi_w, remover(loki_items, row)]
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
        if not kind:
            if instr.value == "odin":
                NAMED.clear(); load_recipe(dict(piece=dict(shape="block", material="Fe_sg229_Iron-alpha.ncmat",
                                                         size_mm=[10, 10, 4]), holders=[dict(
                    shape="block", material="Al_sg225.ncmat", center_mm=[0, -7.5, 0], size_mm=[12, 5, 7])]))
            else:
                load_loki(dict(populations=[dict(model="sphere", particle="silica", parameters=dict(radius=50),
                                                 volume_fraction=0.005)]))
            print("A new sample: change it as you like."); return
        if kind == "sample":
            s = sl.load(instr.value, f"{ROOT}/data/{instr.value}/{datetime.date.today().year}/{proposal.value.strip()}/raw")[ref]
            t = dict(title=s.get("name", ref), description=s.get("description", ""), spec=s,
                     recipe=rb.recipe_from_spec(s) if instr.value == "odin" else None)
        else:
            t = yaml.safe_load(open(ref, encoding="utf-8"))
        title.value = t.get("title") or title.value
        description.value = t.get("description") or ""
        if instr.value == "odin":
            NAMED.clear(); load_recipe(t["recipe"])
        else:
            load_loki(t.get("spec") or t)
        print(f"Loaded: {t.get('title') or ref}. Change it, then build it (below).")

b_start.on_click(load_start)
""")

md(r"""
## Build it, look at it, then save it

*Build and show* places everything (a few seconds; up to a minute for thousands of grains) and shows the sample: two
cuts through it, a radiograph (what the camera would see at 3 Å), and the attenuation of each material.
""")

code(r"""
out = w.Output()
BUILT = {}
b_view = w.Button(description="Build and show", icon="eye", button_style="primary", layout=w.Layout(width="auto"))
b_save = w.Button(description="Save it with my proposal", icon="save", button_style="success", layout=w.Layout(width="auto"))
model_name = w.Text(placeholder="e.g. wet_sandstone", description="Model name", style={"description_width": "86px"})
b_model = w.Button(description="Save as a model", icon="bookmark", layout=w.Layout(width="auto"))

def build():
    # the sample from the page (built again only if the page changed)
    if instr.value == "loki":
        return dict(name=title.value or name.value, description=description.value, **loki_spec()), [], []
    r = recipe()
    if BUILT.get("recipe") != r:
        print("Placing everything...")
        spec, report, problems = rb.build_sample(r)
        BUILT.update(recipe=r, spec=spec, report=report, problems=problems)
    spec = dict(name=title.value or name.value, description=description.value, **BUILT["spec"], recipe=r)
    return spec, BUILT["report"], BUILT["problems"]

def radiograph(spec, ax):
    import odin_hybrid as oh
    T = oh.volumes_transmission(sl.odin_volumes(spec), 0.0, 0.0)
    g = np.linspace(-7e-3, 7e-3, 351)
    X, Y = np.meshgrid(g, g)
    t = T(X.ravel(), Y.ravel(), np.full(X.size, 3.0)).reshape(X.shape)
    im = ax.imshow(t, origin="lower", extent=(-7, 7, -7, 7), cmap="gray", vmin=max(0.0, float(np.percentile(t, 1)) - 0.02),
                   vmax=1.0)
    ax.set(xlabel="x [mm]", ylabel="y [mm]", title="Radiograph at 3 Å (no noise, no blur)")
    plt.colorbar(im, ax=ax, label="transmission T", shrink=0.85)

def sigma_table(spec):
    import odin_hybrid as oh
    named = spec.get("materials") or {}
    rows = []
    for m in dict.fromkeys(v["material"] for v in spec["volumes"]):
        s = oh.sigma_tot(named.get(m, m), np.array([1.8, 3.0])) / 100
        rows.append(f"<tr><td>{sl.odin_material_label(spec, m) if m not in named else m}</td>"
                    f"<td style='text-align:right'>{s[0]:.3f}</td><td style='text-align:right'>{s[1]:.3f}</td></tr>")
    return ("<table><tr><th>material</th><th>Σ at 1.8 Å [cm⁻¹]</th><th>Σ at 3 Å [cm⁻¹]</th></tr>" + "".join(rows) +
            "</table><p><i>T = exp(−Σ L): 1 mm of a material of Σ = 1 cm⁻¹ lets 90 % through.</i></p>")

def view(_):
    out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    with out:
        spec, report, problems = build()
        errors = sl.validate(instr.value, spec) if instr.value == "loki" or len(spec["volumes"]) < 3000 else []
        if problems or errors:
            print("To fix:", *(problems + errors), sep="\n  ")
            if errors:
                return
        print(sl.describe(instr.value, spec))
        for l in report:
            print("  placed:", l)
        if instr.value == "odin":
            sl.draw("odin", spec, hidden=["nothing"], fig=plt.figure(figsize=(11, 5.6)))
            sl.show()
            fig, ax = plt.subplots(figsize=(6.2, 5))
            radiograph(spec, ax)
            sl.show(fig)
            display(w.HTML(sigma_table(spec)))
        else:
            q, I, truth = sl.loki_cross_section(spec)
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.loglog(q, I, "k-")
            ax.set(xlim=(3e-3, 0.6), ylim=(max(I.min() / 2, 1e-4), I.max() * 2), xlabel="Q [1/Å]",
                   ylabel="dΣ/dΩ [1/cm]", title="what your sample scatters (exact, no instrument)")
            ax.grid(alpha=0.3, which="both"); sl.show(fig)

def save(_):
    out.clear_output(wait=True)
    with out:
        if not proposal.value.strip().isdigit():
            print("Give your proposal number (the one entered in NICOS, Experiment panel)."); return
        spec, report, problems = build()
        if problems:
            print("To fix first:", *problems, sep="\n  "); return
        folder = f"{ROOT}/data/{instr.value}/{datetime.date.today().year}/{proposal.value.strip()}/raw"
        try:
            path = sl.save(instr.value, spec, folder, name.value.strip())
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
            t["recipe"] = recipe()
        else:
            t["spec"] = loki_spec()
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(t, f, sort_keys=False, allow_unicode=True, width=120)
        refresh_starts()
        print(f"Saved as a model: {t['title']} ({path}). Anyone can now start from it (Start from, at the top).")

b_view.on_click(view); b_save.on_click(save); b_model.on_click(save_model)
display(w.HBox([b_view, b_save]), w.HBox([model_name, b_model]), out)
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, os.path.join(HERE, "Sample_builder.ipynb"))
print("written Sample_builder.ipynb")
