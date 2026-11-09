"""File-writing brick of the ODIN digital twin: simulated neutrons -> measured counts -> NeXus file in ESS format.

At ESS, the detector sends its events (pixel, arrival time) to Kafka, and the "file writer" stores them in a NeXus
file together with the state of the whole instrument (choppers, motors, shutter...). The ESS reduction packages
(here `essimaging`) read these files.

Here we produce the same file from a McStas simulation, following the method of the scipp team
(`essimaging/tools/mcstas_to_nexus.ipynb`): we start from a **real ODIN file written by the ESS data acquisition
system** (template shipped with `essimaging`, "CODA" profile) and replace only:
  * the events of the Timepix3 detector (`entry/instrument/timepix3/data`);
  * the detector position (sample -> detector distance);
  * the state of the devices the twin can set (stages, pinhole, shutter, diffuser, choppers);
  * the proton charge of each pulse, the title, the sample name, start and end times.
Everything else (geometry, source, ~4700 device logs) is that of the real instrument.

From McStas weights to measured counts (same model as the EventCamera of the ODIN notebook series, but event by event):
  * a simulated neutron i carries an intensity w_i [n/s]; during t_exp it produces on average
    m_i = w_i · t_exp · ε(λ_i) counts (ε: scintillator efficiency);
  * the number of counts follows a Poisson law;
  * Gaussian position blur (light spread in the scintillator), then a uniform background (gamma rays, fast neutrons).
"""
import datetime as _dt
import os
import shutil
import sys

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import odin_paths as paths                      # noqa: E402  (sets sys.path)

H_OVER_M = 3956.034          # m·Å/s
PULSE_HZ = 14.0              # ESS pulse frequency
DET = "entry/instrument/timepix3"


def template_file():
    """Path of the template: the real ODIN file shipped with `essimaging` (downloaded once), recompressed once with
    h5repack (gzip level 1: 172 MB -> 35 MB, mostly the 4096 × 4096 pixel-number table and the ~4700 device logs).
    Same content; falls back to the raw file if h5repack is not available."""
    import subprocess
    import ess.odin.data
    raw = str(ess.odin.data.iron_simulation_ob_small())
    gz = os.path.join(paths.RUN_ROOT, "template", "odin_template_gzip.nxs")
    if os.path.isfile(gz):
        return gz
    h5repack = shutil.which("h5repack") or os.path.join(os.path.dirname(sys.executable), "Library", "bin",
                                                         "h5repack.exe")
    if not os.path.isfile(h5repack):
        return raw
    os.makedirs(os.path.dirname(gz), exist_ok=True)
    r = subprocess.run([h5repack, "-f", "GZIP=1", raw, gz + ".tmp"], capture_output=True)
    if r.returncode != 0:
        return raw
    os.replace(gz + ".tmp", gz)
    return gz


def detector_geometry(template=None):
    """Pixel grid of the template's Timepix3: (x edges, y edges [m], detector_number[ix, iy])."""
    with h5py.File(template or template_file(), "r") as f:
        xo = f[f"{DET}/x_pixel_offset"][()]
        yo = f[f"{DET}/y_pixel_offset"][()]
        num = f[f"{DET}/detector_number"][()]
    dx, dy = xo[1] - xo[0], yo[1] - yo[0]
    return np.r_[xo - dx / 2, xo[-1] + dx / 2], np.r_[yo - dy / 2, yo[-1] + dy / 2], num


def efficiency(lam, lam_abs=8.0):
    """ε(λ) = 1 - exp(-λ/λ_abs): absorption in the scintillator (cf. ODIN notebook 03, §3)."""
    return 1.0 - np.exp(-np.asarray(lam, dtype=float) / lam_abs)


def _background(out, t_exp, field, rate, pixel, rng):
    """Uniform background: `rate` counts/s per pixel² area (1 mm² by default), uniform in time. λ = NaN."""
    x0, x1, y0, y1 = field
    nb = rng.poisson(rate * t_exp * (x1 - x0) * (y1 - y0) / pixel ** 2)
    out["x"] = np.r_[out["x"], rng.uniform(x0, x1, nb).astype(np.float32)]
    out["y"] = np.r_[out["y"], rng.uniform(y0, y1, nb).astype(np.float32)]
    out["t"] = np.r_[out["t"], rng.uniform(0, 1 / PULSE_HZ, nb)]
    out["lam"] = np.r_[out["lam"], np.full(nb, np.nan, dtype=np.float32)]
    return out


