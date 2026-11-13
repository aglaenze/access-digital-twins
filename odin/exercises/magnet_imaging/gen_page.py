"""Generates the guided pages (Voila, no code shown) of the exercise "Seeing a magnetic field with neutrons"
(polarized imaging), one per sample, the student chooses on the card of the catalogue:

  * ODIN_magnet_solenoid.ipynb   the solenoid of Sales et al., Sci. Rep. 8, 2214 (2018);
  * ODIN_magnet_meteorite.ipynb  the magnetized fragment of NWA 7034 of Qvistgaard et al., G-cubed 27,
                                 e2025GC012641 (2026).

    python gen_page.py
"""
import os
import sys

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from nbgen import distribute  # noqa: E402

VARIANTS = {
    "solenoid": dict(
        file="ODIN_magnet_solenoid.ipynb", sample="magnet_solenoid", quiz="odin_magnet_bsc_solenoid",
        title="What is the field inside a coil?",
        mission=r"""
**Your mission.** You are the engineer who builds the small magnets of a neutron instrument: coils that guide and
turn the spin of the neutrons. A new coil must make a field of about **half a millitesla along its axis**. A Hall
probe could measure it at a few points, but it cannot go inside the windings without touching them, and the field
there is what matters. Neutrons cross the windings: **measure the field inside the coil, without opening it**, and
tell the workshop whether the coil is good (part 6).

**The sample is real.** The coil is the one of M. Sales *et al.*, *Three Dimensional
Polarimetric Neutron Tomography of Magnetic Fields*, Sci. Rep. **8**, 2214 (2018), measured at RADEN (J-PARC, Japan)
to show that polarized neutrons can map a magnetic field in three dimensions: 13.5 windings of aluminium wire 1 mm
thick, 15.5 mm long, 11 mm in diameter, a current of 0.6 A. Its axis is horizontal (along $x$, across the beam),
tilted by about 9°. The twin computes its field from the path of the wire (Biot–Savart law), as the authors did.""",
        rots=[0.0],
        sample_text=r"""
A coil of 13.5 windings of aluminium wire, **15.5 mm long and 11 mm in diameter**, its axis along $x$ (horizontal,
across the beam; tilted by 9°), 0.6 A. The two leads go up to the holder. The camera field is 14 mm: the ends of
the coil are just outside it. Aluminium is almost transparent to neutrons: the wire is hardly seen in an ordinary
image. What the neutrons will see is the field.""",
        ),
    "meteorite": dict(
        file="ODIN_magnet_meteorite.ipynb", sample="nwa7034_fragment", quiz="odin_magnet_bsc_meteorite",
        title="A magnet inside a meteorite",
        mission=r"""
**Your mission.** You work with a team of paleomagnetists. Rocks keep a record of the magnetic field in which they
formed: a Martian meteorite tells whether Mars had a magnetic field 4 billion years ago, and how strong it was. But a
magnetometer gives only the total magnetization of the whole rock, and in a breccia like NWA 7034 each fragment may
carry its own. The team wants to know whether neutrons can show **where, inside the rock, the field is**, and how
strong it is. Test the method on a fragment magnetized on purpose, and tell the team what it can and cannot do
(part 6).

**The sample is real.** A fragment of the Martian meteorite NWA 7034, 2 mm thick, about 10 mm wide and 13 mm tall,
measured by polarized imaging at RADEN (J-PARC, Japan) by C. H. Qvistgaard, E. B. Naver *et al.*, Geochem. Geophys.
Geosyst. **27**, e2025GC012641 (2026). It kept no field of its own: they magnetized it with a small whiteboard magnet
before the measurement. The twin uses the field they reconstructed from their data (DTU Data,
doi:10.11583/DTU.30775208, CC BY 4.0), and you will compare your images with their measured ones.""",
        rots=[0.0, 90.0],
        sample_text=r"""
A flat fragment, **2 mm thick, 10 mm wide and 13 mm tall**, standing on the rotation stage: at 0° the beam crosses
its 2 mm thickness (front view), at 90° its 10 mm width (side view). Its magnetic minerals (iron oxides: magnetite)
keep the field given by the magnet, a few millitesla. The camera field is 14 mm.""",
        ),
}

INTRO = r"""
# @@TITLE@@

You are operating the ODIN imaging instrument at ESS. Behind this page, a simulation of the instrument produces your
measurements, in the formats of the real instrument.
@@MISSION@@

**Why neutrons.** A neutron has no charge, so it goes through matter, but it is a small magnet: it has a **spin**,
and its magnetic moment turns about a magnetic field, like a spinning top about gravity (the **Larmor precession**).
After crossing a field $B$ over a length $L$, the spin has turned by the angle

$$\varphi = c\,\lambda\,B\,L, \qquad c = 4.63 \times 10^{14}\ \text{T}^{-1}\,\text{m}^{-2}$$

($\lambda$: the wavelength; $c$ comes from the magnetic moment and the mass of the neutron). For a field that changes
along the path, $B L$ becomes $\int B\,\mathrm{d}l$, the field added up along the line of sight. **Measure how much the
spin has turned, at each pixel, and you have the field.** Slow neutrons (long $\lambda$) spend more time in the field
and turn more.

**Questions along the page** check each step: answer in the box, then click *Check*. A wrong answer is explained;
after a try you can also show the answer. Your answers are kept.
"""

