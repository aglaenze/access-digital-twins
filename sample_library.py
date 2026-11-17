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
  Natural samples (rocks, meteorites) also use irregular shapes (rock_shapes.py):
      - {material: matrix, shape: slab, center_mm: [0, 0, 0], size_mm: [8, 12, 2], seed: 11}    # a sawn piece
      - {material: feldspar, shape: blob, inside: 0, center_mm: [1, 2, 0], size_mm: [0.3, 0.4, 0.2],
         angles_deg: [20, 40, 10], wobble: 0.12, seed: 5}                                       # a lumpy grain
  an ellipsoid turned in 3D (angles about z, x, then y) with lumps (wobble 0: a plain ellipsoid); "inside: k" makes
  a volume an inclusion of volume k (it replaces its material); "secret: true" marks what an exercise hides (drawn
  and described as the material around it when the exercise hides its "inclusions").

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
    "void": "void.ncmat",
}
# minerals and liquids for the mixtures of the sample builder (a rock, a wet material), besides the crystals above
MINERALS = {
    "quartz (SiO2)": "SiO2-alpha_sg154_AlphaQuartz.ncmat",
    "forsterite (olivine, Mg2SiO4)": "Mg2SiO4_sg62_MagnesiumSilicate.ncmat",
    "corundum (Al2O3)": "Al2O3_sg167_Corundum.ncmat",
    "brucite (Mg(OH)2: holds water)": "MgO2H2_sg164_MagnesiumHydroxide.ncmat",
    "portlandite (Ca(OH)2: holds water)": "CaO2H2_sg164_CalciumHydroxide.ncmat",
    "magnesite (MgCO3)": "MgCO3_sg167_MagnesiumCarbonate.ncmat",
    "liquid water (H2O)": "LiquidWaterH2O_T293.6K.ncmat",
    "liquid heavy water (D2O)": "LiquidHeavyWaterD2O_T293.6K.ncmat",
}
MIX_PARTS = {**{k: v for k, v in ODIN_MATERIALS.items() if v != "void.ncmat"}, **MINERALS}
# models to start a mixture from (volume fractions in %): its components then shown, each one can be changed
MIX_MODELS = {
    "Martian rock (model)": [("quartz (SiO2)", 50), ("forsterite (olivine, Mg2SiO4)", 30), ("corundum (Al2O3)", 20)],
    "rock with 6 % water (model)": [("quartz (SiO2)", 80), ("brucite (Mg(OH)2: holds water)", 20)],
}
# the two rocks of the first versions of the builder: still accepted in samples saved with them
LEGACY = {
    "Martian rock (model)": "phases<0.5*SiO2-alpha_sg154_AlphaQuartz.ncmat&0.3*Mg2SiO4_sg62_MagnesiumSilicate.ncmat&0.2*Al2O3_sg167_Corundum.ncmat>",
    "rock with 6 % water (model)": "phases<0.8*SiO2-alpha_sg154_AlphaQuartz.ncmat&0.2*MgO2H2_sg164_MagnesiumHydroxide.ncmat>",
}


def odin_material(base, density=100.0):
    """NCrystal configuration of a crystal with a density in % of the crystal's (pores: less than 100 %)."""
    d = float(density)
    return base if abs(d - 100) < 1e-9 else f"{base};density={d / 100:g}x"


def odin_mixture(parts, density=100.0):
    """NCrystal configuration of a mixture: parts [(label of MIX_PARTS, volume fraction in %)], normalized to 100 %;
    density in % of that of the compact mixture."""
    tot = sum(float(f) for _, f in parts)
    body = "&".join(f"{float(f) / tot:.4g}*{MIX_PARTS[k]}" for k, f in parts)
    return odin_material(f"phases<{body}>", density)


def _split_density(cfg):
    m = re.match(r"^(.*?)(?:;density=([0-9.eE+-]+)x)?$", cfg)
    return m.group(1), (float(m.group(2)) * 100 if m.group(2) else 100.0)


SOLID = re.compile(r"^solid::(?:[A-Z][a-z]?\d+)+/\d+(?:\.\d+)?gcm3$")   # NCrystal: a composition at a density


def _mix_part_ok(mat):
    """A component of a mixture: a crystal or mineral of the builder, or a composition (solid::, no Bragg edges:
    a fine-grained mineral)."""
    return mat in MIX_PARTS.values() or mat.removeprefix("stdlib::") in MIX_PARTS.values() or bool(SOLID.match(mat))


def odin_material_problem(cfg):
    """What is wrong with the material of a student's volume (None: fine): a crystal of the list, a composition
    (solid::), or a mixture of them and of the minerals of the builder, with an optional density factor."""
    if cfg in ODIN_MATERIALS.values() or cfg in LEGACY.values():
        return None
    base, dens = _split_density(cfg)
    if not 5 <= dens <= 100:
        return f"density {dens:g} %: between 5 and 100 % of that of the crystal"
    if (base in ODIN_MATERIALS.values() and base != "void.ncmat") or SOLID.match(base):
        return None
    m = re.match(r"^phases<(.*)>$", base)
    if not m:
        return f"unknown material {cfg!r}"
    if not m.group(1):
        return "a mixture needs at least one component"
    fracs = []
    for part in m.group(1).split("&"):
        f, _, mat = part.partition("*")
        if not _mix_part_ok(mat):
            return f"unknown component {mat!r} in a mixture"
        try:
            fracs.append(float(f))
        except ValueError:
            return f"fraction {f!r} in a mixture"
    if min(fracs) <= 0 or abs(sum(fracs) - 1) > 0.01:
        return "the fractions of a mixture must be positive and add up to 100 %"
    return None


