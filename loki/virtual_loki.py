"""Virtual LoKI (first version): a small-angle scattering measurement with the McStas model of LoKI.

    from virtual_loki import VirtualLoki
    loki = VirtualLoki(session="test")
    loki.move(sample="silica_spheres", heavy_shutter="open", shutter="open")
    f = loki.count(600, title="silica spheres")      # 10 min; returns an HDF5 file with I(Q) per detector bank

What it does: McStas upstream part (official model, precomputed, cached), McStas downstream part for the sample
(cached), detection by the 9 tube panels, time of flight -> λ -> Q, reduction to I(Q) in absolute units with the
counting noise of a measurement of `t` seconds (Gaussian approximation of the Poisson noise per Q bin, plus the
simulation noise). Same interface as VirtualOdin (devices, move, count, scan, status), so the twin server and
NICOS drive it the same way. Not yet: raw event files in the ESS NeXus format, reduction with the ESS software
(esssans), the dark/empty-cell/solvent measurements of a real SANS experiment. See README.md.
"""
import datetime
import hashlib
import json
import os

import h5py
import numpy as np

import loki_paths as paths
import loki_mcstas as lm
import loki_samples as ls
import loki_nexus as lnx
import sys as _sys
_sys.path.insert(0, os.path.dirname(paths.HERE))
import sample_library as sl   # noqa: E402  (twin/sample_library.py: the samples, one file each)

# Configurations of the beamline upstream of the sample (collimation length): upstream part of the official model
# (source and sample apertures, wavelength band l_min–l_max that sets the chopper phases) and number of reuses of each
# MCPL neutron in the downstream part. Same configurations as the LoKI notebook series (notebooks 01–03), where they
# were computed and checked: the longer the collimation, the smaller the beam divergence (lower Q reached, better
# resolution) and the lower the flux, hence more reuses. 8 m: band 3–10 Å (frame overlap at 10 m of detector).
# Key: (collimation, pulse skipping). Pulse skipping ("on"): the choppers turn at 7 Hz and let one source pulse in two
# through, so the time between two pulses doubles and the wavelength band can be twice as wide (3–21.4 Å, as in the
# notebook series), at the price of half of the pulses: lower Q (long wavelengths), wider Q range in one setting.
CONFIGS = {
    ("3m", "off"): dict(front=dict(collen=3.0, sourceapx=0.03, sampleapx=0.01, l_min=3.0, l_max=11.5, ncount=1e9),
                        repeat=8),
    ("5m", "off"): dict(front=dict(collen=5.0, sourceapx=0.02, sampleapx=0.01, l_min=3.0, l_max=11.5, ncount=1e9),
                        repeat=32),
    ("8m", "off"): dict(front=dict(collen=8.0, sourceapx=0.02, sampleapx=0.01, l_min=3.0, l_max=10.0, ncount=1e9),
                        repeat=80),
    ("3m", "on"): dict(front=dict(collen=3.0, sourceapx=0.03, sampleapx=0.01, l_min=3.0, l_max=21.4, pulseskip=1,
                                  ncount=1e9), repeat=8),
}
COLLIMATIONS = tuple(dict.fromkeys(c for c, _ in CONFIGS))
DETECTOR_DISTANCES = (5.0, 10.0)  # m: rear detector bank (the middle and front banks do not move)
Q_EDGES = np.logspace(np.log10(3e-3), np.log10(0.5), 121)

# Choppers of the official model (LOKI_main.instr + includes/loki_functions.c): two pairs of discs, bandwidth chopper
# at 6.5 m and frame-overlap chopper at 15.21 m from the source, 14 Hz (7 Hz with pulse skipping); the delays of the
# two discs of a pair are computed from the wavelength band, with the same formulas as the model.
CHOPPERS = {"ch1": dict(pos=6.5, slit=120.0, name="bandwidth chopper"),
            "ch2": dict(pos=15.21, slit=190.0, name="frame-overlap chopper")}
_DISK_OFFSET = (0.016 + 0.017) / 2          # m: from the center of a pair to the center of each disc
_PULSE_MS = 2.86                            # ms: ESS pulse length used by the model


def chopper_settings(l_min, l_max, pulseskip=0):
    """{chopper: (speed [Hz], delay of disc a [ms], delay of disc b [ms])}, as computed by the official model."""
    freq = 14.0 / (1 + pulseskip)
    out = {}
    for c, d in CHOPPERS.items():
        pa, pb = d["pos"] - _DISK_OFFSET, d["pos"] + _DISK_OFFSET
        half = d["slit"] / 2 * 1000 / (freq * 360)                   # ms to turn by half the opening
        a = l_min * (pa - 0.08) / 3.96 + half                          # leading edge: shortest wavelength
        b = l_max * (pb - 0.08) / 3.96 + _PULSE_MS - half              # trailing edge: longest wavelength
        out[c] = (freq, a, b)
    return out