SETUP = r"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import web_user
web_user.sign_in()            # the online version: the anonymous student of the start page (nothing to do in the app)
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display, clear_output
from odin_virtual import VirtualOdin
import odin_polarized as pol
import live_view
from page_output import into
import quiz
q = quiz.Quiz("@@QUIZ@@")      # the questions, along the page

SAMPLE = "@@SAMPLE@@"
ROTS = @@ROTS@@
odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
odin.move(sample=SAMPLE)
EXT = (-7.05, 7.05, -7.05, 7.05)              # the field of the camera [mm]
C = pol.C_LARMOR                              # 46 320 rad per (Å · T · m)
"""

PRECESSION = r"""
lam_s = w.FloatSlider(value=3.0, min=1.0, max=8.0, step=0.1, description="λ (Å)", continuous_update=True)
B_s = w.FloatSlider(value=0.5, min=0.0, max=5.0, step=0.05, description="B (mT)", continuous_update=True)
L_s = w.FloatSlider(value=11.0, min=0.5, max=20.0, step=0.5, description="L (mm)", continuous_update=True)
view_p = live_view.FigureImage()

def draw_precession(_=None):
    lam, B, L = lam_s.value, B_s.value * 1e-3, L_s.value * 1e-3
    phi = C * lam * B * L
    with view_p:
        fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw=dict(width_ratios=[1, 1.5]))
        a = ax[0]
        t = np.linspace(0, 2 * np.pi, 200)
        a.plot(np.cos(t), np.sin(t), color="0.85")
        a.annotate("", xy=(0, 1), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color="0.6", lw=2))
        a.annotate("", xy=(np.sin(phi), np.cos(phi)), xytext=(0, 0),
                   arrowprops=dict(arrowstyle="-|>", color="tab:red", lw=2.5))
        tt = np.linspace(0, phi, 60)
        a.plot(0.35 * np.sin(tt), 0.35 * np.cos(tt), color="tab:red", lw=1)
        a.text(0.02, 1.08, "spin before", color="0.4", ha="center")
        a.text(1.12 * np.sin(phi), 1.12 * np.cos(phi), "after", color="tab:red", ha="center", va="center")
        a.plot(0, 0, "o", color="tab:blue", ms=9)
        a.text(0.08, -0.18, "B (out of the page)", color="tab:blue", fontsize=9)
        a.set(xlim=(-1.35, 1.35), ylim=(-1.35, 1.35), aspect="equal",
              title=f"φ = c λ B L = {phi:.2f} rad = {np.degrees(phi):.0f}°")
        a.axis("off")
        b = ax[1]
        ll = np.linspace(0.5, 8, 300)
        b.plot(ll, np.cos(C * ll * B * L), color="tab:red", lw=2, label="P = cos φ: spin still along its start")
        b.plot(lam, np.cos(phi), "o", color="tab:red", ms=8)
        b.axhline(0, color="0.6", lw=0.8)
        b.set(xlabel="wavelength λ (Å)", ylabel="polarization P", ylim=(-1.1, 1.1), xlim=(0.5, 8),
              title="All the wavelengths at once: P against λ")
        b.legend(loc="lower left", fontsize=9); b.grid(alpha=0.3)
        plt.tight_layout()

for s in (lam_s, B_s, L_s):
    s.observe(live_view.throttled(draw_precession), "value")
draw_precession()
display(w.VBox([lam_s, B_s, L_s, view_p]))
"""

INSTRUMENT_FIG = r"""
fig, ax = plt.subplots(figsize=(11, 2.6))
items = [(0.5, "neutron\nbeam", "0.85"), (2.0, "polarizer\n(spin up only)", "tab:blue"),
         (3.6, "spin rotator\n(spin_in)", "tab:cyan"), (5.4, "SAMPLE\n(its field B)", "tab:red"),
         (7.2, "spin rotator\n+ analyzer\n(spin_out)", "tab:cyan"), (9.2, "Timepix3 camera\n(time of flight → λ)", "0.4")]
for x, txt, c in items:
    ax.add_patch(plt.Rectangle((x - 0.6, -0.55), 1.2, 1.1, color=c, alpha=0.25))
    ax.text(x, 0, txt, ha="center", va="center", fontsize=9)
for x0, x1 in zip([it[0] for it in items][:-1], [it[0] for it in items][1:]):
    ax.annotate("", xy=(x1 - 0.62, 0), xytext=(x0 + 0.62, 0), arrowprops=dict(arrowstyle="-|>", color="0.3"))
for x, ang in ((2.8, 90), (4.5, 0), (6.3, 35)):
    ax.annotate("", xy=(x + 0.3 * np.cos(np.radians(ang)), 0.85 + 0.3 * np.sin(np.radians(ang))), xytext=(x, 0.85),
                arrowprops=dict(arrowstyle="-|>", color="tab:red", lw=2))
