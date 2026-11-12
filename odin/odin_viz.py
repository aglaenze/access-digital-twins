"""Visualizations of the ODIN digital twin (for the pages and for teaching).

* live_frames(): "live detector" replay of a measurement, read from its NeXus file: the image builds up neutron by
  neutron and the time-of-flight histogram fills, pulse after pulse, as on the live view of a real instrument;
* chopper_diagram(): time–distance diagram of the chopper cascade for a chopper mode (package `tof` of ESS);
* tomo_frames(): tomography that appears projection after projection (reconstruction with the angles measured so far);
* show_*(): matplotlib + ipywidgets players for the pages (Voilà).
"""
import h5py
import numpy as np

import odin_paths  # noqa: F401  (sets sys.path)

DET = "entry/instrument/timepix3"
N_NATIVE = 4096            # Timepix3 of the template: 4096 × 4096 pixels
PULSE_MS = 1e3 / 14.0


def live_frames(nexus_file, n_frames=24, n_pixels=128, toa_bins=150):
    """Cumulative detector images and time-of-flight histograms at n_frames moments of the measurement.

    Returns dict: images (n_frames, n_pixels, n_pixels) [counts], toa (n_frames, toa_bins) [counts],
    toa_edges [ms] (event_time_offset: time since the last pulse), times [s since the start], extent [mm].
    """
    with h5py.File(nexus_file, "r") as f:
        d = f[f"{DET}/data"]
        ids = d["event_id"][()]
        index = d["event_index"][()]
        etz = d["event_time_zero"][()]
        eto = d["event_time_offset"][()] * 1e-6                       # ns -> ms
        xo = f[f"{DET}/x_pixel_offset"][()]
    pulse = np.searchsorted(index, np.arange(len(ids)), side="right") - 1   # pulse index of each event
    ix, iy = (ids - 1) % N_NATIVE, (ids - 1) // N_NATIVE                    # detector_number = 1 + ix + 4096 iy
    b = N_NATIVE // n_pixels
    pix = (iy // b) * n_pixels + ix // b
    toa_edges = np.linspace(0, PULSE_MS, toa_bins + 1)
    tbin = np.clip(np.searchsorted(toa_edges, eto) - 1, 0, toa_bins - 1)
    cuts = np.linspace(0, len(index), n_frames + 1).astype(int)[1:]           # pulses reached at each frame
    images = np.zeros((n_frames, n_pixels * n_pixels))
    toa = np.zeros((n_frames, toa_bins))
    order = np.argsort(pulse, kind="stable")
    pulse, pix, tbin = pulse[order], pix[order], tbin[order]
    start = 0
    for k, c in enumerate(cuts):
        stop = np.searchsorted(pulse, c)
        images[k] = (images[k - 1] if k else 0) + np.bincount(pix[start:stop], minlength=n_pixels ** 2)
        toa[k] = (toa[k - 1] if k else 0) + np.bincount(tbin[start:stop], minlength=toa_bins)
        start = stop
    half = (xo[-1] - xo[0]) / 2 * 1e3
    times = (etz[np.minimum(cuts, len(etz) - 1)] - etz[0]) * 1e-9
    return dict(images=images.reshape(n_frames, n_pixels, n_pixels), toa=toa, toa_edges=toa_edges, times=times,
                extent=(-half, half, -half, half))


def chopper_diagram(mode="wfm", wfm_delta=0.30, distance=60.55, neutrons=60_000, ax=None, seed=1):
    """Time–distance diagram of the chopper cascade (package `tof`): neutron paths from the ESS pulse to the detector;
    gray: neutrons stopped by a chopper. mode: "wfm", "natural" or "white" (no chopper)."""
    import matplotlib.pyplot as plt
    import odin_mcstas as tw
    choppers = tw.chopper_table(mode, wfm_delta) if mode != "white" else {}
    res = tw.tof_run(choppers, distance, neutrons=neutrons, seed=seed)
    import matplotlib.transforms as mtransforms
    from matplotlib.ticker import FuncFormatter
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 5))
    fig = ax.figure
    before = set(fig.axes)
    res.plot(visible_rays=600, blocked_rays=3000, ax=ax)
    # Readability: tof writes one label per chopper, on top of each other where choppers are paired (WFM 1-2, FO + BP,
    # T0 alpha-beta). They are replaced by one short label per group, spread vertically, on the empty right side.
    for t in list(ax.texts):
        if t.get_text() not in ("detector", "Pulse"):
            t.remove()
    groups = []
    for c in sorted(choppers.values(), key=lambda c: c["distance"]):
        if groups and c["distance"] - groups[-1][0] < 1.0:
            groups[-1][1].append(_short_name(c["name"]))
        else:
            groups.append([c["distance"], [_short_name(c["name"])]])
    y_prev = -np.inf
    tr = mtransforms.blended_transform_factory(ax.transAxes, ax.transData)
    for d, names in groups:
        y = max(d, y_prev + 2.3)                      # at least 2.3 m between two labels
        ax.text(0.98, y, " + ".join(names) + f"  ({d:.1f} m)", transform=tr, ha="right", va="center", fontsize=7,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
        y_prev = y
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}"))
    ax.set_xlabel("Time [ms]")
    for cax in set(fig.axes) - before:                # color bar: tof places its label over the plot -> short title
        cax.set_ylabel("")
        cax.set_title("λ [Å]", fontsize=9)
    label = {"wfm": f"WFM, δ = {wfm_delta:.2f} m", "natural": "natural (band-pass + T0)", "white": "white beam (no chopper)"}
    ax.set_title(f"Time–distance diagram\n{label[mode]}")
    return ax


