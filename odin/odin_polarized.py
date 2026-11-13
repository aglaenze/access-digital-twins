"""Polarized neutron imaging with the ODIN twin: the magnetic field inside a sample turns the spin of the neutrons.

A neutron of wavelength λ crossing a field B over a length L has its spin turned about B by the angle

    φ = c λ B L,     c = |γ_n| m_n / h = 4.632 × 10¹⁴ T⁻¹ m⁻²   (46 320 rad per T, m and Å)

A polarizer before the sample sets the spin along i (x, y or z, + or −), an analyzer after it lets through the
neutrons whose spin is along j: the image of the polarization matrix P_ij(x, y) = (I(+i, j) − I(−i, j)) / (I(+i, j) +
I(−i, j)) shows the field integrated along each line of sight (Sales et al. 2018; Qvistgaard et al. 2026).

Two samples, each made of a field map B(x, y, z) on a grid (and an attenuation map):
  * solenoid   the aluminium solenoid of M. Sales et al., Three Dimensional Polarimetric Neutron Tomography of
               Magnetic Fields, Sci. Rep. 8, 2214 (2018), measured at RADEN (J-PARC): length 1.55 cm, radius 0.55 cm,
               wire 0.1 cm, 13.5 windings, 0.6 A, axis along x tilted by about 9° in the xz plane; its field is
               computed here by the Biot–Savart law along the helix of the wire (as in the paper);
  * nwa7034    the magnetized fragment of the Martian meteorite NWA 7034 (10 × 13 × 2 mm³) of C. Qvistgaard et al.,
               Geochem. Geophys. Geosyst. 27, e2025GC012641 (2026), measured at RADEN: the field reconstructed by the
               authors from their data (DTU Data, doi:10.11583/DTU.30775208, CC BY 4.0), 80³ voxels of 0.186 mm.

    P = polarization_matrix("solenoid", rot_deg=0, lam=3.2)     # (3, 3, ny, nx): P[i, j] on the grid of the sample
"""
import functools
import os

import numpy as np

import odin_paths  # noqa: F401  (sets sys.path)
import odin_hybrid as hy
import odin_mcstas as tw

HERE = os.path.dirname(os.path.abspath(__file__))
C_LARMOR = 1.83247171e8 / 3956.034            # [rad / (T m Å)]: φ = C_LARMOR · λ[Å] · ∫B dl [T m]
GAMMA_SIGN = -1.0                              # the neutron's moment is opposite to its spin (sense of rotation)
P0 = (22 - 1) / (22 + 1)                       # beam polarization × analyzer efficiency: flipping ratio 22 (Sales 2018)
POL_TRANSMISSION = 0.32                        # polarizer and analyzer: share of the unpolarized neutrons passed
QV_DIR = os.path.join(HERE, "samples", "data")
QV_FILE = os.path.join(QV_DIR, "nwa7034_qvistgaard2026.npz")


# --------------------------------------------------------------------------- field maps
def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