ax.text(4.5, 1.35, "the spin: set along i, turned by the field, analyzed along j", ha="center", fontsize=9,
        color="tab:red")
ax.set(xlim=(-0.3, 10.2), ylim=(-0.8, 1.6)); ax.axis("off")
plt.tight_layout()
plt.show()
"""

SAMPLE_CELL = r"""
spec = odin.sample_spec(SAMPLE)
import sample_library as sl
smp_out = w.Output()
with into(smp_out):
    sl.draw("odin", spec, fig=plt.figure(figsize=(10, 3.6)))
    sl.show()
display(smp_out)
"""

MEASURE = r"""
st = odin.status()
rot = w.ToggleButtons(options=[(f"{r:g}°", r) for r in ROTS], value=ROTS[0], description="Rotation")
expo = w.ToggleButtons(options=[("30 s (a quick look)", 30), ("150 s (as at RADEN)", 150)], value=150,
                       description="Each image")
button0 = w.Button(description="Measure without the sample (2 images)", button_style="primary", icon="play",
                   layout=w.Layout(width="auto"))
button1 = w.Button(description="Measure the polarization matrix of the sample (18 images)", button_style="primary",
                   icon="play", layout=w.Layout(width="auto"))
out_m = w.Output()

def _prepare(stage_x, r):
    odin.move(sample=SAMPLE, choppers="natural", pinhole=0.02, diffuser="in", shutter="open", stage_x=stage_x,
              stage_rot=r, polarizer="in")

def measure_empty(_):
    button0.disabled = button1.disabled = True
    with out_m:
        clear_output()
        try:
            _prepare(0.5, 0.0)
            for s in ("+y", "-y"):
                odin.move(spin_in=s, spin_out="y")
                f = odin.polarimetry(float(expo.value), title=f"no sample {s} y")
                print(f"{os.path.basename(f)}: spin in {s}, analyzer y, {expo.value} s")
            show_P0()
        except Exception as e:
            print("Error:", e)
    button0.disabled = button1.disabled = False

def measure_matrix(_):
    button0.disabled = button1.disabled = True
    with out_m:
        clear_output()
        try:
            _prepare(0.0, rot.value)
            prog = w.IntProgress(min=0, max=18, description="images")
            display(prog)
            odin.polarization_matrix(float(expo.value), title=f"{SAMPLE} {rot.value:g} deg",
                                     progress=lambda k, n, f: setattr(prog, "value", k))
            print(f"18 images of {expo.value} s: {18 * expo.value / 60:.0f} minutes of beam. Parts 3 to 5 now use them.")
            refresh_all()
        except Exception as e:
            print("Error:", e)
    button0.disabled = button1.disabled = False

def runs():
    out = []
    if os.path.isfile(odin.log_file):
        for l in open(odin.log_file, encoding="utf-8"):
            e = json.loads(l)
            if e["action"] == "polarimetry" and e["details"].get("file"):
                d = e["details"]; s = d["state"]
                if s.get("sample") != SAMPLE or s["shutter"] != "open" or s["polarizer"] != "in":
                    continue
                out.append(dict(path=os.path.join(odin.folder, d["file"]), t=d["t"], spin_in=s["spin_in"],
                                spin_out=s["spin_out"], rot=float(s["stage_rot"]), empty=abs(s["stage_x"]) > 0.02))
    return out

def P0_measured():
    e = [r for r in runs() if r["empty"] and r["spin_out"] == "y" and r["spin_in"] in ("+y", "-y")]
    p = {r["spin_in"]: r["path"] for r in e}
    if len(p) < 2:
        return None, None
    a, b = pol.read(p["+y"])[0][2:13].sum(0), pol.read(p["-y"])[0][2:13].sum(0)      # 2 to 5 Å
    P, dP = pol.polarization(a, b)
    return float(np.nanmean(P)), float(np.nanstd(P) / np.sqrt(np.isfinite(P).sum()))

def latest_matrix(r):
    files = {}
    for x in runs():
        if not x["empty"] and abs(x["rot"] - r) < 1e-6:
            files[(x["spin_in"], x["spin_out"])] = x["path"]        # the newest of each of the 18
    return files if len(files) == 18 else None

out_P0 = w.Output()

def show_P0():
    with into(out_P0):
        P0, dP0 = P0_measured()
        if P0 is None:
            print("Not measured yet: click the first button.")
        else:
            print(f"Polarization without the sample (2 to 5 Å, mean over the field): P0 = {P0:.3f} ± {dP0:.3f}")

button0.on_click(measure_empty)
button1.on_click(measure_matrix)
display(w.VBox([expo, button0, rot, button1, out_m]))
"""

P0_CELL = r"""
show_P0()
display(out_P0)
"""

MAPS = r"""
lam_i = w.IntSlider(value=5, min=0, max=15, description="λ bin", continuous_update=True)
rot_v = w.ToggleButtons(options=[(f"{r:g}°", r) for r in ROTS], value=ROTS[0], description="Rotation")
view_m = live_view.FigureImage()
CACHE = {}

