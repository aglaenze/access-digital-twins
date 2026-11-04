"""McStas engine of the LoKI digital twin (small-angle neutron scattering, ESS).

English, self-contained copy of the parts of `LOKI_formation/loki_twin.py` (French LoKI notebook series, where every
step is explained and validated) used by the twin; the physics is the same.

The beamline model (ESS source, extraction, benders, choppers, collimation) is the official one,
https://git.esss.dk/dmsc-instrumentmodels/LOKI (file instr/LOKI_main.instr). It is not copied by hand: it is read and
cut in two:

  * front()     : official model cut just before the sample; the neutrons leaving the sample aperture are written
                  to an MCPL file. Expensive (~15 min for 1e9 neutrons on 8 cores): once per configuration
                  (collimation length, apertures, wavelength band).
  * back()      : reads this file -> sample (component SANS_Iq_table: tabulated dΣ/dΩ(Q) in absolute units)
                  -> scattered neutrons (MCPL) + incident and transmitted wavelength monitors.
  * Detector    : the 9 tube panels of the official model (front, middle, rear banks); each scattered neutron goes in
                  a straight line to the first panel it meets; pixels, arrival times.
  * events()    : what the instrument measures: arrival time (modulo the source period, frames unwrapped) and pixel
                  -> wavelength and Q, as in a real time-of-flight SANS reduction.
  * reduce()    : I(Q) in absolute units [cm⁻¹ sr⁻¹], one curve per detector bank.
"""
import hashlib
import os
import re
import shutil
import subprocess

import numpy as np

import loki_paths as paths

RUN_ROOT = paths.RUN_ROOT
BUILD = paths.BUILD
EXE = ".exe" if os.name == "nt" else ".out"

H_OVER_M = 3956.034          # h/m_n in m·Å/s: λ[Å] = 3956 / v[m/s]
FRAME = 1 / 14               # source period [s]
Z_SAMPLE_BACK = 0.001        # sample center in the frame of LOKI_back (1 mm after the MCPL plane)
L1 = 23.52                   # moderator -> sample center along the beam [m]
T_EMISSION = 1.80e-3         # mean emission time of the neutrons in the moderator [s]
TAU = 2.86e-3                # proton pulse length [s]
Z_CHOP2 = 15.13              # effective distance of the frame-overlap chopper pair (loki_functions.c: 15.21 - 0.08)


# --------------------------------------------------------------------------- running McStas (MPI executable, cache)
def complete(folder):
    """McStas writes mccode.sim at the start; the 'begin data' blocks only appear at the end."""
    f = os.path.join(folder, "mccode.sim")
    return os.path.isfile(f) and "begin data" in open(f, errors="ignore").read()


