# Beamtime on ODIN: the atomic spacing of iron

**Your role**: the materials engineer of your company. Your steel supplier delivers plates sold as ferritic steel;
before your group checks real components, you must show that ODIN measures the plane spacing of steel reliably.

## Your proposal (accepted)

**Proposal 1234**: *"Lattice spacing of a ferritic steel component by Bragg-edge imaging"*

Steel parts are made of iron crystals. The distance between their atomic planes changes slightly when the part is
strained, or when the steel changes phase. Before measuring real components, your group must show that it can measure
the plane spacing *d* of a reference: a **5 mm iron plate**. The beamtime committee asks for:

1. the wavelength of the (110) Bragg edge, and *d*₁₁₀, with their uncertainties;
2. the lattice parameter *a* of iron, compared with the reference value 2.8665 Å;
3. a short logbook: which measurements you made, why, and with which settings.

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **15 minutes of beam** (counting time with the shutter open).
  Decide how to share it between your measurements before you start.
- Nobody tells you the settings. Choose them, and justify each choice in your logbook: chopper mode, pinhole,
  where the sample must be, counting times, which reference measurements a transmission needs.
- Mistakes are allowed, as at a real instrument. Check your data as you go.

## How to

1. Click **Open NICOS** (at the top of your starter notebook): the NICOS window of ODIN opens, ready.
2. Enter the proposal number **1234** in the *Experiment* panel. Without it NICOS does not record data, as at ESS.
3. Record data with `nexusfile_open`, e.g. `with nexusfile_open('my title'): count(t=60)`.
   Your files go to `data/odin/2026/1234/raw`.
4. Analyze them with the **starter notebook** (button *Starter notebook* of the catalogue). The tools are there; the
   decisions are yours.

**Samples**: the sample changer (`sample_holder`) holds the iron plate and other samples of the library (`sample_info()`
describes the one mounted). For your own questions you can also design a sample with the **sample builder**
(button *Sample builder* at the top of your starter notebook): it is saved with your proposal and appears on the sample changer.

The NICOS commands of the twin are listed in `nicos/README.md`; the physics of Bragg edges is explained in the guided
notebook `odin/ODIN_analysis.ipynb`, if you need it.
