# Keeping the twins up to date with the ESS software

Every program of the image has a **fixed version** (a version number or a git commit), so that the image built today
and the one built in a year give the same results, and an exercise never breaks by itself. The ESS software keeps
moving, though (scipp and its packages publish every month, NICOS every week), and the twins must follow it, or the
students learn on tools that ESS no longer uses. This file says how.

## What is fixed, where

`python container/versions.py` prints every fixed version, the latest one published, and where it is fixed:

| Kind | Software | Fixed in |
|---|---|---|
| Followed (tested every week) | scipp, scippneutron, scippnexus, tof, plopp | `environment-mcstas.yml` (conda-forge) |
| | essreduce, essimaging, esssans, sciline, sasmodels | `environment-mcstas.yml` (pip) |
| | esslivedata | `Containerfile`, `ARG LIVEDATA_VERSION` (a GitHub release: it is not on PyPI) |
| | NICOS, just-bin-it | `Containerfile`, `ARG NICOS_COMMIT` (and `NICOS_VERSION`), `ARG JBI_COMMIT` |
| Reported only (a decision) | McStas models of ODIN and LoKI | `Containerfile`, `ARG ODIN_COMMIT`, `ARG LOKI_COMMIT` |
| | McStas, NCrystal, MCPL | `environment-mcstas.yml` |
| | ESS file-writer (kafka-to-nexus) | the image built by `.github/workflows/filewriter.yml` (input `ref`), its digest in `Containerfile` (`FILEWRITER_IMAGE`) |
| | Kafka | `Containerfile`, `ARG KAFKA_VERSION` and `KAFKA_SHA512` |

Why "reported only": a new McStas model or a new McStas changes the physics, and the precomputed upstream parts of
the instruments (release `fronts-v1`, `fetch_fronts.py`) must be computed again with it; a new file-writer is a choice
to make with ECDC. They are listed so that we know, not raised by routine.

## Every week, automatically

`.github/workflows/latest.yml` (Mondays, and by hand: Actions → "latest versions" → Run workflow) builds the image with
the latest versions of the followed software and runs the full container test (`smoke_test.py`: McStas against
NCrystal, LoKI fits, NICOS, live data, the ESS file-writer, esslivedata). Nothing is published and nothing changes in
the repository. The summary of the run shows the table of versions and the result of the test.

## Raising the fixed versions

1. Look at the last "latest versions" run: it must have passed (otherwise: read the failing check; fix the twin, or
   wait for the ESS software to be fixed, and tell its team if it is their bug).
2. On a branch: `python container/versions.py --apply build-args` writes the latest versions into
   `environment-mcstas.yml`; copy the lines of `build-args` into the `ARG` lines of the `Containerfile` (and delete the
   file `build-args`).
3. Regenerate and run the notebooks that show reduced results (`odin/gen_analysis_notebook.py`,
   `loki/gen_analysis_notebook.py`, then the exercises: `gen_notebooks.py`), and look at what changed: a new version
   can change a number shown to the students (the text must still say what the figure shows).
4. Push: `container.yml` builds and tests the image; when it passes, the new image is published (`latest`) and the
   app gets it at its next start.
5. Write the change in the history of the project (versions before and after, what changed for the students).

Raise one family at a time when something breaks (e.g. scipp and its packages, then NICOS), to know which one did it.
