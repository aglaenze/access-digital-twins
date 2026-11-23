"""The server side of the sample builder page of the app (builder/index.html, served by container/twin_app.py at
/twin/builder): what the page asks, as plain functions of JSON-able values (tested without a browser).

The page edits a samplecraft recipe (the format of scene_builder.Editor: materials, components, a tree of bodies,
fills) of the SAMPLE only; its holder is chosen apart (HOLDERS: a pin, a base plate, a quartz cell, a vanadium can,
tensile grips), placed from the bounds of the sample, and joined to it when the sample is built or saved (bodies with
holder: true, as before), while the sample file also keeps the choice (spec["holder"] = {type, ...}) so that the
builder finds the holder apart again.

Parts of a sample that an exercise hides (secret fills or bodies: the hydrogen-rich clasts of the meteorite) are
SEALED: the page gets a placeholder {"sealed": <id>, "name": ...}; the part itself stays on the server
(TWIN_RUN_ROOT/builder/sealed/<id>.json) and comes back when the sample is saved. The views (3D, radiograph,
thumbnails) are made without them.

Physics as in the rest of the twin: the scene is built by samplecraft (exact path lengths), the radiograph is
odin_hybrid.scene_transmission, Σ is NCrystal (samplecraft.sigma). The 3D meshes are only a view (marching cubes on a
grid, scene_builder.surfaces).
"""
import base64
import copy
import datetime
import glob
import hashlib
import io
import json
import os
import re
import sys
import threading

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "odin")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import matplotlib  # noqa: E402
matplotlib.use("Agg")

FIELD_MM = 14.0                 # the field of view of ODIN's cameras (14 mm square around the beam axis)
LOCK = threading.Lock()         # one build at a time (memory)
THUMB_LOCK = threading.Lock()   # the thumbnails: one at a time, apart (they never wait for the views, nor these for them)
_CACHE = {}                     # {key: built scene}, a few only


def run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin")).replace(os.sep, "/")


def data_folder(instrument, proposal):
    p = str(proposal or "").strip()
    return f"{run_root()}/data/{instrument}/{datetime.date.today().year}/{p}/raw" if p.isdigit() else None


def _key(*obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:20]


# --------------------------------------------------------------------------- catalogues
SHAPES = [   # the shapes offered as icons: (type, label, [(key, label, n values, default, min, max)])
    ("box", "Block", [("size", "size x, y, z", 3, [10.0, 10.0, 4.0], 0.05, 30.0)]),
    ("cylinder", "Cylinder", [("diameter", "diameter", 1, 4.0, 0.05, 30.0), ("height", "height (y)", 1, 8.0, 0.05, 30.0)]),
    ("sphere", "Sphere", [("diameter", "diameter", 1, 2.0, 0.02, 30.0)]),
    ("ellipsoid", "Ellipsoid", [("size", "axes x, y, z", 3, [3.0, 2.0, 1.5], 0.02, 30.0)]),
    ("cone", "Cone", [("diameter_bottom", "bottom diameter", 1, 4.0, 0.0, 30.0),
                      ("diameter_top", "top diameter", 1, 1.0, 0.0, 30.0), ("height", "height (y)", 1, 6.0, 0.05, 30.0)]),
    ("torus", "Ring", [("major_diameter", "ring diameter", 1, 6.0, 0.1, 30.0),
                       ("minor_diameter", "tube diameter", 1, 1.5, 0.05, 15.0)]),
    ("superellipsoid", "Rounded block", [("size", "size x, y, z", 3, [6.0, 6.0, 3.0], 0.05, 30.0),
                                         ("exponent", "squareness (2: ellipsoid)", 1, 4.0, 2.0, 12.0)]),
    ("blob", "Pebble / grain", [("size", "axes x, y, z", 3, [3.0, 2.0, 1.5], 0.02, 30.0),
                                ("wobble", "lumps (0: smooth)", 1, 0.12, 0.0, 0.4), ("seed", "lump pattern", 1, 1, 1, 99)]),
    ("sawn_piece", "Sawn piece of rock", [("size", "width, height, thickness", 3, [8.0, 12.0, 2.0], 0.2, 30.0),
                                           ("seed", "irregularities", 1, 11, 1, 99)]),
]

