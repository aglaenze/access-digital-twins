# NICOS for the digital twins

*Created 2026-11-03, organized as at ESS on 2026-11-04.* NICOS (Networked Instrument Control System, MLZ / ESS) drives
the virtual instruments as it drives the real ones: the same program, the same GUI as at ESS, the same commands
(`move`, `count`, `scan`, `nexusfile_open`...). The twin (McStas, hybrid model, data files) runs in the background;
the user never sees McStas.

Status (2026-11-04): **ODIN and LoKI** on Windows (services, ESS GUI, measurements written to the proposal folder);
ODIN on Linux in the container image (`../container/`), checked by the smoke test of every build (no GUI in the
container yet). Student step-by-step guide: `../TUTORIAL.md`.

## 1. How NICOS is organized at ESS, and in the twins

At ESS there is **one NICOS program** (the `nicos` repository) and **one NICOS installation per instrument**. The
package `nicos_ess` has one folder per instrument (`odin/`, `loki/`, `dream/`, `bifrost/`...), each with its
`nicos.conf`, its *setups* (the devices of the instrument) and its `guiconfig.py` (the layout of its GUI). The NICOS
services (cache, poller, daemon) of an instrument run on the computers of that instrument, which know which instrument
they are (`INSTRUMENT=nicos_ess.odin`). A user does not choose the instrument in NICOS: they sit in the control room
of their instrument, open its NICOS GUI, log in and work in their experiment (proposal number).

The twins do the same with the package **`nicos_twin`** (this folder): `nicos_twin/odin/`, `nicos_twin/loki/`, each
built on its `nicos_ess` counterpart:

| | ESS (`nicos_ess/<instrument>/`) | Twin (`nicos_twin/<instrument>/`) |
|---|---|---|
| GUI | `guiconfig.py`: tabs Experiment, Setup, Instrument interaction (command line, output, scan plot, detector image, script status, devices), Scripting, History, Logs | **the same file** (copied), with small changes in `nicos_twin/gui.py`: workaround for a NICOS bug, scrolling on small screens, Apply button of the Experiment tab under the form, detector-image color levels recomputed for each new image (ODIN), device list that can be enlarged (the detector-image panel no longer blocks the splitter handle) |
| Experiment | `EssExperiment`: proposal number, title, users, samples; look-up in the ESS user office | `TwinExperiment` = `EssExperiment` without the user-office look-up (type any proposal number) |
| Data files | written by the ESS file-writer (Kafka), started by NICOS; `<instrument>/<year>/<proposal>/raw/` | written by the twin, one per count, in `<TWIN_RUN_ROOT>/data/<instrument>/<year>/<proposal>/raw/` |
| Recording commands | `nexusfile_open`, `start_filewriting`, `stop_filewriting`, `list_filewriting_jobs` (`nicos_ess.commands`) | the same commands (`nicos_twin.commands`) |
| Devices | EPICS (motors, choppers...), detector data through Kafka | HTTP orders to the twin server; names of `nicos_ess` where they exist (LoKI: `heavy_shutter`, `fast_shutter`) |
| Which instrument | the computer you sit at | `start_nicos.py` asks (or `--instrument`): like walking into a control room |

What is not reproduced: EPICS, Kafka and the file-writer themselves (§ 9), and ESS accounts (local accounts, § 2).
At ESS, everything recorded inside one `nexusfile_open` block goes into **one** file; the twin writes one file per
count. The device setups of the real instruments are still thin (ODIN and LoKI are in commissioning): most twin devices
have no ESS name yet, and keep the twin names.

```
NICOS GUI (ESS layout)                  conda env "nicos" (numpy < 2)
   │  login, commands
NICOS daemon + cache + poller            conda env "nicos"; INSTRUMENT=nicos_twin.<instrument>
   │  nicos_twin devices: HTTP orders (move, count, status)
twin_server.py --instrument <name>       conda env of the twins (numpy 2, McStas, essimaging)
   │
virtual instrument (twin/odin/, twin/loki/) → data files in the proposal folder
```
Why two environments: NICOS requires numpy < 2, the twins numpy 2; so NICOS does not import the twin, its devices
send their orders to the twin server over HTTP (this computer only).

## 2. Quick start

