"""Generates ODIN_battery.ipynb: the guided page (Voila, no code shown) of the exercise
"How does lithium enter a battery electrode?" (operando white-beam imaging of the lithium half-cell with an
ultra-thick graphite electrode of Strobl et al., Adv. Energy Mater. 2025).

    python gen_page.py
"""
import os
import sys

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from nbgen import distribute  # noqa: E402

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# How does lithium enter a battery electrode?

You are operating the ODIN imaging instrument at ESS. Behind this page, a simulation of the instrument produces your
measurements, in the formats of the real instrument.

**Your mission.** You work for a battery maker. A thicker electrode stores more energy in the same cell, because less
of the cell is current collectors and separators. But the lithium must travel through the whole thickness: does it
reach the far side of an electrode **0.4 mm thick**, or does it pile up near the separator? And how much of it stays
trapped after one charge and discharge, lost for good? Watch the lithium move inside a working cell, image after image,
and tell the team (the last questions).

**The sample is real.** A lithium half-cell with an ultra-thick graphite electrode was imaged exactly this way, during
a whole cycle, by M. Strobl, M. E. Baur, L. Theil Kuhn *et al.*, *Concurrent operando neutron imaging and diffraction
analysis revealing spatial lithiation phase evolution in an ultra-thick graphite electrode*, Adv. Energy Mater. (2025),
at SENJU (J-PARC, Japan); the cell is that of M.-E. Lăcătuşu, L. Theil Kuhn *et al.*, arXiv:2104.03564 (2021). The twin
uses their cell and what they observed; the exact profiles of lithium are a model built on their findings.

**Why neutrons.** Lithium is light: X-rays hardly see it. Neutrons do: natural lithium absorbs them strongly (its
isotope ⁶Li above all). Where lithium arrives, the cell gets darker. Neutrons also go through the aluminium casing.

**Questions along the page** check each step: answer in the box, then click *Check*. A wrong answer is explained;
after a try you can also show the answer. Your answers are kept.
""")

code(r"""
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
import odin_radiography as tomo, odin_mcstas as tw
import sample_library as sl
import live_view
from page_output import into
import quiz
q = quiz.Quiz("odin_battery_bsc")          # the questions, along the page

SAMPLE = "battery_graphite"
odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
odin.move(sample=SAMPLE)
EXT = tomo.extent()
CHORD_CM = 1.6                 # the beam crosses the electrode along its diameter: 16 mm
ELECTRODE = (0.0, 0.40)        # [mm] y of the graphite electrode (0: the separator)
MATS = sl.load("odin")[SAMPLE]["materials"]
""")

md(r"""
## 1. How much does lithium darken the electrode?

The electrode is graphite: layers of carbon, between which lithium slides in (**intercalation**) up to one lithium
atom per six carbons, LiC₆. Its lithium content is written $\text{Li}_x\text{C}_6$, $x$ from 0 to 1. Its pores are
filled with a liquid electrolyte, rich in hydrogen, which attenuates the beam too, but does not change during the cycle.

Move the slider: the attenuation coefficient $\Sigma$ of the electrode (graphite, 35 % of pores filled with
electrolyte) for a lithium content $x$, at the wavelengths of ODIN (NCrystal), and the transmission through the 16 mm
of electrode the beam crosses.
""")

code(r"""
LAM = np.linspace(1.0, 8.0, 141)
S0 = tw.sigma_tot(MATS["graphite x=0.00"], LAM)
S1 = tw.sigma_tot(MATS["graphite x=1.00"], LAM) if "graphite x=1.00" in MATS else None
if S1 is None:
    k = max(float(n.split("=")[1]) for n in MATS if n.startswith("graphite x="))
    S1 = S0 + (tw.sigma_tot(MATS[f"graphite x={k:.2f}"], LAM) - S0) / k
x_s = w.FloatSlider(value=0.5, min=0, max=1, step=0.01, description="x in LiₓC₆", continuous_update=True)
view_x = live_view.FigureImage()