@functools.lru_cache(maxsize=2)
def solenoid_field(n=96, size_m=0.0192, tilt_deg=9.0, length=0.0155, radius=0.0055, turns=13.5, current=0.6,
                   leads=True):
    """B (n, n, n, 3) [T] of the solenoid of Sales et al. (2018) on a cube of side size_m (axes x, y, z; y vertical,
    z along the beam at 0°), by the Biot–Savart law over segments of 0.1 mm of the helix (and of the two leads that
    go up from its ends, along +y, out of the grid); also its wire (attenuation) map. Kept on disk after the first
    computation (about a minute)."""
    tag = f"solenoid_n{n}_s{size_m * 1e3:.1f}_t{tilt_deg:g}_l{int(leads)}"
    path = os.path.join(_run_root(), "polarized", tag + ".npz")
    if os.path.isfile(path):
        z = np.load(path)
        return z["B"], z["wire"], float(z["voxel"])
    mu0 = 4e-7 * np.pi
    s = np.linspace(0, 1, int(2 * np.pi * radius * turns / 1e-4) + 1)          # segments of about 0.1 mm
    th = 2 * np.pi * turns * s
    pts = np.c_[length * (s - 0.5), radius * np.cos(th), radius * np.sin(th)]  # axis along x
    if leads:                                                                   # the leads, up to the holder
        up = np.linspace(0, 0.02, 200)
        a, b = pts[0], pts[-1]
        pts = np.r_[np.c_[np.full(200, a[0]), a[1] + up[::-1], np.full(200, a[2])], pts,
                    np.c_[np.full(200, b[0]), b[1] + up, np.full(200, b[2])]]
    t = np.radians(tilt_deg)                                                    # tilted in the xz plane
    R = np.array([[np.cos(t), 0, np.sin(t)], [0, 1, 0], [-np.sin(t), 0, np.cos(t)]])
    pts = pts @ R.T
    mid, dl = 0.5 * (pts[1:] + pts[:-1]), np.diff(pts, axis=0)
    c = (np.arange(n) - (n - 1) / 2) * size_m / n
    X, Y, Z = np.meshgrid(c, c, c, indexing="ij")
    P = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    B = np.zeros_like(P)
    for q in range(0, len(P), 4096):                                           # in blocks of points and segments
        Pq = P[q:q + 4096]
        for k in range(0, len(mid), 512):
            r = Pq[:, None, :] - mid[None, k:k + 512, :]
            d3 = np.maximum(np.sqrt(np.einsum("ijk,ijk->ij", r, r)), 0.5e-3) ** 3   # inside the wire: no singularity
            B[q:q + 4096] += np.einsum("ijk,ij->ik", np.cross(dl[None, k:k + 512, :], r), 1.0 / d3)
    B *= mu0 * current / (4 * np.pi)
    B = B.reshape(n, n, n, 3)
    # the wire: voxels within 0.5 mm of the helix (aluminium, for the attenuation image)
    wire = np.zeros((n, n, n), bool)
    vox = size_m / n
    idx = np.rint(pts / vox + (n - 1) / 2).astype(int)
    ok = np.all((idx >= 0) & (idx < n), axis=1)
    wire[tuple(idx[ok].T)] = True
    from scipy.ndimage import binary_dilation
    wire = binary_dilation(wire, iterations=max(1, int(round(0.5e-3 / vox))))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, B=B.astype(np.float32), wire=wire, voxel=vox)
    return B.astype(np.float32), wire, vox


@functools.lru_cache(maxsize=1)
def nwa7034_field():
    """B (80, 80, 80, 3) [T] and the attenuation per voxel (80, 80, 80) of the fragment of NWA 7034 of Qvistgaard et
    al. (2026), as reconstructed by the authors; axes (x, y, z), y vertical (rotation axis), z the beam at 0°."""
    z = np.load(QV_FILE)
    return z["B"].astype(np.float32), z["mu_voxel"].astype(np.float32), float(z["voxel"])


def sample_maps(name):
    """(B [T], attenuation per voxel (−ln T contribution), voxel [m]) of a polarized-imaging sample."""
    if name == "solenoid":
        B, wire, vox = solenoid_field()
        sigma_al = 0.10e2                                     # [1/m]: aluminium, about 0.1 cm⁻¹
        return B, wire.astype(np.float32) * sigma_al * vox, vox
    if name == "nwa7034":
        return nwa7034_field()
    if name == "empty":                                      # no sample: no field, no attenuation
        return np.zeros((8, 8, 8, 3), np.float32), np.zeros((8, 8, 8), np.float32), 0.0025
    raise ValueError(f"no field map for {name}")