class Runner:
    """Compiles an .instr file once (mcrun -c), then runs the MPI executable, with one cache folder per simulation.
    A complete folder is read back instead of being recomputed; deleting it forces a new computation."""

    def __init__(self, instr_file, run_dir, mpi=8):
        self.instr_file = instr_file.replace("\\", "/")
        self.build_dir = os.path.dirname(self.instr_file)
        self.name = os.path.splitext(os.path.basename(self.instr_file))[0]
        self.exe = os.path.join(self.build_dir, self.name + EXE)
        self.run_dir, self.mpi = run_dir.replace("\\", "/"), mpi
        assert " " not in self.run_dir, "run_dir must not contain spaces"
        os.makedirs(self.run_dir, exist_ok=True)

    def compile(self):
        stamp = self.exe + ".md5"
        h = hashlib.md5(open(self.instr_file, "rb").read()).hexdigest()
        if os.path.isfile(self.exe) and os.path.isfile(stamp) and open(stamp).read() == h:
            return
        tmp = f"{self.run_dir}/_compile_test"
        shutil.rmtree(tmp, ignore_errors=True)
        for f in (self.exe, stamp):          # remove the old executable: a failed compilation must not go unnoticed
            if os.path.isfile(f):
                os.remove(f)
        p = subprocess.run(f'mcrun -c -y --mpi={self.mpi} -n 0 {self.name}.instr -d "{tmp}"', shell=True,
                           cwd=self.build_dir, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if not os.path.isfile(self.exe):
            print(p.stdout[-3000:], p.stderr[-3000:])
            raise RuntimeError("McStas compilation failed")
        shutil.rmtree(tmp, ignore_errors=True)
        open(stamp, "w").write(h)

    def run(self, name, ncount, **params):
        for v in params.values():
            assert " " not in str(v), "a parameter must not contain spaces (command line)"
        folder = f"{self.run_dir}/{name}"
        if complete(folder):
            return folder
        shutil.rmtree(folder, ignore_errors=True)      # interrupted simulation: start again
        self.compile()
        par = " ".join(f"{k}={v}" for k, v in params.items())
        cmd = (f'mpiexec -np {self.mpi} "{os.path.abspath(self.exe)}" -y --ncount={int(ncount)} '
               f'--dir="{folder}" --format=McCode {par}')
        p = subprocess.run(cmd, shell=True, cwd=self.build_dir, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if not complete(folder):
            print(p.stdout[-3000:], p.stderr[-3000:])
            raise RuntimeError(f"simulation {name} failed")
        return folder


# --------------------------------------------------------------------------- upstream part: official model, cut
def build_front(build_dir=BUILD):
    """Writes build/LOKI_front.instr: LOKI_main.instr cut just before the sample (everything before the comment
    "/// Sample ///" kept as it is), with an MCPL_output at the sample position (5 mm after the sample aperture)."""
    os.makedirs(build_dir, exist_ok=True)
    shutil.copytree(os.path.join(paths.LOKI_REPO, "instr", "includes"), os.path.join(build_dir, "includes"),
                    dirs_exist_ok=True)
    src = open(os.path.join(paths.LOKI_REPO, "instr", "LOKI_main.instr"), encoding="utf-8", errors="replace").read()
    cut = src.index("/// Sample ////")
    front_instr = src[:cut] + """
/// Beam at the sample position, written for the back end (ACCESS digital twin) ///
COMPONENT beam_at_sample = MCPL_output(filename="beam_at_sample", weight_mode=1, polarisationuse=0)
AT (0, 0, 0.005) RELATIVE sampleaperture

FINALLY
%{
%}
END
"""
    front_instr = front_instr.replace("DEFINE INSTRUMENT LOKI_main(", "DEFINE INSTRUMENT LOKI_front(")
    path = os.path.join(build_dir, "LOKI_front.instr")
    if not os.path.isfile(path) or open(path, encoding="utf-8").read() != front_instr:
        open(path, "w", encoding="utf-8").write(front_instr)
    return path


def config_name(collen, l_min, l_max, sourceapx, sampleapx, pulseskip):
    return (f"col{collen:g}m_src{sourceapx*1e3:.0f}mm_sam{sampleapx*1e3:.0f}mm_"
            f"lam{l_min:g}-{l_max:g}_skip{pulseskip}")


def front_folder(collen=3.0, l_min=3.0, l_max=11.5, sourceapx=0.03, sampleapx=0.01, pulseskip=0, ncount=1e9):
    return f"{RUN_ROOT}/front/{config_name(collen, l_min, l_max, sourceapx, sampleapx, pulseskip)}_N{ncount:.0e}"


def front(collen=3.0, l_min=3.0, l_max=11.5, sourceapx=0.03, sampleapx=0.01, pulseskip=0, ncount=1e9, mpi=8):
    """Upstream part for one configuration (computed, or read from the cache). Returns the folder: monitors of the
    official model + beam_at_sample.mcpl.gz. ~1.4 GB of RAM per MPI process: never run two at the same time."""
    folder = front_folder(collen, l_min, l_max, sourceapx, sampleapx, pulseskip, ncount)
    if complete(folder):
        try:
            mcpl_path(folder, "beam_at_sample")
            return folder
        except FileNotFoundError:                    # monitors written but MCPL files not merged: interrupted run
            shutil.rmtree(folder, ignore_errors=True)
    r = Runner(build_front(), f"{RUN_ROOT}/front", mpi=mpi)
    # reardet plays no role before the sample; sampletype=-1: no sample in the official model
    return r.run(os.path.basename(folder), ncount, collen=collen, reardet=5.0, l_min=l_min, l_max=l_max,
                 sourceapx=sourceapx, sampleapx=sampleapx, pulseskip=pulseskip, sampletype=-1)


# --------------------------------------------------------------------------- downstream part: the sample
BACK_INSTR = r"""/*******************************************************************************
* LOKI_back : back end of the LoKI digital twin (ACCESS, DTU).
* Reads the neutrons at the sample position (MCPL file written by LOKI_front, i.e. the
* official LOKI_main.instr cut before the sample), scatters them in a sample described by a
* tabulated dSigma/dOmega(Q) in absolute units (component SANS_Iq_table), and writes
*   - the scattered neutrons in scattered.mcpl.gz (projected onto the detector banks in Python),
*   - the transmitted (unscattered) beam in wavelength monitors (transmission measurement).
*******************************************************************************/
DEFINE INSTRUMENT LOKI_back(string mcpl_file = "beam_at_sample.mcpl.gz", int repeat = 12,
  string iq_file = "Iq.dat", int sample_in = 1, double thickness = 0.001, double xwidth = 0.02,
  double yheight = 0.02, double mu_abs = 0.0, double mu_rem = 0.0, double iflat = 0.0,
  double tth_min = 0.05, double tth_max = 60.0, double p_scatter = 0.95, double lmin = 0.5, double lmax = 25.0)

USERVARS
%{
  int flag_scatt;
  int qtrue;           /* true momentum transfer of the scattering, round(Q [1/AA] * 1e7), stored as MCPL userflag */
  double vx_in;        /* incoming velocity (one declaration per line: required by McStas USERVARS) */
  double vy_in;
  double vz_in;
%}

TRACE

COMPONENT origin = Progress_bar()
AT (0, 0, 0) ABSOLUTE

/* MCPL_input: smearing is needed when the neutrons are reused; it is kept far below the resolution */
COMPONENT beam = MCPL_input(filename = mcpl_file, repeat_count = repeat, v_smear = 1e-4,
  pos_smear = 1e-5, dir_smear = 2e-3, verbose = 0, polarisationuse = 0)
AT (0, 0, 0) RELATIVE origin
EXTEND %{
  flag_scatt = 0;
  qtrue = 0;
  vx_in = vx; vy_in = vy; vz_in = vz;
%}

/* the MCPL file is written at the sample position: the sample is placed 1 mm downstream */
COMPONENT sample_pos = Arm()
AT (0, 0, 0.001) RELATIVE origin

COMPONENT incident_lambda = L_monitor(nL = 245, Lmin = lmin, Lmax = lmax, xwidth = 0.1, yheight = 0.1,
  filename = "incident_lambda", restore_neutron = 1)
AT (0, 0, -0.0005) RELATIVE sample_pos

COMPONENT sample = SANS_Iq_table(Iq_file = iq_file, xwidth = xwidth, yheight = yheight, zdepth = thickness,
  mu_abs = mu_abs, mu_rem = mu_rem, iflat = iflat, tth_min = tth_min, tth_max = tth_max, p_scatter = p_scatter)
WHEN (sample_in == 1)
AT (0, 0, 0) RELATIVE sample_pos
EXTEND %{
  if (SCATTERED) {
    flag_scatt = 1;
    qtrue = (int) (V2K * sqrt ((vx - vx_in) * (vx - vx_in) + (vy - vy_in) * (vy - vy_in) + (vz - vz_in) * (vz - vz_in)) * 1e7 + 0.5);
  }
%}

COMPONENT transmitted_lambda = L_monitor(nL = 245, Lmin = lmin, Lmax = lmax, xwidth = 0.1, yheight = 0.1,
  filename = "transmitted_lambda", restore_neutron = 1)
WHEN (flag_scatt == 0)
AT (0, 0, 0.01) RELATIVE sample_pos

COMPONENT scattered = MCPL_output(filename = "scattered", weight_mode = 1, polarisationuse = 0,
  userflag = "qtrue", userflagcomment = "true Q of the scattering, round(Q [1/AA] * 1e7)")
WHEN (flag_scatt == 1)
AT (0, 0, 0.01) RELATIVE sample_pos

END
"""


def build_back(build_dir=BUILD):
    os.makedirs(build_dir, exist_ok=True)
    shutil.copy(os.path.join(paths.COMPONENTS, "SANS_Iq_table.comp"), build_dir)
    path = os.path.join(build_dir, "LOKI_back.instr")
    if not os.path.isfile(path) or open(path).read() != BACK_INSTR:
        open(path, "w").write(BACK_INSTR)
    return path


def write_iq(path, q, dsdo):
    """Table for SANS_Iq_table: Q [Å⁻¹], dΣ/dΩ [cm⁻¹ sr⁻¹]."""
    np.savetxt(path, np.column_stack([q, dsdo]), header="Q [1/AA]  dSigma/dOmega [1/cm/sr]", fmt="%.6e")


def back(front_dir, name, q, dsdo, thickness=1e-3, mu_abs=0.0, mu_rem=0.0, iflat=0.0, sample_in=1, repeat=8,
         series="samples", tth_max=60.0, mpi=8, width=0.015, p_scatter=0.95):
    """Downstream part (computed, or read from the cache): a sample (table q [Å⁻¹], dsdo [cm⁻¹ sr⁻¹]) in the beam of
    one configuration (folder of front()). thickness [m]; mu_abs [1/m] at 1.798 Å; mu_rem [1/m]; iflat [cm⁻¹ sr⁻¹].
    sample_in=0: no sample (empty beam). p_scatter: fraction of the rays sent to the "scattered" branch."""
    r = Runner(build_back(), f"{RUN_ROOT}/{series}", mpi=mpi)
    iq = f"{r.run_dir}/{name}_Iq.dat"
    write_iq(iq, q, dsdo)
    mc = mcpl_path(front_dir, "beam_at_sample")
    return r.run(name, mcpl_count(mc) * repeat, mcpl_file=mc, repeat=repeat, iq_file=iq, sample_in=sample_in,
                 thickness=thickness, xwidth=width, yheight=width, mu_abs=mu_abs, mu_rem=mu_rem, iflat=iflat,
                 tth_max=tth_max, p_scatter=p_scatter)


# --------------------------------------------------------------------------- MCPL files and monitors
def mcpl_path(folder, name):
    for ext in (".mcpl.gz", ".mcpl"):
        p = os.path.join(folder, name + ext)
        if os.path.isfile(p):
            return p.replace("\\", "/")
    raise FileNotFoundError(os.path.join(folder, name + ".mcpl[.gz]"))


def mcpl_count(path):
    import mcpl
    return mcpl.MCPLFile(path).nparticles


def read_mcpl(path):
    """MCPL file written by McStas -> dict of numpy arrays: x, y, z [m]; ux, uy, uz; t [s]; lam [Å] (true);
    w [n/s] (intensity carried by each neutron); q_true [Å⁻¹] for the "scattered" files (known in a simulation only)."""
    import mcpl
    f = mcpl.MCPLFile(path)
    keys = ("x", "y", "z", "ux", "uy", "uz", "time", "ekin", "weight")
    cols = {k: [] for k in keys}
    for b in f.particle_blocks:
        for k in keys:
            cols[k].append(np.asarray(getattr(b, k), dtype=np.float64))
    d = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in cols.items()}
    n_rays = f.stat_sum.get("initial_ray_count", 1.0)
    out = dict(x=d["x"] / 100, y=d["y"] / 100, z=d["z"] / 100, ux=d["ux"], uy=d["uy"], uz=d["uz"],
               t=d["time"] / 1000, lam=np.sqrt(81.8042 / (d["ekin"] * 1e9)), w=d["weight"] / n_rays, n_rays=n_rays)
    if f.opt_userflags:
        out["q_true"] = np.concatenate([np.asarray(b.userflags, dtype=np.float64) for b in f.particle_blocks]) * 1e-7
    return out


# MCPL_output does not move the neutron to its plane: it records the current position, in its own frame.
Z_SCATTERED_OUT = 0.01       # position of the "scattered" MCPL_output relative to the sample center (LOKI_back)


def scattered(back_folder):
    """Scattered neutrons (downstream file), positions (scattering point) in the frame centered on the sample."""
    ev = read_mcpl(mcpl_path(back_folder, "scattered"))
    ev["z"] = ev["z"] + Z_SCATTERED_OUT
    return ev


def monitor(folder, name):
    """1D McStas monitor: (x, I, error, N), I in n/s per bin."""
    for f in sorted(os.listdir(folder)):
        if f.startswith(name) and not f.endswith(".sim"):
            a = np.loadtxt(os.path.join(folder, f), comments="#")
            return a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    raise FileNotFoundError(f"{name} in {folder}")


# --------------------------------------------------------------------------- detectors (geometry of the official model)
def _rot(rx, ry, rz=0.0):
    """McStas rotation matrix (rot_set_rotation): local coordinates = R · (global - position)."""
    ax, ay, az = np.radians([rx, ry, rz])
    cx, sx, cy, sy, cz, sz = np.cos(ax), np.sin(ax), np.cos(ay), np.sin(ay), np.cos(az), np.sin(az)
    return np.array([[cy * cz, sx * sy * cz + cx * sz, sx * sz - cx * sy * cz],
                     [-cy * sz, cx * cz - sx * sy * sz, sx * cz + cx * sy * sz],
                     [sy, -sx * cy, cx * cy]])


# (name, bank, arm rotation (rx, ry), distance along the arm, panel rotation (rx, ry), width, height, tube direction)
# read from LOKI_main.instr (positions SI-7615-463, August 2025)
PANELS_OFFICIAL = [
    ("front_top", "front", (-32.0, 0.0), 1.3640, (14.7, 0.0), 1.2, 0.6816, "h"),
    ("front_bottom", "front", (27.5, 0.0), 1.340, (-10.0, 0.0), 1.2, 0.568, "h"),
    ("front_left", "front", (0.0, 25.6), 1.75, (0.0, -15.0), 0.9372, 1.2, "v"),
    ("front_right", "front", (0.0, -25.6), 1.75, (0.0, 15.0), 0.9372, 1.2, "v"),
    ("mid_top", "middle", (-9.7, 0.0), 2.95, (4.0, 0.0), 1.0, 0.4544, "h"),
    ("mid_bottom", "middle", (9.7, 0.0), 2.95, (-4.0, 0.0), 1.0, 0.4544, "h"),
    ("mid_right", "middle", (0.0, -6.5), 3.3, (0.0, 2.0), 0.3408, 0.5, "v"),
    ("mid_left", "middle", (0.0, 6.5), 3.3, (0.0, -2.0), 0.3408, 0.5, "v"),
    ("rear", "rear", (0.0, 0.0), None, (0.0, 0.0), 1.0, 1.59, "h"),
]
BANKS = ("front", "middle", "rear")
TUBE_PITCH = 0.0284          # tube pitch [m]
STRAWS = 7                   # straws per tube: transverse pixel 28.4/7 = 4.1 mm
PIX_ALONG = 0.004            # pixel along a tube [m] (charge-division resolution, simplified)
BEAMSTOP = 0.07              # side of the beam stop [m], 1 mm in front of the rear detector


class Panel:
    """One panel of tubes: position, orientation, pixels."""

    def __init__(self, name, bank, arm_rot, dist, rot, w, h, tubes):
        self.name, self.bank, self.w, self.h, self.tubes = name, bank, w, h, tubes
        Ra = _rot(*arm_rot)
        self.R = _rot(*rot) @ Ra                                  # global -> panel frame
        self.center = Ra.T @ np.array([0, 0, dist])                # panel center (sample frame)
        self.normal = self.R[2]
        if tubes == "h":   # horizontal tubes: y = stack of tubes (straws), x = along the tube
            self.nx, self.ny = int(round(w / PIX_ALONG)), int(round(h / TUBE_PITCH)) * STRAWS
        else:
            self.nx, self.ny = int(round(w / TUBE_PITCH)) * STRAWS, int(round(h / PIX_ALONG))
        self.px, self.py = w / self.nx, h / self.ny
        self._geo = None

    def hit(self, r0, u):
        """Intersection of the lines r0 + s·u with the panel plane: (s, ix, iy, inside)."""
        n, c = self.normal, self.center
        with np.errstate(divide="ignore", invalid="ignore"):
            s = ((c - r0) @ n) / (u @ n)
        p = r0 + s[:, None] * u - c
        xl, yl = p @ self.R[0], p @ self.R[1]
        ok = (s > 0) & (np.abs(xl) < self.w / 2) & (np.abs(yl) < self.h / 2)
        ix = np.clip(((xl + self.w / 2) / self.px).astype(int), 0, self.nx - 1)
        iy = np.clip(((yl + self.h / 2) / self.py).astype(int), 0, self.ny - 1)
        return s, ix, iy, ok

    def pixel_centers(self):
        xl = (np.arange(self.nx) + 0.5) * self.px - self.w / 2
        yl = (np.arange(self.ny) + 0.5) * self.py - self.h / 2
        X, Y = np.meshgrid(xl, yl)
        return self.center + X[..., None] * self.R[0] + Y[..., None] * self.R[1]

    def geometry(self):
        """Per pixel (cached): L2 [m], 2θ [rad], solid angle [sr]; "visible" added by Detector.masks()."""
        if self._geo is None:
            P = self.pixel_centers()
            L2 = np.linalg.norm(P, axis=-1)
            self._geo = dict(L2=L2, tth=np.arccos(P[..., 2] / L2),
                             omega=self.px * self.py * np.abs(P @ self.normal) / L2 / L2 ** 2)
        return self._geo


class Detector:
    """The 9 panels of LoKI. detect(ev): each scattered neutron goes in a straight line from the sample to the first
    panel it meets (the beam stop absorbs what hits it)."""

    def __init__(self, reardet=5.0):
        self.reardet = reardet
        self.panels = [Panel(n, b, a, reardet if d is None else d, r, w, h, t)
                       for n, b, a, d, r, w, h, t in PANELS_OFFICIAL]
        self.masks()

    def masks(self, half_beam=0.005):
        """A pixel is visible if the straight lines from the sample center AND from the four corners of the beam
        (±half_beam) to it meet neither a closer panel nor the beam stop. Hidden pixels are masked in the reduction,
        as in a real measurement (without masks, I(Q) of the rear bank is badly wrong)."""
        sources = [(0.0, 0.0)] + [(sx * half_beam, sy * half_beam) for sx in (-1, 1) for sy in (-1, 1)]
        for p in self.panels:
            P = p.pixel_centers().reshape(-1, 3)
            vis = np.ones(len(P), bool)
            for x0, y0 in sources:
                r0 = np.tile([x0, y0, 0.0], (len(P), 1))
                d = P - r0
                dist = np.linalg.norm(d, axis=1)
                u = d / dist[:, None]
                for q in self.panels:
                    if q is not p:
                        s, _, _, ok = q.hit(r0, u)
                        vis &= ~(ok & (s < dist - 1e-6))
                if p.bank == "rear":
                    sb = (self.reardet - 0.001) / u[:, 2]
                    xb, yb = x0 + sb * u[:, 0], y0 + sb * u[:, 1]
                    vis &= ~((np.abs(xb) < BEAMSTOP / 2) & (np.abs(yb) < BEAMSTOP / 2))
            p.geometry()["visible"] = vis.reshape(p.ny, p.nx)

    def detect(self, ev):
        """Per panel: pixels hit (ix, iy), arrival time t [s], true λ, weight w [n/s]."""
        r0 = np.column_stack([ev["x"], ev["y"], ev["z"]])
        u = np.column_stack([ev["ux"], ev["uy"], ev["uz"]])
        v = H_OVER_M / ev["lam"]
        best = np.full(len(v), np.inf)
        who = np.full(len(v), -1)
        hits = []
        for k, p in enumerate(self.panels):
            s, ix, iy, ok = p.hit(r0, u)
            hits.append((s, ix, iy))
            closer = ok & (s < best)
            best[closer] = s[closer]
            who[closer] = k
        sb = (self.reardet - 0.001) / u[:, 2]
        xb, yb = r0[:, 0] + sb * u[:, 0], r0[:, 1] + sb * u[:, 1]
        who[(np.abs(xb) < BEAMSTOP / 2) & (np.abs(yb) < BEAMSTOP / 2) & (sb < best)] = -1
        out = {}
        for k, p in enumerate(self.panels):
            m = who == k
            s, ix, iy = hits[k]
            out[p.name] = dict(ix=ix[m], iy=iy[m], t=ev["t"][m] + s[m] / v[m], lam=ev["lam"][m], w=ev["w"][m])
        return out


# --------------------------------------------------------------------------- arrival time and pixel -> λ and Q
def arrivals(L, lam_min, lam_max):
    """First and last arrival times [s] at distance L [m] of the neutrons passing the frame-overlap choppers, open for
    [λ_min, λ_max]: the fastest left at the END of the pulse, the slowest at its START."""
    t_open = lam_min * Z_CHOP2 / H_OVER_M
    t_close = lam_max * Z_CHOP2 / H_OVER_M + TAU
    return TAU + (t_open - TAU) * L / Z_CHOP2, t_close * L / Z_CHOP2


def frame_start(L, lam_min, lam_max, period=FRAME):
    """Start of the detector time window [s]: in the middle of the gap between the last neutron of one pulse and the
    first of the next one. period: time between two pulses used (2/14 s with pulse skipping)."""
    t_fast, t_slow = arrivals(L, lam_min, lam_max)
    return t_fast - 0.5 * np.maximum(period - (t_slow - t_fast), 0.0)


def events(hits, det, lam_min, lam_max, t0=T_EMISSION, period=FRAME):
    """What the detector measures, neutron by neutron, and what is deduced: pixel -> L2, 2θ; arrival time (modulo the
    period, frames unwrapped) -> λ = h t / (m (L1 + L2)), t counted from the mean emission time; Q = 4π sin(θ)/λ.
    period: time between two pulses used, 1/14 s, or 2/14 s with pulse skipping (the reduction knows which pulses
    were let through by the choppers, as at ESS from the chopper settings)."""
    out = {}
    for p in det.panels:
        h, g = hits[p.name], p.geometry()
        L2 = g["L2"][h["iy"], h["ix"]]
        tth = g["tth"][h["iy"], h["ix"]]
        t0w = frame_start(L1 + L2, lam_min, lam_max, period)
        t = t0w + np.mod(np.mod(h["t"], period) - t0w, period)
        lam = H_OVER_M * (t - t0) / (L1 + L2)
        out[p.name] = dict(Q=4 * np.pi * np.sin(tth / 2) / lam, lam=lam, w=h["w"], lam_true=h["lam"],
                           bank=p.bank, ix=h["ix"], iy=h["iy"])
    return out


def spectrum(folder, lam_edges):
    """Incident spectrum (n/s per λ bin) and transmission T(λ) of the sample, from the monitors of the downstream
    part, regrouped on lam_edges [Å]."""
    l, Ii, _, _ = monitor(folder, "incident_lambda")
    _, It, _, _ = monitor(folder, "transmitted_lambda")
    dl = l[1] - l[0]
    phi = np.zeros(len(lam_edges) - 1); tr = np.zeros(len(lam_edges) - 1)
    for k, (a, b) in enumerate(zip(lam_edges[:-1], lam_edges[1:])):
        f = np.clip((np.minimum(l + dl / 2, b) - np.maximum(l - dl / 2, a)) / dl, 0, 1)
        phi[k], tr[k] = (f * Ii).sum(), (f * It).sum()
    return phi, np.where(phi > 0, tr / np.where(phi > 0, phi, 1), 1.0)


def reduce(ev, det, phi, trans, lam_edges, thickness_cm, q_edges, duration=None):
    """Reduction in absolute units: for each bank and each Q bin,

        I(Q) = Σ_neutrons w  /  Σ_{pixels, λ bins} Φ(λ) T(λ) d ΔΩ_pixel   [cm⁻¹ sr⁻¹]

    (the denominator is what a sample with dΣ/dΩ = 1 cm⁻¹ would give in the same Q bin).
    duration [s]: if given, the error is that of a Poisson count of this duration plus the simulation noise.
    Returns {bank: (Q centers, I, error, denominator)}."""
    lc = 0.5 * (lam_edges[1:] + lam_edges[:-1])
    res = {}
    for bank in BANKS:
        num = np.zeros(len(q_edges) - 1); num2 = np.zeros_like(num); den = np.zeros_like(num)
        for p in det.panels:
            if p.bank != bank:
                continue
            e, g = ev[p.name], p.geometry()
            m = (e["lam"] >= lam_edges[0]) & (e["lam"] < lam_edges[-1])
            if len(e["w"]):
                m &= g["visible"][e["iy"], e["ix"]]
            num += np.histogram(e["Q"][m], q_edges, weights=e["w"][m])[0]
            num2 += np.histogram(e["Q"][m], q_edges, weights=e["w"][m] ** 2)[0]
            s = np.sin(g["tth"].ravel() / 2); om = (g["omega"] * g["visible"]).ravel()
            for l, f, tr in zip(lc, phi, trans):
                den += np.histogram(4 * np.pi * s / l, q_edges, weights=om * f * tr * thickness_cm)[0]
        ok = den > 0
        I = np.where(ok, num / np.where(ok, den, 1), np.nan)
        var = num2 if duration is None else num / duration + num2
        res[bank] = (0.5 * (q_edges[1:] + q_edges[:-1]), I, np.where(ok, np.sqrt(var) / np.where(ok, den, 1), np.nan),
                     den)
    return res


def lambda_bins(lam_min, lam_max, relative_step=0.02):
    """Wavelength bins with a constant relative width."""
    n = int(np.ceil(np.log(lam_max / lam_min) / np.log(1 + relative_step)))
    return lam_min * (1 + relative_step) ** np.arange(n + 1)
