"""Generates the MSc and beamtime notebooks of the exercise "Seeing a magnetic field with neutrons":

  * ODIN_magnet_msc_solenoid.ipynb, ODIN_magnet_msc_meteorite.ipynb   MSc, "develop the method", one per sample (the
        student chooses on the card): measure (NICOS or the panel), read the files, the polarization matrix and P0,
        the angle of rotation (one component or the trace: a choice), ∫B dl with its uncertainty, the map and its
        resolution, then the check against the calculation (coil) or the RADEN measurement (fragment);
  * ODIN_magnet_beamtime.ipynb  beamtime (with NICOS): a starter notebook, tools only (beamtime.md).

    python gen_notebooks.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from nbgen import code, distribute, md, nicos_step, stop, write  # noqa: E402

PROPOSAL = "1270"
SETUP = r'''
import sys, os, json, datetime, warnings
warnings.filterwarnings("ignore")
sys.path[:0] = [os.path.abspath("../../.."), os.path.abspath("../..")]     # twin/ and twin/odin/
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display
import odin_reduction as red, odin_polarized as pol
import live_view                  # figures that follow the sliders
import quiz
q = quiz.Quiz("@@QUIZ@@")       # the questions of this notebook
SAMPLE = "@@SAMPLE@@"
EXT = (-7.05, 7.05, -7.05, 7.05)              # the field of the camera [mm]
C = pol.C_LARMOR                              # 46 320 rad per (Å · T · m)
'''
FILES = r'''
from odin_paths import TWIN_RUN_ROOT
FOLDER = f"{TWIN_RUN_ROOT}/data/odin/{datetime.date.today().year}/@@PROPOSAL@@/raw"
import sample_library as sl
NAME = sl.load("odin")[SAMPLE]["name"]
rows = [r for r in red.measurements(FOLDER) if r.get("detector") == "polarized" and r.get("sample") == NAME]
if not rows:
    raise SystemExit("No polarized image yet in " + FOLDER + ": measure first (part 0).")
for r in rows:
    print(f"{r['file']:20s} {r['kind']:10s} rot {r['stage_rot_deg']:6.1f}°  polarizer {r['polarizer']:3s} "
          f"spin in {r['spin_in']:3s} analyzer {r['spin_out']}  t = {r['t_s']:5.0f} s  {r['title'][:30]}")
'''
PICK = r'''
path = lambda r: os.path.join(FOLDER, r["file"])
EMPTY = {}                                     # without the sample: the newest image of each (spin in, analyzer)
SETS = {}                                      # with the sample, per rotation: the newest of each of the 18
for r in rows:
    if r["polarizer"] != "in" or r["kind"] == "dark":
        continue
    key = (r["spin_in"], r["spin_out"])
    if r["kind"] == "open beam":
        EMPTY[key] = path(r)
    else:
        SETS.setdefault(r["stage_rot_deg"], {})[key] = path(r)
FULL = {rot: f for rot, f in SETS.items() if len(f) == 18}
print("without the sample:", sorted(EMPTY))
print("full matrices (18 images) at the rotations:", sorted(FULL), "| incomplete:",
      {rot: len(f) for rot, f in SETS.items() if len(f) < 18})
'''
P0_CELL = r'''
if ("+y", "y") not in EMPTY or ("-y", "y") not in EMPTY:
    raise SystemExit("Measure without the sample first: spin in +y and −y, analyzer y (part 0).")
a, lam, _ = pol.read(EMPTY[("+y", "y")])
b, _, _ = pol.read(EMPTY[("-y", "y")])
P_lam = (a.sum(axis=(1, 2)) - b.sum(axis=(1, 2))) / (a.sum(axis=(1, 2)) + b.sum(axis=(1, 2)))
k = (lam > 2) & (lam < 5)
P0 = float(np.mean(P_lam[k]))
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
Pimg, _ = pol.polarization(a[k].sum(0), b[k].sum(0))
im = ax[0].imshow(Pimg, origin="lower", extent=EXT, vmin=0.8, vmax=1.0, cmap="viridis")
fig.colorbar(im, ax=ax[0], label="P (2 to 5 Å)"); ax[0].set(xlabel="x (mm)", ylabel="y (mm)", title="No sample: Pyy")
ax[1].plot(lam, P_lam, "o-"); ax[1].set(xlabel="λ (Å)", ylabel="P over the field", ylim=(0.8, 1.0),
                                        title=f"P0 = {P0:.3f} (mean 2 to 5 Å)")
ax[1].grid(alpha=0.3); plt.tight_layout(); plt.show()
'''
MATRIX = r'''
ROT = sorted(FULL)[0] if FULL else None
if ROT is None:
    raise SystemExit("No full matrix yet (18 images with the sample, part 0).")
rebin = w.ToggleButtons(options=[("1 (110 µm)", 1), ("2 (220 µm)", 2), ("4 (440 µm)", 4)], value=2,
                        description="Pixels added")
rot_pick = w.ToggleButtons(options=[(f"{r:g}°", r) for r in sorted(FULL)], value=ROT, description="Rotation")
lam_i = w.IntSlider(value=5, min=0, max=15, description="λ bin", continuous_update=True)
img_m = live_view.FigureImage()
CACHE = {}
def M(rot=None, rb=None):
    key = (rot if rot is not None else rot_pick.value, rb or rebin.value)
    if key not in CACHE:
        CACHE[key] = pol.matrix(FULL[key[0]], P0=P0, rebin=key[1])
    return CACHE[key]
def draw_matrix(_=None):
    P, dP, lam = M()
    k = lam_i.value
    with img_m:
        fig, ax = plt.subplots(3, 3, figsize=(8.4, 8), sharex=True, sharey=True)
        for i, a_ in enumerate("xyz"):
            for j, b_ in enumerate("xyz"):
                im = ax[i, j].imshow(P[k, i, j], origin="lower", extent=EXT, vmin=-1, vmax=1, cmap="RdBu_r")
                ax[i, j].set_title(f"P{a_}{b_}")
        fig.suptitle(f"P / P0 at λ = {lam[k]:.2f} Å, rotation {rot_pick.value:g}°, noise ≈ "
                     f"{np.nanmedian(dP[k, 1, 1]):.3f} per pixel")
        fig.colorbar(im, ax=ax, shrink=0.6)
for c in (rebin, rot_pick, lam_i):
    c.observe(live_view.throttled(draw_matrix), "value")
display(w.VBox([rebin, rot_pick, lam_i, img_m])); draw_matrix()
'''
ANGLE = r'''
method = w.ToggleButtons(options=[("one component: Pyy = cos φ", "Pyy"), ("the trace: 1 + 2 cos φ", "trace")],
                         value="Pyy", description="φ from", style={"button_width": "240px"})
px = w.FloatSlider(value=@@PX@@, min=-6.5, max=6.5, step=0.1, description="x (mm)", continuous_update=True)
py = w.FloatSlider(value=@@PY@@, min=-6.5, max=6.5, step=0.1, description="y (mm)", continuous_update=True)
lam_lo = w.FloatRangeSlider(value=(2.0, 5.0), min=1.5, max=6.0, step=0.1, description="fit λ (Å)",
                            continuous_update=True)
img_a, txt_a = live_view.FigureImage(), w.HTML()
FIT = {}
def angle_at(P, x, y):
    n = P.shape[-1]
    ix = int(np.clip((x - EXT[0]) / (EXT[1] - EXT[0]) * n, 1, n - 2))
    iy = int(np.clip((y - EXT[2]) / (EXT[3] - EXT[2]) * n, 1, n - 2))
    Pm = np.nanmean(P[..., iy - 1:iy + 2, ix - 1:ix + 2], axis=(-1, -2))
    if method.value == "Pyy":
        return np.arccos(np.clip(Pm[:, 1, 1], -1, 1)), Pm
    return np.arccos(np.clip((Pm[:, 0, 0] + Pm[:, 1, 1] + Pm[:, 2, 2] - 1) / 2, -1, 1)), Pm
def draw_angle(_=None):
    P, dP, lam = M(ROT)
    phi, Pm = angle_at(P, px.value, py.value)
    k = (lam >= lam_lo.value[0]) & (lam <= lam_lo.value[1])
    # straight line through zero, φ = s λ, least squares; the scatter of the points gives the uncertainty
    s = np.sum(lam[k] * phi[k]) / np.sum(lam[k] ** 2)
    res = phi[k] - s * lam[k]
    ds = np.sqrt(np.sum(res ** 2) / max(k.sum() - 1, 1) / np.sum(lam[k] ** 2))
    FIT.update(J=s / C * 1e6, dJ=ds / C * 1e6, method=method.value, x=px.value, y=py.value)
    with img_a:
        fig, ax = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw=dict(width_ratios=[1, 1.4]))
        ax[0].imshow(P[5, 1, 1], origin="lower", extent=EXT, vmin=-1, vmax=1, cmap="RdBu_r")
        ax[0].plot(px.value, py.value, "s", mfc="none", mec="k", ms=10, mew=2); ax[0].set(title="Pyy: your point")
        ax[1].plot(lam, phi, "o", color="0.6"); ax[1].plot(lam[k], phi[k], "o", color="k", label="φ used in the fit")
        ll = np.linspace(0, 6.2, 50)
        ax[1].plot(ll, s * ll, color="tab:orange", label=f"φ = c λ ∫B dl: {FIT['J']:.2f} ± {FIT['dJ']:.2f} µT·m")
        ax[1].set(xlabel="λ (Å)", ylabel="φ (rad)", xlim=(0, 6.2), ylim=(0, 3.2), title=f"φ from {method.value}")
        ax[1].legend(fontsize=9); ax[1].grid(alpha=0.3); plt.tight_layout()
    v = pol.rotation_axis(Pm[..., None, None])[..., 0, 0]
    v = np.nanmean(v[k], axis=0); v /= np.linalg.norm(v)
    txt_a.value = (f"∫B dl = <b>{FIT['J']:.2f} ± {FIT['dJ']:.2f} µT·m</b> ({method.value}); axis of the rotation "
                   f"(the field): x {v[0]:+.2f}, y {v[1]:+.2f}, z {v[2]:+.2f}")
for c in (method, px, py, lam_lo):
    c.observe(live_view.throttled(draw_angle), "value")
display(w.VBox([method, px, py, lam_lo, img_a, txt_a])); draw_angle()
'''
MAP = r'''
P, dP, lam = M(ROT)
phi = pol.rotation_angle(P)
J = pol.field_integral(lam, phi) * 1e6
TRUE = pol.true_field_integral(@@FIELD@@, ROT, bins=J.shape[0]) * 1e6
fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
for a_, img, t in ((ax[0], J, "measured ∫B dl (trace, 2 to 5 Å)"), (ax[1], TRUE, "@@TRUE_TITLE@@")):
    im = a_.imshow(img, origin="lower", extent=EXT, cmap="magma", vmin=0, vmax=max(np.nanmax(TRUE), 1e-3) * 1.1)
    a_.set(xlabel="x (mm)", ylabel="y (mm)", title=t)
fig.colorbar(im, ax=ax[:2], label="µT·m")
c = J.shape[0] // 2
yy = np.linspace(EXT[2], EXT[3], J.shape[0])
ax[2].plot(yy, J[:, c], ".", label="measured"); ax[2].plot(yy, TRUE[:, c], "-", label="@@TRUE_LABEL@@")
ax[2].set(xlabel="y (mm) at x = 0", ylabel="∫B dl (µT·m)", title="Profile through the middle"); ax[2].legend(fontsize=9)
ax[2].grid(alpha=0.3); plt.show()
inside = TRUE > 0.3 * TRUE.max()
print(f"inside the field (where the calculation is above 30 % of its maximum): measured − calculated = "
      f"{np.nanmean((J - TRUE)[inside]):+.2f} ± {np.nanstd((J - TRUE)[inside]):.2f} µT·m (mean ± scatter); "
      f"outside: measured {np.nanmean(J[~inside]):.2f} µT·m (the bias of the noise: trace < 3)")
'''
COMPARE = {
    "solenoid": r'''
B, wire, vox = pol.solenoid_field()
n = B.shape[0]; c = n // 2
print(f"Biot–Savart at the center of the coil: B = {np.linalg.norm(B[c, c, c]) * 1e3:.3f} mT, "
      f"∫B dl through the center along the beam = {np.linalg.norm(B[c, c].sum(0)) * vox * 1e6:.2f} µT·m")
print(f"long-solenoid formula: μ0 N I / ℓ = {4e-7 * np.pi * 13.5 * 0.6 / 0.0155 * 1e3:.3f} mT")
if FIT:
    print(f"your fit at ({FIT['x']:.1f}, {FIT['y']:.1f}) mm: {FIT['J']:.2f} ± {FIT['dJ']:.2f} µT·m "
          f"-> mean B over the 11 mm diameter: {FIT['J'] / 11e-3 * 1e-3:.3f} ± {FIT['dJ'] / 11e-3 * 1e-3:.3f} mT")
''',
    "meteorite": r'''
z = np.load(pol.QV_FILE)
meas = z["measured"]                                   # their 33 angles × 9 components, 80 × 80 pixels, unnormalized
P1, _, lam1 = M(0.0, 1) if 0.0 in FULL else M(ROT, 1)
k = (lam1 > 2) & (lam1 < 5)
mine = np.nanmean(P1[k], axis=0) * P0
from scipy.ndimage import zoom
fig, ax = plt.subplots(2, 3, figsize=(10, 6.4))
cor = []
for i in range(3):
    for j in range(3):
        a_ = zoom(np.nan_to_num(mine[i, j]), meas.shape[-1] / mine.shape[-1], order=1)
        cor.append(np.corrcoef(a_.ravel(), np.nan_to_num(meas[0, 3 * i + j]).ravel())[0, 1])
for c_, (i, j) in enumerate(((0, 1), (1, 1), (2, 2))):
    ax[0, c_].imshow(mine[i, j], origin="lower", extent=EXT, vmin=-1, vmax=1, cmap="RdBu_r")
    ax[0, c_].set_title(f"P{'xyz'[i]}{'xyz'[j]}: twin")
    ax[1, c_].imshow(meas[0, 3 * i + j], origin="lower", extent=(-7.44, 7.44, -7.44, 7.44), vmin=-1, vmax=1, cmap="RdBu_r")
    ax[1, c_].set(title=f"P{'xyz'[i]}{'xyz'[j]}: RADEN", xlim=EXT[:2], ylim=EXT[2:])
plt.tight_layout(); plt.show()
print("correlation twin / RADEN, front view, per component (xx xy xz / yx yy yz / zx zy zz):", np.round(cor, 2))
''',
}
QUESTIONS = {
    "solenoid": r'''
q.choice("Part 3: why measure without the sample first?",
         ["To find P0, the polarization the polarizer and analyzer give without field: the images of the sample are "
          "divided by it, or a perfect sample would seem to depolarize the beam.",
          "To find the dark current of the camera.", "To align the coil.", "It is not needed: P is a ratio."],
         answer=0, why={1: "There is no dark here: the shutter stays open.", 2: "The coil is not in the beam then.",
                        3: "The ratio cancels the attenuation, not the imperfect polarizer."},
         explanation="P0 ≈ 0.91 here (flipping ratio 22, Sales et al.); it multiplies all the measured P.",
         hints=["Without field, what should Pyy be? What do you measure?"], title="Q1. P0")
q.choice("Part 5: for the coil, 'one component' (Pyy) and 'the trace' give about the same ∫B dl at the center. Why, "
         "and when would Pyy fail?",
         ["The field is along x, perpendicular to y: a spin along y turns fully and Pyy = cos φ. If the field had a "
          "component along y, Pyy would stay closer to 1 and give too small an angle; the trace works for any "
          "direction.", "Both always agree.", "Pyy is better: it has less noise.", "The trace fails for a coil."],
         answer=0, why={1: "Try the fragment: they do not.", 2: "The trace adds three noisy components but is right "
                        "for any field; Pyy is right only for a field perpendicular to y.",
                        3: "The trace is a property of any rotation."},
         explanation="Rodrigues: Pyy = cos φ + B̂y²(1 − cos φ). Only for B̂y = 0 is it cos φ.",
         hints=["Look at the Rodrigues formula for Pyy."], title="Q2. One component or the trace")
q.number("Part 5: ∫B dl at the center of the coil, from the trace (µT·m):", value=5.58, tol=0.4, unit="µT·m",
         hints=["Put the point at (0, 0), method 'the trace'."], explanation="Biot–Savart: 5.58 µT·m.",
         title="Q3. ∫B dl")
q.number("The largest ∫B dl the arccos method can measure with λ up to 6 Å, before φ passes π (µT·m)?", value=11.3,
         tol=0.6, unit="µT·m", hints=["π = c λ ∫B dl with λ = 6 Å, c = 46 320 rad/(Å T m)."],
         explanation="π / (46 320 × 6) = 11.3 µT·m. Beyond, arccos folds back: use shorter wavelengths, or follow φ "
                     "continuously from short to long λ (unwrapping).", title="Q4. The limit")
q.choice("Part 3: adding 4 × 4 pixels instead of 2 × 2:",
         ["divides the noise per pixel by 2 and doubles the pixel (0.44 mm): fine for the coil, whose field changes "
          "over millimeters; it would blur the field of a rock whose regions are 1 mm.",
          "changes ∫B dl.", "makes the image sharper.", "has no effect."],
         answer=0, why={1: "It averages; the value stays.", 2: "Coarser, not sharper.",
                        3: "Look at the noise printed in the title."},
         explanation="Noise ∝ 1/√N: 4 times more neutrons, half the noise.",
         hints=["Compare the noise in the title of part 3."], title="Q5. Resolution and noise")
q.number("Part 7: the mean field inside the coil along the beam (mT):", value=0.51, tol=0.06, unit="mT",
         hints=["∫B dl / 11 mm: part 7 prints it."], explanation="5.58 × 10⁻⁶ / 0.011 = 0.51 mT; Biot–Savart at the "
                                                                "very center 0.54 mT, the long-solenoid formula 0.66 mT.",
         title="Q6. The field")
q.report()
''',
    "meteorite": r'''
q.choice("Part 3: why measure without the sample first?",
         ["To find P0, the polarization the polarizer and analyzer give without field: the images of the sample are "
          "divided by it, or a perfect sample would seem to depolarize the beam.",
          "To find the dark current of the camera.", "To magnetize the sample.", "It is not needed: P is a ratio."],
         answer=0, why={1: "There is no dark here: the shutter stays open.", 2: "The sample was magnetized before.",
                        3: "The ratio cancels the attenuation, not the imperfect polarizer."},
         explanation="P0 ≈ 0.91 here (0.87 on average at RADEN).",
         hints=["Without field, what should Pyy be? What do you measure?"], title="Q1. P0")
q.choice("Part 5: at the strongest point of the fragment, 'one component' (Pyy) gives a smaller ∫B dl than the "
         "trace (by 10 % or more). Why?",
         ["The field there has a component along y (the axis printed: y about 0.4): a spin along y turns less, Pyy "
          "stays closer to 1. The trace gives the angle for any direction.", "Pyy is noisier.",
          "The trace overestimates the field.", "The sample attenuates the y component."],
         answer=0, why={1: "It is not noise: the difference is systematic.",
                        2: "On the coil both agree: the trace is right.",
                        3: "P is a ratio: the attenuation cancels."},
         explanation="Rodrigues: Pyy = cos φ + B̂y²(1 − cos φ): for B̂y = 0.4 and φ = 1.5 rad, Pyy = 0.22 instead of "
                     "cos φ = 0.07, read as φ = 1.35 rad. Elsewhere in the fragment B̂y is larger and the error too.",
         hints=["Read the axis of the rotation printed under the plot."], title="Q2. One component or the trace")
q.number("Part 5: the largest ∫B dl you find, from the trace (µT·m):", value=8.5, tol=2.0, unit="µT·m",
         hints=["Move the point onto the strongest region (part 6 shows it)."],
         explanation="About 8 to 9 µT·m (9.4 on a single line of sight of the authors' field).", title="Q3. ∫B dl")
q.number("The largest ∫B dl the arccos method can measure with λ up to 6 Å, before φ passes π (µT·m)?", value=11.3,
         tol=0.6, unit="µT·m", hints=["π = c λ ∫B dl with λ = 6 Å, c = 46 320 rad/(Å T m)."],
         explanation="π / (46 320 × 6) = 11.3 µT·m: the fragment is close to it. Beyond, arccos folds back: use "
                     "shorter wavelengths, or follow φ continuously from short to long λ.", title="Q4. The limit")
q.choice("Part 6: the measured map is a little above the calculated one outside the fragment and where the field is "
         "weak. Why?",
         ["Noise: the trace of a noisy matrix is below 3 on average, which reads as an angle φ > 0. It is a bias, "
          "not a field; more neutrons (or adding pixels) reduce it.",
          "The aluminium holder is magnetic.", "The Earth's field.", "The meteorite magnetizes the air."],
         answer=0, why={1: "Aluminium is not magnetic (the authors checked the holder).",
                        2: "A field outside the sample would also turn the spin without the sample: P0 would show it.",
                        3: "No."},
         explanation="arccos of a noisy quantity near its maximum is biased upward: the noise floor of the method.",
         hints=["Compare the bias with the noise per pixel of part 3."], title="Q5. The noise floor")
q.choice("Part 7: the twin and RADEN agree well in the front view. What does it test?",
         ["That the field reconstructed by Qvistgaard et al. from 33 angles reproduces their own projection at 0°: a "
          "consistency check of their tomography (and of the twin).",
          "That the meteorite is uniformly magnetized.", "Nothing: the twin copies the measurement.",
          "That RADEN and ODIN have the same polarizer."],
         answer=0, why={1: "Q2 of the page: it is not.", 2: "The twin computes the images from the 3D field, not from "
                        "the measured images.", 3: "The P0 differ (0.87 and 0.91)."},
         explanation="The forward model of the twin (the field → the spin → P) applied to their reconstruction gives "
                     "back their measured images.", hints=["What does the twin use as input?"],
         title="Q6. What the comparison tests")
q.report()
''',
}

VARIANTS = {
    "solenoid": dict(file="ODIN_magnet_msc_solenoid.ipynb", quiz="odin_magnet_msc_solenoid", sample="magnet_solenoid",
                     field='"solenoid"', px="0.0", py="0.0", title="What is the field inside a coil?",
                     true_title="calculated (Biot–Savart along the wire)", true_label="Biot–Savart",
                     mission=r"""
