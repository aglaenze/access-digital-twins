"""Step 4 of filewriter/README.md: compares the file written by the ESS file-writer during a job with the files the
twin wrote itself for the measurements of that job (one per count).

    python filewriter/compare.py <file of the file-writer> <twin file> [<twin file> ...]

Checked:
  * the neutrons: for every detector bank and monitor, the same events (pulse time, arrival time after the pulse to
    1 ns, pixel), all the measurements of the job together;
  * the devices: every value the twin recorded during its measurements is in the file-writer's file, at the same
    time;
  * the run: title, sample name, start and end times present.
Expected differences (reported, not errors): the file-writer has no entry/twin (the truths and settings of the twin
are not data of the instrument); pulses without neutrons are not written by the file-writer; it has one file per job,
the twin one per count.
"""
import sys

import h5py
import numpy as np

from twin_filewriter import DTYPES, streams


def _events(g):
    etz, idx = g["event_time_zero"][()].astype(np.int64), g["event_index"][()].astype(np.int64)
    n = len(g["event_id"])
    counts = np.diff(np.append(idx, n))
    return (np.repeat(etz, counts), np.round(g["event_time_offset"][()]).astype(np.int64),
            g["event_id"][()].astype(np.int64))


def _sorted(t0, tof, pid):
    order = np.lexsort((pid, tof, t0))
    return t0[order], tof[order], pid[order]


def compare(fw_file, twin_files, log=print):
    """Returns (number of differences, report lines)."""
    lines, bad = [], 0

    def say(ok, text):
        nonlocal bad
        bad += 0 if ok else 1
        lines.append(("  ok  " if ok else "  DIFF ") + text)
        log(lines[-1])

    with h5py.File(fw_file, "r") as fw:
        twins = [h5py.File(p, "r") for p in twin_files]
        try:
            st = streams(twins[0])
            # the neutrons
            for path, module, source, topic in st:
                if module != "ev44":
                    continue
                parts = [_events(t[path]) for t in twins]
                mine = _sorted(*[np.concatenate([p[i] for p in parts]) for i in range(3)])
                if path not in fw or "event_id" not in fw[path]:
                    say(len(mine[0]) == 0, f"{path} ({source}): not in the file-writer's file, "
                                           f"{len(mine[0])} events in the twin's")
                    continue
                theirs = _sorted(*_events(fw[path]))
                same = len(mine[0]) == len(theirs[0]) and all(np.array_equal(a, b) for a, b in zip(mine, theirs))
                say(same, f"{path} ({source} on {topic}): {len(theirs[0])} events written, {len(mine[0])} in the "
                          f"twin's files" + ("" if same else " -- not the same events"))
            # the devices
            n_values, missing = 0, []
            for path, module, source, topic in st:
                if module != "f144":
                    continue
                for t in twins:
                    g = t[path]
                    if "time" not in g or "value" not in g or g["value"].dtype.name not in DTYPES:
                        continue
                    t0 = min((int(t[p]["event_time_zero"][0]) for p, m, *_ in st
                              if m == "ev44" and len(t[p]["event_time_zero"])), default=None)
                    if t0 is None:
                        continue
                    times, values = g["time"][()].astype(np.int64), g["value"][()]
                    for k in np.nonzero(times >= t0)[0]:
                        n_values += 1
                        ok = path in fw and "time" in fw[path]
                        if ok:
                            ft, fv = fw[path]["time"][()].astype(np.int64), fw[path]["value"][()]
                            hit = np.nonzero(ft == times[k])[0]
                            ok = len(hit) > 0 and np.allclose(np.asarray(fv[hit[-1]], float),
                                                              np.asarray(values[k], float), rtol=1e-6, atol=0)
                        if not ok:
                            missing.append(f"{path} ({source}) at {times[k]}")
            say(not missing, f"device values recorded during the measurements: {n_values - len(missing)} of "
                             f"{n_values} in the file-writer's file" + ("" if not missing else
                                                                       ": missing " + "; ".join(missing[:5])))
            # the run
            e = fw["entry"]
            for k in ("title", "start_time", "end_time"):
                say(k in e, f"entry/{k}: " + (repr(e[k][()]) if k in e else "missing"))
            say("sample/name" in e, "entry/sample/name: " + (repr(e["sample/name"][()]) if "sample/name" in e
                                                             else "missing"))
            lines.append("  note entry/twin (truths and settings of the twin) is only in the twin's own files")
            log(lines[-1])
        finally:
            for t in twins:
                t.close()
    return bad, lines


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    n, _ = compare(sys.argv[1], sys.argv[2:])
    print("same data" if n == 0 else f"{n} difference(s)")
    sys.exit(1 if n else 0)
