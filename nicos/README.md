# NICOS for the digital twins

*Created 2026-11-03.* NICOS (Networked Instrument Control System, MLZ / ESS) drives the virtual instruments exactly as
it drives the real ones: devices are moved with `move`, measurements are made with `count` and `scan`, the GUI shows
the devices, the console and the detector image. The twin (McStas, hybrid model, NeXus files) runs in the background;
the user never sees McStas.

Status (2026-11-03): **working on Windows** for ODIN (cache, poller, daemon, GUI client: login and device values
checked by a user); **on Linux in the container image** (`../container/`): cache, poller and daemon, started by the
smoke test of every build (no GUI in the container yet). Student step-by-step guide: `../TUTORIAL.md`.

## 1. How it fits together

```
NICOS GUI (or any NICOS client)          conda env "nicos" (numpy < 2)
   │  login, commands
NICOS daemon + cache                      conda env "nicos"; setup package nicos_twin (this folder)
   │  nicos_twin devices: HTTP orders (move, count, status)
twin_server.py --instrument odin          conda env "mcstas" (numpy 2, McStas, essimaging)
   │
virtual ODIN (twin/odin/) → NeXus files in <TWIN_RUN_ROOT>/odin/<session>/
```

Why two environments: NICOS requires **numpy < 2** (`requirements.txt` of NICOS), while the twin (essimaging, scipp)
uses numpy 2. NICOS therefore does not import the twin: its devices send their orders to the twin server over HTTP
(local only), like the provisional console `../twin_console.py`. The McStas device of NICOS
(`nicos/devices/mcstas.py`, which needs Linux signals) is not used.

## 2. Quick start

```
python start_odin_nicos.py
```
(run it from this folder, with any Python, e.g. the `mcstas` env; in the container: `start.sh nicos`). It starts, in this order: the twin server (env
`mcstas`), the NICOS cache, poller (reads the devices every few seconds, so that the GUI shows their values) and
daemon (env `nicos`), then the NICOS GUI. Press Enter in that terminal to stop
everything. First count with a new configuration: 1–2 min (McStas simulation, then cached); then a few seconds.

**Login in the GUI** (accounts of `nicos_twin/odin/setups/special/daemon.py`; the daemon only accepts connections from
this computer):

| User name | Password | Rights |
|---|---|---|
| `student` | `student` | user: can run measurements (recommended) |
| `guest` | *(empty)* | guest |
| `admin` | `admin` | administrator |

Server: `localhost:1301` (filled in automatically).

Options:
```
python start_odin_nicos.py --session group_A           # data folder <TWIN_RUN_ROOT>/odin/group_A/
python start_odin_nicos.py --mode mcstas                # full McStas instead of the hybrid model (short counts)
python start_odin_nicos.py --no-gui                     # services only (connect another NICOS client)
python start_odin_nicos.py --no-gui --background        # services only, no console needed (stop the process to end)
```

## 3. Using it

In the GUI, tab **Command line** (or in any NICOS client):
```python
read()                                     # state of all devices
move(choppers, 'wfm', wfm_delta, 0.3)      # chopper mode
move(shutter, 'closed'); count(t=10)       # dark run
move(shutter, 'open', stage_x, 500)        # open beam: sample out of the beam (mm)
det.title = 'open beam'                    # title written in the next NeXus files
count(t=10)
move(stage_x, 0); det.title = 'iron plate'
count(t=10)
scan(stage_rot, 0, 3, 60, t=10)            # tomography: 60 projections of 10 s
det.lastfile                               # last NeXus file written
```
After each count, the tab **Detector image** shows the 128 × 128 detector image (live-view sink); the devices are
listed on the right. The NeXus files (ESS format) are written by the twin to `<TWIN_RUN_ROOT>/odin/<session>/`; reduce
them in a notebook (`twin/odin/odin_reduction.py`) or in the student page (`twin/odin/ODIN_virtual.ipynb`).

| NICOS device | Twin device | Values |
|---|---|---|
| `choppers` | `choppers` | `'wfm'`, `'natural'`, `'white'` |
| `wfm_delta` | `wfm_delta` | 0.1, 0.3, 0.45 (m) |
| `shutter` | `shutter` | `'open'`, `'closed'` |
| `pinhole` | `pinhole` | 0.01, 0.02, 0.03, 0.04 (m) |
| `diffuser` | `diffuser` | `'in'`, `'out'` |
| `stage_x` | `stage_x` | −500 to 500 **mm** (the twin uses m: factor `scale = 1e-3`) |
| `stage_rot` | `stage_rot` | −180 to 180 deg |
| `sample_holder` | `sample` | `'iron_plate'` (NICOS reserves the name `Sample`) |
| `det` | detector | preset `t` (s); values: counts, file number; array: image |

