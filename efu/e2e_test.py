"""End-to-end test of the twin with the ESS Event Formation Unit (run by .github/workflows/efu.yml, on Linux): a Kafka
broker and the EFU (timepix3, configs/odin_timepix3.json) are running; this script plays ODIN's camera and timing
system, then compares what the EFU published with the neutrons sent.

    python efu/e2e_test.py --src <real ODIN file> [--brokers 127.0.0.1:9092] [--port 9000] [--topic odin_detector]

The EFU must be started with  timepix3 -f odin_timepix3.json --nohwcheck -b <brokers> -t <topic> -p <port>.

  1. the neutrons of the real ODIN file (entry/instrument/timepix3/data), with its pulses moved to now;
  2. their raw readout (timepix3_readout.packets: EVR packet and TDC word of each pulse, then a cluster of 4 pixel
     hits per neutron) sent over UDP to the EFU;
  3. the ev44 messages of the EFU read back from Kafka; per pulse, its neutrons compared with the ones the EFU must
     find (timepix3_readout.expected: same pixel, same time of flight to the coding of the camera, eto or eto + 1 ns).
Two neutrons in the same pixel at the same ns (repeated rays of the simulation: 6 % of this file) are one flash for
the camera, one neutron for the EFU; two neutrons within 1 ns and 1 chip pixel of each other make one cluster (pile-up,
9 pairs in this file), published as one neutron at their center. The test requires 99.5 % of the distinct neutrons
found exactly, in every pulse.
"""
import argparse
import os
import sys
import time
import uuid

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timepix3_readout as tr                   # noqa: E402

DATA = "entry/instrument/timepix3/data"


def load(src, max_events=0):
    """(etz, eto, ids, counts) of the real file, pulses moved to start now."""
    with h5py.File(src, "r") as f:
        g = f[DATA]
        etz = g["event_time_zero"][()].astype(np.int64)
        idx = g["event_index"][()].astype(np.int64)
        eto = g["event_time_offset"][()].astype(np.int64)
        ids = g["event_id"][()].astype(np.int64)
    counts = np.diff(np.r_[idx, len(eto)])
    if max_events:
        keep = np.searchsorted(np.cumsum(counts), max_events) + 1
        etz, counts = etz[:keep], counts[:keep]
        eto, ids = eto[:counts.sum()], ids[:counts.sum()]
    etz = time.time_ns() // 1000 * 1000 + (etz - etz[0])
    return etz, eto, ids, counts


def keys(ids, tof):
    return np.sort(np.asarray(ids, np.int64) * (1 << 28) + np.asarray(tof, np.int64))


def common(a, b):
    """Size of the intersection of two sorted multisets."""
    ua, ca = np.unique(a, return_counts=True)
    ub, cb = np.unique(b, return_counts=True)
    _, ia, ib = np.intersect1d(ua, ub, assume_unique=True, return_indices=True)
    return int(np.minimum(ca[ia], cb[ib]).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--brokers", default="127.0.0.1:9092")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--topic", default="odin_detector")
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--create-topic", action="store_true", help="only create the topic, then exit")
    a = ap.parse_args()

    from confluent_kafka import Consumer
    from confluent_kafka.admin import AdminClient, NewTopic
    if a.create_topic:
        admin = AdminClient({"bootstrap.servers": a.brokers})
        if a.topic not in admin.list_topics(timeout=20).topics:
            admin.create_topics([NewTopic(a.topic, 1, 1)])[a.topic].result(30)
        print(f"topic {a.topic} ready")
        return 0
    from streaming_data_types import deserialise_ev44

    etz, eto, ids, counts = load(a.src, a.max_events)
    period = 1e9 / tr.PULSE_HZ
    print(f"{counts.sum()} neutrons in {len(etz)} pulses; time of flight {eto.min()}..{eto.max()} ns "
          f"({np.sum(eto > period)} after the next pulse: the EFU drops them)", flush=True)

    c = Consumer({"bootstrap.servers": a.brokers, "group.id": f"efu-test-{uuid.uuid4()}",
                  "auto.offset.reset": "earliest", "enable.auto.commit": False,
                  "fetch.message.max.bytes": 64_000_000})
    c.subscribe([a.topic])
    t0 = time.time()
    while not c.assignment() and time.time() - t0 < 60:
        c.poll(0.5)

    t = time.time()
    payloads = tr.packets(etz, eto, ids, counts)
    print(f"{len(payloads)} UDP packets ({sum(map(len, payloads)) / 1e6:.1f} MB) made in {time.time() - t:.1f} s",
          flush=True)
    t = time.time()
    tr.send(payloads, a.host, a.port, pause_s=200e-6)
    print(f"sent in {time.time() - t:.1f} s", flush=True)

    got = {}                                    # reference time -> (ids, tofs)
    n_got, last = 0, time.time()
    while time.time() - last < 20:
        m = c.poll(1.0)
        if m is None or m.error():
            continue
        e = deserialise_ev44(m.value())
        if e.source_name != "timepix3":
            continue
        ref = int(e.reference_time[0]) if len(e.reference_time) else -1
        gi, gt = got.setdefault(ref, ([], []))
        gi.append(np.asarray(e.pixel_id)), gt.append(np.asarray(e.time_of_flight))
        n_got += len(e.pixel_id)
        last = time.time()
    c.close()
    print(f"the EFU published {n_got} neutrons in {sum(1 for v in got.values() if sum(map(len, v[0])))} pulses",
          flush=True)

    start, n_sent, n_exp, n_match, n_extra, n_dup, bad_pulse = 0, 0, 0, 0, 0, 0, []
    for k, (t0, n) in enumerate(zip(etz, counts)):
        e, d = eto[start:start + n], ids[start:start + n]
        start += n
        ok = e <= period
        n_sent += n
        # identical neutrons (same pixel, same ns: repeated rays of the simulation) are one flash for the camera
        xk = np.unique(keys(*tr.expected(e[ok], d[ok])))
        xid, xtof = xk >> 28, xk & ((1 << 28) - 1)
        n_dup += int(ok.sum()) - len(xk)
        gi, gt = got.pop(int(t0), ([], []))
        gi = np.concatenate(gi) if gi else np.zeros(0, np.int64)
        gt = np.concatenate(gt) if gt else np.zeros(0, np.int64)
        m = common(keys(xid, xtof), keys(gi, gt))
        n_exp += len(xid)
        n_match += m
        n_extra += len(gi) - m
        if m < 0.995 * len(xid):
            bad_pulse.append(k)
        print(f"  pulse {k}: {len(xid)} expected, {len(gi)} published, {m} identical "
              f"(pixel and time of flight), {len(gi) - m} others (merged clusters)", flush=True)
    if got:
        print(f"  messages with other reference times: {[(r, sum(map(len, v[0]))) for r, v in got.items()]}")
    frac = n_match / max(n_exp, 1)
    print(f"RESULT: {n_match} of {n_exp} neutrons found exactly ({100 * frac:.3f} %), {n_extra} other neutrons "
          f"(two or more neutrons in one cluster), {n_dup} identical to another one (one flash), "
          f"{n_sent - n_exp - n_dup} dropped as after the next pulse")
    ok = frac >= 0.995 and n_extra <= 0.005 * n_exp and not bad_pulse
    print("PASS" if ok else f"FAIL (pulses below 99.5 %: {bad_pulse})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
