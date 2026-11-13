# Beamtime on ODIN: lithium in a thick battery electrode

**Your role**: the neutron specialist of a battery maker that tests ultra-thick electrodes: do they fill up across
their whole thickness, and how much lithium is lost in the first cycle?

## Your proposal (accepted)

**Proposal 1260**: *"Operando imaging of lithium in an ultra-thick graphite electrode"*

The lithium half-cell of M. Strobl, M. E. Baur, L. Theil Kuhn *et al.*, Adv. Energy Mater. (2025) (the cell of
M.-E. Lăcătuşu *et al.*, arXiv:2104.03564): a 0.4 mm graphite electrode, a glass-fiber separator (0.26 mm) and
lithium metal (0.75 mm), disks of 16 mm in an aluminium casing, seen edge-on. Its cycler charges it at C/35: the device
`cycle_time` (h) is the time since the start of the cycle.

The committee asks for:

1. the lithium content x (LixC6) across the depth of the electrode during the cycle, with its uncertainty;
2. where the lithium enters first, whether the electrode fills up across its thickness, and what is left after the
   cycle (in mAh/g);
3. how you converted the images into lithium, and the biases of the conversion;
4. a short logbook: which measurements, why, with which settings.

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **2 hours of beam** (counting time with the shutter open).
- The cameras: `radiograph(t, title, pixels)` (white beam: pixels 128 or 512) and the Timepix3 for time of flight
  (`count(t=...)` in a `nexusfile_open` block).
- Nobody tells you the settings: chopper mode, pinhole, camera, exposures, the times of the cycle. Justify each.

## How to

1. Click **Open NICOS** (in your starter notebook). Tab *Experiment*: **Find my proposal**, **1260**, **Apply**.
2. Measure; your files go to `data/odin/<year>/1260/raw`.
3. Analyze them with the **starter notebook**. The tools are there; the decisions are yours.
