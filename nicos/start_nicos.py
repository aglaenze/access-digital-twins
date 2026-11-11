"""Starts a digital twin driven by NICOS: twin server + NICOS cache, poller, daemon (+ NICOS GUI).

As at ESS, every instrument has its own NICOS (same program, its own setups and GUI, its own services on the
instrument computers): choosing the instrument here is like walking into its control room.

    python start_nicos.py                       # asks which instrument, then everything and the NICOS GUI
    python start_nicos.py --instrument odin     # (login in the GUI: student / student)
    python start_nicos.py --instrument loki --no-gui        # services only (e.g. to connect another NICOS client)
    python start_nicos.py --instrument odin --mode mcstas
    python start_nicos.py --instrument odin --no-gui --background   # no console needed (stop the process to end)
    python start_nicos.py --instrument odin --live   # live data as at ESS: Kafka broker + just-bin-it + setup "live"
    python start_nicos.py --instrument odin --filewriter   # files written by the ESS file-writer (kafka-to-nexus), as
                                                           # at ESS (Linux x86-64: the app container; TWIN_FILEWRITER=1)
    python start_nicos.py --instrument loki --livedata     # live reduction of ESS (esslivedata; dashboard on port
                                                           # 5009; the app container; TWIN_LIVEDATA=1)
    python start_nicos.py --instrument odin --epics --filewriter   # the devices as EPICS PVs (soft IOC), relayed to
                                                           # Kafka by the ESS forwarder (the app container; TWIN_EPICS=1)
    python start_nicos.py --instrument odin --efu --filewriter     # the neutrons made by the ESS Event Formation
                                                           # Unit from the raw readout of the camera (ODIN; the app
                                                           # container; TWIN_EFU=1)

Two Python environments are used, on purpose: the twin (McStas, essimaging, numpy 2) in the Python running this launcher, NICOS
(numpy < 2) in the conda env "nicos". They talk over HTTP on this computer only. Press Enter (or Ctrl+C) to stop all.
Paths can be changed with the environment variables CONDA_ROOT, MCSTAS_PYTHON, NICOS_PYTHON, NICOS_ROOT,
TWIN_RUN_ROOT; for --live, --filewriter and --livedata: KAFKA_HOME, JAVA_HOME (see ../kafka/start_kafka.py) and JBI_HOME (sources of
just-bin-it, default ~/McStas_runs/just-bin-it).
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
AUX = []          # optional services (esslivedata): stopped with the rest, but their failure does not stop NICOS
# instruments with a NICOS package nicos_twin/<name> (same names as in twin_server.INSTRUMENTS)
INSTRUMENTS = {"odin": "ODIN — neutron imaging", "loki": "LoKI — small-angle neutron scattering (first version)"}
LIVE = {"odin", "loki"}    # instruments with live data (setup nicos_twin/<instrument>/setups/live.py)
JBI_HOME = os.environ.get("JBI_HOME", os.path.join(HOME, "McStas_runs", "just-bin-it"))


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


def _livedata_service(folder="livedata"):
    """livedata/service.py, epics/service.py (imported under their own names: filewriter/ has a service.py too)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"{folder}_service", os.path.join(TWIN, folder, "service.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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
    for name, p in reversed(PROCS + AUX):
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
    a.add_argument("--live", action="store_true", help="live data: Kafka broker, just-bin-it and setup 'live'")
    a.add_argument("--filewriter", action="store_true", default=os.environ.get("TWIN_FILEWRITER") == "1",
                   help="the ESS file-writer writes the files of nexusfile_open (default: TWIN_FILEWRITER=1)")
    a.add_argument("--livedata", action="store_true", default=os.environ.get("TWIN_LIVEDATA") == "1",
                   help="live data reduction of ESS (esslivedata, dashboard on port 5009; default: TWIN_LIVEDATA=1)")
    a.add_argument("--epics", action="store_true", default=os.environ.get("TWIN_EPICS") == "1",
                   help="the devices as EPICS PVs, relayed to Kafka by the ESS forwarder (default: TWIN_EPICS=1)")
    a.add_argument("--efu", action="store_true", default=os.environ.get("TWIN_EFU") == "1",
                   help="the ESS Event Formation Unit makes the neutrons from the raw readout of the detector (ODIN; "
                        "default: TWIN_EFU=1)")
    a.add_argument("--no-proposals", dest="proposals", action="store_false",
                   default=os.environ.get("TWIN_PROPOSALS", "1") != "0",
                   help="without the twin's user office: any proposal number is typed in the Experiment tab, as when "
                        "the proposal system is unreachable at ESS (default: the user office, as at ESS: Find my proposal lists "
                        "the proposals of the exercises and the student's own; TWIN_PROPOSALS=0 to switch it off)")
    a.add_argument("--until-gui-closes", action="store_true",
                   help="stop everything when the NICOS window is closed (the control room of the app)")
    o = a.parse_args()
    busy = [f"{what} (port {port})" for what, port in (("twin server", o.port), ("NICOS cache", 14869),
                                                         ("NICOS daemon", 1301)) if port_open(port)]
    if busy:      # one instrument at a time on a computer, as one NICOS per instrument computer at ESS
        print("Another twin with NICOS is already running on this computer: " + ", ".join(busy) + ".\n"
              "Stop it first (Enter in its launcher window, or close that launcher), then start again.")
        return 1
    instr = o.instrument or choose_instrument()
    if o.live and instr not in LIVE:
        print(f"Live data not available yet for {instr.upper()}: starting without it.")
        o.live = False
    if o.filewriter:
        sys.path.insert(0, os.path.join(TWIN, "filewriter"))
        import service as fw_service
        usable, what = fw_service.available()
        if not usable:
            print(f"The ESS file-writer is not available here ({what}): the twin writes the files itself.")
            o.filewriter = False
    if o.livedata:
        ld_service = _livedata_service()
        ld_usable, ld_what = ld_service.available()
        if not ld_usable:
            print(f"The live data reduction of ESS is not available here ({ld_what}).")
            o.livedata = False
    if o.epics:
        ep_service = _livedata_service("epics")
        ep_usable, ep_what = ep_service.available()
        if not ep_usable:
            print(f"The EPICS layer (soft IOC + ESS forwarder) is not available here ({ep_what}).")
            o.epics = False
    if o.efu:
        efu_service = _livedata_service("efu")
        efu_usable, efu_what = efu_service.available(instr)
        if not efu_usable:
            print(f"The Event Formation Unit of ESS is not available here ({efu_what}).")
            o.efu = False
    # read by the twin server: each count also publishes its neutrons as the instrument does, for esslivedata; with
    # the EPICS layer, the device values are relayed by the forwarder instead of the twin
    os.environ["TWIN_LIVEDATA"] = "1" if o.livedata else "0"
    os.environ["TWIN_EPICS"] = "1" if o.epics else "0"
    os.environ["TWIN_EFU"] = "1" if o.efu else "0"
    os.makedirs(LOGS, exist_ok=True)
    if o.proposals:            # the twin's user office: the proposal cache that EssExperiment reads (user_office.py)
        r = subprocess.run([MCSTAS_PY, os.path.join(TWIN, "user_office.py"), instr,
                            os.path.join(LOGS, f"cached_proposals_{instr}.json")], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"The twin's user office is not available: {(r.stderr or r.stdout).strip()[-300:]}")
            o.proposals = False
    os.environ["TWIN_PROPOSALS"] = "1" if o.proposals else "0"
    print(f"Starting the {instr.upper()} digital twin with NICOS:", flush=True)
    try:
        if o.live or o.filewriter or o.livedata or o.epics or o.efu:     # data streaming as at ESS: the Kafka broker
            if not port_open(9092):
                start("kafka", [MCSTAS_PY, os.path.join(TWIN, "kafka", "start_kafka.py")], cwd=TWIN)
                wait_for(lambda: port_open(9092), "the Kafka broker", timeout=120)
        if o.filewriter:               # the ESS file-writer (kafka-to-nexus), its topics created first
            p = fw_service.start(instr, log=os.path.join(LOGS, "filewriter.log"))
            PROCS.append(("filewriter", p))
            print(f"  filewriter started (pid {p.pid}, {what}; it logs to syslog only)", flush=True)
            time.sleep(5)              # (it subscribes to its job pool)
        if o.livedata:                 # esslivedata: its backend services and dashboard, its topics created first
            for name, p in ld_service.start(instr, logdir=LOGS):
                AUX.append((f"livedata_{name}", p))
            print(f"  esslivedata started ({ld_what}; dashboard http://127.0.0.1:{ld_service.DASHBOARD_PORT}, "
                  f"logs {LOGS}/livedata_*.log)", flush=True)
        if o.efu:                      # the EFU: raw readout of the detector (UDP) -> neutrons (Kafka)
            procs = efu_service.start(instr, log=os.path.join(LOGS, "efu.log"))
            AUX.extend((f"efu{i or ''}", p) for i, p in enumerate(procs))
            print(f"  {len(procs)} EFU started ({efu_what}; log {LOGS}/efu.log)", flush=True)
        if o.live:                 # just-bin-it (histograms for NICOS); its module
            # just_bin_it.cli defines main() without calling it (installed as a script), hence the -c
            subprocess.run([MCSTAS_PY, os.path.join(TWIN, "kafka", "start_kafka.py"), "--topics", instr],
                           check=True, cwd=TWIN)
            start("just_bin_it", [MCSTAS_PY, "-c", "from just_bin_it.cli import main; main()", "-b", "127.0.0.1:9092",
                                  "-t", f"{instr}_jbi_commands", "-hb", f"{instr}_jbi_heartbeat",
                                  "-rt", f"{instr}_jbi_responses", "-l", "3"],
                  env=dict(os.environ, PYTHONPATH=JBI_HOME), cwd=JBI_HOME)
        start("twin_server", [MCSTAS_PY, os.path.join(TWIN, "twin_server.py"), "--instrument", instr,
                              "--session", o.session, "--mode", o.mode, "--port", str(o.port)], cwd=TWIN)
        wait_for(lambda: http_ok(f"http://127.0.0.1:{o.port}/status"), "the twin server")
        if o.epics:                    # the PVs of the twin (soft IOC) and the ESS forwarder, configured with them
            for name, p in ep_service.start(instr, twin=f"http://127.0.0.1:{o.port}", logdir=LOGS):
                AUX.append((name, p))
            print(f"  EPICS layer started ({ep_what}; logs {LOGS}/epics_ioc.log, forwarder.log)", flush=True)
        # TWIN_RUN_ROOT is read by the NICOS setups (cache database, data root)
        env = dict(os.environ, INSTRUMENT=f"nicos_twin.{instr}", TWIN_RUN_ROOT=RUN_ROOT,
                   TWIN_FILEWRITER="1" if o.filewriter else "0",       # read by nicos_twin/commands.py
                   PYTHONPATH=os.pathsep.join([HERE, os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep))
        if o.epics:                    # NICOS finds the PVs (motor records of the sample stage) on this computer
            env.update(ep_service.CLIENT)
        start("nicos_cache", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-cache")], env=env, cwd=NICOS_ROOT)
        wait_for(lambda: port_open(14869), "the NICOS cache")
        start("nicos_poller", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-poller")], env=env, cwd=NICOS_ROOT)
        start("nicos_daemon", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-daemon")], env=env, cwd=NICOS_ROOT)
        wait_for(lambda: port_open(1301), "the NICOS daemon")
        if o.live:                 # load the live-data setup in the daemon (as AddSetup('live') typed by the user)
            r = subprocess.run([NICOS_PY, os.path.join(HERE, "run_nicos_script.py"), "-c", "AddSetup('live')"],
                               capture_output=True, text=True, timeout=300, cwd=HERE)
            print("  setup 'live' loaded" if r.returncode == 0 else f"  setup 'live' NOT loaded: {r.stdout[-500:]}",
                  flush=True)
        extras = [x for x, on in (("live data", o.live), ("ESS file-writer", o.filewriter),
                                  ("ESS live reduction", o.livedata), ("EPICS + forwarder", o.epics),
                                  ("ESS Event Formation Unit", o.efu), ("user office", o.proposals)) if on]
        print(f"{instr.upper()} services ready{' (' + ', '.join(extras) + ')' if extras else ''}. NICOS daemon on localhost:1301 "
              "(user student, password student).", flush=True)
        if not o.no_gui:
            start("nicos_gui", [NICOS_PY, os.path.join(NICOS_ROOT, "bin", "nicos-gui"),
                                "-c", os.path.join(HERE, "nicos_twin", instr, "guiconfig.py"),
                                "student:student@localhost:1301"], env=env, cwd=NICOS_ROOT)   # logged in at once
        if o.until_gui_closes and not o.no_gui:
            gui = dict(PROCS)["nicos_gui"]
            print("Close the NICOS window to stop everything.", flush=True)
            while gui.poll() is None and all(p.poll() is None for _, p in PROCS if p is not gui):
                time.sleep(1)
            return 0
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
