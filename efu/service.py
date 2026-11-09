"""The ESS Event Formation Unit as a service next to the twin (in the app container: Linux x86-64;
nicos/start_nicos.py --efu starts it). ODIN only for now: the program timepix3, configs/odin_timepix3.json, which
publishes the neutrons on the detector topic of the real file (odin_detector, source timepix3).

    available(instrument)    (True, version) if the EFU of this instrument runs here, else (False, why)
    start(instrument, log)   starts it; returns its Popen
    ADDRESS                  where the twin sends the raw readout (UDP)

With TWIN_EFU=1 the twin server sends the readout of its camera to the EFU (timepix3_readout.Camera) instead of
publishing its neutrons itself (filewriter/twin_filewriter.py: count_messages(efu=...)).
The programs: TWIN_EFU_HOME/bin, else /opt/efu/bin (the app image, copied from ghcr.io/aglaenze/access-digital-twins-efu);
their libraries in ../lib next to them.
"""
import os
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ADDRESS = ("127.0.0.1", 9000)
PROGRAMS = {"odin": ("timepix3", "odin_timepix3.json", "odin_detector")}
CMD_PORT = 8888                  # its command port (counters: STAT_GET_COUNT, STAT_GET i; efu/e2e_test.efu_stats)


def home():
    return os.environ.get("TWIN_EFU_HOME", "/opt/efu")


def _env():
    lib = os.path.join(home(), "lib")
    old = os.environ.get("LD_LIBRARY_PATH", "")
    return dict(os.environ, LD_LIBRARY_PATH=lib + (os.pathsep + old if old else ""))


def config(instrument):
    name = PROGRAMS[instrument][1]
    for d in (os.path.join(HERE, "configs"), os.path.join(home(), "configs")):     # the twin's first
        if os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    return os.path.join(HERE, "configs", name)


def available(instrument="odin"):
    """(True, version) if the EFU of the instrument can run on this computer, else (False, the reason)."""
    if instrument not in PROGRAMS:
        return False, f"no EFU for {instrument.upper()} in the twin yet (ODIN only)"
    if os.name == "nt" or platform.machine().lower() not in ("x86_64", "amd64"):
        return False, f"the EFU is built for Linux x86-64 only (here: {platform.system()} {platform.machine()})"
    exe = os.path.join(home(), "bin", PROGRAMS[instrument][0])
    if not os.path.isfile(exe):
        return False, f"the EFU is not installed ({exe})"
    try:
        r = subprocess.run([exe, "--help"], env=_env(), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"the EFU does not run: {e}"
    if r.returncode != 0:
        return False, f"the EFU does not run: {(r.stderr or r.stdout).strip()[-300:]}"
    v = os.path.join(home(), "EFU_VERSION")
    return True, " ".join(open(v).read().split()) if os.path.isfile(v) else exe


def start(instrument="odin", log=None, brokers="127.0.0.1:9092"):
    """Starts the EFU of the instrument: raw readout on UDP ADDRESS, neutrons to the detector topic of the real file
    (created first). Its receive buffer: 32 MB asked, the kernel may give less (the twin paces its packets)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "filewriter"))
    import twin_filewriter as tf
    prog, _, topic = PROGRAMS[instrument]
    tf.ensure_topics(brokers, [topic])
    out = open(log, "w") if log else subprocess.DEVNULL
    return subprocess.Popen([os.path.join(home(), "bin", prog), "-f", config(instrument), "--nohwcheck",
                             "-b", brokers, "-t", topic, "-p", str(ADDRESS[1]), "-m", str(CMD_PORT),
                             "--rxbuffer", str(32 << 20)],
                            env=_env(), stdout=out, stderr=subprocess.STDOUT)


if __name__ == "__main__":
    ok, what = available()
    print(("available: " if ok else "not available: ") + what)
