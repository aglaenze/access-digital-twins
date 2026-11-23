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

**The sample builder.** ODIN: a page of the app (`../builder/index.html`, `builder.js`, `builder.css`; three.js
0.160.0 vendored in `../builder/vendor/`, MIT), served by `../container/twin_app.py` at `/twin/builder` (its JSON
API at `/twin/builder/api/<what>`, the functions of `../builder_api.py`). Opened from the beamtime notebooks (*Sample
builder*, *Change the sample*: `nb_tools.builder_url`) with the instrument, the proposal and the sample to start from
(`?instrument=odin&proposal=1234&start=<sample>&name=..&title=..`). Three steps: **1. Sample** (a gallery to start
from, with pictures: examples `odin/templates/`, models saved by users `TWIN_RUN_ROOT/templates/odin/`, the samples of
the library and of the proposal, the student's own first, then from the simplest to the most complex in three levels:
simple shapes, several parts or grains, natural samples, `builder_api.level`; the pictures of the examples and of the
library are made in advance and shipped in `../builder/thumbs/`: **after changing an example or a sample of the
library, run `python builder_api.py --thumbs`**, otherwise its picture is made on first use, 5 to 15 s for a rock; help: *? How to use* (a worked example with pictures of the real page, `../builder/help.js`, pictures in `../builder/help/`, made by `../builder/help/tools/shots.py`) and *Tour* (started by itself at the first visit); the parts as a tree; shapes chosen by icons, sizes, position and rotation by
sliders in mm; materials as cards with their Σ at 3 Å and a search; grains placed at random, components, combined
shapes and the whole recipe as text under *Advanced*); **2. Holder**, apart from the sample (none, pin, base plate,
quartz cell, vanadium can, tensile grips: placed from the bounds of the sample, only size and material change; kept
in the sample file as `holder: {type, ...}` and joined to the scene as bodies `holder: true`); **3. Check & save**
(traffic lights: in the 14 mm field of view, transmission at 3 Å, no overlap, holder in or out of the beam; Σ of
the materials; save with the proposal, `sample_library.save`, NICOS: `move(sample_holder, '<name>')`; or as a model;
or download the recipe). On the right, always: the 3D view (drag to turn; the main material see-through; the part
selected in the list outlined; the field of view and the beam drawn) and the beam's eye view (radiograph at the
wavelength chosen, `odin_hybrid.scene_transmission`). The parts an exercise hides (secret fills and bodies of a
library sample) are sealed: the page gets a placeholder, the part stays on the server
(`TWIN_RUN_ROOT/builder/sealed/`) and comes back when the sample is saved; the views leave them out. A large sample
(the meteorite: about a minute to place its grains) is shown without its grains while it is edited.
LoKI: its own page at the same address (`?instrument=loki`: `../builder/loki.html`, `loki.js`, the same `builder.css`;
its API `../builder_loki.py`, the same `/twin/builder/api/<what>` with `"instrument": "loki"`). The same three steps:
**1. Sample** (the gallery: the library samples, models `TWIN_RUN_ROOT/templates/loki/`, the proposal's samples, from
scratch; the liquid: H2O/D2O mixture or air, its D2O fraction and thickness, a line of scattering length densities;
any number of kinds of particles: sphere, rod (cylinder), core-shell sphere, their materials as cards with ρ and the
contrast Δρ against the liquid, sizes in Å by log sliders, volume fraction); **2. Holder** (the quartz cell of
`sample_library`, windows 2 × 1.25 mm fixed, only the gap = the liquid thickness changes, drawn to scale; or no cell
for the empty beam); **3. Check & save** (traffic lights from the twin's physics: transmission at 3 and 10 Å from
`sample_library.loki_sample`, signal over the incoherent background, contrast and match point of each kind, dilute
regime (Percus-Yevick S(0) of hard spheres), the sizes against LoKI's Q range 0.003–0.6 Å⁻¹ (Guinier plateau, first
minimum); save with the proposal, `sample_library.save("loki", ...)`, or as a model, or download the YAML). On the
right: dΣ/dΩ(Q) on log-log axes (`sample_library.loki_cross_section`, exact, no instrument; each kind and the
background apart, LoKI's Q range shaded), the particles to scale with one another, the cell seen from the side.
Polydispersity: not in the sample format, so not offered. The properties an exercise hides (`exercise.yml`,
e.g. the radius and volume fraction of `silica_spheres`) are sealed value by value (keyed hash ids, the values in
`TWIN_RUN_ROOT/builder/sealed/`): a kind with a sealed value is neither drawn nor checked nor put in a model or a
download; saved with the proposal, the values come back and stay hidden (`hidden:` in the file).

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

## The window

No title bar of the system: the dark header of the app is the title bar (drag it to move the window, double-click to
maximize), and the buttons to minimize, maximize and close are drawn over its right end (`titleBarOverlay`, Windows and
Linux; light on the sign-in screen, dark in the app; macOS: its three buttons on the left of the header).

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

## The catalogue: roles, the story, the teacher view

A student first chooses an instrument, sees its introduction, then chooses a **role in the team** (the level):
*Trainee* (BSc), *Method scientist* (MSc, with or without code) or *Lead scientist* (on their own: beamtime with NICOS,
free beamtime). The choice is kept for the account. The requests of that level are then shown as a **map**, as in the
level screen of a game: a bar with the grade and the record (requests answered, questions right at the first try), one
lane per thread of the story of `../STORY.md` (`story:` in each `exercise.yml`; the threads are `THREADS` in
`container/twin_app.py`) with its chapters as nodes on a path (a ring that fills with the progress, a check once
submitted, the next request marked), and the **briefing** of the chosen chapter (client, mission of this level, format,
progress, buttons). A node's name is `short:` in `exercise.yml`; the chapters are numbered along their thread (1, 2, 3...), the numbers
of the exercises (`number:`, the themes of ODIN) appear only in the teacher view. The content of the catalogue follows the width of the
window.

**Teacher view** (every exercise at every level on one page): menu of the account, *Teacher view…*, then the teacher
code. Only a salted hash of the code is shipped (`teacher_code.json`); change it with `node set_teacher_code.js <code>`
(or set `TWIN_TEACHER_CODE`). As for the accounts, a convenience, not a protection.

## For the teacher: classes (prepare, open, follow live)

In the teacher view, a tab **Classes** (`shell/app.js`, `Classes`; server side `../classes.py` through
`/twin/classes` of `../container/twin_app.py`). **New class**: a title, anonymous or named students (a named class
asks each student a name on the start page, e.g. a graded session), the power of the source (free, or fixed for the
whole class: the pages show it locked, "set by your teacher"), and the pages the students may open, among those a
browser can show alone (introductions, guided Trainee pages, class pages; `classes.offer()`). **Open the class**
starts `../web_class.py --class <code>` on this computer (Voila, and a Cloudflare quick tunnel unless unticked): the
link for the students (it holds the code: no password to type) and its QR code (`shell/vendor/qrcode.js`,
qrcode-generator 1.4.4, MIT, Kazuhiko Arase) appear after a few seconds (the beams are prepared meanwhile, web_warmup.py); one class open at a time, closed with
**Close the class** (the whole tree of processes). **Live** (every 5 s, `classes.live`): each student (name, or an
anonymous id), the page, the questions right, right at the first try, the questions tried and still wrong ("stuck"),
the measurements, the last activity, submitted or not; above, the students, the active ones, the submissions, the
question most students are stuck on. No server yet: the class runs on the teacher's computer (keep it on and awake);
the access is a convenience (the code is in the link), not a protection. The local app only (not the container mode).

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
