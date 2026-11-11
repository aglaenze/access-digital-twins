"""Sample library of the digital twins: one YAML file per sample, shared by the pages, the notebooks and NICOS.

Where the samples are:
  * built-in samples, chosen by the teachers: <instrument>/samples/*.yml in this repository;
  * samples made by students with the sample builder (free beamtime): the folder "samples" next to their data, i.e.
    <proposal>/samples/ for NICOS (data in <proposal>/raw) or <session>/samples/ for the web pages.
The twin reads both (the student's samples come after the built-in ones and cannot replace them).

ODIN (imaging): a sample is a set of volumes, each of one crystalline material of NCrystal (non-overlapping), as many
as wanted: boxes, spheres and cylinders (vertical axis, the axis of the rotation stage):
    name: Fe plate 5 mm
    description: ...
    volumes:
      - {material: Fe_sg229_Iron-alpha.ncmat, center_mm: [0, 0, 0], size_mm: [10, 10, 5]}               # a box
      - {material: Cu_sg225.ncmat, shape: sphere, center_mm: [4, 0, 0], size_mm: [3, 3, 3]}             # diameter 3
      - {material: Al_sg225.ncmat, shape: cylinder, center_mm: [-4, 0, 0], size_mm: [2, 8, 2]}          # d 2, h 8
  x horizontal, y vertical, z along the beam (size_mm: the bounding box, size_mm[2] the thickness), centers relative to
  the stage axis. Without "shape": a box.

LoKI (SANS): particles dispersed in a solvent (a mixture of H2O and D2O), in a cell of given thickness:
    name: Silica spheres in D2O
    model: sphere                    # sphere, cylinder, core_shell_sphere (sasmodels), or none (solvent alone)
    parameters: {radius: 50}         # Å
    particle: silica                 # material of the particles (scattering length density, table SLD)
    volume_fraction: 0.01
    solvent: {d2o_fraction: 1.0}
    thickness_mm: 1
  or several kinds of particles (dilute: their scattering adds up):
    populations:
      - {model: sphere, particle: silica, parameters: {radius: 50}, volume_fraction: 0.005}
      - {model: cylinder, particle: gold, parameters: {radius: 20, length: 300}, volume_fraction: 0.002}
  or  empty: true   (nothing in the beam: the empty-beam measurement).

hidden: the exercises can hide some properties from the students (what they have to measure), e.g. the radius.
"""
import glob
import os
import re

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
INSTRUMENTS = ("odin", "loki")

# --------------------------------------------------------------------------- materials
ODIN_MATERIALS = {   # label shown to students: NCrystal file
    "α-iron (ferrite, steel)": "Fe_sg229_Iron-alpha.ncmat", "γ-iron (austenite)": "Fe_sg225_Iron-gamma.ncmat",
    "aluminium": "Al_sg225.ncmat", "copper": "Cu_sg225.ncmat", "nickel": "Ni_sg225.ncmat",
    "vanadium": "V_sg229.ncmat", "niobium": "Nb_sg229.ncmat", "titanium": "Ti_sg194.ncmat",
    "tungsten": "W_sg229.ncmat", "lead": "Pb_sg225.ncmat", "silicon": "Si_sg227.ncmat", "zirconium": "Zr_sg194.ncmat",
    "magnesium": "Mg_sg194.ncmat", "zinc": "Zn_sg194.ncmat", "tin": "Sn_sg141.ncmat", "silver": "Ag_sg225.ncmat",
    "gold": "Au_sg225.ncmat",
}
ODIN_COLORS = {"Fe_sg229_Iron-alpha.ncmat": "#6B7280", "Fe_sg225_Iron-gamma.ncmat": "#9CA3AF",
               "Al_sg225.ncmat": "#C7D2FE", "Cu_sg225.ncmat": "#C2410C", "Ni_sg225.ncmat": "#A3A380",
               "Pb_sg225.ncmat": "#475569", "W_sg229.ncmat": "#334155", "Au_sg225.ncmat": "#EAB308",
               "Ag_sg225.ncmat": "#D1D5DB", "Ti_sg194.ncmat": "#94A3B8"}
