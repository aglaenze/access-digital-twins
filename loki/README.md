# Digital twin of LoKI (small-angle neutron scattering, ESS) — first version

*Started 2026-11-03.* LoKI measures small-angle neutron scattering (SANS) by time of flight: the size, shape and
arrangement of objects from ~1 to ~100 nm (particles, pores, polymers, membranes). This folder is the start of its
digital twin, built like the ODIN twin (`../odin/`), from the official McStas model of LoKI and from the French LoKI
notebook series of this project, where every step of the simulation and of the reduction is explained and validated.

**Status: first version, one easy test case (below).** Driven from Python, from the console (`twin_server.py
--instrument loki` + `twin_console.py`) or from NICOS (`../nicos/start_nicos.py --instrument loki`, ESS GUI and
device names `heavy_shutter`, `fast_shutter`); data analyzed in `LoKI_analysis.ipynb`. Not yet: raw event files
in the ESS NeXus format, reduction with the ESS software (`esssans`), the full series of measurements of a real SANS
experiment (empty cell, solvent, dark, water calibration), web page, container.

## Easy test case: dilute silica spheres

```
python easy_case.py
```
Silica spheres of radius R = 50 Å, 1 % in volume in D₂O, 1 mm thick; 3 m collimation (rear detector at 5 m);
10 min of measurement. Their scattering is known exactly (`loki_samples.silica_spheres`):
dΣ/dΩ = φ V Δρ² P(Q) + background, I(0) = 4.37 cm⁻¹, minima of P(Q) at 0.090 and 0.155 Å⁻¹.

![Easy case](figures/easy_case.png)

Result (2026-11-04): the three detector banks join up and follow the exact curve; Guinier fit (Q Rg < 1.3, 26 points):
**Rg = 39.4 ± 0.2 Å (exact 38.7 Å), I(0) = 4.31 ± 0.01 cm⁻¹ (exact 4.37)**; mean level in the Guinier region 0.984
of the exact one. The apparent Rg is 1.8 % too large because the instrument resolution smears the curve (it also
fills in the minima); it is not corrected here. The first run takes ~2 min (McStas compilation and downstream
simulation, then cached).

## How it works

| Step | Where | What |
|---|---|---|
| Upstream part | `loki_mcstas.front` | official `LOKI_main.instr` cut just before the sample, MCPL file of the neutrons at the sample (computed once per configuration: ~15 min for 10⁹ neutrons on 8 cores, ~1.4 GB RAM per process) |
| Sample | `loki_mcstas.back`, `components/SANS_Iq_table.comp` | McStas downstream part: the sample scatters with a tabulated dΣ/dΩ(Q) in absolute units; scattered neutrons to an MCPL file, transmitted beam to wavelength monitors |
| Detector | `loki_mcstas.Detector` | the 9 tube panels of the official model (front, middle, rear banks), straight lines from the sample to the first panel met, beam stop, masks of hidden pixels |
| Time of flight | `loki_mcstas.events` | arrival time modulo the source period, frames unwrapped, λ = h t / (m L), Q = 4π sin θ / λ |
| Reduction | `loki_mcstas.reduce` | I(Q) in absolute units per bank: counts / (flux × transmission × thickness × solid angle) |
| Instrument | `virtual_loki.VirtualLoki` | devices (`heavy_shutter`, `shutter`, `collimation`, `sample`), `move`, `count(t)` → HDF5 file with I(Q) and errors per bank (counting noise of a `t`-second measurement + simulation noise), live image of the rear panel, logbook `log.jsonl`; same interface as `VirtualOdin`, so the twin server and NICOS drive it |

## Files

| File | Role |
|---|---|
| `loki_paths.py` | paths: official model `LOKI_REPO` (default `~/McStas_runs/LOKI`), results `<TWIN_RUN_ROOT>/loki/` |
| `loki_mcstas.py` | McStas engine (English copy of the engine of the LoKI notebook series, same physics) |
| `loki_samples.py` | samples (dΣ/dΩ in cm⁻¹ sr⁻¹): `silica_spheres` |
| `virtual_loki.py` | the virtual instrument (`VirtualLoki`, `read`) |
| `easy_case.py` | the test case above and its figure |
| `gen_analysis_notebook.py` → `LoKI_analysis.ipynb` | analysis notebook (JupyterLab): logbook, file content, I(Q) of the three banks, Guinier fit (Rg), sphere-model fit (R, background), volume fraction from I(0); on any session or proposal folder (demonstration, 10 min: Rg = 39.4 ± 0.2 Å, R = 49.6 Å, φ = 1.00 %) |
| `components/SANS_Iq_table.comp` | McStas sample component (isotropic SANS from a table, absolute units) |

## Installation

Same environment as the ODIN twin, plus the official LoKI model:
```
git clone https://git.esss.dk/dmsc-instrumentmodels/LOKI.git ~/McStas_runs/LOKI
```
The upstream part of the 3 m configuration (`front/col3m_src30mm_sam10mm_lam3-11.5_skip0_N1e+09/`, 54 MB) is computed
by `loki_mcstas.front()` on first use (~15 min) — on the development computer it was taken (hard link) from the LoKI
notebook series.

## Next steps
1. Raw data: event files in the ESS NeXus format of LoKI, reduced with `esssans` (as ODIN with `essimaging`).
2. A real SANS session: empty beam, empty cell, solvent, sample, dark, water (absolute calibration), with
   transmissions; the samples of the notebook series (Nafion membrane, catalyst layer, porous electrode).
3. Collimations 5 m and 8 m (rear detector at 10 m), to reach lower Q.
4. Done on 2026-11-04: twin server, console and NICOS (`../nicos/nicos_twin/loki/`, ESS GUI of LoKI). Still to do:
   web page, and LoKI in the container image (official model and precomputed upstream part).
