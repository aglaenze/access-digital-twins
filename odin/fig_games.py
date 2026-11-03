"""Figures of the games and visualisations (README): live detector replay, chopper diagrams, mission spectra,
progressive tomography. Data: sessions game_test (mission played 2026-11-03) and validation/tomo."""
import json
import os
import numpy as np
import matplotlib.pyplot as plt
import scipp as sc

import odin_paths
import odin_games as g
import odin_reduction as red
import odin_viz as viz

R = odin_paths.RUN_ROOT
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
S = f"{R}/game_test"
log = [json.loads(l)["details"] for l in open(f"{S}/log.jsonl", encoding="utf-8") if '"count"' in l]
files = {c["title"]: f"{S}/{c['file']}" for c in log}
secret = g.MetalMission("game_test").reveal()

# 1. live detector replay (4 moments)
fr = viz.live_frames(files["sample_C"], n_frames=24)
fig, ax = plt.subplots(2, 4, figsize=(16, 7.2), gridspec_kw=dict(height_ratios=[1.25, 1]))
c = 0.5 * (fr["toa_edges"][1:] + fr["toa_edges"][:-1])
for j, k in enumerate((0, 3, 9, 23)):
    a = ax[0, j]
    a.imshow(fr["images"][k], origin="lower", extent=fr["extent"], cmap="inferno", vmin=0, vmax=fr["images"][-1].max())
    a.set(title=f"after {fr['times'][k]:.1f} s: {fr['images'][k].sum():,.0f} neutrons", xlabel="x (mm)")
    ax[1, j].step(c, fr["toa"][k], where="mid")
    ax[1, j].set(ylim=(0, fr["toa"][-1].max() * 1.05), xlabel="time since last pulse (ms)")
    ax[1, j].grid(alpha=0.3)
ax[0, 0].set_ylabel("y (mm)"); ax[1, 0].set_ylabel("counts")
fig.suptitle("Live detector replay (mystery plate, WFM): the image and the arrival-time spectrum build up")
plt.tight_layout(); fig.savefig(f"{OUT}/live_replay.png", dpi=100); plt.close(fig)

# 2. chopper diagrams
fig, ax = plt.subplots(1, 3, figsize=(21, 6.2))
for a, mode in zip(ax, ("wfm", "natural", "white")):
    viz.chopper_diagram(mode, 0.30, ax=a, neutrons=40_000)
plt.tight_layout(); fig.savefig(f"{OUT}/chopper_diagrams.png", dpi=90); plt.close(fig)

# 3. mission spectra with the expected edges of the true metals (teacher view)
lam = sc.linspace("wavelength", 2.0, 5.5, 176, unit="angstrom")
fig, ax = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
for a, code in zip(ax, g.CODES):
    r = red.reduce(files[code], files["open beam"], files["dark"], lam=lam)
    sp = r["spectrum"]; lc = sc.midpoints(lam).values
    a.errorbar(lc, sp.values, yerr=np.sqrt(sp.variances), fmt=".", ms=3, lw=0.6)
    metal = secret[code]; _, st, aa = g.METALS[metal]
    edges = [2 * aa / np.sqrt(2), aa] if st == "bcc" else [2 * aa / np.sqrt(3), aa]
    for e in edges:
        a.axvline(e, color="tab:red", ls="--", lw=0.8)
    a.set(ylabel="T", title=f"{code} (60 s) — answer for the teacher: {metal} ({st}), first edges {edges[0]:.3f} and {edges[1]:.3f} Å")
    a.grid(alpha=0.3)
ax[-1].set_xlabel("λ (Å)")
plt.tight_layout(); fig.savefig(f"{OUT}/mission_spectra.png", dpi=100); plt.close(fig)

# 4. progressive tomography, sequential vs interleaved order
d = np.load(f"{R}/validation/tomo/tomo.npz")
ext = (d["xs"][0] - 0.125, d["xs"][-1] + 0.125) * 2
fig, ax = plt.subplots(2, 5, figsize=(17, 7.6))
for row, order in enumerate(("sequential", "interleaved")):
    steps, recs = viz.tomo_frames(d["sino"][2], d["ang"], d["xs"], steps=[3, 8, 15, 30, 60], order=order)
    for j, (k, rec) in enumerate(zip(steps, recs)):
        ax[row, j].imshow(rec, origin="lower", extent=ext, cmap="gray", vmin=-0.2, vmax=0.9)
        ax[row, j].set(title=f"{order}: {k} projections", xticks=[], yticks=[])
fig.suptitle("Tomography appearing projection after projection (4.15–5.0 Å): sequential angles (0°, 3°, 6°, ...) "
             "vs interleaved angles (0°, 90°, 45°, 135°, ...)")
plt.tight_layout(h_pad=2.5); fig.savefig(f"{OUT}/tomo_progress.png", dpi=95); plt.close(fig)
print("figures written in", OUT)