# --------------------------------------------------------------------------- the spin through the sample
def _rotate_sample(B, mu, rot_deg):
    """The sample turned by rot_deg about the vertical axis y: positions and field vectors."""
    if abs(rot_deg) < 1e-9:
        return B, mu
    from scipy.ndimage import rotate
    # positions: rotate in the (x, z) plane (axes 0 and 2 of the arrays)
    Br = np.stack([rotate(B[..., k], rot_deg, axes=(2, 0), reshape=False, order=1) for k in range(3)], axis=-1)
    mur = rotate(mu, rot_deg, axes=(2, 0), reshape=False, order=1)
    t = np.radians(rot_deg)                     # vectors: the same rotation (x, z) -> (x cos + z sin, −x sin + z cos)
    bx, bz = Br[..., 0].copy(), Br[..., 2].copy()
    Br[..., 0], Br[..., 2] = np.cos(t) * bx + np.sin(t) * bz, -np.sin(t) * bx + np.cos(t) * bz
    return Br, mur


def spin_through(B, lam, voxel):
    """Final spin for each initial direction i (x, y, z) after crossing the field map along z, voxel by voxel
    (rotation about the local field by c λ |B| voxel; Rodrigues' formula). Returns P (3, 3, nx, ny):
    P[i, j] = component j of the final spin when the initial spin is along i."""
    x = GAMMA_SIGN * C_LARMOR * lam * voxel
    nB = np.linalg.norm(B, axis=-1, keepdims=True)
    u = B / np.where(nB == 0, 1, nB)
    th = x * nB
    c, s = np.cos(th), np.sin(th)
    out = np.zeros((3, 3) + B.shape[:2])
    for i in range(3):
        P = np.zeros(B.shape[:2] + (3,))
        P[..., i] = 1
        for k in range(B.shape[2]):
            uk = u[:, :, k]
            P = P * c[:, :, k] + np.cross(uk, P) * s[:, :, k] + uk * np.sum(uk * P, -1, keepdims=True) * (1 - c[:, :, k])
        out[i] = np.moveaxis(P, -1, 0)
    return out


@functools.lru_cache(maxsize=32)
def polarization_maps(name, rot_deg, lams):
    """(P (n_lam, 3, 3, nx, ny), transmission (nx, ny), voxel) of a sample turned by rot_deg, for the wavelengths
    lams (tuple, Å)."""
    B, mu, vox = sample_maps(name)
    B, mu = _rotate_sample(np.asarray(B, float), np.asarray(mu, float), rot_deg)
    P = np.array([spin_through(B, lam, vox) for lam in lams])
    return P, np.exp(-mu.sum(axis=2)), vox


def to_camera(img, voxel, n_cam=128, field_m=0.0141):
    """A map on the grid of the sample (axes x, y; voxel) resampled on the camera (n_cam × n_cam over field_m,
    rows y, columns x)."""
    from scipy.ndimage import map_coordinates
    n = img.shape[0]
    c = (np.arange(n_cam) - (n_cam - 1) / 2) * field_m / n_cam / voxel + (n - 1) / 2
    X, Y = np.meshgrid(c, c)                        # rows y, columns x
    return map_coordinates(img, [X, Y], order=1, mode="constant", cval=np.nan)


# --------------------------------------------------------------------------- the images of a polarized measurement
SPINS = {"+x": (0, 1), "-x": (0, -1), "+y": (1, 1), "-y": (1, -1), "+z": (2, 1), "-z": (2, -1)}
AXES = {"x": 0, "y": 1, "z": 2}


def _camera_maps(field, rot_deg, lams, bins, area):
    """P (n_lam, 3, 3, bins, bins) and the transmission (bins, bins) on the camera: outside the map of the sample,
    no field (the spin keeps its direction: P = identity) and no attenuation."""
    P, T, vox = polarization_maps(field, round(float(rot_deg), 3), tuple(round(float(l), 4) for l in lams))
    n_lam = len(lams)
    out = np.empty((n_lam, 3, 3, bins, bins))
    for k in range(n_lam):
        for i in range(3):
            for j in range(3):
                m = to_camera(P[k, i, j], vox, bins, area)
                out[k, i, j] = np.where(np.isnan(m), float(i == j), m)
    Tc = to_camera(T, vox, bins, area)
    return out, np.where(np.isnan(Tc), 1.0, Tc)


