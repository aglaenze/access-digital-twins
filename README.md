# ACCESS digital twins of ESS instruments

*Created 2026-11-03.* Virtual instruments for teaching (ACCESS project, DTU / UCPH / ESS): each twin is operated like
the real instrument (NICOS, or a console, or a web page), writes data files in the ESS NeXus format, and its data go
through the official ESS reduction software. Everything is explained and every approximation is stated and checked.
Repository: https://github.com/aglaenze/access-digital-twins (public).

**New here? Start with the step-by-step guide [TUTORIAL.md](TUTORIAL.md)** (installation, then your first
measurement in each of the three ways described below).

## Instruments

| Instrument | Folder | Technique | Status |
|---|---|---|---|
| ODIN | `odin/` — **read `odin/README.md`** | neutron imaging (Bragg edges, tomography, chopper modes) | working (hybrid and mcstas modes, NICOS) |
| LoKI | `loki/` — read `loki/README.md` | small-angle neutron scattering (SANS) | first version: easy test case (silica spheres); Python, console, NICOS |
| DREAM | — | powder diffraction (bispectral, time-of-flight; also single-crystal) | to do (waiting for the official McStas model) |
| BIFROST | — | inelastic scattering: indirect-geometry time-of-flight spectrometer (cold neutrons, multiplexing analysers) | to do (waiting for the official McStas model) |

You choose the instrument when you start a twin (`--instrument odin|loki`; the NICOS launcher asks), as you walk into
the control room of one instrument at ESS.

## Layout

```
twin/
├── README.md            this file
├── twin_server.py       server: one virtual instrument in its own process, driven over HTTP (local)
├── twin_console.py      console with the NICOS commands (standard library only)
├── nicos/               NICOS: setup package nicos_twin (one sub-package per instrument, as nicos_ess) + launcher — read nicos/README.md
├── container/           container image (McStas + twins + NICOS + JupyterLab), built by GitHub Actions — read container/README.md
├── odin/                everything specific to ODIN — read odin/README.md
└── loki/                LoKI (first version) — read loki/README.md
```
Results (outside the repository and OneDrive, no spaces in the path: McStas needs it): `<TWIN_RUN_ROOT>/<instrument>/`,
data recorded with NICOS in `<TWIN_RUN_ROOT>/data/<instrument>/<year>/<proposal>/raw/` (as at ESS); environment variable `TWIN_RUN_ROOT`, default `~/McStas_runs/twin`
(`C:/Users/<user>/McStas_runs/twin` on Windows). Each instrument folder is self-contained (its McStas engine, components,
pages); the McStas models of the instruments themselves are the official ESS ones, installed as Python packages.

## Three ways to use a twin

1. **With NICOS** (as at ESS; Master level, "live a real measurement session"):
   ```
   python nicos/start_nicos.py               # asks the instrument; twin server + NICOS services + the ESS GUI
   ```
   login student / student, a proposal number in the Experiment tab, then e.g.
   `move(shutter, 'open', stage_x, 500)` and `with nexusfile_open('open beam'): count(t=10)` (the ESS way of
   recording data). Details: `nicos/README.md`.
2. **With the console** (no NICOS needed):
   ```
   python twin_server.py --instrument odin --session test      # terminal 1
   python -i twin_console.py                                   # terminal 2
   >>> move(shutter, "open", stage_x, 0.5); count(10)
   ```
3. **In Python or in the student web page** (Bachelor level): `odin/odin_virtual.py` in a notebook, or
   `voila odin/ODIN_virtual.ipynb`. Details: `odin/README.md`.

Games and visualizations (missions with beamtime budget and score, troubleshooting, logbook badges, live detector
replay, chopper diagrams, progressive tomography, 3D neutron trajectories): `odin/README.md` § 11,
`voila odin/ODIN_mission.ipynb`, `python odin/show_3d.py`.

ODIN data are NeXus files (ESS format), reduced with the official ESS code (`odin/odin_reduction.py`, built on
`essimaging`); LoKI data are I(Q) per detector bank (first version).

## Python environments

| Environment | Used by | Key packages |
|---|---|---|
| `mcstas` | the twins, the server, the reduction, the pages | McStas 3.9.2, McStasScript, NCrystal, MCPL, essimaging 26.10.1, scipp, voila (numpy 2) |
| `nicos` | NICOS cache, daemon, GUI | NICOS (sources in `McStas_runs/nicos_src`), nicos-pyctl, PyQt5, gr (numpy 1.26) |

The two environments only talk over HTTP (`twin_server.py`), on this computer.

## Server protocol (`twin_server.py`)
JSON over `http://127.0.0.1:8765`: `GET /status`, `GET /devices`, `GET /log`, `POST /move {device: value}`,
`POST /count {t, title, image}` → `{file, number, n_counts, image}`, `POST /scan {device, values, t, title}`.
One measurement at a time; a command sent during a measurement gets code 409 ("instrument busy"). Adding an
instrument: a sub-folder with a class exposing `move`, `count`, `scan`, `status`, `devices`, `log_file`, `number`,
`folder`, `mode`, `last_image`, and one line in `INSTRUMENTS` of `twin_server.py`.
