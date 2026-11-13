"""Radiography and tomography with the camera images of ODIN, exercise "What is hidden inside a Martian meteorite?"
(the tomography of time-of-flight files, by wavelength band: odin_tomo.py).

    img = image(file)                                    # counts per pixel (128 x 128), its time and its angle
    T = transmission(sample, open_beam, dark)            # T = (I - D) / (O - D), each scaled to its exposure
    vol = reconstruct(files, open_beam, dark)            # filtered back-projection: Σ (cm⁻¹) in 3D, (y, z, x)

A radiograph shows the transmission T = exp(−∫Σ dl) along each line through the sample: everything along the beam is
added up. A tomography takes radiographs at many angles of the rotation stage; for each row of pixels (a horizontal
slice) the projections −ln T at all angles (the sinogram) give back Σ(x, z) of that slice by filtered back-projection:
each projection is filtered (ramp filter, |k|) and smeared back along the beam direction it was taken in.
"""
import functools
import os
import sys

import h5py
import numpy as np

PIXEL_MM = 14.1 / 128          # size of a pixel of the camera image in the sample plane [mm]

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



@functools.lru_cache(maxsize=512)
def _read(file, mtime):
    with h5py.File(file, "r") as f:
        e = f["entry"]
        return dict(data=e["instrument/camera/data"][()].astype(float), t=float(e["duration"][()]),
                    angle=float(e["sample/rotation_angle"][()]), x=float(e["sample/x_translation"][()]),
                    title=e["title"][()].decode() if isinstance(e["title"][()], bytes) else str(e["title"][()]))


def image(file):
    """dict(data (counts, rows y, columns x), t (s), angle (deg), x (m), title) of a camera file."""
    return _read(file, os.path.getmtime(file))


def transmission(sample, open_beam, dark=None):
    """T = (I − D) / (O − D), I, O and D per second of exposure."""
    I, O = image(sample), image(open_beam)
    i, o = I["data"] / I["t"], O["data"] / O["t"]
    if dark:
        D = image(dark)
        d = D["data"] / D["t"]
        i, o = i - d, o - d
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.clip(np.where(o > 0, i / o, np.nan), 1e-3, 2.0)


def extent():
    """(x0, x1, y0, y1) of the image in mm, for imshow(..., origin="lower")."""
    h = 64 * PIXEL_MM
    return (-h, h, -h, h)


def sinogram(files, open_beam, dark=None, row=None):
    """(angles, P): projections −ln T, one line per angle (all rows: P[angle, y, x]; one row: P[angle, x])."""
    angles = np.array([image(f)["angle"] for f in files])
    P = np.array([-np.log(transmission(f, open_beam, dark)) for f in files])
    P = np.nan_to_num(P)
    o = np.argsort(angles)
    angles, P = angles[o], P[o]
    return angles, (P if row is None else P[:, row, :])


FILTERS = ("none", "ramp", "ramp + Hamming window")


def fbp(angles, sino, pixel_mm=PIXEL_MM, filter="ramp + Hamming window"):
    """Filtered back-projection of one slice: sino[angle, x] (−ln T) -> Σ(z, x) in cm⁻¹ on the same pixels.
    filter: "none" (plain back-projection: blurred), "ramp" (|k|: exact, but amplifies the noise), "ramp + Hamming
    window" (|k| rolled off at high k: less noise, a little less sharp)."""
    n = sino.shape[1]
    k = np.fft.fftfreq(2 * n)
    if filter == "none":
        filt = sino
    else:
        ramp = np.abs(k) * ((0.54 + 0.46 * np.cos(2 * np.pi * k)) if "Hamming" in filter else 1.0)
        filt = np.real(np.fft.ifft(np.fft.fft(sino, 2 * n, axis=1) * ramp, axis=1))[:, :n]
    c = (np.arange(n) - (n - 1) / 2)
    X, Z = np.meshgrid(c, c)                     # pixels of the slice (rows z: along the beam at angle 0)
    out = np.zeros((n, n))
    for a, p in zip(np.radians(angles), filt):
        # a point (x, z) of the sample is seen at x' = x cos a + z sin a after a rotation of the stage by a
        s = X * np.cos(a) + Z * np.sin(a) + (n - 1) / 2
        out += np.interp(s.ravel(), np.arange(n), p, left=0, right=0).reshape(n, n)
    span = np.radians(np.ptp(angles) + np.median(np.diff(angles)))   # 180° of data: π
    return out * span / len(angles) / (pixel_mm * 0.1)                # [cm⁻¹]