def measurement(model, field, rot_deg, polarizer, spin_in, spin_out, t, beam_factor=1.0, rng=None, bins=128,
                n_lam=16, lam_range=(1.5, 6.0), lam_abs=8.0):
    """The counts of the Timepix3 camera sorted by wavelength (time of flight), (n_lam, bins, bins), and the centers
    of the wavelength bins: the beam of the hybrid model `model` (spectrum, profile of the beam, L/D blur), through
    the polarizer (polarizer "in": the spin along spin_in, e.g. "+x"; the share POL_TRANSMISSION of the neutrons
    passes), the field of the sample (rotation of the spin), the analyzer (only the spin along +spin_out passes):

        N = N_beam(λ) · T · POL_TRANSMISSION · ½ (1 + P0 · s · P[i, j](λ))

    with s the sign of spin_in. polarizer "out": no polarizer, no analyzer (an ordinary wavelength-resolved image)."""
    from odin_nexus import efficiency
    from scipy.ndimage import gaussian_filter
    rng = rng or np.random.default_rng()
    x0, x1, y0, y1 = model.field
    lamS = model.S["lam"].astype(float)
    edges = np.linspace(lam_range[0], lam_range[1], n_lam + 1)
    wl = np.histogram(lamS, edges, weights=model.r * efficiency(lamS, lam_abs))[0]
    lc = 0.5 * (edges[1:] + edges[:-1])
    xc = x0 + (np.arange(bins) + 0.5) * (x1 - x0) / bins
    yc = y0 + (np.arange(bins) + 0.5) * (y1 - y0) / bins
    X, Y = np.meshgrid(xc, yc)
    f = hy.profile(model.c_f, X.ravel(), Y.ravel()).reshape(bins, bins)
    f = f / f.sum()
    P, T = _camera_maps(field, rot_deg, lc, bins, x1 - x0)
    if polarizer == "in":
        i, s = SPINS[spin_in]
        j = AXES[spin_out]
        share = POL_TRANSMISSION * 0.5 * (1 + P0 * s * P[:, i, j])
    else:
        share = np.ones((n_lam, bins, bins))
    mean = wl[:, None, None] * t * beam_factor * f[None] * T[None] * share
    L = tw.Z_SAMPLE - tw.Z_PINHOLE
    sigma = np.hypot(tw.DET_DIST * model.D / L / np.sqrt(12), 0.055e-3) / ((x1 - x0) / bins)      # [pixels]
    mean = np.array([gaussian_filter(m, sigma, mode="nearest") for m in mean])
    return rng.poisson(mean), lc


def polarization(counts_plus, counts_minus, min_counts=5):
    """P = (N+ − N−) / (N+ + N−) and its uncertainty, from the counts with the spin along +i and −i (same analyzer
    j); NaN where there are fewer than min_counts neutrons in all."""
    a, b = np.asarray(counts_plus, float), np.asarray(counts_minus, float)
    n = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        P = np.where(n >= min_counts, (a - b) / n, np.nan)
        dP = np.where(n >= min_counts, np.sqrt(np.maximum(1 - P ** 2, 0) / n), np.nan)
    return P, dP


# --------------------------------------------------------------------------- analysis of the files
def read(path):
    """(counts (n_lam, y, x), wavelengths [Å], attributes) of a polarized-imaging file."""
    import h5py
    with h5py.File(path, "r") as f:
        cam = f["entry/instrument/camera"]
        return cam["data"][()].astype(float), cam["wavelength"][()], dict(cam.attrs)


