"""EPICS layer of the twin, as at ESS: the soft IOC (ioc.py: every device of the instrument as a PV with its real name)
and the ESS forwarder (EPICS -> Kafka, https://github.com/ess-dmsc/forwarder), which relays the PVs to the topics of
the real instrument (<instrument>_choppers, _motion...) as f144 messages; the file-writer and esslivedata read them
there. nicos/start_nicos.py --epics (TWIN_EPICS=1) starts them, after the twin server.

    available()                    (True, version) if the forwarder is installed here, else (False, why)
    start(instrument, twin, logdir) starts the IOC and the forwarder, configures the forwarder; returns [(name, Popen)]

Both run in the conda environment "forwarder" (Python 3.11, the forwarder's pinned requirements, p4p): fixed release
in the Containerfile. With TWIN_EPICS=1 the twin server no longer publishes the device values itself
(filewriter/twin_filewriter.py: snapshot_messages, count_messages): the forwarder does, as at ESS.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# PV values sent again every 5 s even when unchanged (as the forwarder does at ESS for motors): the file-writer looks
# for the last value of each device in the 10 s before a job starts
UPDATE_PERIOD_MS = 5000
# pvAccess on this computer only (the IOC serves on 127.0.0.1; the forwarder searches there)
CLIENT = {"EPICS_PVA_ADDR_LIST": "127.0.0.1", "EPICS_PVA_AUTO_ADDR_LIST": "NO",
          "EPICS_CA_ADDR_LIST": "127.0.0.1", "EPICS_CA_AUTO_ADDR_LIST": "NO"}


def env_bin():
    """The bin folder of the "forwarder" environment (TWIN_FORWARDER_ENV, else the conda environment of the image)."""
    if os.environ.get("TWIN_FORWARDER_ENV"):
        return os.path.join(os.environ["TWIN_FORWARDER_ENV"], "bin")
    for root in (os.environ.get("MAMBA_ROOT_PREFIX", "/opt/conda"), os.path.expanduser("~/miniforge3")):
        b = os.path.join(root, "envs", "forwarder", "bin")
        if os.path.isdir(b):
            return b
    return os.path.dirname(shutil.which("forwarder-launch") or sys.executable)


def available():
    exe = os.path.join(env_bin(), "forwarder-launch")
    if not os.path.isfile(exe):
        return False, f"ESS forwarder not installed ({exe})"
    py = os.path.join(env_bin(), "python")
    r = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False, f"ESS forwarder does not run: {(r.stderr or r.stdout).strip()[-200:]}"
    r = subprocess.run([py, "-c", "import importlib.metadata as m, p4p.server; print(m.version('p4p'))"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False, f"p4p does not run: {(r.stderr or r.stdout).strip()[-200:]}"
    # the image runs the forwarder from its source tree (TWIN_FORWARDER_SRC, as ESS does); the release is written there
    vf = os.path.join(os.environ.get("TWIN_FORWARDER_SRC", ""), "TWIN_VERSION")
    fw = open(vf).read().strip() if os.path.isfile(vf) else "(release unknown)"
    return True, f"ESS forwarder {fw}, p4p {r.stdout.strip()}"


def topics(instrument):
    return f"{instrument}_forwarder_config", f"{instrument}_forwarder_status"


def _wait(test, what, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if test():
            return
        time.sleep(1)
    raise RuntimeError(f"timeout waiting for {what}")


def start(instrument, twin="http://127.0.0.1:8765", logdir=None, brokers="127.0.0.1:9092"):
    """Starts the soft IOC and the forwarder, then gives the forwarder the PVs to relay (fc00 message: every PV of the
    IOC, to its topic, schema f144, protocol pvAccess, sent again periodically). Returns [(name, Popen)]."""
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "filewriter"))
    import twin_filewriter as tf
    with urllib.request.urlopen(f"{twin}/epics", timeout=60) as r:
        rows = json.loads(r.read())
    config, status = topics(instrument)
    tf.ensure_topics(brokers, {config, status} | {r["topic"] for r in rows})
    b = env_bin()
    env = dict(os.environ, **CLIENT)
    procs = []

    def run(name, cmd):
        out = open(os.path.join(logdir, f"{name}.log"), "w") if logdir else subprocess.DEVNULL
        procs.append((name, subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT)))

    run("epics_ioc", [os.path.join(b, "python"), os.path.join(HERE, "ioc.py"), "--twin", twin])
    if logdir:
        _wait(lambda: "IOC ready" in open(os.path.join(logdir, "epics_ioc.log")).read(), "the soft IOC")
    else:
        time.sleep(10)
    run("forwarder", [os.path.join(b, "forwarder-launch"), "--config-topic", f"{brokers}/{config}",
                      "--status-topic", f"{brokers}/{status}", "--output-broker", brokers,
                      "--pv-update-period", str(UPDATE_PERIOD_MS), "--service-id", f"twin-{instrument}",
                      "--verbosity", "Warning"])
    n = configured(rows, config, status, brokers)
    print(f"  forwarder configured: {n} PVs relayed", flush=True)
    return procs


def configured(rows, config_topic, status_topic, brokers="127.0.0.1:9092", timeout=120):
    """Sends the configuration until the forwarder reports the PVs it relays (status x5f2 messages, every few s).
    The forwarder reads its configuration topic from its end once it has joined its consumer group: a configuration
    sent before that is not seen. Returns the number of PVs it relays."""
    from confluent_kafka import Consumer
    from streaming_data_types.status_x5f2 import deserialise_x5f2
    c = Consumer({"bootstrap.servers": brokers, "group.id": f"twin-epics-{os.getpid()}",
                  "auto.offset.reset": "latest", "enable.auto.commit": False})
    c.subscribe([status_topic])
    t0, sent = time.time(), 0.0
    try:
        while time.time() - t0 < timeout:
            if time.time() - sent > 10:
                configure(rows, config_topic, brokers)
                sent = time.time()
            m = c.poll(1.0)
            if m is None or m.error():
                continue
            try:
                streams = json.loads(deserialise_x5f2(m.value()).status_json).get("streams", [])
            except Exception:                    # noqa: BLE001  (another message on the status topic)
                continue
            if streams:
                return len(streams)
    finally:
        c.close()
    raise RuntimeError(f"the forwarder relays no PV after {timeout} s (see its log)")


def configure(rows, config_topic, brokers="127.0.0.1:9092"):
    """Tells the forwarder which PVs to relay (as the ESS configuration tool does): fc00, REPLACE."""
    from confluent_kafka import Producer
    from streaming_data_types.fbschemas.forwarder_config_update_fc00.UpdateType import UpdateType
    from streaming_data_types.forwarder_config_update_fc00 import Protocol, StreamInfo, serialise_fc00
    seen, streams = set(), []
    for r in rows:
        if (r["pv"], r["topic"]) in seen:
            continue
        seen.add((r["pv"], r["topic"]))
        streams.append(StreamInfo(r["pv"], "f144", r["topic"], Protocol.Protocol.PVA, 1))
    p = Producer({"bootstrap.servers": brokers})
    p.produce(config_topic, serialise_fc00(UpdateType.REPLACE, streams))
    p.flush(30)
    return len(streams)


if __name__ == "__main__":
    ok, what = available()
    print(("available: " if ok else "not available: ") + what)
    sys.exit(0 if ok else 1)