FIELD_MM = 14.0          # ODIN: field of view of the Timepix3 camera
# LoKI: scattering length densities [10⁻⁶ Å⁻²] (usual values, NIST SLD calculator); incoherent scattering of the
# solvent [cm⁻¹ sr⁻¹ per cm of... i.e. dΣ/dΩ] and removal (incoherent, mostly by H) [1/m] for pure H2O and pure D2O
SLD = {"D2O": 6.36, "H2O": -0.56, "silica": 3.47, "polystyrene": 1.41, "deuterated polystyrene": 6.4,
       "gold": 4.5, "silver": 3.5, "iron oxide (magnetite)": 6.97, "protein (average)": 2.4, "lipid (tails)": -0.4,
       "PMMA": 1.07}
SOLVENT_INC = {"D2O": 0.05, "H2O": 0.43}       # cm⁻¹ sr⁻¹ (H2O: σ_inc(H) = 80 b, 6.7·10²² H/cm³, /4π)
SOLVENT_REMOVAL = {"D2O": 0.0, "H2O": 536.0}   # 1/m (H2O: Σ_inc = 5.36 cm⁻¹); D2O neglected (as before)
LOKI_MODELS = {"none": [], "sphere": ["radius"], "cylinder": ["radius", "length"],
               "core_shell_sphere": ["radius", "thickness"]}
UNITS = {"radius": "Å", "length": "Å", "thickness": "Å"}
ODIN_SHAPES = ("box", "sphere", "cylinder")


def odin_inside(v, pts):
    """Which points [n, 3] (mm) are inside the volume v (shape, center_mm, size_mm)."""
    c = np.asarray(v.get("center_mm", (0, 0, 0)), float)
    sx, sy, sz = (float(a) for a in v["size_mm"])
    d = np.asarray(pts, float) - c
    shape = v.get("shape", "box")
    if shape == "sphere":
        return (d ** 2).sum(axis=1) <= (sx / 2) ** 2
    if shape == "cylinder":                           # vertical axis (y)
        return (d[:, 0] ** 2 + d[:, 2] ** 2 <= (sx / 2) ** 2) & (np.abs(d[:, 1]) <= sy / 2)
    return (np.abs(d) <= np.array([sx, sy, sz]) / 2).all(axis=1)


def populations(spec):
    """The particle populations of a LoKI sample: [{model, particle, parameters, volume_fraction}, ...]."""
    if spec.get("populations"):
        return list(spec["populations"])
    if spec.get("model", "none") == "none":
        return []
    return [dict(model=spec["model"], particle=spec.get("particle"), parameters=spec.get("parameters") or {},
                 volume_fraction=spec.get("volume_fraction", 0), core_particle=spec.get("core_particle"))]


# --------------------------------------------------------------------------- files
def user_folder(data_folder):
    """Folder of the students' own samples for a data folder (<proposal>/raw -> <proposal>/samples)."""
    if not data_folder:
        return None
    data_folder = data_folder.rstrip("/\\")
    base = os.path.dirname(data_folder) if os.path.basename(data_folder) in ("raw", TRUTH) else data_folder
    return os.path.join(base, "samples").replace(os.sep, "/")


TRUTH = ".twin"


def truth_folder(data_folder):
    """Where the twin keeps what is not data of the instrument, apart from the files the student reads (as at ESS, a
    data folder holds only what the instrument wrote): the truths about the samples measured (<file>.json) and, when
    the ESS file-writer writes the data, the twin's own files of each count (to check the file-writer's).
    <proposal>/raw -> <proposal>/.twin ; any other folder -> <folder>/.twin."""
    data_folder = data_folder.rstrip("/\\")
    if os.path.basename(data_folder) == TRUTH:
        return data_folder.replace(os.sep, "/")
    base = os.path.dirname(data_folder) if os.path.basename(data_folder) == "raw" else data_folder
    return os.path.join(base, TRUTH).replace(os.sep, "/")


def load(instrument, data_folder=None):
    """{name: spec} of the samples available to the instrument (built-in, then the student's)."""
    out = {}
    folders = [(os.path.join(HERE, instrument, "samples"), "built-in")]
    uf = user_folder(data_folder)
    if uf:
        folders.append((uf, "student"))
    for folder, source in folders:
        for f in sorted(glob.glob(os.path.join(folder, "*.yml"))):
            name = os.path.splitext(os.path.basename(f))[0]
            if name in out:
                continue                              # a student's sample never replaces a built-in one
            with open(f, encoding="utf-8") as fh:
                spec = yaml.safe_load(fh) or {}
            spec.update(id=name, source=source, file=f.replace(os.sep, "/"))
            out[name] = spec
    return out


