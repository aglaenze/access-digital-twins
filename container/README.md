# Container image of the digital twins

One Linux image with everything a student session needs: McStas 3.9.2 and NCrystal, the official McStas models of
ODIN and LoKI (ESS/DMSC, fixed commits), the twins of this repository, the ESS reduction software (essimaging, esssans,
scipp), sasmodels (the engine of SasView), JupyterLab and Voilà, NICOS with its window, Kafka and just-bin-it (live
data), and a Linux desktop shown in the browser. Students only need a browser: the start page is the catalogue of
exercises (`Catalogue.ipynb`), and the NICOS window opens on the desktop of JupyterLab.

## Why a container

The twin needs McStas with a C compiler and MPI, two Python environments (the twins use numpy 2, NICOS numpy < 2),
the official instrument model, NICOS from its sources and precomputed McStas results. Installing this on every
student computer is not realistic; the image is built once, from text files of this repository, with fixed versions,
and runs identically on a laptop, a DTU server, UCloud or ESS's VISA.

## Files

| File | Role |
|---|---|
| `Containerfile` | recipe of the image (base: `mambaorg/micromamba`, Debian, conda-forge packages) |
| `environment-mcstas.yml` | environment of the twins: same versions as on the development computer (Windows), with gcc and Open MPI instead of MSVC and MS-MPI |
| `environment-nicos.yml` | environment of NICOS (Python 3.12, numpy 1.26); NICOS's `requirements.txt` is installed on top |
| `start.sh` | entry point: `jupyter` (default), `voila`, `nicos`, `test`, or any command |
| `desktop/*.desktop` | menu entries and desktop icons "NICOS - ODIN", "NICOS - LoKI" of the desktop in the browser |
| `run_twin.ps1`, `run_twin.sh` | the twins as an app on a laptop (Windows; macOS/Linux): pull, start, open the catalogue |
| `desktop_test.sh`, `browser_desktop_test.sh` | GitHub Actions: the NICOS window on the desktop of the container, and the desktop and catalogue in Chrome (screenshots kept as an artifact of the run) |
| `fetch_fronts.py` | downloads the precomputed McStas upstream parts (release `fronts-v1`) into `$TWIN_RUN_ROOT/odin/front/` |
| `smoke_test.py` | test run after each build: tools, a measurement with the virtual ODIN compared with NCrystal, NICOS services and a measurement recorded through NICOS (`nexusfile_open`, as at ESS) |
| `../.github/workflows/container.yml` | GitHub Actions: build, test, publish to `ghcr.io/aglaenze/access-digital-twins` |

## Precomputed McStas upstream parts

The upstream part of each chopper mode of ODIN (ESS source → guides → choppers → guide exit, MCPL file) takes minutes
to an hour to compute and weighs up to 0.7 GB: too big for git, too slow to compute at each start; the same holds for
the upstream part of LoKI (source → benders → choppers → collimation → sample aperture, 3 m collimation: 56 MB, ~15 min
on 8 cores). They are attached to the GitHub release `fronts-v1` (one `.tar` per upstream part: `front_<mode>.tar` for
ODIN, `loki_front_<configuration>.tar` for LoKI, ~1.6 GB in total, with SHA-256 checksums) and downloaded by
`fetch_fronts.py` on the first start of a container into `/data/twin/odin/front/` and `/data/twin/loki/front/` (a
volume: kept between containers). The repository is public: no token is needed. To compute them yourself instead:
`odin_mcstas.front(...)` (see `../odin/README.md` § 2), `loki_mcstas.front(...)`.

## Use

```
docker run --rm -p 8888:8888 -v twin-data:/data ghcr.io/aglaenze/access-digital-twins
```
then open the address printed by JupyterLab, and in it the **catalogue** (`Catalogue.ipynb`, right-click > *Open
With > Voilà*, or `/voila/render/Catalogue.ipynb`). **The NICOS window**: *File > New Launcher > Desktop* opens a
Linux desktop in a browser tab (TigerVNC + noVNC through the port of JupyterLab, `jupyter-remote-desktop-proxy`);
in it, the icons or the menu *NICOS - ODIN* / *NICOS - LoKI* start the twin with NICOS and its window (login
`student` / `student`), as in the control room of the instrument. Other entry points: `... access-digital-twins voila` (student page,
port 8866), `... nicos` (NICOS services of ODIN, port 1301; another instrument: `-e TWIN_INSTRUMENT=...`), `... test`.
Results and NICOS data (`/data/twin/data/<instrument>/<year>/<proposal>/raw/`) are in the volume (`/data/twin`).
Live data as at ESS (Kafka broker + just-bin-it, ODIN): `-e TWIN_LIVE=1` with the entry point `nicos`
(`../nicos/README.md`, "Live data").
The image contains the ODIN and LoKI twins (official models at fixed commits, `~/odin_model` and `~/loki_model`). A
LoKI measurement needs about 6 GB of memory (downstream McStas part and its 440 MB of scattered neutrons, computed on
the first measurement of each sample, ~2 min): give Docker enough memory.

The image is built by GitHub Actions on every push to `main` (about 30–60 min the first time, faster afterward
thanks to the build cache); the run, its logs and the smoke test are in the "Actions" tab of the repository.

## On a laptop, as an app

`run_twin.ps1` (Windows) and `run_twin.sh` (macOS, Linux) do everything with one command: download the image (several
GB, once), start it with the volume `twin-data`, and open the catalogue in the browser. They need Podman (free;
Podman Desktop on Windows and macOS) or Docker (Docker Desktop is paid for organizations of more than 250 people).
On Windows and macOS both run a small Linux virtual machine (WSL2 on Windows), which the first installation sets up.
Limits of a laptop: the first measurement of a new sample or configuration runs McStas (minutes on 4 cores instead of
seconds to a minute on a server); Apple Silicon Macs run the image emulated (built for Intel/AMD), more slowly; and
no central logbook (teaching follow-up, didactics research) unless the files are collected.

## Still to do

- JupyterHub (one container per student, accounts) for a course; where to run it (DTU server, UCloud, VISA).
- An image for ARM processors (Apple Silicon), built by GitHub Actions as well.