**Your mission.** You build the small magnets of neutron instruments, and you need a method you can trust to measure
the field **inside** a coil without opening it: from the raw files to a map of $\int B\,\mathrm{d}l$ with its
uncertainty, and you find out what limits it. You develop it on the coil of M. Sales *et al.*, *Three Dimensional
Polarimetric Neutron Tomography of Magnetic Fields*, Sci. Rep. **8**, 2214 (2018), measured at RADEN (J-PARC): 13.5
windings of aluminium wire, 15.5 mm long, 11 mm in diameter, 0.6 A, axis along $x$ tilted by 9°. Its field is
computed by the Biot–Savart law along the wire, so you can check your method against the truth.""",
                     rots="0"),
    "meteorite": dict(file="ODIN_magnet_msc_meteorite.ipynb", quiz="odin_magnet_msc_meteorite",
                      sample="nwa7034_fragment", field='"nwa7034"', px="-2.7", py="-0.5",
                      title="A magnet inside a meteorite", true_title="the authors' field (their reconstruction)",
                      true_label="Qvistgaard et al.",
                      mission=r"""
**Your mission.** Paleomagnetists want to know where the magnetization sits inside a rock, not only its total. You
develop the analysis of polarized neutron imaging on the fragment of the Martian meteorite NWA 7034 of
C. H. Qvistgaard, E. B. Naver *et al.*, Geochem. Geophys. Geosyst. **27**, e2025GC012641 (2026), measured at RADEN
(J-PARC): 2 × 10 × 13 mm³, magnetized with a small whiteboard magnet. The twin uses the field they reconstructed from
33 angles (DTU Data, doi:10.11583/DTU.30775208, CC BY 4.0), and you compare your images with their measured ones.""",
                      rots="0 and 90"),
}


def msc(key):
    V = VARIANTS[key]
    sub = lambda s: (s.replace("@@QUIZ@@", V["quiz"]).replace("@@SAMPLE@@", V["sample"])
                      .replace("@@PROPOSAL@@", PROPOSAL).replace("@@FIELD@@", V["field"]).replace("@@PX@@", V["px"])
                      .replace("@@PY@@", V["py"]).replace("@@TRUE_TITLE@@", V["true_title"])
                      .replace("@@TRUE_LABEL@@", V["true_label"]))
    rot_cmds = ("move(stage_x, 0, stage_rot, 0)\npolarization_matrix(150, 'coil 0 deg')" if key == "solenoid" else
                "move(stage_x, 0, stage_rot, 0)\npolarization_matrix(150, 'fragment 0 deg')\n"
                "move(stage_rot, 90)\npolarization_matrix(150, 'fragment 90 deg')")
    cells = [md(f"# {V['title']} (MSc: develop the method)\n" + V["mission"] + r"""

