# Digital twin of LoKI (small-angle neutron scattering, ESS) — first version

*Started 2026-11-03.* LoKI measures small-angle neutron scattering (SANS) by time of flight: the size, shape and
arrangement of objects from ~1 to ~100 nm (particles, pores, polymers, membranes). This folder is the start of its
digital twin, built like the ODIN twin (`../odin/`), from the official McStas model of LoKI and from the French LoKI
notebook series of this project, where every step of the simulation and of the reduction is explained and validated.

**Status (2026-11-05): NeXus event files in the format of the real LoKI, reduced with the ESS software (`esssans`),
analyzed with `sasmodels` (the engine of SasView).** Three collimations, two detector distances, pulse skipping
(below); three samples: `silica_spheres` (in D₂O), `d2o` (the solvent, background) and `empty_beam` (transmission
reference). Driven from Python, from the console (`twin_server.py --instrument loki` + `twin_console.py`) or from
NICOS (`../nicos/start_nicos.py --instrument loki`, ESS GUI and device names `heavy_shutter`, `fast_shutter`,
`sample_holder`); data analyzed in `LoKI_analysis.ipynb`; exercise of the catalogue in `exercises/silica_spheres/`.
Not yet: empty cell measured separately, dark, a movable transmission monitor, the resolution function for the fits.

## NeXus files and the ESS reduction (2026-11-05)

**The file** (`loki_nexus.py`): the template is a real file written by the ESS file writer at LoKI (April 2026, five
pulses), distributed by ESS with esssans (`ess.loki.data.loki_coda_file()`, downloaded once). Its whole structure is
kept (9 detector banks with their real geometry, 2.8 million pixels in 4 layers of tubes of 7 straws, 5 monitors,
choppers, motors, logs); the twin replaces the events and the settings, removes the users of the template, and adds
`entry/twin` (the true sample, the fraction of neutrons written). Each neutron scattered by the sample (McStas) flies
in a straight line to the first bank it meets (beam stop: absorbed); in that bank it is detected in one of the
overlapping sub-detectors (a layer and a straw position, drawn at random), in the pixel closest to its point of
impact, so that each pixel receives neutrons in proportion to its solid angle, as the ESS reduction assumes.
`event_time_offset` = arrival time after its pulse, `event_time_zero` = pulse times (14 Hz). Monitors: m1 (incident,
8.4 m before the sample) and m3 (transmission, 0.2 m after it), efficiency 10⁻³, from the McStas beam at the sample.
**Volume**: LoKI counts millions of neutrons per second (4·10⁹ in 10 min for the silica spheres): a file holds at most
10⁷ detector events and 2·10⁶ per monitor, a random sample at the same rate for detectors and monitors
(`entry/twin/event_sampling`, 0.1 % for the easy case), so that absolute intensities and transmissions are unchanged.
About 140 MB and 1 min per measurement.

**The reduction** (`loki_reduction.py`): `ess.loki.LokiWorkflow`, unmodified, with the parameters of the ESS notebook
"loki-reduction-ess", on each bank. What the twin provides, as the instrument team does at ESS:
- the time → λ **lookup table** of each configuration, built by essreduce (`make_wavelength_lut_from_simulation`)
  from the McStas beam at the sample (`<run root>/loki/lookup_tables/`);
- the **masks** (pixel ids): pixels behind the beam stop or a closer bank, seen from the center and the corners of
  the beam, plus a margin of 0.6 tube pitch around them and along the bank edges (a pixel collects a band one tube
  pitch wide);
- the **direct-beam function** D(λ) of each bank: the calibration that makes I(Q) absolute, measured as at ESS with a
  standard of known cross-section: the twin measures its D₂O (flat, 0.05 cm⁻¹ sr⁻¹) and an empty beam for one hour
  in the configuration, once (`<run root>/loki/calibration/`). It corrects what the geometry alone does not know: the
  layers and straws overlap as seen from the sample, so the solid angle summed over the pixels is about ten times the
  true one (D ≈ 0.08–0.1 times the plain monitor ratio).
Then `red.reduce(sample, background=solvent, empty_beam=empty)` gives I(Q) per bank, background subtracted;
`red.combine` merges the banks into rear / middle / front and divides by the thickness (cm⁻¹ sr⁻¹).