CATALOGUE = {   # materials offered as cards: group -> [(label, material spec)]
    "Metals and crystals": None,          # filled from sample_library.ODIN_MATERIALS
    "Rock-forming minerals": [
        ("plagioclase (feldspar)", {"minerals": {"plag": 100}}), ("orthopyroxene", {"minerals": {"opx": 100}}),
        ("clinopyroxene", {"minerals": {"cpx": 100}}), ("olivine", {"minerals": {"ol": 100}}),
        ("quartz", {"minerals": {"qz": 100}}), ("calcite", {"minerals": {"cc": 100}}),
        ("magnetite", {"minerals": {"mag": 100}}), ("hematite", {"minerals": {"hem": 100}}),
        ("ilmenite", {"minerals": {"ilm": 100}}), ("chlorapatite", {"minerals": {"ap": 100}}),
        ("pyrite", {"minerals": {"py": 100}}), ("goethite (holds H)", {"minerals": {"gt": 100}}),
        ("serpentine (holds H)", {"minerals": {"srp": 100}}), ("gypsum (holds H)", {"minerals": {"gyp": 100}}),
        ("kaolinite (holds H)", {"minerals": {"kln": 100}}),
        ("basalt (plagioclase + pyroxene)", {"minerals": {"plag": 55, "cpx": 40, "mag": 5}}),
        ("sandstone (quartz + feldspar)", {"minerals": {"qz": 80, "afs": 20}}),
    ],
    "Liquids and others": [
        ("water", {"ncrystal": "stdlib::LiquidWaterH2O_T293.6K.ncmat"}),
        ("heavy water", {"ncrystal": "stdlib::LiquidHeavyWaterD2O_T293.6K.ncmat"}),
        ("fused silica (glass)", {"formula": "SiO2", "density": 2.20}),
        ("polyethylene (plastic)", {"formula": "C2H4", "density": 0.94}),
        ("void (a pore, a hole)", {"ncrystal": "void.ncmat"}),
    ],
}
_MINERAL_FORMULA = {"plagioclase (feldspar)": "(Na,Ca)(Al,Si)₄O₈", "orthopyroxene": "(Mg,Fe)₂Si₂O₆",
                    "clinopyroxene": "(Ca,Mg,Fe)₂Si₂O₆", "olivine": "(Mg,Fe)₂SiO₄", "quartz": "SiO₂", "calcite": "CaCO₃",
                    "magnetite": "Fe₃O₄", "hematite": "Fe₂O₃", "ilmenite": "FeTiO₃", "chlorapatite": "Ca₅(PO₄)₃Cl",
                    "pyrite": "FeS₂", "goethite (holds H)": "FeO(OH)", "serpentine (holds H)": "Mg₃Si₂O₅(OH)₄",
                    "gypsum (holds H)": "CaSO₄·2H₂O", "kaolinite (holds H)": "Al₂Si₂O₅(OH)₄", "water": "H₂O",
                    "heavy water": "D₂O", "fused silica (glass)": "SiO₂", "polyethylene (plastic)": "(C₂H₄)ₙ"}


def material_catalogue():
    import sample_library as sl
    out = {}
    for g, items in CATALOGUE.items():
        if items is None:
            items = [(k, {"ncrystal": v}) for k, v in sl.ODIN_MATERIALS.items() if v != "void.ncmat"]
        out[g] = [dict(label=k, spec=v, formula=_MINERAL_FORMULA.get(k, "")) for k, v in items]
    return out


HOLDER_MATERIALS = {"aluminium": {"ncrystal": "Al_sg225.ncmat"}, "steel": {"ncrystal": "Fe_sg229_Iron-alpha.ncmat"},
                    "titanium": {"ncrystal": "Ti_sg194.ncmat"}, "vanadium": {"ncrystal": "V_sg229.ncmat"},
                    "fused silica": {"formula": "SiO2", "density": 2.20}, "copper": {"ncrystal": "Cu_sg225.ncmat"}}

HOLDERS = {   # type -> what the page shows; params: (key, label, default, min, max) [mm]
    "none": dict(title="No holder", text="Nothing but the sample (it floats on the axis: only for a quick test).",
                 material=None, params=[]),
    "pin": dict(title="Pin", text="The sample glued on a thin pin, on the rotation axis: the least material near the "
                "beam. For small solid pieces (rocks, meteorites, metal bits).", material="aluminium",
                params=[("height", "pin height", 6.0, 1.0, 30.0), ("diameter", "pin diameter", 3.0, 0.5, 10.0)]),
    "base": dict(title="Base plate", text="The sample standing on a plate. For blocks and parts that stand on their "
                 "own.", material="aluminium",
                 params=[("thickness", "plate thickness", 3.0, 0.5, 15.0), ("margin", "plate wider by", 1.0, 0.0, 10.0)]),
    "cell": dict(title="Quartz cell", text="A closed cell of glass around the sample: for liquids, powders, "
                 "or wet samples. Its walls are in the beam (take the open beam with the empty cell).",
                 material="fused silica",
                 params=[("wall", "wall thickness", 1.25, 0.2, 3.0), ("gap", "room around the sample", 0.3, 0.0, 5.0)]),
    "can": dict(title="Vanadium can", text="A thin closed can around the sample: vanadium lets almost all neutrons "
                "through and shows no Bragg edge. For powders.", material="vanadium",
                params=[("wall", "wall thickness", 0.15, 0.05, 2.0), ("gap", "room around the sample", 0.3, 0.0, 5.0)]),
    "grips": dict(title="Tensile grips", text="Two grips holding the sample at its two ends (x), as in a load frame. "
                  "For tensile specimens.", material="steel",
                  params=[("length", "grip length (x)", 6.0, 1.0, 20.0), ("margin", "grips larger by", 2.0, 0.0, 10.0)]),
}


def holder_catalogue():
    return {k: dict(title=v["title"], text=v["text"], material=v["material"],
                    params=[dict(key=p[0], label=p[1], default=p[2], min=p[3], max=p[4]) for p in v["params"]])
            for k, v in HOLDERS.items()}