def odin_material_label(spec, name):
    """What a student reads for the material of a volume: the crystal, or the composition of a mixture."""
    named = spec.get("materials") or {}
    cfg = named.get(name, name)
    labels = {v: k for k, v in {**ODIN_MATERIALS, **MINERALS, **LEGACY}.items()}
    if cfg in labels:
        return labels[cfg]
    base, dens = _split_density(cfg)
    m = re.match(r"^phases<(.*)>$", base)
    if base in labels:
        txt = labels[base]
    elif m and all(p.partition("*")[2] in labels for p in m.group(1).split("&")):
        txt = "mixture of " + ", ".join(f"{100 * float(p.partition('*')[0]):.3g} % {labels[p.partition('*')[2]].split(' (')[0]}"
                                         for p in m.group(1).split("&"))
    else:
        return name                     # a material named in the sample (a rock of a built-in sample)
    return txt + (f", {dens:.3g} % of its density" if abs(dens - 100) > 1e-9 else "")
ODIN_COLORS = {"Fe_sg229_Iron-alpha.ncmat": "#6B7280", "Fe_sg225_Iron-gamma.ncmat": "#9CA3AF",
               "Al_sg225.ncmat": "#C7D2FE", "Cu_sg225.ncmat": "#C2410C", "Ni_sg225.ncmat": "#A3A380",
               "Pb_sg225.ncmat": "#475569", "W_sg229.ncmat": "#334155", "Au_sg225.ncmat": "#EAB308",
               "Ag_sg225.ncmat": "#D1D5DB", "Ti_sg194.ncmat": "#94A3B8",
               "phases<0.5*SiO2-alpha_sg154_AlphaQuartz.ncmat&0.3*Mg2SiO4_sg62_MagnesiumSilicate.ncmat&0.2*Al2O3_sg167_Corundum.ncmat>": "#7C6A58", "phases<0.8*SiO2-alpha_sg154_AlphaQuartz.ncmat&0.2*MgO2H2_sg164_MagnesiumHydroxide.ncmat>": "#3B4A63", "void.ncmat": "#FFFFFF"}
FIELD_MM = 14.0          # ODIN: field of view of the Timepix3 camera
# LoKI: scattering length densities [10⁻⁶ Å⁻²] (usual values, NIST SLD calculator); incoherent scattering of the
# solvent [cm⁻¹ sr⁻¹ per cm of... i.e. dΣ/dΩ] and removal (incoherent, mostly by H) [1/m] for pure H2O and pure D2O
SLD = {"D2O": 6.36, "H2O": -0.56, "silica": 3.47, "polystyrene": 1.41, "deuterated polystyrene": 6.4,
       "gold": 4.5, "silver": 3.5, "iron oxide (magnetite)": 6.97, "protein (average)": 2.4, "lipid (tails)": -0.4,
       "PMMA": 1.07}
SOLVENT_INC = {"D2O": 0.05, "H2O": 0.43}       # cm⁻¹ sr⁻¹ (H2O: σ_inc(H) = 80 b, 6.7·10²² H/cm³, /4π)
SOLVENT_REMOVAL = {"D2O": 0.0, "H2O": 536.0}   # 1/m (H2O: Σ_inc = 5.36 cm⁻¹); D2O neglected (as before)
# LoKI: the liquid is held in a cell of fused quartz (as the usual Hellma cells for SANS): two windows of 1.25 mm, the
# liquid between them. Fused silica, 2.20 g/cm³: 2.205·10²² SiO2/cm³; σ_s = 2.17 (Si) + 2 × 4.23 (O) = 10.63 b,
# σ_abs(1.8 Å) = 0.17 b -> Σ_s = 0.234 cm⁻¹ (23.4 /m), Σ_abs = 0.0038 cm⁻¹ (0.38 /m). The windows remove neutrons from
# the beam (transmission 0.94 for both together); their own small-angle scattering (flat and weak for a polished
# glass) is neglected.
CELL_WINDOWS_MM = 2 * 1.25
EMPTY_CELL_DSDO = 1e-4                           # cm⁻¹ sr⁻¹ per cm of the cell's gap: nearly nothing (not 0 for McStas)
QUARTZ_REMOVAL, QUARTZ_ABS = 23.4, 0.38          # 1/m
LOKI_MODELS = {"none": [], "sphere": ["radius"], "cylinder": ["radius", "length"],
               "core_shell_sphere": ["radius", "thickness"]}
UNITS = {"radius": "Å", "length": "Å", "thickness": "Å"}
ODIN_SHAPES = ("box", "sphere", "cylinder", "ellipsoid", "blob", "slab")


def shape_dims(v):
    """dims [m] (and angles, lumps, seed) of a volume for odin_hybrid and rock_shapes."""
    size = [float(s) * 1e-3 for s in v["size_mm"]]
    if len(size) > 3:                                   # the 4th item of a box or an ellipsoid: its own angle [deg]
        size[3] = float(v["size_mm"][3])
    shape = v.get("shape", "box")
    if shape == "blob":
        size = size[:3] + [float(a) for a in (v.get("angles_deg") or (0, 0, 0))] + [float(v.get("wobble", 0.0)),
                                                                                    int(v.get("seed", 0))]
    elif shape == "slab":
        size = size[:3] + [int(v.get("seed", 0))]
    return tuple(size)


def odin_inside(v, pts):
    """Which points [n, 3] (mm) are inside the volume v (shape, center_mm, size_mm)."""
    c = np.asarray(v.get("center_mm", (0, 0, 0)), float)
    d = np.asarray(pts, float) - c
    shape = v.get("shape", "box")
    if shape in ("blob", "slab"):
        import rock_shapes
        return rock_shapes.inside(shape, shape_dims(v), d * 1e-3)
    sx, sy, sz = (float(a) for a in v["size_mm"][:3])
    if shape in ("box", "ellipsoid") and len(v["size_mm"]) > 3 and float(v["size_mm"][3]):
        t = np.radians(float(v["size_mm"][3]))         # its own angle about y: back to its frame
        c_, s_ = np.cos(t), np.sin(t)
        d = np.c_[c_ * d[:, 0] - s_ * d[:, 2], d[:, 1], s_ * d[:, 0] + c_ * d[:, 2]]
    if shape == "ellipsoid":
        return ((d / (np.array([sx, sy, sz]) / 2)) ** 2).sum(axis=1) <= 1
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
            spec = _read_yml(f)
            spec.update(id=name, source=source, file=f.replace(os.sep, "/"))
            out[name] = spec
    return out


