"""Instrument-control brick of the ODIN digital twin (works without NICOS).

It mimics the way NICOS works: **devices** that are moved (`move`), then a **count** (`count`) that produces a
numbered data file, and `scan`. NICOS will later drive the same object through the server (odin_server.py).

What count(t) does:
  1. translates the device state into McStas parameters (chopper mode -> precomputed upstream file, pinhole D,
     sample position and rotation, diffuser);
  2. runs McStas if needed (each configuration is simulated once, then cached);
  3. draws the counts measured during t seconds (Poisson noise, efficiency, blur, background), in one of two modes:
     * "hybrid" (default): open beam built from all upstream neutrons + exact attenuation by the sample
       (odin_hybrid.py); true Poisson noise whatever the counting time;
     * "mcstas": each count is drawn from an event of the full McStas simulation (sample included); exact, sample
       scattering included, but limited to short counts (mc_factor);
  4. writes a NeXus file in ESS format (odin_nexus.write_nexus) with the state of the devices and choppers;
  5. records the action in a log (log.jsonl), as a server recording the sessions would.

Chopper modes (devices "choppers" and "wfm_delta"): WFM (δ = 0.10, 0.30 or 0.45 m), "natural" (band-pass choppers
and T0 only), "white" (no chopper). Each mode reads its own precomputed McStas upstream part (FRONTS).

Limits (told to students): Timepix3 field of view 14 mm × 14 mm; "mcstas" mode: finite number of distinct simulated
neutrons, a long count reuses them (warning); "hybrid" mode: neutrons scattered by the sample are neglected.
"""
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

import odin_paths as paths                      # noqa: E402  (sets sys.path)
import odin_mcstas as tw                        # noqa: E402
import odin_nexus as nx                         # noqa: E402
import odin_hybrid as hy                        # noqa: E402
sys.path.insert(0, os.path.dirname(paths.HERE))
import sample_library as sl                     # noqa: E402  (twin/sample_library.py: the samples, one file each)

RUN_ROOT = paths.RUN_ROOT
BUILD = paths.BUILD
COMPONENTS = paths.COMPONENTS
FIELD = (-0.00705, 0.00705, -0.00705, 0.00705)  # [m] Timepix3 field of view of the template
FOV = 0.016                      # [m] McStas detector window, slightly larger than the Timepix3 (14 mm)
# Largest number of counts per file (memory: ~40 bytes per count while writing). The open beam gives ~1·10⁶ counts/s
# in WFM mode but ~2·10⁷ counts/s in white mode. (A real Timepix3 camera would saturate at such rates; not modeled.)
MAX_COUNTS = 5e7
# Precomputed upstream parts (odin_mcstas.front): (mode, δ) -> (δ in the folder name, neutrons).
# δ only matters in WFM mode (the other modes were computed with δ = 0.30, which has no effect without WFM choppers).
FRONTS = {("wfm", 0.30): (0.30, 1e10), ("wfm", 0.10): (0.10, 2e8), ("wfm", 0.45): (0.45, 2e8),
          ("natural", None): (0.30, 2e8), ("white", None): (0.30, 1e8)}
# Wavelength range simulated at the source for each mode [Å]
LAM_RANGE = tw.FRONT_LAM
# Focused diffuser (components/Graphite_Diffuser_focus.comp): aims at a 20 mm square in the detector plane
# (Z_SAMPLE + DET_DIST), from the diffuser entrance (Z_PINHOLE + 1 mm, as in odin_mcstas.build_back).
FOCUS = dict(focus_xw=0.020, focus_yh=0.020, focus_z=tw.Z_SAMPLE + tw.DET_DIST - (tw.Z_PINHOLE + 1e-3), f_phys=0.1)


