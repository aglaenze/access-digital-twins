# Beamtime on ODIN: water in a Martian meteorite

**Your role**: the neutron specialist of a team of planetary scientists. The Martian meteorite NWA 7034 holds water
from early Mars, bound in some of its rock fragments (clasts). The team will drill out the richest clast for a
chemical analysis: it needs to know where it is, and how much water it holds, without cutting the meteorite.

## Your proposal (accepted)

**Proposal 1250**: *"Water in a Martian meteorite by neutron tomography"*

A cylinder of NWA 7034 (12 mm across, 12 mm high) is mounted on the rotation stage of ODIN. The committee asks for:

1. the clasts rich in water: how many, their positions and sizes (in mm, in the frame of the sample stage);
2. the proof that their extra attenuation is due to hydrogen;
3. the water content (% by mass) of the largest one, with its uncertainty (density of the clasts: 2.6 g/cm³);
4. a short logbook: which measurements, why, with which settings.

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **10 minutes of beam** (counting time with the shutter open).
- Two detectors: the integrating camera (`radiograph(t, title)`, `tomography(t, step)`: white-beam images, no time of
  flight) and the event camera Timepix3 (`count(t=...)` in a `nexusfile_open` block: time of flight).
- Nobody tells you the settings: chopper modes, pinhole, exposures, angular step, references. Justify each choice.

## How to

1. Click **Open NICOS** (in your starter notebook). Tab *Experiment*: **Find my proposal**, **1250**, **Apply**.
2. Measure; your files go to `data/odin/<year>/1250/raw`.
3. Analyze them with the **starter notebook**. The tools are there; the decisions are yours.