_YML = {}                  # {file: (modification time, size, spec)}: a rock has thousands of volumes, read once


def _read_yml(f):
    """The spec of a sample file, parsed once (C parser of libyaml if present) and kept until the file changes; a
    copy is returned (the caller may change it)."""
    import copy
    st = os.stat(f)
    hit = _YML.get(f)
    if hit is None or hit[:2] != (st.st_mtime_ns, st.st_size):
        with open(f, encoding="utf-8") as fh:
            spec = yaml.load(fh, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader)) or {}
        _YML[f] = hit = (st.st_mtime_ns, st.st_size, spec)
    return copy.deepcopy(hit[2])


def validate(instrument, spec):
    """List of problems (empty: the sample can be used)."""
    errors = []
    if instrument == "odin":
        vols = spec.get("volumes") or []
        if not [v for v in vols if not v.get("holder")]:
            errors.append("at least one volume (block, sphere or cylinder) is needed, besides the holder")
        boxes = []
        for k, v in enumerate(vols):
            shape = v.get("shape", "box")
            what = f"{shape if shape != 'box' else 'block'} {k + 1}"
            if shape not in ODIN_SHAPES:
                errors.append(f"{what}: unknown shape (box, sphere or cylinder)")
            problem = odin_material_problem((spec.get("materials") or {}).get(v.get("material"), v.get("material") or ""))
            if problem:
                errors.append(f"{what}: {problem}")
            size = np.asarray(v.get("size_mm", [0, 0, 0]), float)[:3]
            if len(size) != 3 or (size <= 0).any() or (size > 100).any():
                errors.append(f"{what}: sizes must be between 0 and 100 mm")
            elif shape == "sphere" and not np.allclose(size, size[0]):
                errors.append(f"{what}: a sphere has the same size in x, y and z (its diameter)")
            elif shape == "cylinder" and not np.isclose(size[0], size[2]):
                errors.append(f"{what}: a cylinder has the same size in x and z (its diameter)")
            c = np.asarray(v.get("center_mm", [0, 0, 0]), float)
            if shape == "blob":                       # turned in 3D, its lumps out to 1 + wobble
                half = np.full(3, size.max() / 2 * (1 + abs(float(v.get("wobble", 0)))))
            elif shape == "slab":
                half = size / 2 + 0.3
            elif shape in ("box", "ellipsoid") and len(v.get("size_mm", [])) > 3:
                half = np.full(3, float(np.linalg.norm(size)) / 2)        # turned about y
            else:
                half = size / 2
            boxes.append((c - half, c + half))
        if not errors:
            def hosts(k):                             # the volumes around volume k (an inclusion in an inclusion...)
                out = set()
                while "inside" in vols[k] and vols[k]["inside"] not in out:
                    k = vols[k]["inside"]
                    out.add(k)
                return out
            up = [hosts(k) for k in range(len(vols))]
            LO = np.array([b[0] for b in boxes]).reshape(-1, 3); HI = np.array([b[1] for b in boxes]).reshape(-1, 3)
            for i in range(len(boxes)):
                meet = (np.minimum(HI[i], HI[i + 1:]) - np.maximum(LO[i], LO[i + 1:]) > 1e-9).all(axis=1)
                for j in i + 1 + np.flatnonzero(meet):            # only pairs whose bounding boxes meet
                    if i in up[j] or j in up[i]:
                        continue                      # an inclusion and a volume around it
                    lo = np.maximum(boxes[i][0], boxes[j][0]); hi = np.minimum(boxes[i][1], boxes[j][1])
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
        yaml.safe_dump(keep, fh, sort_keys=False, allow_unicode=True, default_flow_style=None)   # [x, y, z] inline
    return path.replace(os.sep, "/")


# --------------------------------------------------------------------------- physics
def odin_volumes(spec):
    """[(NCrystal file, center [m], dims [m]), ...] of an ODIN sample (format of odin_virtual); a sphere or a cylinder
    has a 4th item, its shape (boxes keep 3 items: the same as before, for the cached simulations). A volume inside
    another one (an inclusion: "inside: k", the index of the volume around it, listed before it) has a 5th item, the
    material it replaces (McStas: the later volume has the higher priority; hybrid model: its Σ minus the host's)."""
    out = []
    named = spec.get("materials") or {}                 # a sample may name its materials (a rock: long mixtures)
    mat = lambda name: named.get(name, name)
    for v in spec["volumes"]:
        t = (mat(v["material"]), tuple(float(c) * 1e-3 for c in v.get("center_mm", (0, 0, 0))), shape_dims(v))
        if "inside" in v:
            out.append(t + (v.get("shape", "box"), mat(spec["volumes"][int(v["inside"])]["material"])))
        else:
            out.append(t + ((v["shape"],) if v.get("shape", "box") != "box" else ()))
    return out