```
python start_nicos.py
```
(from this folder, in the twin environment; in the container: `start.sh nicos`). It asks which instrument, then
starts the twin server, the NICOS cache, poller and daemon, and the NICOS GUI. First count with a new configuration:
1–2 min (McStas simulation, then cached); then a few seconds. To stop: Enter in that terminal. Only one instrument at a
time on a computer (as one NICOS per instrument computer): the launcher refuses to start if another one is running.

```
python start_nicos.py --instrument odin                  # no question
python start_nicos.py --instrument loki --no-gui         # services only (connect another NICOS client)
python start_nicos.py --instrument odin --mode mcstas    # ODIN: full McStas instead of the hybrid model
python start_nicos.py --instrument odin --no-gui --background   # no console needed (stop the process to end)
```

**Login** (accounts of `nicos_twin/<instrument>/setups/special/daemon.py`; the daemon only accepts connections from this
computer): `student` / `student` (user: can measure), `guest` / *(empty)*, `admin` / `admin`.

## 3. Taking data: commands, as on the real instruments

Yes, at ESS data are taken by typing commands (or running scripts of commands): NICOS is a Python command line. The
GUI buttons (command builder, script builder) only write these commands for you. In the GUI, tab **Instrument
interaction**, or in any NICOS client:

```python
NewExperiment(1234, 'Bragg edges of iron')     # 1. your experiment: proposal number and title
                                               #    (or the Experiment tab: Proposal ID, title, users, Apply)
read()                                         # state of all devices
move(shutter, 'closed')
with nexusfile_open('dark'):                   # 2. record: everything in the block is written to file
    count(t=10)
move(shutter, 'open', stage_x, 500)            # sample out of the beam (mm)
with nexusfile_open('open beam'):
    count(t=10)
move(stage_x, 0)
with nexusfile_open('iron plate'):
    count(t=10)
list_filewriting_jobs()                        # what was written
```
`count()` alone also writes a file (as at ESS with the file-writer data sink), with the current experiment title;
without a proposal number NICOS refuses to count ("cannot start writing as proposal number not set"), as at ESS.
`nexusfile_open('title')` sets the title, which is also the experiment title shown at the top of the GUI.
The tab **Detector image** shows the image of the last count; the files go to
`<TWIN_RUN_ROOT>/data/<instrument>/<year>/<proposal>/raw/` (shown by `det.lastfile`). Scripts: tab **Scripting**
(editor: Save, Run), saved by default in the scripts folder of the proposal,
`<TWIN_RUN_ROOT>/data/<instrument>/<year>/<proposal>/scripts/`, where `run('my_script.py')` also finds them; or
`run_nicos_script.py my_script.py` from a terminal (§ 4).

Devices of **ODIN** (`nicos_twin/odin/setups/odin.py`):

| NICOS device | Values |
|---|---|
| `choppers` | `'wfm'`, `'natural'`, `'white'` |
| `wfm_delta` | 0.1, 0.3, 0.45 (m) |
| `shutter` | `'open'`, `'closed'` |
| `pinhole` | 0.01, 0.02, 0.03, 0.04 (m) |
| `diffuser` | `'in'`, `'out'` |
| `stage_x` | −500 to 500 mm (out of the beam: 500) |
| `stage_rot` | −180 to 180 deg (tomography: `scan(stage_rot, 0, 3, 60, t=10)`) |
| `sample_holder` | `'iron_plate'` |
| `det` | Timepix3 imaging detector, preset `t` (s); image 128 × 128 |
| read-only (setup `choppers`) | `wfm1_speed`, `wfm1_delay` … `foc5_speed`, `foc5_delay` (Hz, ms; names of the ODIN NeXus file; 0 when the mode stops the chopper), `pulse_skipping`, `wfmc_separation` |

Devices of **LoKI** (`nicos_twin/loki/setups/loki.py`), first version:

| NICOS device | Values |
|---|---|
| `heavy_shutter` | `'Open'`, `'Closed'` (ESS name; main shutter) |
| `fast_shutter` | `'Open'`, `'Closed'` (ESS name; just before the sample) |
| `collimation` | `'3m'`, `'5m'`, `'8m'` (longer: lower Q, better resolution, less flux) |
| `pulse_skipping` | `'off'`, `'on'` (choppers at 7 Hz, one pulse in two, band 3–21.4 Å; with `'3m'` only) |
| `detector_distance` | 5.0, 10.0 (m; rear detector bank) |
| `sample_holder` | `'silica_spheres'` |
| `det` | the 9 tube panels; preset `t` (s); image: rear panel (392 × 250 pixels); file: I(Q) per bank |
| read-only (setup `choppers`) | `ch1_speed`, `ch1a_delay`, `ch1b_delay`, `ch2_speed`, `ch2a_delay`, `ch2b_delay` (Hz, ms; bandwidth and frame-overlap chopper pairs, delays computed as in the official model), `wavelength_band` |