**The physics.** In a field $\vec B$ the spin turns about $\vec B$ by $\varphi = c\,\lambda \int B\,\mathrm{d}l$
($c$ = 4.632 × 10¹⁴ T⁻¹ m⁻²). A polarizer and a spin rotator set the spin along $i$ before the sample, a rotator and an
analyzer select the spin along $j$ after it; with $\pm i$,
$P_{ij} = (N_{+i,j} - N_{-i,j})/(N_{+i,j} + N_{-i,j})$. For a field of one direction $\hat B$ along the line of sight,
$P$ is the rotation matrix of angle $\varphi$ about $\hat B$ (Rodrigues), times $P_0$, the quality of the polarizer and
analyzer: for instance $P_{yy} = \cos\varphi + \hat B_y^2 (1 - \cos\varphi)$ and $P_{yx} - P_{xy} = 2 \hat B_z \sin\varphi$.
The Timepix3 camera sorts the neutrons by wavelength: $\varphi(\lambda)$ is a straight line whose slope gives
$\int B\,\mathrm{d}l$.

The code of each step is given (and locked): read it, run it, and make the decisions with the widgets.
"""), code(sub(SETUP)), md("## The sample"), code(r'''
import sample_library as sl
spec = sl.load("odin")[SAMPLE]
print(sl.describe("odin", spec))
sl.draw("odin", spec, fig=plt.figure(figsize=(10, 3.5))); sl.show()
'''), md(f"""
## Before you measure