def _short_name(name):
    """Short chopper names for the diagrams: wfmc_1 -> WFM 1, fo_chopper_3 -> FO 3, bp_chopper2 -> BP 2, ..."""
    n = name.lower()
    if n.startswith("wfm"):
        return "WFM " + n[-1]
    if n.startswith("fo"):
        return "FO " + n[-1]
    if n.startswith("bp"):
        return "BP " + ("1" if "1" in n else "2")
    if n.startswith("t0"):
        return "T0 " + ("α" if "alpha" in n else "β")
    return name


def interleaved_order(n):
    """Bit-reversal order of n projections (0°, 90°, 45°, 135°, ...): any first k projections spread over 180°."""
    bits = max(1, int(np.ceil(np.log2(n))))
    rev = [int(format(i, f"0{bits}b")[::-1], 2) for i in range(2 ** bits)]
    return [r for r in rev if r < n]


def tomo_frames(sino, angles_deg, xs_mm, steps=None, order="sequential"):
    """Reconstructions with the first k projections (k in steps).

    order "sequential": in acquisition order (0°, 3°, 6°...): a limited angular range at first (streaks, wrong values);
    order "interleaved": bit-reversal order, so that the first projections already cover 180° (coarse but complete).
    Weight of each projection = the angle it represents: 180°/n in sequential order (the first k projections cover only
    k·180°/n), 180°/k in interleaved order (they already span 180°)."""
    import odin_tomo as to
    sino, ang = np.asarray(sino), np.asarray(angles_deg)
    n = len(ang)
    idx = np.arange(n) if order == "sequential" else np.array(interleaved_order(n))
    steps = steps or sorted({max(2, int(round(n * f))) for f in (0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0)})
    # odin_tomo.fbp weights each projection by π/k (projections spanning 180°)
    w = (lambda k: k / n) if order == "sequential" else (lambda k: 1.0)
    return steps, [to.fbp(sino[idx[:k]], ang[idx[:k]], xs_mm) * w(k) for k in steps]


# --------------------------------------------------------------------------- players (pages)
class LiveCount:
    """The detector image and the spectrum of arrival times, filling up during a count (VirtualOdin.count(...,
    progress=live.update)), as on the instrument; then the replay of the measurement (show_live) below them."""

    def __init__(self, field_mm=7.05):
        import ipywidgets as w
        from IPython.display import display
        self.extent = [-field_mm, field_mm, -field_mm, field_mm]
        self.status = w.Label("Counting...")
        self.out = w.Output()
        self.box = w.VBox([self.status, self.out])
        self._last = 0.0
        display(self.box)

    def update(self, image, toa, t_done, t_total, step):
        import time
        import matplotlib.pyplot as plt
        if step == "preparing":
            self.status.value = "Counting... (the first count of a session prepares the instrument: a few seconds)"
        elif step == "writing":
            self.status.value = f"Counted {t_total:.0f} s: writing the file..."
        else:
            self.status.value = f"Counting... {t_done:.0f} s / {t_total:.0f} s"
        if step == "counting" and t_done < t_total and time.time() - self._last < 0.8:
            return                                      # (drawing takes ~0.4 s: not more than about once a second)
        self._last = time.time()
        self.out.clear_output(wait=True)
        with self.out:
            fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[1, 1.4]))
            im = ax[0].imshow(image, origin="lower", extent=self.extent, cmap="inferno", vmin=0,
                              vmax=max(float(np.max(image)), 1.0))
            ax[0].set(xlabel="x (mm)", ylabel="y (mm)",
                      title=f"Detector after {t_done:.1f} s ({float(np.sum(image)):,.0f} neutrons)")
            fig.colorbar(im, ax=ax[0], label="counts per pixel")
            edges = np.linspace(0, PULSE_MS, len(toa) + 1)
            ax[1].step(0.5 * (edges[1:] + edges[:-1]), toa, where="mid", color="tab:blue")
            ax[1].set(xlabel="time since the last pulse (ms)", ylabel="counts", ylim=(0, max(float(np.max(toa)), 1) * 1.05),
                      title="Arrival times (raw data, before reduction)")
            ax[1].grid(alpha=0.3)
            plt.tight_layout(); plt.show()

    def done(self, nexus_file, n_frames=16):
        """The count is over: the file name, then the replay of the measurement (Play, slider)."""
        import os
        self.status.value = f"File written: {os.path.basename(nexus_file)}  (Play or the slider below: replay the count)"
        show_live(nexus_file, n_frames=n_frames, autoplay=False, start="last", into=self.out)



