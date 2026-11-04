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

# Configurations: collimation length -> (upstream part, rear detector distance [m], reuses of each MCPL neutron)
CONFIGS = {
    "3m": (dict(collen=3.0, sourceapx=0.03, sampleapx=0.01, l_min=3.0, l_max=11.5, ncount=1e9), 5.0, 8),
}
LAM_BAND = (3.0, 11.5)           # Å: band used in the reduction (bender transmission < 20 % below 3 Å)
Q_EDGES = np.logspace(np.log10(3e-3), np.log10(0.5), 121)


class Device:
    """A device of the twin with its allowed values (same attributes as odin_virtual.Device, read by the server)."""

    def __init__(self, name, value, choices, help="", unit="", limits=None):
        self.name, self.value, self.choices, self.help, self.unit, self.limits = name, value, choices, help, unit, limits


class VirtualLoki:
    def __init__(self, session="test", mpi=8, seed=None, mode="mcstas"):
        self.session, self.mpi, self.mode = session, mpi, "mcstas"   # always McStas (no hybrid model yet)
        self.devices = {d.name: d for d in [
            Device("heavy_shutter", "closed", ("open", "closed"), "main shutter, upstream in the guide"),
            Device("shutter", "closed", ("open", "closed"), "fast shutter, just before the sample"),
            Device("collimation", "3m", tuple(CONFIGS), "collimation length (sets the rear detector distance)"),
            Device("sample", "silica_spheres", tuple(ls.SAMPLES), "sample in the beam"),
        ]}
        self.choices = {n: d.choices for n, d in self.devices.items()}
        self.folder = None
        self.use_folder(f"{paths.RUN_ROOT}/{session}")
        self.rng = np.random.default_rng(seed)
        self._det = {}
        self.last_image = np.zeros(self.image_shape(), dtype=np.uint32)
        self.last_n_counts = 0

    @property
    def state(self):
        return {n: d.value for n, d in self.devices.items()}

    def status(self):
        return self.state

    def use_folder(self, folder):
        """Writes the next files (and the logbook) in `folder`, e.g. the proposal folder chosen in NICOS."""
        folder = folder.replace(os.sep, "/")
        if folder != self.folder:
            os.makedirs(folder, exist_ok=True)
            self.folder = folder
            self.log_file = os.path.join(folder, "log.jsonl")
            nums = [int(f[5:11]) for f in os.listdir(folder) if f.startswith("loki_") and f.endswith(".h5")]
            self.number = max(nums, default=0)

    @staticmethod
    def image_shape():
        """(rows, columns) of the live image: the rear detector panel, in pixels."""
        name, bank, a, d, r, w, h, t = [x for x in lm.PANELS_OFFICIAL if x[0] == "rear"][0]
        if t == "h":
            return int(round(h / lm.TUBE_PITCH)) * lm.STRAWS, int(round(w / lm.PIX_ALONG))
        return int(round(h / lm.PIX_ALONG)), int(round(w / lm.TUBE_PITCH)) * lm.STRAWS

    def move(self, **settings):
        for k, v in settings.items():
            if k not in self.choices:
                raise KeyError(f"unknown device {k!r}; devices: {list(self.choices)}")
            if v not in self.choices[k]:
                raise ValueError(f"{k} = {v!r} not allowed; allowed values: {self.choices[k]}")
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
        cfg, reardet, repeat = CONFIGS[st["collimation"]]
        front = lm.front(mpi=self.mpi, **cfg)
        fn, kw, thick, mu_abs, mu_rem = ls.SAMPLES[st["sample"]]
        q, dsdo, _ = fn(**kw)
        # cache name: sample, configuration and a fingerprint of everything that defines the sample (a changed
        # parameter must give a new McStas simulation, never an old one read back)
        key = hashlib.md5(np.ascontiguousarray(np.r_[q, dsdo, thick, mu_abs, mu_rem]).tobytes()).hexdigest()[:8]
        back = lm.back(front, f"{st['sample']}_col{st['collimation']}_{key}", q, dsdo, thickness=thick, mu_abs=mu_abs,
                       mu_rem=mu_rem, repeat=repeat, mpi=self.mpi)
        if reardet not in self._det:
            self._det[reardet] = lm.Detector(reardet)
        det = self._det[reardet]
        ev = lm.events(det.detect(lm.scattered(back)), det, *LAM_BAND)
        lam = lm.lambda_bins(*LAM_BAND)
        phi, tr = lm.spectrum(back, lam)
        return ev, det, phi, tr, lam, thick * 100

    def beam_on(self):
        return self.state["heavy_shutter"] == "open" and self.state["shutter"] == "open"

    def count(self, t, title="", write=True):
        """Measures for t seconds; returns the path of the HDF5 file written (I(Q) per bank, absolute units).
        write=False: the live detector image only, no file (a count outside a file-writing job at ESS); returns None."""
        if not 0 < t <= 24 * 3600:
            raise ValueError("counting time between 0 and 24 h")
        sim = self.simulate() if self.beam_on() else None
        self._live_image(sim, t)
        if not write:
            self._log("count", dict(t=t, title=title, file=None, n_counts=self.last_n_counts, state=self.state))
            return None
        self.number += 1
        path = f"{self.folder}/loki_{self.number:06d}.h5"
        with h5py.File(path, "w") as f:
            e = f.create_group("entry"); e.attrs["NX_class"] = "NXentry"
            e["title"] = title; e["start_time"] = datetime.datetime.now().isoformat(timespec="seconds")
            e["duration"] = float(t); e["duration"].attrs["units"] = "s"
            for k, v in self.state.items():
                e[f"instrument_state/{k}"] = v
            if sim is not None:
                ev, det, phi, tr, lam, thick_cm = sim
                red = lm.reduce(ev, det, phi, tr, lam, thick_cm, Q_EDGES, duration=t)
                for bank, (qc, I, err, den) in red.items():
                    ok = np.isfinite(I) & (den > 0.02 * np.nanmax(den))       # bins well covered by this bank
                    noisy = I[ok] + self.rng.normal(0, 1, ok.sum()) * err[ok]   # one realisation of the noise
                    g = e.create_group(f"data_{bank}"); g.attrs["NX_class"] = "NXdata"
                    g["Q"] = qc[ok]; g["Q"].attrs["units"] = "1/angstrom"
                    g["I"] = noisy; g["I"].attrs["units"] = "1/cm"
                    g["Idev"] = err[ok]; g["Idev"].attrs["units"] = "1/cm"
        self._log("count", dict(t=t, title=title, file=path, n_counts=self.last_n_counts, state=self.state))
        return path

    def _live_image(self, sim, t):
        """Counts of a t-second measurement on the rear panel (Poisson), and the total on all panels."""
        shape = self.image_shape()
        self.last_image, self.last_n_counts = np.zeros(shape, dtype=np.uint32), 0
        if sim is None:
            return
        ev, det = sim[0], sim[1]
        for p in det.panels:
            e = ev[p.name]
            m = (e["lam"] >= LAM_BAND[0]) & (e["lam"] < LAM_BAND[1])
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
