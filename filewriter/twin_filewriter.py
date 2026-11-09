"""The twin and the ESS file-writer (kafka-to-nexus): what the twin needs to have its files written as at ESS
(filewriter/README.md, steps 2 and 3).

How it works at ESS, and here:
  * every stream of a real ESS file says where its data came from: the group has the attributes `writer_module`
    (f144: values of a device, ev44: neutron events), `source` (EPICS PV name, detector or monitor name) and `topic`
    (Kafka topic), e.g. entry/instrument/timepix3/data: ev44, source "timepix3", topic "odin_detector";
  * the file-writer starts from a TEMPLATE file of the instrument (the static data: geometry, pixel tables...), found
    at <hdf-template-prefix>/<instrument>/<instrument>.hdf, and adds what the start command (pl72) describes: the
    streams to record, and the values of this run (title, proposal, sample);
  * the twin publishes on the same topics, with the same source names, what the real instrument publishes: the
    neutrons of each pulse (ev44) and the values of its devices (f144). The template, the start command and the
    messages are all made from the real ESS file that the twin uses for its own files, so they cannot disagree.

    make_template(src, out, patch)       the template of the file-writer (src: the real file used by the twin)
    nexus_structure(src, title, ...)     the "nexus_structure" of the start command
    snapshot_messages(src, t_ns)         the last value of every device (the EPICS forwarder at the start of a job)
    count_messages(twin_file)            the neutrons and device values of one twin measurement
    publish(producer, messages, pace)    sends them (pace: at their times, as on the instrument)
    FileWriterControl                    start / stop a job, wait for the file (pl72, 6s4t, answ, wrdn)

Needs h5py, numpy, confluent-kafka, ess-streaming-data-types. Not done by the twin (yet): the chopper top-dead-center
timestamps (tdct): they stay those of the real file, in the template.
"""
import datetime
import json
import os
import shutil
import time
import uuid

import h5py
import numpy as np

PUBLISHED = ("f144", "ev44")          # the streams the twin publishes; the others (tdct) stay static, in the template
PER_RUN = ("entry/title", "entry/experiment_identifier", "entry/start_time", "entry/end_time", "entry/sample/name",
           "entry/twin")             # values of a run: given by the start command (mdat: start and end times)
# root attributes the file-writer writes into each of its files (HDFFile.cpp, write_common_attributes): not in the
# template, where it could not create them again ("attribute already exists"); template_version stays (it reads it)
FILE_ATTRS = ("HDF5_Version", "file_name", "creator", "file_time", "dynamic_version")
DTYPES = {"float64": "double", "float32": "float", "int8": "int8", "uint8": "uint8", "int16": "int16",
          "uint16": "uint16", "int32": "int32", "uint32": "uint32", "int64": "int64", "uint64": "uint64",
          "bool": "uint8"}


def _s(v):
    return v.decode() if isinstance(v, bytes) else str(v)


def streams(f, modules=PUBLISHED):
    """[(path, module, source, topic)] of the stream groups of an open h5py file."""
    out = []

    def visit(name, o):
        if isinstance(o, h5py.Group) and "writer_module" in o.attrs and _s(o.attrs["writer_module"]) in modules:
            out.append((name, _s(o.attrs["writer_module"]), _s(o.attrs.get("source", "")),
                        _s(o.attrs.get("topic", ""))))
    f.visititems(visit)
    return out


def fixed_logs(f):
    """[path] of the NXlogs of an open h5py file that are not streams: written once, with the file (e.g. ODIN
    wfm1/transformations/wfmc_translation, the position of a WFM disc). The twin changes some of them for each
    measurement: the start command gives their values (the template has none)."""
    out = []

    def visit(name, o):
        if (isinstance(o, h5py.Group) and _s(o.attrs.get("NX_class", "")) == "NXlog" and "writer_module" not in o.attrs
                and isinstance(o.get("value"), h5py.Dataset) and o["value"].dtype.name in DTYPES
                and (not isinstance(o.get("time"), h5py.Dataset) or o["time"].dtype.name in DTYPES)):
            out.append(name)
    f.visititems(visit)
    return out