def draw_x(_=None):
    S = S0 + x_s.value * (S1 - S0)
    with view_x:
        fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
        ax[0].plot(LAM, S0, color="0.6", label="x = 0 (graphite + electrolyte)")
        ax[0].plot(LAM, S, color="tab:red", lw=2, label=f"x = {x_s.value:.2f}")
        ax[0].set(xlabel="λ (Å)", ylabel="Σ (cm⁻¹)", title="Attenuation of the electrode"); ax[0].legend(fontsize=9)
        ax[1].plot(LAM, np.exp(-S0 * CHORD_CM), color="0.6"); ax[1].plot(LAM, np.exp(-S * CHORD_CM), color="tab:red", lw=2)
        ax[1].set(xlabel="λ (Å)", ylabel="transmission T", title="Through 16 mm of electrode", ylim=(0, 0.5))
        for a in ax:
            a.grid(alpha=0.3)
        plt.tight_layout()
    txt_x.value = (f"At 3 Å: Σ = {np.interp(3, LAM, S):.2f} cm⁻¹, of which lithium <b>{np.interp(3, LAM, S - S0):.2f} "
                   f"cm⁻¹</b>; the lithium part grows in proportion to λ (absorption: the slower the neutron, the longer "
                   f"it stays near a nucleus).")

txt_x = w.HTML()
x_s.observe(live_view.throttled(draw_x), "value")
draw_x()
display(w.VBox([x_s, view_x, txt_x]))
""")

md(r"""
## 2. Your sample

A cylindrical cell, **seen edge-on**: its layers are horizontal disks 16 mm in diameter, and the beam crosses them along
a diameter. From the bottom: a steel current collector, **metallic lithium** (0.75 mm), a glass-fiber **separator**
soaked with electrolyte (0.26 mm), the **graphite electrode** (0.40 mm), a steel collector; all in an aluminium casing
lined with PTFE. The vertical position $y$ is counted from the separator: the electrode is between $y$ = 0 and
$y$ = 0.40 mm.

A **cycler** drives a constant current of 1.37 mA through the cell, which fills the electrode in 35 hours (a rate of
C/35): lithium leaves the lithium metal, crosses the separator as ions, and enters the graphite (**lithiation**, 30 h),
then the current is reversed and lithium goes back (**delithiation**, about 20 h), then the cell rests until 55 h.
The device `cycle_time` of the twin is the time since the start of the cycle.
""")

code(r"""
spec = odin.sample_spec(SAMPLE)
smp_out = w.Output()
with into(smp_out):
    sl.draw("odin", spec, hidden=["materials"], fig=plt.figure(figsize=(10, 3.6)))
    sl.show()
display(smp_out)
""")

md(r"""
## 3. Operate the instrument: a film of the cycle

The electrode is 0.4 mm thick: you need small pixels. ODIN is set for **white-beam imaging with the high-resolution
camera** (512 × 512 pixels of 27.5 µm, pinhole 1 cm: blur about 0.05 mm), images of **60 s**.

1. a **dark** (shutter closed) and an **open beam** (cell out: stage at 500 mm), 60 s each;
2. *Film the cycle*: one image every Δt of the cycle, from the pristine cell (0 h) to the end (55 h).

A cycle lasts 55 hours; an image, one minute: the process is slow compared with the measurement, so each image is a
snapshot. Strobl *et al.* summed 15 minutes per image at SENJU. (The twin computes each image in a few seconds.)
""")

code(r"""
st = odin.status()
shut = w.ToggleButtons(options=[("closed", "closed"), ("open", "open")], value=st["shutter"], description="Shutter")
inout = w.ToggleButtons(options=[("in", 0.0), ("out", 0.5)], value=0.0 if abs(st["stage_x"]) < 0.02 else 0.5,
                        description="Cell")
button1 = w.Button(description="Take image (60 s)", button_style="primary", icon="camera", layout=w.Layout(width="auto"))
step = w.ToggleButtons(options=[("every 5 h", 5.0), ("every 2.5 h", 2.5), ("every hour", 1.0)], value=2.5,
                       description="Δt")
button2 = w.Button(description="Film the cycle", button_style="primary", icon="film", layout=w.Layout(width="auto"))
bar = w.IntProgress(value=0, min=0, max=1)
out = w.Output()
img_live = live_view.FigureImage()