def holder_bodies(holder, lo, hi):
    """The bodies (recipe format, holder: true) and the materials of a holder, placed from the bounds lo, hi [mm] of
    the sample. holder: {"type", "material", <params>} or {"type": "custom", "bodies", "materials"}."""
    holder = holder or {"type": "none"}
    t = holder.get("type", "none")
    if t == "custom":
        return copy.deepcopy(holder.get("bodies") or []), copy.deepcopy(holder.get("materials") or {})
    if t not in HOLDERS or t == "none":
        return [], {}
    h = HOLDERS[t]
    P = {p[0]: float(holder.get(p[0], p[2])) for p in h["params"]}
    mname = holder.get("material") or h["material"]
    mat_key = f"holder: {mname}"
    mats = {mat_key: copy.deepcopy(HOLDER_MATERIALS.get(mname, HOLDER_MATERIALS["aluminium"]))}
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c, s = 0.5 * (lo + hi), hi - lo
    r = lambda v: [round(float(x), 4) for x in v]
    if t == "pin":
        b = [dict(name="holder: pin", material=mat_key, holder=True,
                  shape=dict(type="cylinder", diameter=P["diameter"], height=P["height"],
                             position=r([c[0], lo[1] - P["height"] / 2, c[2]])))]
    elif t == "base":
        size = [s[0] + 2 * P["margin"], P["thickness"], s[2] + 2 * P["margin"]]
        b = [dict(name="holder: base plate", material=mat_key, holder=True,
                  shape=dict(type="box", size=r(size), position=r([c[0], lo[1] - P["thickness"] / 2, c[2]])))]
    elif t == "cell":
        inner = s + 2 * P["gap"]
        outer = inner + 2 * P["wall"]
        b = [dict(name="holder: quartz cell", material=mat_key, holder=True,
                  shape=dict(type="difference", of=[dict(type="box", size=r(outer), position=r(c)),
                                                     dict(type="box", size=r(inner), position=r(c))]))]
    elif t == "can":
        d_in = float(np.hypot(s[0], s[2])) + 2 * P["gap"]
        h_in = s[1] + 2 * P["gap"]
        b = [dict(name="holder: vanadium can", material=mat_key, holder=True,
                  shape=dict(type="difference", of=[
                      dict(type="cylinder", diameter=round(d_in + 2 * P["wall"], 4), height=round(h_in + 2 * P["wall"], 4),
                           position=r(c)),
                      dict(type="cylinder", diameter=round(d_in, 4), height=round(h_in, 4), position=r(c))]))]
    elif t == "grips":
        size = [P["length"], s[1] + 2 * P["margin"], s[2] + 2 * P["margin"]]
        b = [dict(name=f"holder: grip {side}", material=mat_key, holder=True,
                  shape=dict(type="box", size=r(size), position=r([x, c[1], c[2]])))
             for side, x in (("left", lo[0] - P["length"] / 2), ("right", hi[0] + P["length"] / 2))]
    return b, mats


# --------------------------------------------------------------------------- sealing the hidden parts
def _sealed_dir():
    d = os.path.join(run_root(), "builder", "sealed")
    os.makedirs(d, exist_ok=True)
    return d


def seal(recipe):
    """The recipe for the page: secret fills and bodies replaced by placeholders, kept on the server."""
    r = copy.deepcopy(recipe)
    comps = r.get("components") or {}
    used_by_open = set()

    def uses(x):
        out = set()
        if isinstance(x, dict):
            if "use" in x:
                out.add(x["use"])
            for v in x.values():
                out |= uses(v)
        elif isinstance(x, list):
            for v in x:
                out |= uses(v)
        return out

    def store(kind, item):
        names = uses(item)
        blob = dict(kind=kind, item=item, components={n: comps[n] for n in names if n in comps})
        sid = _key(blob)
        with open(os.path.join(_sealed_dir(), sid + ".json"), "w", encoding="utf-8") as f:
            json.dump(blob, f)
        return sid, names

    hidden = set()

    def go(bodies):
        out = []
        for b in bodies:
            if b.get("secret"):
                sid, names = store("body", b)
                hidden.update(names)
                out.append({"sealed": sid, "name": "hidden part (to be found by measuring)"})
                continue
            fills = []
            for f in b.get("fill") or []:
                if f.get("secret"):
                    sid, names = store("fill", f)
                    hidden.update(names)
                    fills.append({"sealed": sid, "name": "hidden parts (to be found by measuring)"})
                else:
                    fills.append(f)
            if b.get("fill"):
                b["fill"] = fills
            if b.get("children"):
                b["children"] = go(b["children"])
            out.append(b)
        return out

    r["bodies"] = go(r.get("bodies") or [])
    rest = copy.deepcopy(r)
    rest["components"] = {}
    used_by_open = uses(rest)
    for n in list(comps):                     # components only the hidden parts use: hidden too
        if n in hidden and n not in used_by_open:
            comps.pop(n)
    return r


def _load_sealed(sid):
    if not re.fullmatch(r"[0-9a-f]{20}", str(sid)):
        raise ValueError("bad sealed part")
    with open(os.path.join(_sealed_dir(), sid + ".json"), encoding="utf-8") as f:
        return json.load(f)


def unseal(recipe, drop=False):
    """The recipe with its sealed parts back (drop=True: without them, for the views)."""
    r = copy.deepcopy(recipe)
    comps = r.setdefault("components", {})

    def go(bodies):
        out = []
        for b in bodies:
            if "sealed" in b:
                if not drop:
                    blob = _load_sealed(b["sealed"])
                    comps.update({k: v for k, v in blob["components"].items() if k not in comps})
                    out.append(blob["item"])
                continue
            fills = []
            for f in b.get("fill") or []:
                if "sealed" in f:
                    if not drop:
                        blob = _load_sealed(f["sealed"])
                        comps.update({k: v for k, v in blob["components"].items() if k not in comps})
                        fills.append(blob["item"])
                else:
                    fills.append(f)
            if "fill" in b:
                b["fill"] = fills
                if not fills:
                    b.pop("fill")
            if b.get("children"):
                b["children"] = go(b["children"])
            out.append(b)
        return out

    r["bodies"] = go(r.get("bodies") or [])
    return r


def has_sealed(recipe):
    return '"sealed"' in json.dumps(recipe)


