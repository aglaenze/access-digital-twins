"""The folded section "Under the hood" of every guided page: what the raw data recorded in the NeXus files look like,
and how the analysis goes from them to the result shown on the page (with which software), plus a viewer of the
student's own files.

    import analysis_chain
    analysis_chain.section("odin_events", odin)     # Timepix3 events (time of flight): Bragg edges, strain...
    analysis_chain.section("odin_camera", odin)     # integrating camera images: radiography, tomography
    analysis_chain.section("loki", loki)            # SANS
"""
import html
import json
import os

import ipywidgets as w
from IPython.display import Markdown, display

TEXTS = {
"odin_events": r"""
**What a file holds.** Each measurement is one **NeXus** file (HDF5, the standard of neutron facilities), in the
layout of the real ODIN (the ESS template). The Timepix3 camera does not record a picture: it records **each
neutron**, as one *event*, in `entry/instrument/timepix3/...`:

- `event_id`: the number of the pixel it arrived in;
- `event_time_zero`: the time of the source pulse before it (14 pulses per second);
- `event_time_offset`: the time elapsed since that pulse, in nanoseconds: its **time of flight**.

The file also holds the state of the instrument during the count (choppers, pinhole, sample stage...) and the
**proton charge** of each pulse (`entry/instrument/source/pulse_charge`): how many protons hit the target, so how many
neutrons were made.

**The analysis chain**, the one of ESS:

1. **Read the events** with `scippnexus` (NeXus into `scipp` arrays: values with their units and uncertainties).
2. **Time of flight to wavelength**: the ESS package `essreduce` (inside `essimaging`, workflow
   `OdinBraggEdgeWorkflow`) turns each arrival time into a wavelength with a *lookup table* computed from the chopper
   settings and the distances read in the file (the time a neutron of each λ needs to reach the camera).
3. **Histogram**: the events are counted per pixel (or region) and per bin of wavelength.
4. **Normalize** each run by its proton charge, subtract the dark run (scaled to its duration).
5. **Divide by the open beam**: the transmission $T(\lambda) = (S - D)/(O - D)$, with its uncertainty (the Poisson
   noise of the three runs, propagated by `scipp`).

The pages call these steps for you (twin file `odin_reduction.py`: the ESS workflow, unmodified, plus steps 4 and 5).
""",
"odin_camera": r"""
**What a file holds.** Each image is one **NeXus** file (HDF5). The integrating camera (a scintillator screen filmed
by a camera) records **one picture**: the counts of each pixel, summed over the exposure, in
`entry/instrument/camera/data`, with the pixel positions (`x_pixel_offset`, `y_pixel_offset`); no time of flight, so
no wavelength. The file also holds the exposure time (`entry/duration`), the state of the instrument (shutter,
choppers, pinhole), the sample and the angle of the rotation stage (`entry/sample/rotation_angle`), and the proton
charge received during the image.

**The analysis chain:**

1. **Read** the images (`h5py`).
2. **Per second**: each image is divided by its exposure time.
3. **Transmission**: $T = (S - D)/(O - D)$ for each pixel, with the sample, open-beam and dark images.
4. **Tomography** (when there is one): for each row of pixels, $-\ln T$ at every angle forms a *sinogram*; it is
   filtered (ramp filter) and back-projected: this gives the attenuation coefficient $\Sigma$ at each point of the
   slice (filtered back-projection).

For these images the twin uses its own short code (`odin_radiography.py`, with `numpy`); at ESS the same steps are
done with the facility's imaging software.
""",
"odin_polarized": r"""
**What a file holds.** Each polarized image is one **NeXus** file (HDF5). The Timepix3 camera sorts the neutrons by
their time of flight, so the file holds a **cube of counts**: `entry/instrument/camera/data`, of shape
(wavelength, y, x), with the centers of the wavelength bins (`wavelength`, in Å, 16 bins from 1.5 to 6 Å) and the
pixel positions (`x_pixel_offset`, `y_pixel_offset`). The attributes of `entry/instrument/camera` record the state of
the instrument during the image: polarizer, `spin_in` (the direction the spin was turned to before the sample) and
`spin_out` (the direction the analyzer passes), choppers, pinhole. The file also holds the exposure time
(`entry/duration`), the sample and the angle of the stage (`entry/sample/rotation_angle`), and the proton charge.

**The analysis chain** of this page (twin file `odin_polarized.py`, with `numpy`):

1. **Read** the cube of each file and its `spin_in`, `spin_out` (`h5py`).
2. **Pair the images**: for each analyzer direction $j$, the images with the spin in along $+i$ and $-i$.
3. **Polarization**, pixel by pixel and wavelength by wavelength: $P_{ij} = (N_+ - N_-)/(N_+ + N_-)$, with its
   uncertainty from the counts (pixels with too few neutrons are left out); the 9 components form the matrix.
4. **Divide by $P_0$**, the polarization measured without the sample (what the polarizer and the analyzer do alone).
5. **Angle and axis of the rotation**: from the trace of the matrix, $1 + 2\cos\varphi$, and from its antisymmetric
   part (the direction of the field).
6. **Field**: the slope of $\varphi$ against $\lambda$ (2 to 5 Å), fitted through zero, gives $\int B\,\mathrm{d}l$
   along each line of sight.

These steps are the twin's own code (the method of Sales *et al.* 2018 and Qvistgaard *et al.* 2026), not a package
of ESS.
""",
"loki": r"""
**What a file holds.** Each measurement is one **NeXus** file (HDF5), in the layout of the real LoKI. The detectors
(thousands of straw tubes in banks) record **each neutron** as one *event*: `event_id` (the pixel: tube, straw,
position along it) and `event_time_offset` (its time of flight since the pulse). Two **monitors** record the beam too:
**m1** before the sample (the incident beam) and **m3** just after it (the transmitted beam). The file also holds the
chopper settings, the collimation and the detector distance.

**The analysis chain**, the one of ESS (package `esssans`, workflow `LokiWorkflow`):

1. **Read the events** (`scippnexus` into `scipp`).
2. **Time of flight to wavelength** with a lookup table of the chopper configuration (`essreduce`).
3. **Pixel to angle, then Q**: from the position of each pixel, its scattering angle $2\theta$, and
   $Q = 4\pi \sin\theta / \lambda$.
4. **Normalize** by the incident monitor m1, correct for the **transmission** (m3/m1 of the sample run, divided by
   the same ratio of the empty-beam run) and the solid angle of each pixel.
5. **Subtract the background** (the solvent run) and calibrate to absolute units: the cross-section $I(Q)$ in cm⁻¹.

The pages call these steps for you (twin file `loki_reduction.py`: the ESS workflow, unmodified).
""",
}


