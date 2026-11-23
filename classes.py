"""The classes of a teacher: which pages the students may open, and how the class is followed.

A class is prepared by the teacher (the app, teacher view; or this module), then opened from the teacher's computer
(web_class.py --class <code>): the students get one link, which opens a start page with only the pages of the class.
No server yet: everything runs on the teacher's computer, reached by the students through a tunnel. The access is a
convenience, not a protection (the code of the class is in the link).

A class is one file, TWIN_RUN_ROOT/classes/<code>.json:

    code       8 characters, drawn at creation, in the link of the students
    title      shown on the start page of the students
    identity   "anonymous" (no name asked) or "named" (each student types a name before starting: a graded class)
    pages      the pages the students may open, each an id of offer(): "<instrument>/<exercise>/<level>"
    settings   what the teacher fixes for the whole class: power_mw (power of the source, MW; None = the student
               chooses where the page lets them)
    created, note

Only the pages that a browser can show alone are offered (Voila: the guided pages, the introductions, the class
pages); the notebooks (MSc) and the beamtimes (NICOS) need a server per student: later.

    python classes.py offer                                 the pages that can be given to a class
    python classes.py new "<title>" <page id> ... [--named] [--power 2]
    python classes.py list
    python classes.py live <code>                           where each student is, now
"""
import datetime
import glob
import json
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IDENTITIES = ("anonymous", "named")
LEVEL_NAMES = {"all": "Introduction", "bsc": "Trainee (guided page)", "class": "Class session"}


def run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def folder():
    return os.path.join(run_root(), "classes")


def _yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _quiz_name(page):
    """The name of the questions of a page (quiz.Quiz("<name>") in its notebook): the file of its answers."""
    try:
        with open(os.path.join(HERE, page), encoding="utf-8") as f:
            m = re.search(r'quiz\.Quiz\(\\?"([A-Za-z0-9_]+)\\?"', f.read())
        return m.group(1) if m else None
    except OSError:
        return None


def offer():
    """The pages that can be given to a class, in the order of the catalogue: [{id, instrument, exercise, level,
    level_name, title, short, page, what, mission, duration, quiz}]. From the exercise.yml files: the modes opened by
    Voila (open: voila), and the class pages (class_page: in exercise.yml)."""
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "*", "exercises", "*", "exercise.yml"))):
        d = _yaml(f)
        if d.get("status", "ready") != "ready":
            continue
        instr = d.get("instrument") or f.replace("\\", "/").split("/")[-4]
        ex = os.path.basename(os.path.dirname(f))
        modes = dict(d.get("modes") or {})
        if d.get("class_page"):
            modes["class"] = dict(d["class_page"], open="voila")
        for level, m in modes.items():
            if (m or {}).get("open") != "voila" or not os.path.isfile(os.path.join(HERE, m.get("file", ""))):
                continue
            out.append(dict(id=f"{instr}/{ex}/{level}", instrument=instr, exercise=ex, level=level,
                            level_name=LEVEL_NAMES.get(level, level), title=m.get("title") or d.get("title", ex),
                            short=d.get("short", ""), page=m["file"], what=m.get("what", ""),
                            mission=" ".join(str(m.get("mission") or d.get("question", "")).split()),
                            duration=m.get("duration", ""), introduction=d.get("kind") == "introduction",
                            quiz=_quiz_name(m["file"])))
    # the introductions first, then the class pages, then the exercises
    rank = lambda p: (p["instrument"], 0 if p["introduction"] else (1 if p["level"] == "class" else 2), p["exercise"])
    return sorted(out, key=rank)


def _path(code):
    if not re.fullmatch(r"[a-z0-9]{8}", code or ""):
        raise ValueError(f"not a class code: {code!r}")
    return os.path.join(folder(), f"{code}.json")


def new(title, pages, identity="anonymous", settings=None, note=""):
    """Makes a class and returns it (its file is written). pages: ids of offer()."""
    known = {p["id"] for p in offer()}
    bad = [p for p in pages if p not in known]
    if bad:
        raise ValueError(f"pages not offered: {bad} (python classes.py offer)")
    if not pages:
        raise ValueError("a class needs at least one page")
    if identity not in IDENTITIES:
        raise ValueError(f"identity: one of {IDENTITIES}")
    alphabet = "abcdefghijkmnpqrstuvwxyz23456789"          # no 0/o, 1/l: read aloud or copied by hand
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    c = dict(code=code, title=title.strip() or "Class", identity=identity, pages=list(pages),
             settings={"power_mw": None, **(settings or {})}, note=note,
             created=datetime.datetime.now().isoformat(timespec="seconds"))
    save(c)
    return c


