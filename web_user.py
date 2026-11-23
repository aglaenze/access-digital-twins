"""The (anonymous) student of a page in the online version of the twins (one server for a whole class, no account, no app).

The online version (container/start.sh web: TWIN_WEB=1) serves the guided pages with Voila alone: no notebook, no
NICOS, no code, behind a class password (the Voila token). Its start page lets the student choose an exercise and opens
its page with "?sid=<random id>" in the address: the id is drawn once by the browser and kept there (localStorage), so
that a reload or a second visit finds the same measurements. No name is asked: the answers are anonymous. Each page
runs in its own kernel, where

    import web_user
    web_user.sign_in()

reads the id (Voila gives the query string to the kernel) and makes it the student of this kernel: the measurements go
to the session "anon_<id>", the answers carry it (the same environment variables as the app sets for its signed-in
student: TWIN_USER, TWIN_USER_NAME, ODIN_SESSION, LOKI_SESSION). The time the page was first opened is kept
(progress/<id>/web.json) for the statistics of the class (web_results.py). Without TWIN_WEB (the app, a notebook)
sign_in() does nothing.
"""
import datetime
import json
import os
import re
import secrets
from urllib.parse import parse_qs


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def web():
    return os.environ.get("TWIN_WEB") == "1"


def _page():
    """The page of this kernel (path below the root of the repository), from the address Voila was given."""
    p = os.environ.get("SCRIPT_NAME", "") + os.environ.get("PATH_INFO", "")
    m = re.search(r"voila/render/(.+?\.ipynb)", p)
    return m.group(1) if m else ""


def sign_in():
    """Makes the anonymous id of the address the student of this kernel (online version only). Without an id (the
    page opened directly), one is drawn for this visit."""
    if not web():
        return True
    if not _wait_for_request():
        return False                  # a kernel kept in reserve, released without a student (the server stops)
    queue_banner()
    sid = (parse_qs(os.environ.get("QUERY_STRING", "")).get("sid") or [""])[0]
    sid = re.sub(r"[^a-z0-9]", "", sid.lower())[:16]
    known = len(sid) >= 6
    if not known:
        sid = secrets.token_hex(5)
    uid = "anon_" + sid
    q = parse_qs(os.environ.get("QUERY_STRING", ""))
    # the class of this server (web_class.py --class) and, in a named class, the name the student typed on the start
    # page (kept by the browser, sent with each page)
    klass = os.environ.get("TWIN_CLASS", "")
    name = " ".join((q.get("name") or [""])[0].split())[:80]
    os.environ.update(TWIN_USER=uid, TWIN_USER_NAME=name, ODIN_SESSION=uid, LOKI_SESSION=uid)
    folder = os.path.join(_run_root(), "progress", uid)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "account.json"), "w", encoding="utf-8") as f:
        json.dump(dict(id=uid, name=name, email=""), f)
    # first opening of each page: the start of the exercise (kept over reloads)
    p = os.path.join(folder, "web.json")
    try:
        with open(p, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        info = {}
    page = _page() or "page"
    now = datetime.datetime.now().isoformat(timespec="seconds")
    # "Start again" on the start page: ?restart=<token>, once per token (a reload of the page does not start again)
    token = re.sub(r"[^a-z0-9]", "", (q.get("restart") or [""])[0].lower())[:16]
    if token and token not in info.get("restarts", []):
        info.setdefault("restarts", []).append(token)
        _start_again(folder, page)
        info.get("opened", {}).pop(page, None)          # the time of the exercise counts from now
    if klass:
        info["class"] = klass
    if name:
        info["name"] = name
    info.setdefault("opened", {}).setdefault(page, now)
    info.setdefault("visits", []).append(dict(page=page, time=now))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1)
    try:
        import web_results
        web_results.send("opened", uid, dict(page=page, **{"class": klass, "name": name}))
    except Exception:
        pass
    return known


def _start_again(folder, page):
    """Puts aside the answers to the questions of the page (folder _old/ of the student: nothing is deleted, as the
    "Start again" of the app); the measurements stay."""
    import shutil
    try:
        import classes
        quiz_name = classes._quiz_name(page)
    except Exception:
        quiz_name = None
    if not quiz_name:
        return
    old = os.path.join(folder, "_old", f"{quiz_name}_{datetime.datetime.now():%Y%m%d_%H%M%S}")
    for ext in (".jsonl", ".meta.json"):
        f = os.path.join(folder, quiz_name + ext)
        if os.path.isfile(f):
            os.makedirs(old, exist_ok=True)
            shutil.move(f, os.path.join(old, os.path.basename(f)))


def opened(page_part):
    """When the student first opened the page whose path contains page_part (ISO time), or None."""
    p = os.path.join(_run_root(), "progress", os.environ.get("TWIN_USER", ""), "web.json")
    try:
        with open(p, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    for page, t in info.get("opened", {}).items():
        if page_part in page:
            return t
    return None


def _wait_for_request():
    """With pre-heated kernels (web_class.py --preheat), Voila runs the page before a student asks for it: wait here
    for the student's request, which brings the address (sid) into the environment. Without them: nothing to do."""
    if os.environ.get("VOILA_PREHEAT", "False") == "False":
        return True
    try:
        from voila.utils import wait_for_request
        wait_for_request()
    except Exception:
        return False
    return "QUERY_STRING" in os.environ          # set by Voila from the request of the student


_BANNER = []


def queue_banner():
    """A banner at the bottom right of the page while a measurement waits for its turn on the server (twin_slots.py:
    a few heavy operations at once, first come, first served): how many are before it and about how long."""
    if _BANNER:
        return _BANNER[0]
    try:
        import ipywidgets as w
        from IPython.display import display
        import twin_slots
    except ImportError:
        return None
    style = ("position:fixed;right:18px;bottom:18px;z-index:1000;max-width:340px;padding:12px 16px;border-radius:10px;"
             "background:#0F1D31;color:#F8FAFC;box-shadow:0 6px 24px rgba(0,0,0,.25);font:14px/1.4 system-ui,sans-serif")
    banner = w.HTML("")

    def show(state):
        if state is None:
            banner.value = ""
            return
        ahead, m = state["ahead"], max(1, round(state["wait_s"] / 60))
        who = "1 measurement" if ahead == 1 else f"{ahead} measurements"
        banner.value = (f"<div style='{style}'><b>Your measurement is in line.</b><br>{who} before yours (the server "
                        f"runs {state['slots']} at a time): about {m} min. It starts by itself, keep the page "
                        f"open.</div>")
    twin_slots.listen(show)
    display(banner)
    _BANNER.append(banner)
    return banner
