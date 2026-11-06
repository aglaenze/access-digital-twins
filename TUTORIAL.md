# Tutorial: your first session with a digital twin

This guide takes you, step by step, from nothing to your first measurement with a digital twin of an instrument of
the European Spallation Source (ESS). No prior knowledge of McStas or NICOS is needed. Commands to type are in gray
boxes; copy them exactly.

**Which instruments?** The twins do not all offer the same things yet:

| Instrument | Technique | Web page | Console | NICOS | Python script |
|---|---|:-:|:-:|:-:|:-:|
| ODIN | neutron imaging | yes | yes | yes | yes |
| LoKI | small-angle scattering (SANS) | yes | yes | yes | yes |
| DREAM, BIFROST | diffraction, inelastic scattering | — | — | — | — (waiting for the official McStas models) |

The installation (part 1) is common to all twins. **You choose the instrument when you start it** (console:
`--instrument odin` or `loki`; NICOS: the launcher asks), as you would walk into the control room of that instrument
at ESS. The examples of parts 2–4 use **ODIN** (iron plate); part 6 gives the same steps for LoKI.

**What you will do**: install the twins (part 1), then measure with one of the three ways to use a twin (parts 2–4):
a web page, a console, or NICOS, the control software of the real ESS instruments. Part 5 tells you where your data are
and how to analyze them; part 6 covers the other instruments.

**In a course** you will rather use the **app** (first section above): its catalogue of exercises: choose the
instrument, then an exercise, then the way in: a guided web page (BSc), a notebook with tasks
and automatic checks (MSc), or a beamtime with NICOS (a proposal, a budget, your own decisions).

Expect: 20–60 min for the installation (mostly downloads), a few minutes per measurement session.

---

## Students: the app (nothing else to read)