def matrix_of(r):
    files = latest_matrix(r)
    if files is None:
        return None
    key = (r, tuple(sorted(files.values())))
    if key not in CACHE:
        P0 = P0_measured()[0] or pol.P0
        CACHE[key] = pol.matrix(files, P0=P0, rebin=2)
    return CACHE[key]

def draw_maps(_=None):
    M = matrix_of(rot_v.value)
    with view_m:
        if M is None:
            fig = plt.figure(figsize=(6, 1)); plt.axis("off")
            plt.text(0, 0.5, f"No full matrix at {rot_v.value:g}° yet: measure it in part 2.", fontsize=11)
            return
        P, dP, lam = M
        k = lam_i.value
        fig, ax = plt.subplots(3, 3, figsize=(8.4, 8.0), sharex=True, sharey=True)
        for i, a in enumerate("xyz"):
            for j, b in enumerate("xyz"):
                im = ax[i, j].imshow(P[k, i, j], origin="lower", extent=EXT, vmin=-1, vmax=1, cmap="RdBu_r")
                ax[i, j].set_title(f"P{a}{b}", fontsize=11)
                if i == 2:
                    ax[i, j].set_xlabel("x (mm)")
                if j == 0:
                    ax[i, j].set_ylabel(f"spin in along {a}\ny (mm)")
        fig.suptitle(f"Polarization matrix, λ = {lam[k]:.2f} Å (rows: spin in along i; columns: analyzer along j)")
        fig.colorbar(im, ax=ax, shrink=0.6, label="P (divided by P0)")

lam_i.observe(live_view.throttled(draw_maps), "value")
rot_v.observe(live_view.throttled(draw_maps), "value")

def refresh_all():
    draw_maps(); draw_point(); show_P0()
"""

MAPS_SHOW = r"""
draw_maps()
display(w.VBox([rot_v, lam_i, view_m]))
"""

POINT = r"""
px = w.FloatSlider(value=@@PX@@, min=-6.5, max=6.5, step=0.1, description="x (mm)", continuous_update=True)
py = w.FloatSlider(value=@@PY@@, min=-6.5, max=6.5, step=0.1, description="y (mm)", continuous_update=True)
bl = w.FloatSlider(value=2.0, min=0.0, max=15.0, step=0.05, description="∫B dl (µT·m)", continuous_update=True,
                   readout_format=".2f")
view_pt = live_view.FigureImage()
out_pt = w.HTML()

def at_point(M):
    P, dP, lam = M
    n = P.shape[-1]
    ix = int(np.clip((px.value - EXT[0]) / (EXT[1] - EXT[0]) * n, 1, n - 2))
    iy = int(np.clip((py.value - EXT[2]) / (EXT[3] - EXT[2]) * n, 1, n - 2))
    Pm = np.nanmean(P[..., iy - 1:iy + 2, ix - 1:ix + 2], axis=(-1, -2))[..., None, None]    # 3 × 3 pixels
    return Pm, lam

def draw_point(_=None):
    M = matrix_of(ROTS[0])
    with view_pt:
        if M is None:
            fig = plt.figure(figsize=(6, 1)); plt.axis("off")
            plt.text(0, 0.5, "No full matrix yet: measure it in part 2.", fontsize=11)
            out_pt.value = ""
            return
        Pm, lam = at_point(M)
        phi = pol.rotation_angle(Pm)[:, 0, 0]
        axis = pol.rotation_axis(Pm)[:, :, 0, 0]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw=dict(width_ratios=[1, 1.4]))
        im = ax[0].imshow(M[0][5, 1, 1], origin="lower", extent=EXT, vmin=-1, vmax=1, cmap="RdBu_r")
        ax[0].plot(px.value, py.value, "s", mfc="none", mec="k", ms=10, mew=2)
        ax[0].set(xlabel="x (mm)", ylabel="y (mm)", title=f"Pyy at λ = {lam[5]:.2f} Å: your point")
        ax[1].plot(lam, phi, "o", color="k", label="measured: φ from the trace of P")
        ll = np.linspace(0, 6.2, 50)
        ax[1].plot(ll, C * ll * bl.value * 1e-6, color="tab:orange", lw=2, label=f"φ = c λ ∫B dl, ∫B dl = {bl.value:.2f} µT·m")
        ax[1].set(xlabel="wavelength λ (Å)", ylabel="angle turned φ (rad)", xlim=(0, 6.2), ylim=(0, 3.2),
                  title="How much the spin has turned at your point")
        ax[1].legend(loc="upper left", fontsize=9); ax[1].grid(alpha=0.3)
        plt.tight_layout()
    k = (lam > 2) & (lam < 5)
    a = np.nanmean(axis[k], axis=0)
    a = a / np.linalg.norm(a)
    out_pt.value = (f"<p>Direction of the field at this point (the axis of the rotation, 2 to 5 Å): "
                    f"<b>x {a[0]:+.2f}, y {a[1]:+.2f}, z {a[2]:+.2f}</b> (z: along the beam; the sign is fixed by "
                    f"the sense of the rotation).</p>")

