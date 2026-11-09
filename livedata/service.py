"""ESS live data reduction (esslivedata, scipp) as a service next to the twin (in the app container;
nicos/start_nicos.py --livedata starts it). As at ESS: the backend services read the events and device values on the
real topics (<instrument>_detector, _beam_monitor, _choppers...), reduce them live and publish the results on
<instrument>_livedata_data; the dashboard (a web page, port 5009) shows them and starts the reductions; NICOS can read
the "derived devices" (total counts, images) on <instrument>_livedata_nicos_data.

    available()               (True, version) if esslivedata is installed here, else (False, why)
    start(instrument, logdir) starts the services and the dashboard; returns the list of Popen
    start_workflow(...)       starts a reduction (a "workflow"), as the dashboard does (used by the tests)

The twin feeds it the events of each count with the real pixel numbers and source names (twin_server.py, TWIN_LIVEDATA=1:
the same messages as for the ESS file-writer). esslivedata runs in its own conda environment ("livedata", Python 3.13,
release fixed in the Containerfile: it is not on PyPI); the twin only starts its programs (python -m ...).
"""
import json
import os
import shutil
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICES = ("detector_data", "monitor_data", "data_reduction", "timeseries")
DASHBOARD_PORT = 5009
# topics of esslivedata (scripts/setup-kafka-topics.sh of esslivedata): created before the services start
LIVEDATA_TOPICS = ("livedata_commands", "livedata_responses", "livedata_heartbeat", "livedata_data",
                   "livedata_roi", "livedata_context", "livedata_nicos_data")
DATA_TOPICS = ("detector", "beam_monitor", "motion")


def python():
    """The Python of the "livedata" environment (TWIN_LIVEDATA_PYTHON, else the conda environment of the image)."""
    if os.environ.get("TWIN_LIVEDATA_PYTHON"):
        return os.environ["TWIN_LIVEDATA_PYTHON"]
    for root in (os.environ.get("MAMBA_ROOT_PREFIX", "/opt/conda"), os.path.expanduser("~/miniforge3")):
        exe = os.path.join(root, "envs", "livedata", "bin", "python")
        if os.path.isfile(exe):
            return exe
    return shutil.which("python3") or sys.executable


def _env(brokers):
    # the "docker" Kafka configuration of esslivedata reads the broker from the environment (the default "dev" one
    # says localhost, which can resolve to ::1 first)
    return dict(os.environ, LIVEDATA_ENV="docker", KAFKA_BOOTSTRAP_SERVERS=brokers, KAFKA_SECURITY_PROTOCOL="PLAINTEXT",
                LIVEDATA_CONFIG_DIR=os.path.join(_run_root(), "livedata", "config"),
                SCIPP_DATA_DIR=os.path.join(_run_root(), "livedata", "cache"))


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def available():
    """(True, version) if esslivedata can run here, else (False, the reason)."""
    exe = python()
    try:
        r = subprocess.run([exe, "-c", "import ess.livedata as m; print(m.__version__)"], capture_output=True,
                           text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"esslivedata does not run: {e}"
    if r.returncode != 0:
        return False, f"esslivedata not installed ({exe}): {(r.stderr or r.stdout).strip()[-200:]}"
    return True, f"esslivedata {r.stdout.strip()}"


def topics(instrument):
    return [f"{instrument}_{t}" for t in LIVEDATA_TOPICS + DATA_TOPICS]


def start(instrument, logdir=None, brokers="127.0.0.1:9092", dashboard=True):
    """Starts the backend services of esslivedata for `instrument` (production topics, as at ESS) and its dashboard
    (http://127.0.0.1:5009); their topics are created first. Returns [(name, Popen)]."""
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "filewriter"))
    import twin_filewriter as tf
    tf.ensure_topics(brokers, topics(instrument))
    exe, env = python(), _env(brokers)
    for k in ("LIVEDATA_CONFIG_DIR", "SCIPP_DATA_DIR"):
        os.makedirs(env[k], exist_ok=True)
    procs = []
    runs = [(s, [exe, "-m", f"ess.livedata.services.{s}", "--instrument", instrument]) for s in SERVICES]
    if dashboard:
        runs.append(("dashboard", [exe, "-m", "ess.livedata.dashboard.reduction", "--instrument", instrument,
                                   "--port", str(DASHBOARD_PORT), "--theme", "nicos", "--no-fetch-announcements"]))
    for name, cmd in runs:
        out = open(os.path.join(logdir, f"livedata_{name}.log"), "w") if logdir else subprocess.DEVNULL
        procs.append((name, subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT)))
    return procs


def start_workflow(instrument, workflow, source, brokers="127.0.0.1:9092", version=1, params=None, aux=None):
    """Starts a reduction as the dashboard does: a WorkflowConfig (JSON) on <instrument>_livedata_commands.
    workflow: its name in esslivedata (e.g. "odin_detector_xy"); source: e.g. "timepix3". Returns the job number."""
    from confluent_kafka import Producer
    job = str(uuid.uuid4())
    cmd = {"kind": "workflow_config", "identifier": {"instrument": instrument, "name": workflow, "version": version},
           "job_id": {"source_name": source, "job_number": job}, "params": params or {},
           "aux_source_names": aux or {}}
    p = Producer({"bootstrap.servers": brokers})
    p.produce(f"{instrument}_livedata_commands", json.dumps(cmd).encode())      # no key, as the dashboard
    p.flush(30)
    return job


def nicos_devices(instrument, brokers="127.0.0.1:9092", timeout=60, until=None):
    """The latest value of each derived device esslivedata publishes for NICOS ({device name: {variable name: da00
    Variable}}; the value is in "signal"), read for up to `timeout` s from the start of
    <instrument>_livedata_nicos_data. until(out): stop as soon as it is true."""
    import time
    from confluent_kafka import Consumer, TopicPartition
    from streaming_data_types.dataarray_da00 import deserialise_da00
    c = Consumer({"bootstrap.servers": brokers, "group.id": f"twin-{uuid.uuid4()}", "enable.auto.commit": False})
    c.assign([TopicPartition(f"{instrument}_livedata_nicos_data", 0, 0)])
    out, t_end = {}, time.time() + timeout
    while time.time() < t_end:
        m = c.poll(1)
        if m is None or m.error():
            continue
        try:
            d = deserialise_da00(m.value())
        except Exception:                               # noqa: BLE001
            continue
        out[d.source_name] = {v.name: v for v in d.data}
        if until is not None and until(out):
            break
    c.close()
    return out


if __name__ == "__main__":
    ok, what = available()
    print(("available: " if ok else "not available: ") + what)
    sys.exit(0 if ok else 1)
