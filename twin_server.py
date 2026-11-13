"""Digital-twin server: a virtual instrument (e.g. VirtualOdin) in its own process, driven over the network.

Why: on a real instrument, the control station (NICOS) and what it drives are separate processes. Here too: NICOS
cannot live in the McStas environment (it requires numpy < 2; essimaging and scipp use numpy 2). The NICOS devices
(nicos/nicos_twin) send their orders to this server, as the console `twin_console.py` does.

    python twin_server.py --instrument odin [--session NAME] [--port 8765] [--mode hybrid|mcstas]

Instruments: see INSTRUMENTS below (one sub-folder of twin/ per instrument, with a class exposing move, count, scan,
status, devices, log_file, number, folder, mode).

JSON over http://127.0.0.1:<port> (local connections only):
    GET  /status                         -> device state, busy or not, number of the last file
    GET  /devices                        -> description of the devices (unit, limits, choices, help)
    GET  /log                            -> actions of the session
    POST /move   {"device": value, ...}
    POST /folder {"folder": "..."}       -> files (and the student's samples) in this folder
    POST /count  {"t": 10, "title": "...", "image": false, "write": true, "folder": null}
    POST /camera {"t": 2, "title": "...", "folder": null}     (ODIN: integrating camera, one image, no time of flight)
                 -> {"file", "number", "n_counts", ["image": detector image for live displays]}
                 write=false: no file (live image only), as a count outside a file-writing job at ESS;
                 folder: where to write the files (NICOS: the proposal folder), default the session folder
    POST /scan   {"device": ..., "values": [...], "t": 10, "title": "..."}   -> {"files": [...]}
Live data (Kafka, as at ESS; optional): /count with "stream": true replays the neutrons of the measurement to the
Kafka topic <instrument>_detector, pulse by pulse in real time (ev44 messages, kafka/streamer.py), after the file is
written. With "hold": true it first waits for POST /go (NICOS: computed in prepare, streamed from start, so that the
stream and just-bin-it start together); GET /status has "ready": true while it waits. POST /stop ends a stream.
Broker: variable TWIN_KAFKA (default 127.0.0.1:9092).
Device values (Kafka, as the EPICS forwarder of ESS; optional, TWIN_FORWARD=1): the values of all the devices are
published at start and after each /move to the topic <instrument>_devices (f144 messages, kafka/forwarder.py), for the
ESS file-writer.
ESS live data reduction (esslivedata, livedata/service.py; optional, TWIN_LIVEDATA=1): each /count also publishes its
neutrons and device values as the instrument does (the same messages as for the file-writer, below), and lasts the
counting time; esslivedata reduces them live (dashboard http://127.0.0.1:5009).
The ESS file-writer (kafka-to-nexus, filewriter/README.md; optional, Linux):
    POST /filewriter/start {"title", "proposal", "folder"}  -> {"job", "file"}: makes the template of the file-writer
                 (from the real ESS file of the instrument, once), starts a job (pl72 on <instrument>_filewriter_pool,
                 with the settings of the twin in entry/twin), the value of every device published just before (f144: the
                 current settings of the twin, as the EPICS forwarder); then each /count also publishes its neutrons and
                 device values (ev44, f144: topics and sources of the real file), at the times of its pulses, and
                 lasts the counting time (as on the instrument)
    POST /filewriter/stop {}  -> {"file", "error", "twin_files", "differences", "report"}: stops the job, waits for
                 the file, compares it with the twin's own files of the job (filewriter/compare.py)
    The file-writer must see the data folders at the same paths (--hdf-output-prefix /) and the templates in
    TWIN_FW_TEMPLATES (default <TWIN_RUN_ROOT>/filewriter/templates; its --hdf-template-prefix).
One measurement at a time (as on the instrument): a command received during a measurement is refused (code 409,
"instrument busy"), but /status always answers.
"""
import argparse
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# instrument name -> (sub-folder of twin/, module, class)
INSTRUMENTS = {"odin": ("odin", "odin_virtual", "VirtualOdin"),
               "loki": ("loki", "virtual_loki", "VirtualLoki")}