**Validation** (3 m / 5 m, 10 min each, 2026-11-05): D₂O reduced alone: flat within ±3 % on the rear bank for
Q = 0.013–0.26 Å⁻¹ and on the middle bank 1; up to +20 % / −12 % at the inner and outer edges of the middle and front
banks (the calibration is one factor per bank; a pixel-by-pixel flat field would remove it), and −20 to −35 % at the
lowest Q of the rear bank (< 0.011 Å⁻¹, next to the beam-stop mask). Silica spheres minus D₂O, all banks:
**Rg = 39.2 ± 1.2 Å (exact 38.7), I(0) = 4.20 ± 0.08 cm⁻¹ (exact 4.37), sasmodels sphere: R = 49.1 ± 0.1 Å (50),
φ = 1.00 % (1 %), χ²/n = 0.5.** Two pitfalls met on the way (2026-11-05): a too small coverage tolerance let neutrons through the middle
banks (+25 % at the edges of the rear bank), and looking the pixels up along the direction from the sample center smeared the counts by the beam size next to the beam stop.

## Easy test case: dilute silica spheres

```
python easy_case.py
```
Silica spheres of radius R = 50 Å, 1 % in volume in D₂O, 1 mm thick; 3 m collimation (rear detector at 5 m);
10 min of measurement. Their scattering is known exactly (`loki_samples.silica_spheres`):
dΣ/dΩ = φ V Δρ² P(Q) + background, I(0) = 4.37 cm⁻¹, minima of P(Q) at 0.090 and 0.155 Å⁻¹.

![Easy case](figures/easy_case.png)

