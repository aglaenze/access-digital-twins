"""NeXus event files of the LoKI twin, in the format of the real LoKI at ESS.

The template is a real file written by the ESS file writer at LoKI (April 2026, 5 pulses), distributed by ESS with
esssans (`ess.loki.data.loki_coda_file()`, downloaded once from public.esss.dk). We keep its whole structure (9
detector banks with their real pixel geometry, 5 beam monitors, choppers, motors, logs) and replace:

  * the detector events: each neutron scattered by the sample in the twin (McStas) goes in a straight line to the
    real pixel its path crosses (first bank met, beam stop absorbs); event_time_offset = arrival time after the
    source pulse, event_time_zero = time of the pulse (ESS convention, 14 Hz);
  * the monitor events: incident monitor m1 (8.4 m before the sample) and transmission monitor m3 (0.2 m after it),
    from the McStas beam at the sample position (efficiency 1e-3);
  * the settings (choppers, detector carriage, title, sample, times) and an `entry/twin` group with the truth
    (sample model, configuration) that a real file does not have;
  * the users of the template file are removed (privacy).

Data volume: LoKI counts millions of neutrons per second (4·10⁹ in 10 min for the silica spheres), i.e. tens of GB
of events. A twin file holds at most MAX_EVENTS events: a random sample of the neutrons, at the SAME rate for the
detector and the monitors (`entry/twin/event_sampling`, e.g. 1/400). Everything normalized by the monitors (I(Q) in
absolute units, transmission) is therefore unchanged; only the counting noise is that of the events in the file.
"""
import datetime
import os
import shutil

import h5py
import numpy as np

H_OVER_M = 3956.034            # m·Å/s
PERIOD = 1 / 14                # time between two ESS pulses [s]
MAX_EVENTS = 1e7               # detector events per file at most (80 MB)
MAX_MONITOR_EVENTS = 2e6       # events per monitor and file at most
CHUNK = 2_000_000              # neutrons mapped to pixels at a time (memory)
MONITOR_EFFICIENCY = 1e-3      # m1 and m3
MONITORS = {"beam_monitor_m1": -8.4, "beam_monitor_m3": 0.2}   # position along the beam relative to the sample [m]
BANKS = [f"loki_detector_{i}" for i in range(9)]
REAR_Z0 = 5.00483              # z [m] of the first layer of the rear bank when the detector carriage reads 0
BEAMSTOP = 0.07                # side of the beam stop [m], 1 mm in front of the rear detector (as in loki_mcstas)
TUBE_PITCH = 0.0284            # distance between two tubes of a layer [m] (template file)


def template():
    """Path of the real LoKI file (downloaded on first use, then cached by pooch)."""
    from ess.loki.data import loki_coda_file
    return str(loki_coda_file())


