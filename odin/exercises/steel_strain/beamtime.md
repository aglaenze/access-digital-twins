# Beamtime on ODIN: lattice strain of a steel specimen under load

**Your role**: the engineer of a team that designs steel parts for a wind turbine. The team needs to know how the
crystal lattice of its steel is strained under load, inside the part, and how well ODIN can measure it.

## Your proposal (accepted)

**Proposal 1240**: *"Lattice strain of a steel specimen under load by Bragg-edge imaging"*

A flat tensile specimen of ferritic steel (5 mm thick; a narrow gauge, 4 mm wide, between two wide shoulders, 8 mm)
is held in a load frame on the sample stage of ODIN (device `load`, in kN, up to 16 kN). The beamtime committee asks
for:

1. the strain of the lattice along the beam in the gauge and in the shoulders, at two loads at least, with their
   uncertainties;
2. Poisson's ratio of the steel (Young's modulus E = 210 GPa, from a tensile test), with its uncertainty;
3. the size of the systematic errors you found, and how you dealt with them;
4. a short logbook: which measurements you made, why, and with which settings.

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **15 minutes of beam** (counting time with the shutter open).
- Nobody tells you the settings: chopper mode, pinhole, counting times, which references a strain needs. Justify each
  choice in your logbook. The steel must stay elastic: never above 16 kN.
- Mistakes are allowed, as at a real instrument. Check your data as you go.

## How to

1. Click **Open NICOS** (in your starter notebook): the NICOS window of ODIN opens, ready.
2. Tab *Experiment*: **Find my proposal**, choose **1240**, then **Apply**: the specimen is mounted in its load frame.
3. Record data with `nexusfile_open`, e.g. `move(load, 8)` then `with nexusfile_open('steel 8 kN'): count(t=60)`.
   Your files go to `data/odin/<year>/1240/raw`; each file holds the force of the frame.
4. Analyze them with the **starter notebook**. The tools are there; the decisions are yours.
