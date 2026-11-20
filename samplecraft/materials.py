"""Materials: what each body is made of, as an NCrystal configuration, with where it comes from.

A material of a scene is one of
    {ncrystal: "Fe_sg229_Iron-alpha.ncmat"}                  a crystal (or any NCrystal configuration)
    {formula: "Fe2O3", density: 5.26}                        a composition at a density (g/cm³): no Bragg edge
    {minerals: {plag: 85, afs: 15}}                          rock-forming minerals by volume (MINERALS)
    {mix: {water: 0.2, quartz: 0.8}}                         other materials of the scene, by volume fraction
    {calibrate: {base: <material>, add: <material>, sigma_cm: 1.9, wavelength_A: 1.8}}
                                                             the fraction of `add` that gives the measured Σ
and may add  density_factor: 0.9 (pores, less than compact),  temperature_K,  source: "where the numbers come from".
Σ_tot(λ) = (σ_scatter + σ_absorption) × number density, from NCrystal.
"""
import re

import numpy as np

ELEM = {"H": 1.008, "C": 12.011, "O": 15.999, "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974,
        "S": 32.06, "Cl": 35.45, "K": 39.098, "Ca": 40.078, "Ti": 47.867, "Fe": 55.845}
# atoms per formula unit, density [g/cm³] (common values of mineralogy handbooks)
MINERALS = {
    "plag": (dict(Na=0.5, Ca=0.5, Al=1.5, Si=2.5, O=8.0), 2.69),       # plagioclase An50
    "opx": (dict(Mg=1.2, Fe=0.8, Si=2.0, O=6.0), 3.55),                # orthopyroxene
    "cpx": (dict(Ca=0.9, Mg=0.7, Fe=0.4, Si=2.0, O=6.0), 3.40),        # clinopyroxene
    "ol": (dict(Mg=1.6, Fe=0.4, Si=1.0, O=4.0), 3.32),                 # olivine Fo80
    "mag": (dict(Fe=3.0, O=4.0), 5.15),                                # magnetite
    "magh": (dict(Fe=2.0, O=3.0), 4.90),                               # maghemite
    "hem": (dict(Fe=2.0, O=3.0), 5.26),                                # hematite
    "ilm": (dict(Fe=1.0, Ti=1.0, O=3.0), 4.72),                        # ilmenite
    "afs": (dict(Na=1.0, Al=1.0, Si=3.0, O=8.0), 2.62),                # alkali feldspar (albite)
    "ap": (dict(Ca=5.0, P=3.0, O=12.0, Cl=1.0), 3.15),                 # chlorapatite
    "py": (dict(Fe=1.0, S=2.0), 5.01),                                 # pyrite
    "qz": (dict(Si=1.0, O=2.0), 2.65),                                 # quartz
    "cc": (dict(Ca=1.0, C=1.0, O=3.0), 2.71),                          # calcite
    "gt": (dict(Fe=1.0, O=2.0, H=1.0), 4.27),                          # goethite FeO(OH)
    "srp": (dict(Mg=3.0, Si=2.0, O=9.0, H=4.0), 2.55),                 # serpentine Mg3Si2O5(OH)4
    "gyp": (dict(Ca=1.0, S=1.0, O=6.0, H=4.0), 2.32),                  # gypsum CaSO4·2H2O
    "kln": (dict(Al=2.0, Si=2.0, O=9.0, H=4.0), 2.60),                 # kaolinite Al2Si2O5(OH)4
}
WATER = "stdlib::LiquidWaterH2O_T293.6K.ncmat"


def solid(vol):
    """NCrystal configuration (solid::, no Bragg edge: a fine-grained mineral or mixture) of minerals by volume."""
    vt = sum(vol.values())
    mass, rho = {}, 0.0
    for k, v in vol.items():
        at, d = MINERALS[k]
        f = v / vt
        rho += f * d
        m = {el: n * ELEM[el] for el, n in at.items()}
        tot = sum(m.values())
        for el, w in m.items():
            mass[el] = mass.get(el, 0.0) + f * d * w / tot
    tot = sum(mass.values())
    at = {el: w / tot / ELEM[el] for el, w in mass.items()}
    mn = min(at.values())
    return "solid::" + "".join(f"{el}{max(1, int(round(v / mn * 10)))}" for el, v in at.items()) + f"/{rho:.3f}gcm3"


