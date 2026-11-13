"""Reduction brick of the ODIN digital twin: the official ESS code (`essimaging`), unmodified.

The twin's NeXus files (odin_nexus.py) and those of the real ODIN go through the same workflow,
`ess.odin.OdinBraggEdgeWorkflow`: arrival time -> λ from the choppers and distances read in the file, then masks.
We only add what the workflow does not (yet) do for time-of-flight imaging:
  * subtraction of the dark run (detector background, shutter closed), scaled to the duration of each measurement;
  * normalization by the **proton charge** received by the target during the measurement
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


# Time -> λ lookup table of essreduce. "simulation": the ESS source pulse is modeled realistically (package `tof`);
# "analytical" (essimaging default): uniform emission between 0 and 5 ms. Without choppers cutting the pulse (natural
# and white modes), "analytical" assumes a mean emission time ~0.8 ms too late and gives λ 0.05 Å too small; in WFM
# mode both agree (the choppers define the time). Checked event by event, 2026-11-03 (README § 9.6).
WAVELENGTH_FROM = "simulation"


def workflow(wavelength_from=None):
    from ess import odin
    from ess.imaging.types import NeXusDetectorName
    wf = odin.OdinBraggEdgeWorkflow(wavelength_from=wavelength_from or WAVELENGTH_FROM)
    wf[NeXusDetectorName] = "timepix3"
    # the provider's generic types, set here: ess.reduce is imported only when a workflow is made
    from ess.reduce.nexus.types import DiskChoppers, RawChoppers, RunType
    _settled_choppers.__annotations__ = {"choppers": RawChoppers[RunType], "return": DiskChoppers[RunType]}
    wf.insert(_settled_choppers)
    return wf


CHOPPER_SETTINGS = ("rotation_speed_setpoint", "delay", "phase")


def _settled_choppers(choppers):
    """The DiskChoppers of essreduce (to_disk_choppers), each setting of a chopper (speed setpoint, delay, phase) first
    reduced to one value. essreduce needs one value per setting (scippneutron, "processing NeXus choppers"). A file of
    the twin has one; a file of the ESS file-writer has every value received during the job: the one already there
    at its start (as the EPICS forwarder gives it), then those of each measurement. The last one is used (the one
    of the measurement); a warning if they differ (choppers changed during the job: one job per setting, as at ESS)."""
    from ess.reduce.nexus.workflow import to_disk_choppers
    out = {}
    for name, ch in choppers.items():
        ch = ch.copy()
        for key in CHOPPER_SETTINGS:
            v = ch.get(key)
            if isinstance(v, sc.DataArray) and v.ndim == 1 and v.sizes[v.dim] > 1:
                last = v[v.dim, -1]
                if not np.allclose(v.values, last.value, rtol=1e-6, atol=0):
                    warnings.warn(f"chopper {name}: {key} changed during the measurement "
                                  f"({np.unique(v.values)}); the last value is used", stacklevel=2)
                ch[key] = last
        out[name] = ch
    return to_disk_choppers(type(choppers)(out))


def _times_ns(f):
    return [np.datetime64(f[f"entry/{k}"][()].decode().rstrip("Z"), "ns").astype(np.int64)
            for k in ("start_time", "end_time")]


PULSE_RATE = 14.0          # Hz, ESS source


def duration(file):
    """Measurement duration [s]: the source pulses recorded during the measurement (pulse_charge log between start and
    end) / 14 Hz; end_time - start_time if there is no such log. The same for a real file and for a file of the twin
    (one charge per pulse, during the whole run). For a file of the ESS file-writer it is the time the twin was
    really measuring: the job also lasts while the twin computes, with no neutrons and no pulses then."""
    import h5py
    with h5py.File(file, "r") as f:
        t0, t1 = _times_ns(f)
        log = f.get("entry/instrument/source/pulse_charge")
        if log is not None and "time" in log:
            t = log["time"][()].astype(np.int64)
            n = int(((t >= t0) & (t < t1)).sum())
            if n:
                return n / PULSE_RATE
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
        # (the last value: the one of the measurement, as _settled_choppers)
        key = [(c, float(ins[f"{c}/rotation_speed_setpoint/value"][-1])) for c in ("wfm1", "wfm2", "foc1", "foc2", "foc3",
                                                                                 "foc4", "foc5", "bpc1", "bpc2", "t0")]
        key.append(float(ins["wfm1/transformations/wfmc_translation/value"][-1]))
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


def reduce(sample, open_beam, dark=None, lam=None, roi=(-3, 3, -3, 3), n_pixels=64, normalization="charge",
           wavelength_from=None):
    """Transmission: image (all λ) and spectrum T(λ) in roi. normalization: "charge" or "duration";
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
            norm = H[k]["charge"] if normalization == "charge" and H[k]["charge"] > 0 else H[k]["duration"]
            res[k] = h / norm
        out[what] = res["E"] / res["O"]
    out["normalization"] = {k: dict(duration=v["duration"], charge_uC=v["charge"]) for k, v in H.items()}
    return out


