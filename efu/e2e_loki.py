"""End-to-end test of the twin with the ESS Event Formation Unit for LoKI (run by .github/workflows/efu.yml, on Linux):
a Kafka broker and one EFU per bank (program loki, configs/loki.json, a null calibration) are running, as at ESS;
this script plays LoKI's readout system, then compares what the EFUs published with the neutrons sent.

    python efu/e2e_loki.py [--src <real LoKI file>] [--random N] [--brokers 127.0.0.1:9092]

EFU of bank b:  loki -f loki.json --calibration <file> --nohwcheck -b <brokers> -t loki_detector_bank<b>
                -p PORT + b -m CMD_PORT + b

  1. the neutrons: those of the real LoKI file (5 pulses, its 9 banks), then N random neutrons on all the pixels of
     the 9 banks; their pulses moved to now;
  2. their raw readout (caen_readout.Readout: one 24-byte CAEN readout per neutron, ESS readout header) sent over UDP,
     each bank to its EFU;
  3. the ev44 messages read back from the 9 topics; per bank and pulse, each neutron sent must come back once, with the
     same pixel and the time of flight of caen_readout.expected (rounded to a tick of the ESS clock). The test requires
     all of them, and nothing else.
"""
import argparse
import os
import sys
import time
import uuid

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caen_readout as cr                       # noqa: E402
from e2e_test import efu_stats                  # noqa: E402

PORT, CMD_PORT = 9100, 8900
TOPICS = [f"loki_detector_bank{b}" for b in range(cr.N_BANKS)]


def load_file(src):
    """(etz, eto, ids, counts) of the 9 banks of the real file, merged pulse by pulse."""
    etz, eto, ids = [], [], []
    with h5py.File(src, "r") as f:
        for b in range(cr.N_BANKS):
            g = f[f"entry/instrument/loki_detector_{b}/detector_events"]
            z = g["event_time_zero"][()].astype(np.int64)
            n = np.diff(np.r_[g["event_index"][()].astype(np.int64), len(g["event_id"])])
            etz.append(np.repeat(z, n)), eto.append(g["event_time_offset"][()].astype(np.int64))
            ids.append(g["event_id"][()].astype(np.int64))
    etz, eto, ids = (np.concatenate(v) for v in (etz, eto, ids))
    o = np.argsort(etz, kind="stable")
    return by_pulse(etz[o], eto[o], ids[o])


def by_pulse(t, eto, ids):
    pulses, counts = np.unique(t, return_counts=True)
    return pulses, eto, ids, counts


def random_neutrons(n, pulses=30, seed=2):
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, np.ones(pulses) / pulses)
    etz = np.round(np.arange(pulses) * 1e9 / 14).astype(np.int64)
    eto = rng.integers(0, 2 * cr.PERIOD_NS, n)
    return etz, eto, rng.integers(1, cr.N_PIXELS + 1, n), counts


def run(name, etz, eto, ids, counts, a, consumer):
    from streaming_data_types import deserialise_ev44
    from timepix3_readout import send
    etz = time.time_ns() // 1000 * 1000 + (etz - etz[0])
    t0 = np.repeat(etz, counts)
    bank = cr.bank_of(ids)
    print(f"{name}: {counts.sum()} neutrons in {len(etz)} pulses, per bank {np.bincount(bank, minlength=9).tolist()}; "
          f"time of flight {eto.min()}..{eto.max()} ns", flush=True)
    readout, start, n_packets = cr.Readout(), 0, 0
    for p, n in zip(etz, counts):                   # pulse by pulse, each bank to its EFU
        for b, payloads in readout.pulse(p, eto[start:start + n], ids[start:start + n]).items():
            send(payloads, a.host, PORT + b, pause_s=a.pause_us * 1e-6)
            n_packets += len(payloads)
        start += n
    print(f"  {n_packets} UDP packets sent", flush=True)

    got = {b: ([], [], []) for b in range(cr.N_BANKS)}          # bank -> (pulse times, ids, tofs)
    n_got, last = 0, time.time()
    while time.time() - last < 15:
        m = consumer.poll(1.0)
        if m is None or m.error():
            continue
        e = deserialise_ev44(m.value())
        b = TOPICS.index(m.topic())
        ref = int(e.reference_time[0]) if len(e.reference_time) else -1
        assert e.source_name == "caen", e.source_name
        got[b][0].append(np.full(len(e.pixel_id), ref)), got[b][1].append(np.asarray(e.pixel_id))
        got[b][2].append(np.asarray(e.time_of_flight))
        n_got += len(e.pixel_id)
        if len(e.pixel_id):
            last = time.time()
    ok = True
    total = [0, 0, 0]
    for b in range(cr.N_BANKS):
        sel = bank == b
        g = [np.concatenate(v) if v else np.zeros(0, np.int64) for v in got[b]]
        found, sent, published, stray = cr.match(t0[sel], eto[sel], ids[sel], *g)
        wrong_bank = int(np.sum(cr.bank_of(g[1]) != b)) if len(g[1]) else 0
        total = [total[0] + found, total[1] + sent, total[2] + published]
        good = found == sent == published and stray == 0 and wrong_bank == 0
        ok &= good
        print(f"  bank {b} ({TOPICS[b]}): {found} of {sent} neutrons found exactly, {published} published, "
              f"{stray} pulses matching no pulse sent, {wrong_bank} pixels of another bank "
              f"{'ok' if good else 'DIFFERENT'}", flush=True)
    print(f"  {name}: {total[0]} of {total[1]} neutrons found exactly, {total[2]} published", flush=True)
    if not ok:
        for b in range(cr.N_BANKS):
            print(f"  counters of the EFU of bank {b}:\n    " + "\n    ".join(
                efu_stats(port=CMD_PORT + b, show=("parser", "readouts", "geometry", "events", "timestamp",
                                                   "calib", "receive"))), flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="real LoKI file (default: ess.loki.data.loki_coda_file())")
    ap.add_argument("--random", type=int, default=2_000_000, help="random neutrons on all pixels (0: none)")
    ap.add_argument("--brokers", default="127.0.0.1:9092")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--pause-us", type=float, default=200, help="pause between UDP packets")
    ap.add_argument("--create-topics", action="store_true", help="only create the topics, then exit")
    a = ap.parse_args()

    from confluent_kafka import Consumer
    from confluent_kafka.admin import AdminClient, NewTopic
    if a.create_topics:
        admin = AdminClient({"bootstrap.servers": a.brokers})
        have = admin.list_topics(timeout=20).topics
        for t, fut in admin.create_topics([NewTopic(t, 1, 1) for t in TOPICS if t not in have]).items():
            fut.result(30)
        print(f"topics {TOPICS[0]} ... {TOPICS[-1]} ready")
        return 0
    if not a.src:
        from ess.loki.data import loki_coda_file
        a.src = str(loki_coda_file())

    c = Consumer({"bootstrap.servers": a.brokers, "group.id": f"efu-loki-{uuid.uuid4()}",
                  "auto.offset.reset": "earliest", "enable.auto.commit": False,
                  "fetch.message.max.bytes": 64_000_000})
    c.subscribe(TOPICS)
    t = time.time()
    while len(c.assignment()) < len(TOPICS) and time.time() - t < 60:
        c.poll(0.5)
    ok = run("the real LoKI file", *load_file(a.src), a, c)
    if a.random:
        ok &= run(f"{a.random} random neutrons", *random_neutrons(a.random), a, c)
    c.close()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
