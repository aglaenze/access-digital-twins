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