def show(title):
    with img_live:
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.imshow(odin.last_image, origin="lower", extent=EXT, cmap="gray")
        ax.set(ylim=(-2.5, 2.0), xlabel="x (mm)", ylabel="y (mm)", title=title)
        plt.tight_layout()

def settings(**kw):
    odin.move(sample=SAMPLE, choppers="white", pinhole=0.01, diffuser="in", **kw)

def take(_):
    button1.disabled = True
    with out:
        clear_output()
        try:
            settings(shutter=shut.value, stage_x=inout.value)
            kind = "dark" if shut.value == "closed" else ("open beam" if inout.value > 0.02 else
                                                          f"cell {odin.status()['cycle_time']:g} h")
            f = odin.camera(60.0, title=kind, pixels=512)
            print(f"{os.path.basename(f)}: {kind}")
            show(kind)
        except Exception as e:
            print("Error:", e)
    button1.disabled = False
    refresh_list()

def film(_):
    button2.disabled = True
    with out:
        clear_output()
        try:
            times = np.round(np.arange(0, 55.0 + 1e-9, step.value), 2)
            bar.max, bar.value = len(times), 0
            settings(shutter="open", stage_x=0.0)
            for t in times:
                odin.move(cycle_time=float(t))
                odin.camera(60.0, title=f"cell {t:g} h", pixels=512)
                show(f"cell at {t:g} h of the cycle")
                bar.value += 1
            print(f"{len(times)} images, from 0 to 55 h. Parts 5 and 6 now use them.")
            draw_profile()
        except Exception as e:
            print("Error:", e)
    button2.disabled = False
    refresh_list()

button1.on_click(take)
button2.on_click(film)
display(w.VBox([shut, inout, button1, step, w.HBox([button2, bar]), out, img_live]))
""")

md(r"""
## 4. Your measurements
""")

code(r"""
listing = w.Output()

def measurements():
    ms = []
    if os.path.isfile(odin.log_file):
        for l in open(odin.log_file, encoding="utf-8"):
            e = json.loads(l)
            if e["action"] != "camera" or not e["details"].get("file"):
                continue
            d = e["details"]; s = d["state"]
            if s.get("sample") != SAMPLE or d.get("pixels") != 512 or abs(s["pinhole"] - 0.01) > 1e-6:
                continue
            kind = "dark" if s["shutter"] == "closed" else ("open beam" if abs(s["stage_x"]) > 0.02 else "cell")
            ms.append(dict(file=d["file"], path=os.path.join(odin.folder, d["file"]), kind=kind,
                           time=float(s.get("cycle_time", 0.0)), t=d["t"]))
    return ms

def groups():
    ms = measurements()
    dark = [m["path"] for m in ms if m["kind"] == "dark"][-1:]
    ob = [m["path"] for m in ms if m["kind"] == "open beam"][-1:]
    cell = {}
    for m in ms:
        if m["kind"] == "cell":
            cell[m["time"]] = m["path"]            # the newest image at each time of the cycle
    return (dark[0] if dark else None), (ob[0] if ob else None), dict(sorted(cell.items()))

def refresh_list():
    dk, ob, cell = groups()
    with into(listing):
        print(f"dark: {'yes' if dk else 'no'}; open beam: {'yes' if ob else 'no'}; images of the cell at "
              f"{len(cell)} times of the cycle: " + ", ".join(f"{t:g}" for t in cell) + " h")
        if not cell or 0.0 not in cell:
            print("The pristine cell (0 h) is needed: it is the reference of all the others.")

refresh_list()
display(listing)
""")

md(r"""
## 5. Where is the lithium? The profiles

The image of the pristine cell (0 h) holds everything that does not change: the casing, the steel, the electrolyte,
the graphite. Dividing an image by it keeps only what changed. Averaged over the middle of the cell ($x$ from −2.75
to 2.75 mm), for each row $y$:

$$\Delta\mu(y, t) = -\frac{1}{D}\,\ln\frac{T(y, t)}{T(y, 0)}, \qquad D = 1.6\ \text{cm}$$

($T$: the transmission, image minus dark over open beam minus dark): the change of the attenuation coefficient, the
lithium that came in. Move the slider through the times you measured.
""")

code(r"""
PROF = {}

