"""Provisional console of a virtual instrument, until NICOS is available: same commands as the NICOS console.

    python -i twin_console.py                  # interactive console
    python twin_console.py my_script.py        # runs a command script (like a NICOS script)

The server (twin_server.py --instrument ...) must be running. Standard library only: the console runs in any Python (including,
later, NICOS's own) and never sees McStas.

Commands (NICOS syntax):
    status()                           state of all devices
    read(stage_x)                      value of one device
    move(stage_x, 0.5)                 move (several at once: move(shutter, "open", stage_x, 0))
    maw(...)                           "move and wait": same here (virtual motors arrive immediately)
    count(10)                          count for 10 s; count(10, title="open beam")
    scan(stage_rot, 0, 3, 60, t=10)    scan: start, step, number of points, time per point
    log()                              what has been done during the session
    help_twin()                        this help
Devices are objects (as in NICOS), named by the server; for ODIN: choppers, wfm_delta, shutter, pinhole, diffuser,
stage_x, stage_rot, sample.
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("TWIN_URL", "http://127.0.0.1:8765")


class InstrumentError(Exception):
    pass


def _request(path, data=None, timeout=3600):
    req = urllib.request.Request(URL + path, method="POST" if data is not None else "GET",
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise InstrumentError(json.loads(e.read()).get("error", str(e))) from None
    except urllib.error.URLError:
        raise InstrumentError(f"no answer from the instrument ({URL}): is the server running?") from None


class Device:
    def __init__(self, name, desc):
        self.name, self.unit, self.help = name, desc["unit"], desc["help"]

    def read(self):
        return _request("/status")["devices"][self.name]

    def __repr__(self):
        return f"<device {self.name} = {self.read()} {self.unit}>".replace(" >", ">")


def _name(d):
    return d.name if isinstance(d, Device) else str(d)


def status():
    s = _request("/status")
    devs = _request("/devices")
    print(f"Virtual instrument ({s['mode']}), {'BUSY: ' + s['running'] if s['busy'] else 'ready'}; "
          f"last file no. {s['last_number']}; data: {s['folder']}")
    for n, v in s["devices"].items():
        print(f"  {n:10s} = {v!s:>10} {devs[n]['unit']:4s}  {devs[n]['help']}")


def read(device):
    v = device.read() if isinstance(device, Device) else _request("/status")["devices"][device]
    print(f"{_name(device)} = {v}")
    return v


def move(*args):
    if len(args) % 2:
        raise InstrumentError("move(device, value, [device, value, ...])")
    r = _request("/move", {_name(d): v for d, v in zip(args[::2], args[1::2])})
    for d in args[::2]:
        print(f"{_name(d)} -> {r['devices'][_name(d)]}")


maw = move


def count(t, title=""):
    print(f"counting {t:g} s ...", flush=True)
    f = _request("/count", {"t": t, "title": title})["file"]
    print(f"file written: {f}")
    return f


def scan(device, start, step, n, t, title=""):
    values = [start + i * step for i in range(int(n))]
    print(f"scan of {_name(device)}: {values[0]:g} -> {values[-1]:g} ({n} points, {t:g} s per point) ...", flush=True)
    files = _request("/scan", {"device": _name(device), "values": values, "t": t, "title": title})["files"]
    print(f"{len(files)} files: {os.path.basename(files[0])} ... {os.path.basename(files[-1])}")
    return files


def log():
    for e in _request("/log"):
        d = e["details"]
        if e["action"] == "count":
            print(f"{e['time']}  count {d['t']:g} s  {d['file']}  {d['title']}  ({d['n_counts']:,} counts)")
        else:
            print(f"{e['time']}  {e['action']}  {d}")


def help_twin():
    print(__doc__)


# Devices become names usable directly: move(stage_x, 0.5)
try:
    for _n, _d in _request("/devices").items():
        globals()[_n] = Device(_n, _d)
except InstrumentError as e:
    print(e)

if __name__ == "__main__":
    if len(sys.argv) > 1:                                   # command script
        code = open(sys.argv[1], encoding="utf-8").read()
        exec(compile(code, sys.argv[1], "exec"), globals())
    elif sys.flags.interactive:
        print("Digital-twin console. help_twin() for the list of commands; status() for the state.")
