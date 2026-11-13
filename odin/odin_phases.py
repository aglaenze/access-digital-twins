"""Phase mapping from Bragg edges (exercise "Where has the fuel-cell anode been reduced?"): how much of the NiO of
an anode support has turned into Ni, region by region and pixel by pixel.

The attenuation coefficient Σ(λ) = −ln T / thickness of a support reduced to the degree r is a sum over its phases,
each in proportion to its amount: NiO in (1 − r), Ni in r, YSZ constant. So Σ(λ) is a straight line in r at every
wavelength, and so is the height of each Bragg edge (Makowska et al., ECS Trans. 68, 1103, 2015: "a linear relation
between edge heights and weight change"). Calibrated on standards of known r, the edges give r anywhere.

    c = cube(files_sample, files_open, dark)            # Σ(λ) on cells of 0.5 mm: c.sigma (n_lam, ny, nx)
    s, ds = c.region_sigma((x0, x1, y0, y1))            # Σ(λ) of a rectangle [mm]
    h = edge_heights(c.lam, s)                          # {"NiO(220)": ..., "Ni(200)": ...}
"""
import functools
import os
import sys

import numpy as np
import scipp as sc

import odin_reduction as red

THICKNESS_CM = 0.09                    # the bars: 0.9 mm along the beam
WINDOW = (2.70, 4.50)                  # [Å] the four edges of the paper are inside
BIN = 0.01                             # [Å]
CELL = 0.5                             # [mm] cells of the maps
FIELD = 7.05                           # [mm] half the field of the camera
EDGES = {"NiO(220)": 2.954, "Ni(200)": 3.524, "Ni(111)": 4.069, "NiO(200)": 4.177}
# where each edge height is read: Σ just below the edge minus Σ just above it (the two edges near 4.1 Å overlap)
# (bands of 0.15 to 0.2 Å where possible: less noise; what they include besides the edge, such as the edges of the
# zirconia near 3.6 Å, does not change with r and only shifts the calibration line)
SIDES = {"NiO(220)": ((2.75, 2.93), (2.97, 3.15)), "Ni(200)": ((3.30, 3.50), (3.54, 3.75)),
         "Ni(111)": ((3.88, 4.05), (4.09, 4.15)), "NiO(200)": ((4.09, 4.15), (4.20, 4.40))}
# bars in the holder [mm]: x0, x1, y0, y1 (inside the bars, 0.25 mm from their edges)
BARS = {"top": (-6.75, 6.75, 0.75, 6.25), "bottom": (-6.75, 6.75, -6.25, -0.75)}


def _slot(waiting):
    import contextlib
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.append(root)
    try:
        import twin_slots
    except ImportError:
        return contextlib.nullcontext()
    return twin_slots.heavy(waiting)


@functools.lru_cache(maxsize=48)
def _read(file, mtime):
    """Counts (n_lam, ny, nx) of a file on cells of CELL mm, its duration and proton charge."""
    import h5py
    with h5py.File(file, "r") as f:
        hist = "entry/instrument/camera/wavelength" in f
        if hist:                       # the histogram mode of the Timepix3 (VirtualOdin.tof_image): counts (λ, y, x)
            data = f["entry/instrument/camera/data"][()].astype(float)
            edges = f["entry/instrument/camera/wavelength"][()]
            xs = f["entry/instrument/camera/x_pixel_offset"][()] * 1e3
            ys = f["entry/instrument/camera/y_pixel_offset"][()] * 1e3
            dur, charge = float(f["entry/duration"][()]), float(f["entry/instrument/source/proton_charge"][()])
    if hist:
        n = int(round(2 * FIELD / CELL))
        ix = np.clip(((xs + FIELD) / CELL).astype(int), 0, n - 1)
        iy = np.clip(((ys + FIELD) / CELL).astype(int), 0, n - 1)
        lam_c = 0.5 * (edges[1:] + edges[:-1])
        k = (lam_c >= WINDOW[0]) & (lam_c <= WINDOW[1])
        out = np.zeros((int(k.sum()), n, n))
        sub = data[k]
        for a in range(n):
            ra = iy == a
            for b in range(n):
                out[:, a, b] = sub[:, ra][:, :, ix == b].sum(axis=(1, 2))
        return dict(counts=out, lam=lam_c[k], duration=dur, charge=charge)
    with _slot(lambda: print("Waiting: other students are reading their files (a few seconds)...")):
        lam = sc.linspace("wavelength", WINDOW[0], WINDOW[1], int(round((WINDOW[1] - WINDOW[0]) / BIN)) + 1,
                          unit="angstrom")
        da = red.events(file)
        ev = red._event_list(da)
        n = int(round(2 * FIELD / CELL))
        h = ev.hist(wavelength=lam, y=sc.linspace("y", -FIELD, FIELD, n + 1, unit="mm"),
                    x=sc.linspace("x", -FIELD, FIELD, n + 1, unit="mm"))
        return dict(counts=h.values.astype(float), lam=sc.midpoints(lam).values, duration=red.duration(file),
                    charge=red.proton_charge(file))