A value outside the allowed list or limits is refused by NICOS itself ("Out of bounds").

## 4. Files

| File | Role |
|---|---|
| `start_odin_nicos.py` | launcher (twin server + NICOS cache + daemon + GUI) |
| `nicos_twin/devices.py` | NICOS devices: `TwinSwitch`, `TwinMotor` (Moveables), `TwinDetector` (Measurable with image), `TwinExperiment` |
| `nicos_twin/odin/nicos.conf` | setup folders of the instrument |
| `nicos_twin/odin/setups/` | `startup.py` (loaded by the daemon), `odin.py` (devices), `system.py` (instrument, experiment, data sinks), `special/cache.py`, `special/poller.py`, `special/daemon.py` |
| `nicos_twin/odin/guiconfig.py` | GUI layout (standard NICOS panels) |

Outputs, in `<TWIN_RUN_ROOT>/nicos/` (default `~/McStas_runs/twin/nicos/`; the launcher passes `TWIN_RUN_ROOT` to
the setups): `*.log` (one per service, written by the launcher), `cache/` (NICOS cache database), `data/` (NICOS
experiment folders: scripts, scan files). NICOS's own logs and pid files: `log/` and `pid/` in the NICOS root.

Adding an instrument (e.g. LoKI): a sub-package `nicos_twin/loki/` with the same setups, and the instrument in
`INSTRUMENTS` of `../twin_server.py`.

## 5. Installation

**Easiest: the container image** (`../container/`, Linux): NICOS is already installed (sources at a fixed commit,
environment `nicos`, `requirements.txt`). Nothing to do.

**On Windows** (as on the development computer, 2026-11-03; `%USERPROFILE%` is your home folder, e.g. `C:\Users\you`):
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
4. Remaining requirements and GUI:
   ```
   cd %USERPROFILE%\McStas_runs\nicos_src
   %USERPROFILE%\AppData\Local\miniforge3\envs\nicos\python.exe -m pip install -r requirements.txt PyQt5 PyQtWebEngine QScintilla gr
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
- Stopping: the launcher kills the whole process tree of each service (`taskkill /T`).
- On Linux the same package works unchanged (no symbolic-link warning, dry run available); all paths have Linux
  defaults (§ 5).

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot find a version number` | shallow NICOS clone | create `nicos/RELEASE-VERSION` (§ 5.1) |
| `no answer from the twin server` (NICOS error) | twin server not running | start via the launcher; check `<TWIN_RUN_ROOT>/nicos/twin_server.log` |
| `counting without detector` | `SetDetectors(det)` not run | run `SetDetectors(det)`; normally done by `startup.py` |
| `setting parameter ... not possible in slave mode` | daemon not in master mode | `SetMode('master')` (done by `startup.py`) |
| GUI login refused | wrong account | § 2 (e.g. `student` / `student`) |
| device values shown as "-" in the GUI | poller not running | use the launcher (it starts `nicos-poller`) |
| a service stops at once | port already used (old services still running) | stop them (Task Manager: python.exe), restart |

## 8. Validation (2026-11-03)
Scripted session through the daemon (NICOS client API): `read()` shows the twin state; `move(shutter, 'open',
stage_x, 500)`; `count(t=5)` → `odin_000001.nxs`, 2 707 868 counts (open beam); sample in the beam: 2 145 255 counts;
`move(pinhole, 0.025)` refused by NICOS ("Out of bounds … allowed values"); `scan(stage_rot, 0, 30, 3, t=2)` → standard
NICOS scan table with counts and file number per angle (files 3–5). GUI on Windows: login and device panel with
the values of the twin checked by a user; **still to check**: the detector image in the live-view tab after a count.
Linux (container, every build): cache, poller and daemon start with the twin server (`../container/smoke_test.py`).

## 9. Still to do
- NICOS GUI for students when the twin runs in the container or on a server: the daemon accepts connections from
  its own computer only (`daemon.py`: `server = 'localhost'`). Options: a NICOS GUI in the browser (noVNC), or the
  daemon opened to the network with real passwords (the demo accounts above must then be changed).
- A NICOS setup for each new instrument (LoKI: `nicos_twin/loki/`).
