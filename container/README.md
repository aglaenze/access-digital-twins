# Container image of the digital twins

One Linux image with everything a student session needs: McStas 3.9.2 and NCrystal, the official McStas model of
ODIN (ESS/DMSC, fixed commit), the twins of this repository, the ESS reduction software (essimaging, scipp),
JupyterLab and Voilà, and NICOS (cache, poller, daemon; no GUI). Students only need a browser (or a NICOS client).

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
then open the address printed by JupyterLab. Other entry points: `... access-digital-twins voila` (student page,
port 8866), `... nicos` (NICOS services of ODIN, port 1301; another instrument: `-e TWIN_INSTRUMENT=...`), `... test`.
Results and NICOS data (`/data/twin/data/<instrument>/<year>/<proposal>/raw/`) are in the volume (`/data/twin`).
Live data as at ESS (Kafka broker + just-bin-it, ODIN): `-e TWIN_LIVE=1` with the entry point `nicos`
(`../nicos/README.md`, "Live data").
The image contains the ODIN and LoKI twins (official models at fixed commits, `~/odin_model` and `~/loki_model`). A
LoKI measurement needs about 6 GB of memory (downstream McStas part and its 440 MB of scattered neutrons, computed on
the first measurement of each sample, ~2 min): give Docker enough memory.

The image is built by GitHub Actions on every push to `main` (about 30–60 min the first time, faster afterward
thanks to the build cache); the run, its logs and the smoke test are in the "Actions" tab of the repository.

## Still to do

- NICOS clients from outside the container: the daemon listens on `localhost` only; a NICOS GUI in the browser
  (noVNC) or on the student computer.
- JupyterHub (one container per student, accounts) for a course; where to run it (DTU server, UCloud, VISA).