def pixel_mm(n):
    """Size of a pixel of an n × n camera image in the sample plane [mm] (the field is 14.1 mm wide)."""
    return 14.1 / n


def reconstruct(files, open_beam, dark=None, rows=None, filter="ramp + Hamming window"):
    """Σ (cm⁻¹) of the sample in 3D: vol[y, z, x], one slice per row of pixels (rows: the rows to do, all by default).
    For 128 × 128 images; larger ones: Reconstruction (slices on demand)."""
    angles, P = sinogram(files, open_beam, dark)
    rows = range(P.shape[1]) if rows is None else rows
    return np.array([fbp(angles, P[:, r, :], pixel_mm=pixel_mm(P.shape[2]), filter=filter) for r in rows])


class Reconstruction:
    """Filtered back-projection of a tomography, slice by slice on demand (images of 512 × 512 pixels: the whole
    volume would take minutes and gigabytes). The projections are filtered once; a horizontal slice (one row of
    pixels, all depths) or a vertical slice (one depth, all rows) is then back-projected when asked for.

        rec = Reconstruction(files, open_beam, dark)
        rec.horizontal(y_mm)   -> Σ(z, x) [cm⁻¹], rows z, columns x
        rec.vertical(z_mm)     -> Σ(y, x) at that depth
        rec.value(x_mm, y_mm, z_mm, r_mm) -> mean Σ in a small sphere (a region of interest)
    """

    def __init__(self, files, open_beam, dark=None, filter="ramp + Hamming window"):
        angles, P = sinogram(files, open_beam, dark)
        self.n = P.shape[2]
        self.pixel = pixel_mm(self.n)
        self.angles = np.radians(angles)
        k = np.fft.fftfreq(2 * self.n)
        ramp = np.abs(k) * ((0.54 + 0.46 * np.cos(2 * np.pi * k)) if "Hamming" in filter else 1.0)
        F = np.fft.fft(P, 2 * self.n, axis=2) * ramp
        self.F = np.real(np.fft.ifft(F, axis=2))[:, :, :self.n].astype(np.float32)     # (angle, row, x')
        span = np.radians(np.ptp(angles) + np.median(np.diff(angles)))
        self.scale = span / len(angles) / (self.pixel * 0.1)
        self.mm = (np.arange(self.n) - (self.n - 1) / 2) * self.pixel                     # pixel centers [mm]

    def _row(self, y_mm):
        return int(np.clip(round(y_mm / self.pixel + (self.n - 1) / 2), 0, self.n - 1))

    def _bp(self, rows, x, z):
        """Σ at the points (x, z) [mm] of the given rows: array (len(rows), len(x))."""
        out = np.zeros((len(rows), len(x)))
        idx = np.arange(self.n)
        for a, Fa in zip(self.angles, self.F):
            s = (x * np.cos(a) + z * np.sin(a)) / self.pixel + (self.n - 1) / 2
            i0 = np.clip(np.floor(s).astype(int), 0, self.n - 2)
            f = np.clip(s - i0, 0, 1)
            ok = (s >= 0) & (s <= self.n - 1)
            Fr = Fa[rows]
            out += np.where(ok, Fr[:, i0] * (1 - f) + Fr[:, i0 + 1] * f, 0)
        return out * self.scale

    def horizontal(self, y_mm):
        X, Z = np.meshgrid(self.mm, self.mm)
        return self._bp([self._row(y_mm)], X.ravel(), Z.ravel()).reshape(self.n, self.n)

    def vertical(self, z_mm):
        return self._bp(list(range(self.n)), self.mm, np.full(self.n, z_mm))

    def value(self, x_mm, y_mm, z_mm, r_mm=0.06):
        """Mean Σ [cm⁻¹] in a small ball around (x, y, z) [mm] (a region of interest)."""
        d = np.arange(-r_mm, r_mm + 1e-9, self.pixel)
        X, Y, Z = np.meshgrid(d, d, d)
        m = X ** 2 + Y ** 2 + Z ** 2 <= r_mm ** 2
        rows = sorted({self._row(y_mm + dy) for dy in Y[m]})
        vals = []
        for r in rows:
            sel = m & (np.abs(Y + y_mm - (r - (self.n - 1) / 2) * self.pixel) <= self.pixel / 2 + 1e-9)
            if sel.any():
                vals.append(self._bp([r], x_mm + X[sel], z_mm + Z[sel])[0])
        return float(np.mean(np.concatenate(vals))) if vals else float("nan")


