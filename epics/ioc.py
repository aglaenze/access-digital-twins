"""Soft IOC of the twin: every device of the instrument as an EPICS PV (pvAccess), with the name of the real PV.

At ESS each device is an EPICS PV, served by an IOC (the computer program in front of the hardware); the forwarder
relays the PVs to Kafka, where the file-writer and the live data reduction read them. The twin has no hardware: this
IOC serves the PVs of every device written in the real ESS file of the instrument (its f144 streams: the source name
is the PV name, e.g. ODIN-ChpSy1:Chop-WFMC-101:Spd_S) and gives them the current values of the twin, read from the
twin server (GET /epics) every `period` seconds. Read-only for now (NICOS drives the twin over HTTP).

    python ioc.py --twin http://127.0.0.1:8765 [--period 0.5]

Runs in the conda environment "forwarder" (p4p, as the ESS forwarder). Local only: it serves on 127.0.0.1.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

LOCAL = {"EPICS_PVAS_INTF_ADDR_LIST": "127.0.0.1", "EPICS_PVAS_BEACON_ADDR_LIST": "127.0.0.1",
         "EPICS_PVAS_AUTO_BEACON_ADDR_LIST": "NO"}


def table(twin):
    with urllib.request.urlopen(f"{twin}/epics", timeout=60) as r:
        return json.loads(r.read())


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--twin", default="http://127.0.0.1:8765")
    a.add_argument("--period", type=float, default=0.5)
    o = a.parse_args()
    from p4p.nt import NTScalar
    from p4p.server import Server
    from p4p.server.thread import SharedPV

    rows = table(o.twin)
    pvs, last = {}, {}
    for r in rows:
        if r["pv"] in pvs:                      # one PV can be written in several places of the file
            continue
        pvs[r["pv"]] = SharedPV(nt=NTScalar(r["type"]), initial=r["value"])
        last[r["pv"]] = r["value"]
    conf = dict(LOCAL, **{k: os.environ[k] for k in LOCAL if k in os.environ})
    with Server(providers=[pvs], conf=conf, useenv=False):
        print(f"IOC ready: {len(pvs)} PVs (twin {o.twin})", flush=True)
        while True:
            time.sleep(o.period)
            try:
                rows = table(o.twin)
            except Exception as e:              # noqa: BLE001  (the twin is busy or stopping)
                print(f"twin not reachable: {e}", file=sys.stderr, flush=True)
                continue
            now = time.time()
            for r in rows:
                pv, v = r["pv"], r["value"]
                if pv in pvs and last.get(pv) != v:
                    pvs[pv].post(v, timestamp=now)
                    last[pv] = v


if __name__ == "__main__":
    main()
