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
    """ODIN, "Where is a loaded steel part strained?": the V20 tensile specimen (austenitic stainless steel) in the load
    frame as the camera sees it, what the load does to the lattice planes the neutrons see (seen from above), and the
    (111) edge that moves."""
    from scipy.special import erfc
    fig = plt.figure(figsize=(14, 4.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.1, 1.15], left=0.02, right=0.985, bottom=0.13, top=0.86, wspace=0.32)

    # (1) front view: what the camera sees (x horizontal, the force along x)
    ax = fig.add_subplot(gs[0])
    ax.add_patch(plt.Rectangle((-7.05, -7.05), 14.1, 14.1, fill=False, ec=GREY, ls="--", lw=1))
    R, h_half, d = 5.56, 4.9, 1.7
    x = np.linspace(-9.5, 9.5, 400)
    half = np.where(np.abs(x) < 4, 3.2 + (R - np.sqrt(np.clip(R ** 2 - x ** 2, 0, None))), h_half)
    ax.fill_between(x, -half, half, color="#9FB3CC", ec=INK, lw=1.2)
    for xs, dx in ((-9.6, -2.2), (9.6, 2.2)):
        ax.annotate("", xy=(xs + dx, 0), xytext=(xs, 0), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.5))
    ax.text(-10.8, 1.0, "F", color=RED, fontsize=12, fontweight="bold", ha="center")
    ax.text(10.8, 1.0, "F", color=RED, fontsize=12, fontweight="bold", ha="center")
    ax.annotate("", xy=(0, 3.2), xytext=(0, -3.2), arrowprops=dict(arrowstyle="<->", color=INK, lw=1))
    ax.text(-0.3, 0, "6.4 mm", fontsize=9, color=INK, va="center", ha="right")
    ax.annotate("", xy=(5.3, 4.9), xytext=(5.3, -4.9), arrowprops=dict(arrowstyle="<->", color=INK, lw=1))
    ax.text(5.55, 0, "9.8 mm", fontsize=9, color=INK, va="center", ha="left")
    ax.text(0, -8.4, "field of view, 14 mm × 14 mm (dashed)", ha="center", fontsize=8.5, color="#5B6779")
    ax.set(xlim=(-12, 12), ylim=(-9.5, 9.5), aspect="equal")
    ax.axis("off")
    ax.set_title("Seen by the camera", color=INK, fontsize=13, fontweight="bold")

    # (2) seen from above: x along the force, z along the beam; the planes facing the beam (exaggerated)
    ax = fig.add_subplot(gs[1])
    for y0, L, t, title, col in ((2.2, 6.0, 2.8, "without load", GREY), (-3.4, 7.0, 2.2, "with load", RED)):
        x0 = -L / 2
        ax.add_patch(plt.Rectangle((x0, y0), L, t, fc="#E4EAF2", ec=INK, lw=1.2))
        n = 4
        for k in range(n):
            yy = y0 + t * (k + 0.5) / n
            ax.plot([x0 + 0.15, x0 + L - 0.15], [yy, yy], color=TEAL, lw=1.6)
        ya, yb = y0 + t * 1.5 / n, y0 + t * 2.5 / n
        ax.annotate("", xy=(x0 + L + 0.35, yb), xytext=(x0 + L + 0.35, ya),
                    arrowprops=dict(arrowstyle="<->", color=TEAL, lw=1.2, mutation_scale=7, shrinkA=0, shrinkB=0))
        ax.text(x0 + L + 0.6, 0.5 * (ya + yb), "d" if col == GREY else "d (1 + ε), ε < 0", va="center", color=TEAL,
                fontsize=10.5, fontweight="bold")
        ax.text(x0 - 0.3, y0 + t / 2, title, ha="right", va="center", color=INK, fontsize=10.5, fontweight="bold")
    for xs, dx in ((-1.2, -2.2), (1.2, 2.2)):
        ax.annotate("", xy=(xs + dx, -4.1), xytext=(xs, -4.1), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.2))
    ax.text(0, -4.1, "F", color=RED, fontsize=11, fontweight="bold", ha="center", va="center")
    ax.annotate("", xy=(-6.2, 4.6), xytext=(-6.2, -4.4), arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2.5))
    ax.text(-6.6, 0, "neutrons", color=ORANGE, fontsize=10.5, fontweight="bold", ha="right", va="center", rotation=90)
    ax.text(0.5, -4.9, "Pulled along the force, the steel gets longer, and thinner\nacross it (Poisson): the planes "
            "facing the beam move closer.", ha="center", va="top", fontsize=9.5, color="#5B6779")
    ax.set(xlim=(-8.0, 8.2), ylim=(-6.6, 5.6), aspect="equal")
    ax.axis("off")
    ax.set_title("Seen from above", color=INK, fontsize=13, fontweight="bold")

    # (3) the (111) edge moves
    ax = fig.add_subplot(gs[2])
    e0 = 4.164
    lam = np.linspace(4.0, 4.3, 600)
    edge = lambda l0: 0.66 + 0.14 * 0.5 * erfc(-(lam - l0) / (np.sqrt(2) * 0.009))
    shift = 0.026                                   # drawn 7 times larger than at 600 MPa (0.0037 Å)
    ax.plot(lam, edge(e0), color=GREY, lw=2.2, label="without load: λ₀ = 2d₁₁₁")
    ax.plot(lam, edge(e0 - shift), color=RED, lw=2.2, label="with load: λ = 2d₁₁₁ (1 + ε)")
    ax.annotate("", xy=(e0 - shift, 0.735), xytext=(e0, 0.735), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4))
    ax.text(e0 - shift / 2, 0.742, "the edge moves", ha="center", va="bottom", fontsize=9.5, color=INK)
    ax.text(0.97, 0.06, "ε = (λ − λ₀) / λ₀\n(shift drawn 7× larger\nthan at 600 MPa)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=9.5, color="#5B6779")
    ax.set(xlabel="neutron wavelength λ (Å)", ylabel="transmission", ylim=(0.6, 0.85), xlim=(4.0, 4.3))
    ax.legend(loc="upper left", fontsize=9.5, frameon=False)
    ax.set_title("The (111) Bragg edge moves", color=INK, fontsize=13, fontweight="bold")
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
