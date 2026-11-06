"""Generates twin/Sample_builder.ipynb: the sample builder of the free beamtime (Voilà page).

    python gen_sample_builder.py
    voila Sample_builder.ipynb

The student designs a sample (ODIN: blocks of crystalline materials; LoKI: particles in a H2O/D2O solvent), sees it,
and saves it in the samples folder of the proposal; it is then on the sample changer of NICOS
(move(sample_holder, '<name>')), and simulated by McStas on its first count (a few minutes, then cached).
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# Sample builder

For your **free beamtime**: design your own sample, look at it, and put it on the sample changer of the instrument.
As at ESS, where the sample is declared with the proposal, the sample is saved with your proposal: in NICOS it is then
mounted with `move(sample_holder, 'its_name')`, and `sample_info()` describes it. Its first measurement starts a
McStas simulation (a few minutes), the next ones are fast.
""")

code(r"""
import sys, os, datetime, warnings
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as w
from IPython.display import display, clear_output
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("loki"))
import sample_library as sl

ROOT = os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin")).replace(os.sep, "/")
instr = w.ToggleButtons(options=[("ODIN (imaging)", "odin"), ("LoKI (small-angle scattering)", "loki")],
                        description="Instrument")
proposal = w.Text(value="", placeholder="e.g. 1234", description="Proposal")
name = w.Text(value="", placeholder="e.g. my_steel_wedge", description="Short name")
title = w.Text(value="", placeholder="e.g. Steel wedge with a copper insert", description="Title",
               layout=w.Layout(width="520px"))
description = w.Textarea(value="", placeholder="what it is, why you made it", description="Description",
                         layout=w.Layout(width="520px", height="60px"))
display(w.VBox([instr, proposal, name, title, description]))
""")

md(r"""
## ODIN: blocks of material

Up to four blocks, each of one crystalline material (NCrystal), side by side or one behind the other (they must not
overlap). x is horizontal, y vertical (mm, from the center of the beam), z along the beam (to put one block behind
another); width, height and thickness are along x, y and z. The camera sees 14 mm × 14 mm.
""")

code(r"""
MATS = list(sl.ODIN_MATERIALS.items())
rows = []
for k in range(4):
    use = w.Checkbox(value=(k == 0), description=f"block {k + 1}", indent=False, layout=w.Layout(width="80px"))
    mat = w.Dropdown(options=MATS, value=MATS[0][1], layout=w.Layout(width="190px"))
    vals = [w.FloatText(value=v, description=d, layout=w.Layout(width="130px"), style={"description_width": "60px"})
            for d, v in (("x [mm]", 0.0), ("y [mm]", 0.0), ("z [mm]", 0.0), ("width", 10.0), ("height", 10.0),
                         ("thickness", 5.0))]
    rows.append((use, mat, vals))
    for v in vals:
        v.layout.width = "118px"
    display(w.HBox([use, mat] + vals))

def odin_spec():
    vols = [dict(material=mat.value, center_mm=[vals[0].value, vals[1].value, vals[2].value],
                 size_mm=[vals[3].value, vals[4].value, vals[5].value]) for use, mat, vals in rows if use.value]
    return dict(name=title.value or name.value, description=description.value, volumes=vols)
""")

md(r"""
## LoKI: particles in a solvent

Particles of one shape (models of SasView) dispersed in water, dilute (no interaction between them). The solvent is a
mixture of light water (H2O) and heavy water (D2O): changing it changes the **contrast** between particles and solvent,
and the incoherent background (H2O scatters much more).
""")

code(r"""
model = w.Dropdown(options=[("solvent alone", "none"), ("spheres", "sphere"), ("cylinders", "cylinder"),
                            ("core-shell spheres", "core_shell_sphere")], value="sphere", description="Particles")
particle = w.Dropdown(options=list(sl.SLD), value="silica", description="Material")
radius = w.FloatText(value=50.0, description="radius [Å]")
length = w.FloatText(value=400.0, description="length [Å]")
shell = w.FloatText(value=20.0, description="shell [Å]")
phi = w.FloatSlider(value=0.01, min=0.001, max=0.1, step=0.001, readout_format=".3f", description="vol. fraction")
d2o = w.FloatSlider(value=1.0, min=0.0, max=1.0, step=0.05, description="D2O fraction")
thick = w.FloatSlider(value=1.0, min=0.1, max=5.0, step=0.1, description="cell [mm]")
display(w.VBox([model, particle, radius, length, shell, phi, d2o, thick]))

def loki_spec():
    spec = dict(name=title.value or name.value, description=description.value, model=model.value,
                solvent=dict(d2o_fraction=round(d2o.value, 3)), thickness_mm=round(thick.value, 2))
    if model.value != "none":
        p = {"radius": radius.value}
        if model.value == "cylinder":
            p["length"] = length.value
        if model.value == "core_shell_sphere":
            p["thickness"] = shell.value
        spec.update(parameters=p, particle=particle.value, volume_fraction=round(phi.value, 4))
    return spec
""")

md(r"""
## Look at it, then save it
""")

code(r"""
out = w.Output()
b_view = w.Button(description="Show my sample", icon="eye")
b_save = w.Button(description="Save it with my proposal", icon="save", button_style="success")

def spec_now():
    return odin_spec() if instr.value == "odin" else loki_spec()

def view(_):
    out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    with out:
        spec = spec_now()
        errors = sl.validate(instr.value, spec)
        if errors:
            print("To fix:", *errors, sep="\n  ")
            return
        print(sl.describe(instr.value, spec))
        sl.draw(instr.value, spec, fig=plt.figure(figsize=(10, 4)))
        sl.show()
        if instr.value == "loki":
            q, I, truth = sl.loki_cross_section(spec)
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.loglog(q, I, "k-")
            ax.set(xlim=(3e-3, 0.6), ylim=(max(I.min() / 2, 1e-4), I.max() * 2), xlabel="Q [1/Å]",
                   ylabel="dΣ/dΩ [1/cm]", title="what your sample scatters (exact, no instrument)")
            ax.grid(alpha=0.3, which="both"); plt.show()

def save(_):
    out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
    with out:
        if not proposal.value.strip().isdigit():
            print("Give your proposal number (the one entered in NICOS, Experiment panel)."); return
        folder = f"{ROOT}/data/{instr.value}/{datetime.date.today().year}/{proposal.value.strip()}/raw"
        try:
            path = sl.save(instr.value, spec_now(), folder, name.value.strip())
        except ValueError as e:
            print("Not saved:", e); return
        print(f"Saved: {path}")
        print(f"In NICOS ({instr.value.upper()}):   move(sample_holder, '{name.value.strip()}')   then   sample_info()")

b_view.on_click(view); b_save.on_click(save)
display(w.HBox([b_view, b_save]), out)
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, os.path.join(HERE, "Sample_builder.ipynb"))
print("written Sample_builder.ipynb")
