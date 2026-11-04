"""McStas engine of the ODIN digital twin: building blocks to build and run the McStas model of ODIN.

English, self-contained copy of the parts of `ODIN_formation/odin_twin.py` (French ODIN notebook series) used by the
twin; the physics is the same.

The beamline model (ESS source, bispectral extraction, guides, choppers) is the official one,
https://git.esss.dk/dmsc-instrumentmodels/odin (Python package `ODIN_instr`). It is not copied: it is imported, then
split into two parts:

  * build_front()  : source -> guides -> choppers -> guide exit (49 m). The neutrons leaving the guide are written to
                     an MCPL file (position, direction, λ, time, weight). This is the expensive part: it is computed
                     once per chopper mode (front()).
  * build_back()   : reads this MCPL file -> pinhole -> diffuser -> sample -> detector. This is the fast part: it is
                     run again for every sample, pinhole, position.
  * Runner         : compiles once, runs the simulations (MPI), keeps the results in a disk cache.
  * read_mcpl() / iter_mcpl() : MCPL files (beam or detector events) as numpy arrays.
  * chopper_table() / tof_run() : chopper settings of the model and the `tof` package model (time-distance diagrams).
  * sigma_tot()    : attenuation coefficient Σ(λ) from NCrystal.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess

import numpy as np
import mcstasscript as ms

import odin_paths

# --------------------------------------------------------------------------- geometry (optical axis, m)
Z_GUIDE_EXIT = 49.01        # end of the last guide (component "guide_end" of the model)
Z_PINHOLE = 50.0            # pinhole, at the second focal point of the guide
Z_SAMPLE = 60.5             # sample position (moderator -> sample distance)
L_PINHOLE_SAMPLE = Z_SAMPLE - Z_PINHOLE   # 10.5 m: the "L" of the L/D ratio
DET_DIST = 0.05             # sample -> detector (as in the examples of the ODIN repository)
H_OVER_M = 3956.034         # h/m_n in m·Å/s: λ[Å] = 3956 / v[m/s]

# Cache of the simulations (no spaces allowed: McStas command line)
RUN_ROOT = odin_paths.RUN_ROOT

# Chopper modes (chopper names of the ODIN_instr model)
ALL_CHOPPERS = ["wfm_1", "wfm_2", "foc_1", "bp_1", "foc_2", "bp_2", "t0", "foc_3", "foc_4", "foc_5"]
MODES = {
    "white": None,                                  # white beam: no chopper
    # "natural" resolution: band-pass choppers and T0 only
    "natural": dict(wfm_1=False, wfm_2=False, foc_1=False, bp_1=True, foc_2=False, bp_2=True,
                    t0=True, foc_3=False, foc_4=False, foc_5=False),
    "wfm": {c: True for c in ALL_CHOPPERS},         # wavelength-frame multiplication: all choppers
}
# Wavelength range drawn at the source for each mode [Å]. White beam: wide; with choppers only 1–9 Å can pass.
FRONT_LAM = {"white": (0.5, 15.0), "natural": (1.0, 9.0), "wfm": (1.0, 9.0)}
# Number of simulated pulses. The band-pass choppers turn at 7 Hz (half of 14 Hz): they let through ONE pulse out of
# TWO (pulse skipping). The source weights are normalized for a train of identical pulses; simulating 2 pulses, of
# which one passes, directly gives the time-averaged flux (with 1 pulse it would be overestimated by a factor 2).
FRONT_PULSES = {"white": 1, "natural": 2, "wfm": 2}
EXE = ".exe" if os.name == "nt" else ".out"        # extension of the executables written by mcrun


def _odin_localcomps():
    import ODIN_instr
    return os.path.join(os.path.dirname(ODIN_instr.__file__), "localcomps")


# --------------------------------------------------------------------------- upstream part (source -> guide)
def build_front(mode, build_dir, name=None, lam_min=1.0, lam_max=9.0):
    """Official ODIN model cut at the guide exit, with an MCPL output file.

    mode: "white", "natural" or "wfm" (MODES). The instrument parameters of the model (wfm_delta, n_pulses, l_min,
    l_max, WFM2_phase_offset, jitter_wfmc_2, ...) can still be set at run time.
    """
    from ODIN_instr.make import make as make_odin
    name = name or f"ODIN_front_{mode}"
    os.makedirs(build_dir, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):          # the model prints where its chopper data come from
        instr = make_odin(include_choppers=MODES[mode] is not None, enable_choppers=MODES[mode],
                          include_monitors=False, input_path=build_dir, name=name)
    # Everything after the choppers (pinhole, diffuser, sample monitors) belongs to the downstream part. Removed
    # from the end, so that the references stay valid.
    names = [c.name for c in instr.component_list]
    for n in reversed(names[names.index("start_backend"):]):
        instr.remove_component(n)
    instr.set_parameters(l_min=lam_min, l_max=lam_max)
    # Monitors at the guide exit (they restore the neutron, so the MCPL file is not affected)
    instr.add_component("guide_exit_psd", "PSD_monitor", AT=Z_GUIDE_EXIT + 1e-6, RELATIVE="optical_axis").set_parameters(
        nx=100, ny=100, xwidth=0.06, yheight=0.06, filename='"guide_exit_psd.dat"', restore_neutron=1)
    instr.add_component("guide_exit_lambda", "L_monitor", AT=Z_GUIDE_EXIT + 1e-6, RELATIVE="optical_axis").set_parameters(
        nL=400, Lmin="l_min", Lmax="l_max", xwidth=0.06, yheight=0.06, filename='"guide_exit_lambda.dat"',
        restore_neutron=1)
    out = instr.add_component("guide_exit", "MCPL_output", AT=0, RELATIVE="optical_axis")
    out.set_parameters(filename='"guide_exit"', weight_mode=1, polarisationuse=0)
    return instr


# --------------------------------------------------------------------------- downstream part (pinhole -> detector)
def build_back(name, build_dir, sample=None, det_size=0.08, det_dist=DET_DIST,
               D_default=0.03, sample_monitors=True, diffuser=True, lam_min=1.0, lam_max=9.0, polarisation=False,
               events=True, before_sample=None):
    """Downstream part: MCPL (guide exit) -> square pinhole D -> graphite diffuser -> sample -> detector.

    sample(instr): function adding the sample, placed RELATIVE "sample_arm" (which follows sample_x).
    The detector is a square window det_size at det_dist after the sample; every neutron reaching it is recorded
    (event) in events.mcpl.gz: position, arrival time, true λ, weight.
    Instrument parameters (set at run time, no recompilation):
      mcpl_file : MCPL file of the upstream part (path without spaces);
      repeat    : number of reuses of each neutron of the file (with a small random smearing);
      D, sample_x, use_diffuser.
    polarisation=True: the polarisation vector of each neutron is also written to the event file.
    events=False: no event file (the monitors added by sample() are enough).
    before_sample(instr): function adding components between the diffuser and the sample (placed RELATIVE
      "optical_axis", at z < Z_SAMPLE); the twin uses it for the focused diffuser.
    """
    os.makedirs(build_dir, exist_ok=True)
    instr = ms.McStas_instr(name, input_path=build_dir, author="ACCESS training (DTU)", origin="DTU")
    instr.add_search(_odin_localcomps())
    instr.add_parameter("string", "mcpl_file", value='"guide_exit.mcpl.gz"', comment="MCPL file from the front end")
    instr.add_parameter("int", "repeat", value=10, comment="number of times each MCPL neutron is reused")
    instr.add_parameter("double", "lam_lo", value=0.1, comment="[AA] only MCPL neutrons with lam_lo < lambda < lam_hi are used")
    instr.add_parameter("double", "lam_hi", value=100.0, comment="[AA] upper wavelength limit")
    instr.add_parameter("int", "preload", value=0, comment="1: load the (filtered) MCPL file in memory once per process")
    instr.add_parameter("double", "D", value=D_default, comment="[m] side of the square pinhole")
    # Open beam: the sample is translated out of the beam (sample_x = 0.5 m), as on the real instrument.
    # (A WHEN condition cannot be used: Union geometries are set up once, at initialization.)
    instr.add_parameter("double", "sample_x", value=0.0, comment="[m] horizontal sample translation (0.5 = out of beam)")
    instr.add_parameter("int", "use_diffuser", value=1, comment="1: graphite diffuser in the beam, 0: removed")
    instr.add_component("origin", "Progress_bar")
    src = instr.add_component("optical_axis", "MCPL_input", AT=0, RELATIVE="origin")
    # Smearing needed when events are repeated; kept far below the instrument resolutions
    # E [meV] = 81.8042 / lambda^2 [AA]
    src.set_parameters(filename="mcpl_file", repeat_count="repeat", Emin="81.8042/(lam_hi*lam_hi)",
                       Emax="81.8042/(lam_lo*lam_lo)", preload="preload", v_smear=1e-5,
                       pos_smear=2e-4, dir_smear=2e-3, verbose=0)
    instr.add_component("pinhole_2", "Slit", AT=Z_PINHOLE, RELATIVE="optical_axis").set_parameters(
        xwidth="D", yheight="D")
    if diffuser:
        g = instr.add_component("graph", "Graphite_Diffuser", AT=Z_PINHOLE + 1e-3, RELATIVE="optical_axis")
        g.set_parameters(xwidth=0.1, ywidth=0.1, thick=0.2)
        g.set_WHEN("use_diffuser == 1")
    if before_sample is not None:
        before_sample(instr)
    instr.add_component("sample_position", "Arm", AT=Z_SAMPLE, RELATIVE="optical_axis")
    if sample_monitors:
        # Open-beam monitors just before the sample (field of view 30 cm x 30 cm, as in the official model)
        arm = instr.add_component("sample_monitor_arm", "Arm", AT=-0.01, RELATIVE="sample_position")
        instr.add_component("beam_psd", "PSD_monitor", RELATIVE=arm).set_parameters(
            nx=150, ny=150, xwidth=0.3, yheight=0.3, filename='"beam_psd.dat"', restore_neutron=1)
        instr.add_component("beam_psd_fov", "PSD_monitor", RELATIVE=arm).set_parameters(
            nx=80, ny=80, xwidth=det_size, yheight=det_size, filename='"beam_psd_fov.dat"', restore_neutron=1)
        instr.add_component("beam_lambda", "L_monitor", RELATIVE=arm).set_parameters(
            nL=400, Lmin=lam_min, Lmax=lam_max, xwidth=0.01, yheight=0.01, filename='"beam_lambda.dat"',
            restore_neutron=1)
    instr.add_component("sample_arm", "Arm", AT=["sample_x", 0, 0], RELATIVE="sample_position")
    if sample is not None:
        sample(instr)
    instr.add_component("detector_window", "Slit", AT=det_dist, RELATIVE="sample_position").set_parameters(
        xwidth=det_size, yheight=det_size)
    if events:
        ev = instr.add_component("events", "MCPL_output", AT=0, RELATIVE="detector_window")
        ev.set_parameters(filename='"events"', weight_mode=1, polarisationuse=1 if polarisation else 0)
    return instr


# --------------------------------------------------------------------------- running the simulations
def front_folder(mode, ncount, wfm_delta=0.3):
    """Cache folder of the upstream part: RUN_ROOT/front/<mode>_delta<δ>_N<ncount>/."""
    return f"{RUN_ROOT}/front/{mode}_delta{wfm_delta:.2f}_N{ncount:.0e}"


def front(mode, ncount, wfm_delta=0.3, mpi=12, build_dir=None):
    """Upstream part computed (or read from the cache) for one chopper mode. Returns the folder of the simulation
    (monitors + guide_exit.mcpl.gz). Expensive: ~1 h for 1e10 neutrons in WFM mode on 12 cores."""
    lmin, lmax = FRONT_LAM[mode]
    instr = build_front(mode, build_dir or odin_paths.BUILD, lam_min=lmin, lam_max=lmax)
    r = Runner(instr, f"{RUN_ROOT}/front", mpi=mpi)
    return r.run(os.path.basename(front_folder(mode, ncount, wfm_delta)), ncount, wfm_delta=wfm_delta,
                 n_pulses=FRONT_PULSES[mode])


class Runner:
    """Compiles the instrument once, then runs the MPI executable for each simulation, with a disk cache.

    A simulation whose folder exists and is complete is read back instead of being recomputed; deleting its folder
    forces a new computation.
    """

    def __init__(self, instr, run_dir, mpi=12):
        self.instr, self.run_dir, self.mpi = instr, run_dir.replace("\\", "/"), mpi
        self.build_dir = instr.input_path
        os.makedirs(self.build_dir, exist_ok=True)
        os.makedirs(self.run_dir, exist_ok=True)
        assert " " not in self.run_dir, "run_dir must not contain spaces"
        self.exe = os.path.join(self.build_dir, instr.name + EXE)
        self._compiled = False

    def compile(self, force=False):
        instr_file = os.path.join(self.build_dir, self.instr.name + ".instr")
        old = open(instr_file, "rb").read() if os.path.isfile(instr_file) else b""
        self.instr.write_full_instrument()
        new = open(instr_file, "rb").read()
        strip = lambda b: b"\n".join(l for l in b.splitlines() if b"Date:" not in l)  # dated header
        if not force and os.path.isfile(self.exe) and hashlib.md5(strip(old)).digest() == hashlib.md5(strip(new)).digest():
            self._compiled = True
            return
        tmp = os.path.join(self.run_dir, "_compile_test")
        if os.path.isdir(tmp):
            shutil.rmtree(tmp)
        cmd = f'mcrun -c -y --mpi={self.mpi} -n 0 {self.instr.name}.instr -d "{tmp}"'
        p = subprocess.run(cmd, shell=True, cwd=self.build_dir, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if not os.path.isfile(self.exe):
            print(p.stdout[-3000:], p.stderr[-3000:])
            raise RuntimeError("McStas compilation failed")
        self._compiled = True

    @staticmethod
    def complete(folder):
        """McStas writes mccode.sim at the start; the 'begin data' blocks only appear at the end."""
        f = os.path.join(folder, "mccode.sim")
        return os.path.isfile(f) and "begin data" in open(f, errors="ignore").read()

    def folder(self, name):
        return f"{self.run_dir}/{name}"

    def run(self, name, ncount, quiet=True, **params):
        """Runs (or reads from the cache) one simulation; returns the result folder.
        Instrument parameters are given as keywords (e.g. D=0.03, mcpl_file=...)."""
        for v in params.values():
            assert " " not in str(v), "a parameter must not contain spaces (command line)"
        folder = self.folder(name)
        if self.complete(folder):
            return folder
        if os.path.isdir(folder):                       # interrupted simulation: start again
            shutil.rmtree(folder)
        if not self._compiled:
            self.compile()
        par = " ".join(f"{k}={v}" for k, v in params.items())
        # -y: default values for the parameters not given (otherwise the executable waits for input)
        cmd = (f'mpiexec -np {self.mpi} "{os.path.abspath(self.exe)}" -y --ncount={int(ncount)} '
               f'--dir="{folder}" --format=McCode {par}')
        p = subprocess.run(cmd, shell=True, cwd=self.build_dir, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if not self.complete(folder):
            print(p.stdout[-3000:], p.stderr[-3000:])
            raise RuntimeError(f"simulation {name} failed")
        if not quiet:
            print(p.stdout[-1500:])
        return folder


def load(folder):
    """McStas monitors of a simulation (list of McStasScript objects)."""
    return ms.load_data(folder)


def mon(data, name):
    return ms.name_search(name, data)


# --------------------------------------------------------------------------- MCPL files
def read_mcpl(path, light=False, pol=False):
    """Reads an MCPL file written by McStas. Returns a dict of numpy arrays:

    x, y, z [m]; ux, uy, uz (direction); t [s]; lam [Å] (true, known in a simulation);
    w [n/s]: intensity carried by each neutron (the sum of w is the total intensity).
    light=True: only x, y, t, lam, w, in single precision (event files of several GB).
    pol=True: adds sx, sy, sz (polarisation vector, if the file has it: build_back(polarisation=True)).
    """
    import mcpl
    f = mcpl.MCPLFile(path)
    keys = ("x", "y", "time", "ekin", "weight") if light else ("x", "y", "z", "ux", "uy", "uz", "time", "ekin", "weight")
    if pol:
        keys = keys + ("polx", "poly", "polz")
    dt = np.float32 if light else np.float64
    cols = {k: [] for k in keys}
    for b in f.particle_blocks:
        for k in keys:
            cols[k].append(np.asarray(getattr(b, k), dtype=dt))
    d = {k: (np.concatenate(v) if v else np.zeros(0, dtype=dt)) for k, v in cols.items()}
    n_rays = f.stat_sum.get("initial_ray_count", 1.0) if hasattr(f, "stat_sum") else 1.0
    out = dict(x=d["x"] / 100, y=d["y"] / 100, t=d["time"].astype(np.float64) / 1000,
               lam=np.sqrt(81.8042 / (d["ekin"].astype(np.float64) * 1e9)).astype(dt), w=d["weight"] / dt(n_rays))
    if not light:
        out.update(z=d["z"] / 100, ux=d["ux"], uy=d["uy"], uz=d["uz"])
    if pol:
        out.update(sx=d["polx"], sy=d["poly"], sz=d["polz"])
    out["n_rays"] = n_rays
    return out


def iter_mcpl(path, light=True, pol=False, chunk=5_000_000):
    """Like read_mcpl, but in chunks of `chunk` events (generator of dicts): fills histograms progressively without
    loading an event file of several GB in memory."""
    import mcpl
    f = mcpl.MCPLFile(path, blocklength=int(chunk))
    n_rays = f.stat_sum.get("initial_ray_count", 1.0) if hasattr(f, "stat_sum") else 1.0
    dt = np.float32 if light else np.float64
    for b in f.particle_blocks:
        g = lambda k: np.asarray(getattr(b, k), dtype=dt)
        out = dict(x=g("x") / 100, y=g("y") / 100, t=np.asarray(b.time, dtype=np.float64) / 1000,
                   lam=np.sqrt(81.8042 / (np.asarray(b.ekin, dtype=np.float64) * 1e9)).astype(dt),
                   w=g("weight") / dt(n_rays))
        if not light:
            out.update(z=g("z") / 100, ux=g("ux"), uy=g("uy"), uz=g("uz"))
        if pol:
            out.update(sx=g("polx"), sy=g("poly"), sz=g("polz"))
        yield out


def mcpl_path(folder, name):
    for ext in (".mcpl.gz", ".mcpl"):
        p = os.path.join(folder, name + ext)
        if os.path.isfile(p):
            return p.replace("\\", "/")
    raise FileNotFoundError(os.path.join(folder, name + ".mcpl[.gz]"))


# --------------------------------------------------------------------------- choppers
def chopper_table(mode, wfm_delta=0.3, cache_dir=None):
    """Positions, frequencies, phases and openings of the choppers of the model (for the `tof` package).

    The full model is run once with save_comp_pars (a few seconds, 1000 neutrons), then the parameters actually
    used by McStas (computed phases, absolute positions) are read back. Cached as JSON.
    """
    from mcstasscript.data.data import ComponentData
    from ODIN_instr.make import make as make_odin
    from odin_support import analysis
    cache_dir = cache_dir or f"{RUN_ROOT}/choppers"
    os.makedirs(cache_dir, exist_ok=True)
    js = f"{cache_dir}/choppers_{mode}_delta{wfm_delta:.3f}.json"
    if os.path.isfile(js):
        return json.load(open(js))
    bdir = f"{cache_dir}/build_{mode}"
    os.makedirs(bdir, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        instr = make_odin(include_choppers=MODES[mode] is not None, enable_choppers=MODES[mode],
                          include_monitors=False, input_path=bdir, output_path=f"{bdir}/run",
                          name=f"ODIN_choppers_{mode}")
        instr.settings(ncount=1000, mpi=1, suppress_output=True, save_comp_pars=True, force_compile=True)
        instr.set_parameters(wfm_delta=wfm_delta)
        instr.backengine()
    comp = ComponentData(os.path.join(bdir, "component_parameters.txt")).read()
    _, ch = analysis.read_comp_pars(instr.component_list, component_data=comp)
    ch = {k: {kk: (list(map(float, vv)) if isinstance(vv, list) else vv) for kk, vv in v.items()} for k, v in ch.items()}
    json.dump(ch, open(js, "w"), indent=1)
    shutil.rmtree(bdir, ignore_errors=True)
    return ch


def tof_run(choppers, distance, neutrons=2_000_000, seed=1):
    """"Analytical" model of the beamline with the `tof` package (ESS/DMSC): ESS pulse, choppers, detector.

    Each neutron flies in a straight line; the choppers stop it or not. Much faster than McStas (no guide, no
    geometry), but it only gives the time–distance–λ relations. Returns the tof result (.plot(): time–distance diagram).
    """
    import scipp as sc
    import tof
    Hz, deg, meter = sc.Unit("Hz"), sc.Unit("deg"), sc.Unit("m")
    chs = [tof.Chopper(frequency=c["frequency"] * Hz,
                       open=sc.array(dims=["cutout"], values=c["open"], unit="deg"),
                       close=sc.array(dims=["cutout"], values=c["close"], unit="deg"),
                       phase=c["phase"] * deg, distance=c["distance"] * meter, name=c["name"])
           for c in choppers.values()]
    source = tof.Source(facility="ess", neutrons=neutrons, pulses=1, seed=seed)
    det = tof.Detector(distance=distance * meter, name="detector")
    return tof.Model(source=source, choppers=chs, detectors=[det]).run()


# --------------------------------------------------------------------------- materials
def sigma_tot(cfg, wl):
    """Σ(λ) in cm^-1 (barn/Å^3 = cm^-1), from NCrystal."""
    import NCrystal as NC
    m = NC.load(cfg)
    return (m.scatter.xsect(wl=wl) + m.absorption.xsect(wl=wl)) * m.info.getNumberDensity()
