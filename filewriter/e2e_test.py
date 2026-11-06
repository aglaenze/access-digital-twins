"""End-to-end test of the twin with the ESS file-writer (run by .github/workflows/filewriter.yml, on Linux): a Kafka
broker and kafka-to-nexus are running; this script plays the twin and NICOS for one job, then compares the files.

    python filewriter/e2e_test.py --root /tmp/fw --instrument odin --src <real ODIN file> [--brokers 127.0.0.1:9092]

The file-writer must be started with
    --brokers <brokers> --command-status-topic <instrument>_filewriter --job-pool-topic <instrument>_filewriter_pool
    --hdf-output-prefix / --hdf-template-prefix <root>/templates
and see <root> at the same path.

What it does, as the twin and NICOS would:
  1. the template of the file-writer, from the real file (twin_filewriter.make_template);
  2. a "measurement" of the twin: the real file with its pulses moved to now (instead of a McStas simulation, so that
     the test needs neither McStas nor the beam files);
  3. start of the job (pl72, as NICOS: nexusfile_open), last values of all the devices (f144), the measurement
     (ev44 and f144, at the times of its pulses), stop of the job (6s4t), wait for the file (wrdn);
  4. compare.py: the file of the file-writer against the twin's file.
"""
import argparse
import os
import shutil
import sys
import time

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare                                  # noqa: E402
import twin_filewriter as tf                    # noqa: E402


def fake_measurement(src, out, start_ns):
    """The real file `src` with its pulses (and the device values recorded during them) moved to start at start_ns."""
    shutil.copyfile(src, out)
    with h5py.File(out, "r+") as f:
        st = tf.streams(f)
        ev = [p for p, m, *_ in st if m == "ev44" and len(f[p]["event_time_zero"])]
        t_min = min(int(f[p]["event_time_zero"][0]) for p in ev)
        t_max = max(int(f[p]["event_time_zero"][-1]) for p in ev) + 100_000_000
        delta = start_ns - t_min
        for p in ev:
            d = f[p]["event_time_zero"]
            d[...] = (d[()].astype(np.int64) + delta).astype(d.dtype)
        moved = 0
        for p, m, *_ in st:
            if m == "f144" and "time" in f[p]:
                d = f[p]["time"]
                t = d[()].astype(np.int64)
                inside = (t >= t_min) & (t <= t_max)
                if inside.any():
                    t[inside] += delta
                    d[...] = t.astype(d.dtype)
                    moved += int(inside.sum())
        # as the twin: a few devices set for the measurement, one value each at its start
        set_ = [p for p, m, *_ in st if m == "f144" and "value" in f[p] and f[p]["value"].dtype.kind == "f"
                and f[p]["value"].ndim == 1][:3]
        for k, p in enumerate(set_):
            g = f[p]
            for name, data in (("value", np.array([10.0 + k], g["value"].dtype)),
                               ("time", np.array([start_ns], g["time"].dtype))):
                attrs = dict(g[name].attrs)
                del g[name]
                g.create_dataset(name, data=data)
                g[name].attrs.update(attrs)
        moved += len(set_)
    print(f"measurement: {len(ev)} event streams, {moved} device values during the pulses")
    return out


def topics_tool(argv, brokers="127.0.0.1:9092"):
    """--create-topics T...: creates them (one partition); --show-topics T...: the kinds of the messages on them."""
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.admin import AdminClient, NewTopic
    names = argv[1:]
    if argv[0] == "--create-topics":
        admin = AdminClient({"bootstrap.servers": brokers})
        existing = admin.list_topics(timeout=20).topics
        new = [NewTopic(t, 1, 1) for t in names if t not in existing]
        for fut in (admin.create_topics(new).values() if new else []):
            fut.result(30)
        print("topics created:", [t.topic for t in new])
        return
    c = Consumer({"bootstrap.servers": brokers, "group.id": f"show-{time.time()}", "enable.auto.commit": False})
    for t in names:
        lo, hi = c.get_watermark_offsets(TopicPartition(t, 0), timeout=20)
        c.assign([TopicPartition(t, 0, lo)])
        kinds = []
        while len(kinds) < hi - lo:
            m = c.poll(5)
            if m is None:
                break
            if not m.error():
                kinds.append(m.value()[4:8].decode(errors="replace"))
        print(f"{t}: {hi - lo} messages: {' '.join(kinds)}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--create-topics", "--show-topics"):
        return topics_tool(sys.argv[1:])
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", required=True)
    p.add_argument("--instrument", required=True)
    p.add_argument("--src", required=True)
    p.add_argument("--brokers", default="127.0.0.1:9092")
    a = p.parse_args()
    instr = a.instrument
    root = os.path.abspath(a.root)

    template = tf.make_template(a.src, os.path.join(root, "templates", instr, f"{instr}.hdf"))
    with h5py.File(template, "r") as f:
        left = tf.streams(f)
    print(f"template: {template} ({os.path.getsize(template) / 1e6:.0f} MB), streams left in it: {len(left)}")
    assert not left, left

    os.makedirs(os.path.join(root, "out"), exist_ok=True)
    control = tf.FileWriterControl(a.brokers, f"{instr}_filewriter")
    producer = tf.producer(a.brokers)
    structure = tf.nexus_structure(a.src, title="file-writer test", proposal="1000", sample_name="test sample")
    n_modules = sum(1 for _ in _modules(structure))
    print(f"start command: {n_modules} streams")

    job_start = time.time_ns()
    fw_file = os.path.join(root, "out", f"{instr}_job_000001.hdf")
    job = control.start(structure, fw_file, instr, start_ns=job_start, timeout=120)
    print(f"job {job} started: {fw_file}")
    sent = tf.publish(producer, tf.snapshot_messages(a.src, job_start + 1_000_000))
    print(f"device values at the start: {sent} messages")

    twin_file = fake_measurement(a.src, os.path.join(root, "out", f"{instr}_000001.nxs"), time.time_ns() + 2_000_000_000)
    msgs = tf.count_messages(twin_file)
    t0 = time.time()
    sent = tf.publish(producer, msgs, pace=True)
    print(f"measurement: {sent} messages in {time.time() - t0:.1f} s")
    time.sleep(2)
    control.stop(job, timeout=60)
    name, error = control.wait_done(job, timeout=300)
    print(f"file written: {name}" + (f", ERROR {error}" if error else ""))
    assert error is None, error

    bad, _ = compare.compare(fw_file, [twin_file])
    print("SAME DATA" if bad == 0 else f"{bad} DIFFERENCE(S)")
    sys.exit(1 if bad else 0)


def _modules(node):
    for c in node.get("children", []):
        if c.get("module") in tf.PUBLISHED:
            yield c
        yield from _modules(c)


if __name__ == "__main__":
    main()