A value outside the allowed list or limits is refused by NICOS itself ("Out of bounds"); a combination the twin does
not have (e.g. `pulse_skipping` on with `collimation` 8m) is refused by the twin with the list of the available ones.
The read-only devices show what the settings imply (`read('choppers')`... or the device list of the GUI): at ESS
the chopper speeds and phases are devices too.

## 4. Files

| File | Role |
|---|---|
| `start_nicos.py` | launcher: instrument choice, twin server + NICOS cache, poller, daemon + GUI |
| `run_nicos_script.py` | runs NICOS commands from a terminal (`-c "..."` or a script file); used in the container and in tests |
| `nicos_twin/devices.py` | `TwinSwitch`, `TwinMotor` (Moveables), `TwinDetector` (Measurable with image), `TwinExperiment` |
| `nicos_twin/commands.py` | ESS recording commands: `nexusfile_open`, `start_filewriting`, `stop_filewriting`, `list_filewriting_jobs` |
| `nicos_twin/gui.py` | ESS GUI main window with a workaround for a NICOS bug (missing action at the tested commit) |
| `nicos_twin/<instrument>/nicos.conf` | setup folders of the instrument |
| `nicos_twin/<instrument>/setups/` | `startup.py`, `<instrument>.py` (devices), `system.py` (instrument, experiment, data sinks, as in `nicos_ess`), `special/` (cache, poller, daemon) |
| `nicos_twin/<instrument>/guiconfig.py` | copy of `nicos_ess/<instrument>/guiconfig.py` |

Outputs in `<TWIN_RUN_ROOT>/` (default `~/McStas_runs/twin/`): `data/<instrument>/<year>/<proposal>/raw/` (data files
and the logbook `log.jsonl` of the twin), `nicos/*.log` (one log per service), `nicos/<instrument>/cache/` (NICOS
cache). NICOS's own logs and pid files: `log/` and `pid/` in the NICOS root.

Adding an instrument: the twin in `twin/<instrument>/` with the class interface of `VirtualOdin` (devices, move,
count, scan, status, use_folder), its entry in `INSTRUMENTS` of `../twin_server.py` and of `start_nicos.py`, and a
sub-package `nicos_twin/<instrument>/` built from `nicos_ess/<instrument>/`.

## 5. Installation

**Easiest: the container image** (`../container/`, Linux): NICOS is already installed. Nothing to do.

**On Windows** (`%USERPROFILE%` is your home folder, e.g. `C:\Users\you`):
1. NICOS sources in `%USERPROFILE%\McStas_runs\nicos_src` (other place: variable `NICOS_ROOT`):
   ```
   git clone --depth 1 https://github.com/mlz-ictrl/nicos %USERPROFILE%\McStas_runs\nicos_src
   ```
   (version tested: commit `44bec9c`). A shallow clone has no version tag, and NICOS refuses to start without a
   version number: create the file `nicos\RELEASE-VERSION` (ignored by git, as in the NICOS release tarballs) with
   the content `3.13.2.dev0+g44bec9c` (last release tag + commit). Nothing else is changed in the NICOS repository.
2. Separate conda environment:
   ```
   conda create -n nicos -c conda-forge python=3.12 numpy=1.26
   ```
3. `nicos-pyctl` (C extension of the daemon, from the MLZ package index) must be compiled with Visual Studio. From
   **PowerShell**, with the compiler environment set up by the `mcstas` env activation (from Git Bash, the Unix
   `link.exe` of Git shadows the Visual Studio linker and the build fails):
   ```
   conda run -n mcstas %USERPROFILE%\AppData\Local\miniforge3\envs\nicos\python.exe -m pip install --extra-index-url https://forge.frm2.tum.de/simple nicos-pyctl
   ```
