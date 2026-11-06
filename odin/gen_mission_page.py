"""Generates twin/odin/ODIN_mission.ipynb: the game page of the ODIN twin (Voilà).

    python gen_mission_page.py
    voila ODIN_mission.ipynb            # session name: variable TWIN_SESSION (one per student or group)

Mission 1, "Unknown metals": identify three plates within a beamtime budget (score).
Mission 2, "Something is wrong": the instrument has a hidden fault; find it from the data.
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# ODIN beamtime challenge

You have been awarded beamtime on **ODIN**, the imaging instrument of the European Spallation Source (here its
digital twin: a McStas simulation of the instrument, files in the ESS NeXus format, official ESS reduction).

**Mission 1, "Unknown metals"**: you are the neutron expert of a metal-recycling company. Three plates have arrived
with their labels lost (only A, B, C are left); sent to the wrong furnace, a plate ruins a whole batch of alloy.
Chemical tests would damage them: identify each metal and measure its lattice parameter with the Bragg edges of
its transmission spectrum, which neutrons see through the whole plate. Beamtime is precious: you have a
**limited budget**, and unused beamtime gives bonus points.

**Mission 2, "Something is wrong"**: you are the instrument scientist on duty. A user complains that their data
look strange: the instrument has a hidden fault. Find it from your data before the next user arrives.
""")

code(r"""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
import numpy as np, scipp as sc, matplotlib.pyplot as plt, ipywidgets as w
from IPython.display import display, clear_output, Markdown
sys.path.insert(0, os.path.abspath("."))
import odin_games as games, odin_reduction as red, odin_viz as viz
from odin_virtual import LAM_RANGE, FAULTS

SESSION = os.environ.get("TWIN_SESSION", "mission_group1")
mission = games.MetalMission(SESSION, budget_s=300)
odin = mission.instrument()
display(Markdown(mission.brief()))
""")

md(r"""
## 1. Operate the instrument

The plates are 10 × 10 × 5 mm and centered when the stage is at 0 mm; move the stage to 500 mm to measure the open beam.
Each time you press **Count**, a replay of the detector shows the neutrons arriving, as on a real live display.
""")

code(r"""
CHOP = [("WFM, δ = 0.30 m", ("wfm", 0.30)), ("WFM, δ = 0.10 m (sharper, less flux)", ("wfm", 0.10)),
        ("WFM, δ = 0.45 m (more flux, less sharp)", ("wfm", 0.45)), ("natural (much more flux, poor resolution)", ("natural", 0.30))]
chop = w.Dropdown(options=CHOP, value=("wfm", 0.30), description="Choppers", layout=w.Layout(width="440px"))
shut = w.ToggleButtons(options=["closed", "open"], value="closed", description="Shutter")
smp = w.Dropdown(options=list(games.CODES), value=games.CODES[0], description="Sample")
stage = w.Dropdown(options=[("in the beam (0 mm)", 0.0), ("out of the beam (500 mm)", 0.5)], value=0.0, description="Stage")
ttime = w.Dropdown(options=[5, 10, 20, 30, 60, 90], value=30, description="Time (s)")
title = w.Text(placeholder="e.g. open beam", description="Title")
budget = w.FloatProgress(min=0, max=mission.data["budget_s"], description="Beamtime", bar_style="success")
budget_txt = w.Label()
button = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
diag_button = w.Button(description="Show chopper diagram", icon="clock", layout=w.Layout(width="auto"))
out, diag_out = w.Output(), w.Output()

def refresh_budget():
    used = odin.beam_used()
    budget.value = used
    budget.bar_style = "success" if used < 0.7 * budget.max else ("warning" if used < budget.max else "danger")
    budget_txt.value = f"{used:.0f} s used of {budget.max:.0f} s (dark runs are free)"

def do_count(_):
    button.disabled = True
    with out:
        clear_output()
        try:
            mode, delta = chop.value
            odin.move(choppers=mode, wfm_delta=delta, shutter=shut.value, sample=smp.value, stage_x=stage.value)
            print("Measuring...")
            f = odin.count(ttime.value, title=title.value or f"{smp.value} {shut.value}")
            clear_output()
            print(f"File written: {os.path.basename(f)}")
            viz.show_live(f, n_frames=16)
        except Exception as e:
            print("Refused:", e)
    refresh_budget(); refresh_files()
    button.disabled = False

def show_diagram(_):
    with diag_out:
        clear_output()
        mode, delta = chop.value
        fig, ax = plt.subplots(figsize=(8, 5)); viz.chopper_diagram(mode, delta, ax=ax, neutrons=30_000); plt.show()

button.on_click(do_count); diag_button.on_click(show_diagram)
refresh_budget()
display(w.VBox([chop, shut, smp, stage, ttime, title, w.HBox([budget, budget_txt]), w.HBox([button, diag_button]), out, diag_out]))
""")