def profiles():
    dk, ob, cell = groups()
    if not (dk and ob and 0.0 in cell):
        return None
    key = tuple(cell.values())
    if PROF.get("key") != key:
        img = lambda f: tomo.image(f)["data"] / tomo.image(f)["t"]       # counts per second
        D, O = img(dk), img(ob)
        n = D.shape[0]
        c = slice(int(n * 0.305), int(n * 0.695))            # x from −2.75 to 2.75 mm
        T = {t: np.clip((img(p) - D)[:, c].mean(1) / (O - D)[:, c].mean(1), 1e-6, None) for t, p in cell.items()}
        y = np.linspace(EXT[2], EXT[3], n + 1)[:-1] + (EXT[3] - EXT[2]) / (2 * n)
        PROF.update(key=key, y=y, times=np.array(sorted(T)), dmu=np.array([-np.log(T[t] / T[0.0]) / CHORD_CM
                                                                           for t in sorted(T)]))
    return PROF

t_i = w.SelectionSlider(options=[0.0], description="time (h)", continuous_update=True, layout=w.Layout(width="520px"))
view_p, txt_p = live_view.FigureImage(), w.HTML()

def draw_profile(_=None):
    P = profiles()
    if P is None:
        txt_p.value = "Measure first: dark, open beam and the film of the cycle (part 3)."
        return
    if list(t_i.options) != [float(t) for t in P["times"]]:
        t_i.options = [float(t) for t in P["times"]]
    k = int(np.argmin(np.abs(P["times"] - t_i.value)))
    with view_p:
        fig, ax = plt.subplots(figsize=(10, 3.8))
        ax.axvspan(*ELECTRODE, color="tab:orange", alpha=0.12, label="graphite electrode")
        ax.axvspan(-0.26, 0, color="0.85", alpha=0.6, label="separator")
        for j in range(k):
            ax.plot(P["y"], P["dmu"][j], color="0.8", lw=0.8)
        ax.plot(P["y"], P["dmu"][k], color="tab:red", lw=2, label=f"{P['times'][k]:g} h")
        ax.set(xlim=(-0.5, 0.6), ylim=(-0.2, 1.4), xlabel="y: distance from the separator (mm)",
               ylabel="Δμ (cm⁻¹)", title="Change of attenuation since the start (gray: the earlier times)")
        ax.legend(loc="upper right", fontsize=9); ax.grid(alpha=0.3)
        plt.tight_layout()
    e = (P["y"] > 0.03) & (P["y"] < 0.37)
    near, far = P["dmu"][k][(P["y"] > 0.03) & (P["y"] < 0.12)].mean(), P["dmu"][k][(P["y"] > 0.28) & (P["y"] < 0.37)].mean()
    txt_p.value = (f"in the electrode at {P['times'][k]:g} h: mean Δμ <b>{P['dmu'][k][e].mean():.2f} cm⁻¹</b>; "
                   f"near the separator {near:.2f}, near the collector {far:.2f} cm⁻¹")

t_i.observe(live_view.throttled(draw_profile), "value")
button_p = w.Button(description="Read the images", button_style="success", icon="chart-line", layout=w.Layout(width="auto"))
button_p.on_click(lambda _: draw_profile())
display(w.VBox([button_p, t_i, view_p, txt_p]))
draw_profile()
""")

md(r"""
## 6. The whole cycle at once, and how much lithium

The profiles of all the times side by side: time across, depth up, color $\Delta\mu$ (as figure 2b of Strobl *et al.*).
To turn $\Delta\mu$ into lithium, the page computes $\Delta\mu$ for each $x$ from the cross-sections (NCrystal) and
the spectrum of the camera, then reads $x$ back. One subtlety: the neutrons that reach the camera through the
electrode have crossed 16 mm of graphite, electrolyte, PTFE and aluminium first, which removed many of the slow ones
(the beam is **hardened**), and lithium absorbs slow neutrons most. So $\Delta\mu$ is computed with the spectrum
*transmitted* by the cell, and it is not quite proportional to $x$ (about 0.99 cm⁻¹ for $x$ = 1). The cycler counts the charge it passed: at C/35, $x$ would grow by 1/35 per hour
if all the current went into the graphite.
""")

code(r"""
button_m = w.Button(description="Map the cycle", button_style="success", icon="map", layout=w.Layout(width="auto"))
out_m = w.Output()
RES = {}

