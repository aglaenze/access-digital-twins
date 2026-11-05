"""Easy test case of the LoKI twin: dilute silica spheres (R = 50 Å, 1 % in D₂O), 3 m collimation, 10 min.

R = 50 Å so that everything is in the Q range of the 3 m configuration (rear bank from 0.011 Å⁻¹): the Guinier
region (Q < 0.034 Å⁻¹) and the first two minima of the form factor (0.090 and 0.155 Å⁻¹).

    python easy_case.py            # measurements, reduction with esssans, comparison with the exact curve,
                                   # figure figures/easy_case.png

As in a real SANS experiment, three measurements in the same configuration: empty beam, solvent (D₂O), sample; the
NeXus files are reduced with the official ESS software (esssans), solvent subtracted. The scattering of dilute spheres
is known exactly (loki_samples.silica_spheres), so the measured I(Q) can be checked:
  * absolute level: I(Q) in the Guinier region vs the exact curve of the spheres (resolution hardly matters there);
  * radius: Guinier fit ln I = ln I(0) - (Q Rg)²/3 for Q Rg < 1.3, Rg = √(3/5) R; sphere model of sasmodels.
"""
import os
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):      # Å, ⁻¹ also when the output is redirected (Windows)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loki_samples as ls          # noqa: E402
from virtual_loki import VirtualLoki   # noqa: E402
import loki_reduction as red        # noqa: E402
import loki_analysis as la          # noqa: E402

T = 600.0


def main(plot=True, session="easy_case", mpi=None):
    loki = VirtualLoki(session=session, seed=1, mpi=mpi)
    loki.move(collimation="3m", detector_distance=5.0, heavy_shutter="open", shutter="open")
    files = {}
    for sample, t in (("empty_beam", 60.0), ("d2o", T), ("silica_spheres", T)):
        loki.move(sample=sample)
        files[sample] = loki.count(t, title=sample)
        print(f"{sample}: {os.path.basename(files[sample])}", flush=True)
    iq = red.reduce(files["silica_spheres"], background=files["d2o"], empty_beam=files["empty_beam"],
                    banks=[f"loki_detector_{i}" for i in range(9)])
    data = red.combine(iq, float(red.lnx.read_twin(files["silica_spheres"])["sample_thickness_m"]) * 100)
    _, _, P = ls.silica_spheres()
    R, I0, bg = P["radius"], P["i0"], 0.0          # solvent subtracted: the spheres alone
    for bank, (q, I, dI) in data.items():
        print(f"  {bank:6s}: Q = {q.min():.4f} – {q.max():.3f} Å⁻¹, {len(q)} points")

    # Guinier fit on all banks together, Q Rg < 1.3
    q = np.concatenate([d[0] for d in data.values()]); I = np.concatenate([d[1] for d in data.values()])
    dI = np.concatenate([d[2] for d in data.values()])
    rg_true = np.sqrt(3 / 5) * R
    m = (q * rg_true < 1.3) & (I - bg > 0)
    y = np.log(I[m] - bg); w = ((I[m] - bg) / dI[m]) ** 2
    A = np.column_stack([np.ones(m.sum()), q[m] ** 2])
    cov = np.linalg.inv(A.T @ (A * w[:, None]))
    a, b = cov @ (A.T @ (w * y))
    rg, drg = np.sqrt(-3 * b), 1.5 / np.sqrt(-3 * b) * np.sqrt(cov[1, 1])
    i0, di0 = np.exp(a), np.exp(a) * np.sqrt(cov[0, 0])
    print(f"Guinier ({m.sum()} points, Q < {1.3 / rg_true:.4f} Å⁻¹): Rg = {rg:.1f} ± {drg:.1f} Å (true {rg_true:.1f}),"
          f" R = {rg / np.sqrt(0.6):.1f} Å (true {R:.0f}); I(0) = {i0:.3f} ± {di0:.3f} cm⁻¹ (true {I0 - bg:.3f})")
    # level in the Guinier region: measured / exact
    exact = ls.silica_spheres(q=q[m])[1] - P["background"]
    ratio = np.sum(I[m] / dI[m] ** 2) / np.sum(exact / dI[m] ** 2)
    print(f"mean measured / exact in the Guinier region: {ratio:.3f}")
    o = np.argsort(q)
    fit = la.sphere_fit(q[o], I[o], dI[o], radius0=rg / np.sqrt(0.6))
    print(f"sphere model (sasmodels): R = {fit['radius']:.1f} ± {fit['dradius']:.1f} Å (true {R:.0f}), "
          f"φ = {100 * fit['phi']:.3f} ± {100 * fit['dphi']:.3f} % (true {100 * P['phi']:g}), χ²/n = {fit['chi2']:.1f}")
    if plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 5.5))
        qq, II, _ = ls.silica_spheres()
        ax.loglog(qq, II - P["background"], "k-", lw=1, label="exact dΣ/dΩ of the spheres (no resolution)")
        for (bank, (qb, Ib, dIb)), c in zip(data.items(), ("tab:blue", "tab:green", "tab:red")):
            ax.errorbar(qb, Ib, dIb, fmt="o", ms=3, color=c, lw=0.8, label=f"{bank} bank")
        ax.set_xlim(3e-3, 0.6); ax.set_ylim(1e-3, 10)
        ax.set_xlabel("Q [Å⁻¹]"); ax.set_ylabel("dΣ/dΩ [cm⁻¹ sr⁻¹]")
        ax.set_title(f"Virtual LoKI + esssans: silica spheres R = {R:.0f} Å in D₂O, minus D₂O, {T / 60:.0f} min")
        ax.legend(); ax.grid(alpha=0.3, which="both")
        os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
        fig.savefig(os.path.join(HERE, "figures", "easy_case.png"), dpi=110, bbox_inches="tight")
    return dict(rg=rg, drg=drg, rg_true=rg_true, i0=i0, di0=di0, i0_true=I0 - bg, ratio=ratio, radius=fit["radius"],
                phi=fit["phi"])


if __name__ == "__main__":
    main()
