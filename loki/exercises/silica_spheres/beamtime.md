# Beamtime on LoKI: how big are these nanoparticles?

## Your proposal (accepted)

**Proposal 3001**: *"Size of silica nanoparticles for a new polishing slurry"*

A company makes silica nanoparticles that should all have the same size. Your group must measure it with
small-angle neutron scattering (SANS). The particles are dispersed in heavy water (D₂O), 1 % by volume. The beamtime
committee asks for:

1. the reduced curve I(Q) in absolute units (cm⁻¹), with the solvent subtracted;
2. the radius of gyration Rg (Guinier analysis) and the radius of the spheres (sphere model), with uncertainties;
3. a short logbook: which measurements you made, why, and with which settings.

## Your beamtime

- Instrument: **LoKI** (the digital twin). Budget: **1 hour of beam** (counting time with both shutters open).
- Samples available in the sample changer: `silica_spheres`, `d2o` (the solvent in the same cell), `empty_beam`
  (nothing in the beam).
- Nobody tells you the settings. Choose them and justify each choice: collimation, detector distance (which Q range
  do you need for particles of a few nanometers?), counting times, which reference measurements the reduction needs.
- Mistakes are allowed, as at a real instrument. Some combinations are refused by the instrument: find out why.

**Samples**: `sample_info()` describes the sample mounted. To go further (another particle size, a contrast with
H₂O/D₂O), design your own sample with the **sample builder** (button *Sample builder* at the top of your starter notebook): it is saved with
your proposal and appears on the sample changer.

## How to

1. Click **Open NICOS** (at the top of your starter notebook): the NICOS window of LoKI opens, ready.
2. Tab *Experiment*: **Find my proposal**, choose proposal **3001**, then **Apply**. As at ESS, its number, title, users and
   samples are filled in, and the silica spheres are mounted (you may mount another sample).
3. Record data with `nexusfile_open`, e.g. `with nexusfile_open('silica 3m'): count(t=600)`.
   Your files go to `data/loki/2026/3001/raw`.
4. Analyze them with the **starter notebook** (button *Starter notebook* of the catalogue).