1. Install **Podman Desktop** (https://podman-desktop.io, free) and start it once: it sets itself up. The app runs the
   instruments in it.
2. Download the app for your computer from https://github.com/aglaenze/access-digital-twins/releases/tag/app-latest:
   **Windows** the `.exe`, **macOS** the `.dmg` (`arm64` for Apple Silicon M1–M4, `x64` for Intel), **Linux** the
   `.AppImage`. Install it (Windows: double-click; it installs for you only, no administrator rights; macOS: drag it
   to *Applications*).
   The app is not signed yet: **Windows** says "Windows protected your PC": *More info* > *Run anyway*; **macOS**
   refuses the first time: *System Settings* > *Privacy & Security* > *Open Anyway*.
3. Open **ESS digital twins**. The first time it downloads the instruments (several GB, 10–30 min, once). Create your
   account (name, email, password); **write down the recovery code** it shows: it lets you choose a new password if
   you forget yours.

Then: choose an instrument and an exercise in the catalogue; it opens in a tab of the app; come back to the catalogue
when you want: your work is kept (answers, measurements, notebooks). Each exercise gives you a **role and a mission**;
its questions are interactive (a wrong answer is explained, with a hint; you can show the answer). At the end of an
exercise, **Submit my work** makes a file: save it and send it to your teacher (email, or the course page).

What you see depends on your level. **BSc**: guided pages, no code, no NICOS. **MSc**: a notebook; you measure first
in NICOS (button *Open NICOS* in the notebook, step by step), then you analyze. **Beamtime** and **free beamtime**: your
proposal, your sample (the sample builder), NICOS and your analysis, all from the starter notebook.

The rest of this guide is for teachers and for students who want to go further (console, scripts, local installation).
Teachers with the local installation (route B, Windows) run the app from the repository: `twin/app/README.md`.

---

## Part 1 — Installation: choose route A or route B

| | Route A: container (recommended) | Route B: local installation |
|---|---|---|
| For | everyone (Windows, macOS, Linux) | Windows users who want to change the code |
| You install | Podman Desktop (free) or Docker Desktop | Miniforge, Git, Visual Studio Build Tools, NICOS (optional) |
| Disk space | ~10 GB | ~10 GB |
| Ways to use the twin | catalogue, web pages, console, NICOS with its window (in the browser) | web pages, console, NICOS (with its window) |

### Route A — the container

A container is a ready-made Linux system with everything already installed (McStas, the official ODIN and LoKI
models, the twins, the ESS analysis software, JupyterLab, NICOS and its window). You download it once and run it on
your computer.

**The shortest way** is the app (section "Students: the app" above). The steps below start the container by hand,
with JupyterLab and all the files (for teachers, and for the console and script ways of parts 3–4).

1. **Install Podman Desktop** (https://podman-desktop.io, free) or **Docker Desktop**
   (https://www.docker.com/products/docker-desktop/; paid for large organizations) — install, restart if asked, then
   start it and wait until its engine runs. (On Windows it may ask to enable WSL 2: accept.) With Podman, type
   `podman` instead of `docker` in the commands below. Macs with Apple Silicon (M1–M4) get an image made for them.
2. **Open a terminal**: on Windows "PowerShell", on macOS "Terminal".
3. **Download the image** (a few GB, a few minutes):
   ```
   docker pull ghcr.io/aglaenze/access-digital-twins:latest
   ```
4. **Start the twin**:
   ```
   docker run -it --name twin -p 8888:8888 -p 8866:8866 -v twin-data:/data --shm-size=1g ghcr.io/aglaenze/access-digital-twins:latest
   ```
   - `-p 8888:8888`: JupyterLab will be reachable in your browser;
   - `-v twin-data:/data`: your measurements are kept in a Docker volume named `twin-data`, even after the container
     is stopped.

   **The first time only**, the twin downloads the precomputed McStas simulations of the ODIN beamline (1.5 GB):
   you see `downloading front_... .tar` with a progress counter. Then JupyterLab starts and prints lines like:
   ```
   http://127.0.0.1:8888/lab?token=3f2a...
   ```
5. **Open that address** (the one with `127.0.0.1` and the token) in your browser: you see JupyterLab, with the files
   of the twin on the left (the exercises themselves are used through the app).
6. **Check that everything works** (optional, 2 min): in JupyterLab, *File → New → Terminal*, then
   ```
   python container/smoke_test.py
   ```
   It should end with `ALL PASSED`.

To stop: `Ctrl+C` in the terminal of step 4. To start again later: `docker start -ai twin` (the downloads are not
repeated). To start from scratch: `docker rm twin`, then step 4 again.

### Route B — local installation (Windows)

1. **Install the tools** (once):
   - Miniforge (Python and conda): https://conda-forge.org/download/ — installer for Windows, default options;
   - Git: https://git-scm.com/download/win — default options;
   - Visual Studio Build Tools (C compiler, needed by McStas): https://visualstudio.microsoft.com/visual-cpp-build-tools/
     — in the installer, tick **"Desktop development with C++"**.
2. **Open "Miniforge Prompt"** (Start menu). All the following commands are typed there.
3. **Download the twin** (this repository) into your home folder:
   ```
   cd %USERPROFILE%
   git clone https://github.com/aglaenze/access-digital-twins.git
   cd access-digital-twins
   ```
4. **Create the Python environment** (~10 min, ~5 GB):
   ```
   conda env create -f container\environment-windows.yml
   conda activate twins
   ```
   From now on, every time you open a new Miniforge Prompt: `conda activate twins` and
   `cd %USERPROFILE%\access-digital-twins`.
5. **Install the official McStas model of ODIN** (from the ESS):
   ```
   git clone https://git.esss.dk/dmsc-instrumentmodels/odin.git %USERPROFILE%\McStas_runs\odin_model
   git -C %USERPROFILE%\McStas_runs\odin_model checkout ea4fc94
   pip install --no-deps -e %USERPROFILE%\McStas_runs\odin_model\instrpy -e %USERPROFILE%\McStas_runs\odin_model\extra
   ```
6. **Download the precomputed simulations of the beamline** (1.5 GB, into `%USERPROFILE%\McStas_runs\twin`):
   ```
   python container\fetch_fronts.py
   ```
7. **Check that everything works** (2–5 min; the first McStas compilation takes a minute):
   ```
   python container\smoke_test.py --no-nicos
   ```
   It should end with `ALL PASSED`.
8. *(Optional, only for part 4 with the graphical interface)* install NICOS: `nicos/README.md` § 5.
9. *(Optional, only for the LoKI twin, part 6)* install the official McStas model of LoKI and download its
   precomputed upstream part (56 MB; computing it yourself takes ~15 min on 8 cores):
   ```
   git clone https://git.esss.dk/dmsc-instrumentmodels/LOKI.git %USERPROFILE%\McStas_runs\LOKI
   python container\fetch_fronts.py --instrument loki
   ```

Results never go into the repository folder: they go to `%USERPROFILE%\McStas_runs\twin` (McStas does not accept
spaces in paths, so this folder must not be in OneDrive or a folder with spaces).

---

## Part 2 — Way 1: the web page (simplest)

A page with buttons: you set the instrument, measure, and see your transmission spectrum.

- **Route A**: in JupyterLab, open the folder `odin`, then double-click `ODIN_virtual.ipynb`; in the toolbar of
  the notebook, click the button **"Render with Voilà"**. The page opens in a new JupyterLab tab. (Alternatively, start the container with the page only: `docker run -it --rm -p 8866:8866 -v twin-data:/data
  ghcr.io/aglaenze/access-digital-twins:latest voila`, then open http://127.0.0.1:8866.)
- **Route B**:
  ```
  cd odin
  voila ODIN_virtual.ipynb
  ```
  Your browser opens the page.

Then follow the page from top to bottom. In section **1. Operate the instrument**, for each of the three
measurements below, set the controls, give a title, choose the time and click **Count**:
1. **Dark run**: *Shutter* closed, title `dark`, 10 s (measures the background of the detector).
2. **Open beam**: *Shutter* open, *Stage x* = 500 mm (sample out of the beam), title `open beam`, 30 s (measures
   the beam without sample).
3. **Sample**: *Stage x* = 0 mm (sample in the beam), title `iron plate`, 30 s.

Section **2. Your measurements** lists your files (the button *Review my logbook* checks your experimental practice).
In section **3. Reduce**, choose the sample, open-beam and dark files and click **Compute transmission**: the page
divides sample by open beam (after removing the dark). You see the image of the plate and its transmission spectrum,
with sharp jumps: the **Bragg edges** of iron (the last one at 4.05 Å). Section 4 asks you questions about it.

The very first measurement in a new configuration takes 1–2 minutes (the twin runs McStas once and keeps the
result); the following ones take a few seconds.

For a game: `odin/ODIN_mission.ipynb` (same way): identify three unknown metals with a limited beam time.

---

## Part 3 — Way 2: the console (type commands like on the real instrument)

You need **two terminals**: one is the instrument, the other is your control station.

- Route A: in JupyterLab, *File → New → Terminal*, twice.
- Route B: two Miniforge Prompts, each with `conda activate twins` and `cd %USERPROFILE%\access-digital-twins`.

**Terminal 1 — start the instrument:**
```
python twin_server.py --instrument odin --session my_first_session
```
Leave it running (it shows what the instrument does).

**Terminal 2 — control it:**
```
python -i twin_console.py
```
You get a `>>>` prompt. Type, one line at a time:
```
status()
count(10, title="dark")
move(shutter, "open", stage_x, 0.5)
count(10, title="open beam")
move(stage_x, 0.0)
count(10, title="iron plate")
log()
```
- `status()` shows the devices (choppers, shutter, pinhole, diffuser, sample stage);
- `move(device, value, ...)` changes them: `stage_x` is the sample position in meters (0.5 m = out of the beam);
- `count(t)` measures for `t` seconds and writes a NeXus file (the ESS data format);
- try a forbidden value, e.g. `move(pinhole, 0.025)`: the instrument refuses, as a real one would;
- `help_twin()` lists all commands. Quit with `exit()`.

Then analyze the three files: part 5.

---

## Part 4 — Way 3: NICOS (the control software used at ESS)

NICOS is the software that controls the real instruments. Here it controls the twin.

At ESS every instrument has its own NICOS (same program, its own devices and window), running on the computers of
that instrument. Here the launcher asks which instrument you want: that is your "control room". As on the real
instruments, you take data by **typing commands** (or running scripts of commands); the buttons of the window only
write these commands for you.

### With the graphical interface (route B, after installing NICOS)
```
python nicos\start_nicos.py
```
Answer `1` (ODIN). After ~30 s the NICOS window of ESS opens. Log in with user **student**, password **student**
(server `localhost:1301`).

1. Tab **Experiment**: type a *Proposal ID* (any number, e.g. `1234`: at ESS it is the number of your accepted
   proposal), a title, your name in *Users*, then **Apply**. Without a proposal NICOS refuses to record data, as at
   ESS.
2. Tab **Instrument interaction**: type in the command line (one line, then Enter; or several lines in the tab
   **Scripting**, then Run):
   ```
   read()
   move(shutter, 'closed')
   with nexusfile_open('dark'):
       count(t=10)
   move(shutter, 'open', stage_x, 500)
   with nexusfile_open('open beam'):
       count(t=10)
   move(stage_x, 0)
   with nexusfile_open('iron plate'):
       count(t=10)
   ```
   In **Scripting**, *Save* proposes the scripts folder of your proposal
   (`McStas_runs\twin\data\odin\<year>\<proposal>\scripts\`); a saved script can be run again later with
   `run('my_script.py')`.
   `with nexusfile_open('title'):` is the ESS way of recording: what is measured in the indented block is written to
   a data file with this title. (In NICOS, the stage position is in **millimeters**: 500 mm = out of the beam.)
3. The devices and their values are on the right; the image of the last count is in **Detector image**;
   `list_filewriting_jobs()` lists the files written.

To stop: press Enter in the terminal where you started NICOS.

**Live data, as at ESS** (ODIN and LoKI): start with `python nicos\start_nicos.py --instrument odin --live` (needs Kafka and
just-bin-it, installed as in `nicos/README.md`, "Live data"). A count then takes its real time, and during it the tab
**Detector image** shows the image and the spectrum of the arrival times filling up (panels `live_image` and
`live_tof`), as on the real instrument where the neutrons are streamed by Kafka and histogrammed by just-bin-it.

### With the graphical interface (route A, in the container: in your browser)
In the app: button **Open NICOS** of an MSc or beamtime exercise: NICOS of the instrument of the exercise opens (by
hand: the address `/desktop/` of the server, where you choose the instrument).
The control room opens in a new window; after about a minute the NICOS window is there,
full screen and logged in. Continue as in steps 1–3 above. Close the NICOS window to stop NICOS and come back to the
choice of the instrument.

### With text commands (route A, without the desktop)
Terminal 1 (JupyterLab terminal):
```
python nicos/start_nicos.py --instrument odin --no-gui --background
```
Wait for `ODIN services ready`. Terminal 2: write your commands in a file, e.g. `my_session.py`
(JupyterLab: *File → New → Text File*):
```
NewExperiment(1234, 'Bragg edges of iron')
move(shutter, 'open', stage_x, 500)
with nexusfile_open('open beam'):
    count(t=10)
```
and run it:
```
$CONDA_ROOT/envs/nicos/bin/python nicos/run_nicos_script.py my_session.py
```
You see what NICOS answers (devices moving, file written). To stop the services: `Ctrl+C` in terminal 1.

---

## Part 5 — Your data and their analysis

**Where are the files?** Web page and console: one folder per session; NICOS: one folder per proposal, as at ESS:
- route A: `/data/twin/odin/<session>/` and `/data/twin/data/odin/<year>/<proposal>/raw/` in the container (visible in
  JupyterLab's terminal: `ls /data/twin/odin`);
- route B: `%USERPROFILE%\McStas_runs\twin\odin\<session>\` and
  `%USERPROFILE%\McStas_runs\twin\data\odin\<year>\<proposal>\raw\`.

Each measurement is a NeXus file `odin_000001.nxs`, `odin_000002.nxs`, ... (the same format as at ESS: every
detected neutron with its pixel and arrival time, plus the state of the instrument), and `log.jsonl` is the logbook
of the session.

**Analyze them** with the notebook `odin/ODIN_analysis.ipynb` (open it in JupyterLab; route B: `jupyter lab` in the
folder `twin`). Write your folder in its first cell and run the cells one after the other: it reads the logbook,
finds your dark, open beam and sample, shows what is inside a NeXus file, reduces the data with the official ESS
software (transmission spectrum and image) and fits the Bragg edges of iron to give the distance between its atomic
planes. Leave `FOLDER = None` to try it first on a small demonstration session (about 1 min).

The heart of it fits in a few lines, if you prefer your own notebook (*File → New → Notebook*, in the folder `odin`):
```python
import odin_reduction as red
folder = "/data/twin/odin/my_first_session"        # route B: r"C:\Users\<you>\McStas_runs\twin\odin\my_first_session"
r = red.reduce(f"{folder}/odin_000003.nxs", f"{folder}/odin_000002.nxs", dark=f"{folder}/odin_000001.nxs")
r["spectrum"].plot()       # transmission T(λ) of the plate: look for the Bragg edges
r["image"].plot()          # transmission image
```
(files 1, 2, 3 = dark, open beam, sample, in the order you measured them).

**Other samples**: the page and NICOS offer several samples (`steel_steps`, `iron_copper`, ...;
`move(sample_holder, 'steel_steps')`, `sample_info()` describes it). For a free beamtime you can design your own with
the sample builder, `Sample_builder.ipynb` (see README.md, "Samples").

**Going further**: other chopper modes (`move(choppers, "natural")`, `"white"`; in NICOS, the devices `wfm1_speed`,
`bpc1_delay`, ... show the speed and delay of each chopper, which follow the mode: compare them in the three modes),
tomography (rotate the sample with
`scan(stage_rot, 0, 3, 60, t=10)`), the games of `ODIN_mission.ipynb`, the 3D view of the neutrons in the beamline
(`python odin/show_3d.py`, route B). Everything is explained in `odin/README.md`.

---

## Part 6 — Other instruments

### LoKI (small-angle neutron scattering)

The LoKI twin can be used from a web page, from Python, from the console and from NICOS, with both routes: route A
(the container contains it) and route B (step 9 of the installation). It needs about 6 GB of free memory during a
measurement (route A: memory given to Docker). As on the real LoKI, each measurement is a **NeXus event file** (every
detected neutron with its pixel of the real detector and its arrival time) and the reduction to I(Q) is done by the
official ESS software (`esssans`). A SANS experiment needs **three measurements** in the same configuration: the
sample (`silica_spheres`), the solvent alone (`d2o`, subtracted) and the empty beam (`empty_beam`, reference of the
transmission). Its test case measures the three for dilute silica spheres (radius 50 Å) and fits their size (route
A: in a JupyterLab terminal):
```
cd loki
python easy_case.py
```
The first run takes ~10 min (McStas simulations of the samples and the calibration of the configuration, then kept
in the results folder `twin/loki`), the next ones a few minutes. It prints the radius of gyration (expected ≈ 39 Å),
the radius and the volume fraction from the sphere model of sasmodels, and saves the figure `figures/easy_case.png`.
To measure yourself, in Python (started in the folder `loki`):
```python
from virtual_loki import VirtualLoki
import loki_reduction as red
loki = VirtualLoki(session="my_first_sans")
loki.move(collimation="3m", heavy_shutter="open", shutter="open")
files = {}
for s in ("empty_beam", "d2o", "silica_spheres"):
    loki.move(sample=s)
    files[s] = loki.count(600)          # 600 s; returns the NeXus file written
iq = red.reduce(files["silica_spheres"], background=files["d2o"], empty_beam=files["empty_beam"])
iq["loki_detector_0"].plot()            # I(Q) of the rear bank (esssans), divide by the thickness (0.1 cm) for cm⁻¹
```
**Web page**: as in part 2, with `loki/LoKI_virtual.ipynb` (route A: open it in JupyterLab, then "Render with
Voilà"; route B: `voila LoKI_virtual.ipynb` in the folder `loki`). It gives the settings of the measurements (empty
beam, solvent, sample, in two configurations), shows the image of the rear detector after each count, and analyzes
the curve (esssans, Guinier and the sphere model of sasmodels).

**Console**: as in part 3, with `python twin_server.py --instrument loki --session my_first_sans` in terminal 1;
devices `heavy_shutter`, `shutter`, `collimation` (`3m`, `5m`, `8m`), `pulse_skipping` (`off`, `on`: choppers at
7 Hz, wavelength band 3–21.4 Å, with `3m` only), `detector_distance` (5 or 10 m; 10 m only with `8m`: with a wider wavelength band the neutrons of one pulse
would overlap with those of the next one, "frame overlap", and the twin refuses it with the explanation), `sample`. `status()` also shows the
chopper speeds and delays, which follow the configuration.

**NICOS**: `python nicos\start_nicos.py`, answer `2` (LoKI). The window is the one of the real LoKI. In the
Experiment tab give a proposal number, then:
```
move(heavy_shutter, 'Open', fast_shutter, 'Open')
move(sample_holder, 'empty_beam')
with nexusfile_open('empty beam'):
    count(t=60)
move(sample_holder, 'd2o')
with nexusfile_open('D2O'):
    count(t=600)
move(sample_holder, 'silica_spheres')
with nexusfile_open('silica spheres, 10 min'):
    count(t=600)
```
(`heavy_shutter` and `fast_shutter` are the names used by the NICOS of the real LoKI.) Each file holds the events of
the 9 detector banks and of the monitors; the Detector image tab shows the rear detector. To reach lower Q, change the configuration, e.g.
`move(collimation, '8m', detector_distance, 10)`, then count again: compare the Q range of the rear bank and the
counting time needed for the same error bars. Details: `loki/README.md`.

**Analyze** with the notebook `loki/LoKI_analysis.ipynb` (`jupyter lab` in the folder `twin`): write your folder
(session or proposal) in its first cell, then run the cells. It finds your sample, solvent and empty beam in the
logbook, shows what is inside a NeXus file, reduces them with esssans (9 banks, solvent subtracted, absolute units),
finds the radius of gyration with a Guinier fit, and fits the sphere model of sasmodels (the engine of SasView) to
the whole curve: radius and volume fraction. Leave `FOLDER = None` to measure first.

### DREAM, BIFROST

Not started yet: their official McStas models are not yet available to the project (ESS repositories
`dmsc-instrumentmodels/dream`, `dmsc-instrumentmodels/bifrost`). They will appear here when their twin exists.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| `docker: command not found` / "Cannot connect to the Docker daemon" | start Docker Desktop and wait for "Engine running" |
| `port is already allocated` | another container uses the port: `docker rm -f twin`, then start again |
| `The container name "/twin" is already in use` | `docker start -ai twin` (to continue) or `docker rm twin` (to start over) |
| the first count takes minutes | normal the first time in each configuration (McStas simulation, then cached) |
| `upstream part missing` | the beamline simulations were not downloaded: `python container/fetch_fronts.py` |
| `McStas compilation failed` (route B) | Visual Studio Build Tools with "Desktop development with C++" missing |
| `no answer from the instrument` (console) | terminal 1 (`twin_server.py`) is not running |
| NICOS login refused | user `student`, password `student` |

More: `odin/README.md` § 8 and `nicos/README.md` § 7. Questions and bugs: open an issue on
https://github.com/aglaenze/access-digital-twins/issues.
