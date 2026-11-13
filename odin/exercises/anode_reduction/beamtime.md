# Beamtime on ODIN: the reduction of SOC anode supports under load

**Your role**: the neutron specialist of a company that builds stacks of solid-oxide cells. Before a stack runs,
hydrogen turns the NiO of the anode supports into Ni, inside the stack, under load. The team wants to know whether the
load makes the reduction uneven.

## Your proposal (accepted)

**Proposal 1280**: *"Reduction of NiO-YSZ anode supports under load by Bragg-edge imaging"*

Three holders on the sample changer (`sample_holder`), each with two bars of anode support (NiO-YSZ, 20 × 6 × 0.9
mm³, 0.9 mm along the beam), after M. G. Makowska *et al.*, ECS Trans. **68**, 1103 (2015) and J. Appl. Cryst. **49**,
1674 (2016):

- `anode_standards_a`: bars reduced to 0 % (top) and 52 % (bottom), weighed;
- `anode_standards_b`: 11 % (top) and 92 % (bottom);
- `anode_loaded_700C`: two bars reduced together 5 min at 700 °C: the top one clamped at x < −7 mm and loaded at
  x = +3 mm (bent), the bottom one without load.

The committee asks for:

1. the reduction degree of the loaded bar in its bent part and beyond the load point, and of the reference bar, with
   uncertainties;
2. a map of the reduction degree, and what it says about tension and compression;
3. how you calibrated (which edges, which method) and how you know it works;
4. a short logbook: which measurements, why, with which settings.

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **3 hours of beam** (counting time with the shutter open).
- The Timepix3 camera (time of flight): `count(t=...)` in a `nexusfile_open` block; at most about 90 s per file in
  WFM with the 3 cm pinhole (repeat the counts, the analysis adds them up).
- Nobody tells you the settings: chopper mode, pinhole, exposures, references. Justify each.

## How to

1. Click **Open NICOS** (in your starter notebook). Tab *Experiment*: **Find my proposal**, **1280**, **Apply**.
2. Measure; your files go to `data/odin/<year>/1280/raw`.
3. Analyze them with the **starter notebook**. The tools are there; the decisions are yours.
