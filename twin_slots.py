"""At most a few heavy operations at once on one server (the online version for a class: one computer, many students).

A count of the twin draws tens of millions of neutrons, and reading its file loads them all: about a gigabyte of
memory each, for a minute. Ten students doing it at the same moment exhaust the memory of the server. With

    TWIN_HEAVY_SLOTS=2            (set by web_class.py and start.sh web; unset: no limit, as in the app)

    with twin_slots.heavy(lambda: print("Waiting for the instrument...")):
        ...                        # the count, or the reading of an event file

at most 2 such operations run at once (a count of 60 s or the reading of its file: up to 4 GB each), across all the kernels of the server; the others wait for a free slot (the
message is shown once). A slot is a file (TWIN_RUN_ROOT/slots/slotK) holding the process id: the slot of a process
that died, or older than an hour, is freed.
"""
import contextlib
import os
import time


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def _stale(path):
    try:
        with open(path, encoding="utf-8") as f:
            pid = int(f.read().strip() or 0)
    except (OSError, ValueError):
        return False                       # being written: not stale
    try:
        if time.time() - os.path.getmtime(path) > 3600:
            return True
        import psutil
        return not psutil.pid_exists(pid)
    except Exception:
        return False


@contextlib.contextmanager
def heavy(waiting=None):
    n = int(os.environ.get("TWIN_HEAVY_SLOTS", "0") or 0)
    if n <= 0:
        yield
        return
    d = os.path.join(_run_root(), "slots")
    os.makedirs(d, exist_ok=True)
    told, mine = False, None
    while mine is None:
        for k in range(n):
            p = os.path.join(d, f"slot{k}")
            try:
                fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if _stale(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                continue
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            mine = p
            break
        else:
            if not told and waiting is not None:
                waiting()
                told = True
            time.sleep(0.5)
    try:
        yield
    finally:
        try:
            os.remove(mine)
        except OSError:
            pass