1. **Without the sample** (stage x = 500 mm), polarizer in: spin in $+y$ and $-y$, analyzer $y$, 150 s each. This gives
   $P_0$.
2. **The sample** at {V['rots']}°: the 18 images of the polarization matrix, 150 s each (as at RADEN).

Choppers *natural* (the band of one pulse, 1.5 to 6 Å, sorted by time of flight), pinhole 2 cm.
"""), code(r'''
q.number("How many minutes of beam does one full polarization matrix take, with 150 s per image?", value=45, tol=0.5,
         unit="min", hints=["9 components, each from two images (spin in +i and −i)."],
         explanation="18 × 150 s = 45 min, as at RADEN for each angle.", title="Q0. The cost of a matrix")
'''), md(f"""
## 0. Your measurements

Choose how: **in NICOS** (the commands below), or **here, with a panel** (*Polarized image* and *Polarization matrix*).
Either way your files go to the folder of proposal {PROPOSAL}.
"""), code(f'import measure_panel\nmeasure_panel.Panel("odin", proposal="{PROPOSAL}", samples=["{V["sample"]}"])'),
        nicos_step(md(f"""
### Step 1. Your proposal

In NICOS, tab **Experiment**, **Find my proposal**, choose **{PROPOSAL}**, then **Apply**; tab **Sample**: mount
`{V['sample']}`. Then tab **Instrument interaction**, one command at a time.
""")), nicos_step(md(f"""
### Step 2. Without the sample, then the sample