def formula_cfg(formula, density):
    """solid:: of a chemical formula (e.g. 'Fe2O3', 'CaSO4H4O2') at a density [g/cm³]."""
    parts = re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", formula)
    if not parts or "".join(e + n for e, n in parts) != formula:
        raise ValueError(f"formula {formula!r}: elements and counts, e.g. Fe2O3")
    counts = {}
    for e, n in parts:
        counts[e] = counts.get(e, 0) + (float(n) if n else 1.0)
    mn = min(counts.values())
    return "solid::" + "".join(f"{e}{max(1, int(round(c / mn * 10)))}" for e, c in counts.items()) + \
        f"/{float(density):.4g}gcm3"


_SIG = {}


def sigma(cfg, wavelength_A):
    """Σ_tot [1/cm] of an NCrystal configuration at wavelengths [Å] (array)."""
    import NCrystal as NC
    lam = np.atleast_1d(np.asarray(wavelength_A, float))
    if cfg not in _SIG:
        if len(_SIG) > 200:
            _SIG.clear()
        _SIG[cfg] = NC.load(cfg)
    m = _SIG[cfg]
    if cfg.startswith("void"):
        return np.zeros_like(lam)
    return np.asarray(m.scatter.xsect(wl=lam) + m.absorption.xsect(wl=lam)) * m.info.getNumberDensity()


def resolve(materials):
    """{name: NCrystal configuration} of the materials of a scene (mixtures and calibrations resolved in order) and
    {name: note} (how each was obtained)."""
    cfg, notes = {}, {}
    todo = dict(materials)
    for _ in range(len(todo) + 1):
        for name in list(todo):
            spec = todo[name]
            try:
                c, note = _one(spec, cfg)
            except KeyError:
                continue                                  # needs a material not resolved yet
            cfg[name], notes[name] = c, note
            todo.pop(name)
        if not todo:
            return cfg, notes
    raise ValueError(f"materials that cannot be resolved (unknown names, or a loop): {sorted(todo)}")


def _with_density(c, spec):
    f = float(spec.get("density_factor", 1.0))
    if not 0 < f <= 1.0 + 1e-9:
        raise ValueError("density_factor: between 0 and 1")
    if abs(f - 1) > 1e-12:
        c = f"{c};density={f:g}x"
    if spec.get("temperature_K"):
        c = f"{c};temp={float(spec['temperature_K']):g}K"
    return c


def _one(spec, known):
    if isinstance(spec, str):
        return spec, "NCrystal configuration"
    if "ncrystal" in spec:
        return _with_density(spec["ncrystal"], spec), spec.get("source", "NCrystal")
    if "formula" in spec:
        return _with_density(formula_cfg(spec["formula"], spec["density"]), spec), \
            spec.get("source", f"composition {spec['formula']}, {spec['density']} g/cm³")
    if "minerals" in spec:
        return _with_density(solid(spec["minerals"]), spec), \
            spec.get("source", "minerals by volume: " + ", ".join(f"{k} {v}" for k, v in spec["minerals"].items()))
    if "mix" in spec:
        parts = [(known[n], float(f)) for n, f in spec["mix"].items()]
        tot = sum(f for _, f in parts)
        c = "phases<" + "&".join(f"{f / tot:.6g}*{x}" for x, f in parts) + ">"
        return _with_density(c, spec), spec.get("source", "mixture by volume of " + ", ".join(spec["mix"]))
    if "calibrate" in spec:
        cal = spec["calibrate"]
        base = known[cal["base"]] if isinstance(cal["base"], str) and cal["base"] in known else _one(cal["base"], known)[0]
        add = known[cal["add"]] if isinstance(cal.get("add", "water"), str) and cal.get("add", "water") in known \
            else (WATER if cal.get("add", "water") == "water" else _one(cal["add"], known)[0])
        target, lam = float(cal["sigma_cm"]), float(cal.get("wavelength_A", 1.8))
        mix = lambda w: f"phases<{1 - w:.6f}*{base}&{w:.6f}*{add}>"
        s0 = float(sigma(base, lam)[0])
        if s0 >= target:
            return base, f"Σ({lam:g} Å) of the base, {s0:.3f} cm⁻¹, already above the target {target:g}: base kept"
        lo, hi = 0.0, 0.95
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if sigma(mix(mid), lam)[0] < target else (lo, mid)
        w = 0.5 * (lo + hi)
        return mix(w), spec.get("source", "") + f" [calibrated: {100 * w:.3f} % by volume added so that " \
                                                 f"Σ({lam:g} Å) = {target:g} cm⁻¹]"
    raise ValueError(f"material: unknown form {spec!r}")