for s in (px, py, bl):
    s.observe(live_view.throttled(draw_point), "value")
draw_point()
display(w.VBox([px, py, bl, view_pt, out_pt]))
"""

FIELD_MAP = r"""
button_f = w.Button(description="Map ∫B dl over the image", button_style="primary", icon="map",
                    layout=w.Layout(width="auto"))
out_f = w.Output()

def map_field(_):
    M = matrix_of(ROTS[0])
    with into(out_f):
        if M is None:
            print("No full matrix yet: measure it in part 2.")
            return
        P, dP, lam = M
        J = pol.field_integral(lam, pol.rotation_angle(P)) * 1e6
        axis = np.nanmean(pol.rotation_axis(P)[(lam > 2) & (lam < 5)], axis=0)
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
        im = ax[0].imshow(J, origin="lower", extent=EXT, cmap="magma", vmin=0)
        fig.colorbar(im, ax=ax[0], label="∫B dl along the beam (µT·m)")
        ax[0].set(xlabel="x (mm)", ylabel="y (mm)", title="The field added up along each line of sight")
        n = J.shape[0]
        c = np.linspace(EXT[0], EXT[1], n)
        s = slice(2, None, 5)
        Xc, Yc = np.meshgrid(c, c)
        strong = J > 0.3 * np.nanmax(J)
        U, V = np.where(strong, axis[0] * J, np.nan), np.where(strong, axis[1] * J, np.nan)
        ax[1].imshow(np.abs(axis[2]) * strong, origin="lower", extent=EXT, cmap="Greens", vmin=0, vmax=1)
        ax[1].quiver(Xc[s, s], Yc[s, s], U[s, s], V[s, s], color="k", scale=8 * np.nanmax(J), width=0.006)
        ax[1].set(xlabel="x (mm)", ylabel="y (mm)",
                  title="Direction: arrows in the image plane; green: along the beam")
        plt.tight_layout(); plt.show()
        print(f"largest ∫B dl: {np.nanmax(J):.2f} µT·m. Outside the sample the map is not exactly zero: the noise of "
              f"the counts makes the trace of P a little below 3, which reads as a small angle.")

button_f.on_click(map_field)
display(w.VBox([button_f, out_f]))
"""

COMPARE_METEORITE = r"""
button_c = w.Button(description="Compare with the RADEN measurement", button_style="primary", icon="balance-scale",
                    layout=w.Layout(width="auto"))
out_c = w.Output()

def compare(_):
    M = matrix_of(0.0)
    with into(out_c):
        if M is None:
            print("No full matrix at 0° yet: measure it in part 2.")
            return
        P, dP, lam = M
        z = np.load(pol.QV_FILE)
        meas = z["measured"][0]                       # their front view (0°), the 9 components, 80 × 80 pixels
        k = (lam > 2) & (lam < 5)
        mine = np.nanmean(P[k], axis=0) * pol.P0      # P0 put back: their images are not divided by it
        n = meas.shape[-1]
        ext = (-n * 0.186 / 2, n * 0.186 / 2) * 2
        fig, ax = plt.subplots(2, 3, figsize=(10, 6.6))
        for c, (i, j) in enumerate(((0, 1), (1, 0), (1, 1))):
            name = "P" + "xyz"[i] + "xyz"[j]
            ax[0, c].imshow(mine[i, j], origin="lower", extent=EXT, vmin=-1, vmax=1, cmap="RdBu_r")
            ax[0, c].set_title(f"{name}: your measurement (twin)")
            ax[1, c].imshow(meas[3 * i + j], origin="lower", extent=ext[:4], vmin=-1, vmax=1, cmap="RdBu_r")
            ax[1, c].set_title(f"{name}: measured at RADEN")
            for a in ax[:, c]:
                a.set(xlim=EXT[:2], ylim=EXT[2:])
        plt.tight_layout(); plt.show()

button_c.on_click(compare)
display(w.VBox([button_c, out_c]))
"""

QUESTIONS = {
    "solenoid": r"""
q.number("Without the sample, the polarization you measured (part 2): P0 =", value=0.91, tol=0.04,
         hints=["Part 2 prints it after the first button."],
         explanation="About 0.91: the polarizer and the analyzer are not perfect (flipping ratio 22 at RADEN: "
                     "P0 = 21/23 = 0.91). All the images are divided by P0.", title="Q1. Without the sample")
q.choice("In the coil, which component of the matrix stays at 1 (part 3), and why?",
         ["Pxx: a spin along the field, which is along x, does not turn.",
          "Pzz: the beam goes along z.",
          "Pyy: y is vertical.",
          "None: all the components change."],
         answer=0, why={1: "Pzz turns: a spin along z is perpendicular to the field (x).",
                        2: "Pyy turns: look at it while you move the λ slider.",
                        3: "Look at Pxx: it stays red over the whole coil."},
         explanation="A spin precesses about the field: a spin along the field does not move. Pxx = 1 says the field "
                     "inside the coil is along x, its axis.", hints=["Move the λ slider and watch the diagonal."],
         title="Q2. The direction of the field")