def save(c):
    os.makedirs(folder(), exist_ok=True)
    with open(_path(c["code"]), "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1, ensure_ascii=False)


def load(code):
    with open(_path(code), encoding="utf-8") as f:
        return json.load(f)


def classes():
    """All the classes of this computer, newest first."""
    out = []
    for f in glob.glob(os.path.join(folder(), "*.json")):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            pass
    return sorted(out, key=lambda c: c.get("created", ""), reverse=True)


def student_view(c):
    """What the start page of the students needs (written next to it by web_class.py as class.json): no settings
    the students should not see, the pages in the order chosen by the teacher."""
    by_id = {p["id"]: p for p in offer()}
    cards = []
    for pid in c["pages"]:
        p = by_id.get(pid)
        if p:
            cards.append({k: p[k] for k in ("id", "instrument", "level", "level_name", "title", "short", "page",
                                            "what", "mission")})
    return dict(code=c["code"], title=c["title"], identity=c["identity"], cards=cards)


def current():
    """The class of this server (web_class.py --class sets TWIN_CLASS), or None."""
    code = os.environ.get("TWIN_CLASS", "")
    try:
        return load(code) if code else None
    except (OSError, ValueError):
        return None


def setting(name, default=None):
    """A setting fixed by the teacher for the class of this server (None if the class leaves it free, or no class)."""
    c = current()
    v = (c or {}).get("settings", {}).get(name)
    return default if v is None else v


# --------------------------------------------------------------------------- following the class
def _read_jsonl(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def _t(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace(" ", "T"))
    except ValueError:
        return None


def live(code, now=None):
    """Where each student of the class is: [{student, name, page, opened, questions, answered, right, first_try,
    revealed, wrong_tries, stuck, last_question, measurements, last_activity, idle_min, submitted}], one row per
    student and page of the class, the most recent activity first. Read from the files the pages write as the students
    work (progress/, web_results/, the measurement logbooks): no server needed."""
    c = load(code)
    now = now or datetime.datetime.now()
    pages = {p["page"]: p for p in offer() if p["id"] in c["pages"]}
    rr = run_root()
    rows = []
    for wj in glob.glob(os.path.join(rr, "progress", "anon_*", "web.json")):
        uid = os.path.basename(os.path.dirname(wj))
        try:
            with open(wj, encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, ValueError):
            continue
        if info.get("class") != code:
            continue
        meas = [e for e in _read_jsonl(os.path.join(rr, "odin", uid, "log.jsonl")) +
                _read_jsonl(os.path.join(rr, "loki", uid, "log.jsonl"))
                if e.get("action") in ("count", "camera", "tomography", "scan", "tof_histogram", "polarimetry")]
        submitted = {}
        for f in glob.glob(os.path.join(rr, "web_results", uid, "*_submitted.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    s = json.load(fh)
                submitted[s.get("exercise", "")] = os.path.basename(f)[:15]
            except (OSError, ValueError):
                pass
        for page, opened in info.get("opened", {}).items():
            p = pages.get(page)
            if not p:
                continue
            q = p["quiz"]
            recs = _read_jsonl(os.path.join(rr, "progress", uid, f"{q}.jsonl")) if q else []
            try:
                with open(os.path.join(rr, "progress", uid, f"{q}.meta.json"), encoding="utf-8") as f:
                    n_q = json.load(f).get("questions", 0)
            except (OSError, ValueError, TypeError):
                n_q = 0
            by_q = {}
            for r in recs:
                by_q.setdefault(r["question"], []).append(r)
            right = [k for k, v in by_q.items() if any(x["right"] for x in v)]
            first = [k for k, v in by_q.items() if v[0]["answer"] != "revealed" and v[0]["right"]]
            revealed = [k for k, v in by_q.items() if any(x["answer"] == "revealed" for x in v)]
            wrong = {k: sum(1 for x in v if not x["right"] and x["answer"] != "revealed") for k, v in by_q.items()}
            # stuck: a question tried and still not right
            stuck = sorted((k for k in by_q if k not in right), key=lambda k: -wrong[k])
            times = [_t(r["time"]) for r in recs] + [_t(e.get("time")) for e in meas] + [_t(opened)]
            last = max((t for t in times if t), default=None)
            sub = next((v for k, v in submitted.items() if k and (k in page or page.startswith(k))), None)
            rows.append(dict(student=uid, name=info.get("name", ""), page=page, title=p["title"], opened=opened,
                             questions=n_q, answered=len(by_q), right=len(right), first_try=len(first),
                             revealed=len(revealed), wrong_tries=sum(wrong.values()), stuck=stuck,
                             last_question=recs[-1]["question"] if recs else None, measurements=len(meas),
                             last_activity=last.isoformat(timespec="seconds") if last else None,
                             idle_min=round((now - last).total_seconds() / 60, 1) if last else None,
                             submitted=sub))
    return sorted(rows, key=lambda r: r["last_activity"] or "", reverse=True)


# --------------------------------------------------------------------------- opening a class from the app
# One class open at a time on this computer: web_class.py --class <code> (Voila, and the tunnel unless local only),
# started by the app (twin_app.py, /twin/classes/open). Its process id is kept in classes/_open.json, so that an app
# started again finds it and can close it.
def _open_file():
    return os.path.join(folder(), "_open.json")


def _link_file():
    return os.path.join(run_root(), "web_class_link.txt")


def open_status():
    """The class open on this computer: {code, title, pid, started, tunnel, local, link, running}, or None."""
    try:
        with open(_open_file(), encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return None
    import psutil
    st["running"] = psutil.pid_exists(st.get("pid", -1))
    if not st["running"]:
        return None
    st["link"] = None
    try:
        with open(_link_file(), encoding="utf-8") as f:
            st["link"] = f.read().strip() or None
    except OSError:
        pass
    if not st.get("tunnel"):
        st["link"] = st["local"]                   # local only: the address on this computer / its network
    return st


def open_class(code, tunnel=True, port=7860):
    """Starts the server of the class (closing another one first). Returns open_status() at once: the link of the
    tunnel arrives some seconds later (ask open_status() again)."""
    import subprocess
    c = load(code)
    close_class()
    try:
        os.remove(_link_file())                     # the link of an earlier class must not be shown
    except OSError:
        pass
    cmd = [sys.executable, os.path.join(HERE, "web_class.py"), "--class", c["code"], "--port", str(port)]
    if not tunnel:
        cmd.append("--no-tunnel")
    log = open(os.path.join(run_root(), "web_class_app.log"), "a", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    p = subprocess.Popen(cmd, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=flags, env=dict(os.environ, PYTHONUNBUFFERED="1"))
    st = dict(code=c["code"], title=c["title"], pid=p.pid, tunnel=bool(tunnel), port=port,
              local=f"http://localhost:{port}/?token={c['code']}",
              started=datetime.datetime.now().isoformat(timespec="seconds"))
    os.makedirs(folder(), exist_ok=True)
    with open(_open_file(), "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    return dict(st, running=True, link=None if tunnel else st["local"])


def close_class():
    """Stops the server of the open class (web_class.py, Voila, the tunnel: the whole tree of processes)."""
    try:
        with open(_open_file(), encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return False
    import psutil
    try:
        p = psutil.Process(st["pid"])
        procs = p.children(recursive=True) + [p]
        for q in procs:
            try:
                q.terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(procs, timeout=10)
    except psutil.Error:
        pass
    for f in (_open_file(), _link_file(),
              os.path.join(HERE, "container", "app_data", "voila", "templates", "twin", "static", "class.json")):
        try:
            os.remove(f)
        except OSError:
            pass
    return True


def delete(code):
    """Removes a class (its file only: the work of its students stays in progress/ and web_results/)."""
    st = open_status()
    if st and st["code"] == code:
        close_class()
    os.remove(_path(code))


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("offer")
    n = sub.add_parser("new")
    n.add_argument("title")
    n.add_argument("pages", nargs="+")
    n.add_argument("--named", action="store_true", help="each student types a name (otherwise anonymous)")
    n.add_argument("--power", type=float, default=None, help="power of the source fixed for the class (MW)")
    sub.add_parser("list")
    lv = sub.add_parser("live")
    lv.add_argument("code")
    a = ap.parse_args(argv)
    if a.cmd == "offer":
        for p in offer():
            print(f"{p['id']:40s} {p['level_name']:24s} {p['title']}")
    elif a.cmd == "new":
        c = new(a.title, a.pages, identity="named" if a.named else "anonymous", settings=dict(power_mw=a.power))
        print(f"class {c['code']}: {c['title']} ({c['identity']}, {len(c['pages'])} page(s))")
        print(f"open it:  python web_class.py --class {c['code']}")
    elif a.cmd == "list":
        for c in classes():
            print(f"{c['code']}  {c['created'][:16]}  {c['identity']:9s}  {len(c['pages'])} page(s)  {c['title']}")
    elif a.cmd == "live":
        for r in live(a.code):
            who = r["name"] or r["student"]
            print(f"{who:20s} {r['title'][:34]:34s} Q {r['right']}/{r['questions']} (1st try {r['first_try']}, "
                  f"shown {r['revealed']}) stuck {','.join(r['stuck']) or '-':8s} meas {r['measurements']:3d}  "
                  f"idle {r['idle_min']} min  {'SUBMITTED' if r['submitted'] else ''}")


if __name__ == "__main__":
    _main(sys.argv[1:])