# --------------------------------------------------------------------------- samples
def _union_boxes(volumes):
    """McStas sample (Union) made of volumes [(NCrystal cfg, center (m), dims (m)[, shape]), ...], placed relative to
    the stage axis: boxes (no shape), spheres (diameter dims[0]) and cylinders (vertical, diameter dims[0], height
    dims[1]). The same volumes are used by the hybrid mode (odin_hybrid.volumes_transmission)."""
    def f(instr):
        mats = {}
        for v in volumes:
            if v[0] not in mats:
                mats[v[0]] = f"mat_{len(mats)}"
                instr.add_component(mats[v[0]], "Union_NCrystal_material", AT=0, RELATIVE="origin").set_parameters(
                    cfg=f'"{v[0]}"')
        for i, v in enumerate(volumes):
            cfg, center, dims = v[:3]
            shape = v[3] if len(v) > 3 else "box"
            common = dict(material_string=f'"{mats[cfg]}"', priority=10 + i)
            if shape == "sphere":
                instr.add_component(f"sphere_{i}", "Union_sphere", AT=list(center), RELATIVE="sample_arm"
                                    ).set_parameters(radius=dims[0] / 2, **common)
            elif shape == "cylinder":                         # Union_cylinder: axis along y (vertical)
                instr.add_component(f"cylinder_{i}", "Union_cylinder", AT=list(center), RELATIVE="sample_arm"
                                    ).set_parameters(radius=dims[0] / 2, yheight=dims[1], **common)
            else:
                instr.add_component(f"box_{i}", "Union_box", AT=list(center), RELATIVE="sample_arm").set_parameters(
                    xwidth=dims[0], yheight=dims[1], zdepth=dims[2], **common)
        instr.add_component("union_master", "Union_master", AT=0, RELATIVE="origin").set_parameters(
            enable_refraction=0, enable_reflection=0)
    return f


def _with_rotation(build_sample):
    """Adds the rotation stage (vertical axis, parameter sample_rot in degrees) under the sample: the sample
    components placed RELATIVE "sample_arm" are attached to "sample_rot_arm"."""
    def f(instr):
        instr.add_parameter("double", "sample_rot", value=0.0, comment="[deg] sample rotation about the vertical axis")
        instr.add_component("sample_rot_arm", "Arm", AT=[0, 0, 0], RELATIVE="sample_arm", ROTATED=[0, "sample_rot", 0])
        n0 = len(instr.component_list)
        build_sample(instr)
        for c in instr.component_list[n0:]:
            if c.AT_reference == "sample_arm":
                c.set_AT(c.AT_data, RELATIVE="sample_rot_arm")
            if getattr(c, "ROTATED_reference", None) == "sample_arm":
                c.set_ROTATED(c.ROTATED_data, RELATIVE="sample_rot_arm")
    return f


def _focused_diffuser(instr):
    """Graphite diffuser with importance sampling toward the field of view (same dimensions as build_back)."""
    g = instr.add_component("graph", "Graphite_Diffuser_focus", AT=tw.Z_PINHOLE + 1e-3, RELATIVE="optical_axis")
    g.set_parameters(xwidth=0.1, ywidth=0.1, thick=0.2, **FOCUS)
    g.set_WHEN("use_diffuser == 1")


# Hidden faults for troubleshooting exercises (VirtualOdin(faults=...)): what the student may observe
FAULTS = {
    "hot_pixels": "a few pixels count all the time (bright spots, flat time spectrum)",
    "dead_region": "a corner of the detector records nothing",
    "stage_offset": "the sample stage is 3 mm off its reported position",
    "beam_outages": "frequent beam outages (proton charge drops to zero)",
}
REFERENCE_SAMPLE = "iron_plate"    # McStas instrument used for the open-beam simulations of the hybrid model

def _odin_sample(spec):
    return dict(volumes=sl.odin_volumes(spec), name=spec.get("name", spec["id"]), formula=spec.get("formula", ""))


# Built-in samples: odin/samples/*.yml (sample_library). The games add their mystery plates here; the students' own
# samples (sample builder) are read from the samples folder next to their data (VirtualOdin.samples()).
SAMPLES = {n: _odin_sample(s) for n, s in sl.load("odin").items()}


