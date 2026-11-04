"""Starts a digital twin driven by NICOS: twin server + NICOS cache, poller, daemon (+ NICOS GUI).

As at ESS, every instrument has its own NICOS (same program, its own setups and GUI, its own services on the
instrument computers): choosing the instrument here is like walking into its control room.

    python start_nicos.py                       # asks which instrument, then everything and the NICOS GUI
    python start_nicos.py --instrument odin     # (login in the GUI: student / student)
    python start_nicos.py --instrument loki --no-gui        # services only (e.g. to connect another NICOS client)
    python start_nicos.py --instrument odin --mode mcstas
    python start_nicos.py --instrument odin --no-gui --background   # no console needed (stop the process to end)

Two Python environments are used, on purpose: the twin (McStas, essimaging, numpy 2) in the Python running this launcher, NICOS
(numpy < 2) in the conda env "nicos". They talk over HTTP on this computer only. Press Enter (or Ctrl+C) to stop all.
Paths can be changed with the environment variables CONDA_ROOT, MCSTAS_PYTHON, NICOS_PYTHON, NICOS_ROOT,
TWIN_RUN_ROOT.
Logs: <TWIN_RUN_ROOT>/nicos/*.log.
"""
import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TWIN = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
# conda installation holding the "nicos" environment: CONDA_ROOT, else the one of the Python running this launcher
_here = os.path.dirname(os.path.dirname(sys.prefix)) if os.path.basename(os.path.dirname(sys.prefix)) == "envs" else sys.prefix
CONDA = os.environ.get("CONDA_ROOT", _here)


def conda_python(env):
    return os.path.join(CONDA, "envs", env, "python.exe" if os.name == "nt" else os.path.join("bin", "python"))


# The twin server runs with the Python of this launcher (start it from the activated twin environment)
MCSTAS_PY = os.environ.get("MCSTAS_PYTHON", sys.executable)
NICOS_PY = os.environ.get("NICOS_PYTHON", conda_python("nicos"))
NICOS_ROOT = os.environ.get("NICOS_ROOT", os.path.join(HOME, "McStas_runs", "nicos_src"))
RUN_ROOT = os.environ.get("TWIN_RUN_ROOT", os.path.join(HOME, "McStas_runs", "twin")).replace(os.sep, "/")
LOGS = os.path.join(RUN_ROOT, "nicos")
PROCS = []
# instruments with a NICOS package nicos_twin/<name> (same names as in twin_server.INSTRUMENTS)
INSTRUMENTS = {"odin": "ODIN — neutron imaging", "loki": "LoKI — small-angle neutron scattering (first version)"}


def choose_instrument():
    print("Which instrument?")
    names = list(INSTRUMENTS)
    for i, n in enumerate(names, 1):
        print(f"  {i}. {INSTRUMENTS[n]}")
    while True:
        try:
            a = input("Number or name: ").strip().lower()
        except EOFError:
            raise SystemExit("no console: give the instrument with --instrument " + "|".join(names)) from None
        if a in names:
            return a
        if a.isdigit() and 1 <= int(a) <= len(names):
            return names[int(a) - 1]


def start(name, cmd, env=None, cwd=None):
    log = open(os.path.join(LOGS, f"{name}.log"), "w", encoding="utf-8")
    p = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    PROCS.append((name, p))
    print(f"  {name} started (pid {p.pid}, log {log.name})", flush=True)
    return p


def wait_for(test, what, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if test():
            return
        for name, p in PROCS:
            if p.poll() is not None:
                raise RuntimeError(f"{name} stopped (see {LOGS}/{name}.log)")
        time.sleep(0.5)
    raise RuntimeError(f"timeout waiting for {what}")


def http_ok(url):
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:
        return False


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def stop_all():
    for name, p in reversed(PROCS):
        if p.poll() is None:
            if os.name == "nt":       # whole process tree (the daemon has a child for its script thread)
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            else:
                p.terminate()
            print(f"  {name} stopped", flush=True)


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--instrument", choices=sorted(INSTRUMENTS), help="instrument (asked if not given)")
    a.add_argument("--session", default="nicos", help="twin session name (folder of files written outside NICOS)")
    a.add_argument("--mode", default="hybrid", choices=("hybrid", "mcstas"))
    a.add_argument("--port", type=int, default=8765, help="port of the twin server")
    a.add_argument("--no-gui", action="store_true")
    a.add_argument("--background", action="store_true", help="do not wait for Enter (run until stopped)")
    o = a.parse_args()
    busy = [f"{what} (port {port})" for what, port in (("twin server", o.port), ("NICOS cache", 14869),
                                                         ("NICOS daemon", 1301)) if port_open(port)]
    if busy:      # one instrument at a time on a computer, as one NICOS per instrument computer at ESS
        print("Another twin with NICOS is already running on this computer: " + ", ".join(busy) + ".\n"
              "Stop it first (Enter in its launcher window, or close that launcher), then start again.")
        return 1
    instr = o.instrument or choose_instrument()
    os.makedirs(LOGS, exist_ok=True)
    print(f"Starting the {instr.upper()} digital twin with NICOS:", flush=True)
    try:
        start("twin_server", [MCSTAS_PY, os.path.join(TWIN, "twin_server.py"), "--instrument", instr,
                              "--session", o.session, "--mode", o.mode, "--port", str(o.port)], cwd=TWIN)
        wait_for(lambda: http_ok(f"http://127.0.0.1:{o.port}/status"), "the twin server")
        # TWIN_RUN_ROOT is read by the NICOS setups (cache database, data root)
        env = dict(os.environ, INSTRUMENT=f"nicos_twin.{instr}", TWIN_RUN_ROOT=RUN_ROOT,
                   PYTHONPATH=os.pathsep.join([HERE, os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep))
        start("nicos_cache", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-cache")], env=env, cwd=NICOS_ROOT)
        wait_for(lambda: port_open(14869), "the NICOS cache")
        start("nicos_poller", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-poller")], env=env, cwd=NICOS_ROOT)
        start("nicos_daemon", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-daemon")], env=env, cwd=NICOS_ROOT)
        wait_for(lambda: port_open(1301), "the NICOS daemon")
        print(f"{instr.upper()} services ready. NICOS daemon on localhost:1301 (user student, password student).",
              flush=True)
        if not o.no_gui:
            start("nicos_gui", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-gui"),
                                "-c", os.path.join(HERE, "nicos_twin", instr, "guiconfig.py"),
                                "student@localhost:1301"], env=env, cwd=NICOS_ROOT)
        background = o.background
        if not background:
            print("Press Enter to stop everything.", flush=True)
            try:
                input()
            except EOFError:       # no console after all
                background = True
        if background:             # run until this process is stopped (or a service dies)
            print("Running in the background; stop this process to stop everything.", flush=True)
            while all(p.poll() is None for _, p in PROCS):
                time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()


if __name__ == "__main__":
    sys.exit(main())
