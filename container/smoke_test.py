"""Smoke test of the container (run by GitHub Actions after each build): `bash container/start.sh test`.

1. tools: mcrun, mpiexec, h5repack in the twin environment; NICOS importable in its own environment;
2. a short measurement with the virtual ODIN (WFM δ = 0.10 m, the smallest upstream part, downloaded from the
   release; hybrid mode): dark, open beam, iron plate; reduction with essimaging; transmission of the plate compared
   with NCrystal (Beer–Lambert, 5 mm of α-iron) between 2.2 and 3.8 Å (below the first Bragg edge, 4.05 Å);
3. a LoKI measurement (upstream part downloaded from the release, downstream McStas part computed): silica spheres,
   10 min; Guinier fit compared with the exact radius of gyration and I(0);
4. live data (if Kafka is installed: KAFKA_HOME): Kafka broker and just-bin-it started, the iron-plate
   measurement streamed in real time (ev44), the histograms of just-bin-it must hold all its neutrons;
5. NICOS services started headless with the launcher (twin server, cache, poller, daemon), then stopped.
Exit code 0 if everything works.
"""
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TWIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TWIN, "odin"))
FRONT = "wfm_delta0.10_N2e+08"
ok = True


def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    ok &= bool(cond)


def step(title):
    print(f"\n=== {title}", flush=True)


step("tools")
for exe in ("mcrun", "mpiexec", "h5repack"):
    check(shutil.which(exe), f"{exe} found: {shutil.which(exe)}")