def effective_sigma(cfg, spectrum=None):
    """Σ [cm⁻¹] a material shows in a white-beam tomography of ODIN: Σ(λ) averaged over the white spectrum seen by
    the camera (a thin sample; spectrum: (λ, weights): VirtualOdin.camera_spectrum(); by default a cold
    Maxwellian close to the white beam of the twin).
    ICON (where NWA 7034 was measured) has a warmer spectrum (peak 1.8 Å): the same material gives a smaller value
    there; ratios between materials change much less."""
    import NCrystal as NC
    if spectrum is None:
        lam = np.linspace(1.0, 9.0, 161)
        w = lam ** -5 * np.exp(-(2.95 / lam) ** 2) * lam ** 2       # a cold Maxwellian seen by a 1/v-like camera
    else:
        lam, w = spectrum
    m = NC.load(cfg)
    sig = (m.scatter.xsect(wl=lam) + m.absorption.xsect(wl=lam)) * m.info.getNumberDensity()
    return float(np.sum(w * sig) / np.sum(w))


# --------------------------------------------------------------------------- the wavelength of the neutrons
# Two disks of 0.5 mm radius on the radiograph at stage_rot = 0 (x, y, radius in mm): the darkest spot, and the
# matrix below it, through the same thickness of meteorite (the same x: the same chord of the cylinder).
SPOT = (2.5, 2.0, 0.5)
MATRIX = (2.5, -2.1, 0.5)
WINDOW = (1.2, 7.8)            # [Å] wavelengths of the WFM beam used
BIN = 0.1                      # [Å]


@functools.lru_cache(maxsize=16)
def _region_counts(file, mtime, regions):
    with _slot(lambda: print("Waiting: other students are reading their files (a few seconds)...")):
        return _read_region_counts(file, regions)


def _read_region_counts(file, regions):
    import scipp as sc
    import odin_reduction as red
    lam = sc.linspace("wavelength", WINDOW[0], WINDOW[1], int(round((WINDOW[1] - WINDOW[0]) / BIN)) + 1,
                      unit="angstrom")
    ev = red._event_list(red.events(file))
    cx, cy = ev.coords["x"].values, ev.coords["y"].values
    out = dict(lam=sc.midpoints(lam).values, duration=red.duration(file), charge=red.proton_charge(file))
    for k, (x0, y0, r) in enumerate(regions):
        sel = sc.array(dims=["event"], values=(cx - x0) ** 2 + (cy - y0) ** 2 < r * r)
        out[k] = ev[sel].hist(wavelength=lam).values.astype(float)
    return out


def region_transmission(sample, open_beam, dark=None, regions=(SPOT, MATRIX)):
    """(λ, [T of each region], [dT]) from time-of-flight files (Timepix3): T = (E − N) / (O − N) per proton charge."""
    def c(f):
        return _region_counts(f, os.path.getmtime(f), tuple(regions))
    E, O = c(sample), c(open_beam)
    N = c(dark) if dark else None
    norm = lambda m: m["charge"] if m["charge"] > 0 else m["duration"]
    Ts, dTs = [], []
    for k in range(len(regions)):
        v, s2 = {}, {}
        for key, m in (("E", E), ("O", O)):
            a, var = m[k].copy(), m[k].copy()
            if N is not None:
                f = m["duration"] / N["duration"]
                a, var = a - f * N[k], var + f * f * N[k]
            v[key], s2[key] = a / norm(m), var / norm(m) ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            T = v["E"] / v["O"]
            dT = np.abs(T) * np.sqrt(s2["E"] / v["E"] ** 2 + s2["O"] / v["O"] ** 2)
        Ts.append(T)
        dTs.append(dT)
    return E["lam"], Ts, dTs


def sigma_water(lam):
    """Σ(λ) of liquid water (cm⁻¹, NCrystal), the reference for hydrogen."""
    import NCrystal as NC
    m = NC.load("LiquidWaterH2O_T293.6K.ncmat")
    lam = np.asarray(lam, float)
    return (m.scatter.xsect(wl=lam) + m.absorption.xsect(wl=lam)) * m.info.getNumberDensity()
