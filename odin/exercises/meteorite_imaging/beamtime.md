# Beamtime on ODIN: water in a Martian meteorite

**Your role**: the neutron specialist of a team of planetary scientists. The Martian meteorite NWA 7034 holds water
from early Mars (about 6000 ppm), bound in its minerals. The team wants to know where it is and how much of it the
richest regions hold, without cutting the meteorite.

## Your proposal (accepted)

**Proposal 1250**: *"Water in a Martian meteorite by neutron tomography"*

The piece of NWA 7034 studied by E. B. Naver, K. W. Nikolajsen *et al.*, *Direct detection of hydrogen reveals a new
macroscopic crustal water reservoir on early Mars*, arXiv:2601.08390 (2026): 12 mm high, 8 mm wide, 2 mm thick,
mounted on the rotation stage of ODIN (its 2 mm thickness along the beam at 0°). The committee asks for:

1. the regions rich in hydrogen: where they are (in mm, in the frame of the sample stage), their sizes, how they are
   distributed;
2. the proof that their attenuation is due to hydrogen (compare with Table S1 of the paper: the minerals of NWA 7034);
3. the water content (% by mass) of the richest region, with its uncertainty and its biases (density of the region
   about 3.0 g/cm³);
4. a short logbook: which measurements, why, with which settings, and how you compare with the paper (ICON, PSI).

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **8 hours of beam** (counting time with the shutter open).
- Two cameras: the standard one (`radiograph(t, title)`: 128 pixels of 110 µm) and the high-resolution one
  (`radiograph(t, title, 512)`: 512 pixels of 27.5 µm); `tomography(t, step, title, pixels)`; and the event camera
  Timepix3 for time of flight (`count(t=...)` in a `nexusfile_open` block).
- Nobody tells you the settings: chopper mode, pinhole, camera, exposures, angular step, references. Justify each.

## How to

1. Click **Open NICOS** (in your starter notebook). Tab *Experiment*: **Find my proposal**, **1250**, **Apply**.
2. Measure; your files go to `data/odin/<year>/1250/raw`.
3. Analyze them with the **starter notebook**. The tools are there; the decisions are yours.