class Device:
    """A device of the twin with its allowed values (same attributes as odin_virtual.Device, read by the server)."""

    def __init__(self, name, value, choices, help="", unit="", limits=None):
        self.name, self.value, self.choices, self.help, self.unit, self.limits = name, value, choices, help, unit, limits


class VirtualLoki:
    def __init__(self, session="test", mpi=None, seed=None, mode="mcstas"):
        """mpi: number of McStas processes (default: variable TWIN_MPI, else 8)."""
        mpi = int(os.environ.get("TWIN_MPI", "8")) if mpi is None else mpi
        self.session, self.mpi, self.mode = session, mpi, "mcstas"   # always McStas (no hybrid model yet)
        self.devices = {d.name: d for d in [
            Device("heavy_shutter", "closed", ("open", "closed"), "main shutter, upstream in the guide"),
            Device("shutter", "closed", ("open", "closed"), "fast shutter, just before the sample"),
            Device("collimation", "3m", COLLIMATIONS, "collimation length (sets the wavelength band and choppers)"),
            Device("pulse_skipping", "off", ("off", "on"),
                   "on: choppers at 7 Hz, one source pulse in two, wavelength band twice as wide (3 m collimation)"),
            Device("detector_distance", 5.0, DETECTOR_DISTANCES, "distance sample -> rear detector bank", unit="m"),
            Device("sample", "silica_spheres", tuple(sl.load("loki")), "sample in the beam (sample changer)"),
        ]}
        self.choices = {n: d.choices for n, d in self.devices.items()}
        self.folder = None
        self.use_folder(f"{paths.RUN_ROOT}/{session}")
        self.rng = np.random.default_rng(seed)
        self._det = {}
        self._real_det = {}                 # real LoKI pixels (NeXus files), per detector distance
        self.last_image = np.zeros(self.image_shape(), dtype=np.uint32)
        self.last_n_counts = 0

    @property
    def state(self):
        return {n: d.value for n, d in self.devices.items()}

    def status(self):
        return self.state

    @staticmethod
    def config(state):
        """Configuration (CONFIGS) of a device state."""
        return CONFIGS[(state["collimation"], state["pulse_skipping"])]

    def band(self, state=None):
        """Wavelength band (l_min, l_max) [Å] of the configuration."""
        f = self.config(state or self.state)["front"]
        return f["l_min"], f["l_max"]

    def pulseskip(self, state=None):
        return self.config(state or self.state)["front"].get("pulseskip", 0)

    def readings(self):
        """Read-only values that follow from the settings (shown by NICOS as at ESS): chopper speeds and delays."""
        out = {}
        for c, (freq, a, b) in chopper_settings(*self.band(), self.pulseskip()).items():
            out[f"{c}_speed"] = freq
            out[f"{c}a_delay"] = round(a, 3)
            out[f"{c}b_delay"] = round(b, 3)
        out["wavelength_band"] = "%g-%g A" % self.band()
        return out

    @staticmethod
    def readings_help(name):
        """(unit, description) of a read-only value."""
        if name.endswith("_speed"):
            return "Hz", f"rotation speed of the {CHOPPERS[name[:3]]['name']}"
        if name.endswith("_delay"):
            return "ms", f"opening delay of disc {name[3]} of the {CHOPPERS[name[:3]]['name']} after the source pulse"
        return {"wavelength_band": ("", "wavelength band let through by the choppers")}[name]

    def use_folder(self, folder):
        """Writes the next files (and the logbook) in `folder`, e.g. the proposal folder chosen in NICOS."""
        folder = folder.replace(os.sep, "/")
        if folder != self.folder:
            os.makedirs(folder, exist_ok=True)
            self.folder = folder
            self.log_file = os.path.join(folder, "log.jsonl")
            nums = [int(f[5:11]) for f in os.listdir(folder) if f.startswith("loki_") and f.endswith((".nxs", ".h5"))]
            self.number = max(nums, default=0)
            if hasattr(self, "choices"):
                self.samples()

    @staticmethod
    def image_shape():
        """(rows, columns) of the live image: the rear detector panel, in pixels."""
        name, bank, a, d, r, w, h, t = [x for x in lm.PANELS_OFFICIAL if x[0] == "rear"][0]
        if t == "h":
            return int(round(h / lm.TUBE_PITCH)) * lm.STRAWS, int(round(w / lm.PIX_ALONG))
        return int(round(h / lm.PIX_ALONG)), int(round(w / lm.TUBE_PITCH)) * lm.STRAWS

    def samples(self):
        """{name: (function, kwargs, thickness, mu_abs, mu_rem)} available: built-in samples (loki/samples/*.yml), then
        the student's own (samples folder next to the data, sample builder)."""
        out = {}
        for n, spec in sl.load("loki", self.folder).items():
            if spec["source"] == "built-in" or not sl.validate("loki", spec):
                out[n] = sl.loki_sample(spec)
        self.devices["sample"].choices = tuple(out)
        self.choices["sample"] = tuple(out)
        return out

    def sample_spec(self, name=None):
        """The description of a sample (sample_library format), for display."""
        return sl.load("loki", self.folder)[name or self.state["sample"]]

    def move(self, **settings):
        if "sample" in settings:
            self.samples()                 # a sample made since the start is available at once
        for k, v in settings.items():
            if k not in self.choices:
                if k in self.readings():
                    raise KeyError(f"{k} is read-only: it follows from the configuration (collimation, pulse_skipping)")
                raise KeyError(f"unknown device {k!r}; devices: {list(self.choices)}")
            if v not in self.choices[k]:
                raise ValueError(f"{k} = {v!r} not allowed; allowed values: {self.choices[k]}")
        new = dict(self.state, **settings)
        if (new["collimation"], new["pulse_skipping"]) not in CONFIGS:
            raise ValueError(f"collimation {new['collimation']} with pulse_skipping {new['pulse_skipping']}: not "
                             f"available in the twin; available: {[f'{c} / {s}' for c, s in CONFIGS]}")
        # Frame overlap: the neutrons of one pulse (band l_min–l_max) must all arrive at the rear detector before
        # those of the next pulse used; otherwise some get the wrong wavelength (checked: 2 % of the rear-bank
        # neutrons, I(Q) 4 % too low, for 3–11.5 Å at 10 m). On the instrument the band is chosen with the distance.
        lo, hi = self.band(new)
        period = lm.FRAME * (1 + self.pulseskip(new))
        t_fast, t_slow = lm.arrivals(lm.L1 + float(new["detector_distance"]), lo, hi)
        if t_slow - t_fast > period:
            raise ValueError(f"frame overlap: with the band {lo:g}-{hi:g} A the neutrons of one pulse arrive at the "
                             f"detector at {float(new['detector_distance']):g} m over {(t_slow - t_fast) * 1e3:.0f} ms, "
                             f"more than the {period * 1e3:.1f} ms between two pulses used; with the detector at "
                             f"10 m use the collimation 8m (band 3-10 A); to leave 8m, move the detector to 5 m first")
        for k, v in settings.items():
            self.devices[k].value = v
        self._log("move", settings)

    def scan(self, device, values, t, title=""):
        """Like NICOS scan(): for each value, moves the device then counts t seconds. Returns the list of files."""
        files = []
        for v in values:
            self.move(**{device: v})
            files.append(self.count(t, title=f"{title} {device}={v}".strip()))
        return files

    def simulate(self, state=None):
        """Reduced I(Q) per bank for the sample in the beam, with the McStas simulation noise only (no counting)."""
        st = state or self.state
        cfg, repeat, reardet = self.config(st)["front"], self.config(st)["repeat"], float(st["detector_distance"])
        band, skip = self.band(st), self.pulseskip(st)
        front = lm.front(mpi=self.mpi, **cfg)
        fn, kw, thick, mu_abs, mu_rem = self.samples()[st["sample"]]
        if reardet not in self._det:
            self._det[reardet] = lm.Detector(reardet)
        det = self._det[reardet]
        lam = lm.lambda_bins(*band)
        self._front = front
        if fn is None:                                   # empty beam: nothing scattered, everything transmitted
            self._back, self._scattered = None, {k: np.zeros(0) for k in ("x", "y", "z", "ux", "uy", "uz", "t",
                                                                          "lam", "w")}
            phi, tr = np.zeros(len(lam) - 1), np.ones(len(lam) - 1)
        else:
            q, dsdo, _ = fn(**kw)
            # cache name: sample, configuration and a fingerprint of everything that defines the sample (a changed
            # parameter must give a new McStas simulation, never an old one read back)
            key = hashlib.md5(np.ascontiguousarray(np.r_[q, dsdo, thick, mu_abs, mu_rem]).tobytes()).hexdigest()[:8]
            name = f"{st['sample']}_col{st['collimation']}{'_skip' if skip else ''}_{key}"
            self._back = lm.back(front, name, q, dsdo, thickness=thick, mu_abs=mu_abs, mu_rem=mu_rem, repeat=repeat,
                                 mpi=self.mpi)
            self._scattered = lm.scattered(self._back)
            phi, tr = lm.spectrum(self._back, lam)
        ev = lm.events(det.detect(self._scattered), det, *band, period=lm.FRAME * (1 + skip))
        if skip:
            # McStas simulates one source pulse, which the choppers let through, with weights in neutrons per second
            # as if every pulse came: with pulse skipping only one pulse in (1 + skip) does. I(Q) is a ratio (same
            # factor in the scattered neutrons and in the incident flux) but the count rates, hence the counting
            # noise of a t-second measurement, are divided by (1 + skip).
            for e in ev.values():
                e["w"] = e["w"] / (1 + skip)
            phi = phi / (1 + skip)
        return ev, det, phi, tr, lam, thick * 100

    def beam_on(self):
        return self.state["heavy_shutter"] == "open" and self.state["shutter"] == "open"

    def count(self, t, title="", write=True):
        """Measures for t seconds; returns the path of the NeXus event file written (format of the real LoKI,
        loki_nexus.py; reduced with the ESS software, loki_reduction.py).
        write=False: the live detector image only, no file (a count outside a file-writing job at ESS); returns None."""
        if not 0 < t <= 24 * 3600:
            raise ValueError("counting time between 0 and 24 h")
        start = datetime.datetime.now(datetime.timezone.utc)
        sim = self.simulate() if self.beam_on() else None
        self._live_image(sim, t)
        self._last_sim, self._last_t = sim, t          # for the live stream (stream_pulses)
        if not write:
            self._log("count", dict(t=t, title=title, file=None, n_counts=self.last_n_counts, state=self.state))
            return None
        self.number += 1
        path = f"{self.folder}/loki_{self.number:06d}.nxs"
        r = self._write_nexus(path, sim, t, start, title)
        self._log("count", dict(t=t, title=title, file=os.path.basename(path), n_counts=self.last_n_counts,
                                n_events=r["n_events"], event_sampling=r["sampling"], state=self.state))
        return path

    def _write_nexus(self, path, sim, t, start, title):
        """Events of the measurement (all banks, monitors m1 and m3) in a NeXus file of the real LoKI's format."""
        st = self.state
        cfg = self.config(st)["front"]
        skip = self.pulseskip(st)
        reardet = float(st["detector_distance"])
        if reardet not in self._real_det:
            self._real_det[reardet] = lnx.RealDetector(reardet)
        empty = {b: (np.zeros(0, int), np.zeros(0, np.uint32), np.zeros(0, np.uint32)) for b in lnx.BANKS}
        n_pulses = max(1, int(round(t / lnx.PERIOD)))
        sampling, det_ev, mon_ev = 1.0, empty, {}
        if sim is not None:
            sc_ = self._scattered
            beam = lm.read_mcpl(lm.mcpl_path(self._front, "beam_at_sample"))
            rate = 1.0 / (1 + skip)                    # McStas weights: every pulse; pulse skipping uses one in two
            sampling = lnx.sampling_fraction(sc_, beam, t, rate)
            if self._back is not None:
                lam_m, i_inc, _, _ = lm.monitor(self._back, "incident_lambda")
                _, i_tr, _, _ = lm.monitor(self._back, "transmitted_lambda")
                tr = np.where(i_inc > 0, i_tr / np.where(i_inc > 0, i_inc, 1), 1.0)
                transmission = lambda lam: np.interp(lam, lam_m, tr)
            else:
                transmission = lambda lam: np.ones_like(lam)
            det_ev, n_pulses = lnx.detector_events(self.rng, sc_, self._real_det[reardet], t, sampling * rate,
                                                   1 + skip)
            mon_ev = lnx.monitor_events(self.rng, beam, transmission, t, sampling * rate, 1 + skip)
        choppers = {}
        for c, (freq, a, b) in chopper_settings(*self.band(st), skip).items():
            n1, n2 = ("bw_chopper1", "bw_chopper2") if c == "ch1" else ("fo_chopper1", "fo_chopper2")
            choppers[n1], choppers[n2] = (freq, a), (freq, b)
        fn, kw, thick, _, _ = self.samples()[st["sample"]]
        truth = {} if fn is None else {k: v for k, v in fn(**kw)[2].items() if np.isscalar(v)}
        info = {k: float(v) for k, v in cfg.items()}                  # configuration (finds the wavelength table)
        info.update(pulseskip=int(skip), event_sampling=sampling, sample_thickness_m=float(thick),
                    sample_model=st["sample"], proposal=os.path.basename(os.path.dirname(self.folder)),
                    **{f"true_{k}": float(v) for k, v in truth.items()})
        lnx.write(path, det_ev, mon_ev, n_pulses, start, t, title or f"run {self.number}", st["sample"],
                  {k: str(v) for k, v in st.items()}, choppers, reardet - lnx.REAR_Z0, info, lm.L1)
        return dict(n_events=int(sum(len(v[0]) for v in det_ev.values())), sampling=sampling)

    STREAM_MAX_RATE = 1e5          # neutrons per second in the live stream (Kafka), at most
    STREAM_MAX_EVENTS = 2e7        # and per measurement

    def stream_pulses(self, path=None):
        """Neutrons of the last measurement on the rear detector panel, pulse by pulse, for the live stream
        (../kafka/streamer.py): list of (time of the pulse after the first one [ns], detector clock = arrival time
        after the last source pulse [ns], pixel ids 1 + row * columns + column). A LoKI measurement gives millions
        of neutrons per second; the live stream carries a random sample of them (at most STREAM_MAX_RATE per second
        and STREAM_MAX_EVENTS per measurement, fraction in self.stream_fraction): the live image and spectrum have the
        right shape, with fewer counts; the file holds the full measurement."""
        sim, t = getattr(self, "_last_sim", None), getattr(self, "_last_t", 0.0)
        n_pulses = max(1, int(round(t * 14)))
        offsets = (np.arange(n_pulses) * 1e9 / 14).astype(np.int64)
        self.stream_fraction = 0.0
        if sim is None:
            return [(int(o), np.zeros(0, np.int32), np.zeros(0, np.int32)) for o in offsets]
        ev, det = sim[0], sim[1]
        lo, hi = self.band()
        cols = self.image_shape()[1]
        e = next(ev[p.name] for p in det.panels if p.bank == "rear")
        m = (e["lam"] >= lo) & (e["lam"] < hi)
        expected = e["w"][m] * t
        total = expected.sum()
        k = min(1.0, self.STREAM_MAX_RATE * t / total, self.STREAM_MAX_EVENTS / total) if total > 0 else 0.0
        self.stream_fraction = k
        n = self.rng.poisson(expected * k)
        pix = np.repeat((1 + e["iy"][m] * cols + e["ix"][m]).astype(np.int32), n)
        tof = np.repeat((e["clock"][m] * 1e9).astype(np.int32), n)
        pulse = self.rng.integers(0, n_pulses, len(pix))
        order = np.argsort(pulse, kind="stable")
        pix, tof, pulse = pix[order], tof[order], pulse[order]
        bounds = np.searchsorted(pulse, np.arange(n_pulses + 1))
        return [(int(offsets[j]), tof[bounds[j]:bounds[j + 1]], pix[bounds[j]:bounds[j + 1]]) for j in range(n_pulses)]

    def _live_image(self, sim, t):
        """Counts of a t-second measurement on the rear panel (Poisson), and the total on all panels."""
        shape = self.image_shape()
        self.last_image, self.last_n_counts = np.zeros(shape, dtype=np.uint32), 0
        if sim is None:
            return
        ev, det = sim[0], sim[1]
        lo, hi = self.band()
        for p in det.panels:
            e = ev[p.name]
            m = (e["lam"] >= lo) & (e["lam"] < hi)
            if p.bank == "rear":
                expected = np.zeros(shape)
                np.add.at(expected, (e["iy"][m], e["ix"][m]), e["w"][m] * t)
                self.last_image = self.rng.poisson(expected).astype(np.uint32)
                self.last_n_counts += int(self.last_image.sum())
            else:
                self.last_n_counts += int(self.rng.poisson(e["w"][m].sum() * t))

    def _log(self, action, details):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(time=datetime.datetime.now().isoformat(timespec="seconds"), action=action,
                                    details=details)) + "\n")


def read(path):
    """{bank: (Q, I, Idev)} of a file written by VirtualLoki.count."""
    with h5py.File(path, "r") as f:
        return {k[5:]: (f[f"entry/{k}/Q"][()], f[f"entry/{k}/I"][()], f[f"entry/{k}/Idev"][()])
                for k in f["entry"] if k.startswith("data_")}