# --------------------------------------------------------------------------- starting points
LEVELS = {1: "Simple shapes", 2: "Several parts, or grains", 3: "Natural samples"}
NATURAL_SHAPES = {"sawn_piece", "blob", "natural", "pebble", "voxels", "mesh"}
COMBINED_SHAPES = {"union", "difference", "intersection"}


def level(recipe):
    """How complex a starting point is, for the order of the gallery: 1 simple shapes (at most 3 bodies, no grains),
    2 several parts or one population of grains (combined shapes, profiles in many slices), 3 natural samples
    (natural shapes, voxels of a tomogram, several populations of grains, components)."""
    n, fills, types = 0, 0, set()

    def go(bodies):
        nonlocal n, fills
        for b in bodies:
            if b.get("holder"):
                continue
            n += 1
            fills += len(b.get("fill") or [])
            types.add((b.get("shape") or {}).get("type") or ("use" if b.get("use") else "voxels"))
            go(b.get("children", []))
    go(recipe.get("bodies", []))
    if types & NATURAL_SHAPES or "use" in types or fills > 1 or recipe.get("components"):
        return 3
    if fills == 1 or n > 3 or types & COMBINED_SHAPES:
        return 2
    return 1


def starts(instrument, proposal):
    """The starting points of the gallery: from scratch, the samples of the proposal, then the examples, the models
    saved by users and the samples of the library, from the simplest to the most complex (level, LEVELS)."""
    import sample_library as sl
    import scene_builder as sb
    out = [dict(kind="scratch", ref="", title="From scratch", what="an empty block to shape as you like")]
    mine, others = [], []
    for folder, kind in ((os.path.join(HERE, instrument, "templates"), "example"),
                         (f"{run_root()}/templates/{instrument}", "model")):
        for f in sorted(glob.glob(os.path.join(folder, "*.yml"))):
            try:
                t = yaml.safe_load(open(f, encoding="utf-8")) or {}
            except Exception:
                continue
            if "bodies" not in (t.get("recipe") or {}):
                continue
            others.append(dict(kind=kind, ref=os.path.basename(f)[:-4], title=t.get("title") or t.get("name"),
                               what=(f"by {t['author']}" if t.get("author") else kind), level=_level_of(t["recipe"])))
    for n, s in sl.load(instrument, data_folder(instrument, proposal)).items():
        if s.get("source") == "student":
            mine.append(dict(kind="sample", ref=n, title=s.get("name") or n, what="your sample (this proposal)"))
    for n, s in sl.load(instrument).items():
        others.append(dict(kind="sample", ref=n, title=s.get("name") or n, what="sample of the library",
                           level=_level_of(sb.recipe_of(s))))
    others.sort(key=lambda s: (s["level"], str(s["title"]).lower()))
    return out + mine + others


def _level_of(recipe):
    try:
        return level(recipe)
    except Exception:                                   # noqa: BLE001
        return 2


def _template_file(instrument, kind, ref):
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", ref or ""):
        raise ValueError("bad name")
    folder = os.path.join(HERE, instrument, "templates") if kind == "example" else f"{run_root()}/templates/{instrument}"
    return os.path.join(folder, ref + ".yml")


def _split_holder(recipe, spec_holder=None):
    """(sample recipe, holder) of a recipe whose holder bodies are in it (holder: true)."""
    r = copy.deepcopy(recipe)
    hb = [b for b in r.get("bodies", []) if b.get("holder")]
    r["bodies"] = [b for b in r.get("bodies", []) if not b.get("holder")]
    if spec_holder and spec_holder.get("type") in HOLDERS:
        hm = {k: v for k, v in r.get("materials", {}).items() if k.startswith("holder: ")}
        for k in hm:                                  # the materials of the holder made by the builder: made again
            r["materials"].pop(k, None)
        return r, copy.deepcopy(spec_holder)
    if not hb:
        return r, {"type": "none"}
    guess = _guess_holder(r, hb, recipe.get("materials") or {})
    if guess:
        rest = json.dumps([r["bodies"], r.get("components") or {}, {k: v for k, v in r["materials"].items()
                                                                     if k != hb[0].get("material")}])
        if json.dumps(hb[0].get("material")) not in rest:     # the holder's material, used by nothing else
            r["materials"].pop(hb[0].get("material"), None)
        return r, guess
    used = {b.get("material") for b in hb}
    return r, {"type": "custom", "bodies": hb, "materials": {k: r["materials"][k] for k in used if k in r.get("materials", {})},
               "title": "the holder of this sample (as it came)"}


def _guess_holder(sample_recipe, hb, materials):
    """A holder of an older sample (one body: a vertical cylinder or a block under the sample) as a holder of the
    catalogue (pin or base plate) with the same sizes and material; None if it is something else."""
    if len(hb) != 1 or "children" in hb[0]:
        return None
    b, sh = hb[0], hb[0].get("shape") or {}
    spec = materials.get(b.get("material"))
    if isinstance(spec, str):
        spec = {"ncrystal": spec}
    core = lambda m: {k: v for k, v in (m or {}).items() if k not in ("source", "note")}
    mat = next((k for k, v in HOLDER_MATERIALS.items() if v == core(spec)), None)
    if mat is None or sh.get("rotation"):
        return None
    try:
        lo, hi = _sample_bounds(unseal(sample_recipe, drop=True))
    except Exception:                                   # noqa: BLE001
        return None
    pos = sh.get("position", [0, 0, 0])
    if sh.get("type") == "cylinder":
        top = pos[1] + sh["height"] / 2
        if abs(top - lo[1]) < 0.6:
            return dict(type="pin", material=mat, height=float(sh["height"]), diameter=float(sh["diameter"]))
    if sh.get("type") == "box":
        top = pos[1] + sh["size"][1] / 2
        if abs(top - lo[1]) < 0.6:
            return dict(type="base", material=mat, thickness=float(sh["size"][1]),
                        margin=max(0.0, float(sh["size"][0] - (hi[0] - lo[0])) / 2))
    return None


