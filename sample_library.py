"""Sample library of the digital twins: one YAML file per sample, shared by the pages, the notebooks and NICOS.

Where the samples are:
  * built-in samples, chosen by the teachers: <instrument>/samples/*.yml in this repository;
  * samples made by students with the sample builder (free beamtime): the folder "samples" next to their data, i.e.
    <proposal>/samples/ for NICOS (data in <proposal>/raw) or <session>/samples/ for the web pages.
The twin reads both (the student's samples come after the built-in ones and cannot replace them).

ODIN (imaging): a sample is a set of boxes, each of one crystalline material of NCrystal (non-overlapping):
    name: Fe plate 5 mm
    description: ...
    volumes:
      - {material: Fe_sg229_Iron-alpha.ncmat, center_mm: [0, 0, 0], size_mm: [10, 10, 5]}
  x horizontal, y vertical, z along the beam (size_mm[2] is the thickness), centers relative to the stage axis.

LoKI (SANS): particles dispersed in a solvent (a mixture of H2O and D2O), in a cell of given thickness:
    name: Silica spheres in D2O
    model: sphere                    # sphere, cylinder, core_shell_sphere (sasmodels), or none (solvent alone)
    parameters: {radius: 50}         # Å
    particle: silica                 # material of the particles (scattering length density, table SLD)
    volume_fraction: 0.01
    solvent: {d2o_fraction: 1.0}
    thickness_mm: 1
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


# --------------------------------------------------------------------------- files
def user_folder(data_folder):
    """Folder of the students' own samples for a data folder (<proposal>/raw -> <proposal>/samples)."""
    if not data_folder:
        return None
    data_folder = data_folder.rstrip("/\\")
    base = os.path.dirname(data_folder) if os.path.basename(data_folder) == "raw" else data_folder
    return os.path.join(base, "samples").replace(os.sep, "/")


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
            errors.append("at least one block is needed")
        boxes = []
        for k, v in enumerate(vols):
            if v.get("material") not in ODIN_MATERIALS.values():
                errors.append(f"block {k + 1}: unknown material {v.get('material')!r}")
            size = np.asarray(v.get("size_mm", [0, 0, 0]), float)
            if len(size) != 3 or (size <= 0).any() or (size > 100).any():
                errors.append(f"block {k + 1}: sizes must be between 0 and 100 mm")
            c = np.asarray(v.get("center_mm", [0, 0, 0]), float)
            boxes.append((c - size / 2, c + size / 2))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                lo = np.maximum(boxes[i][0], boxes[j][0]); hi = np.minimum(boxes[i][1], boxes[j][1])
                if (hi - lo > 1e-9).all():
                    errors.append(f"blocks {i + 1} and {j + 1} overlap: a point can only be of one material")
    else:
        if spec.get("empty"):
            return errors
        model = spec.get("model", "none")
        if model not in LOKI_MODELS:
            errors.append(f"unknown model {model!r}; models: {list(LOKI_MODELS)}")
        for p in LOKI_MODELS.get(model, []):
            v = (spec.get("parameters") or {}).get(p)
            if v is None or not 5 <= float(v) <= 2000:
                errors.append(f"{p}: between 5 and 2000 Å")
        if model != "none":
            if spec.get("particle") not in SLD:
                errors.append(f"unknown particle material {spec.get('particle')!r}")
            if not 0 < float(spec.get("volume_fraction", 0)) <= 0.1:
                errors.append("volume fraction: between 0 and 0.1 (dilute: no interaction between particles)")
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
    """[(NCrystal file, center [m], dims [m]), ...] of an ODIN sample (format of odin_virtual)."""
    return [(v["material"], tuple(float(c) * 1e-3 for c in v.get("center_mm", (0, 0, 0))),
             tuple(float(s) * 1e-3 for s in v["size_mm"])) for v in spec["volumes"]]


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
    if model == "none":
        return q, np.full_like(q, bg), truth
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
            lines.append(f"  block {k + 1}: {mat}, {sx:g} × {sy:g} mm, {q('thickness', f'{sz:g} mm thick')}, "
                         f"centered at x = {cx:g} mm, y = {cy:g} mm")
    else:
        if spec.get("empty"):
            lines.append("  nothing in the beam")
            return "\n".join(lines)
        x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
        lines.append(f"  cell {float(spec.get('thickness_mm', 1)):g} mm thick, solvent {100 * x:.0f} % D2O / "
                     f"{100 * (1 - x):.0f} % H2O")
        if spec.get("model", "none") != "none":
            pars = ", ".join(f"{p} {q(p, f'{float(v):g} {UNITS.get(p, "")}'.strip())}"
                             for p, v in (spec.get("parameters") or {}).items())
            lines.append(f"  particles: {q('particle', spec.get('particle', '?'))}, shape {q('model', spec['model'])}"
                         f" ({pars}), volume fraction {q('volume_fraction', f'{100 * float(spec['volume_fraction']):g} %')}")
    if hidden:
        lines.append("  ? = not given: this is what you have to measure")
    return "\n".join(lines)


def _sharp_figures():
    """In Jupyter, figures drawn at twice the resolution (sharp on all screens) instead of the default 72 dpi PNG."""
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is not None:
            from matplotlib_inline.backend_inline import set_matplotlib_formats
            set_matplotlib_formats("retina")
    except Exception:
        pass


def draw(instrument, spec, hidden=(), fig=None):
    """Figure of the sample as the student would see it on the sample table (hidden properties not shown)."""
    _sharp_figures()
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
        model = spec.get("model", "none")
        if model != "none":
            rng = np.random.default_rng(1)
            r = float((spec.get("parameters") or {}).get("radius", 50))
            rr = 0.13 if "radius" in hidden else float(np.clip(0.06 + r / 600, 0.06, 0.35))
            n = 14 if "volume_fraction" in hidden else int(np.clip(float(spec["volume_fraction"]) * 1500, 4, 60))
            col = "#9CA3AF" if "particle" in hidden else "#B4562B"
            for _ in range(n):
                ax.add_patch(Circle((rng.uniform(0.7, 3.3), rng.uniform(0.8, 3.4)), rr, fc=col, ec="k", lw=0.5))
        ax.text(4.1, 3.6, describe("loki", spec, hidden), fontsize=10, va="top", family="monospace", wrap=True)
        if model != "none":
            ax.text(4.1, 0.6, "(schematic: particles enlarged ~10⁷ times)", fontsize=9, color="#6B7280")
    fig.tight_layout()
    return fig