INSTR = None
INSTR_NAME = None
LOCK = threading.Lock()
RUNNING = {"action": None}
READY, GO, STOP = threading.Event(), threading.Event(), threading.Event()     # live streaming (Kafka)
STREAMER = {}
FORWARDER = {}
FW = {}                                             # the ESS file-writer: control, producer, the job running
RAW = {}                                            # the data folder of the proposal (NICOS), as given


def _filewriter_mode():
    """The ESS file-writer writes the data files (TWIN_FILEWRITER=1, start_nicos.py --filewriter or --ess): then, as
    at ESS, the data folder of the proposal (<proposal>/raw) holds only its files; the twin writes its own files of
    each count apart, in <proposal>/.twin (sample_library.truth_folder), to check the file-writer's."""
    return os.environ.get("TWIN_FILEWRITER") == "1"


def _use_folder(folder):
    """The data folder given by NICOS (absolute path): where the twin writes its own files (apart with the
    file-writer)."""
    if not os.path.isabs(folder):
        raise ValueError(f"folder must be an absolute path: {folder}")
    RAW["folder"] = folder.replace(os.sep, "/")
    if _filewriter_mode():
        sys.path.insert(0, HERE)
        import sample_library as sl
        folder = sl.truth_folder(folder)
    INSTR.use_folder(folder)


def _fw():
    sys.path.insert(0, os.path.join(HERE, "filewriter"))
    import twin_filewriter
    return twin_filewriter


def _fw_start(args):
    """Starts a job of the ESS file-writer (POST /filewriter/start)."""
    if FW.get("job"):
        raise ValueError(f"a file-writing job is already running ({FW['file']})")
    tf = _fw()
    brokers = os.environ.get("TWIN_KAFKA", "127.0.0.1:9092")
    if args.get("folder"):
        _use_folder(args["folder"])
    src = INSTR.nexus_template()
    run_root = os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))
    root = os.environ.get("TWIN_FW_TEMPLATES", os.path.join(run_root, "filewriter", "templates"))
    template = os.path.join(root, INSTR_NAME, f"{INSTR_NAME}.hdf")
    if (not os.path.isfile(template) or os.path.getmtime(template) < os.path.getmtime(src)
            or not os.path.isfile(template + tf.FIXED_SUFFIX)):
        tf.make_template(src, template, getattr(INSTR, "nexus_static", None))
    if "control" not in FW:
        FW["control"] = tf.FileWriterControl(brokers, f"{INSTR_NAME}_filewriter")
        FW["producer"] = tf.producer(brokers)
    folder = RAW.get("folder", INSTR.folder)        # the data folder of the proposal: the file-writer's files
    os.makedirs(folder, exist_ok=True)
    n = 1 + sum(1 for f in os.listdir(folder) if f.startswith(f"{INSTR_NAME}_job_") and f.endswith(".hdf"))
    path = f"{folder}/{INSTR_NAME}_job_{n:06d}.hdf"
    sample = INSTR.status().get("sample", "")
    try:
        sample = INSTR.samples()[sample].get("name", sample)
    except Exception:                               # noqa: BLE001
        pass
    start_ns = time.time_ns() + 50_000_000
    settings = INSTR.nexus_logs() if hasattr(INSTR, "nexus_logs") else None
    structure = tf.nexus_structure(src, args.get("title", ""), str(args.get("proposal", "")), str(sample),
                                   # the settings of the twin in entry/twin (LoKI: the configuration its reduction
                                   # needs), as NICOS at ESS writes the values of its devices into the start command
                                   twin=INSTR.twin_settings() if hasattr(INSTR, "twin_settings") else None,
                                   # the fixed logs (not streams), with the current settings of the twin (ODIN: the
                                   # positions of the WFM discs)
                                   fixed=tf.fixed_values(template, settings, start_ns))
    tf.ensure_topics(FW["control"].brokers, tf.structure_topics(structure))
    # the value of every device, already published when the job starts, as by the EPICS forwarder at ESS (the
    # file-writer writes the last value before the start of the job): the current settings of the twin, the other
    # devices from the real file
    # (with the EPICS layer, the forwarder has already sent them: on each change, and again every 5 s)
    snapshot = [] if _epics() else tf.snapshot_messages(src, start_ns - 1_000_000, settings)
    tf.publish(FW["producer"], snapshot + tf.topic_markers(structure, start_ns - 1_000_000))
    job = FW["control"].start(structure, path, INSTR_NAME, start_ns=start_ns)
    FW.update(job=job, file=path, twin_files=[])
    return dict(job=job, file=path)


