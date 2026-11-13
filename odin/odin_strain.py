"""Strain from the shift of a Bragg edge (exercise "Where is a loaded steel part strained?").

A Bragg edge sits at λ = 2d: the neutrons are scattered straight back by the lattice planes perpendicular to the beam,
d apart. Under load d becomes d (1 + ε): the edge moves to λ (1 + ε). Measured on the same region of the sample
without load (λ0) and with load (λ), the lattice strain along the beam is ε = (λ − λ0) / λ0.

    r = edge(sample_file, open_beam_file, dark_file, "gauge")  # position of the (110) edge of iron in a region
    s = strain(loaded, reference)                               # ε and its uncertainty from two such results
"""
import functools
import os
import sys

import numpy as np
import scipp as sc
from scipy.optimize import curve_fit
from scipy.special import erfc

import odin_reduction as red

EDGE_110 = 4.054                       # [Å] (110) edge of α-iron without strain (2 d_110, a = 2.8665 Å)
WINDOW = (3.60, 4.50)                  # [Å] range of the fit around the edge
BIN = 0.01                             # [Å] wavelength bins of the fit
# regions of the tensile specimen (odin/samples/steel_tensile.yml), inside each part [mm]: x0, x1, y0, y1
REGIONS = {
    "gauge": (-1.8, 1.8, -2.8, 2.8),
    "upper shoulder": (-3.8, 3.8, 3.3, 6.8),
    "lower shoulder": (-3.8, 3.8, -6.8, -3.3),
}
SECTION_MM2 = {"gauge": 20.0, "upper shoulder": 40.0, "lower shoulder": 40.0}     # width × thickness (5 mm)

def _slot(waiting):
    """A slot for a heavy operation on a server for a class (twin_slots.py, in twin/); no limit without it."""
    import contextlib
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.append(root)
    try:
        import twin_slots
    except ImportError:
        return contextlib.nullcontext()
    return twin_slots.heavy(waiting)



def edge_model(lam, lam_edge, width, base, slope, jump):
    """Transmission around an edge: a step of height `jump` at lam_edge, smoothed by the wavelength resolution of
    the instrument (Gaussian of standard deviation `width`), on a straight line."""
    return base + slope * (lam - lam_edge) + 0.5 * jump * erfc(-(lam - lam_edge) / (np.sqrt(2) * width))


@functools.lru_cache(maxsize=32)
def _counts(file, mtime):
    """The neutrons of a file, read once: counts per wavelength bin in each region, the image, duration and charge."""
    with _slot(lambda: print("Waiting: other students are reading their files (a few seconds)...")):
        return _read_counts(file)


def _read_counts(file):
    lam = sc.linspace("wavelength", WINDOW[0], WINDOW[1], int(round((WINDOW[1] - WINDOW[0]) / BIN)) + 1, unit="angstrom")
    da = red.events(file)
    ev = red._event_list(da)
    x, y = da.coords["x_pixel_offset"], da.coords["y_pixel_offset"]
    xe = sc.linspace("x", x.min().value, x.max().value, 65, unit="mm")
    ye = sc.linspace("y", y.min().value, y.max().value, 65, unit="mm")
    cx, cy = ev.coords["x"].values, ev.coords["y"].values
    out = dict(image=ev.hist(y=ye, x=xe), duration=red.duration(file), charge=red.proton_charge(file),
               lam=sc.midpoints(lam).values)
    for name, (x0, x1, y0, y1) in REGIONS.items():
        sel = sc.array(dims=["event"], values=(cx >= x0) & (cx < x1) & (cy >= y0) & (cy < y1))
        out[name] = ev[sel].hist(wavelength=lam).values.astype(float)
    return out


def counts(file):
    return _counts(file, os.path.getmtime(file))


def _norm(c):
    return c["charge"] if c["charge"] > 0 else c["duration"]


def spectrum(sample, open_beam, dark=None, region="gauge"):
    """(λ, T, dT) around the edge in a region: T = (E − N) / (O − N), the dark N scaled to the duration of each
    measurement, each measurement divided by its proton charge (as odin_reduction.reduce); Poisson error bars."""
    E, O = counts(sample), counts(open_beam)
    N = counts(dark) if dark else None
    val, var = {}, {}
    for k, c in (("E", E), ("O", O)):
        v, s2 = c[region].copy(), c[region].copy()
        if N is not None:
            f = c["duration"] / N["duration"]
            v, s2 = v - f * N[region], s2 + f * f * N[region]
        val[k], var[k] = v / _norm(c), s2 / _norm(c) ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        T = val["E"] / val["O"]
        dT = np.abs(T) * np.sqrt(var["E"] / val["E"] ** 2 + var["O"] / val["O"] ** 2)
    return E["lam"], T, dT


def transmission_image(sample, open_beam):
    """Transmission image (all wavelengths of the window around the edge), for the map."""
    E, O = counts(sample), counts(open_beam)
    return (E["image"] / _norm(E)) / (O["image"] / _norm(O))


