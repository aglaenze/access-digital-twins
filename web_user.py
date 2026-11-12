"""The student of a page in the online version of the twins (one server for a whole class, no account, no app).

The online version (container/start.sh web: TWIN_WEB=1) serves the guided pages with Voila alone: no notebook, no
NICOS, no code. Its start page asks for a name and opens the page of the exercise with "?name=..." in the address;
each page then runs in its own kernel, where

    import web_user
    web_user.sign_in()

reads the name (Voila gives the query string to the kernel) and makes it the student of this kernel: the measurements
go to the session of that name, the answers and the file to submit carry it (the same environment variables as the
app sets for its signed-in student: TWIN_USER, TWIN_USER_NAME, ODIN_SESSION, LOKI_SESSION). Two students who give the
same name share their measurements: the start page asks for the full name. Without TWIN_WEB (the app, a notebook)
sign_in() does nothing.
"""
import json
import os
import re
from urllib.parse import parse_qs


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def safe_id(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:60]


def sign_in():
    """True if the page has its student (always outside the online version). Online without a name: shows a link to
    the start page (and goes there), and the page runs as "guest"."""
    if os.environ.get("TWIN_WEB") != "1":
        return True
    name = (parse_qs(os.environ.get("QUERY_STRING", "")).get("name") or [""])[0].strip()[:60]
    uid = safe_id(name)
    known = bool(uid)
    if not known:
        from IPython.display import HTML, display
        display(HTML('<p><b>No name given.</b> <a href="/">Go to the start page</a> and enter your name first.</p>'
                     '<script>window.location.replace("/");</script>'))
        uid, name = "guest", "Guest"
    os.environ.update(TWIN_USER=uid, TWIN_USER_NAME=name, ODIN_SESSION=uid, LOKI_SESSION=uid)
    folder = os.path.join(_run_root(), "progress", uid)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "account.json"), "w", encoding="utf-8") as f:
        json.dump(dict(id=uid, name=name, email=""), f)
    return known