def sample_counts(ev, t_exp, lam_abs=8.0, blur_m=0.1e-3, background=0.05, background_pixel=1e-3, field=None, rng=None):
    """Draws the counts "measured" during t_exp [s] from simulated events held in memory.

    ev: dict of arrays (x, y [m], t [s], lam [Å], w [n/s]), cf. odin_mcstas.read_mcpl(light=True).
    Returns dict (x, y, t [s, time since the emitting pulse, as in McStas], lam [Å, true; NaN for background]).
    """
    rng = rng or np.random.default_rng()
    m = np.asarray(ev["w"], dtype=float) * t_exp * efficiency(ev["lam"], lam_abs)
    total = m.sum()
    n = rng.poisson(total) if total > 0 else 0
    idx = rng.choice(len(m), size=n, p=m / total) if n > 0 else np.zeros(0, dtype=int)
    out = dict(x=(ev["x"][idx] + rng.normal(0, blur_m, n)).astype(np.float32),
               y=(ev["y"][idx] + rng.normal(0, blur_m, n)).astype(np.float32),
               t=np.asarray(ev["t"])[idx].astype(float), lam=np.asarray(ev["lam"])[idx].astype(np.float32))
    if background > 0 and field is not None:
        out = _background(out, t_exp, field, background, background_pixel, rng)
    out.update(n_mcstas=len(m), mc_factor=1.0)
    return out


def counts_from_mcpl(path, t_exp, lam_abs=8.0, blur_m=0.1e-3, background=0.05, background_pixel=1e-3, field=None,
                     rng=None, chunk=5_000_000, beam_factor=1.0, copies=1):
    """Like sample_counts(), but reads the McStas event file chunk by chunk (bounded memory).

    Each simulated event i gives k_i ~ Poisson(m_i) counts, m_i = w_i · t_exp · ε(λ_i): exactly the same law as
    "N ~ Poisson(Σ m), then multinomial draw", without loading everything.

    Statistical quality: the true variance of a sum of counts is Σ m_i (Poisson, as on the real instrument)
    + Σ m_i² (Monte Carlo noise: the same simulated neutron counted several times, unequal weights).
    copies: number of copies (repeat) of each upstream neutron; they share λ and time, so their counts are
      correlated; upper bound (Cauchy-Schwarz): mc_factor = sqrt(1 + copies · Σ m² / Σ m), the factor by which the
      Poisson error bars are underestimated (~1: behaves like the real detector; > 1.2: count too long).
    beam_factor: mean proton charge of the useful pulses / nominal charge (the background does not depend on it).
    """
    import odin_mcstas as tw
    rng = rng or np.random.default_rng()
    parts = {k: [] for k in ("x", "y", "t", "lam")}
    s1 = s2 = 0.0
    n_mc = 0
    for ev in tw.iter_mcpl(path, light=True, chunk=chunk):
        m = ev["w"].astype(float) * (t_exp * beam_factor) * efficiency(ev["lam"], lam_abs)
        s1 += m.sum()
        s2 += (m * m).sum()
        n_mc += len(m)
        k = rng.poisson(m)
        idx = np.repeat(np.nonzero(k)[0], k[k > 0])
        n = len(idx)
        parts["x"].append((ev["x"][idx] + rng.normal(0, blur_m, n)).astype(np.float32))
        parts["y"].append((ev["y"][idx] + rng.normal(0, blur_m, n)).astype(np.float32))
        parts["t"].append(ev["t"][idx].astype(np.float64))
        parts["lam"].append(ev["lam"][idx].astype(np.float32))
    out = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in parts.items()}
    if background > 0 and field is not None:
        out = _background(out, t_exp, field, background, background_pixel, rng)
    out.update(n_mcstas=n_mc, expected_counts=s1, mc_factor=float(np.sqrt(1 + copies * s2 / s1)) if s1 > 0 else 1.0)
    return out


# --------------------------------------------------------------------------- source
Q_NOMINAL = 2e6 / (2e9 * PULSE_HZ) * 1e6     # µC per pulse: 2 MW, 2 GeV protons, 14 Hz (≈ 71.4 µC)


