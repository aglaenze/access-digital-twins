"""The ODIN part of the sample builder (Sample_builder.ipynb): a samplecraft recipe edited with widgets.

A recipe (samplecraft scene description) holds materials, components and a tree of bodies; each body has a shape
(any samplecraft shape, its position and 3D rotation), a material, children, and fills (populations of grains,
Voronoi polycrystals, pores). The editor shows the tree, a form for the body selected, the materials, the
components, and the whole recipe as YAML (to edit anything the forms do not show). Build: the scene is generated
(seeded), checked, drawn, its radiograph computed. Everything a scientist needs to state in a paper is in the recipe
(sources, assumptions, seed) and is saved with the sample.
"""
import copy
import os

import numpy as np
import yaml

import ipywidgets as w

SHAPE_FIELDS = {        # parameters of each shape in the forms: (key, label, number of values, default)
    "box": [("size", "size x, y, z [mm]", 3, [10.0, 10.0, 4.0])],
    "sphere": [("diameter", "diameter [mm]", 1, 2.0)],
    "ellipsoid": [("size", "axes x, y, z [mm]", 3, [2.0, 1.0, 1.0])],
    "cylinder": [("diameter", "diameter [mm]", 1, 2.0), ("height", "height (along y) [mm]", 1, 5.0)],
    "cone": [("diameter_bottom", "bottom diameter [mm]", 1, 3.0), ("diameter_top", "top diameter [mm]", 1, 1.0),
             ("height", "height (along y) [mm]", 1, 4.0)],
    "torus": [("major_diameter", "ring diameter [mm]", 1, 6.0), ("minor_diameter", "tube diameter [mm]", 1, 1.5)],
    "superellipsoid": [("size", "size x, y, z [mm]", 3, [4.0, 4.0, 2.0]), ("exponent", "exponent (2: ellipsoid)", 1, 4.0)],
    "blob": [("size", "axes x, y, z [mm]", 3, [2.0, 1.5, 1.0]), ("wobble", "lumps (0: smooth)", 1, 0.12),
             ("seed", "lump pattern (seed)", 1, 1)],
    "sawn_piece": [("size", "width, height, thickness [mm]", 3, [8.0, 12.0, 2.0]), ("seed", "irregularities (seed)", 1, 11)],
    "prism": [("thickness", "thickness (along z) [mm]", 1, 2.0)],
    "mesh": [("file", "file (STL, OBJ, OFF, PLY)", 0, ""), ("unit_mm", "unit of the file [mm]", 1, 1.0)],
}
SHAPE_NAMES = {"box": "block", "sphere": "sphere", "ellipsoid": "ellipsoid", "cylinder": "cylinder (axis y)",
               "cone": "cone (axis y)", "torus": "torus (axis y)", "superellipsoid": "rounded block (superellipsoid)",
               "blob": "lumpy grain / pebble", "sawn_piece": "sawn piece of rock", "prism": "prism (polygon in x-y)",
               "mesh": "mesh from a file (STL...)", "union": "union of shapes", "intersection": "intersection of shapes",
               "difference": "shape with cuts (difference)"}
MATERIAL_KINDS = {"ncrystal": "crystal (NCrystal)", "minerals": "minerals (by volume)", "formula": "formula and density",
                  "mix": "mixture of materials of the sample", "calibrate": "calibrated on a measured Σ"}


def _num(desc, v, width="96px", dw="0px"):
    return w.FloatText(value=float(v), description=desc, layout=w.Layout(width=width), style={"description_width": dw})


def new_recipe():
    return dict(samplecraft=1, name="", description="", seed=7,
                provenance=dict(sources=[], assumptions=[]),
                materials={"steel": {"ncrystal": "Fe_sg229_Iron-alpha.ncmat", "source": "NCrystal library"},
                           "aluminium": {"ncrystal": "Al_sg225.ncmat"}},
                components={},
                bodies=[dict(name="the sample", material="steel", shape={"type": "box", "size": [10.0, 10.0, 4.0]}),
                        dict(name="holder", material="aluminium", holder=True,
                             shape={"type": "box", "size": [12.0, 3.0, 6.0], "position": [0.0, -6.5, 0.0]})])


def recipe_of(spec):
    """The recipe of a sample: its own (scene samples keep it), else its volumes turned into a scene."""
    import sample_library as sl
    if sl.is_scene(spec):
        sc = spec["scene"]
        return copy.deepcopy(sc.get("recipe") or {k: v for k, v in sc.items() if k != "recipe"})
    return sl.scene_from_volumes(spec)