# --------------------------------------------------------------------------- the logbook, read from the files
def data_files(folder):
    """The data files of a folder, in the order written: those of the ESS file-writer (odin_job_NNNNNN.hdf, one per
    nexusfile_open block, as at ESS) and those the twin writes itself (odin_NNNNNN.nxs, one per count: the pages of the
    BSc level, and NICOS where the file-writer does not exist)."""
    import glob
    import os
    files = glob.glob(os.path.join(folder, "odin_job_*.hdf")) + glob.glob(os.path.join(folder, "odin_[0-9]*.nxs"))
    return sorted((f.replace(os.sep, "/") for f in files), key=lambda f: (os.path.getmtime(f), f))


def _last(group, path, default=None):
    """Last value of the NXlog `path` (relative to entry/instrument): the value during the measurement. A positioner
    (e.g. spst1_lin_x) holds its NXlog in `value`."""
    import h5py
    d = group.get(f"{path}/value")
    if isinstance(d, h5py.Group):
        d = d.get("value")
    if d is None or d.shape == (0,):
        return default
    v = d[()]
    return v[-1] if np.ndim(v) else v


def _chopper_mode(ins):
    """Chopper mode (wfm, natural, white) and WFM disc separation [m], from the chopper speeds in the file."""
    import odin_nexus as nx
    turning = {c for c in nx.NEXUS_CHOPPERS if (_last(ins, f"{c}/rotation_speed_setpoint", 0.0) or 0.0) != 0.0}
    mode = next((m for m, active in nx.ACTIVE_CHOPPERS.items() if set(active) == turning), "other")
    delta = None
    if mode == "wfm":
        tr = _last(ins, "wfm1/transformations/wfmc_translation", 0.0)
        delta = round(nx.DELTA_TEMPLATE - 2 * float(tr) / 1e3, 4)
    return mode, delta


def measurements(folder):
    """The logbook of a folder, read from the data files themselves (as a user of ESS does: everything is in the
    file): one row per file, with its kind (dark: shutter closed; open beam: shutter open, sample stage far from 0;
    sample), title, duration, number of neutrons and the settings of the instrument during the measurement."""
    import os
    import h5py
    rows = []
    for path in data_files(folder):
        try:
            with h5py.File(path, "r") as f:
                e, ins = f["entry"], f["entry/instrument"]
                title = e["title"][()]
                title = title.decode() if isinstance(title, bytes) else str(title)
                shutter = _last(ins, "experiment_shutter/status", 3)
                x_mm = float(_last(ins, "spst1_lin_x", 0.0))
                rot = float(_last(ins, "spst1_rot_y", 0.0))
                pin = float(_last(ins, "pinhole_2/horizontal_gap", 0.0))
                n = len(ins["timepix3/data/event_id"]) if "timepix3/data/event_id" in ins else 0
                mode, delta = _chopper_mode(ins)
                force = e["sample/applied_force"][()] if "sample/applied_force" in e else None
        except (OSError, KeyError) as err:           # a file still being written, or not a measurement
            rows.append(dict(file=os.path.basename(path), kind="?", title=f"(not readable: {err})"))
            continue
        kind = "dark" if int(shutter) != 3 else ("open beam" if abs(x_mm) > 20 else "sample")
        rows.append(dict(file=os.path.basename(path), kind=kind, title=title, t_s=round(duration(path), 1), counts=n,
                         choppers=mode, wfm_delta_m=delta, pinhole_m=round(pin / 1e3, 4), stage_x_m=round(x_mm / 1e3, 4),
                         stage_rot_deg=round(rot, 2), **({} if force is None else {"load_kN": float(force)})))
    return rows
