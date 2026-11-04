"""Diagram of the ODIN digital twin chain (for the README): who does what, and what flows between the bricks."""
import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(15, 8.6))
ax.set_xlim(0, 15); ax.set_ylim(0, 8.6); ax.axis("off")

C = dict(ui="#dbe9f6", ctl="#fde2c8", phys="#d9f0d3", data="#f2f2f2", red="#e8dcf2")


def box(x, y, w, h, title, text, color, fs=8.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12", fc=color, ec="0.3", lw=1))
    ax.text(x + w / 2, y + h - 0.2, title, ha="center", va="top", fontsize=10, fontweight="bold")
    ax.text(x + w / 2, y + h - 0.58, text, ha="center", va="top", fontsize=fs, linespacing=1.35)


def arrow(x1, y1, x2, y2, txt="", dx=0, dy=0.13, ha="center", style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14, lw=1.2, color="0.25", ls=ls))
    if txt:
        ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, txt, ha=ha, va="bottom", fontsize=8, color="0.15", style="italic")


# Top row: what the user sees
ax.text(0.2, 8.35, "What the user sees", fontsize=11, fontweight="bold", color="0.35")
box(0.2, 6.55, 3.6, 1.55, "Console (provisional)", "odin_console.py\nmove(stage_x, 0.5)\ncount(10) · scan(...)\n→ later: NICOS", C["ui"])
box(4.3, 6.55, 3.6, 1.55, "Student page (Voilà)", "ODIN_virtual.ipynb\nbuttons, logbook,\ntransmission", C["ui"])
box(11.2, 6.55, 3.6, 1.55, "Analysis (Master)", "Jupyter notebook\nodin_reduction, odin_tomo\n(code visible)", C["ui"])

# Middle row: control and files
ax.text(0.2, 5.75, "Instrument control and data", fontsize=11, fontweight="bold", color="0.35")
box(0.2, 3.7, 3.6, 1.8, "Server", 'odin_server.py\nHTTP + JSON, local\none measurement at a time\n("instrument busy")', C["ctl"])
box(4.3, 3.7, 3.6, 1.8, "Virtual instrument", "odin_virtual.py\ndevices: choppers, shutter,\npinhole, diffuser, stages\ncount → counts · log.jsonl", C["ctl"])
box(8.4, 3.7, 2.5, 1.8, "NeXus file", "odin_NNNNNN.nxs\nESS format\n(template: real\nODIN file)", C["data"])
box(11.2, 3.7, 3.6, 1.8, "Official reduction", "essimaging\n(OdinBraggEdgeWorkflow)\ntime → λ from the choppers\nT = (E−N)/(O−N) / charge", C["red"])

# Bottom row: physics
ax.text(0.2, 2.95, "Physics engine (invisible)", fontsize=11, fontweight="bold", color="0.35")
box(0.2, 0.55, 4.3, 2.0, "McStas upstream part", "ESS source → guides → choppers\n(official ODIN_instr model)\ncomputed ONCE per chopper mode\n→ MCPL at the guide exit\n(10–40 min, 1e8–1e10 neutrons)", C["phys"])
box(5.0, 0.55, 4.6, 2.0, "Downstream part",
    '"hybrid" mode (default)\nopen beam = all upstream neutrons\n× acceptance a(λ) × profile f(x, y)\n'
    '+ Beer-Lambert (NCrystal) for the sample\n"mcstas" mode: full McStas (short counts)', C["phys"])
box(10.1, 0.55, 4.7, 2.0, "Virtual detector",
    "Timepix3 of the template (14 mm)\nefficiency ε(λ), blur, Poisson,\nbackground 0.05 count/s/mm²\nproton charge of each pulse\n(71.4 µC at 2 MW)", C["phys"])

# Arrows
arrow(2.0, 6.55, 2.0, 5.5, "orders", dx=0.1, ha="left", dy=0.0)
arrow(3.8, 4.6, 4.3, 4.6)
arrow(6.1, 6.55, 6.1, 5.5, "same\nprocess", dx=0.1, ha="left", dy=-0.05)
arrow(7.9, 4.6, 8.4, 4.6, "writes", dy=0.05)
arrow(10.9, 4.6, 11.2, 4.6)
arrow(13.0, 5.5, 13.0, 6.55, "transmission,\nimages, slices", dx=0.1, ha="left", dy=-0.05)
arrow(6.1, 3.7, 7.3, 2.55, "device state", dx=0.25, ha="left", dy=-0.05)
arrow(4.5, 1.55, 5.0, 1.55)
ax.text(4.75, 0.12, "MCPL →", ha="center", va="bottom", fontsize=8, style="italic", color="0.15")
arrow(9.6, 1.55, 10.1, 1.55)
ax.text(9.85, 0.12, "neutrons (x, y, t, λ, weight) →", ha="center", va="bottom", fontsize=8, style="italic", color="0.15")
arrow(12.4, 2.55, 9.9, 3.7, "counts (pixel, time)", dx=0.55, ha="left", dy=-0.15)
arrow(7.9, 6.65, 11.2, 5.1, "", style="-|>", ls="--")
ax.text(9.3, 6.0, "reads the files", fontsize=8, style="italic", color="0.15", rotation=-21)

plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures", "twin_chain.png")
plt.savefig(out, dpi=115)
print(out)