def show_live(nexus_file, n_frames=24, autoplay=True, fill_s=None, status=None, start="first", into=None):
    """Animated replay of a measurement in a notebook / Voilà page (Play button + slider); autoplay: it starts by
    itself, as the detector image of a real instrument fills up during the count.
    fill_s: the count itself, as on the instrument: the image and the spectrum fill up frame by frame for fill_s
    seconds of wall time (status: a Label showing "Counting... t s / T s"), then the Play button and the slider let
    the student replay it. start "last": shown at the end of the count. into: an Output to draw in (LiveCount)."""
    import time
    import ipywidgets as w
    import matplotlib.pyplot as plt
    from IPython.display import display
    fr = live_frames(nexus_file, n_frames=n_frames)
    vmax = max(fr["images"][-1].max(), 1)
    out = into if into is not None else w.Output()

    def draw(k):
        out.clear_output(wait=True)   # (outside the 'with': inside it, Voila can hang when the page loads)
        with out:
            fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[1, 1.4]))
            im = ax[0].imshow(fr["images"][k], origin="lower", extent=fr["extent"], cmap="inferno", vmin=0, vmax=vmax)
            ax[0].set(xlabel="x (mm)", ylabel="y (mm)", title=f"Detector after {fr['times'][k]:.1f} s "
                                                                f"({fr['images'][k].sum():,.0f} neutrons)")
            fig.colorbar(im, ax=ax[0], label="counts per pixel")
            c = 0.5 * (fr["toa_edges"][1:] + fr["toa_edges"][:-1])
            ax[1].step(c, fr["toa"][k], where="mid", color="tab:blue")
            ax[1].set(xlabel="time since the last pulse (ms)", ylabel="counts", ylim=(0, fr["toa"][-1].max() * 1.05),
                      title="Arrival times (raw data, before reduction)")
            ax[1].grid(alpha=0.3)
            plt.tight_layout(); plt.show()

    play = w.Play(min=0, max=n_frames - 1, step=1, interval=300, value=0)
    slider = w.IntSlider(min=0, max=n_frames - 1, value=0, description="frame")
    w.jslink((play, "value"), (slider, "value"))
    slider.observe(lambda ch: draw(ch["new"]), names="value")
    if fill_s:                       # the count: the frames one after the other, in real time
        play.disabled = slider.disabled = True
        display(w.VBox([w.HBox([play, slider]), out]))
        t0 = time.time()
        for k in range(n_frames):
            draw(k)
            if status is not None:
                status.value = f"Counting... {fr['times'][k]:.0f} s / {fr['times'][-1]:.0f} s"
            time.sleep(max(0.0, t0 + fill_s * (k + 1) / n_frames - time.time()))     # (drawing takes time too)
        slider.unobserve_all("value")
        slider.value = n_frames - 1
        slider.observe(lambda ch: draw(ch["new"]), names="value")
        play.value = n_frames - 1
        play.disabled = slider.disabled = False
        return
    if start == "last":
        slider.unobserve_all("value")
        slider.value = play.value = n_frames - 1
        slider.observe(lambda ch: draw(ch["new"]), names="value")
        draw(n_frames - 1)
    else:
        draw(0)
    display(w.HBox([play, slider]) if into is not None else w.VBox([w.HBox([play, slider]), out]))
    if autoplay and hasattr(play, "playing"):        # ipywidgets 8: the replay starts at once
        play.playing = True
