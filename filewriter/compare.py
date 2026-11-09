"""Step 4 of filewriter/README.md: compares the file written by the ESS file-writer during a job with the files the
twin wrote itself for the measurements of that job (one per count).

    python filewriter/compare.py <file of the file-writer> <twin file> [<twin file> ...]

Checked:
  * the neutrons: for every detector bank and monitor, the same events (pulse time, arrival time after the pulse to
    1 ns, pixel), all the measurements of the job together;
  * the devices: every value the twin recorded during its measurements is in the file-writer's file, at the same
    time;
  * every device has a value (the one at the start of the job at least);
  * the attributes of every stream group (a log can be a transformation: depends_on, vector...);
  * the run: title, sample name, start and end times present;
  * entry/twin, if the start command gave it (LoKI): the settings of the twin at the start of the job, as in its file.
Expected differences (reported, not errors): the file-writer has no truths of the twin (not data of the instrument),
and for ODIN no entry/twin at all; pulses without neutrons are not written by the file-writer; it has one file per job,
the twin one per count.
"""
import sys

import h5py
import numpy as np

from twin_filewriter import DTYPES, PER_PULSE, streams


def _events(g):
    etz, idx = g["event_time_zero"][()].astype(np.int64), g["event_index"][()].astype(np.int64)
    n = len(g["event_id"])
    counts = np.diff(np.append(idx, n))
    return (np.repeat(etz, counts), np.round(g["event_time_offset"][()]).astype(np.int64),
            g["event_id"][()].astype(np.int64))


def _sorted(t0, tof, pid):
    order = np.lexsort((pid, tof, t0))
    return t0[order], tof[order], pid[order]


def _plain(v):
    a = np.asarray(v)
    if a.dtype.kind in "SOU":
        return " ".join(x.decode() if isinstance(x, bytes) else str(x) for x in a.ravel())
    return a


def _same_value(a, b):
    a = a.decode() if isinstance(a, bytes) else a
    b = b.decode() if isinstance(b, bytes) else b
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    return bool(np.allclose(np.asarray(a, float), np.asarray(b, float), rtol=1e-9, atol=0))


def open_fw(path, wait=120):
    """Opens a file of the file-writer for reading, once the file-writer has closed it. It writes in SWMR mode, and
    after its "finished writing" message (wrdn) it opens the file once more to add the metadata (start and end
    times): until then a normal opening fails ("already open for write"), and a reader would make that last step
    fail (the file locked). So: normal opening, tried again for `wait` seconds; only then a reader in SWMR mode."""
    import time
    end = time.time() + wait
    while True:
        try:
            return h5py.File(path, "r")
        except OSError:
            if time.time() > end:
                return h5py.File(path, "r", swmr=True)
            time.sleep(2)


def compare(fw_file, twin_files, log=print):
    """Returns (number of differences, report lines)."""
    lines, bad = [], 0

    def say(ok, text):
        nonlocal bad
        bad += 0 if ok else 1
        lines.append(("  ok  " if ok else "  DIFF ") + text)
        log(lines[-1])

    with open_fw(fw_file) as fw:
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
            # every device has a value (at least the one given before the start of the job); not the logs of every
            # pulse (proton charge), which come with the measurements (checked above, as device values recorded)
            empty = []
            n_dev = 0
            for path, module, source, topic in st:
                if (module != "f144" or path in PER_PULSE or "value" not in twins[0][path]
                        or twins[0][path]["value"].shape[:1] == (0,)):
                    continue
                n_dev += 1
                if path not in fw or "value" not in fw[path] or fw[path]["value"].shape[:1] == (0,):
                    empty.append(f"{path} ({source} on {topic})")
            say(not empty, f"devices with a value in the file-writer's file: {n_dev - len(empty)} of {n_dev}" +
                ("" if not empty else "; none for " + "; ".join(empty[:8])))
            # the attributes of every stream group (e.g. depends_on, vector: a log that is a transformation)
            bad_attrs = []
            for path, module, source, topic in st:
                if path not in fw:
                    continue
                a, b = twins[0][path].attrs, fw[path].attrs
                for k in a:
                    if k not in b or not _same_value(_plain(a[k]), _plain(b[k])):
                        bad_attrs.append(f"{path}@{k}")
            say(not bad_attrs, f"attributes of the {len(st)} stream groups as in the twin's file" +
                ("" if not bad_attrs else ": missing or different " + ", ".join(bad_attrs[:6])))
            # the run
            e = fw["entry"]
            for k in ("title", "start_time", "end_time"):
                say(k in e, f"entry/{k}: " + (repr(e[k][()]) if k in e else "missing"))
            say("sample/name" in e, "entry/sample/name: " + (repr(e["sample/name"][()]) if "sample/name" in e
                                                             else "missing"))
            # the settings of the twin at the start of the job (entry/twin, given by the start command; LoKI)
            if "twin" in e:
                mine = twins[0]["entry"].get("twin")
                diff = [k for k in e["twin"] if mine is None or k not in mine
                        or not _same_value(e["twin"][k][()], mine[k][()])]
                say(not diff, f"entry/twin: {len(e['twin'])} settings of the twin at the start of the job, as in "
                              "the twin's first file" + ("" if not diff else ": different " + ", ".join(diff[:8])))
                lines.append("  note the truths of the twin (true_*) and the event sampling are only in its own files")
            else:
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