def _fw_stop():
    """Stops the job, waits for the file, compares it with the twin's files (POST /filewriter/stop)."""
    if not FW.get("job"):
        raise ValueError("no file-writing job is running")
    job, path, twins = FW["job"], FW["file"], FW["twin_files"]
    FW["job"] = None
    FW["control"].stop(job)
    _, error = FW["control"].wait_done(job, timeout=600)
    out = dict(file=path, error=error, twin_files=twins)
    if error is None and twins and os.path.isfile(path):
        import compare
        out["differences"], out["report"] = compare.compare(path, twins, log=lambda *_: None,
                                                            exact_times=not _epics(),
                                                            efu=tf_efu_sources() if _efu() else ())
    return out


def _epics():
    """The EPICS layer is on (epics/service.py, TWIN_EPICS=1): the ESS forwarder relays the device values to Kafka from
    the PVs of the twin; the twin no longer publishes them itself."""
    return os.environ.get("TWIN_EPICS") == "1"


def _efu():
    """The ESS Event Formation Unit is on (efu/service.py, TWIN_EFU=1): the twin sends the raw readout of its detector
    (ODIN's Timepix3 camera, LoKI's banks) to the EFUs, which publish the neutrons; the twin no longer publishes them
    itself."""
    return os.environ.get("TWIN_EFU") == "1"


def tf_efu_sources():
    return _fw().EFU_SOURCES


