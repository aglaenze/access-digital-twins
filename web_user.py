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
    sid = (parse_qs(os.environ.get("QUERY_STRING", "")).get("sid") or [""])[0]
    sid = re.sub(r"[^a-z0-9]", "", sid.lower())[:16]
    known = len(sid) >= 6
    if not known:
        sid = secrets.token_hex(5)
    uid = "anon_" + sid
    os.environ.update(TWIN_USER=uid, TWIN_USER_NAME="", ODIN_SESSION=uid, LOKI_SESSION=uid)
    folder = os.path.join(_run_root(), "progress", uid)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "account.json"), "w", encoding="utf-8") as f:
        json.dump(dict(id=uid, name="", email=""), f)
    # first opening of each page: the start of the exercise (kept over reloads)
    p = os.path.join(folder, "web.json")
    try:
        with open(p, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        info = {}
    page = _page() or "page"
    now = datetime.datetime.now().isoformat(timespec="seconds")
    info.setdefault("opened", {}).setdefault(page, now)
    info.setdefault("visits", []).append(dict(page=page, time=now))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1)
    try:
        import web_results
        web_results.send("opened", uid, dict(page=page))
    except Exception:
        pass
    return known


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
