"""At most a few heavy operations at once on one server (the online version for a class: one computer, many students).

A count of the twin draws tens of millions of neutrons, and reading its file loads them all: about a gigabyte of
memory each, for a minute. Ten students doing it at the same moment exhaust the memory of the server. With

    TWIN_HEAVY_SLOTS=2            (set by web_class.py and start.sh web; unset: no limit, as in the app)

    with twin_slots.heavy(lambda: print("Waiting for the instrument...")):
        ...                        # the count, or the reading of an event file

at most 2 such operations run at once (a count of 60 s or the reading of its file: up to 4 GB each), across all the
kernels of the server; the others wait, **first come, first served**:

  * a waiting operation holds a ticket (TWIN_RUN_ROOT/slots/queue/<time>_<pid>_<n>); it takes a free slot only when
    no older ticket is waiting before it;
  * a slot is a file (TWIN_RUN_ROOT/slots/slotK) holding the process id; a slot or a ticket of a process that died,
    or older than an hour, is freed;
  * the durations of the last operations (slots/durations.json) give an estimate of the wait.

The student is told where they are: the `waiting` message is shown once, and every function registered with
listen(fn) is called with {"ahead": operations before this one (running or waiting), "slots": n, "wait_s": estimated
wait [s]} whenever that changes, then with None when the operation starts (web_user.py shows it in a banner).
"""
import contextlib
import json
import os
import time

LISTENERS = []           # functions called with the state of the queue (this process)
_SEQ = [0]


def listen(fn):
    """fn(state): state = {"ahead": int, "slots": int, "wait_s": float} while waiting, None when the operation starts."""
    if fn not in LISTENERS:
        LISTENERS.append(fn)


def _tell(state):
    for fn in list(LISTENERS):
        try:
            fn(state)
        except Exception:
            pass


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def _pid_of(path, name=None):
    """Process id written in a slot file, or in the name of a ticket (<time>_<pid>_<n>)."""
    if name is not None:
        try:
            return int(name.split("_")[1])
        except (IndexError, ValueError):
            return 0
    with open(path, encoding="utf-8") as f:
        return int(f.read().strip() or 0)


def _stale(path, name=None):
    try:
        pid = _pid_of(path, name)
    except (OSError, ValueError):
        return False                       # being written: not stale
    try:
        if time.time() - os.path.getmtime(path) > 3600:
            return True
        import psutil
        return not psutil.pid_exists(pid)
    except Exception:
        return False


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _typical_s(d):
    """Typical duration of a heavy operation [s]: median of the last ones (60 s before any is known)."""
    try:
        with open(os.path.join(d, "durations.json"), encoding="utf-8") as f:
            last = [float(x) for x in json.load(f)][-20:]
    except (OSError, ValueError, TypeError):
        last = []
    return float(sorted(last)[len(last) // 2]) if last else 60.0


def _record(d, seconds):
    p = os.path.join(d, "durations.json")
    try:
        with open(p, encoding="utf-8") as f:
            last = list(json.load(f))[-49:]
    except (OSError, ValueError, TypeError):
        last = []
    tmp = f"{p}.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(last + [round(seconds, 1)], f)
        os.replace(tmp, p)
    except OSError:
        _remove(tmp)


@contextlib.contextmanager
def heavy(waiting=None):
    n = int(os.environ.get("TWIN_HEAVY_SLOTS", "0") or 0)
    if n <= 0:
        yield
        return
    d = os.path.join(_run_root(), "slots")
    q = os.path.join(d, "queue")
    os.makedirs(q, exist_ok=True)
    _SEQ[0] += 1
    ticket = os.path.join(q, f"{time.time_ns():020d}_{os.getpid()}_{_SEQ[0]}")
    open(ticket, "w").close()
    told, mine, last_state = False, None, None
    try:
        while mine is None:
            # the tickets waiting before this one (dead ones removed)
            before = 0
            for name in sorted(os.listdir(q)):
                p = os.path.join(q, name)
                if p == ticket:
                    break
                if _stale(p, name):
                    _remove(p)
                    continue
                before += 1
            busy = 0
            for k in range(n):
                p = os.path.join(d, f"slot{k}")
                if os.path.exists(p):
                    if _stale(p):
                        _remove(p)
                    else:
                        busy += 1
            if before == 0:                        # first in the line: take a free slot
                for k in range(n):
                    p = os.path.join(d, f"slot{k}")
                    try:
                        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    except FileExistsError:
                        continue
                    os.write(fd, str(os.getpid()).encode())
                    os.close(fd)
                    mine = p
                    break
            if mine is not None:
                break
            if not told and waiting is not None:
                waiting()
                told = True
            ahead = busy + before
            # n operations at a time: this one starts after about (before // n + 1) typical durations
            state = dict(ahead=ahead, slots=n, wait_s=(before // n + 1) * _typical_s(d))
            if last_state is None or state["ahead"] != last_state["ahead"]:
                _tell(state)
                last_state = state
            time.sleep(0.5)
    finally:
        _remove(ticket)
    _tell(None)
    t0 = time.time()
    try:
        yield
    finally:
        _remove(mine)
        _record(d, time.time() - t0)