def load(instrument, kind, ref, proposal=""):
    """What the page needs to start from a starting point: {recipe (sealed), holder, title, description, name}."""
    import sample_library as sl
    import scene_builder as sb
    if kind == "scratch":
        r = sb.new_recipe()
        r["bodies"] = [b for b in r["bodies"] if not b.get("holder")]
        r["materials"].pop("aluminium", None)
        return dict(recipe=r, holder=dict(type="pin", material="aluminium"), title="", description="", name="")
    if kind in ("example", "model"):
        t = yaml.safe_load(open(_template_file(instrument, kind, ref), encoding="utf-8"))
        r, h = _split_holder(t["recipe"], t.get("holder"))
        return dict(recipe=seal(r), holder=h, title=t.get("title") or "", description=t.get("description") or "",
                    name="")
    if kind == "sample":
        lib = sl.load(instrument, data_folder(instrument, proposal))
        if ref not in lib:
            raise ValueError(f"no sample {ref}")
        s = lib[ref]
        r, h = _split_holder(sb.recipe_of(s), s.get("holder"))
        mine = s.get("source") == "student"
        return dict(recipe=seal(r), holder=h, title=s.get("name", ref), description=s.get("description", ""),
                    name=ref if mine else "")
    raise ValueError(f"unknown kind {kind}")


# --------------------------------------------------------------------------- building
_BOUNDS = {}


def _sample_bounds(recipe_view):
    """Bounds [mm] of the sample alone (its top-level bodies), from a quick build without fills (cached)."""
    k = _key(recipe_view)
    if k not in _BOUNDS:
        if len(_BOUNDS) > 64:
            _BOUNDS.clear()
        _BOUNDS[k] = _sample_bounds_now(recipe_view)
    lo, hi = _BOUNDS[k]
    return lo.copy(), hi.copy()


def _sample_bounds_now(recipe_view):
    import samplecraft as sc
    r = copy.deepcopy(recipe_view)
    for b in r.get("bodies", []):
        b.pop("fill", None)
    scene = sc.Scene.from_dict(r)
    if not scene.bodies:
        return np.zeros(3), np.zeros(3)
    lo = np.min([b.shape.bounds()[0] for b in scene.bodies], axis=0)
    hi = np.max([b.shape.bounds()[1] for b in scene.bodies], axis=0)
    return lo, hi


def compose(recipe, holder, view=True, grains=True):
    """The whole recipe (sample + holder) to build: view=True without the sealed parts; grains=False without the
    fills (a quick view of a large sample)."""
    r = unseal(recipe, drop=view)
    if not grains:
        def nofill(bs):
            for b in bs:
                b.pop("fill", None)
                nofill(b.get("children", []))
        nofill(r.get("bodies", []))
    lo, hi = _sample_bounds(unseal(recipe, drop=True))
    hb, hm = holder_bodies(holder, lo, hi)
    r.setdefault("materials", {}).update(hm)
    r["bodies"] = list(r.get("bodies", [])) + hb
    return r


def built(recipe, holder, view=True, grains=True):
    """(scene, report lines, problems) of the composed recipe, cached."""
    import scene_builder as sb
    full = compose(recipe, holder, view, grains)
    k = _key(full)
    if k not in _CACHE:
        with LOCK:
            if k not in _CACHE:
                if len(_CACHE) > 4:
                    _CACHE.pop(next(iter(_CACHE)))
                _CACHE[k] = sb.build(full) + (full, k)
    scene, lines, problems, full, k = _CACHE[k]
    return scene, lines, problems, full, k


def blocking(problems):
    """The problems that forbid saving: overlaps, bodies out of their parent (scene.check). Grains that did not all
    find room are only reported (the samples of the library have some: a placement at random)."""
    return [p for p in problems if "found room" not in p]


def _colors(scene, names):
    import sample_library as sl
    return sl._rock_colors(dict(materials=dict(scene.cfg())), names)


def _b64(a, dt):
    return base64.b64encode(np.ascontiguousarray(a, dtype=dt).tobytes()).decode()


_SURF = {}


def _surfaces(scene, n, key=None):
    """scene_builder.surfaces, the secret bodies left out (a scene of the views has none: sealed parts dropped);
    cached by the key of the built scene (the same view asked again: the step changed, the page reloaded)."""
    import scene_builder as sb
    if key is None:
        return sb.surfaces(scene, n)
    if (key, n) not in _SURF:
        if len(_SURF) > 8:
            _SURF.pop(next(iter(_SURF)))
        _SURF[(key, n)] = sb.surfaces(scene, n)
    return _SURF[(key, n)]