def matrix(files, P0=None, rebin=1):
    """The polarization matrix from the 18 files {(spin_in, spin_out): path} (or a list of paths: the attributes
    tell which is which): P (n_lam, 3, 3, y, x), its uncertainty, the wavelengths. P0: the polarization measured
    without sample (the result is divided by it); rebin: pixels added up in blocks of rebin × rebin."""
    if not isinstance(files, dict):
        d = {}
        for p in files:
            a = read(p)[2]
            d[(a["spin_in"], a["spin_out"])] = p
        files = d
    cube = {k: read(p) for k, p in files.items()}
    lam = next(iter(cube.values()))[1]
    n_lam, ny, nx = next(iter(cube.values()))[0].shape
    if rebin > 1:
        for k, (c, l, a) in cube.items():
            c = c[:, :ny // rebin * rebin, :nx // rebin * rebin]
            cube[k] = (c.reshape(n_lam, ny // rebin, rebin, nx // rebin, rebin).sum(axis=(2, 4)), l, a)
        ny, nx = ny // rebin, nx // rebin
    P = np.full((n_lam, 3, 3, ny, nx), np.nan)
    dP = np.full_like(P, np.nan)
    for i, a in enumerate("xyz"):
        for j, b in enumerate("xyz"):
            if (f"+{a}", b) in cube and (f"-{a}", b) in cube:
                P[:, i, j], dP[:, i, j] = polarization(cube[(f"+{a}", b)][0], cube[(f"-{a}", b)][0])
    if P0:
        P, dP = P / P0, dP / P0
    return P, dP, lam


def rotation_angle(P):
    """The angle φ by which the spin has turned, from a polarization matrix that is a rotation (P0 divided out):
    trace = 1 + 2 cos φ. P (..., 3, 3, ...) with the matrix axes at -4, -3 (as matrix() returns them)."""
    tr = P[..., 0, 0, :, :] + P[..., 1, 1, :, :] + P[..., 2, 2, :, :]
    return np.arccos(np.clip((tr - 1) / 2, -1, 1))


def rotation_axis(P):
    """The unit vector of the axis of the rotation (the direction of the field, up to its sign), from the
    antisymmetric part of P: (P_zy − P_yz, P_xz − P_zx, P_yx − P_xy). Returns (..., 3, y, x)."""
    v = np.stack([P[..., 2, 1, :, :] - P[..., 1, 2, :, :], P[..., 0, 2, :, :] - P[..., 2, 0, :, :],
                  P[..., 1, 0, :, :] - P[..., 0, 1, :, :]], axis=-3)
    n = np.linalg.norm(v, axis=-3, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return -GAMMA_SIGN * v / n


def field_integral(lam, phi, lam_range=(2.0, 5.0)):
    """∫B dl [T m] along each line of sight: the slope of φ = C_LARMOR λ ∫B dl, fitted through zero over lam_range
    (φ: (n_lam, ...) from rotation_angle)."""
    k = (lam >= lam_range[0]) & (lam <= lam_range[1])
    L = lam[k].reshape((-1,) + (1,) * (phi.ndim - 1))
    ph = np.nan_to_num(phi[k])
    return np.sum(L * ph, axis=0) / np.sum(L * L, axis=0) / C_LARMOR


def true_field_integral(name, rot_deg=0.0, bins=64, field_m=0.0141):
    """|∫B dl| [T m] along the beam on the camera (bins × bins, rows y, columns x), from the field map of the sample
    itself (no measurement): the answer a measurement should find (Biot–Savart for the solenoid, the reconstruction
    of the authors for the fragment)."""
    B, mu, vox = sample_maps(name)
    B, mu = _rotate_sample(np.asarray(B, float), np.asarray(mu, float), rot_deg)
    J = np.linalg.norm(B.sum(axis=2) * vox, axis=-1)
    m = to_camera(J, vox, bins, field_m)
    return np.where(np.isnan(m), 0.0, m)
