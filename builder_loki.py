"""The server side of the LoKI sample builder page (builder/loki.html, served by container/twin_app.py at
/twin/builder?instrument=loki): what the page asks, as plain functions of JSON-able values (tested without a browser).

The page edits a STATE, close to a LoKI sample of sample_library (no new physics here):
    {"medium": "liquid" | "air",            # air: the empty cell (or the empty beam, without the cell)
     "d2o": 1.0,                            # D2O fraction of the H2O/D2O solvent
     "holder": {"type": "cell", "gap_mm": 1.0} | {"type": "none"},    # the quartz cell (windows: CELL_WINDOWS_MM)
     "kinds": [{"model": "sphere", "particle": "silica", "parameters": {"radius": 50}, "volume_fraction": 0.005,
                "core_particle": None}, ...]}                         # core_particle: core_shell_sphere only
and turns it into a sample spec (spec_of) that sample_library validates, computes (loki_cross_section, loki_sample)
and saves (save "loki": NICOS then finds it on the sample changer).

The properties an exercise hides (e.g. the radius and the volume fraction of silica_spheres, exercise.yml) are SEALED
as in builder_api: the page gets {"sealed": <id>} instead of the value; the value stays on the server
(TWIN_RUN_ROOT/builder/sealed/<id>.json, the id a keyed hash: a student cannot find the value by hashing guesses) and
comes back when the sample is saved (its "hidden" list kept, so NICOS still shows "?"). The views, the checks, the
models and the downloads leave out every kind of particles with a sealed value (its curve would give the answer away).
"""
import base64
import copy
import datetime
import glob
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sys

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "loki")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import builder_api as B          # noqa: E402  (run_root, data_folder, the sealed store, YAML)
import sample_library as sl      # noqa: E402

Q_RANGE = (3e-3, 0.6)            # Å⁻¹: what LoKI measures (its three detector banks, the usual settings)
LAMS = (3.0, 10.0)               # Å: a typical band of wavelengths, for the transmission
COLORS = ("#B4562B", "#2A7D6F", "#1D4ED8", "#A16207", "#7C3AED", "#BE185D")   # as sample_library.draw
MODELS = {   # model -> label, [(parameter, label, default [Å], min, max)]; the limits of sample_library.validate
    "sphere": ("Spheres", [("radius", "radius", 50.0, 5.0, 2000.0)]),
    "cylinder": ("Rods (cylinders)", [("radius", "radius", 20.0, 5.0, 2000.0), ("length", "length", 400.0, 5.0, 2000.0)]),
    "core_shell_sphere": ("Core-shell spheres", [("radius", "core radius", 50.0, 5.0, 2000.0),
                                                 ("thickness", "shell thickness", 20.0, 5.0, 2000.0)]),
}
GAP = (0.1, 5.0)                 # mm: the thickness of liquid sample_library.validate accepts
KIND_FIELDS = ("model", "particle", "core_particle", "volume_fraction")


# --------------------------------------------------------------------------- sealing the hidden values
def _secret_key():
    f = os.path.join(B._sealed_dir(), ".key")
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(32))
    return open(f, encoding="utf-8").read().strip().encode()