def pulse_charges(t_exp, rng=None, nominal=Q_NOMINAL, fluctuation=0.01, outages=()):
    """Proton charge of each pulse during t_exp [µC]: nominal value (power of the McStas model), Gaussian relative
    fluctuation from pulse to pulse, and beam outages [(start s, duration s), ...]."""
    rng = rng or np.random.default_rng()
    n = int(round(t_exp * PULSE_HZ))
    q = nominal * np.clip(1 + fluctuation * rng.standard_normal(n), 0, None)
    tk = np.arange(n) / PULSE_HZ
    for t0, d in outages:
        q[(tk >= t0) & (tk < t0 + d)] = 0.0
    return q


# --------------------------------------------------------------------------- NeXus helpers
def _replace(grp, name, values, compress=False):
    """Replaces a dataset, keeping its attributes (units...). compress: gzip level 1, chunked (large event arrays;
    read transparently by h5py, scippnexus, essimaging)."""
    attrs = dict(grp[name].attrs)
    del grp[name]
    values = np.asarray(values)
    if compress and values.size > 10_000:
        d = grp.create_dataset(name, data=values, compression="gzip", compression_opts=1,
                               chunks=(min(values.size, 1 << 20),), shuffle=True)
    else:
        d = grp.create_dataset(name, data=values)
    d.attrs.update(attrs)


def _write_log(f, path, value, t_ns):
    """Writes a constant value into a NeXus device (NXlog `value`, and `target_value` if present)."""
    if path not in f:
        raise KeyError(f"device not found in the template: {path}")
    g = f[path]
    # Two forms in ESS files: a plain NXlog (e.g. shutter/status), or an NXpositioner holding the NXlogs
    # "value" (readback) and "target_value" (setpoint).
    logs = [g] if isinstance(g.get("value"), h5py.Dataset) else \
        [g[s] for s in ("value", "target_value") if isinstance(g.get(s), h5py.Group) and "value" in g[s]]
    if not logs:
        raise KeyError(f"nothing to write in {path}")
    for log in logs:
        dt = log["value"].dtype
        n_old = log["value"].shape[0] if log["value"].ndim else 1
        for k in list(log.keys()):        # alarms, connection states...: same length as value -> 1 entry
            o = log[k]
            if (k not in ("value", "time") and isinstance(o, h5py.Dataset) and o.ndim == 1
                    and o.shape[0] == n_old and n_old != 1):
                _replace(log, k, o[:1])
        _replace(log, "value", np.array([value], dtype=dt))
        _replace(log, "time", np.array([t_ns], dtype=log["time"].dtype))
        for k in ("average_value", "minimum_value", "maximum_value"):
            if k in log:
                _replace(log, k, np.array(value, dtype=log[k].dtype))


# --------------------------------------------------------------------------- chopper modes
# Chopper names in the ODIN file (template); McStas model names (odin_mcstas.ALL_CHOPPERS):
# wfm1 = wfm_1, wfm2 = wfm_2, foc1..5 = foc_1..5, bpc1/bpc2 = bp_1/bp_2, t0 = t0.
NEXUS_CHOPPERS = ("wfm1", "wfm2", "foc1", "bpc1", "foc2", "bpc2", "t0", "foc3", "foc4", "foc5")
ACTIVE_CHOPPERS = {"wfm": NEXUS_CHOPPERS, "natural": ("bpc1", "bpc2", "t0"), "white": ()}
# Source pulses per frame: the band-pass choppers (7 Hz) let only one pulse in two through
PULSES_PER_FRAME = {"wfm": 2, "natural": 2, "white": 1}
DELTA_TEMPLATE = 0.45   # [m] WFM disc separation when the wfmc_translation stage is at 0 (template: 6.775 and 7.225 m)
_CHOPPER_TEMPLATE = {}


def chopper_template():
    """{chopper: (speed setpoint [Hz], delay [ms])} read from the real ODIN file used as template for the NeXus files:
    the values the choppers have when they turn (the same in every mode; the twin does not compute new phases)."""
    if not _CHOPPER_TEMPLATE:
        with h5py.File(template_file(), "r") as f:
            for c in NEXUS_CHOPPERS:
                g = f[f"entry/instrument/{c}"]
                _CHOPPER_TEMPLATE[c] = (abs(float(g["rotation_speed_setpoint/value"][0])),
                                        float(g["delay/value"][0]) * 1e-6)
    return _CHOPPER_TEMPLATE