class Editor:
    """Widgets editing a recipe (self.recipe, a dict)."""

    def __init__(self, recipe=None, files_dir=None):
        self.recipe = recipe or new_recipe()
        self.files_dir = files_dir                    # where imported files (meshes, voxels) are kept
        self.sel = (0,)                               # path of the body selected (indices in bodies / children)
        self.tree = w.Select(rows=12, layout=w.Layout(width="420px"))
        self.tree.observe(self._on_select, "value")
        bt = lambda d, icon, f: (lambda b: (b.on_click(lambda _: self._do(f)), b)[1])(
            w.Button(description=d, icon=icon, layout=w.Layout(width="auto")))
        self.tree_buttons = w.VBox([bt("Add inside", "plus", self.add_child), bt("Add beside", "plus", self.add_sibling),
                                    bt("Duplicate", "copy", self.duplicate), bt("Up", "arrow-up", lambda: self.move(-1)),
                                    bt("Down", "arrow-down", lambda: self.move(1)), bt("Remove", "trash", self.remove),
                                    bt("Make a component of it", "cube", self.componentize)])
        self.form = w.VBox()
        self.fills = w.VBox()
        self.mats = w.VBox()
        self.comps = w.VBox()
        self.msg = w.HTML()
        self.yaml_text = w.Textarea(layout=w.Layout(width="100%", height="420px"))
        b_yaml = w.Button(description="Apply this YAML", icon="check", layout=w.Layout(width="auto"))
        b_yaml.on_click(lambda _: self.apply_yaml())
        self.tabs = w.Tab([w.VBox([w.HBox([self.tree, self.tree_buttons]), self.form, self.fills]),
                           self.mats, self.comps,
                           w.VBox([w.HTML("The whole recipe (samplecraft scene, YAML). Anything can be changed here: "
                                          "every shape, rotation, material, fill, component, the sources and the "
                                          "assumptions. <i>Apply</i> checks it and updates the forms."),
                                   self.yaml_text, b_yaml])])
        for i, t in enumerate(["Bodies", "Materials", "Components", "Recipe (YAML)"]):
            self.tabs.set_title(i, t)
        self.tabs.observe(lambda c: self._sync_yaml() if c["new"] == 3 else None, "selected_index")
        self.widget = w.VBox([self.tabs, self.msg])
        self.refresh()

    # ------------------------------------------------------------------ tree
    def _walk(self, bodies=None, path=()):
        for i, b in enumerate(self.recipe["bodies"] if bodies is None else bodies):
            p = path + (i,)
            yield p, b
            yield from self._walk(b.get("children", []), p)

    def body(self, path=None):
        path = path or self.sel
        b = self.recipe["bodies"][path[0]]
        for i in path[1:]:
            b = b["children"][i]
        return b

    def _siblings(self, path):
        if len(path) == 1:
            return self.recipe["bodies"]
        return self.body(path[:-1]).setdefault("children", [])

    def _label(self, b):
        what = f"use {b['use']}" if "use" in b else SHAPE_NAMES.get(b.get("shape", {}).get("type"), "?")
        tags = "".join(t for t, k in ((" [holder]", "holder"), (" [secret]", "secret")) if b.get(k))
        fill = f" + {len(b['fill'])} fill" if b.get("fill") else ""
        return f"{b.get('name') or '(unnamed)'}: {what}, {b.get('material', '')}{tags}{fill}"

    def refresh(self):
        opts = [("    " * (len(p) - 1) + ("└ " if len(p) > 1 else "") + self._label(b), p) for p, b in self._walk()]
        self.tree.unobserve(self._on_select, "value")
        self.tree.options = opts
        if self.sel not in [o[1] for o in opts]:
            self.sel = opts[0][1] if opts else None
        if self.sel is not None:
            self.tree.value = self.sel
        self.tree.observe(self._on_select, "value")
        self._form()
        self._materials()
        self._components()

    def _on_select(self, c):
        if c["new"] is not None:
            self.sel = c["new"]
            self._form()

    def _do(self, f):
        try:
            f()
            self.msg.value = ""
        except Exception as e:
            self.msg.value = f"<span style='color:#B91C1C'>{e}</span>"
        self.refresh()

    def add_child(self):
        b = self.body()
        mat = next(iter(self.recipe["materials"]))
        b.setdefault("children", []).append(dict(name="new part", material=mat,
                                                 shape={"type": "sphere", "diameter": 1.0,
                                                        "position": list(b.get("shape", {}).get("position", [0, 0, 0]))}))
        self.sel = self.sel + (len(b["children"]) - 1,)

    def add_sibling(self):
        sib = self._siblings(self.sel)
        mat = next(iter(self.recipe["materials"]))
        sib.append(dict(name="new body", material=mat, shape={"type": "box", "size": [2.0, 2.0, 2.0]}))
        self.sel = self.sel[:-1] + (len(sib) - 1,)

    def duplicate(self):
        sib = self._siblings(self.sel)
        b = copy.deepcopy(self.body())
        b["name"] = (b.get("name") or "body") + " (copy)"
        sib.insert(self.sel[-1] + 1, b)
        self.sel = self.sel[:-1] + (self.sel[-1] + 1,)

    def move(self, step):
        sib = self._siblings(self.sel)
        i, j = self.sel[-1], self.sel[-1] + step
        if 0 <= j < len(sib):
            sib[i], sib[j] = sib[j], sib[i]
            self.sel = self.sel[:-1] + (j,)

    def remove(self):
        sib = self._siblings(self.sel)
        if len(self.sel) == 1 and len(sib) == 1:
            raise ValueError("a sample needs at least one body")
        sib.pop(self.sel[-1])
        self.sel = self.sel[:-1] + (max(0, self.sel[-1] - 1),) if len(sib) else self.sel[:-1]

    def componentize(self):
        b = self.body()
        if "use" in b:
            raise ValueError("this body already uses a component")
        name = b.get("name") or "component"
        comp = {k: copy.deepcopy(v) for k, v in b.items() if k not in ("name", "secret", "holder")}
        pos = comp.get("shape", {}).get("position")
        if pos:                                          # the component centered on its own origin
            comp = _shifted(comp, [-x for x in pos])
        self.recipe.setdefault("components", {})[name] = comp
        keep = {k: b[k] for k in ("name", "secret") if k in b}
        b.clear()
        b.update(keep, use=name, position=pos or [0.0, 0.0, 0.0], scale=1.0)

    # ------------------------------------------------------------------ the form of a body
    def _form(self):
        if self.sel is None:
            self.form.children = (); self.fills.children = (); return
        b = self.body()
        rows = []
        name = w.Text(value=b.get("name", ""), description="name", layout=w.Layout(width="300px"))
        name.observe(lambda c: (b.__setitem__("name", c["new"]), self._relabel()), "value")
        rows.append(name)
        flags = []
        for k, lab in (("holder", "holder (what the sample stands on)"), ("secret", "secret (hidden in an exercise)")):
            cb = w.Checkbox(value=bool(b.get(k)), description=lab, indent=False, layout=w.Layout(width="auto"))
            cb.observe(lambda c, k=k: (b.__setitem__(k, True) if c["new"] else b.pop(k, None), self._relabel()), "value")
            flags.append(cb)
        rows.append(w.HBox(flags))
        if "use" in b:
            comp = w.Dropdown(options=list(self.recipe.get("components", {})), value=b["use"], description="component")
            comp.observe(lambda c: b.__setitem__("use", c["new"]), "value")
            sc_ = _num("scale", b.get("scale", 1.0), "140px", "40px")
            sc_.observe(lambda c: b.__setitem__("scale", c["new"]), "value")
            rows += [w.HBox([comp, sc_]), self._pose_widgets(b)]
        else:
            rows.append(self._material_dropdown(b))
            rows.append(self._shape_widgets(b.setdefault("shape", {"type": "box", "size": [1.0, 1.0, 1.0]})))
        self.form.children = rows
        self._fill_widgets(b)

    def _relabel(self):
        self.tree.unobserve(self._on_select, "value")
        self.tree.options = [("    " * (len(p) - 1) + ("└ " if len(p) > 1 else "") + self._label(b), p)
                             for p, b in self._walk()]
        self.tree.value = self.sel
        self.tree.observe(self._on_select, "value")

    def _material_dropdown(self, d, key="material", desc="material"):
        opts = list(self.recipe["materials"])
        if d.get(key) not in opts and d.get(key):
            opts.append(d[key])
        dd = w.Dropdown(options=opts, value=d.get(key) or opts[0], description=desc, layout=w.Layout(width="360px"))
        d.setdefault(key, dd.value)
        dd.observe(lambda c: (d.__setitem__(key, c["new"]), self._relabel()), "value")
        return dd

    def _pose_widgets(self, d):
        pos = list(d.get("position", [0.0, 0.0, 0.0]))
        rot = d.get("rotation") or {}
        eul = list(rot.get("euler_deg", [0.0, 0.0, 0.0])) if "matrix" not in rot else None
        P = [_num(lab, v, "120px", "22px") for lab, v in zip(("x", "y", "z"), pos)]
        out = [w.HTML("position [mm]&nbsp;")] + P

        def setp(_):
            d["position"] = [f.value for f in P]
        for f in P:
            f.observe(setp, "value")
        if eul is not None:
            E = [_num(lab, v, "136px", "40px") for lab, v in zip(("z°", "x°", "y°"), eul)]

            def sete(_):
                if any(f.value for f in E):
                    d["rotation"] = {"euler_deg": [f.value for f in E]}
                else:
                    d.pop("rotation", None)
            for f in E:
                f.observe(sete, "value")
            out += [w.HTML("&nbsp;turned about z, then x, then y&nbsp;")] + E
        else:
            out.append(w.HTML("&nbsp;(rotation given as a matrix: see the YAML)"))
        return w.HBox(out, layout=w.Layout(flex_flow="row wrap"))

    def _shape_widgets(self, sh):
        kinds = list(SHAPE_NAMES)
        typ = w.Dropdown(options=[(SHAPE_NAMES[k], k) for k in kinds], value=sh.get("type", "box"), description="shape",
                         layout=w.Layout(width="360px"))
        box = w.VBox()

        def build(_=None):
            t = typ.value
            if t != sh.get("type"):                     # a new type: its default parameters, the pose kept
                keep = {k: sh[k] for k in ("position", "rotation") if k in sh}
                sh.clear(); sh.update(type=t, **keep)
                for k, _, n, dflt in SHAPE_FIELDS.get(t, []):
                    sh[k] = copy.deepcopy(dflt)
                if t == "prism":
                    sh["polygon"] = [[-2.0, -2.0], [2.0, -2.0], [2.0, 2.0], [-2.0, 2.0]]
                if t in ("union", "intersection", "difference"):
                    sh["of"] = [{"type": "box", "size": [4.0, 4.0, 2.0]}, {"type": "cylinder", "diameter": 1.0,
                                                                         "height": 3.0, "rotation": {"euler_deg": [0, 90, 0]}}]
                self._relabel()
            rows = []
            for k, lab, n, dflt in SHAPE_FIELDS.get(t, []):
                if n == 0:
                    f = w.Text(value=str(sh.get(k, "")), description=lab, layout=w.Layout(width="520px"),
                               style={"description_width": "180px"})
                    f.observe(lambda c, k=k: sh.__setitem__(k, c["new"]), "value")
                    rows.append(f)
                    continue
                v = sh.get(k, dflt)
                vals = list(v) if n > 1 else [v]
                F = [_num("", x, "96px") for x in vals]

                def setv(_, k=k, F=F, n=n):
                    sh[k] = [f.value for f in F] if n > 1 else (int(F[0].value) if k == "seed" else F[0].value)
                for f in F:
                    f.observe(setv, "value")
                rows.append(w.HBox([w.HTML(f"<span style='display:inline-block;width:190px'>{lab}</span>")] + F))
            if t == "prism":
                pl = w.Textarea(value="\n".join(f"{x:g}, {y:g}" for x, y in sh["polygon"]),
                                description="vertices x, y [mm]", layout=w.Layout(width="360px", height="110px"),
                                style={"description_width": "120px"})
                pl.observe(lambda c: sh.__setitem__("polygon", [[float(a) for a in l.split(",")]
                                                                 for l in c["new"].splitlines() if l.strip()]), "value")
                rows.append(pl)
            if t in ("union", "intersection", "difference"):
                rows.append(w.HTML("The shapes combined are edited in the <b>Recipe (YAML)</b> tab (key <code>of</code> "
                                   "of this body's shape): any shapes, each with its position and rotation; a "
                                   "difference is the first one minus the others."))
            if t == "mesh" and self.files_dir:
                up = w.FileUpload(accept=".stl,.obj,.off,.ply", multiple=False, description="Upload a mesh")

                def got(c):
                    for f in (c["new"] or []):
                        os.makedirs(self.files_dir, exist_ok=True)
                        path = os.path.join(self.files_dir, f["name"])
                        with open(path, "wb") as fh:
                            fh.write(bytes(f["content"]))
                        sh["file"] = path
                        build()
                up.observe(got, "value")
                rows.append(up)
            rows.append(self._pose_widgets(sh))
            box.children = rows
        typ.observe(build, "value")
        build()
        return w.VBox([typ, box])

    # ------------------------------------------------------------------ fills
    def _fill_widgets(self, b):
        fills = b.setdefault("fill", []) if "use" not in b else []
        rows = [w.HTML("<b>Fill</b>: grains placed at random inside this body (none overlapping, largest first), a "
                       "Voronoi polycrystal, or pores from a Gaussian random field.")]
        for i, f in enumerate(fills):
            rows.append(self._one_fill(b, f, i))
        add = []
        for lab, mk in (("Add grains", lambda: dict(material=next(iter(self.recipe["materials"])), fraction=0.05,
                                                     size_mm=[0.1, 0.5], grain={"type": "blob", "wobble": 0.1})),
                        ("Add copies of a component", lambda: dict(use=next(iter(self.recipe.get("components") or {"?": 0})),
                                                                   count=10, scale=[0.8, 1.2])),
                        ("Add a Voronoi polycrystal", lambda: dict(voronoi=dict(count=50, phases={next(iter(self.recipe["materials"])): 1.0}))),
                        ("Add pores", lambda: dict(pores=dict(porosity=0.02, correlation_mm=0.1, voxel_mm=0.025,
                                                               material="void")))):
            bt = w.Button(description=lab, icon="plus", layout=w.Layout(width="auto"))
            bt.on_click(lambda _, mk=mk: (fills.append(mk()), self._ensure_void(), self._fill_widgets(b), self._relabel()))
            add.append(bt)
        if "use" not in b:
            rows.append(w.HBox(add, layout=w.Layout(flex_flow="row wrap")))
        if not b.get("fill"):
            b.pop("fill", None)
        self.fills.children = rows

    def _ensure_void(self):
        self.recipe["materials"].setdefault("void", {"ncrystal": "void.ncmat"})

    def _one_fill(self, b, f, i):
        rm = w.Button(description="", icon="trash", layout=w.Layout(width="40px"))
        rm.on_click(lambda _: (b["fill"].pop(i), self._fill_widgets(b), self._relabel()))
        if "voronoi" in f:
            v = f["voronoi"]
            n = w.BoundedIntText(value=int(v.get("count", 50)), min=2, max=100000, description="grains",
                                 layout=w.Layout(width="170px"))
            n.observe(lambda c: v.__setitem__("count", int(c["new"])), "value")
            ph = w.Text(value=", ".join(f"{k}: {x:g}" for k, x in v.get("phases", {}).items()),
                        description="phases (material: fraction)", layout=w.Layout(width="520px"),
                        style={"description_width": "190px"})

            def setph(c):
                try:
                    v["phases"] = {k.strip(): float(x) for k, x in (p.split(":") for p in c["new"].split(",") if p.strip())}
                except ValueError:
                    pass
            ph.observe(setph, "value")
            return w.HBox([w.HTML("<b>Voronoi</b>&nbsp;"), n, ph, rm], layout=w.Layout(flex_flow="row wrap"))
        if "pores" in f:
            p = f["pores"]
            F = [(k, _num(lab, p.get(k, d), "190px", "110px")) for k, lab, d in
                 (("porosity", "porosity (0-1)", 0.02), ("correlation_mm", "correlation [mm]", 0.1),
                  ("voxel_mm", "voxel [mm]", 0.025))]
            for k, f_ in F:
                f_.observe(lambda c, k=k: p.__setitem__(k, c["new"]), "value")
            return w.HBox([w.HTML("<b>Pores</b>&nbsp;")] + [f_ for _, f_ in F] + [self._material_dropdown(p), rm],
                          layout=w.Layout(flex_flow="row wrap"))
        # grains (a material or a component)
        head = []
        if "use" in f:
            dd = w.Dropdown(options=list(self.recipe.get("components") or {}), value=f["use"] if f["use"] in
                            (self.recipe.get("components") or {}) else None, description="copies of")
            dd.observe(lambda c: f.__setitem__("use", c["new"]), "value")
            head.append(dd)
        else:
            head.append(self._material_dropdown(f, desc="grains of"))
        how = w.Dropdown(options=[("% of the volume", "fraction"), ("number", "count")],
                         value="count" if "count" in f else "fraction", layout=w.Layout(width="150px"))
        amt = _num("", 100 * f["fraction"] if "fraction" in f else f.get("count", 10), "90px")

        def setamt(_=None):
            f.pop("fraction", None); f.pop("count", None)
            if how.value == "count":
                f["count"] = int(amt.value)
            else:
                f["fraction"] = amt.value / 100
        how.observe(setamt, "value"); amt.observe(setamt, "value")
        key = "scale" if "use" in f else "size_mm"
        lohi = f.get(key) or [0.1, 0.5]
        if "size" in f and "lognormal" in f["size"]:
            sz = w.HTML(f"&nbsp;sizes: log-normal (see YAML)")
        else:
            a_, b_ = _num("", lohi[0], "80px"), _num("", lohi[1], "80px")
            a_.observe(lambda c: f.__setitem__(key, [a_.value, b_.value]), "value")
            b_.observe(lambda c: f.__setitem__(key, [a_.value, b_.value]), "value")
            sz = w.HBox([w.HTML("&nbsp;scale" if key == "scale" else "&nbsp;longest axis [mm]&nbsp;"), a_, w.HTML("to"), b_])
        rows = [w.HBox(head + [amt, how, sz, rm], layout=w.Layout(flex_flow="row wrap"))]
        if "use" not in f:
            g = f.setdefault("grain", {"type": "blob", "wobble": 0.0})
            gt = w.Dropdown(options=["blob", "ellipsoid", "box", "superellipsoid", "sphere"], value=g.get("type", "blob"),
                            description="grain", layout=w.Layout(width="220px"))
            gt.observe(lambda c: g.__setitem__("type", c["new"]), "value")
            wb = _num("lumps", g.get("wobble", 0.0), "140px", "44px")
            wb.observe(lambda c: g.__setitem__("wobble", c["new"]), "value")
            asp = f.get("aspect", [[0.45, 0.9], [0.5, 0.95]])
            A = [_num("", x, "70px") for x in (asp[0][0], asp[0][1], asp[1][0], asp[1][1])]

            def seta(_):
                f["aspect"] = [[A[0].value, A[1].value], [A[2].value, A[3].value]]
            for x in A:
                x.observe(seta, "value")
            rows.append(w.HBox([gt, wb, w.HTML("&nbsp;other axes / longest: ")] + A[:2] + [w.HTML("and")] + A[2:],
                               layout=w.Layout(flex_flow="row wrap", margin="0 0 0 24px")))
        cl = f.get("clusters") or {}
        nc = w.BoundedIntText(value=int(cl.get("count", 0)), min=0, max=1000, description="clusters",
                              layout=w.Layout(width="150px"), style={"description_width": "56px"})
        sp = _num("spread [mm]", cl.get("spread_mm", 0.3), "170px", "80px")
        grp = w.Text(value=cl.get("group", ""), placeholder="(shared with...)", description="group",
                     layout=w.Layout(width="220px"), style={"description_width": "44px"})

        def setcl(_):
            if nc.value:
                f["clusters"] = {"count": int(nc.value), "spread_mm": sp.value, **({"group": grp.value} if grp.value else {})}
            else:
                f.pop("clusters", None)
        for x in (nc, sp, grp):
            x.observe(setcl, "value")
        ori = f.get("orientation", "random")
        od = w.Dropdown(options=["random", "fixed", "texture"], value="texture" if isinstance(ori, dict) else ori,
                        description="orientation", layout=w.Layout(width="220px"))
        ax = [_num("", v, "60px") for v in (ori.get("axis", [0, 1, 0]) if isinstance(ori, dict) else [0, 1, 0])]
        spd = _num("±°", ori.get("spread_deg", 10) if isinstance(ori, dict) else 10, "110px", "24px")

        def setori(_):
            f["orientation"] = ({"axis": [a.value for a in ax], "spread_deg": spd.value} if od.value == "texture"
                                else od.value)
        for x in [od, spd] + ax:
            x.observe(setori, "value")
        sec = w.Checkbox(value=bool(f.get("secret")), description="secret", indent=False, layout=w.Layout(width="90px"))
        sec.observe(lambda c: f.__setitem__("secret", True) if c["new"] else f.pop("secret", None), "value")
        rows.append(w.HBox([nc, sp, grp, od, w.HTML("&nbsp;axis")] + ax + [spd, sec],
                           layout=w.Layout(flex_flow="row wrap", margin="0 0 8px 24px")))
        return w.VBox(rows, layout=w.Layout(border="1px solid #E2E8F0", padding="4px", margin="2px 0"))

    # ------------------------------------------------------------------ materials
    def _materials(self):
        mats = self.recipe["materials"]
        rows = [w.HTML("Each material: a crystal of NCrystal, minerals by volume, a formula and density, a mixture of "
                       "the other materials, or a base calibrated so that its Σ at a wavelength is a measured value "
                       "(with water added for hydrogen). A density factor below 1 for pores; the source of the "
                       "numbers is kept with the sample.")]
        for name in list(mats):
            rows.append(self._one_material(name))
        nm = w.Text(placeholder="new material name", layout=w.Layout(width="220px"))
        add = w.Button(description="Add a material", icon="plus", layout=w.Layout(width="auto"))
        add.on_click(lambda _: (mats.__setitem__(nm.value.strip(), {"minerals": {"plag": 100}}), self.refresh())
                     if nm.value.strip() and nm.value.strip() not in mats else None)
        b_sig = w.Button(description="Compute Σ of all", icon="calculator", layout=w.Layout(width="auto"))
        out = w.HTML()
        b_sig.on_click(lambda _: out.__setattr__("value", self.sigma_table()))
        rows += [w.HBox([nm, add, b_sig]), out]
        self.mats.children = rows

    def _one_material(self, name):
        import samplecraft.materials as scm
        import sample_library as sl
        m = self.recipe["materials"][name]
        if isinstance(m, str):
            m = self.recipe["materials"][name] = {"ncrystal": m}
        kind = next((k for k in MATERIAL_KINDS if k in m), "ncrystal")
        kd = w.Dropdown(options=[(v, k) for k, v in MATERIAL_KINDS.items()], value=kind, layout=w.Layout(width="250px"))
        body = w.VBox()

        def show(_=None):
            k = kd.value
            if k not in m:
                for x in MATERIAL_KINDS:
                    m.pop(x, None)
                m.pop("density", None)
                m[k] = {"ncrystal": "Fe_sg229_Iron-alpha.ncmat", "minerals": {"plag": 100}, "formula": "SiO2",
                        "mix": {}, "calibrate": {"base": {"minerals": {"plag": 100}}, "add": "water", "sigma_cm": 1.0,
                                                 "wavelength_A": 1.8}}[k]
                if k == "formula":
                    m["density"] = 2.65
            if k == "ncrystal":
                crystals = list(sl.ODIN_MATERIALS.values())
                f = w.Combobox(value=m["ncrystal"], options=crystals, placeholder="NCrystal configuration",
                               layout=w.Layout(width="460px"))
                f.observe(lambda c: m.__setitem__("ncrystal", c["new"]), "value")
                body.children = [f]
            elif k == "minerals":
                f = w.Text(value=", ".join(f"{a}: {b:g}" for a, b in m["minerals"].items()),
                           layout=w.Layout(width="460px"))

                def setm(c):
                    try:
                        m["minerals"] = {a.strip(): float(b) for a, b in (p.split(":") for p in c["new"].split(",") if p.strip())}
                    except ValueError:
                        pass
                f.observe(setm, "value")
                body.children = [f, w.HTML("<small>minerals: " + ", ".join(scm.MINERALS) + "</small>")]
            elif k == "formula":
                f = w.Text(value=m["formula"], description="formula", layout=w.Layout(width="260px"))
                f.observe(lambda c: m.__setitem__("formula", c["new"]), "value")
                dd = _num("g/cm³", m.get("density", 2.65), "160px", "50px")
                dd.observe(lambda c: m.__setitem__("density", c["new"]), "value")
                body.children = [w.HBox([f, dd])]
            elif k == "mix":
                f = w.Text(value=", ".join(f"{a}: {b:g}" for a, b in m["mix"].items()), placeholder="material: fraction, ...",
                           layout=w.Layout(width="460px"))

                def setx(c):
                    try:
                        m["mix"] = {a.strip(): float(b) for a, b in (p.split(":") for p in c["new"].split(",") if p.strip())}
                    except ValueError:
                        pass
                f.observe(setx, "value")
                body.children = [f]
            else:
                cal = m["calibrate"]
                base = w.Text(value=", ".join(f"{a}: {b:g}" for a, b in cal["base"].get("minerals", {}).items())
                              if isinstance(cal["base"], dict) else str(cal["base"]),
                              description="base minerals", layout=w.Layout(width="420px"), style={"description_width": "100px"})

                def setb(c):
                    try:
                        cal["base"] = {"minerals": {a.strip(): float(b) for a, b in
                                                    (p.split(":") for p in c["new"].split(",") if p.strip())}}
                    except ValueError:
                        cal["base"] = c["new"].strip()
                base.observe(setb, "value")
                sg = _num("Σ [1/cm]", cal["sigma_cm"], "170px", "70px")
                sg.observe(lambda c: cal.__setitem__("sigma_cm", c["new"]), "value")
                wl = _num("at λ [Å]", cal.get("wavelength_A", 1.8), "160px", "60px")
                wl.observe(lambda c: cal.__setitem__("wavelength_A", c["new"]), "value")
                body.children = [base, w.HBox([sg, wl, w.HTML("&nbsp;(water added to reach it)")])]
        kd.observe(show, "value")
        show()
        df = _num("density factor", m.get("density_factor", 1.0), "200px", "100px")
        df.observe(lambda c: m.__setitem__("density_factor", c["new"]) if c["new"] != 1 else m.pop("density_factor", None),
                   "value")
        src = w.Text(value=m.get("source", ""), placeholder="source (paper, table, assumption)",
                     layout=w.Layout(width="460px"))
        src.observe(lambda c: m.__setitem__("source", c["new"]) if c["new"] else m.pop("source", None), "value")
        rm = w.Button(description="", icon="trash", layout=w.Layout(width="40px"))
        rm.on_click(lambda _: (self.recipe["materials"].pop(name), self.refresh()))
        return w.VBox([w.HBox([w.HTML(f"<b style='display:inline-block;width:200px'>{name}</b>"), kd, df, rm]),
                       w.HBox([w.HTML("<span style='display:inline-block;width:200px'></span>"), w.VBox([body, src])])],
                      layout=w.Layout(border="1px solid #E2E8F0", padding="4px", margin="2px 0"))

    def sigma_table(self):
        import samplecraft as sc
        try:
            cfg, notes = sc.resolve_materials(self.recipe["materials"])
        except Exception as e:
            return f"<span style='color:#B91C1C'>{e}</span>"
        rows = "".join(f"<tr><td>{k}</td><td style='text-align:right'>{sc.sigma(c, [1.8])[0]:.3f}</td>"
                       f"<td style='text-align:right'>{sc.sigma(c, [3.0])[0]:.3f}</td><td><small>{notes[k]}</small></td></tr>"
                       for k, c in cfg.items())
        return ("<table><tr><th>material</th><th>Σ(1.8 Å) [1/cm]</th><th>Σ(3 Å) [1/cm]</th><th>how</th></tr>" + rows +
                "</table>")

    # ------------------------------------------------------------------ components
    def _components(self):
        comps = self.recipe.setdefault("components", {})
        rows = [w.HTML("Components: bodies with their own parts, used several times (a clast with its grains, a "
                       "cell with its electrodes...). A body can <i>use</i> one (with a position, rotation and scale), "
                       "and a fill can place many copies, each scaled and turned at random. Edit them in the YAML "
                       "tab, or make one from a body (<i>Make a component of it</i>).")]
        for n, c in comps.items():
            k = len(c.get("children", []))
            rm = w.Button(description="", icon="trash", layout=w.Layout(width="40px"))
            rm.on_click(lambda _, n=n: (comps.pop(n), self.refresh()))
            rows.append(w.HBox([w.HTML(f"<b>{n}</b>: {SHAPE_NAMES.get(c.get('shape', {}).get('type'), '?')} of "
                                       f"{c.get('material')}, {k} part{'s' if k != 1 else ''} inside"), rm]))
        self.comps.children = rows

    # ------------------------------------------------------------------ YAML
    def _sync_yaml(self):
        self.yaml_text.value = yaml.safe_dump(self.recipe, sort_keys=False, allow_unicode=True, width=110,
                                              default_flow_style=None)

    def apply_yaml(self):
        try:
            r = yaml.safe_load(self.yaml_text.value)
            if not isinstance(r, dict) or "bodies" not in r or "materials" not in r:
                raise ValueError("a recipe needs 'materials' and 'bodies'")
            import samplecraft as sc
            sc.resolve_materials(r["materials"])
            self.recipe = r
            self.sel = (0,)
            self.msg.value = "<span style='color:#15803D'>Recipe applied.</span>"
            self.refresh()
        except Exception as e:
            self.msg.value = f"<span style='color:#B91C1C'>Not applied: {e}</span>"

    def recipe_copy(self):
        r = copy.deepcopy(self.recipe)
        for _, b in self._walk(r["bodies"]):
            if not b.get("fill"):
                b.pop("fill", None)
        return r


