"""What the student may change in a measurement already taken: its title only (a wrong name typed), in the logbook
of the session and in the NeXus file. Used by VirtualOdin.rename and VirtualLoki.rename (and measure_control.py)."""
import json
import os


def rename(folder, log_file, file, title):
    title = str(title).strip()
    if not title:
        raise ValueError("the new title is empty")
    name = os.path.basename(file)
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        raise ValueError(f"no file {name} in this session")
    import h5py
    with h5py.File(path, "r+") as f:
        if "entry/title" in f:
            del f["entry/title"]
        f["entry/title"] = title
    lines = []
    with open(log_file, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                lines.append(line)
                continue
            if (e.get("details") or {}).get("file") == name:
                e["details"]["title"] = title
                line = json.dumps(e, ensure_ascii=False) + "\n"
            lines.append(line)
    tmp = log_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    os.replace(tmp, log_file)