def do_map(_=None):
    with into(out_m):
        P = profiles()
        if P is None:
            print("Measure first (part 3)."); return
        settings()                                    # the settings of the images: white beam, pinhole 1 cm
        lam, wgt = odin.camera_spectrum()
        k1 = max(float(n.split("=")[1]) for n in MATS if n.startswith("graphite x="))
        S0 = tw.sigma_tot(MATS["graphite x=0.00"], lam)
        dS = (tw.sigma_tot(MATS[f"graphite x={k1:.2f}"], lam) - S0) / k1           # per unit of x
        wT = wgt * np.exp(-S0 * CHORD_CM - tw.sigma_tot(MATS["PTFE"], lam) * 0.2
                          - tw.sigma_tot(MATS["aluminium"], lam) * 0.4)
        xs = np.linspace(0, 1.3, 131)
        dmu_x = np.array([-np.log(np.sum(wT * np.exp(-CHORD_CM * x * dS)) / np.sum(wT)) / CHORD_CM for x in xs])
        dmu1 = float(np.interp(1.0, xs, dmu_x))
        e = (P["y"] > 0.03) & (P["y"] < 0.37)
        x_img = np.interp(P["dmu"][:, e].mean(1), dmu_x, xs)
        t = P["times"]
        x_charge = np.where(t <= 30, t / 35, np.maximum(30 / 35 - (t - 30) / 35, 0.27))   # the cycler stops at 0.27
        RES.update(dmu1=dmu1, t=t, x=x_img)
        fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
        m = (P["y"] > -0.3) & (P["y"] < 0.5)
        im = ax[0].pcolormesh(t, P["y"][m], P["dmu"][:, m].T, cmap="viridis", vmin=0, vmax=1.2, shading="nearest")
        ax[0].axhline(0, color="w", lw=0.8); ax[0].axhline(0.4, color="w", lw=0.8)
        ax[0].axvline(30, color="w", ls="--", lw=0.8)
        fig.colorbar(im, ax=ax[0], label="Δμ (cm⁻¹)")
        ax[0].set(xlabel="time of the cycle (h)", ylabel="y (mm)", title="Lithiation, then delithiation (dashed: 30 h)")
        ax[1].plot(t, x_img, "o-", label="x from the images")
        ax[1].plot(t, x_charge, "--", color="0.4", label="x from the charge passed (cycler)")
        ax[1].set(xlabel="time of the cycle (h)", ylabel="mean x in LiₓC₆", title="Lithium in the electrode")
        ax[1].legend(); ax[1].grid(alpha=0.3)
        plt.tight_layout(); plt.show()
        print(f"Δμ for x = 1: {dmu1:.2f} cm⁻¹ in ODIN's white beam hardened by the cell; at the end of the lithiation x = "
              f"{x_img[np.argmin(np.abs(t - 30))]:.2f}; after the whole cycle x = {x_img[-1]:.2f}")

button_m.on_click(do_map)
display(w.VBox([button_m, out_m]))
""")

md(r"""
## 7. Your results

Your score on the questions of the page, and a report to download.
""")

code(r"""
q.choice("Part 1: why can neutrons see the lithium in the electrode, when X-rays hardly can?",
         ["Lithium absorbs neutrons strongly (natural Li: 70 barn at 1.8 Å, mostly its isotope ⁶Li); X-rays interact "
          "with electrons, and lithium has only three.",
          "Neutrons are smaller than X-rays.", "Lithium is magnetic.", "Neutrons are charged and lithium ions too."],
         answer=0, why={1: "Size is not the point: the interaction is.", 2: "It is not.", 3: "Neutrons have no charge."},
         explanation="Neutron contrast depends on the nucleus, not on the number of electrons: light elements (H, Li, "
                     "B) can stand out.", hints=["What do X-rays interact with? And neutrons?"], title="Q1. Why neutrons")