def validate(instrument, spec):
    """List of problems (empty: the sample can be used)."""
    errors = []
    if instrument == "odin":
        vols = spec.get("volumes") or []
        if not vols:
            errors.append("at least one volume (block, sphere or cylinder) is needed")
        boxes = []
        for k, v in enumerate(vols):
            shape = v.get("shape", "box")
            what = f"{shape if shape != 'box' else 'block'} {k + 1}"
            if shape not in ODIN_SHAPES:
                errors.append(f"{what}: unknown shape (box, sphere or cylinder)")
            if v.get("material") not in ODIN_MATERIALS.values():
                errors.append(f"{what}: unknown material {v.get('material')!r}")
            size = np.asarray(v.get("size_mm", [0, 0, 0]), float)
            if len(size) != 3 or (size <= 0).any() or (size > 100).any():
                errors.append(f"{what}: sizes must be between 0 and 100 mm")
            elif shape == "sphere" and not np.allclose(size, size[0]):
                errors.append(f"{what}: a sphere has the same size in x, y and z (its diameter)")
            elif shape == "cylinder" and not np.isclose(size[0], size[2]):
                errors.append(f"{what}: a cylinder has the same size in x and z (its diameter)")
            c = np.asarray(v.get("center_mm", [0, 0, 0]), float)
            boxes.append((c - size / 2, c + size / 2))
        if not errors:
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    lo = np.maximum(boxes[i][0], boxes[j][0]); hi = np.minimum(boxes[i][1], boxes[j][1])
                    if not (hi - lo > 1e-9).all():
                        continue                      # the bounding boxes do not even meet
                    g = [np.linspace(a, b, 15)[1:-1] for a, b in zip(lo, hi)]     # points inside the common box
                    pts = np.stack(np.meshgrid(*g, indexing="ij"), axis=-1).reshape(-1, 3)
                    if (odin_inside(vols[i], pts) & odin_inside(vols[j], pts)).any():
                        errors.append(f"volumes {i + 1} and {j + 1} overlap: a point can only be of one material")
    else:
        if spec.get("empty"):
            return errors
        pops = populations(spec)
        for k, pop in enumerate(pops):
            what = f"particles {k + 1}: " if len(pops) > 1 else ""
            model = pop.get("model", "none")
            if model not in LOKI_MODELS or model == "none":
                errors.append(f"{what}unknown model {model!r}; models: {[m for m in LOKI_MODELS if m != 'none']}")
            for p in LOKI_MODELS.get(model, []):
                v = (pop.get("parameters") or {}).get(p)
                if v is None or not 5 <= float(v) <= 2000:
                    errors.append(f"{what}{p}: between 5 and 2000 Å")
            if pop.get("particle") not in SLD:
                errors.append(f"{what}unknown particle material {pop.get('particle')!r}")
            if not 0 < float(pop.get("volume_fraction", 0)) <= 0.1:
                errors.append(f"{what}volume fraction: between 0 and 0.1")
        if sum(float(p.get("volume_fraction", 0)) for p in pops) > 0.1:
            errors.append("total volume fraction above 0.1: not dilute any more (the particles would interact)")
        x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
        if not 0 <= x <= 1:
            errors.append("D2O fraction: between 0 and 1")
        if not 0.1 <= float(spec.get("thickness_mm", 1)) <= 5:
            errors.append("cell thickness: between 0.1 and 5 mm")
    return errors