def chopper_readings(mode, wfm_delta=0.30):
    """Read-only values shown by NICOS for a chopper mode: speed [Hz] and delay [ms] of each chopper (0 when stopped),
    pulses used and wavelength band."""
    out = {}
    for c, (speed, delay) in chopper_template().items():
        on = c in ACTIVE_CHOPPERS[mode]
        out[f"{c}_speed"] = speed if on else 0.0
        out[f"{c}_delay"] = round(delay, 4) if on else 0.0
    out["pulse_skipping"] = ("1 pulse in 2 (band-pass choppers at 7 Hz)" if PULSES_PER_FRAME[mode] == 2
                             else "none: every pulse, frames overlap")
    out["wfmc_separation"] = wfm_delta if mode == "wfm" else 0.0
    return out


READINGS_HELP = {
    "speed": ("Hz", "rotation speed of the chopper (0: stopped, out of the beam)"),
    "delay": ("ms", "opening delay of the chopper after the source pulse"),
    "pulse_skipping": ("", "source pulses used"),
    "wfmc_separation": ("m", "separation of the two WFM discs (0: WFM choppers stopped)"),
}


def chopper_settings(mode, wfm_delta=0.30):
    """Settings to write into the NeXus file for a chopper mode (paths relative to entry/instrument).

    * stopped chopper: speed (and setpoint) zero -> the reduction treats it as open, like the McStas model where a
      disabled chopper is removed from the beam;
    * WFM mode: separation δ of the two WFM discs, set by the translation stage. The field description in the ESS
      file is ambiguous ("the readback is the change in WFM disc separation; each disc moves by only half of it, but
      the wfm1 and wfm2 transformations apply the full value"). We write half of it, (0.45 - δ)/2, in both
      transformations so that the geometry is right (checked: positions read back by the reduction), and the change
      in separation (0.45 - δ) in the wfmc_translation device. To be confirmed with the ODIN team.
    """
    if mode not in ACTIVE_CHOPPERS:
        raise ValueError(f"unknown chopper mode: {mode}")
    out = {}
    for c in NEXUS_CHOPPERS:
        if c not in ACTIVE_CHOPPERS[mode]:
            out[f"{c}/rotation_speed"] = 0.0
            out[f"{c}/rotation_speed_setpoint"] = 0.0
            out[f"{c}/in_phase"] = 0
    if mode == "wfm":
        half_mm = (DELTA_TEMPLATE - wfm_delta) / 2 * 1e3
        out["wfm1/transformations/wfmc_translation"] = half_mm
        out["wfm2/transformations/wfmc_translation"] = half_mm
        out["wfmc_translation"] = 2 * half_mm
    return out


