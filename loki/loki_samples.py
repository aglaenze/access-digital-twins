"""Virtual samples of the LoKI twin: differential cross-sections dΣ/dΩ(Q) in absolute units [cm⁻¹ sr⁻¹].

Each function returns (q [Å⁻¹], dΣ/dΩ [cm⁻¹ sr⁻¹], parameters). Lengths in Å, scattering length densities (SLD) in
10⁻⁶ Å⁻² (usual values, e.g. from the NIST SLD calculator).
"""
import numpy as np

SLD = {"D2O": 6.36, "H2O": -0.56, "silica": 3.47}       # 10⁻⁶ Å⁻²
Q_MAX_TABLE = 2.15          # Å⁻¹: beyond 60° of scattering at 3 Å (covers the front banks)


def q_grid(q_min=1e-4, q_max=Q_MAX_TABLE, n=6000):
    """Logarithmic Q grid. ≥ 6000 points: with fewer, the log-log interpolation of the McStas component fills in the
    sharp minima of a monodisperse sphere curve (-1 %)."""
    return np.logspace(np.log10(q_min), np.log10(q_max), n)


def sphere_form_factor(q, radius):
    """P(Q) of a homogeneous sphere, normalized to 1 at Q = 0: [3 (sin x - x cos x) / x³]², x = Q R."""
    x = np.asarray(q) * radius
    with np.errstate(invalid="ignore", divide="ignore"):
        f = np.where(x > 1e-6, 3 * (np.sin(x) - x * np.cos(x)) / x ** 3, 1.0 - x ** 2 / 10)
    return f ** 2


def silica_spheres(radius=50.0, phi=0.01, background=0.05, q=None):
    """Monodisperse silica spheres (radius [Å], volume fraction phi) dispersed in D₂O, dilute (no structure factor),
    plus a flat incoherent background [cm⁻¹ sr⁻¹]:

        dΣ/dΩ(Q) = φ V Δρ² P(Q) + background,   V = 4/3 π R³,   Δρ = ρ(D₂O) - ρ(silica) = 2.89·10⁻⁶ Å⁻².

    Units: φ V Δρ² with V in cm³ and Δρ in cm⁻² gives cm⁻¹ (1 Å = 10⁻⁸ cm, 10⁻⁶ Å⁻² = 10¹⁰ cm⁻²).
    R = 50 Å, φ = 1 %: I(0) = 4.37 cm⁻¹; zeros of P(Q) at Q R = 4.493, 7.725 -> Q = 0.090, 0.155 Å⁻¹;
    radius of gyration Rg = √(3/5) R = 38.7 Å (Guinier region Q < 1.3/Rg = 0.034 Å⁻¹)."""
    q = q_grid() if q is None else np.asarray(q)
    drho = (SLD["D2O"] - SLD["silica"]) * 1e10                   # cm⁻²
    volume = 4 / 3 * np.pi * (radius * 1e-8) ** 3                # cm³
    i0 = phi * volume * drho ** 2
    return q, i0 * sphere_form_factor(q, radius) + background, dict(radius=radius, phi=phi, background=background,
                                                                     i0=i0, drho=drho)


def d2o(background=0.05, q=None):
    """The solvent alone, D₂O in the same cell (the "background" measurement of a SANS experiment): its flat incoherent
    scattering, the same as in silica_spheres. Subtracting it leaves the scattering of the spheres alone (the 1 % of
    volume they take from the solvent is neglected)."""
    q = q_grid() if q is None else np.asarray(q)
    return q, np.full_like(q, background), dict(background=background)


SAMPLES = {
    # name: (function, keyword arguments, thickness [m], mu_abs [1/m at 1.798 Å], mu_rem [1/m])
    "silica_spheres": (silica_spheres, {}, 1e-3, 0.0, 0.0),
    "d2o": (d2o, {}, 1e-3, 0.0, 0.0),
    # nothing in the beam: the "empty beam" measurement (transmission reference of the reduction)
    "empty_beam": (None, {}, 0.0, 0.0, 0.0),
}