def _efu_targets():
    """{detector topic: (host, UDP port)} of the EFUs (efu/service.py; TWIN_EFU_HOST, default 127.0.0.1)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("efu_service", os.path.join(HERE, "efu", "service.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.targets(os.environ.get("TWIN_EFU_HOST", "127.0.0.1"))


def _livedata():
    """ESS live data reduction (esslivedata, livedata/service.py) is on: TWIN_LIVEDATA=1 (start_nicos.py --livedata)."""
    return os.environ.get("TWIN_LIVEDATA") == "1"


def _fw_publish(f):
    """The neutrons and device values of the measurement in file f, as the instrument sends them (real topics, sources
    and pixel numbers), for the file-writer and for esslivedata: at the times of its pulses, in a thread (joined
    before /count answers: the count lasts its counting time, as on the instrument)."""
    tf = _fw()
    if "producer" not in FW:
        FW["producer"] = tf.producer(os.environ.get("TWIN_KAFKA", "127.0.0.1:9092"))
    msgs = tf.count_messages(f, devices=not _epics(),
                             efu=_efu_targets() if _efu() else None)
    if _livedata():          # the detectors keep sending after the count: esslivedata then reduces its last pulse
        msgs += tf.tail_messages(f)
    th = threading.Thread(target=tf.publish, args=(FW["producer"], msgs), kwargs=dict(pace=True), daemon=True)
    th.start()
    return th


EPICS = {}


def _epics_values():
    """[{"pv", "topic", "type", "value"}] of every device of the real ESS file of the instrument (its f144 streams; the
    source name is the EPICS PV name), with the current settings of the twin: the PVs the soft IOC serves
    (epics/ioc.py) and the ESS forwarder relays to Kafka. type: "d" (float64), "l" (int64), "i" (int32)."""
    tf = _fw()
    if "table" not in EPICS:                      # the devices of the real file (read once; the values change)
        EPICS["table"] = tf.device_values(INSTR.nexus_template())
    settings = INSTR.nexus_logs() if hasattr(INSTR, "nexus_logs") else {}
    over = {}
    for p, v in settings.items():
        for q in (p, f"{p}/value", f"{p}/target_value"):
            over[q] = v
    kind = {"float64": "d", "float32": "d", "int64": "l", "uint64": "l"}
    out = []
    for path, source, topic, value in EPICS["table"]:
        v = np.asarray(over[path], dtype=value.dtype) if path in over else value
        out.append(dict(pv=source, topic=topic, type=kind.get(value.dtype.name, "i"), value=v.item()))
    return out


def _motor_map():
    """{motor record (e.g. ODIN-SpSt1:MC-LinY-01:Mtr): twin device} for the twin's motors (devices with limits) whose
    position is written in the real file as the readback of an EPICS motor record (<record>.RBV), as at ESS."""
    if "motors" not in EPICS:
        rbv = {path: pv[:-4] for path, pv, _t, _v in EPICS["table"] if pv.endswith(".RBV")}
        out = {}
        for d in INSTR.devices.values():
            if getattr(d, "limits", None) is None or not isinstance(getattr(d, "nexus", None), str):
                continue
            base = rbv.get(f"entry/instrument/{d.nexus}/value")
            if base:
                out[base] = d
        EPICS["motors"] = out
    return EPICS["motors"]


def _to_file(d, v):
    return float(d.to_nexus(v) if d.to_nexus else v)


def _epics_motors():
    """[{record, device, unit, value, low, high, desc}] of the motors (GET /epics/motors): the soft IOC serves the
    fields of an EPICS motor record for each (VAL, RBV, DMOV, HLM, LLM, EGU...), as the IOCs of ESS, so that NICOS drives
    them with the class of ESS (nicos_ess.devices.epics.pva.motor.EpicsMotor). Values in the units of the file (mm)."""
    _epics_values()
    out = []
    for base, d in _motor_map().items():
        scale = _to_file(d, 1.0) - _to_file(d, 0.0)
        unit = "mm" if d.unit == "m" and abs(scale - 1e3) < 1e-9 else d.unit
        lo, hi = sorted((_to_file(d, d.limits[0]), _to_file(d, d.limits[1])))
        out.append(dict(record=base, device=d.name, unit=unit, value=_to_file(d, d.value), low=lo, high=hi,
                        desc=d.help[:40]))
    return out


def _epics_put(args):
    """POST /epics/put {record, value}: a new target written to the VAL field of a motor record (by NICOS, through the
    soft IOC): the twin's device moves there (value in the units of the file, converted back to the twin's)."""
    d = _motor_map()[args["record"]]
    y = float(args["value"])
    a = _to_file(d, 0.0)
    x = (y - a) / (_to_file(d, 1.0) - a)             # the conversions to the file are linear (mm = 1e3 m, deg)
    INSTR.move(**{d.name: x})
    _forward()
    return dict(device=d.name, value=x, file_value=_to_file(d, d.value))


def _forward(only_changes=True):
    """Publishes the values of the devices (f144) if TWIN_FORWARD=1; never stops the twin if Kafka is not there."""
    if os.environ.get("TWIN_FORWARD") != "1":
        return 0
    try:
        if "f" not in FORWARDER:
            sys.path.insert(0, os.path.join(HERE, "kafka"))
            import forwarder
            if not forwarder.available():
                return 0
            FORWARDER["f"] = forwarder.Forwarder(os.environ.get("TWIN_KAFKA", "127.0.0.1:9092"),
                                                 topic=f"{INSTR_NAME}_devices", prefix=INSTR_NAME)
        values = dict(INSTR.status())
        if hasattr(INSTR, "readings"):              # read-only values (chopper speeds and delays...)
            try:
                values.update(INSTR.readings())
            except Exception:                       # noqa: BLE001
                pass
        return FORWARDER["f"].publish(values, getattr(INSTR, "devices", None), only_changes=only_changes)
    except Exception as e:                          # noqa: BLE001
        print(f"[server] forwarder: {e}", flush=True)
        return 0


def _json(v):
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    return v.item() if hasattr(v, "item") else v


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, content):
        body = json.dumps(content, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):            # server log: one line per request
        sys.stderr.write("[server] " + fmt % args + "\n")

    def do_GET(self):
        if self.path == "/status":
            readings = INSTR.readings() if hasattr(INSTR, "readings") else {}
            return self._reply(200, dict(devices=INSTR.status(), readings=_json(readings), busy=LOCK.locked(),
                                         running=RUNNING["action"], last_number=INSTR.number, folder=INSTR.folder,
                                         mode=INSTR.mode, ready=READY.is_set()))
        if self.path == "/epics":                              # the PVs of the soft IOC (epics/ioc.py)
            return self._reply(200, _epics_values())
        if self.path == "/epics/motors":                       # its motor records (NICOS drives them)
            return self._reply(200, _epics_motors())
        if self.path == "/devices":
            if hasattr(INSTR, "samples"):
                INSTR.samples()            # the student's own samples appear in the list at once
            out = {n: dict(value=d.value, unit=d.unit, limits=d.limits,
                           choices=_json(d.choices) if d.choices else None, help=d.help)
                   for n, d in INSTR.devices.items()}
            if hasattr(INSTR, "readings"):                     # read-only values (chopper speeds...)
                for n, v in INSTR.readings().items():
                    unit, hlp = INSTR.readings_help(n)
                    out[n] = dict(value=_json(v), unit=unit, limits=None, choices=None, help=hlp, readonly=True)
            return self._reply(200, out)
        if self.path == "/sample":                             # the mounted sample: description and drawing
            import matplotlib
            matplotlib.use("Agg")
            import sample_library as sl
            spec = INSTR.sample_spec()
            text = sl.describe(INSTR_NAME, spec)
            folder = sl.user_folder(INSTR.folder)
            os.makedirs(folder, exist_ok=True)
            png = f"{folder}/{spec['id']}.png"
            sl.draw(INSTR_NAME, spec).savefig(png, dpi=90)
            return self._reply(200, dict(name=spec["id"], text=text, png=png))
        if self.path == "/log":
            lines = []
            if os.path.isfile(INSTR.log_file):
                lines = [json.loads(l) for l in open(INSTR.log_file, encoding="utf-8")]
            return self._reply(200, lines)
        self._reply(404, dict(error=f"unknown: {self.path}"))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            args = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError as e:
            return self._reply(400, dict(error=f"invalid JSON: {e}"))
        if self.path in ("/go", "/stop"):                # live stream control: answered even during a count
            if self.path == "/stop":
                STOP.set()
            GO.set()
            return self._reply(200, dict(ok=True))
        if not LOCK.acquire(blocking=False):
            return self._reply(409, dict(error=f"instrument busy ({RUNNING['action']})"))
        try:
            RUNNING["action"] = self.path
            if self.path == "/folder":                     # data folder (NICOS proposal): its samples too
                _use_folder(args.get("folder", ""))
                return self._reply(200, dict(folder=INSTR.folder))
            if self.path == "/filewriter/start":
                return self._reply(200, _fw_start(args))
            if self.path == "/filewriter/stop":
                return self._reply(200, _fw_stop())
            if self.path == "/epics/put":                  # NICOS moved a motor through its EPICS PV
                return self._reply(200, _epics_put(args))
            if self.path == "/move":
                INSTR.move(**args)
                _forward()
                return self._reply(200, dict(devices=INSTR.status()))
            if self.path == "/count":
                if args.get("folder"):
                    _use_folder(args["folder"])
                f = INSTR.count(float(args["t"]), title=args.get("title", ""), write=args.get("write", True))
                out = dict(file=f, number=INSTR.number, n_counts=getattr(INSTR, "last_n_counts", None))
                fw = _fw_publish(f) if f and (FW.get("job") or _livedata()) else None
                if args.get("stream") and f:
                    out["streamed"] = _stream(f, hold=args.get("hold", False))
                if fw is not None:
                    fw.join()
                    if FW.get("job"):
                        FW["twin_files"].append(f)
                        out["filewriter"] = FW["file"]
                    if _livedata():
                        out["livedata"] = True
                if args.get("image"):                          # detector image for live displays (NICOS)
                    out["image"] = INSTR.last_image.tolist()
                return self._reply(200, out)
            if self.path == "/camera":                     # ODIN: an image of the integrating camera (white beam)
                if args.get("folder"):
                    _use_folder(args["folder"])
                f = INSTR.camera(float(args["t"]), title=args.get("title", ""), write=args.get("write", True))
                return self._reply(200, dict(file=f, number=INSTR.number, n_counts=INSTR.last_n_counts))
            if self.path == "/scan":
                files = INSTR.scan(args["device"], args["values"], float(args["t"]), title=args.get("title", ""))
                return self._reply(200, dict(files=files))
            return self._reply(404, dict(error=f"unknown command: {self.path}"))
        except (ValueError, KeyError, TypeError) as e:         # user error: impossible setting...
            return self._reply(400, dict(error=str(e)))
        except Exception as e:                                 # twin error
            traceback.print_exc()
            return self._reply(500, dict(error=f"{type(e).__name__}: {e}"))
        finally:
            RUNNING["action"] = None
            LOCK.release()


def _stream(f, hold=False):
    """Replays the neutrons of file f to Kafka in real time; returns the number of events sent (0 if not possible)."""
    if not hasattr(INSTR, "stream_pulses"):
        return 0
    sys.path.insert(0, os.path.join(HERE, "kafka"))
    import streamer
    if not streamer.available():
        print("[server] live stream skipped: confluent-kafka / ess-streaming-data-types not installed", flush=True)
        return 0
    pulses = INSTR.stream_pulses(f)
    STOP.clear(); GO.clear()
    if "s" not in STREAMER:
        STREAMER["s"] = streamer.Streamer(os.environ.get("TWIN_KAFKA", "127.0.0.1:9092"),
                                          topic=f"{INSTR_NAME}_detector", source=f"{INSTR_NAME}_detector")
    STREAMER["s"].empty_pulse()                       # the detector stream exists before the count starts
    if hold:                                          # computed: wait for the start of the count (POST /go)
        READY.set()
        GO.wait(timeout=600)
        READY.clear()
    if STOP.is_set():
        return 0
    return STREAMER["s"].stream(pulses, stop=STOP)


def main():
    global INSTR, INSTR_NAME
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--instrument", default="odin", choices=sorted(INSTRUMENTS))
    p.add_argument("--session", default=os.environ.get("TWIN_SESSION", "console"))
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--mode", default="hybrid", choices=("hybrid", "mcstas"))
    a = p.parse_args()
    folder, module, cls = INSTRUMENTS[a.instrument]
    sys.path.insert(0, os.path.join(HERE, folder))
    import importlib
    INSTR = getattr(importlib.import_module(module), cls)(session=a.session, mode=a.mode)
    INSTR_NAME = a.instrument
    _forward(only_changes=False)                       # the values of all the devices, once at start
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Virtual {a.instrument.upper()} ready: http://127.0.0.1:{a.port}  (session {a.session}, files in {INSTR.folder})",
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
