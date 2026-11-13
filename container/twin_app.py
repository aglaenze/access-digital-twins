"""Jupyter server extension of the app "ESS digital twins" (twin/app, Electron): what the app asks the server.

Loaded by the server of the app (container/start.sh in the container, twin/app/main.js on a computer without the
container):  jupyter server --ServerApp.jpserver_extensions="{'twin_app': True}"  with container/ in PYTHONPATH.
All requests need the token of the server (header "Authorization: token ...").

    GET  /twin/catalogue           instruments, exercises (exercise.yml), free beamtimes, the progress of the student
    POST /twin/user {id,name,email} the student who signs in: the kernels started from now on work for them
                                   (TWIN_USER, sessions of the pages, logbooks of the questions); open kernels stop
    POST /twin/open {dir,mode,what} the address to show for one way into an exercise (a page, or the student's own
                                   copy of a notebook, made on first opening) and records that it was opened
                                   ({file, proposal}: the starter notebook of a free beamtime, one copy per proposal)
    POST /twin/proposal {instrument, kind, title, proposal, samples}
                                   the user office of the twin (user_office.py): a new free beamtime (kind "free", a
                                   new number each time) or an imported proposal (kind "imported": its number, title,
                                   samples [{name, formula}]); NICOS finds it in Find my proposal within a minute
    POST /twin/reset {dir,mode}    starts one way into an exercise again: the student's copy of its notebook, the
                                   answers to its questions and its state (started, submitted) are put aside (folder
                                   _old/ of the student, nothing is deleted); the measurements stay
    POST /twin/nicos {instrument}  opens NICOS of this instrument: windows of this computer (local app), or the control
                                   room of the container (returns the address of the remote screen)
    GET  /twin/handin              the work of the student as a zip file (logbooks, notebooks, measurements logbook)

The student's things: notebooks in work/<user>/, logbooks in TWIN_RUN_ROOT/progress/<user>/, measurements of the
pages in the sessions TWIN_RUN_ROOT/<instrument>/<user>/. Accounts and passwords stay in the app (twin/app/accounts.js).
"""
import asyncio
import datetime
import glob
import io
import json
import os
import re
import socket
import subprocess
import sys
import zipfile

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
from tornado import web

INSTRUMENTS = {
    "odin": dict(name="ODIN", kind="Imaging", text="Radiography and tomography with neutrons, wavelength by wavelength"),
    "loki": dict(name="LoKI", kind="Small-angle scattering", text="Sizes and shapes of nanostructures, 1 to 100 nm"),
    "dream": dict(name="DREAM", kind="Powder diffraction", text="Not available yet: no official McStas model"),
    "bifrost": dict(name="BIFROST", kind="Spectroscopy", text="Not available yet: no official McStas model"),
}
QUIZ = {  # the quiz (quiz.Quiz name) of each way into an exercise, for the progress shown in the catalogue
    ("odin/exercises/introduction", "all"): "odin_intro",
    ("loki/exercises/introduction", "all"): "loki_intro",
    ("odin/exercises/iron_bragg_edges", "bsc"): "odin_iron_bsc",
    ("odin/exercises/iron_bragg_edges", "msc"): "odin_iron_msc",
    ("odin/exercises/steel_strain", "bsc"): "odin_steel_bsc",
    ("odin/exercises/steel_strain", "msc"): "odin_steel_msc",
    ("odin/exercises/meteorite_imaging", "bsc"): "odin_meteorite_bsc",
    ("odin/exercises/meteorite_imaging", "msc"): "odin_meteorite_msc",
    # an exercise with a choice of samples (variants on its card): one quiz per sample, the furthest one is shown
    ("odin/exercises/magnet_imaging", "bsc"): ("odin_magnet_bsc_solenoid", "odin_magnet_bsc_meteorite"),
    ("odin/exercises/magnet_imaging", "msc"): ("odin_magnet_msc_solenoid", "odin_magnet_msc_meteorite"),
    ("loki/exercises/silica_spheres", "bsc"): "loki_silica_bsc",
    ("loki/exercises/silica_spheres", "msc"): "loki_silica_msc",
}
SESSION_VARS = ("ODIN_SESSION", "LOKI_SESSION")