def preview(recipe, holder, n=56, grains=True):
    """The 3D view of the sample and its holder: meshes per material (vertices as float32, faces as uint32, base64),
    the bounds of every body of the recipe (to highlight one), problems, the bounds of the sample."""
    import sample_library as sl
    import time
    t0 = time.time()
    scene, lines, problems, full, k = built(recipe, holder, view=True, grains=grains)
    surf = _surfaces(scene, n, k)
    names = [s[0] for s in surf if not s[3]]
    colors = _colors(scene, names)
    label = lambda m: sl._rock_label(dict(materials=dict(scene.cfg())), m) if m else m
    meshes = [dict(material=m, label=label(m), holder=bool(h), share=float(sh),
                   color="#C9CFD8" if h else colors.get(m, "#8C7B6B"),
                   vertices=_b64(v, np.float32), faces=_b64(f, np.uint32), n_vertices=int(len(v)), n_faces=int(len(f)))
              for m, v, f, h, sh in surf]
    # bounds of the bodies of the recipe (path -> bounds), found by name along the tree of the built scene
    bounds = {}

    def go(rb, sb_, path):
        by_name = {}
        for x in sb_:
            by_name.setdefault(x.name, x)
        for i, b in enumerate(rb):
            x = by_name.get(b.get("name"))
            if x is None:
                continue
            lo, hi = x.shape.bounds()
            bounds[".".join(map(str, path + (i,)))] = [list(map(float, lo)), list(map(float, hi))]
            go(b.get("children", []), getattr(x, "children", []), path + (i,))

    go([b for b in full["bodies"] if not b.get("holder")], [b for b in scene.bodies if not getattr(b, "holder", False)], ())
    lo, hi = _sample_bounds(unseal(recipe, drop=True))
    return dict(key=k, meshes=meshes, bounds=bounds, problems=blocking(problems) if grains else [], lines=lines,
                sample_bounds=[lo.tolist(), hi.tolist()], n_bodies=sum(1 for _ in scene.walk()), grains=grains,
                n_fills=json.dumps(unseal(recipe, drop=True).get("bodies")).count('"fill"'),
                seconds=round(time.time() - t0, 1))


class _Mem:                       # a sample built here, for the hybrid model of the twin (odin_hybrid)
    def __init__(self, scene, key):
        self.scene, self.key = scene, f"mem:{key}"


def _transmission(recipe, holder, lam, n=241, half=FIELD_MM / 2):
    import odin_hybrid as oh
    scene, _, _, _, k = built(recipe, holder, view=True)
    T = oh.scene_transmission(_Mem(scene, k), 0.0, 0.0)
    g = np.linspace(-half * 1e-3, half * 1e-3, n)
    X, Y = np.meshgrid(g, g)
    return T(X.ravel(), Y.ravel(), np.full(X.size, float(lam))).reshape(X.shape), g * 1e3


def radiograph(recipe, holder, lam=3.0):
    """The radiograph (beam's eye view) at the wavelength lam: transmission, no noise, no blur, over the field of
    view; PNG (base64) and numbers."""
    import matplotlib.pyplot as plt
    t, g = _transmission(recipe, holder, lam)
    fig, ax = plt.subplots(figsize=(4.6, 4.0), dpi=110)
    im = ax.imshow(t, origin="lower", extent=(g[0], g[-1], g[0], g[-1]), cmap="gray",
                   vmin=max(0.0, float(np.percentile(t, 1)) - 0.02), vmax=1.0)
    ax.set(xlabel="x [mm]", ylabel="y [mm]")
    ax.set_title(f"What the camera sees at {lam:.1f} Å (no noise, no blur)", fontsize=9)
    fig.colorbar(im, ax=ax, label="transmission T", shrink=0.85)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return dict(png=base64.b64encode(buf.getvalue()).decode(), t_min=float(t.min()), t_median=float(np.median(t)))


def sigmas(recipe, holder, lams=(1.8, 3.0)):
    """Σ [1/cm] of the materials of the sample and its holder at a few wavelengths, and how each was obtained."""
    import samplecraft as sc
    import sample_library as sl
    full = compose(recipe, holder, view=True)
    cfg, notes = sc.resolve_materials(full.get("materials") or {})
    colors = sl._rock_colors(dict(materials=cfg), list(cfg))
    return [dict(material=k, label=sl._rock_label(dict(materials=cfg), k), color=colors.get(k, "#8C7B6B"),
                 sigma=[round(float(x), 4) for x in sc.sigma(c, list(lams))], how=notes[k]) for k, c in cfg.items()]


_CAT_SIG = {}


def catalogue_sigmas(lam=3.0):
    """Σ at lam of every material card of the catalogue (cached)."""
    import samplecraft as sc
    out = {}
    for g, items in material_catalogue().items():
        for it in items:
            k = (_key(it["spec"]), round(float(lam), 2))
            if k not in _CAT_SIG:
                try:
                    cfg, _ = sc.resolve_materials({"m": it["spec"]})
                    _CAT_SIG[k] = round(float(sc.sigma(cfg["m"], [lam])[0]), 3)
                except Exception:
                    _CAT_SIG[k] = None
            out[it["label"]] = _CAT_SIG[k]
    return out