# --------------------------------------------------------------------------- writing
def write_nexus(counts, out_file, t_exp, start=None, det_dist=0.05, title="ODIN digital twin", sample_name="",
                settings=None, template=None, charge=None, pulses_per_frame=2):
    """Writes an ODIN NeXus file (ESS format) containing the measured counts.

    counts: output of sample_counts() / counts_from_mcpl(); t = time since the emitting pulse [s] (McStas time).
    t_exp: measurement duration [s]; start: UTC datetime of the start (now by default).
    det_dist: sample -> scintillator distance [m] (the sample is at the origin of the ODIN NeXus frame).
    settings: dict {NeXus device path (relative to entry/instrument): value}, e.g. {"spst1_lin_x": 0.0}.
    charge: proton charge of each pulse [µC] (pulse_charges()); written to entry/instrument/source/pulse_charge.

    Time: at ESS, each event is stamped with the time of the previous pulse (event_time_zero, 14 Hz) and the time
    elapsed since (event_time_offset < 71.4 ms). A neutron emitted by pulse k (at k/14 s) arrives at k/14 + t. With
    the pulse-skipping band-pass choppers (7 Hz), the McStas simulation covers two pulses (t counted from the first):
    each count gets a random frame of 2 pulses (pulses_per_frame = 2). Without choppers (white beam), every pulse
    emits: frames of 1 pulse; slow neutrons then arrive after the next pulse (frame overlap, as on the real
    instrument).
    """
    template = template or template_file()
    start = start or _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    t0_ns = int(start.timestamp() * 1e9)
    ex, ey, num = detector_geometry(template)
    ix = np.searchsorted(ex, counts["x"]) - 1
    iy = np.searchsorted(ey, counts["y"]) - 1
    ok = (ix >= 0) & (ix < len(ex) - 1) & (iy >= 0) & (iy < len(ey) - 1)
    rng = np.random.default_rng(int(t0_ns % 2**32))
    ppf = int(pulses_per_frame)
    n_frames = max(int(t_exp * PULSE_HZ / ppf), 1)
    if charge is None:
        frame = rng.integers(0, n_frames, ok.sum())
    else:
        # Beam neutrons follow the charge of the pulse that produced them (pulse ppf·c of frame c; with the band-pass
        # choppers, the other one is stopped); the background (λ = NaN) is spread uniformly.
        qf = np.asarray(charge, float)[0:ppf * n_frames:ppf]
        bkg = np.isnan(counts["lam"][ok])
        frame = np.empty(ok.sum(), dtype=np.int64)
        frame[bkg] = rng.integers(0, n_frames, bkg.sum())
        frame[~bkg] = rng.choice(n_frames, size=(~bkg).sum(), p=qf / qf.sum()) if qf.sum() > 0 else 0
    t_abs_ns = frame * (ppf * 1e9 / PULSE_HZ) + counts["t"][ok] * 1e9
    period_ns = 1e9 / PULSE_HZ
    k = np.floor(t_abs_ns / period_ns).astype(np.int64)
    order = np.argsort(t_abs_ns, kind="stable")
    k = k[order]
    # whole nanoseconds after the pulse time written in event_time_zero (rounded to the ns too), as at ESS (ev44:
    # int32 ns): the files of the ESS file-writer then hold exactly the same numbers
    eto = np.maximum(np.round(t_abs_ns[order]) - np.round(k * period_ns), 0).astype(np.int32)
    ids = num[ix[ok], iy[ok]][order].astype(np.int32)
    # One entry per pulse of the measurement (including pulses without neutrons, like the real system)
    n_pulses = int(round(t_exp * PULSE_HZ))
    k_all = np.arange(max(n_pulses, k.max() + 1 if len(k) else 1))
    index = np.searchsorted(k, k_all).astype(np.int64)
    etz = (t0_ns + np.round(k_all * period_ns)).astype(np.int64)
    end_ns = t0_ns + int(t_exp * 1e9)

    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    shutil.copyfile(template, out_file)
    with h5py.File(out_file, "r+") as f:
        d = f[f"{DET}/data"]
        _replace(d, "event_id", ids, compress=True)
        unit = d["event_time_offset"].attrs.get("units", b"ns")
        assert (unit.decode() if isinstance(unit, bytes) else unit) == "ns"
        _replace(d, "event_time_offset", eto, compress=True)
        _replace(d, "event_index", index, compress=True)
        _replace(d, "event_time_zero", etz, compress=True)
        _replace(f[f"{DET}/transformations"], "translation", np.float64(det_dist))
        e = f["entry"]
        iso = lambda ns: _dt.datetime.fromtimestamp(ns / 1e9, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for name, val in (("title", title), ("start_time", iso(t0_ns)), ("end_time", iso(end_ns)),
                          ("experiment_description", "ACCESS digital twin (McStas simulation)")):
            _replace(e, name, val.encode())
        if sample_name:
            _replace(e["sample"], "name", sample_name.encode())
        for path, val in (settings or {}).items():
            _write_log(f, f"entry/instrument/{path}", val, t0_ns)
        if charge is not None:
            # Proton charge of each pulse (µC), stamped like event_time_zero (ESS f144 log)
            log = f["entry/instrument/source/pulse_charge"]
            q = np.asarray(charge, dtype=log["value"].dtype)[:len(etz)]
            _replace(log, "value", q)
            _replace(log, "time", etz[:len(q)].astype(log["time"].dtype))
            for k_, v_ in (("average_value", q.mean()), ("minimum_value", q.min()), ("maximum_value", q.max())):
                if k_ in log:
                    _replace(log, k_, np.array(v_, dtype=log[k_].dtype))
            for k_ in ("alarm_message", "alarm_severity", "alarm_time", "connection_status", "connection_status_time"):
                if k_ in log:           # arrays of the template's length: emptied
                    _replace(log, k_, log[k_][:0])
    # McStas "truth" in file order (to validate the reduction; does not exist on the real instrument)
    truth = dict(event_id=ids, event_time_offset_ns=eto, lam=counts["lam"][ok][order])
    return dict(file=out_file, n_counts=int(ok.sum()), outside=int((~ok).sum()), n_pulses=len(k_all), truth=truth)