def _seal(field, value):
    blob = dict(kind="loki", field=field, item=value)
    sid = hmac.new(_secret_key(), json.dumps(blob, sort_keys=True).encode(), hashlib.sha256).hexdigest()[:20]
    path = os.path.join(B._sealed_dir(), sid + ".json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(blob, f)
    return {"sealed": sid}


def _is_sealed(v):
    return isinstance(v, dict) and "sealed" in v


def _unseal_value(v, field):
    if not _is_sealed(v):
        return v
    blob = B._load_sealed(v["sealed"])
    if blob.get("kind") != "loki" or blob.get("field") != field:
        raise ValueError("bad sealed value")
    return blob["item"]


def kind_sealed(k):
    """The names of the sealed properties of a kind of particles."""
    out = [f for f in KIND_FIELDS if _is_sealed(k.get(f))]
    return out + [p for p, v in (k.get("parameters") or {}).items() if _is_sealed(v)]


def hidden_of(ref, spec):
    """The properties hidden from the students for a sample: its own list, and what the exercises using it hide."""
    hidden = set(spec.get("hidden") or [])
    for f in glob.glob(os.path.join(HERE, "loki", "exercises", "*", "exercise.yml")):
        try:
            hidden |= set(sl.exercise_hidden(f).get(ref) or [])
        except Exception:                                # noqa: BLE001 (an exercise file being edited)
            pass
    return hidden


# --------------------------------------------------------------------------- state <-> sample spec
def default_kind(model="sphere"):
    return dict(model=model, particle="silica", parameters={p[0]: p[2] for p in MODELS[model][1]},
                volume_fraction=0.005, core_particle=None)


def state_of(spec, hidden=()):
    """The state of the page for a LoKI sample spec, its hidden properties sealed."""
    hidden = set(hidden or ())
    if spec.get("empty"):
        return dict(medium="air", d2o=1.0, holder=dict(type="none"), kinds=[])
    gap = float(spec.get("thickness_mm", 1.0))
    if spec.get("empty_cell"):
        return dict(medium="air", d2o=1.0, holder=dict(type="cell", gap_mm=gap), kinds=[])
    kinds = []
    for pop in sl.populations(spec):
        k = dict(model=pop["model"], particle=pop.get("particle"), parameters=dict(pop.get("parameters") or {}),
                 volume_fraction=float(pop.get("volume_fraction", 0)), core_particle=pop.get("core_particle"))
        for f in KIND_FIELDS:
            if f in hidden and k.get(f) is not None:
                k[f] = _seal(f, k[f])
        for p in list(k["parameters"]):
            if p in hidden or "model" in hidden:          # (the names of the parameters tell the model)
                k["parameters"][p] = _seal(p, k["parameters"][p])
        kinds.append(k)
    return dict(medium="liquid", d2o=float((spec.get("solvent") or {}).get("d2o_fraction", 1.0)),
                holder=dict(type="cell", gap_mm=gap), kinds=kinds)


def _clean_kind(k, unseal):
    """A kind of particles of the page as a population of sample_library (values unsealed if unseal)."""
    get = (lambda v, f: _unseal_value(v, f)) if unseal else (lambda v, f: v)
    model = get(k.get("model"), "model")
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}")
    params = {}
    for p, *_ in MODELS[model][1]:
        v = get((k.get("parameters") or {}).get(p), p)
        params[p] = round(float(v), 3)
    pop = dict(model=model, particle=get(k.get("particle"), "particle"), parameters=params,
               volume_fraction=round(float(get(k.get("volume_fraction"), "volume_fraction")), 6))
    core = get(k.get("core_particle"), "core_particle")
    if model == "core_shell_sphere" and core and core != pop["particle"]:
        pop["core_particle"] = core
    for f in ("particle", "core_particle"):
        if f in pop and pop[f] not in sl.SLD:
            raise ValueError(f"unknown material {pop[f]!r}")
    return pop


def spec_of(state, mode="open"):
    """The sample spec of a state. mode "full": the sealed values back (to save); "open": every kind of particles
    with a sealed value left out (views, checks, models, downloads)."""
    st = state or {}
    holder = (st.get("holder") or {}).get("type", "cell")
    gap = round(float((st.get("holder") or {}).get("gap_mm", 1.0)), 3)
    if st.get("medium") == "air":
        return dict(empty=True) if holder == "none" else dict(empty_cell=True, thickness_mm=gap)
    if holder == "none":
        raise ValueError("A liquid needs a cell: choose the quartz cell (step 2), or air for the empty beam.")
    kinds = [k for k in st.get("kinds") or [] if mode == "full" or not kind_sealed(k)]
    pops = [_clean_kind(k, unseal=(mode == "full")) for k in kinds]
    spec = dict(solvent=dict(d2o_fraction=round(float(st.get("d2o", 1.0)), 4)), thickness_mm=gap)
    if not pops:
        return dict(model="none", **spec)
    if len(pops) == 1:                      # the format of the library samples (the same truths as theirs)
        return dict(**pops[0], **spec)
    return dict(populations=pops, **spec)


def hidden_list(state):
    return sorted({h for k in (state or {}).get("kinds") or [] for h in kind_sealed(k)})


# --------------------------------------------------------------------------- starting points
def _template_files():
    return [(os.path.join(HERE, "loki", "templates"), "example"), (f"{B.run_root()}/templates/loki", "model")]


def starts(proposal):
    out = [dict(kind="scratch", ref="", title="From scratch", what="spheres in heavy water, to change as you like")]
    for folder, kind in _template_files():
        for f in sorted(glob.glob(os.path.join(folder, "*.yml"))):
            try:
                t = yaml.safe_load(open(f, encoding="utf-8")) or {}
            except Exception:                            # noqa: BLE001
                continue
            if not isinstance(t.get("spec"), dict):
                continue
            out.append(dict(kind=kind, ref=os.path.basename(f)[:-4], title=t.get("title") or t.get("name"),
                            what=(f"by {t['author']}" if t.get("author") else kind)))
    for n, s in sl.load("loki", B.data_folder("loki", proposal)).items():
        if s.get("source") == "student":
            out.append(dict(kind="sample", ref=n, title=s.get("name") or n, what="your sample (this proposal)"))
    for n, s in sl.load("loki").items():
        out.append(dict(kind="sample", ref=n, title=s.get("name") or n, what="sample of the library"))
    return out