def _shifted(body, d):
    """A body description moved by d (its shape and its children's)."""
    b = copy.deepcopy(body)
    if "shape" in b:
        b["shape"]["position"] = [p + q for p, q in zip(b["shape"].get("position", [0, 0, 0]), d)]
    if "position" in b:
        b["position"] = [p + q for p, q in zip(b["position"], d)]
    b["children"] = [_shifted(c, d) for c in b.get("children", [])]
    if not b["children"]:
        b.pop("children")
    return b


def build(recipe):
    """(scene, report lines, problems) of a recipe."""
    import samplecraft as sc
    scene = sc.Scene.from_dict(recipe)
    lines = []
    for r in getattr(scene, "report", []):
        line = f"{r['population']} in {r['body']}: {r['placed']} placed (asked {r['asked']})"
        if r.get("target_mm3"):
            line += f", {100 * r['volume_mm3'] / r['target_mm3']:.0f} % of the volume asked"
        lines.append(line)
    problems = scene.check(n=800)
    for r in getattr(scene, "report", []):
        if r.get("target_mm3") and r["volume_mm3"] < 0.9 * r["target_mm3"]:
            problems.append(f"{r['population']} in {r['body']}: only {100 * r['volume_mm3'] / r['target_mm3']:.0f} % "
                            f"of the volume asked found room (smaller grains, or less)")
        elif isinstance(r.get("asked"), int) and isinstance(r.get("placed"), int) and r["placed"] < r["asked"]:
            problems.append(f"{r['population']} in {r['body']}: {r['placed']} of {r['asked']} found room")
    return scene, lines, problems


