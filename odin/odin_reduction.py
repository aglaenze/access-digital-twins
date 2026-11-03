"""Reduction brick of the ODIN digital twin: the official ESS code (`essimaging`), unmodified.

The twin's NeXus files (odin_nexus.py) and those of the real ODIN go through the same workflow,
`ess.odin.OdinBraggEdgeWorkflow`: arrival time -> λ from the choppers and distances read in the file, then masks.
We only add what the workflow does not (yet) do for time-of-flight imaging:
  * subtraction of the dark run (detector background, shutter closed), scaled to the duration of each measurement;
  * normalisation by the **proton charge** received by the target during the measurement
    (`entry/instrument/source/pulse_charge`), as at ESS: the number of neutrons produced is proportional to it, while
    the source power varies (fluctuations, outages). Falls back to the duration if the log is empty;
  * division by the open beam -> transmission T(λ) and transmission image.

T = [(E - N·t_E/t_N) / Q_E] / [(O - N·t_O/t_N) / Q_O]
(E, O, N: counts of the sample, open-beam and dark runs; t: durations; Q: proton charges).
Uncertainties: Poisson noise of the three measurements, propagated by scipp.
"""
import warnings

import numpy as np
import scipp as sc

warnings.filterwarnings("ignore", category=FutureWarning, module="ess")   # numba -> scipy backend warning


# Time -> λ lookup table of essreduce. "simulation": the ESS source pulse is modelled realistically (package `tof`);
# "analytical" (essimaging default): uniform emission between 0 and 5 ms. Without choppers cutting the pulse (natural
# and white modes), "analytical" assumes a mean emission time ~0.8 ms too late and gives λ 0.05 Å too small; in WFM
# mode both agree (the choppers define the time). Checked event by event, 2026-11-03 (README § 9.6).
WAVELENGTH_FROM = "simulation"


def workflow(wavelength_from=None):
    from ess import odin
    from ess.imaging.types import NeXusDetectorName
    wf = odin.OdinBraggEdgeWorkflow(wavelength_from=wavelength_from or WAVELENGTH_FROM)
    wf[NeXusDetectorName] = "timepix3"
    return wf


def _times_ns(f):
    return [np.datetime64(f[f"entry/{k}"][()].decode().rstrip("Z"), "ns").astype(np.int64)
            for k in ("start_time", "end_time")]


def duration(file):
    """Measurement duration [s] read in the file (end_time - start_time)."""
    import h5py
    with h5py.File(file, "r") as f:
        t0, t1 = _times_ns(f)
    return (t1 - t0) * 1e-9


def proton_charge(file):
    """Proton charge [µC] received during the measurement: sum of the pulse_charge log between start and end."""
    import h5py
    with h5py.File(file, "r") as f:
        log = f["entry/instrument/source/pulse_charge"]
        q, t = log["value"][()], log["time"][()].astype(np.int64)
        t0, t1 = _times_ns(f)
    return float(q[(t >= t0) & (t < t1)].sum())


_LUTS = {}


def _chopper_fingerprint(file):
    """Chopper configuration written in the file (speed setpoints, WFM disc translation): one lookup table each."""
    import h5py
    with h5py.File(file, "r") as f:
        ins = f["entry/instrument"]
        key = [(c, float(ins[f"{c}/rotation_speed_setpoint/value"][0])) for c in ("wfm1", "wfm2", "foc1", "foc2", "foc3",
                                                                                 "foc4", "foc5", "bpc1", "bpc2", "t0")]
        key.append(float(ins["wfm1/transformations/wfmc_translation/value"][0]))
    return tuple(key)


def lookup_table(file, wavelength_from=None):
    """Time -> λ lookup table for the chopper configuration of `file`, computed once and reused for every file with
    the same configuration. Essential with "simulation": the table comes from a Monte Carlo simulation (package tof),
    and the sample and open-beam runs must use the SAME table, otherwise its noise does not cancel in E/O."""
    from ess.imaging.types import Filename, SampleRun
    from ess.reduce.unwrap.types import LookupTable
    from scippnexus import NXdetector
    mode = wavelength_from or WAVELENGTH_FROM
    key = (mode, _chopper_fingerprint(file))
    if key not in _LUTS:
        wf = workflow(mode)
        wf[Filename[SampleRun]] = file
        _LUTS[key] = wf.compute(LookupTable[SampleRun, NXdetector])
    return _LUTS[key]