# --------------------------------------------------------------------------- the template
def make_template(src, out, patch=None):
    """Writes the template of the file-writer: the real file `src` without the streams the twin publishes and without
    the values of a run (they come with the start command), nor the values of the fixed logs (fixed_logs: they also
    come with the start command, the twin changes some; kept in <out>.fixed.json). patch(f): the static changes the
    twin makes to its own files (e.g. the detector distance of the model), applied first. Returns out."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".tmp"
    shutil.copyfile(src, tmp)
    with h5py.File(tmp, "r+") as f:
        if patch is not None:
            patch(f)
        for path, *_ in streams(f):
            del f[path]
        fixed = {}
        for path in fixed_logs(f):
            g = f[path]
            fixed[path] = {k: {"values": g[k][()].tolist(), "dtype": DTYPES.get(g[k].dtype.name, "double"),
                               "attributes": _attributes(g[k])} for k in ("value", "time") if k in g}
            for k in fixed[path]:
                del g[k]
        for p in PER_RUN:
            if p in f:
                del f[p]
        for k in [k for k in f["entry"] if k.startswith("user_")]:       # no real users in the twin's files
            del f["entry"][k]
        f["entry"].attrs["twin_template"] = "template of the ESS file-writer, made by the digital twin"
    # written again in the format of HDF5 1.10 or later: the file-writer opens its copy in SWMR mode, which needs a
    # superblock of version 3 (the real files have an older one); this also drops the space of the deleted streams
    with h5py.File(tmp, "r") as f, h5py.File(out + ".new", "w", libver=("v110", "latest")) as g:
        for k, v in f.attrs.items():
            if k not in FILE_ATTRS:
                g.attrs[k] = v
        for name in f:
            f.copy(f[name], g, name=name)
    os.remove(tmp)
    os.replace(out + ".new", out)
    with open(out + FIXED_SUFFIX, "w") as fo:
        json.dump(fixed, fo)
    return out


FIXED_SUFFIX = ".fixed.json"     # next to the template: the fixed logs taken out of it, with their values


def fixed_values(template, settings=None, t_ns=None):
    """{path: {"value": ..., "time": ...}} of the fixed logs taken out of the template (make_template), for the start
    command: the values of the template, or the current setting of the twin ({path: value}, stamped t_ns)."""
    with open(template + FIXED_SUFFIX) as fi:
        fixed = json.load(fi)
    for path, v in (settings or {}).items():
        if path in fixed:
            fixed[path]["value"]["values"] = [float(v)] if fixed[path]["value"]["dtype"] in ("double", "float")                 else [int(v)]
            if "time" in fixed[path] and t_ns is not None:
                fixed[path]["time"]["values"] = [int(t_ns)]
    return fixed


def superblock_version(path):
    with h5py.File(path, "r") as f:
        return f.id.get_create_plist().get_version()[0]


# --------------------------------------------------------------------------- the start command
def _module(f, path, module, source, topic):
    if module == "ev44":
        return {"module": "ev44", "config": {"source": source, "topic": topic}}
    v = f[path].get("value")
    cfg = {"source": source, "topic": topic, "dtype": "double"}
    if v is not None:
        if v.dtype.name not in DTYPES:          # strings: f144 has none
            return None
        cfg["dtype"] = DTYPES[v.dtype.name]
        if "units" in v.attrs:
            cfg["value_units"] = _s(v.attrs["units"])
        if v.ndim > 1:
            cfg["array_size"] = int(np.prod(v.shape[1:]))
    return {"module": "f144", "config": cfg}


STREAM_ATTRS = ("writer_module", "source", "topic")      # given by the module itself


def _attributes(obj):
    """The attributes of an HDF5 object in the form of the start command ([{name, values[, dtype]}]). A stream group
    is not in the template: the file-writer creates it from the start command, so its attributes must be there, e.g.
    those that make a log a transformation (depends_on, transformation_type, vector, units)."""
    out = []
    for k, v in obj.attrs.items():
        if k in STREAM_ATTRS:
            continue
        if isinstance(v, bytes):
            v = v.decode()
        if isinstance(v, str):
            out.append({"name": k, "values": v})
            continue
        a = np.asarray(v)
        if a.dtype.kind in "SO":
            out.append({"name": k, "values": [_s(x) for x in a.ravel()] if a.ndim else _s(a.item())})
        elif a.dtype.name in DTYPES:
            out.append({"name": k, "values": a.tolist(), "dtype": DTYPES[a.dtype.name]})
    return out


def _string(name, value):
    return {"module": "dataset", "config": {"name": name, "values": str(value), "dtype": "string"}}


def _value(name, value):
    if isinstance(value, (bool, np.bool_)):
        value = int(value)
    if isinstance(value, (int, np.integer)):
        return {"module": "dataset", "config": {"name": name, "values": int(value), "dtype": "int64"}}
    if isinstance(value, (float, np.floating)):
        return {"module": "dataset", "config": {"name": name, "values": float(value), "dtype": "double"}}
    return _string(name, value)


def nexus_structure(src, title="", proposal="", sample_name="", twin=None, fixed=None):
    """The nexus_structure (dict) of the start command: the groups down to every stream of `src`, each stream as its
    writer module (same source and topic as in the real file), and the values of the run. twin: {name: value}, the
    settings of the twin at the start of the job, written in entry/twin (NXcollection), as NICOS writes the values
    of its devices into the start command at ESS (what the reduction of the twin needs, e.g. LoKI's configuration).
    fixed: fixed_values(template, ...), the values of the fixed logs (dataset modules, with their attributes)."""
    root = {"children": []}
    nodes = {"": root}

    def group(path):
        if path in nodes:
            return nodes[path]
        parent, _, name = path.rpartition("/")
        g = {"type": "group", "name": name, "children": []}
        group(parent)["children"].append(g)
        nodes[path] = g
        return g

    with h5py.File(src, "r") as f:
        for path, module, source, topic in streams(f):
            m = _module(f, path, module, source, topic)
            if m is not None:
                g = group(path)
                g["children"].append(m)
                attrs = _attributes(f[path])
                if attrs:
                    g["attributes"] = attrs
    for path, data in (fixed or {}).items():
        group(path)["children"] += [{"module": "dataset", "config": {"name": k, "values": d["values"],
                                                                     "dtype": d["dtype"]},
                                     "attributes": d["attributes"]} for k, d in data.items()]
    entry = group("entry")
    entry["children"] += [_string("title", title), _string("experiment_identifier", proposal),
                          {"module": "mdat", "config": {"items": ["start_time", "end_time"]}}]
    group("entry/sample")["children"].append(_string("name", sample_name))
    if twin:
        g = group("entry/twin")
        g["attributes"] = [{"name": "NX_class", "values": "NXcollection"},
                           {"name": "description", "values": "Digital twin: its settings at the start of the job "
                                                             "(given by the start command, as NICOS does at ESS)"}]
        g["children"] += [_value(k, v) for k, v in twin.items()]
    return root


# --------------------------------------------------------------------------- the messages
def _f144(source, value, t_ns):
    from streaming_data_types import serialise_f144
    return serialise_f144(source, value, int(t_ns))


# logs with a value at every source pulse, which the twin writes in its files with the neutrons (ODIN: the proton
# charge, used to normalize): published with each measurement, never in the snapshot (a value at the start of a job
# would count as one more pulse)
PER_PULSE = ("entry/instrument/source/pulse_charge",)


def snapshot_messages(src, t_ns, settings=None):
    """[(t_ns, topic, payload)]: the value of every device of `src` (f144), stamped t_ns: its last value in `src`, or
    the current setting of the twin given in `settings` ({path of the device in the file: value}; a device that is an
    NXpositioner: its logs value and target_value). At ESS the EPICS forwarder publishes each PV when it changes;
    the file-writer then has a value for every device of the file. Not the logs of PER_PULSE (the proton charge): those
    come with the neutrons of each measurement."""
    settings = settings or {}
    over = {}
    for p, v in settings.items():
        for q in (p, f"{p}/value", f"{p}/target_value"):
            over[q] = v
    out = []
    with h5py.File(src, "r") as f:
        for path, module, source, topic in streams(f, ("f144",)):
            v = f[path].get("value")
            if v is None or v.dtype.name not in DTYPES or path in PER_PULSE:
                continue
            if path in over:
                value = np.asarray(over[path], dtype=v.dtype)
            elif v.shape[0]:
                value = np.asarray(v[-1])
            else:
                continue
            out.append((int(t_ns), topic, _f144(source, value, t_ns)))
    return out


MARKER = "twin_topic_marker"       # a source name no stream of a job uses: the file-writer reads, then drops it


def topic_markers(structure, t_ns):
    """[(t_ns, topic, payload)]: one message (source MARKER) on each topic of the nexus structure of a job, published
    just before it. At the start of a job, kafka-to-nexus looks on each topic for the first message of the last 10 s (offsets for time,
    BeforeStartTime); on a topic without one (empty, or quiet for 10 s: the detector of the twin between two
    measurements) it reads from the end of the topic, wherever that is when it gets there: the first neutrons sent
    after the start could be lost (2026-11-09: 22 of the 46 events of a dark job of ODIN). With a marker, it starts
    from the marker. Its source is in no job: it is not written. On a topic of events: an ev44 message without events
    (just-bin-it reads those topics too, and only ev44)."""
    from streaming_data_types import serialise_ev44
    kinds = {}
    def walk(node):
        if isinstance(node, dict):
            c = node.get("config")
            if node.get("module") in PUBLISHED and isinstance(c, dict) and c.get("topic"):
                kinds.setdefault(c["topic"], set()).add(node["module"])
            for ch in node.get("children", []):
                walk(ch)
    walk(structure)
    empty = np.zeros(0, np.int32)
    return [(int(t_ns), t, serialise_ev44(MARKER, 0, np.array([t_ns], np.int64), np.array([0], np.int32), empty, empty)
             if "ev44" in m else _f144(MARKER, np.float64(0.0), t_ns)) for t, m in sorted(kinds.items())]


def count_messages(twin_file, message_id=0):
    """[(t_ns, topic, payload)] of one measurement of the twin (its NeXus file): one ev44 message per pulse with
    neutrons and per detector bank or monitor, and the device values recorded during the measurement (f144). The
    times are those of the file. Pulses without neutrons are not sent (the file-writer would not write them)."""
    from streaming_data_types import serialise_ev44
    out = []
    with h5py.File(twin_file, "r") as f:
        st = streams(f)
        t0 = None
        for path, module, source, topic in st:
            if module != "ev44":
                continue
            g = f[path]
            etz, idx = g["event_time_zero"][()].astype(np.int64), g["event_index"][()].astype(np.int64)
            eto = np.round(g["event_time_offset"][()]).astype(np.int32)
            eid = g["event_id"][()].astype(np.int32)
            if len(etz):
                t0 = etz[0] if t0 is None else min(t0, etz[0])
            bounds = np.append(idx, len(eid))
            for k in range(len(etz)):
                a, b = bounds[k], bounds[k + 1]
                if b <= a:
                    continue
                message_id += 1
                out.append((int(etz[k]), topic, serialise_ev44(source, message_id, np.array([etz[k]], np.int64),
                                                              np.array([0], np.int32), eto[a:b], eid[a:b])))
        if t0 is not None:
            for path, module, source, topic in st:
                if module != "f144":
                    continue
                g = f[path]
                if "time" not in g or "value" not in g or g["value"].dtype.name not in DTYPES:
                    continue
                t, v = g["time"][()].astype(np.int64), g["value"][()]
                for k in np.nonzero(t >= t0)[0]:
                    out.append((int(t[k]), topic, _f144(source, np.asarray(v[k]), t[k])))
    out.sort(key=lambda m: m[0])
    return out


def publish(producer, messages, pace=False, stop=None):
    """Sends [(t_ns, topic, payload)]; pace: each message not before its time (wall clock), as the instrument
    produces them. Returns the number sent."""
    n = 0
    for t_ns, topic, payload in messages:
        if pace:
            wait = (t_ns - time.time_ns()) / 1e9
            if wait > 0:
                time.sleep(wait)
        if stop is not None and stop.is_set():
            break
        producer.produce(topic, payload, timestamp=t_ns // 1_000_000)
        producer.poll(0)
        n += 1
    producer.flush(30)
    return n


def producer(brokers):
    from confluent_kafka import Producer
    return Producer({"bootstrap.servers": brokers, "message.max.bytes": 16_000_000,
                     "queue.buffering.max.kbytes": 1_048_576, "linger.ms": 5})


# --------------------------------------------------------------------------- start / stop a job
def nicos_uuid():
    """A job or command id the file-writer accepts (kafka-to-nexus src/CommandSystem/Handler.cpp, isValidUUID; others
    are refused, "job id was invalid"): the form of a UUID, digits only up to position 14, 5 at position 14 and 8 at
    position 19."""
    u = list(str(uuid.uuid4()))
    for i in range(14):
        if u[i] != "-":
            u[i] = str(int(u[i], 16) % 10)
    u[14], u[19] = "5", "8"
    return "".join(u)


def _utc(t_ns):
    return datetime.datetime.fromtimestamp(t_ns / 1e9, datetime.timezone.utc)


def structure_topics(node):
    """The Kafka topics named in a nexus structure (the config of its writer modules)."""
    out = set()
    if isinstance(node, dict):
        t = (node.get("config") or {}).get("topic") if isinstance(node.get("config"), dict) else None
        if t:
            out.add(t)
        for c in node.get("children", []):
            out |= structure_topics(c)
    return out


def ensure_topics(brokers, names):
    """Creates the topics that do not exist yet (one partition each)."""
    from confluent_kafka.admin import AdminClient, NewTopic
    admin = AdminClient({"bootstrap.servers": brokers})
    existing = admin.list_topics(timeout=20).topics
    new = [NewTopic(t, 1, 1) for t in sorted(set(names)) if t not in existing]
    for fut in (admin.create_topics(new).values() if new else []):
        try:
            fut.result(30)
        except Exception:                          # noqa: BLE001  (created meanwhile)
            pass
    return [t.topic for t in new]


class FileWriterControl:
    """Starts and stops jobs of a file-writer, as NICOS does at ESS (nicos_ess/devices/datasinks/file_writer.py):
    the start (pl72) goes to the job pool (`pool_topic`, the --job-pool-topic of the file-writer, default
    `<command_topic>_pool`) and names `command_topic` as the control topic of the job: the file-writer then answers
    there (answ), takes the stop (6s4t) there and reports the end of the file there (wrdn)."""

    def __init__(self, brokers, command_topic, pool_topic=None):
        from confluent_kafka import Consumer, TopicPartition
        self.brokers, self.topic = brokers, command_topic
        self.pool_topic = pool_topic or f"{command_topic}_pool"
        ensure_topics(brokers, (command_topic, self.pool_topic))
        self.producer = producer(brokers)
        self.consumer = Consumer({"bootstrap.servers": brokers, "group.id": f"twin-{uuid.uuid4()}",
                                  "enable.auto.commit": False, "fetch.message.max.bytes": 16_000_000})
        for attempt in range(10):                   # a topic just created may have no leader yet; the bootstrap
            try:                                    # connection may be dropped (localhost resolved to ::1 first)
                _, hi = self.consumer.get_watermark_offsets(TopicPartition(command_topic, 0), timeout=20)
                break
            except Exception:                       # noqa: BLE001
                if attempt == 9:
                    raise
                time.sleep(2)
        self.consumer.assign([TopicPartition(command_topic, 0, hi)])

    def _send(self, payload, topic=None):
        self.producer.produce(topic or self.topic, payload)
        self.producer.flush(30)

    def _wait(self, job_id, kind, timeout):
        """The next message `kind` (b"answ" or b"wrdn") about job_id, deserialised; TimeoutError if none."""
        from streaming_data_types import deserialise_answ, deserialise_wrdn
        end = time.time() + timeout
        while time.time() < end:
            m = self.consumer.poll(1.0)
            if m is None or m.error() or m.value() is None or len(m.value()) < 8:
                continue
            if kind == b"answ" and m.value()[4:8] == b"wrdn":       # the job ended while an answer was awaited
                w = deserialise_wrdn(m.value())
                if w.job_id == job_id:
                    raise RuntimeError(f"the file-writer ended job {job_id}: error={w.error_encountered} "
                                       f"message={w.message!r} file={w.file_name!r}")
            if m.value()[4:8] != kind:
                continue
            r = (deserialise_answ if kind == b"answ" else deserialise_wrdn)(m.value())
            if r.job_id == job_id:
                return r
        raise TimeoutError(f"no {kind.decode()} message of the file-writer for job {job_id} in {timeout:.0f} s "
                           f"(is it running? topic {self.topic})")

    def start(self, structure, filename, instrument, start_ns=None, job_id=None, timeout=60):
        """Starts a job writing `filename` (as the file-writer sees it) from the template of `instrument`. Returns
        the job id; RuntimeError if the file-writer refuses."""
        from streaming_data_types import serialise_pl72
        from streaming_data_types.action_response_answ import ActionOutcome
        job_id = job_id or nicos_uuid()
        start_ns = start_ns or time.time_ns()
        # every topic of the structure must exist when the job starts (the file-writer ends it otherwise: "Unable to
        # set up consumer ... as this topic does not exist"); at ESS they always exist
        ensure_topics(self.brokers, structure_topics(structure))
        stop = _utc(start_ns) + datetime.timedelta(days=365.25 * 10)      # as NICOS: open-ended, until the stop
        self._send(serialise_pl72(job_id, filename, start_time=_utc(start_ns), stop_time=stop,
                                  run_name=os.path.basename(filename), nexus_structure=json.dumps(structure),
                                  instrument_name=instrument, broker=self.brokers, control_topic=self.topic),
                   topic=self.pool_topic)
        r = self._wait(job_id, b"answ", timeout)
        if r.outcome != ActionOutcome.Success:
            raise RuntimeError(f"the file-writer refused the job: {r.message}")
        return job_id

    def stop(self, job_id, stop_ns=None, timeout=60):
        """Sets the stop time of the job (now by default)."""
        from streaming_data_types import serialise_6s4t
        from streaming_data_types.action_response_answ import ActionOutcome
        self._send(serialise_6s4t(job_id, stop_time=_utc(stop_ns or time.time_ns()), command_id=nicos_uuid()))
        r = self._wait(job_id, b"answ", timeout)
        if r.outcome != ActionOutcome.Success:
            raise RuntimeError(f"the file-writer refused to stop the job: {r.message}")

    def wait_done(self, job_id, timeout=120):
        """Waits for the end of the file; returns (file name, error message or None)."""
        r = self._wait(job_id, b"wrdn", timeout)
        return r.file_name, (r.message or "error") if r.error_encountered else None
