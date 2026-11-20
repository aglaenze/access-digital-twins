"""Cross-validation of samplecraft against McStas Union: the same sample, a parallel monochromatic beam; the
transmission of the neutrons that went through without scattering (McStas) against exp(−Σ Σ_m L_m) (samplecraft,
the scene as exported); also how many scattered neutrons reach the detector (what the path-length model leaves out).

    python -m samplecraft.union_check odin/templates/machined_steel_part.yml C:/runs/union_check --wavelength 3

Run it in the conda environment of McStas (mcrun on the path; no spaces in the output folder). Writes
<out>/comparison.png and prints the agreement: the mean ratio McStas / samplecraft in the sample (with its
statistical error), the χ² per pixel, the fraction of scattered neutrons among those counted behind the sample.
"""
import argparse
import os
import subprocess
import sys

import numpy as np
import yaml

from . import union
from .scene import Scene


def read_psd(path):
    """(I, E, N) of a McStas 2D monitor file (McCode format)."""
    with open(path) as f:
        lines = f.readlines()
    blocks, cur = {}, None
    for ln in lines:
        if ln.startswith("# Data") or ln.startswith("# Errors") or ln.startswith("# Events"):
            cur = ln.split()[1]
            blocks[cur] = []
        elif not ln.startswith("#") and cur is not None and ln.strip():
            blocks[cur].append([float(x) for x in ln.split()])
    return tuple(np.array(blocks[k]) for k in ("Data", "Errors", "Events"))


