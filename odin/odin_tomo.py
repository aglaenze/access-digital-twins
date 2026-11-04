"""Tomography brick of the ODIN digital twin: sinogram from the NeXus files of a rotation scan, then filtered
back-projection (FBP).

Chain: one NeXus file per angle (VirtualOdin.scan("stage_rot", angles, t)) -> essimaging (λ of each count)
-> for each angle: counts per (λ band, column x) in a horizontal slice y -> transmission T = (E - N)/(O - N) normalized
by the proton charge -> projection p = -ln T -> sinogram -> FBP -> μ(x, z).
Units: p is dimensionless, the reconstructed slice μ is in cm⁻¹ (= Σ_tot of the material, comparable to NCrystal).
"""
import numpy as np
import scipp as sc

import odin_reduction as red


def profiles(file, bands, x_edges_mm, y_slice_mm):
    """Counts per (λ band, column x) in the slice y_slice_mm = (ymin, ymax), plus duration and proton charge.
    bands: list of (λmin, λmax) in Å, possibly overlapping (e.g. white beam + narrow bands)."""
    ev = red._event_list(red.events(file))
    y = ev.coords["y"].values
    ev = ev[sc.array(dims=["event"], values=(y >= y_slice_mm[0]) & (y < y_slice_mm[1]))]
    xe = sc.array(dims=["x"], values=x_edges_mm, unit="mm")
    n = [ev.hist(wavelength=sc.array(dims=["wavelength"], values=[lo, hi], unit="angstrom"), x=xe).values[0]
         for lo, hi in bands]
    return dict(n=np.array(n), duration=red.duration(file), charge=red.proton_charge(file))


def sinogram(files, open_beam, dark, bands, x_edges_mm, y_slice_mm):
    """Projections p = -ln T, shape (λ band, angle, x), with their variance (Poisson, propagated)."""
    O = profiles(open_beam, bands, x_edges_mm, y_slice_mm)
    N = profiles(dark, bands, x_edges_mm, y_slice_mm) if dark else None

    def rate(P):
        n = P["n"] - (N["n"] * P["duration"] / N["duration"] if N else 0)
        var = P["n"] + (N["n"] * (P["duration"] / N["duration"]) ** 2 if N else 0)
        return n / P["charge"], var / P["charge"] ** 2

    o, vo = rate(O)
    p, vp = [], []
    for f in files:
        e, ve = rate(profiles(f, bands, x_edges_mm, y_slice_mm))
        e = np.clip(e, 1e-12, None)
        p.append(-np.log(e / o))
        vp.append(ve / e ** 2 + vo / o ** 2)       # var(ln T)
    return np.transpose(p, (1, 0, 2)), np.transpose(vp, (1, 0, 2))


def ramp_filter(sino, dx):
    """Ram-Lak ramp filter written in real space (Kak & Slaney, "Principles of Computerized Tomographic Imaging",
    eq. 3.61): h(0) = 1/(4 dx²), h(k odd) = -1/(π k dx)², h(k even) = 0, applied by convolution.
    Why not simply |f| in frequency space: sampling |f| sets the DC component of the discrete filter to zero and
    loses ~4 % on μ (checked on the iron plate, 2026-11-03)."""
    n = sino.shape[-1]
    k = np.arange(-(n - 1), n)
    h = np.zeros(len(k))
    h[k == 0] = 1 / (4 * dx * dx)
    odd = k % 2 == 1
    h[odd] = -1 / (np.pi * k[odd] * dx) ** 2
    m = 4 * n                                               # zero padding: linear, not circular, convolution
    H = np.fft.fft(np.roll(np.r_[h, np.zeros(m - len(h))], -(n - 1)))
    return np.real(np.fft.ifft(np.fft.fft(sino, m, axis=-1) * H, axis=-1))[..., :n] * dx


def fbp(sino, angles_deg, xs_mm):
    """Filtered back-projection of a sinogram (angle, x) over 180° -> slice μ(z, x) in cm⁻¹ (xs in mm).

    Convention: the stage rotates by +θ about the vertical axis; a point (x, z) of the object projects onto
    x·cos θ + z·sin θ (cf. odin_hybrid.box_path_length)."""
    dx = xs_mm[1] - xs_mm[0]
    filt = ramp_filter(np.asarray(sino), dx)
    X, Z = np.meshgrid(xs_mm, xs_mm)
    rec = np.zeros_like(X)
    for k, a in enumerate(np.radians(angles_deg)):
        rec += np.interp(X * np.cos(a) + Z * np.sin(a), xs_mm, filt[k], left=0, right=0)
    return rec * np.pi / len(angles_deg) * 10          # mm⁻¹ -> cm⁻¹