NO_NICOS = "--no-nicos" in sys.argv                    # python container/smoke_test.py --no-nicos: twin only
conda_root = os.environ.get("CONDA_ROOT", os.path.dirname(os.path.dirname(sys.prefix)))
nicos_py = os.path.join(conda_root, "envs", "nicos", "python.exe" if os.name == "nt" else os.path.join("bin", "python"))
r = subprocess.CompletedProcess([], 0, "skipped (--no-nicos)", "") if NO_NICOS else subprocess.run([nicos_py, "-c", "import nicos, nicospyctl, numpy; print(nicos.__version__, numpy.__version__)"],
                   cwd=os.environ.get("NICOS_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "nicos_src")),
                   capture_output=True, text=True)
check(r.returncode == 0, f"NICOS environment: {r.stdout.strip() or r.stderr.strip()[-300:]}")

step("upstream part")
r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_fronts.py"), FRONT])
check(r.returncode == 0, f"upstream part {FRONT} downloaded")

step("measurement with the virtual ODIN (hybrid mode)")
t0 = time.time()
import numpy as np                                    # noqa: E402
import NCrystal as NC                                 # noqa: E402
import odin_virtual as ov                             # noqa: E402
import odin_reduction as red                          # noqa: E402
odin = ov.VirtualOdin(session="ci_smoke_test", mpi=int(os.environ.get("TWIN_MPI", "4")))
odin.move(choppers="wfm", wfm_delta=0.10)
dark = odin.count(5, title="dark")
odin.move(shutter="open", stage_x=0.5)
ob = odin.count(20, title="open beam")
odin.move(stage_x=0.0)
smp = odin.count(20, title="iron plate")
print(f"three counts in {time.time() - t0:.0f} s (including the first McStas compilation and open-beam simulation)")
out = red.reduce(smp, ob, dark=dark)
spec = out["spectrum"]
edges = spec.coords["wavelength"].values
lam = 0.5 * (edges[1:] + edges[:-1])
band = (lam > 2.2) & (lam < 3.8)
T = spec.values[band]
m = NC.load("Fe_sg229_Iron-alpha.ncmat")
sigma = (m.scatter.xsect(wl=lam[band]) + m.absorption.xsect(wl=lam[band])) * m.info.getNumberDensity()   # cm^-1
T_nc = np.exp(-sigma * 0.5)
dev = np.mean(T) - np.mean(T_nc)
print(f"transmission 2.2–3.8 Å: measured {np.mean(T):.3f}, NCrystal {np.mean(T_nc):.3f}")
check(abs(dev) < 0.03, f"iron plate transmission agrees with NCrystal (difference {dev:+.3f})")

step("measurement with the virtual LoKI")
r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_fronts.py"), "--instrument", "loki"])
check(r.returncode == 0, "LoKI upstream part downloaded")
t0 = time.time()
sys.path.insert(0, os.path.join(TWIN, "loki"))
import easy_case                                      # noqa: E402
res = easy_case.main(plot=False, session="ci_loki", mpi=int(os.environ.get("TWIN_MPI", "4")))
print(f"LoKI measurement in {time.time() - t0:.0f} s (including the McStas compilation and the downstream part)")
check(abs(res["rg"] / res["rg_true"] - 1) < 0.05, f"radius of gyration {res['rg']:.1f} Å within 5 % of {res['rg_true']:.1f} Å")
check(abs(res["i0"] / res["i0_true"] - 1) < 0.05, f"I(0) {res['i0']:.3f} cm⁻¹ within 5 % of {res['i0_true']:.3f} cm⁻¹")

step("live data: Kafka broker, just-bin-it, stream of an ODIN measurement")
LIVE_PROCS = []
if "--no-live" in sys.argv or not os.path.isdir(os.environ.get("KAFKA_HOME", "/nonexistent")):
    print("skipped (--no-live or no Kafka: KAFKA_HOME)")
else:
    import json
    import threading
    from confluent_kafka import Consumer, Producer, TopicPartition
    from streaming_data_types import deserialise_hs01
    sys.path.insert(0, os.path.join(TWIN, "kafka"))
    import streamer
    LIVE_PROCS.append(subprocess.Popen([sys.executable, os.path.join(TWIN, "kafka", "start_kafka.py")]))
    t0 = time.time()
    while time.time() - t0 < 120 and subprocess.run([sys.executable, os.path.join(TWIN, "kafka", "start_kafka.py"),
                                                      "--check"], capture_output=True).returncode:
        time.sleep(2)
    jbi_home = os.environ.get("JBI_HOME", "")
    LIVE_PROCS.append(subprocess.Popen([sys.executable, "-m", "just_bin_it.cli", "-b", "127.0.0.1:9092", "-t",
                                        "test_jbi_commands", "-hb", "test_jbi_heartbeat", "-rt", "test_jbi_responses"],
                                       cwd=jbi_home, env=dict(os.environ, PYTHONPATH=jbi_home)))
    time.sleep(10)
    pulses = ov.VirtualOdin.stream_pulses(smp)          # the iron-plate measurement above (20 s)
    n_events = sum(len(p[2]) for p in pulses)
    resp = Consumer({"bootstrap.servers": "127.0.0.1:9092", "group.id": "smoke", "auto.offset.reset": "earliest"})
    resp.subscribe(["test_jbi_responses"])
    hists = Consumer({"bootstrap.servers": "127.0.0.1:9092", "group.id": "smoke-h", "auto.offset.reset": "earliest",
                      "fetch.message.max.bytes": 16_000_000})
    hists.subscribe(["test_visualisation"])
    config = {"cmd": "config", "msg_id": "smoke-1", "input_schema": "ev44", "output_schema": "hs01", "interval": 30,
              "histograms": [
                  {"type": "dethist", "data_brokers": ["127.0.0.1:9092"], "data_topics": ["odin_detector"],
                   "det_range": [1, 16385], "width": 128, "height": 128, "topic": "test_visualisation", "id": "image"},
                  {"type": "hist1d", "data_brokers": ["127.0.0.1:9092"], "data_topics": ["odin_detector"],
                   "tof_range": [0, 71428571], "num_bins": 300, "topic": "test_visualisation", "id": "tof"}]}
    prod = Producer({"bootstrap.servers": "127.0.0.1:9092"})
    acked = False
    for attempt in range(6):                         # just-bin-it may still be starting: resend until acknowledged
        prod.produce("test_jbi_commands", json.dumps(config).encode()); prod.flush(10)
        t1 = time.time()
        while time.time() - t1 < 10 and not acked:
            m = resp.poll(1.0)
            if m is not None and not m.error():
                r = json.loads(m.value())
                acked = r.get("msg_id") == "smoke-1" and r.get("response") == "ACK"
        if acked:
            break
    check(acked, "just-bin-it acknowledged the histogram configuration")
    sent = streamer.Streamer("127.0.0.1:9092", topic="odin_detector", source="odin_detector").stream(pulses)
    print(f"streamed {sent} events in {len(pulses)} pulses")
    last, t1 = {}, time.time()
    while time.time() - t1 < 60:                     # latest histograms (just-bin-it publishes every 0.5 s)
        m = hists.poll(1.0)
        if m is None or m.error():
            continue
        h = deserialise_hs01(m.value())
        hid = json.loads(h["info"]).get("id", "")
        last[hid] = (float(np.sum(h["data"])), json.loads(h["info"]).get("state"))
        if all(last.get(k, (0, ""))[0] >= sent for k in ("image", "tof")):
            break
    print("histogram totals:", last)
    check(sent == n_events and last.get("image", (0,))[0] == sent and last.get("tof", (0,))[0] == sent,
          f"live histograms of just-bin-it hold all the {n_events} streamed neutrons (image and arrival times)")
    for p in reversed(LIVE_PROCS):
        p.terminate()

step("NICOS services (headless)")
if NO_NICOS:
    print("skipped (--no-nicos)")
    sys.exit(0 if ok else 1)
p = subprocess.Popen([sys.executable, os.path.join(TWIN, "nicos", "start_nicos.py"), "--instrument", "odin", "--no-gui", "--background",
                      "--session", "ci_nicos"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
ready, lines, t0 = False, [], time.time()
while time.time() - t0 < 300:
    line = p.stdout.readline()
    if not line:
        break
    lines.append(line.rstrip())
    print("  " + line.rstrip(), flush=True)
    if "services ready" in line:
        ready = True
        break
check(ready, "NICOS cache, poller and daemon started with the twin server")
if ready:   # a measurement driven through NICOS, as a student would do (login student / student)
    r = subprocess.run([nicos_py, os.path.join(TWIN, "nicos", "run_nicos_script.py"), "-c",
                        "NewExperiment(1234, 'smoke test')\n"
                        "move(choppers, 'wfm', wfm_delta, 0.1); move(shutter, 'open', stage_x, 500)\n"
                        "with nexusfile_open('open beam via NICOS'):\n"
                        "    count(t=5)\n"],
                       capture_output=True, text=True, timeout=900)
    print("  " + r.stdout.replace("\n", "\n  ") + r.stderr[-2000:], flush=True)
    check(r.returncode == 0 and "file written" in r.stdout, "measurement driven through NICOS (file written)")
if os.name == "nt":                                  # Windows: no SIGINT; stop the whole process tree
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
else:
    p.send_signal(signal.SIGINT)
try:
    p.wait(60)
except subprocess.TimeoutExpired:
    p.kill()
logs = os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "nicos")
if not ready and os.path.isdir(logs):
    for f in sorted(os.listdir(logs)):
        if f.endswith(".log"):
            print(f"--- {f}\n" + open(os.path.join(logs, f), errors="replace").read()[-3000:])

print("\nALL PASSED" if ok else "\nSOME CHECKS FAILED")
sys.exit(0 if ok else 1)
