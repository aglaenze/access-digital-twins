"""The ESS file-writer as a service next to the twin (in the app container: Linux x86-64; nicos/start_nicos.py
--filewriter starts it). One kafka-to-nexus per instrument, as at ESS, with the topics of NICOS ESS:
<instrument>_filewriter (commands and answers) and <instrument>_filewriter_pool (job pool).

    available()            (True, version) if kafka-to-nexus runs here, else (False, why)
    start(instrument, log) starts it (the topics first: it does not see a topic created after it subscribed)
    templates_root()       where the twin writes the templates (<instrument>/<instrument>.hdf): its --hdf-template-prefix

The program: TWIN_K2N, else kafka-to-nexus on the PATH, else /opt/kafka-to-nexus/bin/kafka-to-nexus (the app image,
copied from ghcr.io/aglaenze/access-digital-twins-filewriter); its libraries in ../lib next to it. It logs only to
syslog (none in the container): its errors reach the twin in its answers (answ, wrdn), which NICOS shows.
"""
import os
import platform
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = "/opt/kafka-to-nexus/bin/kafka-to-nexus"


def program():
    return os.environ.get("TWIN_K2N") or shutil.which("kafka-to-nexus") or DEFAULT


def _env(exe):
    lib = os.path.join(os.path.dirname(os.path.dirname(exe)), "lib")
    old = os.environ.get("LD_LIBRARY_PATH", "")
    return dict(os.environ, LD_LIBRARY_PATH=lib + (os.pathsep + old if old else ""))


def available():
    """(True, version) if kafka-to-nexus can run on this computer, else (False, the reason)."""
    exe = program()
    if os.name == "nt" or platform.machine().lower() not in ("x86_64", "amd64"):
        return False, f"kafka-to-nexus is built for Linux x86-64 only (here: {platform.system()} {platform.machine()})"
    if not os.path.isfile(exe):
        return False, f"kafka-to-nexus not found ({exe})"
    try:
        r = subprocess.run([exe, "--help"], env=_env(exe), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"kafka-to-nexus does not run: {e}"
    if r.returncode != 0:
        return False, f"kafka-to-nexus does not run: {(r.stderr or r.stdout).strip()[-300:]}"
    built = os.path.join(os.path.dirname(os.path.dirname(exe)), "K2N_VERSION")     # written by its Containerfile
    return True, open(built).read().strip() if os.path.isfile(built) else exe


def templates_root():
    """Its --hdf-template-prefix: where the twin server writes the templates (same rule as twin_server._fw_start)."""
    run_root = os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))
    return os.environ.get("TWIN_FW_TEMPLATES", os.path.join(run_root, "filewriter", "templates"))


def command_topics(instrument):
    return f"{instrument}_filewriter", f"{instrument}_filewriter_pool"


def start(instrument, log=None, brokers="127.0.0.1:9092"):
    """Starts kafka-to-nexus for `instrument` (its command and pool topics created first); returns the Popen. It must
    see the data folders at the paths the twin gives (--hdf-output-prefix /: the twin gives absolute paths)."""
    sys.path.insert(0, HERE)
    import twin_filewriter as tf
    command, pool = command_topics(instrument)
    tf.ensure_topics(brokers, (command, pool))
    os.makedirs(templates_root(), exist_ok=True)
    exe = program()
    out = open(log, "w") if log else subprocess.DEVNULL
    return subprocess.Popen([exe, "--brokers", brokers, "--command-status-topic", command, "--job-pool-topic", pool,
                             "--hdf-output-prefix", "/", "--hdf-template-prefix", templates_root()],
                            env=_env(exe), stdout=out, stderr=subprocess.STDOUT)


if __name__ == "__main__":
    ok, what = available()
    print(("available: " if ok else "not available: ") + what)
    sys.exit(0 if ok else 1)