def check(recipe, holder):
    """The traffic lights of step 3: [(status green/amber/red, title, text)]."""
    items = []
    scene, lines, problems, full, k = built(recipe, holder, view=True)
    lo, hi = _sample_bounds(unseal(recipe, drop=True))
    h = FIELD_MM / 2
    inside = (lo[0] >= -h) and (hi[0] <= h) and (lo[1] >= -h) and (hi[1] <= h)
    seen = (hi[0] > -h) and (lo[0] < h) and (hi[1] > -h) and (lo[1] < h)
    size = f"{hi[0] - lo[0]:.1f} × {hi[1] - lo[1]:.1f} × {hi[2] - lo[2]:.1f} mm (x × y × z)"
    if inside:
        rmax = float(np.max(np.hypot(np.r_[lo[0], hi[0]][:, None], np.r_[lo[2], hi[2]][None, :])))
        if rmax > h:
            items.append(("amber", "Field of view (14 mm)", f"The sample ({size}) is in the field of view, but turned "
                          f"for a tomography its corners go {rmax:.1f} mm from the axis, out of the field."))
        else:
            items.append(("green", "Field of view (14 mm)", f"The whole sample ({size}) is in the field of view, at "
                          "every angle of a tomography."))
    elif seen:
        items.append(("amber", "Field of view (14 mm)", f"Part of the sample ({size}) is out of the 14 mm field of "
                      "view: only the part inside will be measured (or move it with the stage)."))
    else:
        items.append(("red", "Field of view (14 mm)", f"The sample ({size}) is out of the field of view: move it "
                      "closer to the beam axis (x = 0, y = 0)."))
    try:
        t, g = _transmission(recipe, holder, 3.0, n=161)
        X, Y = np.meshgrid(g, g)
        m = (X >= lo[0]) & (X <= hi[0]) & (Y >= lo[1]) & (Y <= hi[1]) & (t < 0.9999)
        if m.any():
            tmin, tmed = float(t[m].min()), float(np.median(t[m]))
            if tmin < 0.01:
                items.append(("red", "Transmission at 3 Å", f"Almost no neutron goes through the thickest part "
                              f"(T = {tmin:.3f}): thinner, or a less absorbing material."))
            elif tmin < 0.1:
                items.append(("amber", "Transmission at 3 Å", f"The thickest part lets {100 * tmin:.0f} % through: "
                              "long counts there (noisy); thinner if you can."))
            elif tmed > 0.97:
                items.append(("amber", "Transmission at 3 Å", f"Almost transparent (median T = {tmed:.3f}): little "
                              "contrast; thicker, or longer counts."))
            else:
                items.append(("green", "Transmission at 3 Å", f"From T = {tmin:.2f} (thickest part) to "
                              f"{float(t[m].max()):.2f}, median {tmed:.2f}: good contrast."))
    except Exception as e:
        items.append(("amber", "Transmission at 3 Å", f"Not computed: {e}"))
    if blocking(problems):
        items.append(("red", "No overlap", "To fix: " + "; ".join(blocking(problems)[:6])))
    else:
        items.append(("green", "No overlap", "Every part is inside its parent, no two neighbors overlap."))
    short = [p for p in problems if "found room" in p]       # (the views: hidden parts left out, so not reported)
    if short:
        items.append(("amber", "Grains placed at random", "Not all found room: " + "; ".join(short[:4]) +
                      " (fewer or smaller grains, if it matters)."))
    hb = [b for b in scene.bodies if getattr(b, "holder", False)]
    t_ = (holder or {}).get("type", "none")
    if not hb:
        items.append(("green" if t_ == "none" else "amber", "Holder",
                      "No holder." + ("" if t_ == "none" else " (none could be placed)")))
    else:
        blo = np.min([b.shape.bounds()[0] for b in hb], axis=0)
        bhi = np.max([b.shape.bounds()[1] for b in hb], axis=0)
        in_fov = (bhi[0] > -h) and (blo[0] < h) and (bhi[1] > -h) and (blo[1] < h)
        if t_ in ("cell", "can"):
            items.append(("amber", "Holder in the beam", "The walls of the holder are in the beam (it is made for "
                          "that): measure the open beam with the empty holder, or see its walls in the images."))
        elif in_fov:
            part = max(0.0, min(bhi[1], h) - max(blo[1], -h))
            items.append(("amber", "Holder in the beam", f"{part:.1f} mm of the holder are in the field of view: it "
                          "shows in the images (an edge of the image), usually harmless."))
        else:
            items.append(("green", "Holder out of the beam", "The holder stays out of the field of view."))
    return [dict(status=s, title=a, text=b) for s, a, b in items]


# --------------------------------------------------------------------------- thumbnails
SHIPPED_THUMBS = os.path.join(HERE, "builder", "thumbs")


def thumb_key(instrument, kind, ref, proposal="", size=150):
    """The name of the thumbnail of a starting point: from the content of its file (not its date, which changes at
    each copy of the code), and from the proposal only for a sample of the student."""
    import hashlib
    stamp, prop = "", ""
    try:
        if kind in ("example", "model"):
            fn = _template_file(instrument, kind, ref)
        elif kind == "sample":
            import sample_library as sl
            s = sl.load(instrument, data_folder(instrument, proposal)).get(ref) or {}
            fn = s.get("file") or ""
            prop = proposal if s.get("source") == "student" else ""
        else:
            fn = ""
        if fn and os.path.exists(fn):
            with open(fn, "rb") as fh:
                stamp = hashlib.sha1(fh.read()).hexdigest()
    except (OSError, ValueError):
        pass
    return _key(instrument, kind, ref, prop, stamp, size)


def make_shipped_thumbs(instrument="odin"):
    """The thumbnails of the examples and of the samples of the library, made in advance (builder/thumbs/, shipped
    with the code): the gallery opens at once, even on a new computer (a rock takes 5 to 15 s to build)."""
    os.makedirs(SHIPPED_THUMBS, exist_ok=True)
    keep = set()
    for s in starts(instrument, ""):
        if s["kind"] in ("example", "sample"):
            png = thumb(instrument, s["kind"], s["ref"])
            name = thumb_key(instrument, s["kind"], s["ref"]) + ".png"
            with open(os.path.join(SHIPPED_THUMBS, name), "wb") as fh:
                fh.write(png)
            keep.add(name)
    for g in glob.glob(os.path.join(SHIPPED_THUMBS, "*.png")):       # thumbnails of files that changed: removed
        if os.path.basename(g) not in keep:
            os.remove(g)
    return sorted(keep)