def _template_file(kind, ref):
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", ref or ""):
        raise ValueError("bad name")
    folder = {k: f for f, k in _template_files()}[kind]
    return os.path.join(folder, ref + ".yml")


def load(kind, ref, proposal=""):
    """What the page needs to start from a starting point: {state (sealed), title, description, name}."""
    if kind == "scratch":
        return dict(state=dict(medium="liquid", d2o=1.0, holder=dict(type="cell", gap_mm=1.0), kinds=[default_kind()]),
                    title="", description="", name="")
    if kind in ("example", "model"):
        t = yaml.safe_load(open(_template_file(kind, ref), encoding="utf-8"))
        return dict(state=state_of(t["spec"]), title=t.get("title") or "", description=t.get("description") or "",
                    name="")
    if kind == "sample":
        lib = sl.load("loki", B.data_folder("loki", proposal))
        if ref not in lib:
            raise ValueError(f"no sample {ref}")
        s = lib[ref]
        mine = s.get("source") == "student"
        return dict(state=state_of(s, hidden_of(ref, s)), title=s.get("name", ref),
                    description=s.get("description", ""), name=ref if mine else "")
    raise ValueError(f"unknown kind {kind}")


# --------------------------------------------------------------------------- what the sample scatters
def _sig(a, n=5):
    return [float(f"{float(x):.{n}g}") for x in np.asarray(a, float)]


def transmission(spec, lam):
    """T at the wavelength lam [Å]: the removal and absorption of sample_library.loki_sample (solvent, quartz windows),
    as the McStas component applies them (mu = mu_abs λ / 1.798 + mu_rem)."""
    _, _, thick, mu_abs, mu_rem = sl.loki_sample(spec)
    return float(np.exp(-thick * (mu_abs * lam / 1.798 + mu_rem)))


def view(state):
    """The live view: dΣ/dΩ(Q) of the sample (exact, sample_library.loki_cross_section, no instrument), the share of
    each kind of particles, the flat background, the transmission; kinds with sealed values left out."""
    spec = spec_of(state, "open")
    kinds = (state or {}).get("kinds") or []
    hidden = [i for i, k in enumerate(kinds) if kind_sealed(k)] if (state or {}).get("medium") != "air" else []
    q = np.logspace(np.log10(5e-4), 0.0, 260)
    out = dict(q=_sig(q, 4), q_range=list(Q_RANGE), hidden=hidden, lams=list(LAMS))
    if spec.get("empty"):
        return dict(out, empty=True, transmission=[1.0, 1.0])
    out["transmission"] = [round(transmission(spec, lam), 4) for lam in LAMS]
    r = sl.loki_cross_section(spec, q)
    out["total"] = _sig(r[1])
    if spec.get("empty_cell"):
        return dict(out, empty_cell=True, background=float(sl.EMPTY_CELL_DSDO), kinds=[])
    bg = float(r[2]["background"])
    out["background"] = bg
    out["kinds"] = []
    open_i = [i for i, k in enumerate(kinds) if not kind_sealed(k)]
    for i in open_i:
        one = dict(_clean_kind(kinds[i], unseal=False), solvent=spec["solvent"])
        i_k = sl.loki_cross_section(one, q)[1] - bg
        out["kinds"].append(dict(index=i, color=COLORS[i % len(COLORS)], curve=_sig(np.clip(i_k, 0, None))))
    return out


# --------------------------------------------------------------------------- the traffic lights
def _rg_and_features(pop):
    """(radius of gyration [Å], the Q of the first feature after the plateau [Å⁻¹], what that feature is)."""
    p = pop["parameters"]
    if pop["model"] == "sphere":
        return np.sqrt(3 / 5) * p["radius"], 4.493 / p["radius"], "the first minimum of the sphere"
    if pop["model"] == "core_shell_sphere":
        R = p["radius"] + p["thickness"]          # (Rg of the outer sphere as if uniform: an estimate, the core
        return np.sqrt(3 / 5) * R, 4.493 / R, "the first minimum of the outer sphere"   # changes it a little)
    R, L = p["radius"], p["length"]
    return float(np.sqrt(R ** 2 / 2 + L ** 2 / 12)), 3.832 / R, "the oscillation of the cross-section (radius)"