4. Remaining requirements, GUI, and what the ESS setups need (`yuos_query`: ESS experiment; `h5py`, `pyqtgraph`: ESS
   GUI panels):
   ```
   cd %USERPROFILE%\McStas_runs\nicos_src
   %USERPROFILE%\AppData\Local\miniforge3\envs\nicos\python.exe -m pip install -r requirements.txt PyQt5 PyQtWebEngine QScintilla gr pyqtgraph "h5py<3.15" https://github.com/ess-dmsc/yuos_query/releases/download/v0.1.21/yuos_query-0.1.21-py3-none-any.whl
   ```
The launcher runs the twin server with its own Python (start it from the activated twin environment) and finds the
`nicos` environment in the same conda installation; otherwise: variables `MCSTAS_PYTHON`, `NICOS_PYTHON`,
`CONDA_ROOT`.

**On Linux** (without the container): the same steps, without Visual Studio (`nicos-pyctl` compiles with gcc).
The commands are those of `../container/Containerfile`.

## 6. Windows and Linux notes
- **Symbolic links**: NICOS creates "current" links (experiment folder, cache day, log files); Windows only allows them
  with administrator rights or developer mode. `TwinExperiment` disables the experiment links; the cache prints a
  harmless warning ("error setting lastday symlink").
- **Dry run** (simulation of a script before running it, in the GUI) uses `fork` and is not available on Windows.
- Stopping: the launcher kills the whole process tree of each service (`taskkill /T`). Closing the GUI of a launcher
  started with `--background` stops everything.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Another twin with NICOS is already running` | services of a previous session | Enter in its launcher window (or close it), then start again |
| `cannot start writing as proposal number not set` | no experiment yet | `NewExperiment(1234, 'title')` or the Experiment tab |
| `Cannot find a version number` | shallow NICOS clone | create `nicos/RELEASE-VERSION` (§ 5.1) |
| `No module named 'yuos_query'` / `'pyqtgraph'` | ESS requirements missing | § 5.4 |
| `no answer from the twin server` (NICOS error) | twin server not running | start via the launcher; check `<TWIN_RUN_ROOT>/nicos/twin_server.log` |
| GUI login refused | wrong account | § 2 (`student` / `student`) |
| device values shown as "-" in the GUI | poller not running | use the launcher (it starts `nicos-poller`) |

## 8. Validation (2026-11-04, Windows)
- ODIN, scripted session through the daemon: `count(t=2)` without proposal refused with the ESS message;
  `NewExperiment(1234, ...)`, then `with nexusfile_open('open beam'): count(t=5)` → `data/odin/2026/1234/raw/odin_000001.nxs`
  (2.7 million counts), job listed by `list_filewriting_jobs()`; sample in the beam: 2.1 million counts; shutter
  closed: 16 counts (background).
- ESS GUI (`nicos_ess/odin/guiconfig.py`): starts and connects, header "Instrument: ODIN, Experiment: <title>",
  Experiment tab with the proposal number and title editable. **Still to check by a user**: the detector image
  (tab Instrument interaction → Detector image) after a count.
- LoKI: `move(heavy_shutter, 'Open', fast_shutter, 'Open')`, `with nexusfile_open('silica spheres, 10 min'):
  count(t=600)` → `data/loki/2026/3001/raw/loki_000001.h5` (I(Q) of the 3 banks), in 25 s once the simulations are
  cached.
- Linux (container, every build): ODIN services and a measurement through NICOS with `nexusfile_open`
  (`../container/smoke_test.py`).

## 9. Still to do
- NICOS GUI for students when the twin runs in the container or on a server: the daemon accepts connections from
  its own computer only (`daemon.py`: `server = 'localhost'`). Options: a NICOS GUI in the browser (noVNC), or the
  daemon opened to the network with real passwords (the demo accounts above must then be changed).
- Closer to ESS: the twin publishing its events to Kafka and the real ESS file-writer writing the NeXus files (one
  file per `nexusfile_open` block), and devices as simulated EPICS process variables, so that the unmodified
  `nicos_ess` setups can be used. To discuss with ESS (ECDC), who built such test set-ups (simulated AMOR, NeXus
  streamer).
- LoKI in the container image (official model and its precomputed upstream part).
- DREAM and BIFROST: `nicos_twin/dream/`, `nicos_twin/bifrost/` once their twins have devices.