md(r"""
## 2. Reduce and measure the Bragg edges

Choose a sample run, the open beam and the dark run measured **with the same chopper setting**. Move the cursor onto
a Bragg edge (where the transmission jumps up) to read its wavelength. The first edge is at λ = 2 d of the planes with
the largest spacing: d₁₁₀ = a/√2 for body-centered cubic (bcc) metals, d₁₁₁ = a/√3 for face-centered cubic (fcc) ones.
""")

code(r"""
def runs():
    return [json.loads(l)["details"] for l in open(odin.log_file, encoding="utf-8") if '"count"' in l] \
        if os.path.isfile(odin.log_file) else []

pick_E = w.Dropdown(description="Sample run", layout=w.Layout(width="460px"))
pick_O = w.Dropdown(description="Open beam", layout=w.Layout(width="460px"))
pick_N = w.Dropdown(description="Dark run", layout=w.Layout(width="460px"))

def refresh_files():
    opts = [(f"{r['file']}: {r['title']} ({r['state']['choppers']}, {r['t']:g} s)", f"{odin.folder}/{r['file']}") for r in runs()]
    for d in (pick_E, pick_O, pick_N):
        d.options = opts

cursor = w.FloatSlider(min=2.0, max=5.5, step=0.005, value=4.0, description="λ cursor (Å)", readout_format=".3f",
                       layout=w.Layout(width="520px"))
structure = w.ToggleButtons(options=["bcc", "fcc"], description="Structure")
a_txt = w.HTML()
red_button = w.Button(description="Compute transmission", button_style="success", icon="calculator", layout=w.Layout(width="auto"))
red_out = w.Output()
SPEC = {}

def plot_spectrum():
    red_out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    with red_out:
        if not SPEC:
            return
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.errorbar(SPEC["lc"], SPEC["T"], yerr=SPEC["dT"], fmt=".", ms=3, lw=0.6)
        ax.axvline(cursor.value, color="tab:red", lw=1)
        ax.set(xlabel="λ (Å)", ylabel="T", title=SPEC["title"]); ax.grid(alpha=0.3)
        plt.show()
    f = np.sqrt(2) / 2 if structure.value == "bcc" else np.sqrt(3) / 2
    a_txt.value = f"First edge at the cursor: λ = {cursor.value:.3f} Å → a = {cursor.value * f:.4f} Å ({structure.value})"

def do_reduce(_):
    with red_out:
        clear_output(); print("Reducing...")
    N = pick_N.value if pick_N.value not in (pick_E.value, pick_O.value) else None
    lam = sc.linspace("wavelength", 2.0, 5.5, 176, unit="angstrom")
    r = red.reduce(pick_E.value, pick_O.value, N, lam=lam)
    s = r["spectrum"]
    SPEC.update(lc=sc.midpoints(lam).values, T=s.values, dT=np.sqrt(s.variances), title=os.path.basename(pick_E.value))
    plot_spectrum()

red_button.on_click(do_reduce)
cursor.observe(lambda _: plot_spectrum(), names="value"); structure.observe(lambda _: plot_spectrum(), names="value")
refresh_files()
display(w.VBox([pick_E, pick_O, pick_N, red_button, cursor, structure, a_txt, red_out]))
""")

md(r"""
## 3. Submit your answers

One submission counts for the score (you may resubmit, all attempts are recorded): 100 points per correct metal,
+50 if your lattice parameter is within 0.5 %, + 1 point per 5 s of beamtime left (if at least one metal
is right).
""")