`polarimetry(t, title)` takes one image (counts per wavelength) with the present `spin_in` and `spin_out`;
`polarization_matrix(t, title)` takes the 18.

```
move(choppers, 'natural', pinhole, 0.02, diffuser, 'in', shutter, 'open', polarizer, 'in')
move(stage_x, 500, spin_out, 'y', spin_in, '+y')
polarimetry(150, 'no sample +y y')
move(spin_in, '-y')
polarimetry(150, 'no sample -y y')
{rot_cmds}
```
""")), stop(md("## 1. Your files\n\nThe polarized images of the folder of the proposal, read from the files.")),
        code(sub(FILES)), md("## 2. Which file is what?"), code(PICK), md(r"""
## 3. P0, and the matrix

$P_0(\lambda)$ from the two images without the sample; then the 18 images of the sample give $P/P_0$. **Your
decision:** how many pixels to add up (noise against resolution). The title prints the noise per pixel.
"""), code(P0_CELL), code(MATRIX), md(r"""
## 4. Develop the measurement of the angle

Two ways to get $\varphi$ at a point (3 × 3 pixels): from **one component**, $P_{yy} = \cos\varphi$ (true only for a
field perpendicular to $y$), or from **the trace**, $P_{xx} + P_{yy} + P_{zz} = 1 + 2\cos\varphi$ (true for any
direction). $\varphi(\lambda)$ is then fitted by a straight line through zero over the range of $\lambda$ you choose:
its slope is $c \int B\,\mathrm{d}l$; the scatter of the points around it gives the uncertainty. The axis of the
rotation (the antisymmetric part of $P$) gives the direction of the field.
"""), code(sub(ANGLE)), md(r"""
## 5. The map, and the truth