def _nm(a):
    return f"{a:.0f} Å ({a / 10:.3g} nm)"


def check(state):
    """The traffic lights of step 3: [{status green/amber/red, title, text}]. Kinds with sealed values: not checked
    (what they are is what the exercise asks to measure)."""
    items = []
    st = state or {}
    try:
        full = spec_of(st, "full")
        errors = sl.validate("loki", full)
    except (ValueError, KeyError, TypeError) as e:
        full, errors = None, [str(e)]
    if errors:
        items.append(("red", "The twin cannot take it", "To fix: " + "; ".join(errors)))
    spec = spec_of(st, "open") if full is not None else None
    if spec is None:
        return [dict(status=s, title=a, text=b) for s, a, b in items]
    if spec.get("empty"):
        items.append(("green", "Empty beam", "Nothing on the sample position: the reference for the transmission of the "
                      "other measurements (no cell, no liquid)."))
        return [dict(status=s, title=a, text=b) for s, a, b in items]
    T = [transmission(spec, lam) for lam in LAMS]
    t = min(T)
    x = float(st.get("d2o", 1.0))
    gap = float(spec.get("thickness_mm", 1.0))
    what = ("the quartz windows (2 × 1.25 mm)" if spec.get("empty_cell") else
            f"{gap:g} mm of solvent ({100 * x:.0f} % D2O) and the quartz windows (2 × 1.25 mm)")
    txt = (f"T = {T[0]:.2f} at {LAMS[0]:g} Å, {T[1]:.2f} at {LAMS[1]:g} Å: the share of neutrons that cross {what} "
           "without being removed (the twin counts the incoherent scattering of H and the quartz; it neglects what D2O "
           "and the particles themselves remove, small for a dilute sample).")
    if t < 0.3:
        items.append(("red", "Transmission", txt + " Too thick: most neutrons are scattered more than once or lost; "
                      "a thinner gap (1 mm for H2O-rich solvents) or more D2O."))
    elif t < 0.5:
        items.append(("amber", "Transmission", txt + " Rather thick: some neutrons are scattered twice (multiple "
                      "scattering blurs the curve); a thinner gap if you can."))
    else:
        items.append(("green", "Transmission", txt))
    if spec.get("empty_cell"):
        items.append(("green", "Empty cell", "The cell alone (air between its windows): the measurement that tells "
                      "what the cell does to the beam."))
        return [dict(status=s, title=a, text=b) for s, a, b in items]
    kinds = st.get("kinds") or []
    n_hidden = sum(1 for k in kinds if kind_sealed(k))
    note = (f"{n_hidden} kind{'s' if n_hidden > 1 else ''} of particles with hidden properties: not drawn, not "
            "checked here (that is what you measure).") if n_hidden else ""
    open_pops = [_clean_kind(k, unseal=False) for k in kinds if not kind_sealed(k)]
    bg = x * sl.SOLVENT_INC["D2O"] + (1 - x) * sl.SOLVENT_INC["H2O"]
    rho_s = sl.solvent_sld(x)
    # signal and incoherent background
    if not kinds:
        items.append(("green", "Solvent alone", f"No particles: the background measurement of a SANS experiment (flat, "
                      f"{bg:.3g} cm⁻¹ sr⁻¹ of incoherent scattering, mostly from the H of H2O)."))
    elif open_pops:
        q = np.logspace(np.log10(Q_RANGE[0]), np.log10(Q_RANGE[1]), 400)
        sig = sl.loki_cross_section(spec, q)[1] - bg
        ratio = float(sig[0] / bg)
        above = q[sig > bg]
        upto = (f"; the particles scatter more than the background up to Q ≈ {above.max():.2g} Å⁻¹"
                if above.size else "")
        txt = (f"At Q = {Q_RANGE[0]:g} Å⁻¹ the particles scatter {ratio:.3g} times the flat incoherent background of the "
               f"solvent ({bg:.3g} cm⁻¹ sr⁻¹){upto}. Beyond, the curve is the background (subtracted with the solvent "
               "measurement, but its noise stays).")
        hint = " More particles, more contrast, or more D2O (H2O scatters 9 times more incoherently)."
        if ratio < 1:
            items.append(("red", "Signal over background", txt + hint))
        elif ratio < 10:
            items.append(("amber", "Signal over background", txt + hint))
        else:
            items.append(("green", "Signal over background", txt))
    # contrast
    for i, k in enumerate(kinds):
        if _is_sealed(k.get("particle")) or _is_sealed(k.get("core_particle")):
            continue
        pops = [("", k.get("particle"))]
        if k.get("model") == "core_shell_sphere" and k.get("core_particle") and k["core_particle"] != k["particle"]:
            pops = [("shell ", k["particle"]), ("core ", k["core_particle"])]
        parts, worst = [], 0.0
        for lab, m in pops:
            if m not in sl.SLD:
                continue
            d = sl.SLD[m] - rho_s
            xm = (sl.SLD[m] - sl.SLD["H2O"]) / (sl.SLD["D2O"] - sl.SLD["H2O"])
            match = (f"matched (invisible) at {100 * xm:.0f} % D2O" if 0 <= xm <= 1 else
                     "no H2O/D2O mixture matches it")
            parts.append(f"{lab}{m}: Δρ = {d:+.2f}·10⁻⁶ Å⁻² against the solvent ({rho_s:.2f}), {match}")
            worst = max(worst, abs(d))
        title = f"Contrast, kind {i + 1}"
        txt = "; ".join(parts) + ". The intensity grows as Δρ²."
        if worst < 0.3:
            items.append(("red", title, txt + " Almost no contrast: these particles are nearly invisible here; change "
                          "the D2O fraction or the material."))
        elif worst < 1.0:
            items.append(("amber", title, txt + " Weak contrast: a weak signal."))
        else:
            items.append(("green", title, txt))
    # dilute regime
    if kinds and not any(_is_sealed(k.get("volume_fraction")) for k in kinds):
        phi = sum(float(k.get("volume_fraction", 0)) for k in kinds)
        s0 = (1 - phi) ** 4 / (1 + 2 * phi) ** 2
        txt = (f"{100 * phi:.3g} % of the volume is particles. The twin adds the scattering of each particle as if alone "
               f"(no interaction). Real particles repel: for hard spheres at this fraction (Percus-Yevick) the "
               f"intensity at low Q would be {100 * (1 - s0):.0f} % lower (S(0) = {s0:.2f}); charged particles or long "
               "rods interact already at lower fractions.")
        if s0 >= 0.9:
            items.append(("green", "Dilute", txt))
        elif s0 >= 0.7:
            items.append(("amber", "Dilute?", txt + " A real sample would show it: dilute it if you want the form factor "
                          "alone."))
        else:
            items.append(("red", "Not dilute", txt + " The model no longer describes a real sample: dilute it."))
    # sizes in the Q range of LoKI
    for i, k in enumerate(kinds):
        if kind_sealed(k):
            continue
        pop = _clean_kind(k, unseal=False)
        rg, q1, feat = _rg_and_features(pop)
        title = f"Size in LoKI's range, kind {i + 1}"
        lo, hi = Q_RANGE
        eq = "≈" if pop["model"] == "core_shell_sphere" else "="
        base = (f"Q from {lo:g} to {hi:g} Å⁻¹. Radius of gyration Rg {eq} {_nm(rg)}: the Guinier plateau needs "
                f"Q·Rg < 1.3, i.e. Q < {1.3 / rg:.2g} Å⁻¹; {feat} at Q ≈ {q1:.2g} Å⁻¹.")
        guinier, feature = 1.3 / rg > lo * 1.5, q1 < hi
        if guinier and feature:
            items.append(("green", title, base + " Both are measured: the size can be fitted."))
        elif guinier:
            items.append(("amber", title, base + " Small particles: no feature in the range, only the Guinier decay "
                          "(the size from Rg, not the shape)."))
        elif feature:
            items.append(("amber", title, base + " Large particles: the Guinier plateau is below the smallest Q of LoKI; "
                          "the overall size is hard to measure (the oscillations and the Porod law Q⁻⁴ remain)."))
        else:
            items.append(("red", title, base + " Nothing to see in the range: change the size."))
    if note:
        items.append(("amber", "Hidden properties", note))
    return [dict(status=s, title=a, text=b) for s, a, b in items]


