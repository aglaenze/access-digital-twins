"""Virtual LoKI (first version): a small-angle scattering measurement with the McStas model of LoKI.

    from virtual_loki import VirtualLoki
    loki = VirtualLoki(session="test")
    loki.move(sample="silica_spheres", shutter="open")
    f = loki.count(600, title="silica spheres")      # 10 min; returns an HDF5 file with I(Q) per detector bank

What it does: McStas upstream part (official model, precomputed, cached), McStas downstream part for the sample
(cached), detection by the 9 tube panels, time of flight -> λ -> Q, reduction to I(Q) in absolute units with the
counting noise of a measurement of `t` seconds (Gaussian approximation of the Poisson noise per Q bin, plus the
simulation noise). Not yet: raw event files in the ESS NeXus format, reduction with the ESS software (esssans),
the dark/empty-cell/solvent measurements of a real SANS experiment, NICOS. See README.md.
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


class VirtualLoki:
    def __init__(self, session="test", mpi=8, seed=None):
        self.session, self.mpi = session, mpi
        self.state = dict(collimation="3m", sample="silica_spheres", shutter="closed")
        self.choices = dict(collimation=tuple(CONFIGS), sample=tuple(ls.SAMPLES), shutter=("open", "closed"))
        self.folder = f"{paths.RUN_ROOT}/{session}"
        os.makedirs(self.folder, exist_ok=True)
        self.log_file = os.path.join(self.folder, "log.jsonl")
        self.number = len([f for f in os.listdir(self.folder) if f.endswith(".h5")])
        self.rng = np.random.default_rng(seed)
        self._det = {}

    def status(self):
        return dict(self.state)

    def move(self, **settings):
        for k, v in settings.items():
            if k not in self.choices:
                raise KeyError(f"unknown device {k!r}; devices: {list(self.choices)}")
            if v not in self.choices[k]:
                raise ValueError(f"{k} = {v!r} not allowed; allowed values: {self.choices[k]}")
        self.state.update(settings)
        self._log("move", settings)

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

    def count(self, t, title=""):
        """Measures for t seconds; returns the path of the HDF5 file written (I(Q) per bank, absolute units)."""
        if not 0 < t <= 24 * 3600:
            raise ValueError("counting time between 0 and 24 h")
        self.number += 1
        path = os.path.join(self.folder, f"loki_{self.number:06d}.h5")
        with h5py.File(path, "w") as f:
            e = f.create_group("entry"); e.attrs["NX_class"] = "NXentry"
            e["title"] = title; e["start_time"] = datetime.datetime.now().isoformat(timespec="seconds")
            e["duration"] = float(t); e["duration"].attrs["units"] = "s"
            for k, v in self.state.items():
                e[f"instrument_state/{k}"] = v
            if self.state["shutter"] == "open":
                ev, det, phi, tr, lam, thick_cm = self.simulate()
                red = lm.reduce(ev, det, phi, tr, lam, thick_cm, Q_EDGES, duration=t)
                for bank, (qc, I, err, den) in red.items():
                    ok = np.isfinite(I) & (den > 0.02 * np.nanmax(den))       # bins well covered by this bank
                    noisy = I[ok] + self.rng.normal(0, 1, ok.sum()) * err[ok]   # one realisation of the noise
                    g = e.create_group(f"data_{bank}"); g.attrs["NX_class"] = "NXdata"
                    g["Q"] = qc[ok]; g["Q"].attrs["units"] = "1/angstrom"
                    g["I"] = noisy; g["I"].attrs["units"] = "1/cm"
                    g["Idev"] = err[ok]; g["Idev"].attrs["units"] = "1/cm"
        self._log("count", dict(t=t, title=title, file=path, state=dict(self.state)))
        return path

    def _log(self, action, details):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(time=datetime.datetime.now().isoformat(timespec="seconds"), action=action,
                                    details=details)) + "\n")


def read(path):
    """{bank: (Q, I, Idev)} of a file written by VirtualLoki.count."""
    with h5py.File(path, "r") as f:
        return {k[5:]: (f[f"entry/{k}/Q"][()], f[f"entry/{k}/I"][()], f[f"entry/{k}/Idev"][()])
                for k in f["entry"] if k.startswith("data_")}