def events(file, wf=None, wavelength_from=None):
    """Detector events with their λ (Å), grouped by pixel: WavelengthDetector output of the workflow."""
    from ess.imaging.types import Filename, SampleRun, WavelengthDetector
    from ess.reduce.unwrap.types import LookupTable
    from scippnexus import NXdetector
    wf = (wf or workflow(wavelength_from)).copy()
    wf[Filename[SampleRun]] = file
    wf[LookupTable[SampleRun, NXdetector]] = lookup_table(file, wavelength_from)
    da = wf.compute(WavelengthDetector[SampleRun])
    da.coords["x_pixel_offset"] = da.coords["x_pixel_offset"].to(unit="mm")
    da.coords["y_pixel_offset"] = da.coords["y_pixel_offset"].to(unit="mm")
    return da


def _event_list(da):
    """Flat list of events with λ, x, y (pixel position); events with unknown λ (WFM frame boundaries) removed."""
    ev = da.bins.concat().value
    ev = sc.DataArray(ev.data, coords={"wavelength": ev.coords["wavelength"],
                                       "x": sc.bins_like(da, da.coords["x_pixel_offset"]).bins.concat().value,
                                       "y": sc.bins_like(da, da.coords["y_pixel_offset"]).bins.concat().value})
    return ev[~sc.isnan(ev.coords["wavelength"])]


def histograms(file, lam, roi, n_pixels=64, wavelength_from=None):
    """Image (integrated over λ, n_pixels × n_pixels) and spectrum in the region roi (mm), from a single load."""
    da = events(file, wavelength_from=wavelength_from)
    ev = _event_list(da)
    x, y = da.coords["x_pixel_offset"], da.coords["y_pixel_offset"]
    xe = sc.linspace("x", x.min().value, x.max().value, n_pixels + 1, unit="mm")
    ye = sc.linspace("y", y.min().value, y.max().value, n_pixels + 1, unit="mm")
    image = ev.hist(y=ye, x=xe)
    x0, x1, y0, y1 = roi
    cx, cy = ev.coords["x"].values, ev.coords["y"].values
    spectrum = ev[sc.array(dims=["event"], values=(cx >= x0) & (cx < x1) & (cy >= y0) & (cy < y1))].hist(wavelength=lam)
    for h in (image, spectrum):
        h.variances = h.values.copy()                               # counting: variance = number of counts
    return dict(image=image, spectrum=spectrum, duration=duration(file), charge=proton_charge(file))


def reduce(sample, open_beam, dark=None, lam=None, roi=(-3, 3, -3, 3), n_pixels=64, normalisation="charge",
           wavelength_from=None):
    """Transmission: image (all λ) and spectrum T(λ) in roi. normalisation: "charge" or "duration";
    wavelength_from: "simulation" (default, WAVELENGTH_FROM) or "analytical" (essimaging default)."""
    if lam is None:
        lam = sc.linspace("wavelength", 1.0, 9.0, 201, unit="angstrom")
    H = {k: histograms(f, lam, roi, n_pixels, wavelength_from) for k, f in (("E", sample), ("O", open_beam), ("N", dark))
         if f is not None}
    out = {}
    for what in ("image", "spectrum"):
        res = {}
        for k in ("E", "O"):
            h = H[k][what]
            if "N" in H:
                h = h - H["N"][what] * (H[k]["duration"] / H["N"]["duration"])
            norm = H[k]["charge"] if normalisation == "charge" and H[k]["charge"] > 0 else H[k]["duration"]
            res[k] = h / norm
        out[what] = res["E"] / res["O"]
    out["normalisation"] = {k: dict(duration=v["duration"], charge_uC=v["charge"]) for k, v in H.items()}
    return out