def odin_strain_per_kN(spec):
    """Lattice strain along the beam of each volume of an ODIN sample, per kN of tensile load: None if the sample
    cannot be loaded. A sample with
        load: {axis: y, max_kN: 16, young_GPa: 210, poisson: 0.29}
    is pulled along the vertical axis (y; or x with axis: x) by a load frame. Each volume (a box) carries the whole
    force F over its cross-section A = width (x) × thickness (z) (axis x: height (y) × thickness (z)): stress σ = F / A (uniform in the volume: the stress concentration
    where the section changes is not modeled), strain along the load ε = σ / E (Hooke, elastic range), and across
    it, along the beam, ε_beam = −ν σ / E (Poisson contraction). Neutron transmission sees the lattice planes
    perpendicular to the beam (a Bragg edge is back-scattering): it measures ε_beam."""
    load = spec.get("load")
    if not load:
        return None
    E, nu = float(load["young_GPa"]) * 1e9, float(load["poisson"])
    across = 1 if load.get("axis", "y") == "x" else 0      # pulled along x: the section is height (y) × thickness (z)
    return [0.0 if v.get("holder") else -nu * 1e3 / (float(v["size_mm"][across]) * float(v["size_mm"][2]) * 1e-6 * E)
            for v in spec["volumes"]]


def solvent_sld(x):
    """SLD of a H2O/D2O mixture with a fraction x of D2O [10⁻⁶ Å⁻²]."""
    return x * SLD["D2O"] + (1 - x) * SLD["H2O"]


def loki_cross_section(spec, q=None):
    """(q [Å⁻¹], dΣ/dΩ [cm⁻¹ sr⁻¹], truth {name: value}) of a LoKI sample; None for the empty beam."""
    import loki_samples as ls                   # (folder loki/ on the path)
    if spec.get("empty"):
        return None
    q = ls.q_grid() if q is None else np.asarray(q)
    if spec.get("empty_cell"):                  # the cell alone, with air inside: its windows scatter (almost) nothing
        return q, np.full_like(q, EMPTY_CELL_DSDO, dtype=float), dict(background=EMPTY_CELL_DSDO)
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
    thick_mm = float(spec.get("thickness_mm", 1))
    x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
    mu_rem = 0.0 if spec.get("empty_cell") else x * SOLVENT_REMOVAL["D2O"] + (1 - x) * SOLVENT_REMOVAL["H2O"]
    # the quartz windows of the cell, as the same removal spread over the thickness of the liquid (the McStas sample
    # is one slab): exp(-Σ_q · 2.5 mm) on every neutron, transmitted or scattered at small angle
    w = CELL_WINDOWS_MM / thick_mm
    return (lambda: loki_cross_section(spec), {}, thick_mm * 1e-3, QUARTZ_ABS * w, float(mu_rem) + QUARTZ_REMOVAL * w)


# --------------------------------------------------------------------------- what the student sees
def exercise_hidden(exercise_yml):
    """{sample: [hidden properties]} of an exercise (field "samples" of its exercise.yml)."""
    with open(exercise_yml, encoding="utf-8") as fh:
        ex = yaml.safe_load(fh) or {}
    return {n: (v or {}).get("hidden", []) for n, v in (ex.get("samples") or {}).items()}


def _secret_material(spec, hidden, k):
    """Whether the material of volume k is hidden from the student: "material(s)" hidden, and the volume is not the
    holder; for an operando sample (a battery) only its slices that change with time (the casing, the lithium foil...
    are no secret)."""
    v = spec["volumes"][k]
    if "material" not in hidden or v.get("holder"):
        return False
    op = spec.get("operando")
    return k in {int(i) for i in op.get("slices", [])} if op else True


def describe(instrument, spec, hidden=()):
    """Plain-text description of a sample, with the hidden properties replaced by "?" (what is to be measured)."""
    hidden = set(hidden or spec.get("hidden", []))
    if "materials" in hidden:                          # (the samples write "materials", the code tests "material")
        hidden.add("material")
    q = lambda k, txt: "?" if k in hidden else txt
    lines = [f"{spec.get('name', spec.get('id'))}" + (f"  ({spec['source']} sample)" if spec.get("source") else "")]
    if spec.get("description"):
        lines.append(spec["description"])
    if instrument == "odin" and any(v.get("shape") in ("blob", "slab") for v in spec.get("volumes", [])):
        lines += _describe_rock(spec, hidden)
    elif instrument == "odin":
        n_inc = 0
        for k, v in enumerate(spec.get("volumes", [])):
            if "inside" in v and "inclusions" in hidden:          # inclusions to be found: not described
                n_inc += 1
                continue
            mat = "?" if _secret_material(spec, hidden, k) else odin_material_label(spec, v["material"])
            sx, sy, sz = (list(v["size_mm"]) * 3)[:3] if len(v["size_mm"]) == 1 else (list(v["size_mm"]) + [0, 0])[:3]
            cx, cy, cz = v.get("center_mm", (0, 0, 0))
            at = f"centered at x = {cx:g} mm, y = {cy:g} mm" + (f", z = {cz:g} mm" if cz else "")
            shape = v.get("shape", "box")
            if v.get("holder"):
                what = {"sphere": "sphere", "cylinder": "cylinder"}.get(shape, "block")
                dims = (f"diameter {sx:g} mm" + (f", height {sy:g} mm" if shape == "cylinder" else "")
                        if shape in ("sphere", "cylinder") else f"{sx:g} × {sy:g} mm, {sz:g} mm thick")
                lines.append(f"  holder ({what}): {mat}, {dims}, {at}")
            elif shape == "sphere":
                lines.append(f"  sphere {k + 1}: {mat}, diameter {q('thickness', f'{sx:g} mm')}, {at}")
            elif shape == "cylinder":
                lines.append(f"  cylinder {k + 1}: {mat}, diameter {q('thickness', f'{sx:g} mm')}, height {sy:g} mm "
                             f"(vertical), {at}")
            else:
                lines.append(f"  block {k + 1}: {mat}, {sx:g} × {sy:g} mm, {q('thickness', f'{sz:g} mm thick')}, {at}")
        if n_inc:
            lines.append("  inclusions inside: ? (where, how many, what: to be found)")
    else:
        if spec.get("empty"):
            lines.append("  nothing in the beam")
            return "\n".join(lines)
        x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
        if spec.get("empty_cell"):
            lines.append(f"  cell of fused quartz (windows 1.25 mm), {float(spec.get('thickness_mm', 1)):g} mm gap, "
                         f"empty (air)")
            return "\n".join(lines)
        lines.append(f"  cell of fused quartz (windows 1.25 mm), {float(spec.get('thickness_mm', 1)):g} mm of solvent: "
                     f"{100 * x:.0f} % D2O / {100 * (1 - x):.0f} % H2O")
        for pop in populations(spec):
            pars = ", ".join(f"{p} {q(p, f'{float(v):g} {UNITS.get(p, "")}'.strip())}"
                             for p, v in (pop.get("parameters") or {}).items())
            lines.append(f"  particles: {q('particle', pop.get('particle', '?'))}, shape {q('model', pop['model'])}"
                         f" ({pars}), volume fraction {q('volume_fraction', f'{100 * float(pop['volume_fraction']):g} %')}")
    if hidden:
        lines.append("  ? = not given: this is what you have to measure")
    return "\n".join(lines)