q.choice("Part 5: why divide each image by the image of the pristine cell (0 h)?",
         ["Everything that does not change (casing, steel, electrolyte, graphite) cancels: only the lithium that moved "
          "remains.", "To correct the dark of the camera.", "To make the image brighter.",
          "Because the open beam changes during the cycle."],
         answer=0, why={1: "The dark is subtracted before.", 2: "It is about contrast, not brightness.",
                        3: "The open beam is the same."},
         explanation="Strobl et al. did the same: the attenuation integrates all the materials along the beam; the "
                     "change since t = 0 is the lithium.", hints=["What changes during the cycle?"],
         title="Q2. The reference")
q.choice("Part 5, early in the lithiation (5 to 10 h): where does the lithium enter first?",
         ["Near the separator: the ions arrive through the separator and fill the side of the electrode facing it "
          "first; the far side follows later.", "Near the steel collector.", "Evenly across the electrode.",
          "In the separator."],
         answer=0, why={1: "Δμ is lower there.", 2: "There is a clear gradient.",
                        3: "The separator hardly changes: the ions cross it."},
         explanation="A gradient from the separator side, as observed by Strobl et al.; it fades as the lithiation goes "
                     "on.", hints=["Compare 'near the separator' and 'near the collector'."], title="Q3. Where first")
q.choice("Part 5, at the end of the lithiation (30 h):",
         ["The profile is nearly flat: the lithium has reached the whole thickness at this slow rate (C/35).",
          "All the lithium is still near the separator.", "The electrode is empty.", "The lithium is in the separator."],
         answer=0, why={1: "Look at the profile at 30 h.", 2: "Δμ is largest at 30 h.", 3: "The separator stays flat."},
         explanation="At C/35 the ions have time to diffuse: the final LiC₆ phase is nearly homogeneous (the paper). "
                     "At a faster rate the gradient would remain: the limit of thick electrodes.",
         hints=["Compare near and far at 30 h."], title="Q4. End of the lithiation")
q.number("Part 6: the mean x in the electrode at the end of the lithiation (30 h):", value=0.86, tol=0.15,
         hints=["Part 6 prints it."], explanation="About 0.86 = 30 h / 35 h: all the charge passed, of which 0.27 is not "
                                                  "in the graphite layers but in the SEI and dead lithium.",
         title="Q5. Full?")
q.number("Part 6: the mean x left after the whole cycle (55 h):", value=0.27, tol=0.1,
         hints=["Part 6 prints it."],
         explanation="About 0.27: lithium trapped for good (solid electrolyte interphase, dead lithium), about "
                     "0.27 × 372 = 100 mAh/g of irreversible capacity, as in the paper.", title="Q6. Lost lithium")
q.choice("Where does the lithium that stays after the cycle sit?",
         ["Mostly near the separator: where the lithium entered first and where the SEI formed most.",
          "Evenly.", "Near the collector.", "In the lithium metal."],
         answer=0, why={1: "Look at the profile at 55 h.", 2: "It is lowest there.",
                        3: "The change is in the graphite electrode."},
         explanation="The irreversible losses are significantly more pronounced at the separator side (Strobl et al.).",
         hints=["The last profile of part 5."], title="Q7. Where it is lost")
q.choice("**Your report to the team.**",
         ["At C/35 the lithium reaches the whole 0.4 mm electrode (entering from the separator side, homogeneous at the "
          "end); about 0.27 of LiC₆ (100 mAh/g) is lost in the first cycle, mostly near the separator. Faster charging "
          "of thick electrodes must be tested: the gradient would grow.",
          "Thick electrodes cannot be filled.", "No lithium is lost.", "The lithium goes into the separator."],
         answer=0, why={1: "At C/35 they are filled.", 2: "Q6.", 3: "The separator stays unchanged."},
         explanation="The conclusions of Strobl et al. (2025).", hints=["Q3 to Q7 together."], title="Q8. The report")
q.report()
""")

md(r"""
## 8. Submit your work

When you are done, tell what you thought of the exercise and submit your work.
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/battery_operando", "bsc", quiz=q)
""")

distribute(cells, [
    ("display(w.VBox([x_s, view_x, txt_x]))", [1]),
    ("display(w.VBox([button_p, t_i, view_p, txt_p]))", [2, 3, 4]),
    ("display(w.VBox([button_m, out_m]))", [5, 6, 7]),
])
nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_battery.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
