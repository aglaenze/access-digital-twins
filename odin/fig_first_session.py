"""Figure: 5 mm iron plate, reduced by essimaging, in "mcstas" mode (10 s) and in "hybrid" mode (60 s).
Data: McStas_runs/twin/odin/validation/{mcstas_10s,hybrid_60s}/red.npz (written by the session tests)."""
import os
import odin_paths
import numpy as np
import matplotlib.pyplot as plt

R = odin_paths.RUN_ROOT + "/validation/"
cases = [("mcstas_10s", '"mcstas" mode, 10 s', ((2.0, "47"), (3.4, "5.9"), (6.0, "1.3"), (8.0, "1.1"))),
         ("hybrid_60s", '"hybrid" mode, 60 s', ((2.0, "0.76"), (3.4, "1.38"), (6.0, "1.04"), (8.0, "0.72")))]
fig, ax = plt.subplots(2, 2, figsize=(13, 9), gridspec_kw=dict(width_ratios=[1, 1.7]))
for row, (folder, label, chi2) in enumerate(cases):
    d = np.load(R + folder + "/red.npz")
    im = ax[row, 0].imshow(d["img"], origin="lower", extent=(-7.05, 7.05, -7.05, 7.05), vmin=0, vmax=1.2, cmap="gray")
    ax[row, 0].add_patch(plt.Rectangle((-3, -3), 6, 6, fill=False, ec="tab:red", lw=1.5))
    ax[row, 0].set(xlabel="x (mm)", ylabel="y (mm)", title=f"Transmission, all λ — {label}")
    fig.colorbar(im, ax=ax[row, 0], label="T", shrink=0.85)
    a = ax[row, 1]
    ok = np.isfinite(d["T"])
    a.errorbar(d["lc"][ok], d["T"][ok], yerr=d["dT"][ok], fmt=".", ms=3, lw=0.6, label=f"twin ({label}), reduced by essimaging")
    a.plot(d["lc"], d["th"], "k-", lw=1, label="exp(−Σ(λ)·0.5 cm), NCrystal")
    a.axvline(2 * 2.8665 / np.sqrt(2), color="tab:green", ls="--", lw=0.8)
    a.text(2 * 2.8665 / np.sqrt(2) - 0.08, 0.25, "2 d₁₁₀ = 4.05 Å", color="tab:green", ha="right")
    for x, txt in chi2:
        a.text(x, 1.03, f"χ²/n = {txt}", ha="center", fontsize=9, color="tab:red")
    for x in (3, 5, 7):
        a.axvline(x, color="tab:red", lw=0.4, ls=":")
    a.text(8.95, 0.94, "χ²/n per 2 Å band (≈ 1: correct error bars)", ha="right", fontsize=8, color="tab:red")
    a.set(xlabel="λ (Å)", ylabel="T", ylim=(0, 1.1), xlim=(1, 9), title="Transmission at the center (red 6 × 6 mm square)")
    a.legend(loc="lower right", fontsize=9)
    a.grid(alpha=0.3)
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures", "first_session.png")
plt.savefig(out, dpi=120)
print(out)