The trace and the fit at every pixel (`pol.rotation_angle`, `pol.field_integral`), next to the $\int B\,\mathrm{d}l$
of the field the twin uses (what a perfect measurement would find). The difference tells the accuracy of the method.
"""), code(sub(MAP)), md("## 6. " + ("The field of the coil" if key == "solenoid" else "Your images and those of RADEN")),
        code(COMPARE[key]), md("## Your results\n\nYour score on the questions of the notebook, and a report to download."),
        code(QUESTIONS[key]), md(r"""
## Submit your work

When you are done: save this notebook (*Save*), write what you thought of the exercise, then submit.
"""), code('import submit\n_ = submit.Submit("odin/exercises/magnet_imaging", "msc", quiz=q)')]
    distribute(cells, [
        ("display(w.VBox([rebin, rot_pick, lam_i, img_m]))", [1]),
        ("display(w.VBox([method, px, py, lam_lo, img_a, txt_a]))", [2, 3, 4]),
        ("(the bias of the noise: trace < 3)", [5]),
    ])
    write(cells, os.path.join(HERE, V["file"]), all_code_locked=True)
    print("written:", V["file"])


def beamtime():
    bt = [md(f"""
# Beamtime on ODIN: magnetic fields inside matter (starter notebook)

Your proposal (**{PROPOSAL}**) is below, with the button *Open NICOS*. This notebook only gives you the tools; what to
measure and how to analyze it is your decision, as at a real beamtime.
"""), md("**Your proposal** (click to open it):"),
        code('import sys, os\nsys.path.insert(0, os.path.abspath("../../.."))\nimport nb_tools\n'
             'nb_tools.proposal("odin/exercises/magnet_imaging/beamtime.md")'),
        code('nb_tools.nicos("odin")'),
        stop(md("## Your files\n\nNICOS writes them to the folder of the proposal; the logbook is read from the files.")),
        code(SETUP.replace('q = quiz.Quiz("@@QUIZ@@")       # the questions of this notebook\n', "")
             .replace('SAMPLE = "@@SAMPLE@@"\n', "")),
        code(FILES.replace("@@PROPOSAL@@", PROPOSAL).replace(
            'import sample_library as sl\nNAME = sl.load("odin")[SAMPLE]["name"]\n', "").replace(
            ' and r.get("sample") == NAME', "")),
        md(r"""