def run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def user():
    return os.environ.get("TWIN_USER", "")


def safe_id(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:60]


class Base(APIHandler):
    @property
    def root(self):
        return os.path.abspath(os.path.expanduser(self.settings["server_root_dir"]))   # (it may start with "~")

    def body(self):
        try:
            return json.loads(self.request.body or b"{}")
        except ValueError:
            raise web.HTTPError(400, "JSON expected")

    def progress(self):
        return os.path.join(run_root(), "progress", user()) if user() else None

    def opened(self):
        p = self.progress()
        try:
            with open(os.path.join(p, "opened.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError, TypeError):
            return {}


class Catalogue(Base):
    @web.authenticated
    def get(self):
        import yaml
        ex = []
        for f in sorted(glob.glob(os.path.join(self.root, "*", "exercises", "*", "exercise.yml"))):
            with open(f, encoding="utf-8") as fh:
                e = yaml.safe_load(fh)
            e["dir"] = os.path.relpath(os.path.dirname(f), self.root).replace(os.sep, "/")
            for key, m in (e.get("modes") or {}).items():
                if m.get("file", "").endswith(".md"):            # the proposal sheet of a beamtime, as HTML
                    try:
                        import mistune
                        with open(os.path.join(self.root, m["file"]), encoding="utf-8") as fh:
                            m["sheet"] = mistune.html(fh.read())
                    except Exception:
                        m["sheet"] = ""
                m["progress"] = self.mode_progress(e["dir"], key)
            ex.append(e)
        planned = os.path.join(self.root, "catalogue_planned.yml")
        if os.path.isfile(planned):
            with open(planned, encoding="utf-8") as fh:
                ex += [dict(e, status="planned") for e in yaml.safe_load(fh) or []]
        free = {k: f"{k}/exercises/free_beamtime/{v['name']}_free_beamtime.ipynb" for k, v in INSTRUMENTS.items()}
        free = {k: f for k, f in free.items() if os.path.isfile(os.path.join(self.root, f))}
        mine = {}                                  # the student's free beamtimes and imported proposals
        if user():
            import user_office
            for p in user_office.proposals(owner=user()):
                if p["kind"] != "exercise":
                    mine.setdefault(p["instrument"], []).append(p)
        self.finish(json.dumps(dict(instruments=INSTRUMENTS, exercises=ex, free=free, proposals=mine, user=user(),
                                    local=bool(os.environ.get("TWIN_APP_LOCAL")))))

    def mode_progress(self, d, mode):
        """{"status": "new" | "started" | "done", "text": ..., "pct": 0-100}"""
        out = dict(status="new", text="Not started", pct=0)
        when = self.opened().get(f"{d}:{mode}")
        if when:
            out.update(status="started", text=f"Started {when[:10]}", pct=5)
        qs, p = QUIZ.get((d, mode)), self.progress()
        qs = (qs,) if isinstance(qs, str) else (qs or ())
        sub = {}
        try:
            with open(os.path.join(p, "submitted.json"), encoding="utf-8") as f:
                sub = json.load(f)
        except (OSError, ValueError, TypeError):
            pass
        for q in qs:
            if not (p and os.path.isfile(os.path.join(p, q + ".meta.json"))):
                continue
            try:
                with open(os.path.join(p, q + ".meta.json"), encoding="utf-8") as f:
                    total = json.load(f).get("questions", 0)
                import quiz
                done = sum(1 for s in quiz._previous(os.path.join(p, q + ".jsonl")).values()
                           if s["right"] or s["revealed"])
                if total and round(100 * done / total) >= out["pct"]:
                    pct = round(100 * done / total)
                    out.update(status="done" if done >= total else "started", pct=pct,
                               text=f"Questions: {done} of {total}")
            except (OSError, ValueError, ImportError):
                pass
        if sub.get(f"{d}:{mode}"):
            out.update(status="done", pct=100, text=f"Submitted {sub[f'{d}:{mode}'][:10]}")
        return out


class User(Base):
    @web.authenticated
    async def post(self):
        b = self.body()
        uid = safe_id(b.get("id"))
        if not uid:
            raise web.HTTPError(400, "id needed")
        changed = uid != user()
        os.environ.update(TWIN_USER=uid, TWIN_USER_NAME=b.get("name", ""), TWIN_USER_EMAIL=b.get("email", ""))
        for v in SESSION_VARS:                       # the pages measure in the session of the student
            os.environ[v] = uid
        os.makedirs(os.path.join(run_root(), "progress", uid), exist_ok=True)
        import user_office
        user_office.set_signed_in(uid)               # NICOS lists the proposals of this student (start_nicos.py)
        with open(os.path.join(run_root(), "progress", uid, "account.json"), "w", encoding="utf-8") as f:
            json.dump(dict(id=uid, name=b.get("name", ""), email=b.get("email", "")), f)
        if changed:                                  # kernels of the previous student (not the kept ones of
            km = self.kernel_manager                 # twin_kernels.py: they get the student's environment when given)
            kept = set(km.kept()) if hasattr(km, "kept") else set()
            for kid in list(km.list_kernel_ids()):
                if kid not in kept:
                    await km.shutdown_kernel(kid)
            if hasattr(km, "fill"):
                asyncio.ensure_future(km.fill())
        self.finish(json.dumps(dict(user=uid)))


class Reset(Base):
    @web.authenticated
    def post(self):
        import shutil
        import yaml
        b = self.body()
        d, mode = b.get("dir", ""), b.get("mode", "")
        who = user()
        if not who or not d or ".." in d.split("/"):
            raise web.HTTPError(400, "sign in, and give dir and mode")
        with open(os.path.join(self.root, d, "exercise.yml"), encoding="utf-8") as fh:
            m = yaml.safe_load(fh)["modes"][mode]
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        old = os.path.join(run_root(), "progress", who, "_old", f"{os.path.basename(d)}_{mode}_{stamp}")
        moved = []

        def put_aside(path):
            if os.path.exists(path):
                os.makedirs(old, exist_ok=True)
                shutil.move(path, os.path.join(old, os.path.basename(path)))
                moved.append(os.path.basename(path))

        # the student's copy of the notebook of this way in (made again, clean, at the next opening)
        instr, ex = d.split("/")[0], os.path.basename(d)
        rel = m.get("analysis") if mode == "beamtime" else m.get("file")
        if rel and rel.endswith(".ipynb") and m.get("open") != "voila":
            put_aside(os.path.join(self.root, "work", who, f"{instr}_{ex}", os.path.basename(rel)))
        # the answers to its questions
        qs = QUIZ.get((d, mode))
        for q in ((qs,) if isinstance(qs, str) else (qs or ())):
            for ext in (".jsonl", ".meta.json"):
                put_aside(os.path.join(run_root(), "progress", who, q + ext))
        # its state in the catalogue (started, submitted)
        for name in ("opened.json", "submitted.json"):
            f = os.path.join(run_root(), "progress", who, name)
            try:
                with open(f, encoding="utf-8") as fh:
                    state = json.load(fh)
            except (OSError, ValueError):
                continue
            if state.pop(f"{d}:{mode}", None) is not None:
                with open(f, "w", encoding="utf-8") as fh:
                    json.dump(state, fh)
        self.finish(json.dumps(dict(reset=True, put_aside=moved, folder=old if moved else None)))


class Open(Base):
    @web.authenticated
    def post(self):
        b = self.body()
        d, mode, what = b.get("dir", ""), b.get("mode", ""), b.get("what", "file")
        rel = b.get("file")
        if not rel:
            import yaml
            with open(os.path.join(self.root, d, "exercise.yml"), encoding="utf-8") as fh:
                m = yaml.safe_load(fh)["modes"][mode]
            rel = m["analysis"] if what == "analysis" else m["file"]
            if what == "file" and m.get("variants") and b.get("variant") not in (None, ""):
                rel = m["variants"][int(b["variant"])]["file"]          # the sample chosen on the card
            kind = "page" if (m.get("open") == "voila" and what == "file") else "notebook"
        else:
            kind = b.get("kind", "notebook")
        if not os.path.isfile(os.path.join(self.root, rel)) or ".." in rel.split("/"):
            raise web.HTTPError(404, rel)
        proposal = str(b.get("proposal") or "")
        if proposal and not proposal.isdigit():
            raise web.HTTPError(400, "proposal: digits")
        if kind == "page":
            url = "/voila/render/" + rel
        else:
            url = "/notebooks/" + self.personal_copy(rel, proposal)
        if d and mode and self.progress():
            o = self.opened()
            o.setdefault(f"{d}:{mode}", datetime.datetime.now().isoformat(timespec="minutes"))
            os.makedirs(self.progress(), exist_ok=True)
            with open(os.path.join(self.progress(), "opened.json"), "w", encoding="utf-8") as f:
                json.dump(o, f)
        self.finish(json.dumps(dict(url=url, kind=kind)))

    def personal_copy(self, rel, proposal=""):
        """The student's own copy of a notebook (made once, then kept), its relative paths made absolute. With a
        proposal (free beamtime, imported proposal): one copy per proposal, its number in place of "1000"."""
        import nbformat
        src = os.path.join(self.root, rel)
        ex_dir = os.path.dirname(src)
        instr_dir = os.path.dirname(os.path.dirname(ex_dir))
        who = user() or "guest"
        folder = f"{os.path.basename(instr_dir)}_{os.path.basename(ex_dir)}" + (f"_{proposal}" if proposal else "")
        dst_rel = f"work/{who}/{folder}/{os.path.basename(rel)}"
        dst = os.path.join(self.root, dst_rel)
        if not os.path.isfile(dst):
            nb = nbformat.read(src, as_version=4)
            # the copy is elsewhere (work/<user>/...): its paths go through TWIN_ROOT (set by this server for the
            # kernels), never through the folders of one computer
            root = 'os.environ.get("TWIN_ROOT", os.path.abspath("../../.."))'
            instr = os.path.basename(instr_dir)
            yml = os.path.relpath(os.path.join(ex_dir, "exercise.yml"), self.root).replace(os.sep, "/")
            for c in nb.cells:
                c.source = (c.source.replace('os.path.abspath("../../..")', root)
                            .replace('os.path.abspath("../..")', f'os.path.join({root}, "{instr}")')
                            .replace('"exercise.yml"', f'os.path.join({root}, "{yml}")'))
                if proposal and c.cell_type == "code":
                    c.source = c.source.replace('"1000"', f'"{proposal}"')
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            nbformat.write(nb, dst)
        return dst_rel


class Proposal(Base):
    @web.authenticated
    def get(self):
        """The number a new free beamtime gets by default (shown, and editable, in the dialog of the app)."""
        import user_office
        self.finish(json.dumps(dict(next=user_office.next_free())))

    @web.authenticated
    def post(self):
        import user_office
        who = user()
        if not who:
            raise web.HTTPError(400, "sign in first")
        b = self.body()
        name = ""
        try:
            with open(os.path.join(run_root(), "progress", who, "account.json"), encoding="utf-8") as f:
                name = json.load(f).get("name", "")
        except (OSError, ValueError):
            pass
        try:
            p = user_office.create(b.get("instrument", ""), b.get("title", ""), who, kind=b.get("kind", "free"),
                                   proposal_id=b.get("proposal"), samples=b.get("samples") or [], owner_name=name)
        except ValueError as e:
            self.set_status(400)
            self.finish(json.dumps(dict(error=str(e))))
            return
        try:                                       # NICOS (if open) reads its proposal cache again within a minute
            user_office.write_cache(p["instrument"], os.path.join(run_root(), "nicos",
                                                                  f"cached_proposals_{p['instrument']}.json"), who)
        except Exception:                          # noqa: BLE001 (written again when NICOS starts)
            pass
        self.finish(json.dumps(p))


class Nicos(Base):
    @web.authenticated
    def get(self):
        """The step of the launch of NICOS on this computer (written by nicos/start_nicos.py), shown by the app."""
        try:
            with open(os.path.join(run_root(), "nicos", "launch_status.json"), encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            st = {"step": "", "state": "unknown", "time": 0}
        self.finish(json.dumps(st))

    @web.authenticated
    def post(self):
        instr = self.body().get("instrument", "")
        if instr not in ("odin", "loki"):
            raise web.HTTPError(400, "instrument: odin or loki")
        if os.environ.get("TWIN_APP_LOCAL"):          # windows of this computer
            try:                                       # already open (its daemon answers): nothing to start
                socket.create_connection(("localhost", 1301), timeout=1).close()
                self.finish(json.dumps(dict(where="desktop", already=True)))
                return
            except OSError:
                pass
            flags = 0
            if os.name == "nt":
                flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB
            cmd = [sys.executable, os.path.join(self.root, "container", "control_room_local.py"), "--instrument", instr]
            try:
                subprocess.Popen(cmd, cwd=self.root, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                subprocess.Popen(cmd, cwd=self.root, creationflags=flags & ~0x01000000, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            self.finish(json.dumps(dict(where="desktop")))
        else:                                          # the control room of the container (remote screen)
            with open(os.path.expanduser("~/.control_room_request"), "w") as f:
                f.write(instr)
            self.finish(json.dumps(dict(where="remote", url="/desktop/")))


class Handin(Base):
    @web.authenticated
    def get(self):
        who = user()
        if not who:
            raise web.HTTPError(400, "nobody signed in")
        buf = io.BytesIO()
        rr = run_root()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in glob.glob(os.path.join(rr, "progress", who, "*")):
                z.write(f, f"{who}/progress/{os.path.basename(f)}")
            for f in glob.glob(os.path.join(self.root, "work", who, "**", "*.ipynb"), recursive=True):
                if ".ipynb_checkpoints" not in f:
                    z.write(f, f"{who}/notebooks/" + os.path.relpath(f, os.path.join(self.root, "work", who)).replace(os.sep, "/"))
            for instr in ("odin", "loki"):
                f = os.path.join(rr, instr, who, "log.jsonl")
                if os.path.isfile(f):
                    z.write(f, f"{who}/measurements_{instr}.jsonl")
        name = f"{who}_{datetime.date.today().isoformat()}.zip"
        self.set_header("Content-Type", "application/zip")
        self.set_header("Content-Disposition", f'attachment; filename="{name}"')
        self.finish(buf.getvalue())


def _jupyter_server_extension_points():
    return [{"module": "twin_app"}]


def _load_jupyter_server_extension(serverapp):
    base = serverapp.web_app.settings["base_url"]
    serverapp.web_app.add_handlers(".*$", [(url_path_join(base, "twin", p), h) for p, h in [
        ("catalogue", Catalogue), ("user", User), ("open", Open), ("reset", Reset), ("proposal", Proposal),
        ("nicos", Nicos), ("handin", Handin)]])
    # the twin root on the path of the server (quiz.py: the progress shown in the catalogue)
    root = os.path.abspath(os.path.expanduser(serverapp.root_dir))
    os.environ["TWIN_ROOT"] = root            # the kernels find the twin from the students' copies (work/<user>/...)
    if root not in sys.path:
        sys.path.insert(0, root)
    km = serverapp.kernel_manager
    if hasattr(km, "fill"):                    # kernels kept ready (twin_kernels.py): start filling now
        serverapp.io_loop.call_later(1.0, lambda: asyncio.ensure_future(km.fill()))
    serverapp.log.info("twin_app: /twin/ API of the app loaded")