code(r"""
METAL_OPTS = ["?"] + list(games.METALS)
ans = {c: (w.Dropdown(options=METAL_OPTS, description=c), w.FloatText(value=0.0, description="a (Å)")) for c in games.CODES}
sub_button = w.Button(description="Submit", button_style="warning", icon="check", layout=w.Layout(width="auto"))
sub_out = w.Output()

def do_submit(_):
    answers = {c: (m.value if m.value != "?" else None, a.value or None) for c, (m, a) in ans.items()}
    score, rows, bonus = mission.submit(answers, odin.beam_used())
    with sub_out:
        clear_output()
        if mission.data.get("revealed"):
            print("You have shown the answers: this submission is not scored (your earlier score stays).")
        for r in rows:
            print(f"{r['sample']}: {r['answer'] or '?':3s} {'correct' if r['correct'] else 'wrong'}"
                  f"{' + lattice parameter within 0.5 %' if r['a_within_0_5_percent'] else ''}  -> {r['points']} points")
        print(f"beamtime bonus: {bonus} points\nSCORE: {score}")
        checks, badges = games.review_log(odin.log_file, budget_s=mission.data["budget_s"])
        print("\nLogbook review:")
        for ok, msg in checks:
            print(("  OK   " if ok else "  !!   ") + msg)
        print("Badges:", ", ".join(badges) if badges else "none yet")
        wrong = [r for r in rows if not r["correct"]]
        if wrong:
            print("\nTo check your wrong answers against your data:")
            for r in wrong:
                print(f"  {r['sample']}: " + (games.explain_metal(r["answer"]) if r["answer"] else "no answer yet.")
                      + " Do your measured edges match?")
            show_button.layout.display = ""

def do_show(_):
    secret = mission.give_up()
    with sub_out:
        print("\nThe answers:")
        for c in games.CODES:
            print(f"  {c}: {games.explain_metal(secret[c])}")
        print("Two metals with almost the same first edge (Fe and Ni, Nb and Al) are told apart by their second edge.")
    show_button.layout.display = "none"

show_button = w.Button(description="Show the answers (ends the scoring)", icon="eye", layout=w.Layout(width="auto", display="none"))
sub_button.on_click(do_submit)
show_button.on_click(do_show)
display(w.VBox([w.HBox([m, a]) for m, a in ans.values()] + [w.HBox([sub_button, show_button]), sub_out]))
""")

md(r"""
## 4. Mission 2: something is wrong

This is a different instrument session, with a hidden fault. Measure (dark run, open beam, sample), look at the live
replay and at your reduced data, then name the fault.
""")

code(r"""
trouble = games.Troubleshooting(SESSION + "_fault")
odin2 = trouble.instrument()
shut2 = w.ToggleButtons(options=["closed", "open"], value="open", description="Shutter")
stage2 = w.Dropdown(options=[("in the beam (0 mm)", 0.0), ("out of the beam (500 mm)", 0.5)], value=0.5, description="Stage")
b2 = w.Button(description="Count 10 s", button_style="primary", icon="play", layout=w.Layout(width="auto"))
out2 = w.Output()

def count2(_):
    with out2:
        clear_output()
        odin2.move(shutter=shut2.value, stage_x=stage2.value, sample="iron_plate")
        f = odin2.count(10, title=f"{shut2.value}, stage {stage2.value * 1000:.0f} mm")
        viz.show_live(f, n_frames=10)

b2.on_click(count2)
guess = w.Dropdown(options=[(f"{k}: {v}", k) for k, v in FAULTS.items()], description="Fault", layout=w.Layout(width="720px"))
gb = w.Button(description="This is the fault!", button_style="warning", layout=w.Layout(width="auto"))
gout = w.Output()

def do_guess(_):
    with gout:
        clear_output()
        if trouble.guess(guess.value):
            print("Well diagnosed! It shows as " + games.FAULT_SIGNS[guess.value] + ".")
            reveal2.layout.display = "none"
        else:
            print("No. If it were this fault you would see " + games.FAULT_SIGNS[guess.value] + ". Do you? Compare a "
                  "dark run, an open beam and the sample, and look at the images and at the numbers of counts.")
            reveal2.layout.display = ""

def do_reveal2(_):
    with gout:
        f = trouble.reveal()
        print(f"\nThe fault was: {FAULTS[f]}. It shows as {games.FAULT_SIGNS[f]}.")
    reveal2.layout.display = "none"

reveal2 = w.Button(description="Show the answer", icon="eye", layout=w.Layout(width="auto", display="none"))
gb.on_click(do_guess)
reveal2.on_click(do_reveal2)
display(w.VBox([shut2, stage2, b2, out2, guess, w.HBox([gb, reveal2]), gout]))
""")

md(r"""
## Submit your work

When you are done, submit: the file for your teacher is made from your answers and your measurements.
""")

code(r"""
import submit
_ = submit.Submit("odin/exercises/unknown_metals", "bsc")
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out_nb = os.path.join(HERE, "ODIN_mission.ipynb")
nbf.write(nb, out_nb)
print("written:", out_nb)
