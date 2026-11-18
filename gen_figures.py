"""Explanatory figures of the exercises (twin/figures/), embedded in the pages and notebooks by their generators.

    python gen_figures.py

iron_structures.png  ODIN, "How far apart are the atoms in iron?": the two structures to tell apart (alpha-iron,
                     body-centered cubic; gamma-iron, face-centered cubic), one family of atomic planes each, and the
                     Bragg edges each structure gives (lambda_edge = 2 d_hkl): what the measurement has to decide.
sans_particles.png   LoKI, "How big are these nanoparticles?": particles in heavy water, the small-angle scattering on
                     the detector, and how the size sets the curve I(Q) (sphere form factor, two sizes as examples).
steel_strain.png     ODIN, "Where is a loaded steel part strained?": the specimen in its load frame (camera view) and the
                     (111) edge that moves under load.
steel_lattice.png    the crystal without load and under load (square grid, exaggerated): spacing along the force grows,
                     along the beam shrinks (Poisson); the planes facing the beam set the edge.
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



def _save(fig, name):
    """The figure as PNG (dpi 150) and as SVG (vectors: what the pages show, sharp at every size; nbfig.figure_cell)."""
    fig.savefig(os.path.join(OUT, name), dpi=150)
    fig.savefig(os.path.join(OUT, os.path.splitext(name)[0] + ".svg"))

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
    _save(fig, "iron_structures.png")
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
    _save(fig, "sans_particles.png")
    plt.close(fig)


def steel_strain():
    """ODIN, "Where is a loaded steel part strained?": the V20 tensile specimen (austenitic stainless steel) in the load
    frame as the camera sees it, what the load does to the lattice planes the neutrons see (seen from above), and the
    (111) edge that moves."""
    from scipy.special import erfc
    # drawn at the width it is shown (10.6 in ≈ the width of the page): every text at 11 pt or more stays readable
    fig = plt.figure(figsize=(10.6, 4.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.15], left=0.02, right=0.98, bottom=0.15, top=0.88, wspace=0.18)

    # (1) front view: what the camera sees (x horizontal, the force along x)
    ax = fig.add_subplot(gs[0])
    ax.add_patch(plt.Rectangle((-7.05, -7.05), 14.1, 14.1, fill=False, ec=GREY, ls="--", lw=1.2))
    R, h_half = 5.56, 4.9
    x = np.linspace(-9.5, 9.5, 400)
    half = np.where(np.abs(x) < 4, 3.2 + (R - np.sqrt(np.clip(R ** 2 - x ** 2, 0, None))), h_half)
    ax.fill_between(x, -half, half, color="#9FB3CC", ec=INK, lw=1.2)
    for xs, dx in ((-9.6, -2.2), (9.6, 2.2)):
        ax.annotate("", xy=(xs + dx, 0), xytext=(xs, 0), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.5))
    ax.text(-10.8, 1.0, "F", color=RED, fontsize=14, fontweight="bold", ha="center")
    ax.text(10.8, 1.0, "F", color=RED, fontsize=14, fontweight="bold", ha="center")
    ax.annotate("", xy=(0, 3.2), xytext=(0, -3.2), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2))
    ax.text(-0.3, 0, "6.4 mm", fontsize=11, color=INK, va="center", ha="right")
    ax.annotate("", xy=(5.3, 4.9), xytext=(5.3, -4.9), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2))
    ax.text(5.55, 0, "9.8 mm", fontsize=11, color=INK, va="center", ha="left")
    ax.text(0, -8.5, "dashed: field of view, 14 mm", ha="center", fontsize=11, color="#5B6779")
    ax.set(xlim=(-12, 12), ylim=(-9.6, 8.6), aspect="equal")
    ax.axis("off")
    ax.set_title("Seen by the camera", color=INK, fontsize=14, fontweight="bold")

    # (2) the (111) edge moves
    ax = fig.add_subplot(gs[1])
    e0 = 4.164
    lam = np.linspace(4.0, 4.3, 600)
    edge = lambda l0: 0.66 + 0.14 * 0.5 * erfc(-(lam - l0) / (np.sqrt(2) * 0.009))
    shift = 0.026                                   # drawn 7 times larger than at 600 MPa (0.0037 Å)
    ax.plot(lam, edge(e0), color=GREY, lw=2.4, label="without load: λ₀ = 2d")
    ax.plot(lam, edge(e0 - shift), color=RED, lw=2.4, label="under load: λ = 2d (1 + ε)")
    ax.annotate("", xy=(e0 - shift, 0.735), xytext=(e0, 0.735), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5))
    ax.text(e0 - shift / 2, 0.744, "the edge moves", ha="center", va="bottom", fontsize=11, color=INK)
    ax.text(0.97, 0.05, "ε = (λ − λ₀) / λ₀\nshift drawn 7× larger", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=11, color="#5B6779")
    ax.set(xlabel="neutron wavelength λ (Å)", ylabel="transmission", ylim=(0.6, 0.85), xlim=(4.0, 4.3))
    ax.xaxis.label.set_size(12); ax.yaxis.label.set_size(12)
    ax.tick_params(labelsize=11)
    ax.legend(loc="upper left", fontsize=11, frameon=False)
    ax.set_title("The (111) Bragg edge moves", color=INK, fontsize=14, fontweight="bold")
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    _save(fig, "steel_strain.png")
    plt.close(fig)


def steel_lattice():
    """ODIN, steel exercise: the crystal without load and under load, seen from above (x along the force, z along the
    beam). A simplified picture: a square grid of atoms (the steel is face-centered cubic; its edge is that of the
    (111) planes). Under load the spacing along the force grows by ε = σ/E, the spacing across it shrinks by ν σ/E
    (Poisson). The edge measured is set by the planes facing the beam (λ = 2d, back-scattering): their spacing is the
    one along the beam, so the edge moves to a SHORTER wavelength. Deformation drawn 65 times larger than at 600 MPa
    (ε_force = 600/195 000 = 3.1e-3 drawn as 0.20; ε_beam = -0.29 × 3.1e-3 = -0.9e-3 drawn as -0.06)."""
    fig, axs = plt.subplots(1, 2, figsize=(10.6, 5.4))
    n = 5
    for ax, (sx, sz, title) in zip(axs, ((1.0, 1.0, "Without load"), (1.20, 0.94, "Under load (exaggerated)"))):
        xs = (np.arange(n) - (n - 1) / 2) * sx
        zs = (np.arange(n) - (n - 1) / 2) * sz
        for z in zs:                                         # the planes facing the beam (perpendicular to z)
            ax.plot([xs[0] - 0.35, xs[-1] + 0.35], [z, z], color=TEAL, lw=1.6, alpha=0.7, zorder=1)
        X, Z = np.meshgrid(xs, zs)
        ax.scatter(X, Z, s=260, color="#9FB3CC", edgecolor=INK, linewidth=1.0, zorder=3)
        # the spacing along the beam (z): d
        xa = xs[-1] + 0.75
        ax.annotate("", xy=(xa, zs[3]), xytext=(xa, zs[2]),
                    arrowprops=dict(arrowstyle="<->", color=TEAL, lw=1.6, shrinkA=0, shrinkB=0))
        ax.text(xa + 0.15, 0.5 * (zs[2] + zs[3]), "d" if sz == 1.0 else "d\nsmaller", color=TEAL, fontsize=13,
                fontweight="bold", va="center", ha="left")
        # the spacing along the force (x)
        za = zs[0] - 0.75
        ax.annotate("", xy=(xs[3], za), xytext=(xs[2], za),
                    arrowprops=dict(arrowstyle="<->", color=RED, lw=1.6, shrinkA=0, shrinkB=0))
        ax.text(0.5 * (xs[2] + xs[3]), za - 0.2, "larger" if sx > 1 else "", color=RED, fontsize=12, ha="center",
                va="top")
        zf = zs[-1] + 0.75                                   # the force, pulling above the grid
        if sx > 1:
            for x0, dx in ((xs[0], -1.0), (xs[-1], 1.0)):
                ax.annotate("", xy=(x0 + dx, zf), xytext=(x0, zf), arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.6))
                ax.text(x0 + dx * 0.5, zf + 0.15, "F", color=RED, fontsize=14, fontweight="bold", ha="center",
                        va="bottom")
        else:
            ax.text(0, zf, "no force", color=GREY, fontsize=12, ha="center", va="center")
        # the beam, from below, on the left of the grid
        xb = xs[0] - 1.3
        ax.annotate("", xy=(xb, 2.3), xytext=(xb, -2.3), arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2.6))
        ax.text(xb - 0.3, 0, "neutrons", color=ORANGE, fontsize=12, fontweight="bold", rotation=90, ha="right",
                va="center")
        ax.set_title(title, color=INK, fontsize=14, fontweight="bold")
        ax.set(xlim=(-4.9, 5.0), ylim=(-3.9, 3.3), aspect="equal")
        ax.axis("off")
    axs[0].text(-0.2, -3.75, "teal lines: the planes facing the beam", ha="center", fontsize=11, color=TEAL)
    axs[1].text(0, -3.75, "longer along the force, thinner across it", ha="center", fontsize=11, color=INK)
    fig.text(0.5, 0.025, "Seen from above, the force along x, the beam along z. The edge λ = 2d is set by the planes "
             "facing the beam:\ntheir spacing d shrinks, the edge moves to a shorter wavelength. Deformation drawn "
             "about 65 times larger than at 600 MPa.", ha="center", va="bottom", fontsize=11, color="#5B6779")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.14, wspace=0.05)
    _save(fig, "steel_lattice.png")
    plt.close(fig)


def bragg_edge_explained():
    """What a Bragg edge is. Left: planes d apart reflect a wave when λ = 2d sin θ; the longer λ, the larger θ, up to
    θ = 90° (straight back) at λ = 2d; beyond, no reflection. Right: the transmission of 1 cm of α-iron against λ
    (NCrystal, scattering + absorption): below 2d grains well oriented scatter neutrons out of the beam, above 2d none
    can: the transmission jumps. Last edge: (110) planes, d = 2.027 Å, edge at 4.05 Å."""
    import NCrystal as NC
    from matplotlib.patches import FancyArrowPatch
    cfg = "stdlib::Fe_sg229_Iron-alpha.ncmat"
    info, sc, ab = NC.createInfo(cfg), NC.createScatter(cfg), NC.createAbsorption(cfg)
    lam = np.linspace(1.0, 6.0, 1200)
    e = NC.wl2ekin(lam)
    sig = sc.xsect(ekin=e) + ab.xsect(ekin=e)                    # barn per atom
    T = np.exp(-info.numberdensity * sig * 1.0)                    # 1 cm: n [Å⁻³] × σ [barn] = cm⁻¹ (1e24 × 1e-24)
    fig = plt.figure(figsize=(10.6, 4.4))
    # left: Bragg's law, three wavelengths
    ax = fig.add_axes([0.02, 0.06, 0.40, 0.84])
    for y in (0.0, -0.9, -1.8):
        ax.plot([-2.2, 2.2], [y, y], color=GREY, lw=2)
        ax.plot(np.linspace(-2, 2, 9), np.full(9, y), "o", color=INK, ms=5)
    ax.annotate("", (2.45, -0.9), (2.45, 0.0), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text(2.55, -0.45, "d", fontsize=13, color=INK, va="center", fontweight="bold")
    for th, c, lab in ((25, TEAL, "short λ: small θ"), (60, ORANGE, "longer λ: larger θ"),
                       (88, RED, "λ = 2d: θ = 90°,\nstraight back")):
        t = np.radians(th)
        x0, y0 = -1.9 * np.cos(t), 1.9 * np.sin(t)
        ax.add_patch(FancyArrowPatch((x0, y0), (0, 0.02), arrowstyle="-|>", mutation_scale=14, color=c, lw=2))
        x1 = -x0 if th < 85 else 0.12
        ax.add_patch(FancyArrowPatch((0, 0.02), (x1, y0), arrowstyle="-|>", mutation_scale=14, color=c, lw=2, ls="--"))
        if th < 85:                                         # at the reflected wave
            ax.text(x1 + 0.15, y0, lab, fontsize=11, color=c, ha="left", va="center")
        else:                                               # straight up: on the left, clear of the others
            ax.text(-0.3, y0 + 0.25, lab, fontsize=11, color=c, ha="right", va="center")
    ax.text(0.6, -2.45, "Bragg's law: λ = 2d sin θ, and sin θ ≤ 1:\nno reflection at all when λ > 2d",
            ha="center", va="top", fontsize=11.5, color=INK)
    ax.set_xlim(-2.6, 4.4); ax.set_ylim(-3.2, 2.6); ax.axis("off")
    ax.set_title("A family of planes reflects up to λ = 2d", fontsize=12.5, fontweight="bold", color=INK)
    # right: transmission of α-iron
    b = fig.add_axes([0.53, 0.15, 0.44, 0.72])
    b.plot(lam, T, color=TEAL, lw=2)
    b.axvline(4.054, color=RED, lw=1.2, ls="--")
    b.annotate("Bragg edge of the (110) planes:\nλ = 2d = 2 × 2.027 Å = 4.05 Å", (4.054, 0.45), (1.15, 0.66),
               fontsize=11, color=RED, arrowprops=dict(arrowstyle="->", color=RED))
    b.text(3.0, 0.08, "some grains scatter\nneutrons out of the beam", fontsize=10.5, color=INK, ha="center")
    b.text(5.05, 0.70, "no grain can\nscatter any more", fontsize=10.5, color=INK, ha="center")
    b.set(xlabel="wavelength λ (Å)", ylabel="transmission T", xlim=(1.0, 6.0), ylim=(0, 0.85))
    b.set_title("Transmission of 1 cm of α-iron (NCrystal)", fontsize=12.5, fontweight="bold", color=INK)
    b.grid(alpha=0.3)
    for s in ("top", "right"):
        b.spines[s].set_visible(False)
    _save(fig, "bragg_edge_explained.png")
    plt.close(fig)


def meteorite_tomography():
    """Top view of one horizontal slice of the piece of NWA 7034 (8 mm across, 2 mm along the beam at 0°, as in the
    twin): two H-rich clasts one behind the other make one peak; turned by 60° they make two; back-projecting the
    projections of all angles finds them. Attenuation from the values measured at ICON (Naver et al. 2026): matrix
    0.45 cm⁻¹, H-rich clasts 1.9 cm⁻¹. The clasts (0.3 mm across in the paper) are drawn 3 times larger to be seen."""
    from matplotlib.patches import Circle, Polygon
    W, T = 8.0, 2.0                                          # piece: x across, z along the beam at 0° [mm]
    S_MAT, S_CL, ENL = 0.045, 0.19, 3.0                      # Σ [1/mm]; clasts drawn ENL times larger
    clasts = [((1.6, -0.55), 0.17), ((1.6, 0.5), 0.15), ((-2.4, 0.1), 0.2)]      # (x, z), true radius [mm]
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.3))

    def rot(x, z, deg):
        th = np.radians(deg)
        return x * np.cos(th) + z * np.sin(th), -x * np.sin(th) + z * np.cos(th)

    def sample(ax, deg=0.0, faint=False):
        corners = [rot(x, z, deg) for x, z in ((-W / 2, -T / 2), (W / 2, -T / 2), (W / 2, T / 2), (-W / 2, T / 2))]
        ax.add_patch(Polygon(corners, closed=True, fc="#F3EEE6" if faint else "#D9CBB6", ec=INK, lw=1.2))
        if not faint:
            for (x, z), r in clasts:
                ax.add_patch(Circle(rot(x, z, deg), r * ENL, fc="#3B4A63", ec="none"))
        ax.set(xlim=(-7, 7), ylim=(-8.6, 9.6), aspect="equal")
        ax.axis("off")

    def profile(ax, deg, y0, color):
        """−ln T across the camera after a rotation deg: Σ integrated along the beam (z) on a fine grid."""
        g = np.linspace(-5, 5, 1001)
        X, Z = np.meshgrid(g, g, indexing="ij")              # camera frame: X across, Z along the beam
        th = np.radians(-deg)
        x, z = X * np.cos(th) + Z * np.sin(th), -X * np.sin(th) + Z * np.cos(th)     # back to the piece's frame
        mu = np.where((np.abs(x) <= W / 2) & (np.abs(z) <= T / 2), S_MAT, 0.0)
        for (cx, cz), r in clasts:
            mu = np.where((x - cx) ** 2 + (z - cz) ** 2 <= r ** 2, S_CL, mu)
        p = mu.sum(axis=1) * (g[1] - g[0])
        ax.plot([-6.5, 6.5], [y0, y0], color=GREY, lw=3)
        ax.plot(g, y0 + 0.3 + 9.0 * p, color=color, lw=1.8)

    for k, deg in enumerate((0, 60)):
        ax = axs[k]
        sample(ax, deg)
        for x in np.linspace(-6, 6, 9):
            ax.annotate("", xy=(x, 5.0), xytext=(x, -7.0), arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=0.8,
                                                                         alpha=0.6))
        profile(ax, deg, 5.4, RED)
        ax.text(0, -8.3, "neutron beam" if k == 0 else "the stage turns", ha="center",
                color=TEAL if k == 0 else ORANGE, fontsize=10)
    axs[0].text(-6.6, 7.4, "camera:\nattenuation", ha="left", va="bottom", fontsize=9.5, color=INK)
    axs[0].text(4.6, 7.4, "two clasts one behind\nthe other: one peak", ha="center", fontsize=9.5, color=RED)
    axs[0].set_title("A radiograph adds up\neverything along the beam", color=INK, fontsize=12.5, fontweight="bold")
    axs[1].annotate("", xy=(3.0, -6.4), xytext=(-3.0, -6.4),
                    arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.8, connectionstyle="arc3,rad=0.35"))
    axs[1].text(4.6, 7.4, "turned by 60°:\ntwo peaks", ha="center", fontsize=9.5, color=RED)
    axs[1].set_title("Turning the sample: the clasts\nseparate in the projections", color=INK, fontsize=12.5,
                     fontweight="bold")

    ax = axs[2]
    sample(ax, 0, faint=True)
    for deg in np.arange(0, 180, 12):
        th = np.radians(deg)
        d = np.array([-np.sin(th), np.cos(th)])              # beam direction in the piece's frame
        n = np.array([np.cos(th), np.sin(th)])               # detector axis
        for (x, z), r in clasts:
            s_ = x * n[0] + z * n[1]
            a, b = s_ * n - 5 * d, s_ * n + 5 * d
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#3B4A63", lw=6 * r * ENL, alpha=0.07, solid_capstyle="butt")
    for (x, z), r in clasts:
        ax.add_patch(Circle((x, z), r * ENL + 0.15, fc="none", ec=RED, lw=1.4, ls="--"))
    ax.text(0, -8.3, "each projection smeared back along its beam:\nthe lines cross where the clasts are",
            ha="center", fontsize=10, color=INK)
    ax.set_title("Back-projection gives\nthe slice back", color=INK, fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.text(0.5, 0.03, "Tomography, seen from above: one horizontal slice of the piece of NWA 7034 (8 mm × 2 mm). "
             "H-rich clasts (about 0.3 mm) drawn 3 times larger; attenuation as measured at ICON.",
             ha="center", fontsize=11.5, color="#5B6779")
    _save(fig, "meteorite_tomography.png")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("alpha edges:", [(h, round(l, 3)) for h, l in ALPHA], " gamma edges:", [(h, round(l, 3)) for h, l in GAMMA])
    iron()
    sans()
    steel_strain()
    steel_lattice()
    bragg_edge_explained()
    meteorite_tomography()
    print("written", OUT)
