"""Smoke test of the container (run by GitHub Actions after each build): `bash container/start.sh test`.

1. tools: mcrun, mpiexec, h5repack in the twin environment; NICOS importable in its own environment;
2. a short measurement with the virtual ODIN (WFM δ = 0.10 m, the smallest upstream part, downloaded from the
   release; hybrid mode): dark, open beam, iron plate; reduction with essimaging; transmission of the plate compared
   with NCrystal (Beer–Lambert, 5 mm of α-iron) between 2.2 and 3.8 Å (below the first Bragg edge, 4.05 Å);
3. a LoKI measurement (upstream part downloaded from the release, downstream McStas part computed): silica spheres,
   10 min; Guinier fit compared with the exact radius of gyration and I(0);
4. live data (if Kafka is installed: KAFKA_HOME): Kafka broker and just-bin-it started, the iron-plate
   measurement streamed in real time (ev44), the histograms of just-bin-it must hold all its neutrons;
5. NICOS services started headless with the launcher (twin server, cache, poller, daemon), then stopped;
6. the ESS file-writer (Linux x86-64; --no-filewriter to skip): NICOS with --filewriter, jobs of ODIN (dark, open
   beam, iron plate) and LoKI (empty beam, solvent, silica spheres) written by kafka-to-nexus and compared with the
   twin's own files, then reduced (essimaging, esssans) from both: the same results.
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

step("LoKI: empty beam, solvent and sample, NeXus event files reduced with esssans, sasmodels fit")
r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_fronts.py"), "--instrument", "loki"])
check(r.returncode == 0, "LoKI upstream part downloaded")
t0 = time.time()
sys.path.insert(0, os.path.join(TWIN, "loki"))
import easy_case                                      # noqa: E402
res = easy_case.main(plot=False, session="ci_loki", mpi=int(os.environ.get("TWIN_MPI", "4")))
print(f"LoKI measurement in {time.time() - t0:.0f} s (including the McStas compilation and the downstream part)")
# the Guinier fit has a statistical uncertainty (drg, about 1.2 Å for this count): 5 % or 3 standard deviations
tol = max(0.05 * res["rg_true"], 3 * res["drg"])
check(abs(res["rg"] - res["rg_true"]) < tol,
      f"radius of gyration {res['rg']:.1f} ± {res['drg']:.1f} Å within {tol:.1f} Å of {res['rg_true']:.1f} Å "
      f"(5 % or 3 standard deviations of the fit)")
check(abs(res["radius"] / 50.0 - 1) < 0.03, f"sphere radius (sasmodels) {res['radius']:.1f} Å within 3 % of 50 Å")
check(abs(res["phi"] / 0.01 - 1) < 0.08, f"volume fraction (absolute units) {100 * res['phi']:.2f} % within 8 % of 1 %")

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
    sys.path.insert(0, os.path.join(TWIN, "kafka"))
    import start_kafka
    start_kafka.create_topics(["odin_detector", "test_jbi_commands", "test_jbi_heartbeat", "test_jbi_responses",
                               "test_visualisation"])
    jbi_home = os.environ.get("JBI_HOME", "")
    LIVE_PROCS.append(subprocess.Popen([sys.executable, "-c", "from just_bin_it.cli import main; main()", "-b", "127.0.0.1:9092", "-t",
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
    now_ms = int(time.time() * 1000)
    config = {"cmd": "config", "msg_id": "smoke-1", "input_schema": "ev44", "output_schema": "hs01",
              "start": now_ms, "stop": now_ms + 60_000,
              "histograms": [
                  {"type": "dethist", "data_brokers": ["127.0.0.1:9092"], "data_topics": ["odin_detector"],
                   "det_range": [1, 16385], "width": 128, "height": 128, "topic": "test_visualisation", "id": "image"},
                  {"type": "hist1d", "data_brokers": ["127.0.0.1:9092"], "data_topics": ["odin_detector"],
                   "tof_range": [0, 71428571], "num_bins": 300, "topic": "test_visualisation", "id": "tof"}]}
    prod = Producer({"bootstrap.servers": "127.0.0.1:9092"})
    det_stream = streamer.Streamer("127.0.0.1:9092", topic="odin_detector", source="odin_detector")
    det_stream.empty_pulse()                         # a detector stream exists before the histogramming starts
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
    sent = det_stream.stream(pulses)
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


def show_logs():
    if os.path.isdir(logs):
        for f in sorted(os.listdir(logs)):
            if f.endswith(".log"):
                print(f"--- {f}\n" + open(os.path.join(logs, f), errors="replace").read()[-3000:])


if not ready:
    show_logs()


def nicos_session(instrument, session, script, extra=(), before=None, after=None, timeout=3600):
    """Starts NICOS for `instrument` with the launcher (headless), runs `script`, stops it; returns (ready, output).
    before(), after(): called once the services are ready, before and after the script (while they still run).
    timeout [s]: the script is stopped after it (its output is still shown)."""
    import socket
    t0 = time.time()                                 # the services of the previous session are gone (their ports)
    while time.time() - t0 < 120:
        busy = []
        for port in (8765, 14869, 1301):
            with socket.socket() as so:
                so.settimeout(1)
                if so.connect_ex(("127.0.0.1", port)) == 0:
                    busy.append(port)
        if not busy:
            break
        time.sleep(2)
    p = subprocess.Popen([sys.executable, os.path.join(TWIN, "nicos", "start_nicos.py"), "--instrument", instrument,
                          "--no-gui", "--background", "--session", session, *extra],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ready, t0, out = False, time.time(), ""
    while time.time() - t0 < 300:
        line = p.stdout.readline()
        if not line:
            break
        print("  " + line.rstrip(), flush=True)
        if "services ready" in line:
            ready = "ESS file-writer" in line if "--filewriter" in extra else True
            break
    if ready:
        if before is not None:
            before()
        r = subprocess.run([nicos_py, os.path.join(TWIN, "nicos", "run_nicos_script.py"), "-c", script,
                            "--timeout", str(timeout)], capture_output=True, text=True, timeout=timeout + 300)
        out = r.stdout + r.stderr[-2000:]
        print("  " + out.replace("\n", "\n  "), flush=True)
        if after is not None:
            after()
    p.send_signal(signal.SIGINT)
    try:
        p.wait(60)
    except subprocess.TimeoutExpired:
        p.kill()
    if not ready:
        show_logs()
    return ready, out


def job_files(instrument, proposal):
    """The files of the file-writer (one per job) and of the twin (one per count) of a proposal, in the order
    written."""
    import glob
    raw = glob.glob(os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "**", str(proposal), "raw"), recursive=True)
    if not raw:
        return [], []
    return (sorted(glob.glob(os.path.join(raw[0], f"{instrument}_job_*.hdf"))),
            sorted(glob.glob(os.path.join(raw[0], f"{instrument}_0*.nxs"))))


def same(a, b):
    return (np.array_equal(a.values, b.values, equal_nan=True)
            and (a.variances is None or np.array_equal(a.variances, b.variances, equal_nan=True)))


def odin_mismatch(fw, tw, a, b):
    """Where the reductions of the file-writer's and the twin's ODIN files differ (printed when they do)."""
    for what in ("spectrum", "image"):
        x, y = a[what].values, b[what].values
        d = np.abs(x - y)[np.isfinite(x) & np.isfinite(y)]
        print(f"  {what}: {int((d > 0).sum())} of {x.size} bins differ, by up to {d.max() if d.size else 0:.3g}; "
              f"non-finite bins {int((~np.isfinite(x)).sum())} / {int((~np.isfinite(y)).sum())}")
    for f, t in zip(fw, tw):
        kf, kt = red._chopper_fingerprint(f), red._chopper_fingerprint(t)
        print(f"  {os.path.basename(f)} / {os.path.basename(t)}: chopper fingerprints "
              + ("same" if kf == kt else f"DIFFER: {[(p, q) for p, q in zip(kf, kt) if p != q]}"))
        ea, eb = red.events(f), red.events(t)
        na, nb = ea.bins.size().values.ravel(), eb.bins.size().values.ravel()
        la = np.sort(np.nan_to_num(ea.bins.concat().value.coords["wavelength"].values, nan=-1))
        lb = np.sort(np.nan_to_num(eb.bins.concat().value.coords["wavelength"].values, nan=-1))
        msg = "same" if len(la) == len(lb) and np.array_equal(la, lb) else (
            f"{int((la != lb).sum())} of {len(la)} differ, by up to {np.abs(la - lb).max():.3g} A"
            if len(la) == len(lb) else f"{len(la)} / {len(lb)} events")
        print(f"    events per pixel {'same' if np.array_equal(na, nb) else 'DIFFERENT'}; wavelengths {msg}; "
              f"duration {red.duration(f)} / {red.duration(t)}; charge {red.proton_charge(f)} / {red.proton_charge(t)}")


step("ESS file-writer: NICOS jobs written by kafka-to-nexus, then reduced as the twin's own files (ODIN, LoKI)")
sys.path.insert(0, os.path.join(TWIN, "filewriter"))
import service as fw_service                          # noqa: E402
usable, what = fw_service.available()
if "--no-filewriter" in sys.argv or not usable:
    print("skipped: " + ("--no-filewriter" if usable else what))
else:
    print(f"kafka-to-nexus: {what}")
    # ODIN: dark, open beam, iron plate, one job each (as at ESS: one file per job)
    ready, out = nicos_session("odin", "ci_fw_odin",
                               "NewExperiment(1235, 'file-writer test')\n"
                               "move(choppers, 'wfm', wfm_delta, 0.1); move(shutter, 'closed')\n"
                               "with nexusfile_open('dark'):\n    count(t=5)\n"
                               "move(shutter, 'open', stage_x, 500)\n"
                               "with nexusfile_open('open beam'):\n    count(t=20)\n"
                               "move(stage_x, 0)\n"
                               "with nexusfile_open('iron plate'):\n    count(t=20)\n", ["--filewriter"])
    check(ready, "NICOS started with the ESS file-writer (ODIN)")
    check(out.count("same data") == 3, f"ODIN: 3 jobs written by the file-writer, same data as the twin's files "
                                       f"({out.count('same data')} of 3)")
    fw, tw = job_files("odin", 1235)
    if len(fw) == 3 and len(tw) == 3:
        try:
            a = red.reduce(fw[2], fw[1], dark=fw[0])
            b = red.reduce(tw[2], tw[1], dark=tw[0])
            print(f"transmission 2.2-3.8 A from the file-writer's files: {np.nanmean(a['spectrum'].values[band]):.3f} "
                  f"(NCrystal {np.mean(T_nc):.3f}); normalization: file-writer {a['normalization']}, "
                  f"twin {b['normalization']}")
            identical = same(a["spectrum"], b["spectrum"]) and same(a["image"], b["image"])
            if not identical:
                odin_mismatch(fw, tw, a, b)
            check(identical, "ODIN: essimaging gives the same transmission (spectrum and image) from the file-writer's files")
        except Exception as e:                      # noqa: BLE001  (the LoKI part still runs)
            import traceback
            traceback.print_exc()
            check(False, f"ODIN: reduction of the file-writer's files: {type(e).__name__}: {e}")
    else:
        check(False, f"ODIN: files of the jobs ({len(fw)} of the file-writer, {len(tw)} of the twin; 3 expected)")
    # LoKI: empty beam, solvent, sample, one job each, reduced with esssans
    ready, out = nicos_session("loki", "ci_fw_loki",
                               "NewExperiment(1236, 'file-writer test')\n"
                               "move(collimation, '3m', detector_distance, 5.0, heavy_shutter, 'Open', "
                               "fast_shutter, 'Open')\n"
                               "move(sample_holder, 'empty_beam')\n"
                               "with nexusfile_open('empty beam'):\n    count(t=30)\n"
                               "move(sample_holder, 'd2o')\n"
                               "with nexusfile_open('solvent'):\n    count(t=60)\n"
                               "move(sample_holder, 'silica_spheres')\n"
                               "with nexusfile_open('silica spheres'):\n    count(t=60)\n", ["--filewriter"])
    check(ready, "NICOS started with the ESS file-writer (LoKI)")
    check(out.count("same data") == 3, f"LoKI: 3 jobs written by the file-writer, same data as the twin's files "
                                       f"({out.count('same data')} of 3)")
    fw, tw = job_files("loki", 1236)
    if len(fw) == 3 and len(tw) == 3:
        import loki_reduction as lred
        banks = ["loki_detector_0", "loki_detector_1", "loki_detector_5"]
        try:
            a = lred.reduce(fw[2], background=fw[1], empty_beam=fw[0], banks=banks)
            b = lred.reduce(tw[2], background=tw[1], empty_beam=tw[0], banks=banks)
            check(all(same(a[k], b[k]) for k in banks),
                  "LoKI: esssans gives the same I(Q) (rear, middle and front banks) from the file-writer's files")
        except Exception as e:                      # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(False, f"LoKI: reduction of the file-writer's files: {type(e).__name__}: {e}")
    else:
        check(False, f"LoKI: files of the jobs ({len(fw)} of the file-writer, {len(tw)} of the twin; 3 expected)")

step("ESS live data reduction: esslivedata reduces a count of ODIN live, as at ESS (dashboard, NICOS devices)")
import importlib.util                                  # noqa: E402
_spec = importlib.util.spec_from_file_location("livedata_service", os.path.join(TWIN, "livedata", "service.py"))
ld = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ld)
usable, what = ld.available()
if "--no-livedata" in sys.argv or not usable:
    print("skipped: " + ("--no-livedata" if usable else what))
else:
    print(what)
    LD = {}

    def ld_before():
        import urllib.request
        t0 = time.time()                             # the dashboard (a web page) answers
        while time.time() - t0 < 180 and "dashboard" not in LD:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{ld.DASHBOARD_PORT}/", timeout=5)
                LD["dashboard"] = time.time() - t0
            except Exception:                        # noqa: BLE001
                time.sleep(3)
        time.sleep(20)                               # the backend services subscribe to their topics
        # the image of the Timepix3 detector, started as from the dashboard (NICOS reads its total)
        LD["job"] = ld.start_workflow("odin", "odin_detector_xy", "timepix3")
        time.sleep(15)

    def ld_after():
        import glob
        files = sorted(glob.glob(os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "**", "1237", "raw",
                                              "odin_0*.nxs"), recursive=True))
        n = 0
        if files:
            import h5py
            with h5py.File(files[-1], "r") as f:
                LD["ids"] = f["entry/instrument/timepix3/data/event_id"][()]
                LD["pulses"] = f["entry/instrument/timepix3/data/event_index"][()]
                LD["eto"] = f["entry/instrument/timepix3/data/event_time_offset"][()]
            n = len(LD["ids"])
        LD["events"] = n

        def total(out):
            v = out.get("timepix3_counts_total", {}).get("signal")
            return None if v is None else float(np.asarray(v.data).sum())
        dev = ld.nicos_devices("odin", timeout=180, until=lambda out: n and total(out) == n)
        LD["total"] = total(dev)
        LD["devices"] = sorted(dev)
        img = dev.get("timepix3_image", {}).get("signal")
        LD["image"] = None if img is None else np.asarray(img.values if hasattr(img, "values") else img.data)

    ready, out = nicos_session("odin", "ci_livedata",
                               "NewExperiment(1237, 'live reduction test')\n"
                               "move(choppers, 'wfm', wfm_delta, 0.1); move(shutter, 'open', stage_x, 500)\n"
                               "with nexusfile_open('open beam'):\n    count(t=10)\n",
                               ["--livedata"], before=ld_before, after=ld_after)
    check(ready, "NICOS started with esslivedata (ODIN)")
    check("dashboard" in LD, "esslivedata dashboard answers on port "
                             f"{ld.DASHBOARD_PORT}" + (f" (after {LD['dashboard']:.0f} s)" if "dashboard" in LD else ""))
    print(f"NICOS devices of esslivedata: {LD.get('devices')}; total {LD.get('total')}, events in the file "
          f"{LD.get('events')}")
    check(LD.get("events", 0) > 0 and LD.get("total") == LD.get("events"),
          "esslivedata: the live image of ODIN holds all the neutrons of the count")
    if LD.get("total") != LD.get("events") and "eto" in LD:     # where the missing neutrons may be (diagnosis)
        e, idx = np.asarray(LD["eto"]), np.asarray(LD["pulses"])
        per = np.diff(np.r_[idx, len(e)])
        print(f"  time of flight {e.min()}..{e.max()} ns ({np.sum(e <= 0)} at 0 or below, "
              f"{np.sum(e >= 71_430_000)} at 71.43 ms or above); {len(per)} pulses, neutrons in the first "
              f"{per[:2].tolist()} and the last {per[-3:].tolist()}")
    if not (LD.get("total") == LD.get("events")):
        # where the missing neutrons are: the live image (512 x 512) against the same image made from the file's
        # events (ids laid out as x * 4096 + y from the first id, 8 x 8 pixels per cell), for a first id of 0 or 1
        ids, img = LD.get("ids"), LD.get("image")
        if ids is not None and img is not None and img.size == 512 * 512:
            img = img.reshape(512, 512)
            for first in (0, 1):
                x, y = np.divmod(ids.astype(np.int64) - first, 4096)
                keep = (x >= 0) & (x < 4096)
                mine = np.zeros((512, 512))
                np.add.at(mine, (x[keep] // 8, y[keep] // 8), 1)
                for name, a in (("as is", img), ("transposed", img.T)):
                    d = np.argwhere(mine != a)
                    print(f"first id {first}, live image {name}: {len(d)} cells differ, {(~keep).sum()} ids outside; "
                          f"cells {[(int(i), int(j), mine[i, j], a[i, j]) for i, j in d[:5]]}")
        if ids is not None:
            print(f"event ids: min {ids.min()} max {ids.max()}; arrival times: min {LD['eto'].min()} max "
                  f"{LD['eto'].max()} ns; pulses {len(LD['pulses'])}, events in the first and last pulses: "
                  f"{int(LD['pulses'][1] - LD['pulses'][0]) if len(LD['pulses']) > 1 else '?'}, "
                  f"{int(len(ids) - LD['pulses'][-1])}")
        for name in ("detector_data", "dashboard"):
            path = os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "nicos", f"livedata_{name}.log")
            if os.path.isfile(path):
                print(f"--- {path} (end)\n" + open(path, errors="replace").read()[-4000:])

step("EPICS layer: the devices of ODIN as EPICS PVs (soft IOC), relayed by the ESS forwarder to the file-writer")
_spec = importlib.util.spec_from_file_location("epics_service", os.path.join(TWIN, "epics", "service.py"))
ep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep)
ep_usable, ep_what = ep.available()
if fw_service.available()[0] and "--no-epics" not in sys.argv:
    # where the file-writer is (Intel/AMD), the forwarder must be too: its absence is a failure, not a skip
    check(ep_usable, f"ESS forwarder installed ({ep_what})")
if "--no-epics" in sys.argv or not ep_usable or not fw_service.available()[0]:
    print("skipped: " + ("--no-epics" if "--no-epics" in sys.argv else ep_what if not ep_usable
                         else "no ESS file-writer here"))
else:
    print(ep_what)
    ready, out = nicos_session("odin", "ci_epics",
                               "NewExperiment(1238, 'EPICS test')\n"
                               "print('stage_x class: %s %s' % (type(stage_x).__name__, stage_x.motorpv))\n"
                               "move(choppers, 'wfm', wfm_delta, 0.1); move(shutter, 'open', stage_x, 500)\n"
                               "print('stage_x read: %s %s %s' % (stage_x.read(0), stage_x.unit, stage_x.status(0)))\n"
                               "with nexusfile_open('open beam'):\n    count(t=10)\n", ["--filewriter", "--epics"])
    check(ready, "NICOS started with the EPICS layer and the ESS file-writer (ODIN)")
    check("stage_x class: EpicsMotor ODIN-SpSt1:MC-LinY-01:Mtr" in out,
          "EPICS: NICOS drives the sample stage with the motor class of ESS (EpicsMotor, its real motor record)")
    check("stage_x read: 500.0 mm" in out, "EPICS: the motor record reads back the position set in NICOS (500 mm)")
    check(out.count("same data") == 1, "EPICS: the job written by the file-writer has the same data as the twin's file, "
                                       "device values relayed by the ESS forwarder")
    fw, tw = job_files("odin", 1238)
    if fw and tw:
        import h5py
        with h5py.File(fw[-1], "r") as a, h5py.File(tw[-1], "r") as b:
            p = "entry/instrument/spst1_lin_x/value/value"          # the sample stage, moved to 500 mm
            fa, fb = a[p][()], b[p][()]
        print(f"sample stage x: file-writer {fa[-3:]}, twin {fb[-3:]}")
        check(len(fa) > 0 and len(fb) > 0 and float(fa[-1]) == float(fb[-1]),
              "EPICS: a setting of the twin (sample stage) reached the file-writer through its PV and the forwarder")
    else:
        check(False, f"EPICS: files of the job ({len(fw)} of the file-writer, {len(tw)} of the twin)")
    for name in ("epics_ioc", "forwarder"):
        path = os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "nicos", f"{name}.log")
        if os.path.isfile(path):
            print(f"--- {path} (end)\n" + open(path, errors="replace").read()[-2500:])

step("Event Formation Unit: the twin sends the raw readout of ODIN's camera, the EFU of ESS makes the neutrons, the "
     "file-writer writes them")
_spec = importlib.util.spec_from_file_location("efu_service", os.path.join(TWIN, "efu", "service.py"))
efu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(efu)
efu_usable, efu_what = efu.available("odin")
if fw_service.available()[0] and "--no-efu" not in sys.argv:
    check(efu_usable, f"ESS Event Formation Unit installed ({efu_what})")   # with the file-writer (Intel/AMD)
if "--no-efu" in sys.argv or not efu_usable or not fw_service.available()[0]:
    print("skipped: " + ("--no-efu" if "--no-efu" in sys.argv else efu_what if not efu_usable
                         else "no ESS file-writer here"))
else:
    sys.path.insert(0, os.path.join(TWIN, "efu"))
    import e2e_test as efu_e2e

    def efu_counters():
        print("  counters of the EFU:\n    " + "\n    ".join(efu_e2e.efu_stats(port=efu.CMD_PORT)), flush=True)
    ready, out = nicos_session("odin", "ci_efu",
                               "NewExperiment(1239, 'EFU test')\n"
                               "move(choppers, 'wfm', wfm_delta, 0.1); move(shutter, 'open', stage_x, 500)\n"
                               "with nexusfile_open('open beam'):\n    count(t=10)\n", ["--filewriter", "--efu"],
                               after=efu_counters)
    check(ready, "NICOS started with the ESS Event Formation Unit and the ESS file-writer (ODIN)")
    line = next((x for x in out.splitlines() if "through the EFU" in x), "")
    print("  " + (line.strip() or "(no comparison of the neutrons through the EFU)"))
    check("through the EFU" in out and out.count("same data") == 1,
          "EFU: the neutrons written by the file-writer are those the EFU makes of the twin's readout "
          "(same pixel and time of flight), the other data the same as the twin's file")
    path = os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "nicos", "efu.log")
    if os.path.isfile(path):
        print(f"--- {path} (end)\n" + open(path, errors="replace").read()[-2500:])

    # LoKI: one EFU per bank (CAEN readout, charge division); every neutron must come back, once
    def loki_counters():
        for b, (_, _, topic, _, cmd) in enumerate(efu.INSTANCES["loki"]):
            print(f"  counters of the EFU of {topic}: " + "; ".join(efu_e2e.efu_stats(
                port=cmd, show=("events.count", "readouts", "errors", "parser", "geometry", "tof"))), flush=True)
    ready, out = nicos_session("loki", "ci_efu_loki",
                               "NewExperiment(1240, 'EFU test')\n"
                               "move(collimation, '3m', detector_distance, 5.0, heavy_shutter, 'Open', "
                               "fast_shutter, 'Open')\n"
                               "move(sample_holder, 'd2o')\n"
                               "with nexusfile_open('D2O'):\n    count(t=30)\n", ["--filewriter", "--efu"],
                               after=loki_counters)
    check(ready, "NICOS started with 9 Event Formation Units (one per bank) and the ESS file-writer (LoKI)")
    lines = [x.strip() for x in out.splitlines() if "through the EFU" in x]
    print("  " + ("\n  ".join(lines) or "(no comparison of the neutrons through the EFU)"))
    check(sum(x.startswith("ok  caen on loki_detector_bank") for x in lines) == 9 and out.count("same data") == 1,
          "EFU: the 9 banks of LoKI in the file-writer's file hold every neutron of the twin's readout, once, "
          "same pixel and time of flight to a tick of the ESS clock; the other data the same as the twin's file")
    if os.path.isfile(path):
        print(f"--- {path} (end)\n" + open(path, errors="replace").read()[-1500:])

step("User office: the Experiment tab queries the teaching proposals (proposal cache of yuos_query, as at ESS)")
ready, out = nicos_session("odin", "ci_proposals",
                           "for _ in range(30):\n"
                           "    if Exp._canQueryProposals() and "
                           "Exp._client.all_proposals(): break\n"
                           "    sleep(1)\n"
                           "r = Exp._queryProposals(kwds={'fed_id': 'student', 'admin': False})\n"
                           "for p in r: printinfo('proposal %s | %s | %s | %s' % (p['proposal'], p['title'], "
                           "[s['name'] for s in p['samples']], [u['facility_user_id'] for u in p['users']]))\n"
                           "NewExperiment(r[0]['proposal'], r[0]['title'], users=r[0]['users'])\n"
                           "Exp.sample.set_samples({i: s for i, s in enumerate(Exp._queryProposals(kwds={'fed_id': 'student', 'admin': False})[0]['samples'])})\n"
                           "printinfo('experiment %s: %s' % (Exp.proposal, Exp.title))\n",
                           ["--proposals"], timeout=600)
check(ready, "NICOS started with the twin's user office (ODIN)")
props = [x.split("proposal ", 1)[1] for x in out.splitlines() if "proposal 1000" in x]
print("  " + "\n  ".join(props))
check(len(props) == 3 and "Iron plate, 5 mm" in out and "experiment 100001: Bragg edges of alpha-iron" in out,
      "user office: the 3 proposals of ODIN for the account student, with their samples; the first one becomes the "
      "experiment, as with Query and Apply in the Experiment tab")
if "experiment 100001" not in out:
    show_logs()

print("\nALL PASSED" if ok else "\nSOME CHECKS FAILED")
sys.exit(0 if ok else 1)
