"""Explanatory figures of the exercises (twin/figures/), embedded in the pages and notebooks by their generators.

    python gen_figures.py

iron_structures.png  ODIN, "How far apart are the atoms in iron?": the two structures to tell apart (alpha-iron,
                     body-centered cubic; gamma-iron, face-centered cubic), one family of atomic planes each, and the
                     Bragg edges each structure gives (lambda_edge = 2 d_hkl): what the measurement has to decide.
sans_particles.png   LoKI, "How big are these nanoparticles?": particles in heavy water, the small-angle scattering on
                     the detector, and how the size sets the curve I(Q) (sphere form factor, two sizes as examples).
steel_strain.png     ODIN, "Where is a loaded steel part strained?": the specimen in its load frame, the lattice
                     planes facing the beam moving closer under load (Poisson contraction), and the edge that moves.
meteorite_tomography.png  ODIN, "What is hidden inside a Martian meteorite?": a radiograph adds up the clasts along the
                     beam, turning the sample separates them, back-projection finds them (top view of one slice).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
INK, TEAL, ORANGE, GREY, RED = "#142033", "#0E7C70", "#C7711A", "#8A94A6", "#B4562B"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#5B6779",
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

A_ALPHA, A_GAMMA = 2.8665, 3.59           # lattice parameters [Å] (alpha-iron at room temperature; gamma-iron)


def edges(a, hkls):
    """Bragg edges lambda = 2 d_hkl, d_hkl = a / sqrt(h^2 + k^2 + l^2) (cubic)."""
    return [(h, 2 * a / np.sqrt(h[0] ** 2 + h[1] ** 2 + h[2] ** 2)) for h in hkls]


ALPHA = edges(A_ALPHA, [(1, 1, 0), (2, 0, 0), (2, 1, 1)])              # bcc: h+k+l even
GAMMA = edges(A_GAMMA, [(1, 1, 1), (2, 0, 0), (2, 2, 0)])              # fcc: h, k, l all even or all odd


def cube(ax, atoms, plane, title, sub, color, view=(18, -58)):
    r = [0, 1]
    for s in r:
        for t in r:
            ax.plot([0, 1], [s, s], [t, t], color=GREY, lw=1)
            ax.plot([s, s], [0, 1], [t, t], color=GREY, lw=1)
            ax.plot([s, s], [t, t], [0, 1], color=GREY, lw=1)
    ax.add_collection3d(Poly3DCollection([plane], alpha=0.28, facecolor=color, edgecolor=color, lw=1.5))
    on = lambda p: abs(np.dot(np.cross(np.subtract(plane[1], plane[0]), np.subtract(plane[2], plane[0])),
                              np.subtract(p, plane[0]))) < 1e-9
    for p in atoms:
        ax.scatter(*p, s=170, color=color if on(p) else "#C9CFDA", edgecolor=INK, linewidth=0.8, depthshade=False)
    ax.set_title(title, color=INK, fontsize=13, fontweight="bold", pad=0)
    ax.text2D(0.5, -0.02, sub, transform=ax.transAxes, ha="center", va="top", fontsize=10.5, color=INK)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=view[0], azim=view[1])
    ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_zlim(0, 1)


def iron():
    corners = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    bcc = corners + [(0.5, 0.5, 0.5)]
    fcc = corners + [(0.5, 0.5, 0), (0.5, 0.5, 1), (0.5, 0, 0.5), (0.5, 1, 0.5), (0, 0.5, 0.5), (1, 0.5, 0.5)]
    fig = plt.figure(figsize=(13, 4.9))
    ax1 = fig.add_subplot(1, 3, 1, projection="3d")
    cube(ax1, bcc, [(0, 0, 0), (1, 1, 0), (1, 1, 1), (0, 0, 1)], "α-iron (ferritic steel)",
         f"body-centered cubic, a = {A_ALPHA:.2f} Å\nplanes (110): d = a/√2 = {A_ALPHA / np.sqrt(2):.2f} Å", TEAL)
    ax2 = fig.add_subplot(1, 3, 2, projection="3d")
    cube(ax2, fcc, [(1, 0, 0), (0, 1, 0), (0, 0, 1)], "γ-iron (austenitic steel)",
         f"face-centered cubic, a = {A_GAMMA:.2f} Å\nplanes (111): d = a/√3 = {A_GAMMA / np.sqrt(3):.2f} Å", ORANGE,
         view=(24, 28))       # (seen from near the [111] direction: the plane faces us)
    ax3 = fig.add_axes([0.70, 0.20, 0.28, 0.66])
    lam = np.linspace(1.8, 5.2, 1200)

    def sketch(ed, base):     # transmission rises at each edge (a sketch: the shapes, not the real values)
        t = np.full_like(lam, base)
        for k, (_, le) in enumerate(ed):
            t += 0.12 / (k + 1) * 0.5 * (1 + np.tanh((lam - le) / 0.012))
        return t
    ax3.plot(lam, sketch(ALPHA, 0.42), color=TEAL, lw=2.2, label="α-iron")
    ax3.plot(lam, sketch(GAMMA, 0.30), color=ORANGE, lw=2.2, label="γ-iron")
    for (h, le), c, xy, txt in [(ALPHA[0], TEAL, (ALPHA[0][1], 0.62), (3.05, 0.76)),
                                (GAMMA[0], ORANGE, (GAMMA[0][1], 0.52), (4.35, 0.36))]:
        ax3.annotate(f"({''.join(map(str, h))}) edge\n{le:.2f} Å", xy, xytext=txt,
                     color=c, fontsize=10, arrowprops=dict(arrowstyle="->", color=c, lw=1))
    ax3.set_xlabel("neutron wavelength λ (Å)")
    ax3.set_ylabel("transmission")
    ax3.set_yticks([])
    ax3.set_xlim(1.8, 5.2)
    ax3.set_ylim(0.2, 0.85)
    ax3.legend(loc="upper left", frameon=False)
    ax3.set_title("Bragg edges: at λ = 2d the\ntransmission jumps (sketch)", color=INK, fontsize=12, fontweight="bold")
    for s in ("top", "right"):
        ax3.spines[s].set_visible(False)
    fig.text(0.01, 0.02, "Highlighted: one family of atomic planes. Neutrons longer than 2d cannot be diffracted by "
             "these planes: they go through,\nand the transmission jumps up. The last edge tells d, hence the structure.",
             fontsize=10, color="#5B6779")
    fig.savefig(os.path.join(OUT, "iron_structures.png"), dpi=150)
    plt.close(fig)


def sphere_ff(q, r):
    x = q * r
    return (3 * (np.sin(x) - x * np.cos(x)) / x ** 3) ** 2


def sans():
    fig = plt.figure(figsize=(13, 4.4))
    # 1. particles in heavy water
    ax = fig.add_axes([0.01, 0.12, 0.27, 0.76])
    rng = np.random.default_rng(3)
    ax.add_patch(plt.Rectangle((0, 0), 10, 10, color="#DDEBF5"))
    pts = []
    for _ in range(5000):                # up to 10 particles that do not overlap
        if len(pts) == 10:
            break
        p = rng.uniform(1.2, 8.8, 2)
        if all(np.hypot(*(p - q)) > 2.3 for q in pts):
            pts.append(p)
    for p in pts:
        ax.add_patch(plt.Circle(p, 0.9, color="#B9C2CF", ec=INK, lw=0.8))
    p = pts[0]
    ax.annotate("", p + (0.9, 0), p, arrowprops=dict(arrowstyle="<->", color=RED, lw=1.5))
    ax.text(p[0] + 0.45, p[1] + 0.25, "R", color=RED, fontsize=12, ha="center", fontweight="bold")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Silica spheres in heavy water", color=INK, fontsize=13, fontweight="bold")
    ax.text(5, -0.6, "billions of particles: R ≈ 5 nm = 50 Å?", ha="center", va="top", fontsize=10.5, color=INK)
    # 2. the measurement
    ax = fig.add_axes([0.31, 0.12, 0.33, 0.76])
    ax.plot([0, 3.2], [0, 0], color=TEAL, lw=5, solid_capstyle="butt")
    ax.add_patch(plt.Rectangle((3.2, -0.6), 0.35, 1.2, color="#B9C2CF", ec=INK))
    for ang in (-0.16, -0.08, 0.08, 0.16):
        ax.plot([3.4, 9.4], [0, 6 * np.tan(ang)], color=ORANGE, lw=1.2, ls="--")
    ax.plot([9.5, 9.5], [-1.7, 1.7], color=INK, lw=4)
    ax.annotate("", (9.4, 6 * np.tan(0.16)), (9.4, 0), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text(5.6, 1.45, "2θ: a few degrees", fontsize=10, color=INK)
    ax.text(1.5, 0.3, "neutrons", color=TEAL, fontsize=10, ha="center")
    ax.text(3.37, -0.95, "sample", fontsize=10, ha="center", color=INK)
    ax.text(9.5, -2.0, "detector", fontsize=10, ha="center", color=INK)
    ax.set_xlim(-0.2, 10.3); ax.set_ylim(-2.4, 2.2); ax.axis("off")
    ax.set_title("Small-angle scattering (LoKI)", color=INK, fontsize=13, fontweight="bold")
    ax.text(5, -2.6, "Q = 4π sin θ / λ: small Q = large distances", ha="center", va="top", fontsize=10.5, color=INK)
    # 3. I(Q) for two sizes
    ax = fig.add_axes([0.71, 0.2, 0.27, 0.66])
    q = np.logspace(-2.3, -0.5, 500)
    for r, c in [(30, TEAL), (70, ORANGE)]:
        ax.loglog(q, sphere_ff(q, r), color=c, lw=2, label=f"R = {r / 10:g} nm")
        ax.axvline(4.493 / r, color=c, lw=0.8, ls=":")
    ax.set_ylim(1e-6, 2)
    ax.set_xlabel("Q (Å⁻¹)")
    ax.set_ylabel("I(Q) (a sphere, scaled)")
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("The size sets the curve", color=INK, fontsize=13, fontweight="bold")
    ax.text(0.03, 0.62, "larger R:\ncurve at\nsmaller Q\n(minimum at\nQR = 4.49)", transform=ax.transAxes,
            ha="left", va="top", fontsize=9.5, color="#5B6779")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(os.path.join(OUT, "sans_particles.png"), dpi=150)
    plt.close(fig)


def steel_strain():
    """ODIN, "Where is a loaded steel part strained?": the specimen in the load frame as the camera sees it, what
    the load does to the lattice planes the neutrons see (seen from the side), and the edge that moves."""
    from scipy.special import erfc
    fig = plt.figure(figsize=(13.5, 4.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.8, 1.25, 1.2], left=0.03, right=0.985, bottom=0.13, top=0.86, wspace=0.22)

    # (1) front view: what the camera sees
    ax = fig.add_subplot(gs[0])
    ax.add_patch(plt.Rectangle((-7.05, -7.05), 14.1, 14.1, fill=False, ec=GREY, ls="--", lw=1))
    for (x0, y0, w, h) in ((-4, 3, 8, 6.5), (-4, -9.5, 8, 6.5)):
        ax.add_patch(plt.Rectangle((x0, y0), w, h, fc="#C9D3E0", ec=INK, lw=1.2))
    ax.add_patch(plt.Rectangle((-2, -3), 4, 6, fc="#9FB3CC", ec=INK, lw=1.2))
    for y, dy in ((9.6, 2.6), (-9.6, -2.6)):
        ax.annotate("", xy=(0, y + dy), xytext=(0, y), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.5))
    ax.text(0.8, 11.2, "force F", color=RED, fontsize=11, fontweight="bold", va="center")
    ax.text(0.8, -11.2, "force F", color=RED, fontsize=11, fontweight="bold", va="center")
    ax.text(2.5, 0, "gauge," + chr(10) + "4 mm wide", ha="left", va="center", fontsize=9.5, color=INK)
    ax.text(0, 5.2, "shoulder, 8 mm wide", ha="center", va="center", fontsize=9.5, color=INK)
    ax.text(0, -5.2, "shoulder, 8 mm wide", ha="center", va="center", fontsize=9.5, color=INK)
    ax.text(-7.3, 0, "field of view, 14 mm × 14 mm", ha="right", va="center", fontsize=8.5, color="#5B6779", rotation=90)
    ax.set(xlim=(-9, 9), ylim=(-13.2, 13.2), aspect="equal")
    ax.axis("off")
    ax.set_title("Seen by the camera", color=INK, fontsize=13, fontweight="bold")

    # (2) side view: the lattice planes the neutrons see, without and with load (changes exaggerated)
    ax = fig.add_subplot(gs[1])
    for x0, t, h, title, col in ((0.0, 3.0, 5.0, "without load", GREY), (5.6, 2.55, 5.9, "with load", RED)):
        y0 = -h / 2
        ax.add_patch(plt.Rectangle((x0, y0), t, h, fc="#E4EAF2", ec=INK, lw=1.2))
        n = 7
        for k in range(n):
            x = x0 + t * (k + 0.5) / n
            ax.plot([x, x], [y0 + 0.15, y0 + h - 0.15], color=TEAL, lw=1.6)
        xa, xb = x0 + t * 2.5 / n, x0 + t * 3.5 / n
        ax.annotate("", xy=(xb, y0 - 0.35), xytext=(xa, y0 - 0.35), arrowprops=dict(arrowstyle="<->", color=TEAL, lw=1.2))
        ax.text(0.5 * (xa + xb), y0 - 0.75, "d" if col == GREY else "d (1 + ε), ε < 0", ha="center", va="top",
                color=TEAL, fontsize=10.5, fontweight="bold")
        ax.text(x0 + t / 2, 3.75, title, ha="center", va="bottom", color=INK, fontsize=11, fontweight="bold")
    for y, dy in ((3.0, 0.9), (-3.0, -0.9)):
        ax.annotate("", xy=(5.6 + 2.55 / 2 + 2.3, y * 0.6 + dy), xytext=(5.6 + 2.55 / 2 + 2.3, y * 0.6),
                    arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.2))
    ax.text(5.6 + 2.55 / 2 + 2.55, 0, "F", color=RED, fontsize=12, fontweight="bold", va="center", ha="left")
    ax.annotate("", xy=(-0.25, 0), xytext=(-2.6, 0), arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2.5))
    ax.text(-2.6, 0.35, "neutrons", color=ORANGE, fontsize=10.5, fontweight="bold", ha="left", va="bottom")
    ax.annotate("", xy=(5.35, 0), xytext=(3.25, 0), arrowprops=dict(arrowstyle="-|>", color="#5B6779", lw=1.5))
    ax.text(4.3, -4.55, "Pulled along the force, the steel gets longer, and thinner\nacross it (Poisson): the planes "
            "facing the beam move closer.", ha="center", va="top", fontsize=9.5, color="#5B6779")
    ax.set(xlim=(-3, 11.2), ylim=(-5.9, 4.6), aspect="equal")
    ax.axis("off")
    ax.set_title("Seen from the side: the planes facing the beam", color=INK, fontsize=13, fontweight="bold")

    # (3) the edge moves
    ax = fig.add_subplot(gs[2])
    lam = np.linspace(3.9, 4.2, 600)
    edge = lambda l0: 0.41 + 0.36 * 0.5 * erfc(-(lam - l0) / (np.sqrt(2) * 0.009))
    shift = 0.03                                    # drawn 7 times larger than at 16 kN (0.0045 Å)
    ax.plot(lam, edge(4.054), color=GREY, lw=2.2, label="without load: λ₀ = 2d")
    ax.plot(lam, edge(4.054 - shift), color=RED, lw=2.2, label="with load: λ = 2d (1 + ε)")
    ax.annotate("", xy=(4.054 - shift, 0.59), xytext=(4.054, 0.59), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4))
    ax.text(4.054 - shift / 2, 0.615, "the edge moves", ha="center", va="bottom", fontsize=9.5, color=INK)
    ax.text(0.97, 0.06, "ε = (λ − λ₀) / λ₀\n(shift drawn 7× larger\nthan at 16 kN)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=9.5, color="#5B6779")
    ax.set(xlabel="neutron wavelength λ (Å)", ylabel="transmission", ylim=(0.3, 0.9), xlim=(3.9, 4.2))
    ax.legend(loc="upper left", fontsize=9.5, frameon=False)
    ax.set_title("The (110) Bragg edge moves", color=INK, fontsize=13, fontweight="bold")
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.savefig(os.path.join(OUT, "steel_strain.png"), dpi=150)
    plt.close(fig)


def meteorite_tomography():
    """Top view of the cylinder (x across, z along the beam): two clasts one behind the other make one spot; at
    another angle they make two; back-projecting the projections of all angles finds them."""
    from matplotlib.patches import Circle
    R = 6.0
    clasts = [((2.5, -1.5), 1.5), ((2.3, 3.0), 0.9), ((-2.8, 2.0), 1.1)]       # (x, z), radius [mm] (top view)
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.3))

    def sample(ax, rot=0.0):
        th = np.radians(rot)
        ax.add_patch(Circle((0, 0), R, fc="#D9CBB6", ec=INK, lw=1.2))
        for (x, z), r in clasts:
            xr, zr = x * np.cos(th) + z * np.sin(th), -x * np.sin(th) + z * np.cos(th)
            ax.add_patch(Circle((xr, zr), r, fc="#3B4A63", ec="none"))
        ax.set(xlim=(-9, 9), ylim=(-11, 12.5), aspect="equal")
        ax.axis("off")

    def profile(ax, rot, y0, color):
        """−ln T along x' after a rotation rot, drawn as a camera profile at height y0."""
        th = np.radians(rot)
        xs = np.linspace(-8, 8, 400)
        p = 0.25 * 2 * np.sqrt(np.clip(R ** 2 - xs ** 2, 0, None)) / 10
        for (x, z), r in clasts:
            xr = x * np.cos(th) + z * np.sin(th)
            p += 0.7 * 2 * np.sqrt(np.clip(r ** 2 - (xs - xr) ** 2, 0, None)) / 10
        ax.plot([-8, 8], [y0, y0], color=GREY, lw=3)
        ax.plot(xs, y0 + 0.3 + 1.6 * p, color=color, lw=1.8)
        return xs, p

    ax = axs[0]
    sample(ax)
    for x in np.linspace(-7, 7, 8):
        ax.annotate("", xy=(x, 7.2), xytext=(x, -9.6), arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=0.8, alpha=0.6))
    profile(ax, 0, 7.6, RED)
    ax.text(0, -10.9, "neutron beam", ha="center", color=TEAL, fontsize=10)
    ax.text(-8.5, 8.8, "camera:\nattenuation", ha="left", va="bottom", fontsize=9.5, color=INK)
    ax.text(5.6, 9.6, "one peak:\ntwo clasts", ha="center", fontsize=9.5, color=RED)
    ax.set_title("A radiograph adds up\neverything along the beam", color=INK, fontsize=12.5, fontweight="bold")

    ax = axs[1]
    sample(ax, 60)
    for x in np.linspace(-7, 7, 8):
        ax.annotate("", xy=(x, 7.2), xytext=(x, -9.6), arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=0.8, alpha=0.6))
    profile(ax, 60, 7.6, RED)
    ax.annotate("", xy=(3.5, -8.2), xytext=(-3.5, -8.2),
                arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.8, connectionstyle="arc3,rad=0.35"))
    ax.text(0, -10.9, "the stage turns", ha="center", color=ORANGE, fontsize=10)
    ax.text(5.6, 9.6, "turned by 60°:\ntwo peaks", ha="center", fontsize=9.5, color=RED)
    ax.set_title("Turning the sample: the clasts\nseparate in the projections", color=INK, fontsize=12.5, fontweight="bold")

    ax = axs[2]
    ax.add_patch(Circle((0, 0), R, fc="#F3EEE6", ec=INK, lw=1.2))
    for rot in np.arange(0, 180, 12):
        th = np.radians(rot)
        d = np.array([-np.sin(th), np.cos(th)])          # beam direction in the sample frame
        n = np.array([np.cos(th), np.sin(th)])           # detector axis
        for (x, z), r in clasts:
            s = x * n[0] + z * n[1]                      # where the clast is seen on the detector
            a, b = s * n - 8 * d, s * n + 8 * d
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#3B4A63", lw=2.2 * r, alpha=0.07, solid_capstyle="butt")
    for (x, z), r in clasts:
        ax.add_patch(Circle((x, z), r, fc="none", ec=RED, lw=1.4, ls="--"))
    ax.set(xlim=(-9, 9), ylim=(-11, 12.5), aspect="equal")
    ax.axis("off")
    ax.text(0, -10.9, "each projection smeared back along its beam:\nthe lines cross where the clasts are",
            ha="center", fontsize=10, color=INK)
    ax.set_title("Back-projection gives\nthe slice back", color=INK, fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.text(0.5, 0.025, "Tomography: seen from above, one horizontal slice of the cylinder", ha="center", fontsize=12, color="#5B6779")
    fig.savefig(os.path.join(OUT, "meteorite_tomography.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("alpha edges:", [(h, round(l, 3)) for h, l in ALPHA], " gamma edges:", [(h, round(l, 3)) for h, l in GAMMA])
    iron()
    sans()
    steel_strain()
    meteorite_tomography()
    print("written", OUT)
