# Beamtime on ODIN: magnetic fields inside matter

**Your role**: the neutron specialist of a team that needs to see magnetic fields where no probe can go: inside the
windings of a coil, inside a rock.

## Your proposal (accepted)

**Proposal 1270**: *"Magnetic fields inside matter by polarized neutron imaging"*

Two samples are available on the sample changer (`sample_holder`):

- `magnet_solenoid`: the coil of M. Sales *et al.*, Sci. Rep. **8**, 2214 (2018): 13.5 windings of aluminium wire,
  15.5 mm long, 11 mm in diameter, 0.6 A, its axis along x (tilted by about 9°);
- `nwa7034_fragment`: the fragment of the Martian meteorite NWA 7034 of C. H. Qvistgaard, E. B. Naver *et al.*,
  Geochem. Geophys. Geosyst. **27**, e2025GC012641 (2026), 2 × 10 × 13 mm³, magnetized with a whiteboard magnet.

The committee asks for:

1. for each sample you measure, a map of ∫B dl along the beam and of the direction of the field, with uncertainties;
2. for the coil: the field inside it, compared with the formula of a long solenoid and with a calculation of your
   choice; for the fragment: where the field is, how strong (in mT), and what one view cannot tell;
3. the limits of your method: the noise floor, the largest ∫B dl it can measure, the resolution;
4. a short logbook: which measurements, why, with which settings.

## Your beamtime

- Instrument: **ODIN** (the digital twin). Budget: **6 hours of beam** (counting time with the shutter open).
- Polarized imaging: devices `polarizer`, `spin_in`, `spin_out`; commands `polarimetry(t, title)` and
  `polarization_matrix(t, title)` (18 images). The Timepix3 camera sorts the neutrons by wavelength.
- Nobody tells you the settings: chopper mode, pinhole, exposures, angles, references. Justify each.

## How to

1. Click **Open NICOS** (in your starter notebook). Tab *Experiment*: **Find my proposal**, **1270**, **Apply**.
2. Measure; your files go to `data/odin/<year>/1270/raw`.
3. Analyze them with the **starter notebook**. The tools are there; the decisions are yours.