def counts(files):
    """The counts of one file or of several (added up, as one longer measurement)."""
    files = [files] if isinstance(files, str) else list(files)
    parts = [_read(f, os.path.getmtime(f)) for f in files]
    out = dict(parts[0])
    for p in parts[1:]:
        for k in ("counts", "duration", "charge"):
            out[k] = out[k] + p[k]
    return out


class Cube:
    """Σ(λ) on the cells of the image (n_lam, ny, nx) [cm⁻¹], from sample, open beam and dark (files or lists)."""

    def __init__(self, sample, open_beam, dark=None, thickness_cm=THICKNESS_CM):
        E, O = counts(sample), counts(open_beam)
        N = counts(dark) if dark else None
        self.lam = E["lam"]
        self.thickness = thickness_cm
        val, var = {}, {}
        for k, c in (("E", E), ("O", O)):
            v, s2 = c["counts"].copy(), c["counts"].copy()
            if N is not None:
                f = c["duration"] / N["duration"]
                v, s2 = v - f * N["counts"], s2 + f * f * N["counts"]
            norm = c["charge"] if c["charge"] > 0 else c["duration"]
            val[k], var[k] = v / norm, s2 / norm ** 2
        self.val, self.var = val, var
        n = val["E"].shape[-1]
        self.centers = -FIELD + CELL * (np.arange(n) + 0.5)

    def _mask(self, rect):
        x0, x1, y0, y1 = rect
        X, Y = np.meshgrid(self.centers, self.centers)          # rows y, columns x
        return (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)

    def region_sigma(self, rect):
        """Σ(λ) and its uncertainty in a rectangle (x0, x1, y0, y1) [mm] (the neutrons of its cells added up)."""
        m = self._mask(rect)
        E, O = self.val["E"][:, m].sum(1), self.val["O"][:, m].sum(1)
        vE, vO = self.var["E"][:, m].sum(1), self.var["O"][:, m].sum(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            T = E / O
            dT = np.abs(T) * np.sqrt(vE / E ** 2 + vO / O ** 2)
            return -np.log(T) / self.thickness, dT / T / self.thickness

    def sigma(self, block=1):
        """Σ(λ) per cell (n_lam, ny, nx), cells added up in blocks of block × block (block 2: 1 mm)."""
        E, O = self.val["E"], self.val["O"]
        if block > 1:
            k, ny, nx = E.shape
            b = lambda a: a[:, :ny // block * block, :nx // block * block].reshape(
                k, ny // block, block, nx // block, block).sum(axis=(2, 4))
            E, O = b(E), b(O)
        with np.errstate(divide="ignore", invalid="ignore"):
            return -np.log(E / O) / self.thickness


def edge_heights(lam, sigma):
    """Height of each edge: mean Σ on its short-wavelength side minus mean Σ on its long side (as Makowska et al.:
    the difference of Σ between the highest and the lowest point of the edge). sigma: (n_lam, ...)."""
    out = {}
    for k, (lo, hi) in SIDES.items():
        a = (lam >= lo[0]) & (lam <= lo[1])
        b = (lam >= hi[0]) & (lam <= hi[1])
        out[k] = np.nanmean(sigma[a], axis=0) - np.nanmean(sigma[b], axis=0)
    return out


def calibrate(r_known, heights):
    """Straight lines height = a + b r for each edge, from standards: {edge: (a, b)}."""
    r = np.asarray(r_known, float)
    return {k: tuple(np.polyfit(r, np.asarray([h[k] for h in heights], float), 1)[::-1]) for k in heights[0]}


def reduction(heights, cal, use=("NiO(220)", "Ni(200)")):
    """The reduction degree from edge heights: each edge gives r = (h − a) / b; the mean of the edges used."""
    rs = [(heights[k] - cal[k][0]) / cal[k][1] for k in use]
    return np.mean(rs, axis=0), {k: v for k, v in zip(use, rs)}


def unmix(lam, sigma, sigma_0, sigma_1, r_1, window=(2.8, 4.4)):
    """The reduction degree by fitting the whole spectrum: Σ(λ) = Σ0(λ) + r (Σ1(λ) − Σ0(λ)) / r_1, with Σ0 a standard
    at 0 % and Σ1 one at r_1 (least squares over the window; the straight line in r of the module docstring).
    sigma: (n_lam, ...)."""
    k = (lam >= window[0]) & (lam <= window[1])
    d = ((sigma_1 - sigma_0) / r_1)[k]
    y = sigma[k] - sigma_0[k].reshape((-1,) + (1,) * (sigma.ndim - 1))
    d = d.reshape((-1,) + (1,) * (sigma.ndim - 1))
    return np.nansum(d * y, axis=0) / np.nansum(d * d * np.isfinite(y), axis=0)