## Tools

- in NICOS: devices `polarizer` (in/out), `spin_in` (±x, ±y, ±z), `spin_out` (x, y, z), `stage_rot`; commands
  `polarimetry(t, title)` (one image, counts per wavelength) and `polarization_matrix(t, title)` (the 18 images);
- `pol.read(file)` → counts (λ, y, x), λ, attributes; `pol.polarization(N_plus, N_minus)` → P, dP;
- `pol.matrix(files, P0=..., rebin=...)` → P (λ, 3, 3, y, x), dP, λ (files: a list, the attributes tell which is
  which);
- `pol.rotation_angle(P)` (from the trace), `pol.rotation_axis(P)`, `pol.field_integral(λ, φ, lam_range)` → ∫B dl [T m];
- `pol.C_LARMOR` = 46 320 rad / (Å T m); `EXT` for `imshow`;
- for the fragment: the matrices measured at RADEN, `np.load(pol.QV_FILE)["measured"]` (33 angles × 9 components ×
  80 × 80 pixels of 0.186 mm; angle index 0 = 0°).
"""), code("# your analysis\n"), code(""), md("## Results for the committee\n\n(your answers, with uncertainties, "
                                                 "and your logbook)")]
    write(bt, os.path.join(HERE, "ODIN_magnet_beamtime.ipynb"), all_code_locked=False)
    print("written: ODIN_magnet_beamtime.ipynb")


if __name__ == "__main__":
    for k in VARIANTS:
        msc(k)
    beamtime()
