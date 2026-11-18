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


BRAGG_EDGES = r"""
**What is a Bragg edge?** You may know **Bragg's law** from X-ray diffraction: a family of planes of atoms, a
distance $d$ apart, reflects a wave of wavelength $\lambda$ when

$$\lambda = 2d\sin\theta$$

with $\theta$ the angle between the wave and the planes (the wave is deviated by $2\theta$). A piece of metal is a
**polycrystal**: millions of small grains, turned in all directions. For any wavelength shorter than $2d$, some grains
are turned just right, and they scatter some neutrons **out of the beam**: the beam that comes through, the
transmission, is a little weaker. The longer the wavelength, the larger the angle $\theta$, until $\theta$ = 90° (the
neutrons sent straight back) at $\lambda = 2d$. Since $\sin\theta$ cannot exceed 1, for $\lambda > 2d$ **no grain at all**
can reflect them: this scattering stops at once, and the transmission **jumps up**. That jump, at $\lambda = 2d$, is a
**Bragg edge**. Each family of planes gives one; the last one (the longest wavelength) belongs to the planes farthest
apart.

So by measuring the transmission against the wavelength (the time of flight), ODIN reads the distances $d$ of the
crystal: the same information as a diffraction pattern, but in the direct beam, and in every pixel of an image.

*For X-ray users:* this is **not** an absorption edge. The K or L edges of X-rays come from the electrons of one
element, at an energy fixed by that element. A Bragg edge comes from the **arrangement** of the atoms: it tells the
crystal structure, and it moves when the crystal is strained.
"""


def insert_bragg_edges(cells, marker):
    """Puts the explanation of the Bragg edges (text, then the figure bragg_edge_explained) in the page, just before
    `marker` (a text in a markdown cell; the cell is split there)."""
    import nbformat as nbf
    from nbfig import figure_cell
    k = next(i for i, c in enumerate(cells) if c.cell_type == "markdown" and marker in c.source)
    src = cells[k].source
    j = src.index(marker)
    before, after = src[:j].rstrip(), src[j:]
    new = [nbf.v4.new_markdown_cell(BRAGG_EDGES.strip()),
           figure_cell("bragg_edge_explained.png", "Left: Bragg's law; the longer the wavelength, the larger the "
                       "angle, up to 90° at λ = 2d. Right: the transmission of 1 cm of α-iron against the wavelength "
                       "(NCrystal): each family of planes gives a jump, a Bragg edge; the last one at 4.05 Å."),
           nbf.v4.new_markdown_cell(after)]
    if before:
        cells[k].source = before
        cells[k + 1:k + 1] = new
    else:
        cells[k:k + 1] = new
    return cells


def measurement_table(rows, header):
    """The measurements to take and their settings, as a Markdown table (the BSc pages, section "Operate")."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(lines)