def _describe_rock(spec, hidden):
    """A rock: its outline, then each phase (how many grains, how large), the hidden ones left out."""
    vols = spec.get("volumes", [])
    has_secret = any(v.get("secret") for v in vols)
    skip = set()
    if "inclusions" in hidden:
        skip = {k for k, v in enumerate(vols) if (v.get("secret") if has_secret else "inside" in v)}
        while True:
            n = len(skip)
            skip |= {k for k, v in enumerate(vols) if v.get("inside") in skip}
            if len(skip) == n:
                break
    lines, groups = [], {}
    named = spec.get("materials") or {}
    is_void = lambda n: _split_density(named.get(n, n))[0] == "void.ncmat"
    what_shape = {"box": "a block", "cylinder": "a cylinder", "sphere": "a sphere", "ellipsoid": "an ellipsoid",
                  "slab": "a sawn piece (irregular edges)"}
    for k, v in enumerate(vols):
        if k in skip:
            continue
        sx, sy, sz = (float(a) for a in v["size_mm"][:3])
        shape = v.get("shape", "box")
        label = _rock_label(spec, v["material"])
        if v.get("holder"):
            dims = (f"diameter {sx:g} mm, height {sy:g} mm" if shape == "cylinder" else
                    f"{sx:g} × {sy:g} mm, {sz:g} mm thick")
            lines.append(f"  holder ({'cylinder' if shape == 'cylinder' else 'block'}): {label}, {dims}, centered at "
                         f"y = {v['center_mm'][1]:g} mm")
        elif "inside" not in v:
            kind = what_shape.get(shape, "a lumpy piece" if v.get("wobble") else "an ellipsoid")
            dims = (f"{sx:g} mm across" if shape == "sphere" else
                    f"diameter {sx:g} mm, height {sy:g} mm" if shape == "cylinder" else
                    f"{sx:g} × {sy:g} × {sz:g} mm")
            lines.append(f"  {kind} of {label}, {dims}")
        else:
            groups.setdefault(v["material"], []).append(max(sx, sy, sz))
    for name, sizes in groups.items():
        sizes = np.array(sizes) * 1e3
        label = _rock_label(spec, name)
        if is_void(name):
            lines.append(f"  {len(sizes)} pores, {sizes.min():.0f} to {sizes.max():.0f} µm" if len(sizes) > 1 else
                         f"  1 pore, {sizes[0]:.0f} µm")
        else:
            lines.append(f"  {len(sizes)} grains of {label}, {sizes.min():.0f} to {sizes.max():.0f} µm"
                         if len(sizes) > 1 else f"  1 inclusion of {label}, {sizes[0]:.0f} µm")
    if skip:
        lines.append("  what holds the hydrogen: ? (where, how many, how much: to be found)")
    return lines


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
    if "materials" in hidden:                          # (the samples write "materials", the code tests "material")
        hidden.add("material")
    fig = fig or plt.figure(figsize=(10, 4.2))
    fig.clf()
    if instrument == "odin" and any(v.get("shape") in ("blob", "slab") for v in spec.get("volumes", [])):
        return _draw_rock(spec, hidden, fig)
    if instrument == "odin":
        # two views at the same scale, framed on the sample (and the field of view of the camera); the holder hatched
        # and behind; the legend under the views
        ink, mute, beam = "#1F2A3C", "#6B7689", "#B4562B"
        a1, a2 = fig.subplots(1, 2, gridspec_kw=dict(wspace=0.28))
        front, top = [], []                            # extents [(x0, x1, y0, y1)] of what is drawn in each view
        legend = {}
        # many small volumes (a profile drawn in slices, a map of cells): no outline each, the colors only
        thin = sum(1 for v in spec.get("volumes", []) if not v.get("holder")) > 20
        for k, v in enumerate(spec.get("volumes", [])):
            if "inside" in v and "inclusions" in hidden:      # inclusions to be found: not drawn
                continue
            secret = _secret_material(spec, hidden, k)
            sz_ = list(v["size_mm"])
            (sx, sy, sz) = (sz_ * 3)[:3] if len(sz_) == 1 else (sz_ + [0, 0])[:3]
            (cx, cy, cz) = v.get("center_mm", (0, 0, 0))
            cfg = (spec.get("materials") or {}).get(v["material"], v["material"])
            col = "#9CA3AF" if secret else ODIN_COLORS.get(_split_density(cfg)[0],
                                                          "#7C6A58" if "phases<" in cfg else "#A8A29E")
            name = "? (to be measured)" if secret else odin_material_label(spec, v["material"])
            holder = bool(v.get("holder"))
            style = (dict(fc="#EEF1F5", ec="#8A94A6", lw=1.0, hatch="////", zorder=1) if holder else
                     dict(fc=col, ec=col if thin else ink, lw=0.4 if thin else 1.1, zorder=3))
            if holder:                                 # its own name in the sample (grip steel), or its material
                name = "holder: " + (v["material"] if v["material"] in (spec.get("materials") or {})
                                     else odin_material_label(spec, v["material"]))
            shape = v.get("shape", "box")
            if shape == "sphere":                      # a disk in both views
                p1 = Circle((cx, cy), sx / 2, **style); p2 = Circle((cz, cx), sx / 2, **style)
            elif shape == "cylinder":                  # vertical: a rectangle seen by the beam, a disk from above
                p1 = Rectangle((cx - sx / 2, cy - sy / 2), sx, sy, **style); p2 = Circle((cz, cx), sx / 2, **style)
            else:
                p1 = Rectangle((cx - sx / 2, cy - sy / 2), sx, sy, **style)
                p2 = Rectangle((cz - sz / 2, cx - sx / 2), sz, sx, **style)
            a1.add_patch(p1); a2.add_patch(p2)
            legend.setdefault(name, Rectangle((0, 0), 1, 1, **{k: x for k, x in style.items() if k != "zorder"}))
            front.append((cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2))
            top.append((cz - sz / 2, cz + sz / 2, cx - sx / 2, cx + sx / 2))
        h = FIELD_MM / 2
        a1.add_patch(Rectangle((-h, -h), FIELD_MM, FIELD_MM, fill=False, ec="#2A7D6F", lw=1.8, ls=(0, (5, 3)), zorder=4))
        legend["field of view of the camera (14 mm)"] = Rectangle((0, 0), 1, 1, fill=False, ec="#2A7D6F", lw=1.8,
                                                                ls=(0, (5, 3)))
        # frames: the same mm per inch in both views, around what is drawn
        e1 = np.array(front + [(-h, h, -h, h)]); e2 = np.array(top or [(-1, 1, -1, 1)])
        f1 = [e1[:, 0].min() - 1.5, e1[:, 1].max() + 1.5, e1[:, 2].min() - 1.5, e1[:, 3].max() + 1.5]
        z0 = e2[:, 0].min() - 9.0                                         # room for the arrow of the beam
        f2 = [z0, e2[:, 1].max() + 2.0, e2[:, 2].min() - 1.5, e2[:, 3].max() + 1.5]
        a2.annotate("", xy=(e2[:, 0].min() - 0.8, 0), xytext=(z0 + 0.5, 0),
                    arrowprops=dict(arrowstyle="-|>", color=beam, lw=2), zorder=5)
        a2.text(z0 + 0.6, 0.6, "neutrons", color=beam, fontsize=9, va="bottom", zorder=5)
        a1.plot([0], [0], marker="o", ms=7, mfc="none", mec=beam, mew=1.5, zorder=6)
        a1.plot([0], [0], marker=".", ms=4, color=beam, zorder=6)
        from matplotlib.lines import Line2D
        legend["beam axis (toward you)"] = Line2D([], [], marker="o", ms=7, mfc="none", mec=beam, mew=1.5, ls="none")
        for ax, f, title, xl, yl in ((a1, f1, "Seen by the neutrons (beam's eye view)", "x [mm]", "y [mm]"),
                                     (a2, f2, "Seen from above", "z, along the beam [mm]", "x [mm]")):
            ax.set_xlim(f[0], f[1]); ax.set_ylim(f[2], f[3]); ax.set_aspect("equal")
            ax.set_title(title, fontsize=11, color=ink, loc="left", fontweight="bold")
            ax.set_xlabel(xl, color=mute, fontsize=9); ax.set_ylabel(yl, color=mute, fontsize=9)
            ax.tick_params(colors=mute, labelsize=8)
            for s_ in ax.spines.values():
                s_.set_color("#CBD2DC")
            ax.grid(alpha=0.25, lw=0.6)
            ax.set_facecolor("#FBFCFD")
        if "thickness" in hidden:
            a2.text(0.98, 0.04, "thickness: ?", transform=a2.transAxes, ha="right", color=ink, fontsize=9)
        if "inclusions" in hidden:
            a1.text(0.98, 0.03, "inclusions inside: to be found", transform=a1.transAxes, ha="right", color=mute,
                    fontsize=8.5, style="italic")
        # a sample of many cells of different compositions (a map): one entry for all of them
        kinds = [k for k in legend if not k.startswith(("holder", "field of view", "beam axis"))]
        if len(kinds) > 6:
            first = legend[kinds[0]]
            for k in kinds:
                legend.pop(k)
            legend = {f"the sample ({len(kinds)} compositions)": first, **legend}
        rows = -(-len(legend) // 3)
        fig.legend(legend.values(), legend.keys(), loc="lower center", ncol=min(3, len(legend)), frameon=False,
                   fontsize=9, handlelength=1.6, bbox_to_anchor=(0.5, 0.0))
        fig.subplots_adjust(bottom=0.16 + 0.075 * rows, top=0.9, left=0.07, right=0.98)
    else:
        ax = fig.add_subplot(1, 1, 1)
        ax.set_axis_off(); ax.set_xlim(0, 10); ax.set_ylim(0, 4.2)
        if spec.get("empty"):
            ax.text(5, 2.1, "empty beam: nothing on the sample position", ha="center", fontsize=13)
            return fig
        x = float((spec.get("solvent") or {}).get("d2o_fraction", 1.0))
        solvent = np.array([0.80, 0.90, 1.0]) * x + np.array([0.93, 0.97, 0.93]) * (1 - x)
        ax.add_patch(Rectangle((0.25, 0.35), 3.5, 3.5, fc="#E0F2FE", ec="#64748B", lw=1.5))     # the quartz cell
        ax.add_patch(Rectangle((0.4, 0.5), 3.2, 3.2, fc="white" if spec.get("empty_cell") else solvent, ec="#334155",
                               lw=1))
        ax.text(2.0, 0.05, f"quartz cell: {float(spec.get('thickness_mm', 1)):g} mm of "
                           f"{'air (empty cell)' if spec.get('empty_cell') else 'solvent'}", ha="center", fontsize=10)
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


# colors of the phases of a rock (by the name of the material in the sample), as they look on a polished face
ROCK_COLORS = {"matrix": "#4A423C", "plagioclase": "#E9E3D2", "feldspar": "#E9E3D2", "pyroxene": "#6E7F55",
               "Fe-Ti oxide": "#B9C2CC", "apatite": "#D9C38B", "pyrite": "#D4AF37", "void": "#FFFFFF",
               "H-Fe-ox clast": "#A0522D", "H-rich region": "#2563EB", "olivine": "#8DB255", "quartz": "#F2EFE6",
               "calcite": "#EFE3C8", "hematite": "#8B2E1F", "goethite": "#C9782C", "serpentine": "#2F8F6B",
               "gypsum": "#FBFAF4", "clay": "#C9A57A", "basalt": "#3F3D3B"}
# for the materials that have no color of their own: distinct colors, in turn
OTHER_COLORS = ["#0F766E", "#B45309", "#7C3AED", "#BE123C", "#0369A1", "#4D7C0F", "#A21CAF", "#92400E"]


def _rock_color(name):
    for k, c in ROCK_COLORS.items():
        if name == k or name.startswith(k) or k in name:
            return c
    return "#8C857E"


def _rock_colors(spec, names):
    """{name: color} of the materials of a rock drawing: the color of the mineral (ROCK_COLORS), of the crystal
    (ODIN_COLORS), or a distinct one."""
    named = spec.get("materials") or {}
    out, k = {}, 0
    for n in names:
        c = _rock_color(n)
        if c == "#8C857E":
            c = ODIN_COLORS.get(_split_density(named.get(n, n))[0])
        if c is None:
            c = OTHER_COLORS[k % len(OTHER_COLORS)]
            k += 1
        out[n] = c
    return out


def _rock_label(spec, name):
    """What the legend says for a material: its name, or the label of its crystal or mixture."""
    named = spec.get("materials") or {}
    if name in named and not name.endswith(".ncmat"):
        return re.sub(r" \d+$", "", name)
    return odin_material_label(spec, name)


def _draw_rock(spec, hidden, fig):
    """A natural sample (a rock): its face toward the neutrons and a horizontal cut through its middle, as phase maps
    computed from the volumes (every grain, clast and pore at its real size and shape). What an exercise hides (its
    "secret" inclusions) is drawn as the material around it."""
    from matplotlib.colors import to_rgb
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle, Rectangle
    ink, mute, beam = "#1F2A3C", "#6B7689", "#B4562B"
    vols = spec.get("volumes", [])
    has_secret = any(v.get("secret") for v in vols)
    skip = set()
    if "inclusions" in hidden:
        skip = {k for k, v in enumerate(vols) if (v.get("secret") if has_secret else "inside" in v)}
        while True:                                    # what is inside a hidden volume is hidden too
            n = len(skip)
            skip |= {k for k, v in enumerate(vols) if v.get("inside") in skip}
            if len(skip) == n:
                break
    body = [k for k, v in enumerate(vols) if not v.get("holder") and "inside" not in v]
    ext = []
    for k in body:
        c = np.asarray(vols[k].get("center_mm", (0, 0, 0)), float)
        s_ = np.asarray(vols[k]["size_mm"][:3], float)
        ext.append(np.r_[c - s_ / 2 - 0.3, c + s_ / 2 + 0.3])
    ext = np.array(ext)
    lo, hi = ext[:, :3].min(axis=0), ext[:, 3:].max(axis=0)
    step = max(0.01, float(max(hi[0] - lo[0], hi[1] - lo[1])) / 700)
    z_face = float(0.5 * (lo[2] + hi[2]))              # a cut parallel to the face, through its middle (beam along z)
    gx = np.arange(lo[0], hi[0], step)
    gy = np.arange(lo[1], hi[1], step)
    gz = np.arange(lo[2], hi[2], step / 2)
    names = []

    def phase_map(axes_pts, shape):
        lab = np.full(shape, -1, np.int32)
        for k, v in enumerate(vols):
            if k in skip or v.get("holder"):
                continue
            c = np.asarray(v.get("center_mm", (0, 0, 0)), float)
            if v.get("shape") == "slab":
                r = 0.5 * float(np.linalg.norm(v["size_mm"][:3])) + 0.3
            elif v.get("shape") == "blob":
                r = 0.5 * max(v["size_mm"][:3]) * (1 + abs(float(v.get("wobble", 0))))
            else:
                r = 0.5 * float(np.linalg.norm(np.asarray(v["size_mm"][:3], float)))
            sel, pts, shp = axes_pts(c, r)
            if sel is None:
                continue
            ins = odin_inside(v, pts).reshape(shp)
            if not ins.any():
                continue
            name = v["material"]
            if name not in names:
                names.append(name)
            lab[sel] = np.where(ins, names.index(name), lab[sel])
        return lab

    def face(c, r):                                    # plane z = z_face, grid (y, x)
        if abs(c[2] - z_face) > r:
            return None, None, None
        ix = np.where(np.abs(gx - c[0]) <= r)[0]
        iy = np.where(np.abs(gy - c[1]) <= r)[0]
        if not len(ix) or not len(iy):
            return None, None, None
        X, Y = np.meshgrid(gx[ix], gy[iy])
        return ((slice(iy[0], iy[-1] + 1), slice(ix[0], ix[-1] + 1)),
                np.c_[X.ravel(), Y.ravel(), np.full(X.size, z_face)], X.shape)

    def cut(c, r):                                     # plane y = 0, grid (x, z)
        if abs(c[1]) > r:
            return None, None, None
        ix = np.where(np.abs(gx - c[0]) <= r)[0]
        iz = np.where(np.abs(gz - c[2]) <= r)[0]
        if not len(ix) or not len(iz):
            return None, None, None
        Z, X = np.meshgrid(gz[iz], gx[ix])
        return ((slice(ix[0], ix[-1] + 1), slice(iz[0], iz[-1] + 1)),
                np.c_[X.ravel(), np.zeros(X.size), Z.ravel()], X.shape)

    m1 = phase_map(face, (len(gy), len(gx)))
    m2 = phase_map(cut, (len(gx), len(gz)))
    colors = _rock_colors(spec, names)
    pal = np.array([to_rgb(colors[n]) for n in names] + [to_rgb("#FBFCFD")])

    def rgba(m):
        img = pal[np.where(m < 0, len(names), m)]
        return np.dstack([img, np.where(m < 0, 0.0, 1.0)])

    a1, a2 = fig.subplots(1, 2, gridspec_kw=dict(wspace=0.25))
    a1.imshow(rgba(m1), extent=(gx[0], gx[-1] + step, gy[0], gy[-1] + step), origin="lower",
              interpolation="nearest", zorder=3)
    a2.imshow(rgba(m2), extent=(gz[0], gz[-1] + step / 2, gx[0], gx[-1] + step), origin="lower",
              interpolation="nearest", zorder=3)
    legend = {}
    for v in vols:                                     # the holder, hatched and behind
        if not v.get("holder"):
            continue
        c = v.get("center_mm", (0, 0, 0))
        s_ = v["size_mm"]
        style = dict(fc="#EEF1F5", ec="#8A94A6", lw=1.0, hatch="////", zorder=1)
        a1.add_patch(Rectangle((c[0] - s_[0] / 2, c[1] - s_[1] / 2), s_[0], s_[1], **style))
        if v.get("shape") == "cylinder" and abs(c[1]) <= s_[1] / 2:      # only if the cut (y = 0) goes through it
            a2.add_patch(Circle((c[2], c[0]), s_[0] / 2, **style))
        legend["holder: " + (v["material"] if v["material"] in (spec.get("materials") or {})
                             else odin_material_label(spec, v["material"]))] = Rectangle(
            (0, 0), 1, 1, **{k_: x for k_, x in style.items() if k_ != "zorder"})
    for n in names:                                    # "H-rich region 1" and "H-rich region": one entry
        legend[_rock_label(spec, n)] = Rectangle((0, 0), 1, 1, fc=colors[n], ec="#8A94A6", lw=0.5)
    h = FIELD_MM / 2
    a1.add_patch(Rectangle((-h, -h), FIELD_MM, FIELD_MM, fill=False, ec="#2A7D6F", lw=1.8, ls=(0, (5, 3)), zorder=4))
    legend["field of view of the camera (14 mm)"] = Rectangle((0, 0), 1, 1, fill=False, ec="#2A7D6F", lw=1.8,
                                                            ls=(0, (5, 3)))
    a1.plot([0], [0], marker="o", ms=7, mfc="none", mec=beam, mew=1.5, zorder=6)
    legend["beam axis (toward you)"] = Line2D([], [], marker="o", ms=7, mfc="none", mec=beam, mew=1.5, ls="none")
    hold = [v for v in vols if v.get("holder")]
    ylo = min([lo[1]] + [v["center_mm"][1] - v["size_mm"][1] / 2 for v in hold])
    f1 = [min(lo[0], -h) - 1.0, max(hi[0], h) + 1.0, min(ylo, -h) - 1.0, max(hi[1], h) + 1.0]
    z0 = lo[2] - 3.5
    f2 = [z0, hi[2] + 0.8, lo[0] - 0.5, hi[0] + 0.5]
    a2.annotate("", xy=(lo[2] - 0.1, 0), xytext=(z0 + 0.2, 0), arrowprops=dict(arrowstyle="-|>", color=beam, lw=2),
                zorder=5)
    a2.text(z0 + 0.2, 0.3, "neutrons", color=beam, fontsize=9, va="bottom", zorder=5)
    for ax, f, title, xl, yl in ((a1, f1, "Facing the neutrons: cut through its middle", "x [mm]", "y [mm]"),
                                 (a2, f2, "Cut through its middle, from above", "z, along the beam [mm]", "x [mm]")):
        ax.set_xlim(f[0], f[1])
        ax.set_ylim(f[2], f[3])
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=11, color=ink, loc="left", fontweight="bold")
        ax.set_xlabel(xl, color=mute, fontsize=9)
        ax.set_ylabel(yl, color=mute, fontsize=9)
        ax.tick_params(colors=mute, labelsize=8)
        for s_ in ax.spines.values():
            s_.set_color("#CBD2DC")
        ax.grid(alpha=0.25, lw=0.6)
        ax.set_facecolor("#FBFCFD")
    if skip:                                           # the note in the legend (inside the axes it hid the ticks)
        legend["what holds hydrogen: to be found" if any("H" in vols[k]["material"] for k in skip)
               else "inclusions inside: to be found"] = Line2D([], [], ls="none")
    rows = -(-len(legend) // 4)
    # room for the ticks, the axis labels and the legend under the two pictures, whatever size the caller asked for:
    # the legend lies below the axis labels, never over them
    height = 4.4 + 0.28 * rows
    fig.set_size_inches(10, height)
    below = (0.6 + 0.28 * rows + 0.1) / height         # ticks + label (0.6 in), legend rows, margin
    fig.legend(legend.values(), legend.keys(), loc="lower center", ncol=min(4, len(legend)), frameon=False, fontsize=9,
               handlelength=1.6, bbox_to_anchor=(0.5, 0.02))
    fig.subplots_adjust(bottom=below, top=0.92, left=0.07, right=0.98)
    return fig