q.choice("When λ gets longer, Pyy in the coil:",
         ["goes down, from 1 toward 0: the slower neutrons spend more time in the field and turn more.",
          "stays the same: the field does not change.",
          "goes up: the faster neutrons turn more.",
          "changes sign at every bin: noise."],
         answer=0, why={1: "The angle φ = c λ B L grows with λ.", 2: "Slow neutrons (long λ) turn more.",
                        3: "It changes smoothly; the noise is much smaller."},
         explanation="Pyy = cos φ with φ ∝ λ: from about 0.9 at 2 Å to about 0.2 at 5.5 Å in the coil.",
         hints=["Part 1: P = cos φ against λ."], title="Q3. The wavelength")
q.number("At the center of the coil (x = 0, y = 0), the ∫B dl that matches your points (part 4), in µT·m:",
         value=5.6, tol=0.8, unit="µT·m",
         hints=["Move the slider ∫B dl until the orange line goes through the black points."],
         explanation="About 5.6 µT·m: the angle grows by about 0.26 rad per Å.", title="Q4. The field along the beam")
q.number("The beam crosses the coil over its diameter, 11 mm. The mean field inside along that path, in mT:",
         value=0.51, tol=0.1, unit="mT",
         hints=["B = ∫B dl / L: 5.6 µT·m / 0.011 m."],
         explanation="5.6 × 10⁻⁶ / 0.011 = 0.51 mT. Biot–Savart gives 0.54 mT at the very center, a little less off "
                     "center: the mean along the path is 0.51 mT.", title="Q5. The field inside")
q.choice("The formula of a long solenoid, B = μ0 N I / ℓ = 4π × 10⁻⁷ × 13.5 × 0.6 / 0.0155 = 0.66 mT, gives more than "
         "you measured. Why?",
         ["The coil is short (15.5 mm long for 11 mm wide): the field lines spread out at its ends, so the field is "
          "weaker than in an infinitely long coil.",
          "The neutrons slow the field down.",
          "Aluminium screens the field.",
          "The measurement is wrong by 25 %."],
         answer=0, why={1: "The neutrons do not change the field.", 2: "Aluminium is not magnetic.",
                        3: "Your uncertainty is a few %; the difference is real."},
         explanation="μ0 N I / ℓ holds for a coil much longer than wide. For this short coil, Biot–Savart gives "
                     "0.54 mT at the center: the field the neutrons see.", hints=["Compare the length and the diameter."],
         title="Q6. A short coil")
q.choice("Part 4 also gives the direction of the field at the center. It is:",
         ["along x, tilted by a few degrees toward z: the axis of the coil.",
          "along the beam (z).", "vertical (y).", "random: it changes with λ."],
         answer=0, why={1: "The z component is small (about 0.15).", 2: "The y component is almost zero.",
                        3: "It is the same at all wavelengths: the field does not depend on the neutrons."},
         explanation="About (0.99, 0.0, −0.15): the axis of the coil, tilted by 9° (sin 9° = 0.16), as in the paper.",
         hints=["Read the line printed under the plot of part 4."], title="Q7. The direction")
q.choice("**Your report to the workshop.**",
         ["The field inside is along the axis of the coil, about 0.5 mT, uniform over the middle: as designed for a "
          "short coil (Biot–Savart), 20 % below the long-solenoid formula; the method sees it without touching the "
          "windings.",
          "The coil is faulty: it gives 25 % less than μ0 N I / ℓ.",
          "The field is along the beam.",
          "Neutrons cannot measure a field of 0.5 mT."],
         answer=0, why={1: "The formula of a long solenoid does not apply to a short coil.",
                        2: "Pxx = 1: the field is along x.", 3: "It turns the spin by about 1 rad: easily measured."},
         explanation="This is the test of the method by Sales et al. (2018): the field of a known coil, measured by "
                     "neutrons, agrees with its calculation.", hints=["Q5, Q6 and Q7 together."],
         title="Q8. The report")
q.report()
""",
    "meteorite": r"""
q.number("Without the sample, the polarization you measured (part 2): P0 =", value=0.91, tol=0.04,
         hints=["Part 2 prints it after the first button."],
         explanation="About 0.91: the polarizer and the analyzer are not perfect (at RADEN: 0.87 on average). All "
                     "the images are divided by P0.", title="Q1. Without the sample")
q.choice("Is the field the same over the whole fragment (part 3, front view)?",
         ["No: some parts turn the spin one way, others the other way (Pxy red in one region, blue in another): "
          "regions magnetized in opposite directions.",
          "Yes: the fragment is one uniform magnet.",
          "There is no field: P stays at 1 everywhere.",
          "The field is only outside the fragment."],
         answer=0, why={1: "Pxy changes sign across the fragment.", 2: "Pxx and Pyy drop well below 1 inside it.",
                        3: "Outside the fragment P stays at 1: no field there."},
         explanation="Like Qvistgaard et al.: the field is not uniform; regions of opposite field also cancel each "
                     "other along a line of sight.", hints=["Move the λ slider and look at Pxy and Pyx."],
         title="Q2. A uniform magnet?")