def load_scene(path):
    with open(path, encoding="utf-8") as f:
        d = yaml.load(f, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    d = d.get("recipe") or d.get("scene") or d
    return Scene.from_dict(d, os.path.dirname(os.path.abspath(path)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("scene")
    ap.add_argument("out")
    ap.add_argument("--wavelength", type=float, default=3.0)
    ap.add_argument("--ncount", type=float, default=2e7)
    ap.add_argument("--mpi", type=int, default=4)
    ap.add_argument("--chunk", type=float, default=1e6, help="neutrons per McStas run")
    ap.add_argument("--bin", type=int, default=5, help="pixels of 20 µm put together (5: 100 µm)")
    a = ap.parse_args(argv)
    scene = load_scene(a.scene)
    name = os.path.splitext(os.path.basename(a.scene))[0]
    out = union.export(scene, a.out, name)
    for r in out["shapes"]:
        print(f"  {r['body']:28s} {r['union']:15s} volume error {r['volume_error']:+.1e}  ({r['how']})")
    instr = os.path.basename(out["instrument"])
    # in runs of a.chunk neutrons (each with its own seed), averaged: Union_master stops a process after 100 "trace
    # errors" (rays lost on surfaces after a scattering, about 1 in 10⁴ here); those rays had scattered already, so
    # they do not touch the transmission of the unscattered neutrons compared here
    n_runs = max(1, int(round(a.ncount / a.chunk)))
    I_u = E2 = I_a = None
    done, lost = 0, 0
    subprocess.run(f"mcrun {instr} -c -y -n 0 -d _compile", shell=True, cwd=a.out, capture_output=True,
                   stdin=subprocess.DEVNULL)
    # large random seeds: McStas streams of small neighboring seeds (1, 2, ...) are correlated (0.94 between the
    # maps of seeds 1 and 2) and over-dispersed (variance 2.3 times the counts)
    seeds = np.random.default_rng(20261120).integers(10 ** 8, 2 * 10 ** 9, n_runs)
    for k_run, seed in enumerate(seeds):
        run = f"run_{a.wavelength:g}A_{a.chunk:.0e}_seed{seed}".replace("+", "")
        if not os.path.isfile(os.path.join(a.out, run, "all.dat")):
            if os.path.isdir(os.path.join(a.out, run)):        # left by a stopped run: McStas will not reuse it
                import shutil
                shutil.rmtree(os.path.join(a.out, run))
            cmd = (f"mcrun {instr} -y -n {a.chunk:.0f} --mpi={a.mpi} --seed={seed} -d {run} "
                   f"lambda={a.wavelength}")
            # the output goes to a file, read line by line: with many grains Union prints a lot (a MemoryError once)
            log = os.path.join(a.out, f"{run}.log")
            with open(log, "w", encoding="utf-8", errors="replace") as f:
                subprocess.run(cmd, shell=True, cwd=a.out, stdout=f, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL)
            with open(log, encoding="utf-8", errors="replace") as f:
                text = f.read()
            lost += text.count("Trace error number")
            if not os.path.isfile(os.path.join(a.out, run, "all.dat")):
                why = "too many trace errors" if "To many errors" in text else f"see {run}.log"
                print(f"  run {k_run + 1} failed ({why}): left out")
                continue
        iu, eu, _ = read_psd(os.path.join(a.out, run, "unscattered.dat"))
        ia, _, _ = read_psd(os.path.join(a.out, run, "all.dat"))
        I_u = iu if I_u is None else I_u + iu
        E2 = eu ** 2 if E2 is None else E2 + eu ** 2
        I_a = ia if I_a is None else I_a + ia
        done += 1
    if not done:
        sys.exit("McStas runs failed")
    I_u, E_u, I_a = I_u / done, np.sqrt(E2) / done, I_a / done
    print(f"  {done} runs of {a.chunk:.0e} neutrons; rays lost by Union after a scattering: {lost} "
          f"({lost / (done * a.chunk):.1e} of all)")
    b = out["beam"]
    # the open beam: the source is uniform; its level from the counts and the area (no sample there)
    ny, nx = I_u.shape
    k = a.bin
    nyb, nxb = ny // k, nx // k
    binned = lambda A: A[:nyb * k, :nxb * k].reshape(nyb, k, nxb, k).sum(axis=(1, 3))
    Iu, Eu, Ia = binned(I_u), np.sqrt(binned(E_u ** 2)), binned(I_a)
    # samplecraft: transmission of the scene as exported, averaged over each binned pixel (4 × 4 rays in each)
    px_x, px_y = b["xwidth_mm"] / nx * k, b["yheight_mm"] / ny * k
    x0 = b["center_mm"][0] - b["xwidth_mm"] / 2
    y0 = b["center_mm"][1] - b["yheight_mm"] / 2
    sub = (np.arange(4) + 0.5) / 4
    xs = x0 + (np.arange(nxb)[:, None] + sub[None, :]).ravel() * px_x
    ys = y0 + (np.arange(nyb)[:, None] + sub[None, :]).ravel() * px_y
    X, Y = np.meshgrid(xs, ys)
    lo, _ = scene.bounds()
    o = np.c_[X.ravel(), Y.ravel(), np.full(X.size, lo[2] - 5)]
    d = np.tile([0.0, 0.0, 1.0], (len(o), 1))
    T = out["as_exported"].transmission(o, d, a.wavelength).reshape(nyb, 4, nxb, 4).mean(axis=(1, 3))
    T0 = scene.transmission(o, d, a.wavelength).reshape(nyb, 4, nxb, 4).mean(axis=(1, 3))
    # the open level: pixels where samplecraft sees nothing
    open_ = T > 1 - 1e-12
    if open_.sum() < 20:
        sys.exit("no open-beam pixels around the sample: increase beam_margin_mm")
    level = Iu[open_].mean()
    Tm, Em = Iu / level, Eu / level
    s = T < 0.999
    ratio = Tm[s].sum() / T[s].sum()
    err = np.sqrt((Em[s] ** 2).sum()) / T[s].sum()
    chi2 = float((((Tm - T)[s] / np.maximum(Em[s], 1e-30)) ** 2).mean())
    scat = 1 - Iu[s].sum() / Ia[s].sum()
    print(f"\n{scene.name or name}, λ = {a.wavelength:g} Å, {done * a.chunk:.2g} neutrons, pixels of {px_x * 1e3:.0f} µm:")
    print(f"  McStas Union / samplecraft (sample pixels, transmission < 0.999): {ratio:.4f} ± {err:.4f}")
    print(f"  χ² per pixel: {chi2:.2f} ({s.sum()} pixels)")
    print(f"  scattered among the neutrons counted behind the sample: {100 * scat:.2f} %")
    print(f"  samplecraft exact scene / as exported (mean over the sample): {T0[s].mean() / T[s].mean():.5f}")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ext = (x0, x0 + nxb * px_x, y0, y0 + nyb * px_y)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.2))
    for a_, img, t in ((ax[0], Tm, "McStas Union (unscattered)"), (ax[1], T, "samplecraft (exp(−ΣL))")):
        im = a_.imshow(img, origin="lower", extent=ext, vmin=min(T.min(), 0.9 * Tm.min()), vmax=1.02, cmap="gray")
        a_.set_title(t, fontsize=10)
        a_.set_xlabel("x [mm]"); a_.set_ylabel("y [mm]")
    fig.colorbar(im, ax=ax[:2], shrink=0.8, label="transmission")
    z = np.where(s, (Tm - T) / np.maximum(Em, 1e-30), np.nan)
    im = ax[2].imshow(z, origin="lower", extent=ext, vmin=-4, vmax=4, cmap="RdBu_r")
    ax[2].set_title("(McStas − samplecraft) / error", fontsize=10)
    ax[2].set_xlabel("x [mm]")
    fig.colorbar(im, ax=ax[2], shrink=0.8)
    fig.savefig(os.path.join(a.out, "comparison.png"), dpi=110, bbox_inches="tight")
    return dict(ratio=ratio, err=err, chi2=chi2, scattered=scat)


if __name__ == "__main__":
    main()
