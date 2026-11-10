"""The ESS Event Formation Unit as a service next to the twin (in the app container: Linux x86-64;
nicos/start_nicos.py --efu starts it). One EFU per detector topic of the real file, as at ESS:

* ODIN: the program timepix3 (configs/odin_timepix3.json), topic odin_detector, source timepix3;
* LoKI: the program loki (configs/loki.json and a null calibration), one per bank, topics loki_detector_bank0 ... 8,
  source caen.

    available(instrument)    (True, version) if the EFU of this instrument runs here, else (False, why)
    start(instrument, log)   starts its EFUs; returns their Popen
    targets(host)            {topic: (host, UDP port)}: where the twin sends the raw readout of each detector topic
    INSTANCES                instrument -> [(program, config, topic, UDP port, command port)]

With TWIN_EFU=1 the twin server sends the raw readout of its detectors to the EFUs (ODIN: timepix3_readout.Camera;
LoKI: caen_readout.Readout) instead of publishing their neutrons itself (filewriter/twin_filewriter.py:
count_messages(efu=targets())).
The programs: TWIN_EFU_HOME/bin, else /opt/efu/bin (the app image, copied from ghcr.io/aglaenze/access-digital-twins-efu);
their libraries in ../lib next to them.
"""
import os
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
INSTANCES = {
    "odin": [("timepix3", "odin_timepix3.json", "odin_detector", 9000, 8888)],
    "loki": [("loki", "loki.json", f"loki_detector_bank{b}", 9100 + b, 8900 + b) for b in range(9)],
}
CMD_PORT = 8888                  # command port of ODIN's EFU (counters: STAT_GET_COUNT, STAT_GET i; efu/e2e_test.efu_stats)


def home():
    return os.environ.get("TWIN_EFU_HOME", "/opt/efu")


def _env():
    lib = os.path.join(home(), "lib")
    old = os.environ.get("LD_LIBRARY_PATH", "")
    return dict(os.environ, LD_LIBRARY_PATH=lib + (os.pathsep + old if old else ""))


def config(name):
    for d in (os.path.join(HERE, "configs"), os.path.join(home(), "configs")):     # the twin's first
        if os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    return os.path.join(HERE, "configs", name)


def targets(host=HOST):
    """{detector topic: (host, UDP port)} of every EFU of the twin (the topics differ from one instrument to another)."""
    return {topic: (host, port) for inst in INSTANCES.values() for _, _, topic, port, _ in inst}


def available(instrument="odin"):
    """(True, version) if the EFU of the instrument can run on this computer, else (False, the reason)."""
    if instrument not in INSTANCES:
        return False, f"no EFU for {instrument.upper()} in the twin"
    if os.name == "nt" or platform.machine().lower() not in ("x86_64", "amd64"):
        return False, f"the EFU is built for Linux x86-64 only (here: {platform.system()} {platform.machine()})"
    exe = os.path.join(home(), "bin", INSTANCES[instrument][0][0])
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
    """Starts the EFUs of the instrument: raw readout on their UDP ports, neutrons to the detector topics of the real
    file (created first). Returns their Popen. Receive buffer: 32 MB asked, the kernel may give less (the twin paces
    its packets). log: the file of the first one; the others write next to it (log.1, log.2, ...)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "filewriter"))
    import twin_filewriter as tf
    inst = INSTANCES[instrument]
    tf.ensure_topics(brokers, [topic for _, _, topic, _, _ in inst])
    calibration = []
    if instrument == "loki":                  # an ideal charge division: no correction (efu/caen_readout.py)
        sys.path.insert(0, HERE)
        import caen_readout
        path = os.path.join(os.path.dirname(log) if log else HERE, "efu_loki_calibration.json")
        calibration = ["--calibration", caen_readout.null_calibration(path)]
    procs = []
    for i, (prog, cfg, topic, port, cmd) in enumerate(inst):
        out = open(log + (f".{i}" if i else ""), "w") if log else subprocess.DEVNULL
        procs.append(subprocess.Popen([os.path.join(home(), "bin", prog), "-f", config(cfg), *calibration,
                                       "--nohwcheck", "-b", brokers, "-t", topic, "-p", str(port), "-m", str(cmd),
                                       "--rxbuffer", str(32 << 20)],
                                      env=_env(), stdout=out, stderr=subprocess.STDOUT))
    return procs


if __name__ == "__main__":
    for name in INSTANCES:
        ok, what = available(name)
        print(f"{name}: " + ("available: " if ok else "not available: ") + what)