Since 2026-11-05 the easy case measures, as a real SANS experiment, an empty beam (60 s), the solvent and the sample
(10 min each), writes NeXus event files and reduces them with esssans (§ NeXus files); results above. The first run
takes ~10 min (McStas simulations of the two samples, calibration of the configuration, then cached), the next ones
~4 min. Before (2026-11-04, the twin's own reduction to I(Q)): Rg = 39.4 ± 0.2 Å, I(0) = 4.31 cm⁻¹.

## Configurations

What can be changed, as on the instrument (devices of `VirtualLoki`, same names in NICOS):

| Device | Values | Effect |
|---|---|---|
| `collimation` | `3m`, `5m`, `8m` | upstream part of the official model; longer: smaller divergence (lower Q, better resolution), less flux. Source / sample apertures 30/10 mm (3 m), 20/10 mm (5 m, 8 m); band 3–11.5 Å (3 m, 5 m), 3–10 Å (8 m) |
| `pulse_skipping` | `off`, `on` | `on`: choppers at 7 Hz, one source pulse in two, band 3–21.4 Å (3 m collimation only) |
| `detector_distance` | 5, 10 m | rear detector bank (the middle and front banks do not move); farther: lower Q |

The configurations are those of the LoKI notebook series (notebooks 01–03), where the upstream parts were computed and
checked; the pulse-skipping upstream part was computed for the twin (10⁹ neutrons). Each is a precomputed upstream
part (release asset, `../container/fetch_fronts.py --instrument loki`); a combination that does not exist is refused
with the list of the available ones.

**Read-only values** (`VirtualLoki.readings()`, NICOS devices of the setup `choppers`): speed of the two chopper pairs
of the model, bandwidth chopper `ch1` (6.5 m from the source) and frame-overlap chopper `ch2` (15.21 m), 14 Hz or 7 Hz,
and the opening delay of each disc (`ch1a_delay`, `ch1b_delay`, ...), computed from the wavelength band with the
formulas of the model (`includes/loki_functions.c`; checked against the values printed by the compiled model, to the
μs, for 3 m / 3–11.5 Å, 8 m / 3–10 Å and pulse skipping / 3–21.4 Å); `wavelength_band`.

**Pulse skipping in the twin**: the arrival times are unwrapped with a period of 2/14 s, and the count rates are
halved (McStas simulates one pulse, which the choppers let through, with weights in neutrons per second as if every
pulse came; I(Q) is a ratio and does not change, but the counting noise of a t-second measurement does).

**Validation of the configurations** (2026-11-04, with the twin's own reduction, before the NeXus files; silica
spheres of the easy case, 10 min, Guinier fit Q Rg < 1.3 on all banks; exact Rg = 38.7 Å, I(0) = 4.373 cm⁻¹):

| Collimation / detector | Rear bank Q range [Å⁻¹] | Rg [Å] | I(0) [cm⁻¹] | Level / exact (Guinier region) |
|---|---|---|---|---|
| 3 m / 5 m | 0.0115–0.258 | 39.4 ± 0.2 | 4.311 | 0.984 |
| 3 m / 10 m (now refused: frame overlap) | 0.0078–0.184 | 39.2 ± 0.2 | 4.178 | 0.956 |
| 5 m / 5 m | 0.0115–0.258 | 40.1 ± 0.2 | 4.396 | 0.994 |
| 5 m / 10 m (now refused: frame overlap) | 0.0078–0.184 | 39.3 ± 0.2 | 4.222 | 0.965 |
| 8 m / 10 m | 0.0082–0.184 | 39.9 ± 0.2 | 4.374 | 0.992 |
| 8 m / 5 m | 0.0120–0.258 | 39.8 ± 0.2 | 4.380 | 0.993 |
| 3 m, pulse skipping / 5 m | 0.0106–0.258 | 39.9 ± 0.2 | 4.357 | 0.987 |
| 3 m, pulse skipping / 10 m (now refused: frame overlap) | 0.0075–0.176 | 39.1 ± 0.2 | 4.285 | 0.981 |

All within 5 % of the exact values. Pulse skipping, checked neutron by neutron: the wavelength rebuilt from the
arrival time (period 2/14 s) differs from the true one by +3 % (median), as without pulse skipping (+4 %: the long
ESS pulse, the reduction assumes the mean emission time), with no frame error; the incident flux is halved
(7.8·10⁸ → 4.0·10⁸ n/s on the sample, 3 m). The longest wavelengths are few, so the rear bank gains little at low Q
(0.0106 instead of 0.0115 Å⁻¹ at 5 m); the gain is a wider Q range in one setting (front bank from 0.136 Å⁻¹). Rg comes out 1–4 % too large in every configuration (resolution, not corrected).
**Frame overlap** (explained 2026-11-04): with the band 3–11.5 Å and the rear detector at 10 m, the neutrons of one
pulse reach the detector over 82 ms (fastest 3 Å to slowest 11.5 Å, pulse length included), more than the 71.4 ms
between two pulses: the slowest neutrons of a pulse arrive with the fastest of the next one, and get a wrong wavelength
(checked neutron by neutron: 1.9 % of the rear-bank neutrons with an error above 30 %), hence the 4 % low level. With
pulse skipping (3–21.4 Å, 142.9 ms between pulses used) the same happens at 10 m (166 ms; 0.3 %). This is why the 8 m
configuration uses 3–10 Å (69 ms at 10 m). On the instrument the band is chosen with the detector distance; the twin
now refuses a setting with frame overlap (`VirtualLoki.move`, computed from the band, the distance and the period),
with the explanation. Allowed: 3 m / 5 m, 5 m / 5 m, 8 m / 5 m, 8 m / 10 m, 3 m pulse skipping / 5 m. Computing time: < 30 s for a
configuration already simulated, ~1 min for a new one; peak memory 4.4–5.6 GB (8 MPI processes).

## How it works

| Step | Where | What |
|---|---|---|
| Upstream part | `loki_mcstas.front` | official `LOKI_main.instr` cut just before the sample, MCPL file of the neutrons at the sample (computed once per configuration: ~15 min for 10⁹ neutrons on 8 cores, ~1.4 GB RAM per process) |
| Sample | `loki_mcstas.back`, `components/SANS_Iq_table.comp` | McStas downstream part: the sample scatters with a tabulated dΣ/dΩ(Q) in absolute units; scattered neutrons to an MCPL file, transmitted beam to wavelength monitors |
| Detector | `loki_mcstas.Detector` (live image), `loki_nexus.RealDetector` (files) | the 9 banks: panels of the official model for the live image; real pixels of LoKI for the NeXus files; straight lines from the sample, beam stop |
| Time of flight | `loki_mcstas.events` | arrival time modulo the source period (2/14 s with pulse skipping), frames unwrapped, λ = h t / (m L), Q = 4π sin θ / λ |
| File | `loki_nexus` | NeXus event file of the real LoKI's format (events of the 9 banks and of the monitors m1, m3, settings) |
| Reduction | `loki_reduction` (esssans) | I(Q) in absolute units per bank, solvent subtracted; lookup table, masks, direct-beam calibration provided by the twin |
| Analysis | `loki_analysis` | Guinier fit, sphere model of sasmodels (scale = volume fraction) |
| Instrument | `virtual_loki.VirtualLoki` | devices (`heavy_shutter`, `shutter`, `collimation`, `pulse_skipping`, `detector_distance`, `sample`), `move`, `count(t)` → NeXus file, live image of the rear panel, logbook `log.jsonl`; same interface as `VirtualOdin`, so the twin server and NICOS drive it |

## Files

| File | Role |
|---|---|
| `loki_paths.py` | paths: official model `LOKI_REPO` (default `~/McStas_runs/LOKI`), results `<TWIN_RUN_ROOT>/loki/` |
| `loki_mcstas.py` | McStas engine (English copy of the engine of the LoKI notebook series, same physics) |
| `loki_samples.py` | samples (dΣ/dΩ in cm⁻¹ sr⁻¹): `silica_spheres`, `d2o`, `empty_beam` |
| `virtual_loki.py` | the virtual instrument (`VirtualLoki`) |
| `loki_nexus.py` | NeXus event files from the real LoKI template; real pixel geometry, masks |
| `loki_reduction.py` | reduction with esssans: lookup tables, masks, direct-beam calibration, `reduce`, `combine` |
| `loki_analysis.py` | Guinier, sasmodels sphere fit (used by the web page) |
| `loki_exercises.py` | automatic checks of the MSc notebook |
| `exercises/silica_spheres/` | exercise of the catalogue: `exercise.yml`, MSc notebook, beamtime sheet and starter notebook (`gen_notebooks.py`) |
| `easy_case.py` | the test case above and its figure |
| `gen_student_page.py` → `LoKI_virtual.ipynb` | BSc page (Voilà): settings table (empty beam, solvent, sample, two configurations), operate (sample, collimation, pulse skipping, detector distance, shutters; refusals explained), image of the rear panel, logbook, analysis (esssans, Guinier, sasmodels), questions |
| `gen_analysis_notebook.py` → `LoKI_analysis.ipynb` | analysis notebook (JupyterLab): logbook (kind of each file), inside a NeXus file, reduction with esssans (9 banks, solvent subtracted, transmission), Guinier fit, sasmodels sphere fit (R, φ); on any session or proposal folder |
| `components/SANS_Iq_table.comp` | McStas sample component (isotropic SANS from a table, absolute units) |

## Installation

Same environment as the ODIN twin, plus the official LoKI model:
```
git clone https://git.esss.dk/dmsc-instrumentmodels/LOKI.git ~/McStas_runs/LOKI
```
The upstream part of the 3 m configuration (`front/col3m_src30mm_sam10mm_lam3-11.5_skip0_N1e+09/`, 54 MB) is
downloaded from the release of this repository (`python ../container/fetch_fronts.py --instrument loki`, asset
`loki_front_...tar`); otherwise it is computed by `loki_mcstas.front()` on first use (~15 min on 8 cores). With the
upstream part present, the official model is not needed to measure.

**Container**: the image contains the official model (fixed commit, `LOKI_REPO=~/loki_model`) and downloads the
upstream part at start. Checked on 2026-11-04 from an empty results folder, without the official model, 4 MPI
processes: the easy case takes 2 min (compilation + downstream part), Rg = 39.3 ± 0.2 Å, I(0) = 4.33 cm⁻¹, peak memory
5.6 GB. The smoke test of the container runs it at every push. Number of McStas processes: variable `TWIN_MPI`
(default 8).

## Next steps
1. Done on 2026-11-05: event files in the ESS NeXus format of LoKI, reduced with `esssans`; solvent and empty beam.
2. A complete SANS session: empty cell measured separately, dark, a movable transmission monitor, flat field per
   pixel (removes the bank-edge deviations), the resolution for the fits (sasmodels `dq`); the samples of the
   notebook series (Nafion membrane, catalyst layer, porous electrode).
3. Done on 2026-11-04: collimations 5 m and 8 m, rear detector at 5 or 10 m, pulse skipping (§ Configurations).
   To do: understand the 4 % low level with a short collimation and the detector at 10 m; more samples.
4. Done on 2026-11-04: twin server, console and NICOS (`../nicos/nicos_twin/loki/`, ESS GUI of LoKI), analysis
   notebook, container image, live data with Kafka and just-bin-it (rear panel, sample of the neutrons;
   `../nicos/README.md`, "Live data"), web page `LoKI_virtual.ipynb`.