def sample_spec(recipe, scene, name="", title="", description=""):
    """The sample file of a built recipe (sample_library format: metadata + the scene as built, with its recipe)."""
    d = scene.to_dict()
    d["recipe"] = recipe
    spec = dict(name=title or name or recipe.get("name", ""), description=description or recipe.get("description", ""),
                scene=d)
    if any(b.get("secret") for _, b in Editor._walk(Editor.__new__(Editor), recipe["bodies"])):
        spec["hidden"] = ["inclusions"]
    return spec


# --------------------------------------------------------------------------- 3D view
def surfaces(scene, n=72):
    """The surfaces of a built scene for a 3D view: the material at each point of a grid of about n points along the
    longest side (the bounds of the sample and its holders), then one surface per material (marching cubes on its
    mask, smoothed a little). Returns [(material, vertices (k, 3) [mm], faces (m, 3), is a holder, volume share)].
    A view, not the model: details smaller than the grid step are lost (the exact model is the scene itself)."""
    from scipy.ndimage import gaussian_filter
    from skimage.measure import marching_cubes
    holders = [b for b in scene.bodies if getattr(b, "holder", False)]
    bodies = [b for b in scene.bodies if not getattr(b, "holder", False)]
    allb = bodies + holders
    lo = np.min([b.shape.bounds()[0] for b in allb], axis=0)
    hi = np.max([b.shape.bounds()[1] for b in allb], axis=0)
    step = float(np.max(hi - lo)) / n
    lo, hi = lo - 1.5 * step, hi + 1.5 * step
    axes = [np.arange(lo[k], hi[k] + step / 2, step) for k in range(3)]
    P = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    shape = tuple(len(a) for a in axes)
    out = []
    for part, is_holder in ((bodies, False), (holders, True)):
        if not part:
            continue
        m = type(scene)(part, scene.materials).material_at(P).reshape(shape)
        names = [x for x in dict.fromkeys(m.ravel()) if x is not None]
        total = max(1, sum(int((m == x).sum()) for x in names))
        for name in names:
            mask = gaussian_filter((m == name).astype(float), 0.6)
            if mask.max() < 0.5:
                continue                                  # thinner than the grid: not drawn
            v, f, _, _ = marching_cubes(mask, 0.5)
            out.append((name, v * step + lo, f, is_holder, int((m == name).sum()) / total))
    return out