q.choice("In the front view, Pxy and Pyx are large and of opposite signs. The Rodrigues formula gives "
         "Pxy = B̂x B̂y (1 − cos φ) − B̂z sin φ and Pyx = B̂y B̂x (1 − cos φ) + B̂z sin φ. Which component of the "
         "field do they show?",
         ["Bz, along the beam: the terms ± B̂z sin φ have opposite signs in Pxy and Pyx.",
          "Bx, horizontal.", "By, vertical.", "None: they show the attenuation."],
         answer=0, why={1: "Bx alone would make Pxy = Pyx (same sign).", 2: "By alone would make Pxy = Pyx too.",
                        3: "P is a ratio of two images: the attenuation cancels."},
         explanation="The antisymmetric part Pyx − Pxy = 2 B̂z sin φ: a field along the beam, through the 2 mm "
                     "thickness of the plate.", hints=["Which term changes sign between the two?"],
         title="Q3. Which component")
q.number("The largest ∫B dl you find (part 4 or the map of part 5), in µT·m:", value=8.5, tol=2.5, unit="µT·m",
         hints=["Put the point where Pxy is darkest and match the orange line, or read the map."],
         explanation="About 8 to 9 µT·m in the strongest region (the field of the authors: 9.4 µT·m on one line of "
                     "sight, less when averaged over a few pixels).", title="Q4. The strongest field")
q.number("The fragment is 2 mm thick along the beam (front view). The mean field along that line, in mT:",
         value=4.3, tol=1.5, unit="mT",
         hints=["B = ∫B dl / L, with L = 0.002 m."],
         explanation="8.5 × 10⁻⁶ / 0.002 ≈ 4 mT: about 80 times the field of the Earth (0.05 mT), the field left by a "
                     "whiteboard magnet in the iron oxides of the rock.", title="Q5. How strong")
q.choice("Qvistgaard et al. measured the fragment at 33 angles and computed the field in 3D (a tomography). Why is "
         "one view not enough?",
         ["Each pixel adds up the field along the beam: regions of opposite field cancel, and a field along the "
          "line of sight cannot be placed along it. Views from many angles give the field at each point.",
          "One view is enough; the other angles only reduce the noise.",
          "The neutrons need to cross the sample several times to turn.",
          "The camera sees only one component per angle."],
         answer=0, why={1: "Turn the sample (rotation 90°): the images change completely.",
                        2: "The spin turns in one crossing.", 3: "The 9 components are measured at every angle."},
         explanation="As for an ordinary tomography: a projection loses the depth. The authors found a domain along y "
                     "with an opposite wrapping field behind it, which cancel in the front view.",
         hints=["Compare the views at 0° and 90°."], title="Q6. Why a tomography")
q.number("At RADEN each of the 9 components took 2 × 150 s, at each of the 33 angles. The whole tomography took how "
         "many hours?", value=24.75, tol=0.3, unit="h",
         hints=["33 × 9 × 300 s."], explanation="33 × 9 × 300 s = 89 100 s = 24 h 45 min, as in the paper.",
         title="Q7. Beam time")
q.choice("**Your report to the paleomagnetists.**",
         ["Polarized neutrons show where the field is inside the rock and its strength (a few mT here), without "
          "cutting it; one view adds up opposite fields, a tomography (a day of beam) places them in 3D. A weak "
          "natural remanence (µT) would turn the spin a thousand times less: the method suits strongly magnetized "
          "regions.",
          "Neutrons measure the field of the planet in which the rock formed directly.",
          "The fragment is uniformly magnetized at 4 mT.",
          "Neutrons cannot see fields inside a rock."],
         answer=0, why={1: "They measure the field of the magnetized minerals today.",
                        2: "Q2: the field is not uniform.", 3: "You have just seen it."},
         explanation="This is the conclusion of Qvistgaard et al. (2026): a first 3D map of the field inside a "
                     "meteorite fragment, with the limits of sensitivity of the method.",
         hints=["Q2, Q5 and Q6 together."], title="Q8. The report")
q.report()
""",
}


def build(key):
    V = VARIANTS[key]
    cells = []
    md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
    code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))
    md(INTRO.replace("@@TITLE@@", V["title"]).replace("@@MISSION@@", V["mission"]))
    code(SETUP.replace("@@QUIZ@@", V["quiz"]).replace("@@SAMPLE@@", V["sample"]).replace("@@ROTS@@", repr(V["rots"])))
    md(r"""
## 1. The spin turns in a field

Move the sliders: the wavelength $\lambda$, the field $B$ and the length $L$ of field crossed. On the left, the spin
before (gray) and after (red) the field, seen along the field. On the right, the **polarization** $P = \cos\varphi$:
the share of the spin still along its start direction (1: unchanged; 0: turned by 90°; −1: reversed). The camera of
ODIN sorts the neutrons by wavelength (time of flight), so it measures the whole curve at once.
""")
    code(PRECESSION)
    md(r"""
## 2. The instrument, the sample, and your measurements