# --------------------------------------------------------------------------- real pixel geometry
class RealDetector:
    """Pixels of the 9 banks of the real LoKI (positions in the frame of the sample, from the template file), and
    which pixel each scattered neutron hits."""

    def __init__(self, reardet=5.0):
        from scipy.spatial import cKDTree
        self.reardet = reardet
        self.carriage = reardet - REAR_Z0                     # detector carriage reading [m]
        self.banks = {}
        with h5py.File(template(), "r") as f:
            ins = f["entry/instrument"]
            for b in BANKS:
                g = ins[b]
                off = np.stack([g[c][()] for c in ("x_pixel_offset", "y_pixel_offset", "z_pixel_offset")], 1)
                if b == "loki_detector_0":                     # on the detector carriage
                    t = ins["detector_carriage/transformations/detector_carriage_zero"]
                    origin = t.attrs["vector"] * t[()] + np.array([0, 0, self.carriage])
                else:
                    t = g["transformations"]
                    t = t[list(t)[0]]
                    origin = t.attrs["vector"] * t[()]
                pos = (off + origin).astype(np.float64)
                r = np.linalg.norm(pos, axis=1)
                u = pos / r[:, None]
                tree = cKDTree(u)
                # sub-detectors: one layer and one straw position of every tube. Seen from the sample, the 4 layers
                # of tubes and the 7 straws of a tube overlap; each sub-detector covers the bank once, without overlap
                from ess.loki.workflow import DETECTOR_BANK_SIZES
                sz = DETECTOR_BANK_SIZES[b]
                n_pix = len(pos) // (sz["layer"] * sz["tube"] * sz["straw"])
                i = np.arange(len(pos))
                sub = (i // (sz["tube"] * sz["straw"] * n_pix)) * sz["straw"] + (i // n_pix) % sz["straw"]
                subsets = [np.nonzero(sub == k)[0] for k in range(sz["layer"] * sz["straw"])]
                self.banks[b] = dict(ids=g["detector_number"][()].astype(np.uint32), pos=pos, r=r, tree=tree,
                                     # coverage: a direction belongs to the bank if a pixel is closer than 0.3 tube
                                     # pitch seen from the sample (about the edge of the outermost straws)
                                     tol=0.3 * TUBE_PITCH / np.median(r), margin=0.6 * TUBE_PITCH / np.median(r),
                                     box=(u[:, 0].min(), u[:, 0].max(), u[:, 1].min(),
                                                                   u[:, 1].max()),
                                     subsets=subsets, subtrees=[cKDTree(u[k]) for k in subsets],
                                     L=float(np.median(pos[:, 2])))    # distance of the bank along the beam [m]

    def hit(self, x, y, z, ux, uy, uz, rng=None):
        """(bank index or -1, pixel id, flight path sample -> pixel [m]) of each neutron (straight line).
        The bank is the first one the neutron meets (beam stop: -1). rng given: the neutron is detected in one of the
        overlapping sub-detectors of that bank (a layer and a straw position, drawn at random), in its pixel closest
        to the direction of flight; each pixel then receives neutrons in proportion to its solid angle, as the ESS
        reduction assumes. rng None: the pixel closest to the direction among all (used for the masks)."""
        n = len(x)
        best = np.full(n, np.inf)
        bank = np.full(n, -1)
        pix = np.zeros(n, np.uint32)
        u = np.column_stack([ux, uy, uz])
        r0 = np.column_stack([x, y, z])
        ueff = {}
        for k, b in enumerate(BANKS):
            d = self.banks[b]
            # direction from the center of the sample to the point where the neutron reaches the bank (it starts
            # anywhere in the beam): the pixels are looked up in this direction
            p = r0 + u * (d["L"] / np.where(u[:, 2] > 1e-6, u[:, 2], 1e-6))[:, None]
            ue = p / np.linalg.norm(p, axis=1)[:, None]
            ueff[k] = ue
            x0, x1, y0, y1 = d["box"]
            m = ((ue[:, 0] >= x0 - d["tol"]) & (ue[:, 0] <= x1 + d["tol"]) & (ue[:, 1] >= y0 - d["tol"])
                 & (ue[:, 1] <= y1 + d["tol"]) & (u[:, 2] > 0))
            idx = np.nonzero(m)[0]
            if not len(idx):
                continue
            dist, j = d["tree"].query(ue[idx], distance_upper_bound=d["tol"])
            ok = np.isfinite(dist)
            idx, j = idx[ok], j[ok]
            path = np.linalg.norm(d["pos"][j] - r0[idx], axis=1)
            closer = path < best[idx]                         # the first bank met catches the neutron
            idx, j, path = idx[closer], j[closer], path[closer]
            best[idx], bank[idx], pix[idx] = path, k, d["ids"][j]
        # beam stop (square, 1 mm in front of the rear bank)
        with np.errstate(divide="ignore", invalid="ignore"):
            sb = (self.reardet - 0.001 - z) / uz
        xb, yb = x + sb * ux, y + sb * uy
        bank[(np.abs(xb) < BEAMSTOP / 2) & (np.abs(yb) < BEAMSTOP / 2) & (sb > 0) & (sb < best)] = -1
        if rng is not None:
            for k, b in enumerate(BANKS):
                d = self.banks[b]
                idx = np.nonzero(bank == k)[0]
                which = rng.integers(0, len(d["subsets"]), len(idx))
                for s_ in np.unique(which):
                    ii = idx[which == s_]
                    _, j = d["subtrees"][s_].query(ueff[k][ii])
                    j = d["subsets"][s_][j]
                    pix[ii] = d["ids"][j]
                    best[ii] = np.linalg.norm(d["pos"][j] - r0[ii], axis=1)
        return bank, pix, best


    def hidden_ids(self, bank, half_beam=0.005):
        """Detector numbers of the pixels of `bank` to mask: those the sample does not see (behind the beam stop or a
        closer bank, seen from the center or a corner of the beam, ±half_beam), and those within a margin of 0.6 tube
        pitch of such a region or of the edge of the bank. Each pixel collects the neutrons of a band one tube pitch
        wide across the tubes (the four layers and seven straws overlap): near an edge, part of that band is missing.
        As the instrument team masks the beam stop and the bank edges on the real LoKI."""
        d = self.banks[bank]
        k = BANKS.index(bank)
        hidden = np.zeros(len(d["ids"]), bool)
        u0 = d["pos"] / d["r"][:, None]
        rays = [(x0, y0, 0.0, 0.0) for x0, y0 in [(0.0, 0.0)] + [(sx * half_beam, sy * half_beam)
                                                               for sx in (-1, 1) for sy in (-1, 1)]]
        rays += [(0.0, 0.0, dx * d["margin"], dy * d["margin"]) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        for x0, y0, dx, dy in rays:
            v = d["pos"] - np.array([x0, y0, 0.0])
            u = v / np.linalg.norm(v, axis=1)[:, None] + np.array([dx, dy, 0.0])
            u /= np.linalg.norm(u, axis=1)[:, None]
            b, _, _ = self.hit(np.full(len(u), x0), np.full(len(u), y0), np.zeros(len(u)), u[:, 0], u[:, 1], u[:, 2])
            hidden |= b != k
        return d["ids"][hidden]


# --------------------------------------------------------------------------- events
def _draw(rng, w, n):
    """n indices drawn with probability ∝ w."""
    if n <= 0 or w.sum() <= 0:
        return np.zeros(0, int)
    c = np.cumsum(w)
    return np.minimum(np.searchsorted(c, rng.random(n) * c[-1]), len(w) - 1)


def _pulses(rng, toa, duration, stride):
    """Absolute arrival times -> (pulse index, offset after that pulse [ns]). Each neutron comes from a random source
    pulse among those let through by the choppers (one in `stride`)."""
    n_pulses = max(1, int(round(duration / PERIOD)))
    k = stride * rng.integers(0, max(1, n_pulses // stride), len(toa))
    a = k * PERIOD + toa
    j = np.floor(a / PERIOD).astype(np.int64)
    keep = j < n_pulses
    j, a = j[keep], a[keep]
    off = np.round((a - j * PERIOD) * 1e9).astype(np.uint32)
    return j, off, keep, n_pulses


def sampling_fraction(scattered, beam, duration, rate=1.0):
    """Fraction of the neutrons written as events, the same for the detector and the monitors: at most MAX_EVENTS
    detector events and MAX_MONITOR_EVENTS per monitor."""
    det = scattered["w"].sum() * duration * rate
    mon = beam["w"].sum() * MONITOR_EFFICIENCY * duration * rate
    return min(1.0, MAX_EVENTS / det if det > 0 else 1.0, MAX_MONITOR_EVENTS / mon if mon > 0 else 1.0)


def detector_events(rng, scattered, det, duration, sampling, stride):
    """{bank: (pulse index, offset [ns], pixel id)} for a count of `duration` s, a fraction `sampling` of the neutrons
    kept. scattered: neutrons after the sample (loki_mcstas.scattered), weights in n/s."""
    n = rng.poisson(scattered["w"].sum() * duration * sampling)
    i_all = _draw(rng, scattered["w"], n)
    banks, pixs, toas = [], [], []
    for c in range(0, len(i_all), CHUNK):             # by chunks: memory
        i = i_all[c:c + CHUNK]
        s = {k: scattered[k][i] for k in ("x", "y", "z", "ux", "uy", "uz", "t", "lam")}
        bank, pix, path = det.hit(s["x"], s["y"], s["z"], s["ux"], s["uy"], s["uz"], rng=rng)
        hit = bank >= 0                               # the others miss all banks or end in the beam stop
        banks.append(bank[hit]); pixs.append(pix[hit])
        toas.append(s["t"][hit] + path[hit] / (H_OVER_M / s["lam"][hit]))
    bank, pix, toa = (np.concatenate(banks) if banks else np.zeros(0, int)),         (np.concatenate(pixs) if pixs else np.zeros(0, np.uint32)), (np.concatenate(toas) if toas else np.zeros(0))
    j, off, keep, n_pulses = _pulses(rng, toa, duration, stride)
    bank, pix = bank[keep], pix[keep]
    return {b: (j[bank == k], off[bank == k], pix[bank == k]) for k, b in enumerate(BANKS)}, n_pulses


def monitor_events(rng, beam, transmission, duration, sampling, stride):
    """{monitor: (pulse index, offset [ns])}: m1 sees the incident beam, m3 the beam transmitted by the sample.
    beam: neutrons at the sample position (loki_mcstas.read_mcpl), transmission: function λ -> T."""
    out = {}
    for name, dz in MONITORS.items():
        w = beam["w"] * (transmission(beam["lam"]) if dz > 0 else 1.0)
        n = rng.poisson(w.sum() * MONITOR_EFFICIENCY * duration * sampling)
        i = _draw(rng, w, n)
        toa = beam["t"][i] + (dz - beam["z"][i]) / (H_OVER_M / beam["lam"][i])
        j, off, _, _ = _pulses(rng, toa, duration, stride)
        out[name] = (j, off)
    return out


# --------------------------------------------------------------------------- writing
def _replace(g, name, data, attrs=None):
    old = dict(g[name].attrs) if name in g else {}
    if name in g:
        del g[name]
    g.create_dataset(name, data=data)
    for k, v in (attrs if attrs is not None else old).items():
        g[name].attrs[k] = v


def _event_group(g, pulse, offset, ids, n_pulses, start_ns):
    order = np.argsort(pulse, kind="stable")
    pulse, offset, ids = pulse[order], offset[order], ids[order]
    _replace(g, "event_time_zero", (start_ns + np.round(np.arange(n_pulses) * PERIOD * 1e9)).astype(np.uint64))
    _replace(g, "event_index", np.searchsorted(pulse, np.arange(n_pulses)).astype(np.uint32))
    _replace(g, "event_time_offset", offset.astype(np.uint32))
    _replace(g, "event_id", ids.astype(np.uint32))
    _replace(g, "cue_index", np.zeros(0, np.uint32))
    _replace(g, "cue_timestamp_zero", np.zeros(0, np.uint64))


def _log(g, value, t_ns):
    """An NXlog with a single value at time t_ns (the setting during the whole measurement)."""
    v = np.asarray([value], dtype=g["value"].dtype if g["value"].dtype.kind == "f" else np.float64)
    _replace(g, "value", v)
    _replace(g, "time", np.array([t_ns], dtype=np.uint64))
    for k in ("average_value", "minimum_value", "maximum_value"):
        if k in g:
            _replace(g, k, np.float64(value))


def _text(g, name, s):
    if name in g:
        del g[name]
    g.create_dataset(name, data=s, dtype=h5py.string_dtype())


def write(path, det_events, mon_events, n_pulses, start, duration, title, sample_name, settings, choppers, carriage,
          twin_info, l1):
    """Copies the template and writes the measurement. start: datetime (UTC); settings: {device: value} written in
    entry/twin; choppers: {nexus chopper name: (speed [Hz], delay [ms])}; carriage: detector carriage [m]."""
    shutil.copy(template(), path)
    start_ns = int(start.timestamp() * 1e9)
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    with h5py.File(path, "r+") as f:
        e = f["entry"]
        for k in [k for k in e if k.startswith("user_")]:            # no real users in the twin's files
            del e[k]
        _text(e, "title", title)
        _text(e, "start_time", iso(start))
        _text(e, "end_time", iso(start + datetime.timedelta(seconds=duration)))
        _text(e, "experiment_identifier", str(twin_info.get("proposal", "")))
        _text(e["sample"], "name", sample_name)
        ins = e["instrument"]
        for b in BANKS:
            j, off, ids = det_events[b]
            _event_group(ins[f"{b}/detector_events"], j, off, ids, n_pulses, start_ns)
        for m in ("beam_monitor_m0", "beam_monitor_m1", "beam_monitor_m2", "beam_monitor_m3", "beam_monitor_m4"):
            g = ins[f"{m}/monitor_events"]
            mid = int(g["event_id"][0]) if len(g["event_id"]) else 1
            j, off = mon_events.get(m, (np.zeros(0, int), np.zeros(0, np.uint32)))
            _event_group(g, j, off, np.full(len(j), mid, np.uint32), n_pulses, start_ns)
        # source at the distance of the McStas model (L1), so that the flight paths match the wavelength table
        src = ins["source/transformations"]
        src[list(src)[0]][...] = l1
        _log(ins["detector_carriage/value"], carriage * 1000.0, start_ns)          # mm, as in the real file
        _log(ins["detector_carriage/target_value"], carriage * 1000.0, start_ns)
        for c, (speed, delay) in choppers.items():
            g = ins[c]
            _log(g["rotation_speed"], speed, start_ns)
            _log(g["rotation_speed_setpoint"], speed, start_ns)
            _log(g["delay"], delay * 1e6, start_ns)                                  # ns
        for k in ("heavy_shutter", "experiment_shutter"):
            if k in ins and "value" in ins[k]:
                _log(ins[f"{k}/value"], 1.0, start_ns)
        tw = e.require_group("twin")
        tw.attrs["NX_class"] = "NXcollection"
        tw.attrs["description"] = ("Digital twin of LoKI (McStas). Not in a real file: the settings of the twin, the "
                                   "true sample, and the fraction of the neutrons written as events.")
        for k, v in {**settings, **twin_info}.items():
            if isinstance(v, str):
                _text(tw, k, v)
            else:
                _replace(tw, k, v, {})
    return path


def read_twin(path):
    """entry/twin of a twin file, as a dict."""
    with h5py.File(path, "r") as f:
        g = f["entry/twin"]
        return {k: (g[k].asstr()[()] if g[k].dtype.kind in "OS" else g[k][()]) for k in g}
