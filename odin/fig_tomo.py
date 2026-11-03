"""Figure: tomography of the iron plate with the twin (hybrid mode, 60 projections of 10 s, 0–177°).
Data: McStas_runs/twin/odin/validation/tomo/{tomo,rot30}.npz (written by the tomography test)."""
import os
import odin_paths
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

R = odin_paths.RUN_ROOT + "/validation/tomo/"
d = np.load(R + "tomo.npz")
xs, ang = d["xs"], d["ang"]
ext = (xs[0] - 0.125, xs[-1] + 0.125, xs[0] - 0.125, xs[-1] + 0.125)
fig, ax = plt.subplots(2, 3, figsize=(15, 9.2))

a = ax[0, 0]
im = a.imshow(d["sino"][0], aspect="auto", origin="lower", extent=(ext[0], ext[1], ang[0] - 1.5, ang[-1] + 1.5), cmap="gray_r")
a.set(xlabel="x (mm)", ylabel="stage angle (°)", title="Sinogram (white band 1–9 Å)")
fig.colorbar(im, ax=a, label="p = −ln T")

titles = ("white band 1–9 Å", "3.6–4.0 Å\n(below the Fe 110 edge)", "4.15–5.0 Å\n(above the edge)")
expected = ("1.01–1.03", "1.602", "0.620")
X, Z = np.meshgrid(xs, xs)
for i, (a, t, exp_) in enumerate(zip((ax[0, 1], ax[0, 2], ax[1, 0]), titles, expected)):
    rec = d[f"rec{i}"]
    im = a.imshow(rec, origin="lower", extent=ext, cmap="gray", vmin=-0.1, vmax=1.9 if i == 1 else 1.2)
    a.add_patch(Rectangle((-5, -2.5), 10, 5, fill=False, ec="y", ls=":", lw=1))
    a.add_patch(Rectangle((-3.5, -1.5), 7, 3, fill=False, ec="tab:red", lw=0.8))
    m = rec[(abs(X) < 3.5) & (abs(Z) < 1.5)].mean()
    a.set(xlabel="x (mm)", ylabel="z (mm)", title=f"Reconstructed slice, {t}")
    a.text(0.5, 0.06, f"μ (red frame) = {m:.3f} cm⁻¹\nexpected {exp_}", ha="center", color="w", fontsize=8.5,
           transform=a.transAxes, bbox=dict(fc="k", alpha=0.6, lw=0))
    fig.colorbar(im, ax=a, label="μ (cm⁻¹)")

a = ax[1, 1]
for i, t in enumerate(titles):
    a.plot(xs, d[f"rec{i}"][abs(xs) < 1].mean(0), label=t.replace("\n", " "))
a.axvline(-5, color="k", ls=":", lw=0.8); a.axvline(5, color="k", ls=":", lw=0.8)
a.set(xlabel="x (mm)", ylabel="μ (cm⁻¹)", title="Central profile (|z| < 1 mm)\ndotted: true edges of the plate")
a.legend(fontsize=8); a.grid(alpha=0.3)

a = ax[1, 2]
r = np.load(R + "rot30.npz")
a.errorbar(r["xs"], r["pm"], yerr=np.sqrt(r["vm"]), fmt=".", ms=3, lw=0.6, label='"mcstas" mode (full McStas, 2 s)')
a.errorbar(r["xs"], r["ph"], yerr=np.sqrt(r["vh"]), fmt=".", ms=3, lw=0.6, label='"hybrid" mode (10 s)')
a.set(xlabel="x (mm)", ylabel="p = −ln T (1–9 Å)", title="Projection at 30°: both modes")
a.text(0, 0.69, '"mcstas" error bars underestimated\n(simulation statistics)', ha="center", fontsize=8)
a.legend(fontsize=8, loc="upper right"); a.grid(alpha=0.3); a.set_ylim(-0.05, 0.85)
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures", "tomography.png")
plt.savefig(out, dpi=110)
print(out)