def save(instrument, spec, data_folder, name):
    """Writes a student's sample (after validation) in the samples folder of the data folder; returns the path."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name):
        raise ValueError("name: lowercase letters, digits and _, starting with a letter (e.g. my_steel_wedge)")
    if name in load(instrument):
        raise ValueError(f"{name} is the name of a built-in sample: choose another one")
    errors = validate(instrument, spec)
    if errors:
        raise ValueError("; ".join(errors))
    folder = user_folder(data_folder)
    os.makedirs(folder, exist_ok=True)
    keep = {k: v for k, v in spec.items() if k not in ("id", "source", "file")}
    path = os.path.join(folder, name + ".yml")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(keep, fh, sort_keys=False, allow_unicode=True)
    return path.replace(os.sep, "/")


# --------------------------------------------------------------------------- physics
def odin_volumes(spec):
    """[(NCrystal file, center [m], dims [m]), ...] of an ODIN sample (format of odin_virtual); a sphere or a cylinder
    has a 4th item, its shape (boxes keep 3 items: the same as before, for the cached simulations)."""
    out = []
    for v in spec["volumes"]:
        t = (v["material"], tuple(float(c) * 1e-3 for c in v.get("center_mm", (0, 0, 0))),
             tuple(float(s) * 1e-3 for s in v["size_mm"]))
        out.append(t + ((v["shape"],) if v.get("shape", "box") != "box" else ()))
    return out


def solvent_sld(x):
    """SLD of a H2O/D2O mixture with a fraction x of D2O [10⁻⁶ Å⁻²]."""
    return x * SLD["D2O"] + (1 - x) * SLD["H2O"]


def loki_cross_section(spec, q=None):
    """(q [Å⁻¹], dΣ/dΩ [cm⁻¹ sr⁻¹], truth {name: value}) of a LoKI sample; None for the empty beam."""
    import loki_samples as ls                   # (folder loki/ on the path)
    if spec.get("empty"):
        return None
    q = ls.q_grid() if q is None else np.asarray(q)
    x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
    bg = x * SOLVENT_INC["D2O"] + (1 - x) * SOLVENT_INC["H2O"]
    model = spec.get("model", "none")
    truth = dict(d2o_fraction=x, background=bg)
    pops = populations(spec)
    if not pops:
        return q, np.full_like(q, bg), truth
    if len(pops) > 1 or spec.get("populations"):    # several kinds of particles: dilute, their intensities add up
        total = np.full_like(q, bg, dtype=float)
        for k, pop in enumerate(pops):
            one = dict(pop, solvent=spec.get("solvent"))
            one.pop("populations", None)
            _, i_k, t_k = loki_cross_section({**one, "model": pop["model"]}, q)
            total += i_k - bg
            truth.update({f"pop{k + 1}_{n}": v for n, v in t_k.items() if n not in ("d2o_fraction", "background")})
        truth["populations"] = len(pops)
        return q, total, truth
    par = {k: float(v) for k, v in (spec.get("parameters") or {}).items()}
    phi = float(spec["volume_fraction"])
    sld_p, sld_s = SLD[spec["particle"]], solvent_sld(x)
    truth.update(par, volume_fraction=phi, sld_particle=sld_p, sld_solvent=sld_s)
    if model == "sphere":                       # same arithmetic as loki_samples.silica_spheres (cached simulations)
        drho = (sld_s - sld_p) * 1e10
        volume = 4 / 3 * np.pi * (par["radius"] * 1e-8) ** 3
        i0 = phi * volume * drho ** 2
        truth["i0"] = i0
        return q, i0 * ls.sphere_form_factor(q, par["radius"]) + bg, truth
    from sasmodels.core import load_model
    from sasmodels.direct_model import call_kernel
    m = load_model(model)
    extra = dict(sld_shell=sld_p) if model == "core_shell_sphere" else {}
    sld_core = spec.get("core_particle")
    pars = dict(scale=phi, background=bg, sld_solvent=sld_s, **par, **extra)
    pars["sld_core" if model == "core_shell_sphere" else "sld"] = SLD[sld_core] if sld_core else sld_p
    return q, call_kernel(m.make_kernel([q]), pars), truth


def loki_sample(spec):
    """(function returning (q, dΣ/dΩ, truth), kwargs, thickness [m], mu_abs [1/m], mu_rem [1/m]): the format of
    loki_samples.SAMPLES; function None for the empty beam."""
    if spec.get("empty"):
        return (None, {}, 0.0, 0.0, 0.0)
    x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
    mu_rem = x * SOLVENT_REMOVAL["D2O"] + (1 - x) * SOLVENT_REMOVAL["H2O"]
    return (lambda: loki_cross_section(spec), {}, float(spec.get("thickness_mm", 1)) * 1e-3, 0.0, float(mu_rem))


# --------------------------------------------------------------------------- what the student sees
def exercise_hidden(exercise_yml):
    """{sample: [hidden properties]} of an exercise (field "samples" of its exercise.yml)."""
    with open(exercise_yml, encoding="utf-8") as fh:
        ex = yaml.safe_load(fh) or {}
    return {n: (v or {}).get("hidden", []) for n, v in (ex.get("samples") or {}).items()}


def describe(instrument, spec, hidden=()):
    """Plain-text description of a sample, with the hidden properties replaced by "?" (what is to be measured)."""
    hidden = set(hidden or spec.get("hidden", []))
    q = lambda k, txt: "?" if k in hidden else txt
    lines = [f"{spec.get('name', spec.get('id'))}" + (f"  ({spec['source']} sample)" if spec.get("source") else "")]
    if spec.get("description"):
        lines.append(spec["description"])
    if instrument == "odin":
        label = {v: k for k, v in ODIN_MATERIALS.items()}
        for k, v in enumerate(spec.get("volumes", [])):
            mat = q("material", label.get(v["material"], v["material"]))
            sx, sy, sz = v["size_mm"]; cx, cy, cz = v.get("center_mm", (0, 0, 0))
            at = f"centered at x = {cx:g} mm, y = {cy:g} mm" + (f", z = {cz:g} mm" if cz else "")
            shape = v.get("shape", "box")
            if shape == "sphere":
                lines.append(f"  sphere {k + 1}: {mat}, diameter {q('thickness', f'{sx:g} mm')}, {at}")
            elif shape == "cylinder":
                lines.append(f"  cylinder {k + 1}: {mat}, diameter {q('thickness', f'{sx:g} mm')}, height {sy:g} mm "
                             f"(vertical), {at}")
            else:
                lines.append(f"  block {k + 1}: {mat}, {sx:g} × {sy:g} mm, {q('thickness', f'{sz:g} mm thick')}, {at}")
    else:
        if spec.get("empty"):
            lines.append("  nothing in the beam")
            return "\n".join(lines)
        x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
        lines.append(f"  cell {float(spec.get('thickness_mm', 1)):g} mm thick, solvent {100 * x:.0f} % D2O / "
                     f"{100 * (1 - x):.0f} % H2O")
        for pop in populations(spec):
            pars = ", ".join(f"{p} {q(p, f'{float(v):g} {UNITS.get(p, "")}'.strip())}"
                             for p, v in (pop.get("parameters") or {}).items())
            lines.append(f"  particles: {q('particle', pop.get('particle', '?'))}, shape {q('model', pop['model'])}"
                         f" ({pars}), volume fraction {q('volume_fraction', f'{100 * float(pop['volume_fraction']):g} %')}")
    if hidden:
        lines.append("  ? = not given: this is what you have to measure")
    return "\n".join(lines)


def show(fig=None):
    """Shows a figure in Jupyter at twice the resolution (sharp on all screens), at its normal size. Used instead of
    plt.show() after draw(): the global "retina" setting of matplotlib could block Voila pages."""
    import io
    import struct
    import matplotlib.pyplot as plt
    from IPython.display import Image, display
    fig = fig or plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=2 * fig.dpi, bbox_inches="tight")
    plt.close(fig)
    data = buf.getvalue()
    width = struct.unpack(">I", data[16:20])[0] // 2              # PNG header: width in pixels
    display(Image(data=data, width=width))


def draw(instrument, spec, hidden=(), fig=None):
    """Figure of the sample as the student would see it on the sample table (hidden properties not shown)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    hidden = set(hidden or spec.get("hidden", []))
    fig = fig or plt.figure(figsize=(10, 4.2))
    fig.clf()
    if instrument == "odin":
        label = {v: k for k, v in ODIN_MATERIALS.items()}
        a1, a2 = fig.add_subplot(1, 2, 1), fig.add_subplot(1, 2, 2)
        for v in spec.get("volumes", []):
            (sx, sy, sz), (cx, cy, cz) = v["size_mm"], v.get("center_mm", (0, 0, 0))
            col = "#9CA3AF" if "material" in hidden else ODIN_COLORS.get(v["material"], "#A8A29E")
            name = "?" if "material" in hidden else label.get(v["material"], v["material"])
            shape = v.get("shape", "box")
            if shape == "sphere":                      # a disk in both views
                a1.add_patch(Circle((cx, cy), sx / 2, fc=col, ec="k", alpha=0.85, label=name))
                a2.add_patch(Circle((cz, cx), sx / 2, fc=col, ec="k", alpha=0.85))
            elif shape == "cylinder":                  # vertical: a rectangle seen by the beam, a disk from above
                a1.add_patch(Rectangle((cx - sx / 2, cy - sy / 2), sx, sy, fc=col, ec="k", alpha=0.85, label=name))
                a2.add_patch(Circle((cz, cx), sx / 2, fc=col, ec="k", alpha=0.85))
            else:
                a1.add_patch(Rectangle((cx - sx / 2, cy - sy / 2), sx, sy, fc=col, ec="k", alpha=0.85, label=name))
                a2.add_patch(Rectangle((cz - sz / 2, cx - sx / 2), sz, sx, fc=col, ec="k", alpha=0.85))
        h = FIELD_MM / 2
        a1.add_patch(Rectangle((-h, -h), FIELD_MM, FIELD_MM, fill=False, ec="#2A7D6F", lw=2, ls="--",
                               label="field of view (14 mm)"))
        a1.set(title="seen by the neutrons (beam's eye view)", xlabel="x [mm]", ylabel="y [mm]", aspect="equal")
        handles, labels = a1.get_legend_handles_labels()
        uniq = dict(zip(labels, handles))
        a1.legend(uniq.values(), uniq.keys(), fontsize=8, loc="upper right")
        a2.annotate("", xy=(0, 0), xytext=(-25, 0), arrowprops=dict(arrowstyle="->", color="#B4562B", lw=2))
        a2.text(-24, 1.5, "neutrons", color="#B4562B", fontsize=9)
        a2.set(title="seen from above (thickness along the beam)", xlabel="z, along the beam [mm]", ylabel="x [mm]",
               aspect="equal")
        if "thickness" in hidden:
            a2.text(0.5, 0.02, "thickness: ?", transform=a2.transAxes, ha="center")
        for a, lim in ((a1, 12), (a2, 14)):
            a.autoscale_view(); a.set_xlim(min(a.get_xlim()[0], -lim), max(a.get_xlim()[1], lim))
            a.set_ylim(min(a.get_ylim()[0], -lim), max(a.get_ylim()[1], lim)); a.grid(alpha=0.3)
        a2.set_xlim(-27, max(a2.get_xlim()[1], 10))
    else:
        ax = fig.add_subplot(1, 1, 1)
        ax.set_axis_off(); ax.set_xlim(0, 10); ax.set_ylim(0, 4.2)
        if spec.get("empty"):
            ax.text(5, 2.1, "empty beam: nothing on the sample position", ha="center", fontsize=13)
            return fig
        x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
        solvent = np.array([0.80, 0.90, 1.0]) * x + np.array([0.93, 0.97, 0.93]) * (1 - x)
        ax.add_patch(Rectangle((0.4, 0.5), 3.2, 3.2, fc=solvent, ec="#334155", lw=2))
        ax.text(2.0, 0.2, f"cell: {float(spec.get('thickness_mm', 1)):g} mm of solvent", ha="center", fontsize=10)
        pops = populations(spec)
        rng = np.random.default_rng(1)
        for k, pop in enumerate(pops):
            r = float((pop.get("parameters") or {}).get("radius", 50))
            rr = 0.13 if "radius" in hidden else float(np.clip(0.06 + r / 600, 0.06, 0.35))
            n = 14 if "volume_fraction" in hidden else int(np.clip(float(pop["volume_fraction"]) * 1500, 4, 60))
            col = "#9CA3AF" if "particle" in hidden else ("#B4562B", "#2A7D6F", "#1D4ED8", "#A16207")[k % 4]
            for _ in range(n):
                xy = (rng.uniform(0.7, 3.3), rng.uniform(0.8, 3.4))
                if pop["model"] == "cylinder":         # a rod, randomly oriented
                    ln = rr * float(np.clip(float(pop["parameters"].get("length", 200)) / r, 1.5, 6)) / 2
                    a = rng.uniform(0, np.pi)
                    ax.plot([xy[0] - ln * np.cos(a), xy[0] + ln * np.cos(a)], [xy[1] - ln * np.sin(a), xy[1] + ln * np.sin(a)],
                            color=col, lw=max(2, 30 * rr), solid_capstyle="round")
                else:
                    ax.add_patch(Circle(xy, rr, fc=col, ec="k", lw=0.5))
        model = "particles" if pops else "none"
        ax.text(4.1, 3.6, describe("loki", spec, hidden), fontsize=10, va="top", family="monospace", wrap=True)
        if model != "none":
            ax.text(4.1, 0.6, "(schematic: particles enlarged ~10⁷ times)", fontsize=9, color="#6B7280")
    fig.tight_layout()
    return fig
