# ACCESS digital twins of ESS instruments

*Created 2026-11-03.* Virtual instruments for teaching (ACCESS project, DTU / UCPH / ESS): each twin is operated like
the real instrument (NICOS, or a console, or a web page), writes data files in the ESS NeXus format, and its data go
through the official ESS reduction software. Everything is explained and every approximation is stated and checked.
Repository: https://github.com/aglaenze/access-digital-twins (public).

**Students**: install Podman Desktop and the app **ESS digital twins** (installers: https://github.com/aglaenze/access-digital-twins/releases/tag/app-latest),
then open it: sign in, choose an exercise ([TUTORIAL.md](TUTORIAL.md), first section). **New here otherwise? Start with [TUTORIAL.md](TUTORIAL.md)**
(installation, then your first measurement in each of the three ways described below).

**The app** ([app/](app/README.md), Electron, 2026-11-06): a real application window. The student signs in (name,
email, password; accounts on the computer), chooses an exercise in the catalogue (with their progress), works in tabs
of the app, goes back to the catalogue, and *submits* each exercise at its end (`submit.py`: one file for the
teacher). Installers: GitHub release `app-latest` (app.yml). Teachers can also run it from the repository
(local mode).

**For a course: the catalogue of exercises** (in the app; read from the `exercise.yml` files by `container/twin_app.py`):
choose the instrument, then an exercise, then the way in: BSc guided web page, MSc notebook with tasks and automatic
checks (the student measures first in NICOS, from the notebook), or a beamtime with NICOS (proposal, sample builder,
NICOS, all from the starter notebook). NICOS is for the MSc level
and the free beamtime only: BSc students use the web pages and never see NICOS. Each exercise is one folder
`<instrument>/exercises/<name>/` with an `exercise.yml`; its MSc and beamtime notebooks are generated from the guided
analysis notebook of the instrument (`gen_notebooks.py`). Exercises planned: `catalogue_planned.yml`.
Rules for every exercise: the student has a **role and a mission** that say why the measurement matters (field
`mission` of `exercise.yml`, shown on the card, in the page and in the notebooks, with a final verdict); every
question is **interactive** (`quiz.py`: multiple choice or a value checked with a tolerance, a wrong answer is
explained, the answer can be shown, MSc tasks have their solution behind a button), so that the exercises work
without a teacher. Each instrument also has a **free beamtime** (no exercise: NICOS, sample builder, a starter
notebook asking for the question and the plan first; `gen_free_beamtime.py`). The answers are kept in
`TWIN_RUN_ROOT/progress/`; `progress_summary.py` gives the teacher a table for a class.

## Instruments

| Instrument | Folder | Technique | Status |
|---|---|---|---|
| ODIN | `odin/` — **read `odin/README.md`** | neutron imaging (Bragg edges, tomography, chopper modes) | working (hybrid and mcstas modes, web pages, NICOS, live data with Kafka) |
| LoKI | `loki/` — read `loki/README.md` | small-angle neutron scattering (SANS) | working: NeXus event files of the real LoKI's format reduced with esssans, sasmodels fits; 3 collimations, 2 detector distances, pulse skipping; web page, Python, console, NICOS, live data |
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
├── loki/                everything specific to LoKI — read loki/README.md
├── sample_library.py    the samples (one YAML file each: odin/samples, loki/samples, <proposal>/samples)
├── quiz.py              interactive questions (explanations, answers on request, report, progress files)
├── gen_free_beamtime.py starter notebooks of the free beamtime (<instrument>/exercises/free_beamtime/)
├── progress_summary.py  teachers: the answers of a class, from the students' progress files
└── Sample_builder.ipynb the sample builder of the free beamtime (gen_sample_builder.py)
```
Results (outside the repository and OneDrive, no spaces in the path: McStas needs it): `<TWIN_RUN_ROOT>/<instrument>/`,
data recorded with NICOS in `<TWIN_RUN_ROOT>/data/<instrument>/<year>/<proposal>/raw/` (as at ESS); environment variable `TWIN_RUN_ROOT`, default `~/McStas_runs/twin`
(`C:/Users/<user>/McStas_runs/twin` on Windows). Each instrument folder is self-contained (its McStas engine, components,
pages); the McStas models of the instruments themselves are the official ESS ones (below).

## Where the instrument models come from

The McStas models of the instruments are **not** written here: they are the official models of ESS, maintained by
the instrument teams and DMSC in the group **dmsc-instrumentmodels** of the ESS GitLab, https://git.esss.dk/dmsc-instrumentmodels/:

| Instrument | Official model | Used as | Version in the container |
|---|---|---|---|
| ODIN | https://git.esss.dk/dmsc-instrumentmodels/odin | Python packages `ODIN_instr` and `odin_support` (`pip install -e`) | commit `ea4fc94e` |
| LoKI | https://git.esss.dk/dmsc-instrumentmodels/LOKI | the instrument file `instr/LOKI_main.instr` (`LOKI_REPO`) | commit `00fc29c7` |

The twins cut these models in two (upstream part, recorded once as MCPL files; the sample and detector part, simulated
at each count), add the samples, the NeXus files of the real instruments and NICOS; the physics of the instruments
(source, guides, choppers, detectors) is that of the official models. The versions are fixed in
`container/Containerfile` (`ODIN_COMMIT`, `LOKI_COMMIT`); the details are in `odin/README.md` and `loki/README.md`.

## Samples

Every sample is one YAML file, read by the pages, the notebooks and NICOS (`sample_library.py`):
- **built-in samples**, chosen by the teachers: `odin/samples/*.yml` (blocks of crystalline materials of NCrystal:
  `iron_plate`, `steel_steps`, `iron_copper`) and `loki/samples/*.yml` (particles of a sasmodels shape in a H2O/D2O
  solvent: `silica_spheres`, `d2o`, `empty_beam`). Adding a sample = adding a file;
- **students' samples** (free beamtime): made with the **sample builder** (`Sample_builder.ipynb`, Voilà, generated by
  `gen_sample_builder.py`), saved in `<proposal>/samples/` next to `<proposal>/raw/`, and then on the sample changer
  of NICOS (`move(sample_holder, 'name')`; the list is read from the twin). A built-in name cannot be reused;
  overlapping blocks and out-of-range values are refused.
- **what the students see**: the pages and the MSc notebooks draw the sample (ODIN: beam's eye view with the 14 mm
  field of view, and from above; LoKI: the cell and its particles); in NICOS, `sample_info()` describes it and saves
  its drawing in `<proposal>/samples/`. An exercise can hide what is to be measured (`samples:` in its
  `exercise.yml`, e.g. the radius of the silica spheres, shown as "?").
A new sample is simulated by McStas on its first count (ODIN "mcstas" mode, LoKI), then cached; ODIN's default
"hybrid" mode computes its transmission at once from NCrystal.

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
`essimaging`); LoKI data are NeXus event files of the real LoKI's format, reduced with `esssans`
(`loki/loki_reduction.py`). Each instrument has a step-by-step analysis notebook for the students:
`odin/ODIN_analysis.ipynb` (transmission, Bragg edges) and `loki/LoKI_analysis.ipynb` (reduction, Guinier, sasmodels).

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
