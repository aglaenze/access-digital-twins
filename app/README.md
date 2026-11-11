# The app "ESS digital twins" (Electron)

A real application window (not a browser): the student signs in, chooses an exercise in the catalogue, works on it in a
tab of the app, comes back to the catalogue, and submits each exercise at its end. Created 2026-11-06, version 0.1.

| File | Role |
|---|---|
| `main.js` | the window; accounts; the exercises in tabs; *Export all my work* (menu of the account); a self-test (below) |
| `../submit.py` | *Submit your work*, at the end of every page and notebook of the exercises |
| `ci_selftest.sh` | the self-test in `container` mode, on GitHub Actions, with the image just built |
| `backend.js` | the server behind the app: Jupyter with the API of the app, started with the app (while the student signs in) |
| `accounts.js` | accounts on this computer (`accounts.json` in the data folder of the app): name, email, salted scrypt hash of the password |
| `preload.js` | what the shell may ask the main process |
| `shell/` | the interface (sign in, catalogue, tabs): `index.html`, `style.css`, `app.js` |
| `../container/twin_app.py` | the API on the server side (`/twin/catalogue`, `/twin/user`, `/twin/open`, `/twin/nicos`, `/twin/handin`) |
| `../container/app_data/voila/templates/twin/static/twin.css` | the look of the app on the Voilà pages |

**What the student gets.** An account (name, email, password, at least 8 characters) that stays on this computer. The
catalogue shows each exercise with its mission and, for each level, where the student is (*Questions: 4 of 9*,
*Started*, *Not started*). An exercise opens in a tab; going back to the catalogue keeps it open (no reloading). The
answers to the questions are saved as they are given and shown again when the page is reopened; the notebooks are the
student's own copies (`work/<account>/`), saved by *Save*, every 2 minutes and when the app closes. At the end of each
exercise, *Submit my work* makes the file for the teacher (summary with name and score, answers, logbook of the
measurements, notebooks), keeps it in `TWIN_RUN_ROOT/submissions/<account>/` and offers it for download; the catalogue
then shows *Submitted*. *Export all my work* (menu of the account)
saves a zip file (the logbooks of the questions, the notebooks, the logbook of the measurements) to send to the
teacher; `../progress_summary.py` turns the files of a class into one table.

**Start again.** Each level already started has a link *Start again* (catalogue): after a confirmation, the tab of
the exercise is closed without saving, and the student's copy of the notebook, the answers to its questions and its
state (started, submitted) are put aside in `TWIN_RUN_ROOT/progress/<account>/_old/` (nothing is deleted; the
measurements stay); the next opening makes a clean copy (`/twin/reset`, `../container/twin_kernels.py` not involved).

**Kernels kept ready** (`../container/twin_kernels.py`, faster pages): **off** by default (`TWIN_KERNEL_POOL=1` to try):
a notebook given a kept kernel froze once in two tries on 2026-11-06; fresh kernels never did. Two faults found
and fixed since (a kept kernel lost its folder and the student's environment when restarted; a start without
environment failed when the pool was empty), the freeze itself not reproduced.

**Password forgotten.** The accounts are on this computer: no email can reset a password. At the creation of an
account the app shows a **recovery code** (once; only its hash is kept); *Forgot your password?* on the sign-in screen
sets a new password with the email and this code. A student who did not sign out is signed in again at the next start.

**The sample builder** (`../gen_sample_builder.py`) opens from the beamtime notebooks for their instrument and proposal
(nothing to choose): ODIN, as many blocks, spheres and vertical cylinders as wanted (`sample_library`: shapes, overlap
check; the twin: McStas `Union_sphere`/`Union_cylinder`, path lengths of the hybrid mode); LoKI, as many kinds of
particles as wanted (their scattering adds up: dilute).

**Where things are.** Logbooks: `TWIN_RUN_ROOT/progress/<account>/`; measurements of the pages:
`TWIN_RUN_ROOT/<instrument>/<account>/`; notebooks: `work/<account>/`. NICOS data stay in the proposal folders
(`data/<instrument>/<year>/<proposal>`), shared by the accounts of one computer.

**The server.** `local` mode: the conda environment `mcstas` of this computer and the twin folder next to the app
(teachers, developers); chosen when the app runs from the repository and that Python is found. `container` mode: the
image `ghcr.io/aglaenze/access-digital-twins` in Podman or Docker (students; the image is pulled the first time). Force
one with `TWIN_BACKEND=local|container`; `TWIN_PYTHON`, `TWIN_IMAGE` also work, or `settings.json` in the data folder.