def edge(sample, open_beam, dark=None, region="gauge"):
    """Fits the (110) edge in a region (REGIONS): dict(lam, T, dT, p, cov, lam_edge, dlam_edge, width, chi2); raises
    ValueError with a message for the student if there is no edge to fit (no steel in the beam, too few neutrons)."""
    lam, T, dT = spectrum(sample, open_beam, dark, region)
    m = np.isfinite(T) & np.isfinite(dT) & (dT > 0)
    if m.sum() < 20:
        raise ValueError("too few neutrons in this region to fit an edge: is the shutter open, the open beam chosen?")
    lo, hi = np.median(T[m][:15]), np.median(T[m][-15:])
    if hi - lo < 0.05:
        raise ValueError(f"no edge found (transmission {lo:.2f} below 4.05 Å and {hi:.2f} above): is the specimen in "
                         f"the beam (stage x = 0) for this run, and out of it for the open beam?")
    p, cov = curve_fit(edge_model, lam[m], T[m], sigma=dT[m], absolute_sigma=True,
                       p0=[EDGE_110, 0.01, lo, 0.0, hi - lo],
                       bounds=([WINDOW[0] + 0.1, 0.001, 0, -5, 0], [WINDOW[1] - 0.1, 0.1, 2, 5, 2]))
    chi2 = float(np.sum(((T[m] - edge_model(lam[m], *p)) / dT[m]) ** 2) / (m.sum() - 5))
    return dict(lam=lam[m], T=T[m], dT=dT[m], p=p, cov=cov, lam_edge=float(p[0]), dlam_edge=float(np.sqrt(cov[0, 0])),
                width=float(p[1]), chi2=chi2)


def strain(loaded, reference):
    """(ε, dε) along the beam from the edges of the same region with and without load (results of edge())."""
    l, l0 = loaded["lam_edge"], reference["lam_edge"]
    return (l - l0) / l0, float(np.hypot(loaded["dlam_edge"], reference["dlam_edge"]) / l0)


def stress_MPa(load_kN, region="gauge"):
    """Stress along the load in a region: force / cross-section."""
    return load_kN * 1e3 / SECTION_MM2[region]


def line_through_zero(x, y, dy):
    """Weighted fit y = a x (no load, no strain): (a, da)."""
    x, y, dy = (np.asarray(v, float) for v in (x, y, dy))
    w = 1.0 / dy ** 2
    return float(np.sum(w * x * y) / np.sum(w * x * x)), float(1.0 / np.sqrt(np.sum(w * x * x)))


# --------------------------------------------------------------------------- figures
def plot_edges(ax, loaded, reference, load_kN, region):
    """The two edges (reference: gray, loaded: color) with their fits, zoomed on the edge."""
    for r, c, lab in ((reference, "0.45", "without load"), (loaded, "tab:red", f"{load_kN:g} kN")):
        ax.errorbar(r["lam"], r["T"], yerr=r["dT"], fmt=".", ms=4, lw=0.6, color=c, alpha=0.8)
        x = np.linspace(r["lam"][0], r["lam"][-1], 800)
        ax.plot(x, edge_model(x, *r["p"]), color=c, lw=1.6,
                label=f"{lab}: edge at {r['lam_edge']:.4f} ± {r['dlam_edge']:.4f} Å")
        ax.axvline(r["lam_edge"], color=c, lw=0.8, ls=":")
    ax.set(xlim=(EDGE_110 - 0.12, EDGE_110 + 0.12), xlabel="λ (Å)", ylabel="transmission T",
           title=f"The (110) edge in the {region}")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)


def plot_map(ax, image, strains):
    """The transmission image with the three regions colored by their strain: {region: (ε, dε)}. Returns the
    mappable (for the colorbar)."""
    import matplotlib.pyplot as plt
    from matplotlib import cm, colors
    ax.pcolormesh(image.coords["x"].values, image.coords["y"].values, image.values, vmin=0, vmax=1.2, cmap="gray")
    vmax = max(1.0, max(abs(e) for e, _ in strains.values()) * 1e3 * 1.1)
    norm = colors.Normalize(-vmax, vmax)
    for region, (e, de) in strains.items():
        x0, x1, y0, y1 = REGIONS[region]
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fc=cm.coolwarm(norm(e * 1e3)), ec="k", lw=1.0, alpha=0.85))
        ax.text(0.5 * (x0 + x1), 0.5 * (y0 + y1), f"{e * 1e3:+.2f}\n± {de * 1e3:.2f}", ha="center", va="center",
                fontsize=10, fontweight="bold")
    ax.set(aspect="equal", xlabel="x (mm)", ylabel="y (mm)", title="Strain along the beam (10⁻³)")
    return cm.ScalarMappable(norm=norm, cmap="coolwarm")
