"""Texts shared by the guided pages (the generators of the exercises), so that every exercise says them the same way.

    from page_texts import transmission_md, measurement_table
    md(transmission_md("sample out: stage at 500 mm"))
    md(measurement_table([("A1", "dark", "standard", "closed", "in", "10 s"), ...],
                         ("Step", "Image", "Setup", "Shutter", "Sample", "Exposure")))
"""


def transmission_md(open_beam_how="the sample moved out of the beam", per_wavelength=False):
    """Why a transmission needs three images (sample, open beam, dark), before the student operates the instrument."""
    per = (" (and, with the time of flight, for each wavelength)" if per_wavelength else "")
    return f"""
**Why three images?** The camera does not measure the transmission $T$ directly: it counts, in each pixel, what
arrives. To get $T$, three images are needed:

- the **sample** image $I$: the neutrons that crossed the sample;
- the **open beam** $O$ ({open_beam_how}): the same beam without the sample. The beam is not perfectly even over the
  field, and the pixels are not all equally sensitive: the open beam records both, so that they can be divided out;
- the **dark** $D$ (shutter closed, no neutrons): the camera gives a small signal even without neutrons (its offset and
  noise), which must be taken away from the two others.

Then, for each pixel{per}, with each image counted per second of exposure,

$$T = \\frac{{I - D}}{{O - D}}$$

Everything that is not the sample cancels: $T$ = 1 where nothing is stopped, $T$ = 0 where everything is.
"""


def measurement_table(rows, header):
    """The measurements to take and their settings, as a Markdown table (the BSc pages, section "Operate")."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(lines)