## Running it

    cd twin/app
    npm install           # once: Electron (in node_modules/, not in git)
    npx electron .

On the computer of the author, Electron is installed outside OneDrive (`%LOCALAPPDATA%\ESS-twins-electron`) and the
desktop icon **ESS digital twins (local)** starts `electron.exe twin/app`.

**Self-test** (no window on the screen: it is placed out of the screen): creates an account, opens the catalogue, the
ODIN BSc page (answers a question), the MSc notebook, and saves screenshots:

    TWIN_RUN_ROOT=<empty folder> TWIN_APP_DATA=<empty folder> TWIN_APP_SELFTEST=<folder for the screenshots> electron .

## The notebooks of the exercises

- **MSc**: the student measures first, in NICOS, as at ESS: part 0 of the notebook gives the button *Open NICOS*
  (`../nb_tools.py`) and the steps of the measurement. Part 1 reads the files of the proposal
  (`PROPOSAL`); without files the notebook stops there with a message (`nb_tools.need_measurements`), no hidden
  simulation.
- **Beamtime and free beamtime**: the proposal (folded), *Open NICOS* and *Sample builder* are at the top of the starter
  notebook; the catalogue only opens the notebook. The card of the free beamtime makes proposals in the twin's user
  office (`../user_office.py`, `POST /twin/proposal`): *New free beamtime* (a new number each time, the question as
  title), *Import a proposal* (a real one: number, title, samples); the student's proposals are listed, each with its
  own copy of the starter notebook (`work/<user>/<instr>_free_beamtime_<proposal>/`). In NICOS: Experiment, Find my proposal.
- A notebook opens **already run**: the app runs all its cells once the kernel is ready (Notebook 7 exposes its
  commands: `exposeAppInBrowser` in `../container/app_config/labconfig/page_config.json`), then shows where it stopped.
- The code of the questions and of the solutions (the answers are in it) is hidden; only their widgets show.
- The students' copies (`work/<account>/...`) find the twin through `TWIN_ROOT` (set by the server of the app): no path
  of one computer in them.

## For the teacher: collecting the work

*Submit my work* (end of each exercise) makes a zip file on the student's computer (with `submission.json`: name,
email, exercise, level, date, score); the student sends it to the teacher (email, course page): there is no central
server (accounts are local). Put the files received in one folder, then

    python progress_summary.py <folder> [--csv class.csv]

gives one table: who, which exercise and level, when, questions right (at the first try), answers shown, solutions
opened (the newest file of a student counts). A central collection (a server, or the course page) would need a server.

## Installers

GitHub Actions (`.github/workflows/app.yml`) builds them at every change of `app/` and publishes them on the release
**app-latest**: https://github.com/aglaenze/access-digital-twins/releases/tag/app-latest (Windows `.exe`, installs for
the user without administrator rights; macOS `.dmg`, Apple Silicon and Intel; Linux `.AppImage`). The students also
need Podman Desktop (the app starts the instruments in it). `container.yml` tests the app in `container` mode with the
image it has just built (`ci_selftest.sh`).

## Code signing (not done yet)

Without a signature, Windows shows "Windows protected your PC" (*More info* > *Run anyway*) and macOS refuses to open
the app the first time (*System Settings* > *Privacy & Security* > *Open Anyway*). What is needed:

- **Windows**: a code-signing certificate in the name of the organization (DTU), either from a certificate authority
  (OV certificate, a few hundred euros per year, the key on a hardware token or in a cloud HSM), or Microsoft's
  *Artifact Signing* (formerly Trusted Signing, about 10 USD per month, identity of the organization checked by
  Microsoft). Ask DTU IT first: universities often have one. The warning fades as the signed app gains reputation.
- **macOS**: the Apple Developer Program (99 USD per year; as DTU it needs DTU's D-U-N-S number, or DTU's existing
  account), a *Developer ID Application* certificate, and notarization by Apple (electron-builder does it).
- **Linux**: nothing.

The certificates then go into the secrets of the GitHub repository (`CSC_LINK`, `CSC_KEY_PASSWORD`; `APPLE_ID`,
`APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`), and `app.yml` signs at every build.

## Still to do

- Code signing (above).
- NICOS data stay in the proposal folders, shared by the accounts of one computer.