def thumb(instrument, kind, ref, proposal="", size=150):
    """A small picture of a starting point (PNG bytes): the cut through its middle, seen by the beam, colored by
    material (hidden parts left out). Cached on disk."""
    folder = os.path.join(run_root(), "builder", "thumbs")
    os.makedirs(folder, exist_ok=True)
    f = os.path.join(folder, thumb_key(instrument, kind, ref, proposal, size) + ".png")
    shipped = os.path.join(SHIPPED_THUMBS, os.path.basename(f))
    for g in (shipped, f):               # made in advance for the examples and the library (python builder_api.py
        if os.path.exists(g):            # --thumbs), else made once here
            return open(g, "rb").read()
    from PIL import Image
    from matplotlib.colors import to_rgb
    import scene_builder as sb
    d = load(instrument, kind, ref, proposal)
    with THUMB_LOCK:
        scene = sb.build(compose(d["recipe"], d["holder"], view=True), check=False)[0]
    lo = np.min([b.shape.bounds()[0] for b in scene.bodies], axis=0)
    hi = np.max([b.shape.bounds()[1] for b in scene.bodies], axis=0)
    c, half = 0.5 * (lo + hi), 0.55 * float(max(hi[0] - lo[0], hi[1] - lo[1]))
    g = np.linspace(-half, half, size)
    X, Y = np.meshgrid(c[0] + g, c[1] - g)
    zc = 0.5 * (lo[2] + hi[2])
    hold = [b for b in scene.bodies if getattr(b, "holder", False)]
    sample = [b for b in scene.bodies if not getattr(b, "holder", False)]
    P = np.c_[X.ravel(), Y.ravel(), np.full(X.size, zc)]
    img = np.full((X.size, 3), 251, np.uint8)
    for part, is_h in ((hold, True), (sample, False)):
        if not part:
            continue
        m = type(scene)(part, scene.materials).material_at(P)
        names = [x for x in dict.fromkeys(m) if x is not None]
        cols = _colors(scene, names)
        for nm in names:
            rgb = np.array(to_rgb("#C9CFD8" if is_h else cols.get(nm, "#8C7B6B"))) * 255
            img[m == nm] = rgb.astype(np.uint8)
    im = Image.fromarray(img.reshape(size, size, 3))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    with open(f, "wb") as fh:
        fh.write(buf.getvalue())
    return buf.getvalue()


# --------------------------------------------------------------------------- saving
def save(instrument, proposal, name, title, description, recipe, holder):
    """Saves the sample (sample + holder, the hidden parts back) with the proposal: NICOS finds it on the sample
    changer (move(sample_holder, name)). Returns {path, nicos}."""
    import sample_library as sl
    import scene_builder as sb
    folder = data_folder(instrument, proposal)
    if not folder:
        raise ValueError("Give your proposal number (the one applied in NICOS, Experiment panel).")
    scene, lines, problems, full, k = built(recipe, holder, view=False)
    if blocking(problems):
        raise ValueError("To fix first: " + "; ".join(blocking(problems)[:6]))
    spec = sb.sample_spec(full, scene, name, title, description)
    if has_sealed(recipe):
        spec["hidden"] = sorted(set(spec.get("hidden", [])) | {"inclusions"})
    spec["holder"] = copy.deepcopy(holder) if (holder or {}).get("type") in HOLDERS else {"type": "custom"}
    path = sl.save(instrument, spec, folder, (name or "").strip())
    return dict(path=path, nicos=f"move(sample_holder, '{name.strip()}')   then   sample_info()")


def save_model(instrument, proposal, model, title, description, recipe, holder):
    """Saves the recipe (sample + holder, the hidden parts left out) as a model anyone can start from."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", model or ""):
        raise ValueError("Model name: lowercase letters, digits and _, starting with a letter (e.g. wet_sandstone).")
    folder = f"{run_root()}/templates/{instrument}"
    path = os.path.join(folder, model + ".yml")
    author = f"proposal {proposal}" if str(proposal).strip() else "anonymous"
    if os.path.exists(path) and (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("author") != author:
        raise ValueError(f"A model {model} already exists (made by someone else): choose another name.")
    full = compose(recipe, holder, view=True)
    t = dict(name=model, instrument=instrument, title=title or model, description=description or "", author=author,
             saved=datetime.datetime.now().isoformat(timespec="minutes"), recipe=full,
             holder=copy.deepcopy(holder) if (holder or {}).get("type") in HOLDERS else {"type": "custom"})
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(t, f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)
    return dict(path=path.replace(os.sep, "/"))


def to_yaml(obj):
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=110, default_flow_style=None)


def from_yaml(text):
    d = yaml.safe_load(text)
    if not isinstance(d, (dict, list)):
        raise ValueError("YAML of a mapping or a list expected")
    return d


def info(instrument="odin", proposal="", start=""):
    """Everything the page needs at its opening."""
    return dict(instrument=instrument, proposal=proposal, field_mm=FIELD_MM, shapes=[
        dict(type=t, label=l, fields=[dict(key=a, label=b, n=c, default=d, min=e, max=f_) for a, b, c, d, e, f_ in fs])
        for t, l, fs in SHAPES], holders=holder_catalogue(), materials=material_catalogue(),
        starts=starts(instrument, proposal), start=start)


if __name__ == "__main__":
    import sys
    if "--thumbs" in sys.argv:          # python builder_api.py --thumbs: the thumbnails shipped with the code (again
        for name in make_shipped_thumbs("odin"):     # after a change of an example or of a sample of the library)
            print(name)