# --------------------------------------------------------------------------- thumbnails
def thumb(kind, ref, proposal="", size=150):
    """A small picture of a starting point (PNG bytes): the cell, the solvent tinted by its D2O fraction, the kinds of
    particles drawn (sizes relative to one another); hidden kinds gray with a "?". Cached on disk."""
    folder = os.path.join(B.run_root(), "builder", "thumbs")
    os.makedirs(folder, exist_ok=True)
    stamp = ""
    try:
        if kind in ("example", "model"):
            stamp = str(os.path.getmtime(_template_file(kind, ref)))
        elif kind == "sample":
            s = sl.load("loki", B.data_folder("loki", proposal)).get(ref) or {}
            stamp = str(os.path.getmtime(s["file"])) if s.get("file") and os.path.exists(s["file"]) else ""
    except OSError:
        pass
    f = os.path.join(folder, B._key("loki", kind, ref, proposal if kind == "sample" else "", stamp, size, 2) + ".png")
    if os.path.exists(f):
        return open(f, "rb").read()
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
    st = load(kind, ref, proposal)["state"]
    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_axis_off()
    fig.patch.set_facecolor("#FBFCFD")
    ax.annotate("", xy=(9.6, 5), xytext=(0.3, 5), arrowprops=dict(arrowstyle="-|>", color="#E8B9A4", lw=2))
    if st["holder"]["type"] == "cell":
        ax.add_patch(FancyBboxPatch((1.6, 0.9), 6.8, 8.2, boxstyle="round,pad=0,rounding_size=0.4", fc="#E0F2FE",
                                    ec="#5B87A8", lw=1.6))
        if st["medium"] == "liquid":
            x = float(st["d2o"])
            col = np.array([0.80, 0.90, 1.0]) * x + np.array([0.90, 0.96, 0.90]) * (1 - x)
            ax.add_patch(Rectangle((2.1, 1.4), 5.8, 7.2, fc=col, ec="#334155", lw=0.8))
        else:
            ax.add_patch(Rectangle((2.1, 1.4), 5.8, 7.2, fc="white", ec="#334155", lw=0.8))
    rng = np.random.default_rng(3)
    kinds = st["kinds"] if st["medium"] == "liquid" else []
    sizes = []
    for k in kinds:
        p = k.get("parameters") or {}
        if kind_sealed(k):
            sizes.append(None)
        else:
            sizes.append(float(p.get("radius", 50)) + float(p.get("thickness", 0)))
    big = max([s for s in sizes if s] or [1.0])
    for i, (k, s) in enumerate(zip(kinds, sizes)):
        col = "#9CA3AF" if s is None else COLORS[i % len(COLORS)]
        rr = 0.55 if s is None else float(np.clip(0.75 * (s / big) ** 0.5, 0.12, 0.75))
        n = 5 if s is None else 6
        for _ in range(n):
            c = (rng.uniform(2.9, 7.1), rng.uniform(2.2, 7.8))
            if s is None:
                ax.add_patch(Circle(c, rr, fc=col, ec="#4B5563", lw=0.6))
                ax.text(*c, "?", ha="center", va="center", fontsize=7, color="white", fontweight="bold")
            elif k["model"] == "cylinder":
                L = rr * float(np.clip(float(k["parameters"]["length"]) / float(k["parameters"]["radius"]), 1.5, 6))
                a = rng.uniform(0, np.pi)
                ax.plot([c[0] - L / 2 * np.cos(a), c[0] + L / 2 * np.cos(a)], [c[1] - L / 2 * np.sin(a), c[1] + L / 2 * np.sin(a)],
                        color=col, lw=max(1.5, 9 * rr), solid_capstyle="round")
            else:
                ax.add_patch(Circle(c, rr, fc=col, ec="#1F2937", lw=0.5))
                if k["model"] == "core_shell_sphere":
                    p = k["parameters"]
                    ax.add_patch(Circle(c, rr * float(p["radius"]) / (float(p["radius"]) + float(p["thickness"])),
                                        fc="#F5E6C8", ec="none"))
    if st["holder"]["type"] == "none":
        ax.text(5, 7.4, "empty beam", ha="center", fontsize=8, color="#5B6779")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    with open(f, "wb") as fh:
        fh.write(buf.getvalue())
    return buf.getvalue()