# --------------------------------------------------------------------------- devices
class Device:
    """A settable device with its limits (like a NICOS motor) and its name in the NeXus file."""

    def __init__(self, name, value, unit="", limits=None, choices=None, nexus=None, to_nexus=None, help=""):
        self.name, self.value, self.unit = name, value, unit
        self.limits, self.choices, self.nexus, self.to_nexus, self.help = limits, choices, nexus, to_nexus, help

    def check(self, v):
        if self.choices is not None and v not in self.choices:
            raise ValueError(f"{self.name}: value {v!r} not allowed; choices: {list(self.choices)}")
        if self.limits is not None:
            lo, hi = self.limits
            if not lo <= v <= hi:
                raise ValueError(f"{self.name}: {v} {self.unit} outside the limits [{lo}, {hi}] {self.unit}")

    def __repr__(self):
        return f"{self.name} = {self.value} {self.unit}".strip()


class VirtualOdin:
    """Virtual ODIN: devices + counting -> numbered NeXus files in RUN_ROOT/<session>/."""

    def __init__(self, session="test", mpi=4, repeat=4, focus=True, seed=None, fluctuation=0.01,
                 outages_per_hour=0.0, mode="hybrid", budget_s=None, faults=()):
        """repeat: reuses of each upstream MCPL neutron in McStas (upstream part: table FRONTS);
        focus: focused diffuser toward the field of view (otherwise the original component, much less efficient);
        fluctuation: relative pulse-to-pulse variation of the proton charge;
        outages_per_hour: random beam outages (5 to 60 s), as on a real source;
        mode: "hybrid" (any counting time) or "mcstas" (everything in McStas, short counts);
        budget_s: beamtime budget [s of counting with the shutter open], None = unlimited (games, odin_games.py);
        faults: hidden instrument faults (FAULTS), e.g. ("hot_pixels",) for troubleshooting exercises."""
        unknown = set(faults) - set(FAULTS)
        if unknown:
            raise ValueError(f"unknown faults {unknown}; available: {list(FAULTS)}")
        self.budget_s, self.faults = budget_s, tuple(faults)
        if "beam_outages" in self.faults:
            outages_per_hour = max(outages_per_hour, 240.0)
        if mode not in ("hybrid", "mcstas"):
            raise ValueError("mode: 'hybrid' or 'mcstas'")
        self.fluctuation, self.outages_per_hour, self.mode = fluctuation, outages_per_hour, mode
        self.folder = f"{RUN_ROOT}/{session}"
        os.makedirs(self.folder, exist_ok=True)
        self.mpi, self.repeat, self.focus = mpi, repeat, focus
        # Under MPI, MCPL_input repeats the file ceil(repeat / mpi) times in EACH process:
        # actual number of copies of each upstream neutron (cf. MCPL_input.comp)
        self.copies = -(-repeat // mpi) * mpi
        self.rng = np.random.default_rng(seed)
        self.log_file = os.path.join(self.folder, "log.jsonl")
        # Devices. The NeXus names are those of the real ODIN file (template).
        self.devices = {d.name: d for d in [
            Device("choppers", "wfm", choices=("wfm", "natural", "white"),
                   help="chopper mode: wfm (wavelength frame multiplication), natural (band-pass + T0), white (none)"),
            Device("wfm_delta", 0.30, "m", choices=(0.10, 0.30, 0.45),
                   help="separation of the two WFM discs (wfm mode): smaller = better resolution, less flux"),
            Device("shutter", "closed", choices=("open", "closed"), nexus="experiment_shutter/status",
                   to_nexus=lambda v: 3 if v == "open" else 0,             # 3 = "Opened", 0 = "Closed"
                   help="experiment shutter, just upstream of the sample"),
            Device("pinhole", 0.03, "m", choices=(0.01, 0.02, 0.03, 0.04),
                   nexus=("pinhole_2/horizontal_gap", "pinhole_2/vertical_gap"), to_nexus=lambda v: v * 1e3,
                   help="side D of the square pinhole at 50 m (L = 10.5 m to the sample: L/D)"),
            Device("diffuser", "in", choices=("in", "out"), nexus="pinhole_diffuser/status",
                   to_nexus=lambda v: 3 if v == "in" else 0,               # assumed convention, to be checked
                   help="graphite diffuser after the pinhole (homogenises the beam)"),
            Device("stage_x", 0.0, "m", limits=(-0.5, 0.5), nexus="spst1_lin_x", to_nexus=lambda v: v * 1e3,
                   help="horizontal sample translation; |x| > 2 cm: out of the field of view"),
            Device("stage_rot", 0.0, "deg", limits=(-180, 180), nexus="spst1_rot_y",
                   help="sample rotation about the vertical axis"),
            Device("sample", "iron_plate", choices=tuple(SAMPLES), help="sample mounted on the stage"),
        ]}
        self._back = {}
        self._models = {}
        self.last_image = np.zeros((128, 128), dtype=np.uint32)
        self.number = self._last_number()

    # ------------------------------------------------------------------ NICOS-like commands
    def samples(self):
        """{name: sample} available: built-in (and games), then the student's own (samples folder next to the data)."""
        out = dict(SAMPLES)
        for n, spec in sl.load("odin", self.folder).items():
            if spec["source"] == "student" and n not in out and not sl.validate("odin", spec):
                out[n] = _odin_sample(spec)
        self.devices["sample"].choices = tuple(out)
        return out

    def sample_spec(self, name=None):
        """The description of a sample (sample_library format), for display."""
        name = name or self.devices["sample"].value
        lib = sl.load("odin", self.folder)
        if name in lib:
            return lib[name]
        s = self.samples()[name]           # a mystery plate of a game: its material is not told
        return dict(id=name, name=s["name"], hidden=["material"], volumes=[
            dict(material=v[0], center_mm=[c * 1e3 for c in v[1]], size_mm=[d * 1e3 for d in v[2]],
                 **({"shape": v[3]} if len(v) > 3 else {})) for v in s["volumes"]])

    def move(self, **settings):
        """Sets one or several devices: odin.move(stage_x=0.5, shutter="open")."""
        if "sample" in settings:
            self.samples()                 # a sample made since the start is available at once
        for name, v in settings.items():
            if name not in self.devices:
                if name in self.readings():
                    raise KeyError(f"{name} is read-only: it follows from the chopper mode (devices choppers, wfm_delta)")
                raise KeyError(f"unknown device: {name}; devices: {list(self.devices)}")
            self.devices[name].check(v)
        for name, v in settings.items():
            self.devices[name].value = v
        self._log("move", settings)

    def status(self):
        return {n: d.value for n, d in self.devices.items()}

    def readings(self):
        """Read-only values that follow from the settings (shown by NICOS as at ESS): chopper speeds and delays."""
        return nx.chopper_readings(self.devices["choppers"].value, self.devices["wfm_delta"].value)

    @staticmethod
    def stream_pulses(nexus_file, block=32):
        """The neutrons of a NeXus file, pulse by pulse, for the live stream (kafka/streamer.py): list of (time of the
        pulse after the first one [ns], arrival times [ns], pixel ids). The Timepix3 pixels (4096 × 4096) are grouped
        in blocks of block × block, numbered 1 + ix + n iy (n = 4096 / block: 128 × 128 for 32), so that the live
        histograms stay small; the file keeps the full pixel ids."""
        import h5py
        with h5py.File(nexus_file, "r") as f:
            d = f["entry/instrument/timepix3/data"]
            tz, idx = d["event_time_zero"][()], d["event_index"][()]
            tof, pid = d["event_time_offset"][()], d["event_id"][()]
        n = 4096 // block
        p = pid.astype(np.int64) - 1
        sp = (1 + (p % 4096) // block + n * ((p // 4096) // block)).astype(np.int32)
        bounds = list(idx) + [len(pid)]
        return [(int(tz[k] - tz[0]), tof[bounds[k]:bounds[k + 1]].astype(np.int32), sp[bounds[k]:bounds[k + 1]])
                for k in range(len(tz))]

    @staticmethod
    def readings_help(name):
        """(unit, description) of a read-only value."""
        key = name.rsplit("_", 1)[-1] if name.endswith(("_speed", "_delay")) else name
        return nx.READINGS_HELP[key]

    def use_folder(self, folder):
        """Writes the next files (and the logbook) in `folder`, e.g. the proposal folder chosen in NICOS."""
        folder = folder.replace(os.sep, "/")
        if folder != self.folder:
            os.makedirs(folder, exist_ok=True)
            self.folder = folder
            self.log_file = os.path.join(folder, "log.jsonl")
            self.number = self._last_number()
            self.samples()

    def count(self, t, title="", write=True):
        """Measures for t seconds; returns the path of the NeXus file written.
        write=False: the detector image only (live display), no file, as a count outside a file-writing job at ESS;
        returns None."""
        if not 0 < t <= 3600:
            raise ValueError("counting time between 0 and 3600 s")
        t0 = time.time()
        state = self.status()
        if self.budget_s is not None and state["shutter"] == "open" and self.beam_used() + t > self.budget_s + 1e-9:
            raise ValueError(f"beamtime exhausted: {self.budget_s - self.beam_used():.0f} s left of {self.budget_s:.0f} s")
        if "stage_offset" in self.faults:          # the stage is not where it says it is (hidden from the files)
            state = dict(state, stage_x=state["stage_x"] + 0.003)
        # Source: proton charge of each pulse (and possible beam outages)
        n_out = self.rng.poisson(self.outages_per_hour * t / 3600)
        outages = [(self.rng.uniform(0, t), self.rng.uniform(5, 60)) for _ in range(n_out)]
        charge = nx.pulse_charges(t, self.rng, fluctuation=self.fluctuation, outages=outages)
        ppf = nx.PULSES_PER_FRAME[state["choppers"]]
        beam_factor = charge[0::ppf].mean() / nx.Q_NOMINAL          # useful pulses (one in two with the band-pass choppers)
        if state["shutter"] == "closed":                              # background only
            counts = nx.sample_counts({k: np.zeros(0) for k in ("x", "y", "t", "lam", "w")}, t, field=FIELD,
                                      rng=self.rng)
        elif self.mode == "hybrid":
            model = self.model(state)
            expected = model.rate() * t * beam_factor
            if expected > MAX_COUNTS:
                raise ValueError(f"about {expected:.2g} counts expected, above the twin's limit of {MAX_COUNTS:.0e} "
                                 f"counts per file: count for at most {t * MAX_COUNTS / expected:.1f} s here "
                                 f"(or use a smaller pinhole / another chopper mode)")
            T = hy.volumes_transmission(self.samples()[state["sample"]]["volumes"], state["stage_x"], state["stage_rot"])
            counts = model.counts(t, transmission=T, rng=self.rng, beam_factor=beam_factor)
        else:
            counts = nx.counts_from_mcpl(self.simulate(state), t, field=FIELD, rng=self.rng,
                                         beam_factor=beam_factor, copies=self.copies)
        counts = self._apply_faults(counts, t)
        if counts["mc_factor"] > 1.2:
            print(f"Warning: counting time too long for the statistics of the simulation; the Poisson error bars are "
                  f"underestimated by a factor {counts['mc_factor']:.2f}.")
        # Detector image of this measurement (128 × 128 pixels of 110 µm), for live displays (NICOS, page)
        self.last_image = np.histogram2d(counts["y"], counts["x"], bins=128,
                                         range=[FIELD[2:], FIELD[:2]])[0].astype(np.uint32)
        if not write:
            self.last_n_counts = int(self.last_image.sum())
            self._log("count", dict(t=t, title=title, file=None, n_counts=self.last_n_counts, mode=self.mode,
                                    charge_uC=round(float(charge.sum()), 1), state=self.status(),
                                    compute_time=round(time.time() - t0, 1)))
            return None
        self.number += 1
        out_file = f"{self.folder}/odin_{self.number:06d}.nxs"
        r = nx.write_nexus(counts, out_file, t, title=title or f"run {self.number}",
                           sample_name=self.samples()[state["sample"]]["name"], det_dist=tw.DET_DIST, charge=charge,
                           pulses_per_frame=ppf,
                           settings=self._nexus_settings() | nx.chopper_settings(state["choppers"], state["wfm_delta"]))
        self.last_n_counts = r["n_counts"]
        self._log("count", dict(t=t, title=title, file=os.path.basename(out_file), n_counts=r["n_counts"],
                                mode=self.mode, mc_factor=round(counts["mc_factor"], 3),
                                charge_uC=round(float(charge.sum()), 1),
                                outages=[(round(a, 1), round(b, 1)) for a, b in outages],
                                state=self.status(), compute_time=round(time.time() - t0, 1)))
        return out_file

    def beam_used(self):
        """Counting time with the shutter open spent so far in this session [s] (from the log)."""
        used = 0.0
        if os.path.isfile(self.log_file):
            for line in open(self.log_file, encoding="utf-8"):
                e = json.loads(line)
                if e["action"] == "count" and e["details"]["state"]["shutter"] == "open":
                    used += e["details"]["t"]
        return used

    def _apply_faults(self, counts, t):
        """Hidden detector faults (troubleshooting exercises)."""
        if "hot_pixels" in self.faults:            # a few noisy pixels: many counts, random times, no λ
            rng = np.random.default_rng(7)         # always the same pixels
            hot = rng.uniform(FIELD[0], FIELD[1], (6, 2))
            n = int(2000 * t)
            k = self.rng.integers(0, len(hot), n)
            counts = dict(counts, x=np.r_[counts["x"], hot[k, 0].astype(np.float32)],
                          y=np.r_[counts["y"], hot[k, 1].astype(np.float32)],
                          t=np.r_[counts["t"], self.rng.uniform(0, 1 / nx.PULSE_HZ, n)],
                          lam=np.r_[counts["lam"], np.full(n, np.nan, dtype=np.float32)])
        if "dead_region" in self.faults:           # a dead corner of the detector (e.g. a damaged chip)
            keep = ~((counts["x"] > 0.003) & (counts["y"] > 0.003))
            counts = dict(counts, **{k: counts[k][keep] for k in ("x", "y", "t", "lam")})
        return counts

    def scan(self, device, values, t, title=""):
        """Like NICOS scan(): for each value, moves the device then counts t seconds. Returns the list of files.
        Example: odin.scan("stage_rot", np.arange(0, 180, 3), 10)."""
        self.devices[device].check(values[0])
        files = []
        for v in values:
            if isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool):
                v = float(v)
            self.move(**{device: v})
            label = f"{device}={v:g}" if isinstance(v, float) else f"{device}={v}"
            files.append(self.count(t, title=f"{title} {label}".strip()))
        return files

    # ------------------------------------------------------------------ engine (also called, later, by NICOS)
    def simulate(self, state):
        """McStas event file (weights in n/s) for a device state; None if the shutter is closed (only the detector
        background remains). Each configuration is simulated once (disk cache)."""
        if state["shutter"] == "closed":
            return None
        back = self._instrument(state["sample"])
        tag, mcpl = self._upstream(state)
        runner = tw.Runner(back, f"{RUN_ROOT}/mcstas/{state['sample']}_{'focus' if self.focus else 'phys'}_"
                                 f"{tag}_c{self.copies}", mpi=self.mpi)
        name = (f"D{state['pinhole']:.3f}_x{state['stage_x']:+.4f}_rot{state['stage_rot']:+.2f}_"
                f"diff{int(state['diffuser'] == 'in')}")
        if not runner.complete(runner.folder(name)):
            print(f"McStas simulation of configuration {tag} {name} (once, then cached)...")
        folder = runner.run(name, 1, mcpl_file=mcpl, repeat=self.repeat, D=state["pinhole"],
                            sample_x=state["stage_x"], sample_rot=state["stage_rot"],
                            use_diffuser=int(state["diffuser"] == "in"))
        return tw.mcpl_path(folder, "events")

    def model(self, state):
        """Hybrid open-beam model for (chopper mode, D, diffuser): built from the full McStas simulation of the open
        beam (sample out, stage_x = 0.5 m), once, then cached."""
        tag, mcpl = self._upstream(state)
        key = (tag, state["pinhole"], state["diffuser"])
        if key not in self._models:
            # Open beam: the sample is out of the beam, so the reference sample instrument is used for every sample
            events_ob = self.simulate(dict(state, stage_x=0.5, stage_rot=0.0, sample=REFERENCE_SAMPLE))
            self._models[key] = hy.HybridModel(mcpl, state["pinhole"], events_ob, field=FIELD,
                                               cache_dir=f"{RUN_ROOT}/hybrid/{tag}",
                                               lam=LAM_RANGE[state["choppers"]])
        return self._models[key]

    def _instrument(self, sample):
        vols = self.samples()[sample]["volumes"]
        key = (sample, repr(vols))
        if key not in self._back:
            os.makedirs(BUILD, exist_ok=True)
            shutil.copy(os.path.join(COMPONENTS, "Graphite_Diffuser_focus.comp"), BUILD)   # McStas searches BUILD
            # the name carries a fingerprint of the geometry: a sample changed under the same name is simulated again
            tag = sample if sample in SAMPLES else f"{sample}_{hashlib.md5(repr(vols).encode()).hexdigest()[:6]}"
            self._back[key] = tw.build_back(
                f"ODIN_twin_{tag}_{'focus' if self.focus else 'phys'}", BUILD,
                sample=_with_rotation(_union_boxes(vols)), det_size=FOV,
                diffuser=not self.focus, before_sample=_focused_diffuser if self.focus else None,
                sample_monitors=True)   # monitors needed: Runner.complete() checks their data
        return self._back[key]

    def _upstream(self, state):
        """(short tag, MCPL file) of the precomputed upstream part for the chopper mode of the state."""
        mode = state["choppers"]
        delta = round(float(state["wfm_delta"]), 2) if mode == "wfm" else None
        if (mode, delta) not in FRONTS:
            raise ValueError(f"no precomputed upstream part for {mode} δ={delta}; available: {list(FRONTS)}")
        tw_delta, n = FRONTS[(mode, delta)]
        folder = tw.front_folder(mode, n, tw_delta)
        if not tw.Runner.complete(folder):
            raise RuntimeError(f"upstream part missing: {folder} (compute it with "
                               f"odin_mcstas.front({mode!r}, {n:.0e}, wfm_delta={tw_delta}))")
        tag = f"wfm{delta:.2f}_N{n:.0e}" if mode == "wfm" else f"{mode}_N{n:.0e}"
        return tag, tw.mcpl_path(folder, "guide_exit")

    # ------------------------------------------------------------------ files, log
    def _nexus_settings(self):
        out = {}
        for d in self.devices.values():
            if d.nexus is None:
                continue
            v = d.to_nexus(d.value) if d.to_nexus else d.value
            for path in (d.nexus if isinstance(d.nexus, tuple) else (d.nexus,)):
                out[path] = v
        return out

    def _last_number(self):
        nums = [int(f[5:11]) for f in os.listdir(self.folder) if f.startswith("odin_") and f.endswith(".nxs")]
        return max(nums, default=0)

    def _log(self, action, details):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(time=_dt.datetime.now().isoformat(timespec="seconds"), action=action,
                                    details=details), ensure_ascii=False) + "\n")
