# Tutorial: your first session with a digital twin

This guide takes you, step by step, from nothing to your first measurement with the virtual ODIN (neutron imaging
at the European Spallation Source). No prior knowledge of McStas or NICOS is needed. Commands to type are in grey
boxes; copy them exactly.

**What you will do**: install the twin (part 1), then measure the transmission of an iron plate in one of three ways
(parts 2–4): in a web page, with a console, or with NICOS, the control software of the real instrument. Part 5 tells
you where your data are and how to analyse them.

Expect: 20–60 min for the installation (mostly downloads), a few minutes per measurement session.

---

## Part 1 — Installation: choose route A or route B

| | Route A: container (recommended) | Route B: local installation |
|---|---|---|
| For | everyone (Windows, macOS, Linux) | Windows users who want to change the code |
| You install | Docker Desktop | Miniforge, Git, Visual Studio Build Tools, NICOS (optional) |
| Disk space | ~8 GB | ~10 GB |
| Ways to use the twin | web page, console, NICOS (text commands) | web page, console, NICOS (with its graphical interface) |

### Route A — the container

A container is a ready-made Linux system with everything already installed (McStas, the official ODIN model, the
twin, the ESS analysis software, JupyterLab, NICOS). You download it once and run it on your computer.

1. **Install Docker Desktop**: https://www.docker.com/products/docker-desktop/ — install, restart if asked, then
   start Docker Desktop and wait until it says "Engine running". (On Windows it may ask to enable WSL 2: accept.)
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
   of the twin on the left.
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
- `move(device, value, ...)` changes them: `stage_x` is the sample position in metres (0.5 m = out of the beam);
- `count(t)` measures for `t` seconds and writes a NeXus file (the ESS data format);
- try a forbidden value, e.g. `move(pinhole, 0.025)`: the instrument refuses, as a real one would;
- `help_twin()` lists all commands. Quit with `exit()`.

Then analyse the three files: part 5.

---

## Part 4 — Way 3: NICOS (the control software used at ESS)

NICOS is the software that controls the real instruments. Here it controls the twin.

### With the graphical interface (route B, after installing NICOS)
```
python nicos\start_odin_nicos.py
```
After ~30 s the NICOS window opens. Log in with user **student**, password **student** (server `localhost:1301`).
In the tab *Command line*, type:
```
read()
move(shutter, 'closed'); count(t=10)
move(shutter, 'open', stage_x, 500)
det.title = 'open beam'; count(t=10)
move(stage_x, 0)
det.title = 'iron plate'; count(t=10)
```
(In NICOS, the stage position is in **millimetres**: 500 mm = out of the beam.) The devices and their values are
shown on the right. To stop: press Enter in the terminal where you started NICOS.

### With text commands (route A, in the container; no graphical interface yet)
Terminal 1 (JupyterLab terminal):
```
python nicos/start_odin_nicos.py --no-gui --background --session my_nicos_session
```
Wait for `Services ready`. Terminal 2:
```
$CONDA_ROOT/envs/nicos/bin/python nicos/run_nicos_script.py -c "read(); move(shutter, 'open', stage_x, 500); det.title = 'open beam'; count(t=10)"
```
You see what NICOS answers (devices moving, file written). A longer session can be written in a file (one NICOS
command per line) and run with `.../python nicos/run_nicos_script.py my_session.py`. To stop the services:
`Ctrl+C` in terminal 1.

---

## Part 5 — Your data and their analysis

**Where are the files?** One folder per session:
- route A: `/data/twin/odin/<session>/` in the container (visible in JupyterLab's terminal: `ls /data/twin/odin`);
- route B: `%USERPROFILE%\McStas_runs\twin\odin\<session>\`.

Each measurement is a NeXus file `odin_000001.nxs`, `odin_000002.nxs`, ... (the same format as at ESS: every
detected neutron with its pixel and arrival time, plus the state of the instrument), and `log.jsonl` is the logbook
of the session.

**Analyse them** in a notebook (JupyterLab: *File → New → Notebook*, in the folder `odin`), with the official ESS
reduction software:
```python
import odin_reduction as red
folder = "/data/twin/odin/my_first_session"        # route B: r"C:\Users\<you>\McStas_runs\twin\odin\my_first_session"
r = red.reduce(f"{folder}/odin_000003.nxs", f"{folder}/odin_000002.nxs", dark=f"{folder}/odin_000001.nxs")
r["spectrum"].plot()       # transmission T(λ) of the plate: look for the Bragg edges
r["image"].plot()          # transmission image
```
(files 1, 2, 3 = dark, open beam, sample, in the order you measured them).

**Going further**: other chopper modes (`move(choppers, "natural")`, `"white"`), tomography (rotate the sample with
`scan(stage_rot, 0, 3, 60, t=10)`), the games of `ODIN_mission.ipynb`, the 3D view of the neutrons in the beamline
(`python odin/show_3d.py`, route B). Everything is explained in `odin/README.md`.

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