A **polarizer** lets through only the neutrons whose spin points one way. A **spin rotator** turns that spin along
the direction $i$ you choose (`spin_in`: $\pm x$, $\pm y$, $\pm z$; $x$ horizontal, $y$ vertical, $z$ along the
beam). After the sample, a second rotator and an **analyzer** let through only the spin along $j$ (`spin_out`). The
Timepix3 camera counts the neutrons at each pixel and wavelength.

From two images, spin in along $+i$ and along $-i$ (same analyzer $j$), the **polarization**

$$P_{ij} = \frac{N(+i, j) - N(-i, j)}{N(+i, j) + N(-i, j)}$$

is the component $j$ of the spin after the sample when it entered along $i$. The 9 components form the
**polarization matrix**: 18 images. Without field, $P_{ij}$ is 1 on the diagonal and 0 elsewhere (times $P_0$, the
quality of the polarizer and analyzer); a field turns the spin and mixes them. The attenuation of the sample is the
same in both images: it cancels in $P$.
""")
    code(INSTRUMENT_FIG)
    md("### The sample\n" + V["sample_text"])
    code(SAMPLE_CELL)
    md(r"""
### Your measurements

ODIN is set for you: choppers in the *natural* mode (the band of wavelengths of one pulse, 1.5 to 6 Å, sorted by time
of flight), pinhole 2 cm, polarizer and analyzer in. **First** measure without the sample (stage out): spin in along
$+y$ and $-y$, analyzer along $y$. This gives $P_0$. **Then** the 18 images of the sample. At RADEN each image took
150 s; the twin computes them in about a minute.
""")
    code(MEASURE)
    code(P0_CELL)
    md(r"""
## 3. The polarization matrix

The 9 images of $P_{ij}$ (divided by $P_0$; red: +1, blue: −1, white: 0), at the wavelength of the slider. Outside the
sample: 1 on the diagonal, 0 elsewhere. Move the slider: where there is a field, the images change with $\lambda$.
""")
    code(MAPS)
    code(MAPS_SHOW)
    md(r"""
## 4. How much has the spin turned? The field at one point

A field turns the spin by $\varphi$ about its own direction: $P$ is then a **rotation matrix**, and its diagonal adds
up to $P_{xx} + P_{yy} + P_{zz} = 1 + 2\cos\varphi$, whatever the direction of the field. The page computes
$\varphi$ from it at each wavelength, at the point you choose (3 × 3 pixels), and the direction of the axis of the
rotation (the direction of the field) from the parts of $P$ that are not symmetric.

$\varphi = c\,\lambda \int B\,\mathrm{d}l$ is a straight line through zero: move the slider $\int B\,\mathrm{d}l$
until the orange line goes through your points.
""")
    code(POINT.replace("@@PX@@", "0.0" if key == "solenoid" else "-2.7")
              .replace("@@PY@@", "0.0" if key == "solenoid" else "-0.5"))
    md(r"""
## 5. A map of the field

The same fit at every pixel: the slope of $\varphi$ against $\lambda$ (2 to 5 Å) gives $\int B\,\mathrm{d}l$ along
each line of sight; the axis of the rotation gives its direction (arrows: its part in the plane of the image; green:
its part along the beam).
""")
    code(FIELD_MAP)
    if key == "meteorite":
        md(r"""
## 6. Your images and the real ones

Qvistgaard *et al.* published their measured matrices. Here, three components of the front view (0°): yours (averaged
over 2 to 5 Å, times $P_0$) and theirs (their whole spectrum, mean 3.3 Å). The twin uses the field **they
reconstructed** from all 33 angles: the agreement is good but not perfect (the reconstruction itself does not reproduce
every detail of the measurement, and their pixel was 0.19 mm, 23.8 mm of field). Turn the sample by 90° in part 2 to
see the side view, where the field along $y$ shows.
""")
        code(COMPARE_METEORITE)
    else:
        md(r"""
## 6. Your field and the calculation

The workshop computes the field of the coil in two ways: the formula of an infinitely long solenoid,
$B = \mu_0 N I / \ell$ = 0.66 mT, and the Biot–Savart law along the real wire, which gives 0.54 mT at the center (the
coil is short: its field spreads out at the ends). Compare with what you measured (Q5, Q6).
""")
    code(QUESTIONS[key])
    md(r"""
## 7. Submit your work

When you are done, tell what you thought of the exercise and submit your work.
""")
    code(r"""
import submit
_ = submit.Submit("odin/exercises/magnet_imaging", "bsc", quiz=q)
""")
    distribute(cells, [
        ("display(out_P0)", [1]),
        ("display(w.VBox([rot_v, lam_i, view_m]))", [2, 3]),
        ("display(w.VBox([px, py, bl, view_pt, out_pt]))", [4, 5]),
        ("display(w.VBox([button_f, out_f]))", [6, 7]),
    ])
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    out_nb = os.path.join(HERE, V["file"])
    nbf.write(nb, out_nb)
    print("written:", out_nb)


if __name__ == "__main__":
    for k in VARIANTS:
        build(k)