# --------------------------------------------------------------------------- saving
def save(proposal, name, title, description, state):
    """Saves the sample (the hidden values back, still hidden) with the proposal: NICOS finds it on the sample changer
    (move(sample_holder, name)). Returns {path, nicos}."""
    folder = B.data_folder("loki", proposal)
    if not folder:
        raise ValueError("Give your proposal number (the one applied in NICOS, Experiment panel).")
    name = (name or "").strip()
    spec = dict(name=(title or "").strip() or name, description=(description or "").strip(), **spec_of(state, "full"))
    hidden = hidden_list(state)
    if hidden:
        spec["hidden"] = hidden
    path = sl.save("loki", spec, folder, name)
    return dict(path=path, nicos=f"move(sample_holder, '{name}')   then   sample_info()")


def save_model(proposal, model, title, description, state):
    """Saves the sample as a model anyone can start from (kinds with hidden values left out)."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", model or ""):
        raise ValueError("Model name: lowercase letters, digits and _, starting with a letter (e.g. gold_rods).")
    folder = f"{B.run_root()}/templates/loki"
    path = os.path.join(folder, model + ".yml")
    author = f"proposal {proposal}" if str(proposal).strip() else "anonymous"
    if os.path.exists(path) and (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("author") != author:
        raise ValueError(f"A model {model} already exists (made by someone else): choose another name.")
    spec = spec_of(state, "open")
    t = dict(name=model, instrument="loki", title=title or model, description=description or "", author=author,
             saved=datetime.datetime.now().isoformat(timespec="minutes"), spec=spec)
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(t, f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=None)
    left = sum(1 for k in (state or {}).get("kinds") or [] if kind_sealed(k))
    return dict(path=path.replace(os.sep, "/"), left_out=left)


def download(title, description, state):
    """The sample as YAML (the format of the sample files; kinds with hidden values left out)."""
    spec = dict(name=title or "", description=description or "", **spec_of(state, "open"))
    return B.to_yaml(spec)


def info(proposal="", start=""):
    """Everything the page needs at its opening."""
    return dict(
        instrument="loki", proposal=proposal, start=start, q_range=list(Q_RANGE), lams=list(LAMS),
        sld={k: v for k, v in sl.SLD.items()}, solvent_inc=dict(sl.SOLVENT_INC),
        materials=[dict(label=k, sld=v) for k, v in sl.SLD.items() if k not in ("H2O", "D2O")],
        models=[dict(type=m, label=lab, params=[dict(key=a, label=b, default=c, min=d, max=e) for a, b, c, d, e in ps])
                for m, (lab, ps) in MODELS.items()],
        cell=dict(window_mm=sl.CELL_WINDOWS_MM / 2, gap_min=GAP[0], gap_max=GAP[1]),
        max_fraction=0.1, colors=list(COLORS), starts=starts(proposal))


# --------------------------------------------------------------------------- step 4: fit the sample to the measurements
# The sizes and volume fractions of the kinds of particles are fitted to the I(Q) measured with LoKI (the sample, the
# solvent as background, the empty beam: files of the proposal, reduced as at ESS by loki_reduction / esssans): the
# model is the cross section of the sample (sample_library.loki_cross_section) minus its flat background, plus a
# flat background fitted with it (what the subtraction of the solvent leaves).
def _lr():
    import sys
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loki")
    if p not in sys.path:
        sys.path.insert(0, p)
    import loki_reduction
    return loki_reduction


def fit_files(proposal):
    """The measurements of the proposal, with their kind (sample, solvent, empty beam)."""
    folder = B.data_folder("loki", proposal)
    if not folder or not os.path.isdir(folder):
        return dict(folder=folder, rows=[])
    rows = [r for r in _lr().measurements(folder) if r.get("kind") in ("sample", "solvent", "empty beam")]
    return dict(folder=folder, rows=rows)


def fit_params(state):
    """The numbers a fit can change: the sizes [Å] and the volume fraction of each kind of particles (not the hidden
    ones), with bounds to start from."""
    out = []
    for i, k in enumerate((state or {}).get("kinds") or []):
        if kind_sealed(k) or k.get("model") not in MODELS:
            continue
        who = f"kind {i + 1} ({k.get('particle')})"
        for p, label, _, lo, hi in MODELS[k["model"]][1]:
            v = float((k.get("parameters") or {}).get(p, 0))
            out.append(dict(key=f"{i}.parameters.{p}", label=f"{who}: {label} (Å)", value=v,
                            min=round(max(lo, v / 3), 3), max=round(min(hi, v * 3), 3)))
        vf = float(k.get("volume_fraction", 0))
        out.append(dict(key=f"{i}.volume_fraction", label=f"{who}: volume fraction", value=vf, min=0.0,
                        max=round(min(0.5, max(vf * 5, 0.01)), 4)))
    return out


def _set(state, key, v):
    i, *rest = key.split(".")
    node = state["kinds"][int(i)]
    for r in rest[:-1]:
        node = node[r]
    node[rest[-1]] = float(v)


def fit_run(proposal, state, sample, solvent, empty_beam, params):
    """Fits the chosen numbers to the measured I(Q) (rear and middle banks): values, errors, χ²/dof, a picture."""
    import matplotlib.pyplot as plt
    from scipy.optimize import least_squares
    folder = B.data_folder("loki", proposal)
    if not folder:
        raise ValueError("no proposal: open the builder from a beamtime notebook (or give its number)")

    def path(f, what):
        if not f:
            raise ValueError(f"choose the {what}")
        p = os.path.join(folder, os.path.basename(str(f)))
        if not os.path.isfile(p):
            raise ValueError(f"{f}: not in the folder of proposal {proposal}")
        return p
    if not params:
        raise ValueError("choose at least one number to fit")
    lr = _lr()
    groups = {g: lr.BANK_GROUPS[g] for g in ("rear", "middle")}
    banks = tuple(b for g in groups.values() for b in g)
    res = lr.reduce(path(sample, "sample"), background=path(solvent, "solvent (background)"),
                    empty_beam=path(empty_beam, "empty beam"), banks=banks)
    gap_cm = float(((state or {}).get("holder") or {}).get("gap_mm", 1.0)) / 10
    data = lr.combine(res, gap_cm, groups)
    q = np.concatenate([data[g][0] for g in data]); I = np.concatenate([data[g][1] for g in data])
    dI = np.concatenate([data[g][2] for g in data])
    o = np.argsort(q); q, I, dI = q[o], I[o], dI[o]
    ok = np.isfinite(I) & np.isfinite(dI) & (dI > 0)
    q, I, dI = q[ok], I[ok], dI[ok]
    if len(q) < 8:
        raise ValueError("too few points in I(Q): longer counts, or check the files")
    base = copy.deepcopy(state)                        # (the hidden kinds stay out of the model, as in the views)
    keys = [p["key"] for p in params]
    x0 = [min(max(float(next(q_["value"] for q_ in fit_params(base) if q_["key"] == k)), p["min"]), p["max"])
          for k, p in zip(keys, params)]
    lo = [float(p["min"]) for p in params] + [-abs(I).max()]
    hi = [float(p["max"]) for p in params] + [abs(I).max()]

    def model(x):
        st = copy.deepcopy(base)
        for k, v in zip(keys, x[:-1]):
            _set(st, k, v)
        spec = spec_of(st, "open")
        r = sl.loki_cross_section(spec, q)
        return r[1] - float(r[2].get("background", 0.0)) + x[-1]

    # (the page rounds the sizes to 0.001 Å: the steps of the derivatives must be larger, 0.1 %)
    fit = least_squares(lambda x: (model(x) - I) / dI, x0 + [0.0], bounds=(lo, hi), x_scale="jac", diff_step=1e-3)
    try:
        cov = np.linalg.inv(fit.jac.T @ fit.jac)
        err = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        err = np.full(len(fit.x), np.nan)
    chi2 = float((fit.fun ** 2).sum()); dof = max(1, len(q) - len(fit.x))
    lines = [f"χ² = {chi2:.4g} for {len(q)} points, {dof} degrees of freedom: χ²/dof = {chi2 / dof:.3f}"]
    for p, v, e in zip(params, fit.x, err):
        lines.append(f"  {p['label']:44s} {v:.5g} ± {e:.2g}   [{p['min']:g}, {p['max']:g}]")
    lines.append(f"  {'flat background left by the subtraction':44s} {fit.x[-1]:.3g} ± {err[-1]:.2g} cm⁻¹")
    if not fit.success:
        lines.append(f"  the fit did not converge: {fit.message}")
    fig, ax = plt.subplots(figsize=(6.2, 3.6), dpi=110)
    ax.errorbar(q, I, yerr=dI, fmt="o", ms=3, color="#1B1F24", ecolor="#9AA39A", label="measured (sample − solvent)")
    m = model(fit.x)
    ax.plot(q, np.clip(m, 1e-6, None), color="#D9480F", lw=2, label="fitted sample")
    ax.set(xscale="log", yscale="log", xlabel="Q [Å⁻¹]", ylabel="I(Q) [cm⁻¹]")
    pos = I > 0
    if pos.any():
        ax.set_ylim(max(I[pos].min() * 0.3, 1e-4), I.max() * 3)
    ax.set_title(f"χ²/dof = {chi2 / dof:.2f}", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png"); plt.close(fig)
    return dict(png=base64.b64encode(buf.getvalue()).decode(), report="\n".join(lines), chi2_red=chi2 / dof,
                success=bool(fit.success),
                values=[dict(key=k, label=p["label"], value=float(v), error=float(e)) for k, p, v, e in zip(keys, params, fit.x, err)])