def _tree(path, max_lines=60):
    """The groups and datasets of a NeXus file: shape, type, units, a few values."""
    import h5py
    import numpy as np
    lines = []

    def visit(name, obj):
        if len(lines) >= max_lines:
            return
        depth = name.count("/")
        pad = "  " * depth
        base = name.split("/")[-1]
        if isinstance(obj, h5py.Group):
            cls = obj.attrs.get("NX_class", b"")
            cls = cls.decode() if isinstance(cls, bytes) else str(cls)
            lines.append(f"{pad}{base}/" + (f"   ({cls})" if cls else ""))
        else:
            units = obj.attrs.get("units", b"")
            units = units.decode() if isinstance(units, bytes) else str(units)
            if obj.shape == ():
                v = obj[()]
                v = v.decode() if isinstance(v, bytes) else v
                desc = f"= {v}"
            else:
                n = int(np.prod(obj.shape))
                first = obj[tuple(slice(0, min(3, s)) for s in obj.shape)] if n else []
                first = np.asarray(first).ravel()[:3]
                desc = f"{obj.dtype}, {' × '.join(map(str, obj.shape))} values" + \
                       (f", first: {', '.join(str(x) for x in first)}" if n else "")
            lines.append(f"{pad}{base}  {desc}" + (f"  [{units}]" if units else ""))

    with h5py.File(path, "r") as f:
        f.visititems(visit)
    if len(lines) >= max_lines:
        lines.append("  ... (more)")
    return "\n".join(lines)


def file_viewer(instrument):
    """Choose one of your files, see what is inside."""
    pick = w.Dropdown(description="Your file", layout=w.Layout(width="460px"), style={"description_width": "90px"})
    view = w.HTML()

    def update(_=None):
        opts = []
        try:
            with open(instrument.log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = (json.loads(line).get("details") or {})
                    except ValueError:
                        continue
                    if d.get("file"):
                        opts.append((f"{d['file']}: {d.get('title') or '(no title)'}", d["file"]))
        except (OSError, TypeError):
            pass
        pick.options = list(reversed(opts))

    def show(_=None):
        if not pick.value:
            view.value = "<i>No file yet: take a measurement first, then click Refresh.</i>"
            return
        try:
            t = _tree(os.path.join(instrument.folder, pick.value))
            view.value = f"<pre class='tw-status' style='max-height:420px;overflow:auto'>{html.escape(t)}</pre>"
        except Exception as e:
            view.value = f"<i>Cannot read it: {html.escape(str(e))}</i>"

    refresh = w.Button(description="Refresh", icon="refresh", layout=w.Layout(width="auto"))
    look = w.Button(description="Look inside", icon="search", layout=w.Layout(width="auto"))
    refresh.on_click(update)
    look.on_click(show)
    update()
    return w.VBox([w.HBox([pick, look, refresh]), view])


def section(kind, instrument, title="Under the hood: the raw data and the analysis chain (click to open)"):
    """The folded section: the explanation of `kind` (odin_events, odin_camera, loki) and the file viewer."""
    from page_output import collapsed
    with collapsed(title):
        display(Markdown(TEXTS[kind]))
        display(Markdown("**Look inside one of your files** (the groups and datasets of the NeXus file, with the first "
                         "values):"))
        display(file_viewer(instrument))
