"""Soft IOC of the twin: every device of the instrument as an EPICS PV (pvAccess), with the name of the real PV.

At ESS each device is an EPICS PV, served by an IOC (the computer program in front of the hardware); the forwarder
relays the PVs to Kafka, where the file-writer and the live data reduction read them. The twin has no hardware: this
IOC serves the PVs of every device written in the real ESS file of the instrument (its f144 streams: the source name
is the PV name, e.g. ODIN-ChpSy1:Chop-WFMC-101:Spd_S) and gives them the current values of the twin, read from the
twin server (GET /epics) every `period` seconds.

The twin's motors (sample stage...) are full EPICS motor records, as at ESS: the fields VAL (target), RBV (readback),
DMOV, MOVN, HLM, LLM, EGU, DESC... (GET /epics/motors), so that NICOS drives them with the motor class of ESS
(nicos_ess.devices.epics.pva.motor.EpicsMotor). A new value written to VAL moves the twin's device (POST /epics/put);
the move is immediate (DMOV goes to 0, then back to 1 with the new RBV). The other PVs are read-only.

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


def table(twin, path="/epics"):
    with urllib.request.urlopen(f"{twin}{path}", timeout=60) as r:
        return json.loads(r.read())


def post(url, content):
    req = urllib.request.Request(url, data=json.dumps(content).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# (every PV starts with the time of the IOC start as its timestamp: the forwarder rejects updates stamped more than
# a year ago, e.g. at 0 = 1970, the default)
# fields of an EPICS motor record served for each motor, besides VAL, RBV and DMOV (type, value); those NICOS reads
# (nicos_ess.devices.epics.pva.motor.EpicsMotor._record_fields). Constant: the twin's motors are ideal (no limit
# switch, no error, always enabled, position reached exactly).
MOTOR_FIELDS = {"MOVN": ("i", 0), "MISS": ("i", 0), "HOMF": ("i", 0), "HOMR": ("i", 0), "VELO": ("d", 10.0),
                "OFF": ("d", 0.0), "LVIO": ("i", 0), "LLS": ("i", 0), "HLS": ("i", 0), "CNEN": ("i", 1),
                "SET": ("i", 0), "FOFF": ("i", 0), "STOP": ("i", 0), "STAT": ("i", 0), "SEVR": ("i", 0),
                "RDBD": ("d", 0.001)}


def stamped(nt, value, **kws):
    """A SharedPV of type nt starting at value, stamped now. The initial value must be made by the same nt object as
    the PV (p4p: post() requires the exact type of open())."""
    from p4p.server.thread import SharedPV
    return SharedPV(nt=nt, initial=nt.wrap(value, timestamp=time.time()), **kws)


def motor_pvs(m, types, twin, pvs, last):
    """The PVs of one motor record m (from GET /epics/motors) into pvs; VAL is writable."""
    from p4p.nt import NTScalar
    from p4p.server.thread import SharedPV
    base = m["record"]

    def number(field, code, value, meta=False):
        nt = NTScalar(code, display=meta, control=meta)
        v = nt.wrap(value, timestamp=time.time())
        if meta:
            v["display.units"] = m["unit"]
            v["display.description"] = m["desc"]
            v["display.limitLow"], v["display.limitHigh"] = m["low"], m["high"]
            v["control.limitLow"], v["control.limitHigh"] = m["low"], m["high"]
        return v, nt

    for field, (code, value) in MOTOR_FIELDS.items():
        v, nt = number(field, code, value)
        pvs[f"{base}.{field}"] = SharedPV(nt=nt, initial=v)
    for field, value in (("HLM", m["high"]), ("LLM", m["low"])):
        v, nt = number(field, "d", value)
        pvs[f"{base}.{field}"] = SharedPV(nt=nt, initial=v)
    for field, text in (("EGU", m["unit"]), ("DESC", m["desc"])):
        pvs[f"{base}.{field}"] = stamped(NTScalar("s"), text)
    v, nt = number("RBV", types.get(f"{base}.RBV", "d"), m["value"], meta=True)
    pvs[f"{base}.RBV"] = SharedPV(nt=nt, initial=v)
    pvs[f"{base}.DMOV"] = stamped(NTScalar(types.get(f"{base}.DMOV", "l")), 1)
    last[f"{base}.RBV"], last[f"{base}.DMOV"] = m["value"], 1

    class Target:                                   # handler of VAL: a new target moves the twin's device
        def put(self, pv, op):
            v = op.value()                          # (a Value, or the unwrapped number)
            target = float(v["value"] if hasattr(v, "getID") else v)
            if not m["low"] <= target <= m["high"]:
                op.done(error=f"{base}: {target} {m['unit']} outside [{m['low']}, {m['high']}]")
                return
            now = time.time()
            pvs[f"{base}.DMOV"].post(0, timestamp=now)
            pvs[f"{base}.MOVN"].post(1, timestamp=now)
            try:
                r = post(f"{twin}/epics/put", dict(record=base, value=target))
            except Exception as e:                  # noqa: BLE001  (busy: a count is running)
                pvs[f"{base}.DMOV"].post(1)
                pvs[f"{base}.MOVN"].post(0)
                op.done(error=f"{base}: the twin did not move ({e})")
                return
            now = time.time()
            pv.post(target, timestamp=now)
            pvs[f"{base}.RBV"].post(r["file_value"], timestamp=now)
            last[f"{base}.VAL"] = target
            last[f"{base}.RBV"] = r["file_value"]
            pvs[f"{base}.MOVN"].post(0, timestamp=now)
            pvs[f"{base}.DMOV"].post(1, timestamp=now)
            print(f"{base}.VAL = {target} {m['unit']}: {r['device']} = {r['value']}", flush=True)
            op.done()

    v, nt = number("VAL", types.get(f"{base}.VAL", "d"), m["value"], meta=True)
    pvs[f"{base}.VAL"] = SharedPV(nt=nt, initial=v, handler=Target())
    last[f"{base}.VAL"] = m["value"]


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
    try:
        motors = table(o.twin, "/epics/motors")
    except Exception:                               # noqa: BLE001  (a twin without motor records)
        motors = []
    types = {r["pv"]: r["type"] for r in rows}
    for m in motors:
        motor_pvs(m, types, o.twin, pvs, last)
    for r in rows:
        if r["pv"] in pvs:                      # one PV can be written in several places of the file
            continue
        pvs[r["pv"]] = stamped(NTScalar(r["type"]), r["value"])
        last[r["pv"]] = r["value"]
    conf = dict(LOCAL, **{k: os.environ[k] for k in LOCAL if k in os.environ})
    with Server(providers=[pvs], conf=conf, useenv=False):
        print(f"IOC ready: {len(pvs)} PVs, {len(motors)} motor records (twin {o.twin})", flush=True)
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
                    try:
                        pvs[pv].post(v, timestamp=now)
                    except Exception as e:      # noqa: BLE001  (one PV must not stop the IOC)
                        print(f"{pv}: update to {v!r} failed: {e}", file=sys.stderr, flush=True)
                    last[pv] = v


if __name__ == "__main__":
    main()