def draw_3d(scene, spec=None, azim=-60.0, elev=20.0, fig=None, n=72, surf=None):
    """A 3D view of the sample (surfaces()): the material that fills most of it see-through, so that what is inside
    shows; holders pale gray; the beam (z) as an arrow. Vertical axis of the plot = y (vertical of the twin).
    surf: the output of surfaces(), when it is already computed (turning the view)."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from matplotlib.colors import to_rgb
    import sample_library as sl
    surf = surfaces(scene, n) if surf is None else surf
    fig = fig or plt.figure(figsize=(7.5, 6.5))
    ax = fig.add_subplot(projection="3d")
    names = [s[0] for s in surf if not s[3]]
    colors = sl._rock_colors(dict(spec or {}, materials=dict(scene.cfg())), names)
    main = max((s for s in surf if not s[3]), key=lambda s: s[4], default=(None,))[0]
    light = np.array([0.4, 0.8, 0.45]); light /= np.linalg.norm(light)
    pts = []
    for name, v, f, holder, share in surf:
        # plot axes: (x, z, y) so that y (vertical in the twin) is up and the beam z goes into the picture
        V = v[:, [0, 2, 1]]
        tri = V[f]
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        shade = 0.55 + 0.45 * np.abs(nrm @ light)
        base = np.array(to_rgb("#C9CFD8" if holder else colors.get(name, "#8C7B6B")))
        alpha = 0.25 if holder else (0.22 if (name == main and len(names) > 1) else 0.95)
        fc = np.c_[np.clip(base[None] * shade[:, None], 0, 1), np.full(len(f), alpha)]
        ax.add_collection3d(Poly3DCollection(tri, facecolors=fc, edgecolors="none"))
        pts.append(V)
        ax.plot([], [], "s", color=base, alpha=max(alpha, 0.5),
                label=("holder: " if holder else "") + sl.odin_material_label(dict(spec or {}, materials=dict(scene.cfg())), name))
    P = np.concatenate(pts)
    c, r = 0.5 * (P.min(0) + P.max(0)), 0.5 * float(np.max(P.max(0) - P.min(0)))
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    top = c[2] + 0.92 * r                              # the beam: an arrow along z above the sample, toward it
    ax.quiver(c[0], c[1] - r, top, 0, 0.75 * r, 0, color="#B4562B", lw=2, arrow_length_ratio=0.2)
    ax.text(c[0], c[1] - r, top + 0.08 * r, "neutrons", color="#B4562B", fontsize=9)
    ax.set_xlabel("x [mm]"); ax.set_ylabel("z, along the beam [mm]"); ax.set_zlabel("y [mm]")
    ax.view_init(elev=elev, azim=azim)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.set_title("The sample in 3D (a view on a grid: the finest details are smoothed)", fontsize=10, loc="left")
    return fig
