"""The results of a class on the online version: what each (anonymous) student did, for the teacher.

On the server (container/start.sh web), every page opened and every "Submit" makes one small JSON file:

    web_results/<student>/<time>_<kind>.json      kind: "opened" (a page) or "submitted" (answers, times, comment)

kept on the server and, if the server has a write token (HF_TOKEN, a secret of the Space) and a dataset
(TWIN_RESULTS_REPO, e.g. "agrgl/access-twin-results", private), sent there at once: the server of a Space may be
restarted (its disk is lost then), the dataset keeps everything. One file per event: ten students submitting at the
same moment never write the same file.

The teacher gets the table (one row per student and exercise, one column per question) with

    python web_results.py agrgl/access-twin-results results.xlsx     # needs: pip install huggingface_hub openpyxl
    python web_results.py <local folder web_results> results.csv     # from a copy of the folder

(the token of the teacher: `hf auth login` once, or HF_TOKEN).
"""
import datetime
import glob
import json
import os
import sys
import threading


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def send(kind, student, data):
    """Keeps one event (and sends it to the dataset, in the background). Never raises."""
    now = datetime.datetime.now()
    rec = dict(data, kind=kind, student=student, time=now.isoformat(timespec="seconds"))
    rel = f"{student}/{now:%Y%m%d_%H%M%S}_{now.microsecond:06d}_{kind}.json"
    path = os.path.join(_run_root(), "web_results", *rel.split("/"))
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1, ensure_ascii=False)
    except OSError:
        return rec
    repo, token = os.environ.get("TWIN_RESULTS_REPO"), os.environ.get("HF_TOKEN")
    if repo and token:
        threading.Thread(target=_upload, args=(path, rel, repo, token), daemon=True).start()
    return rec


def _upload(path, rel, repo, token):
    for attempt in range(4):
        try:
            from huggingface_hub import HfApi
            HfApi(token=token).upload_file(path_or_fileobj=path, path_in_repo="results/" + rel, repo_id=repo,
                                           repo_type="dataset", commit_message=f"result {rel}")
            return
        except Exception as e:                       # network, rate limit: try again a little later
            err = e
            threading.Event().wait(5 * (attempt + 1))
    try:
        with open(path + ".not_sent", "w", encoding="utf-8") as f:
            f.write(repr(err))
    except OSError:
        pass


# --------------------------------------------------------------------------- the table of the teacher
def load(source):
    """All the events: from a local folder, or from a dataset of Hugging Face (owner/name)."""
    if not os.path.isdir(source):
        from huggingface_hub import snapshot_download
        source = os.path.join(snapshot_download(source, repo_type="dataset"), "results")
    events = []
    for f in glob.glob(os.path.join(source, "**", "*.json"), recursive=True):
        try:
            with open(f, encoding="utf-8") as fh:
                events.append(json.load(fh))
        except (OSError, ValueError):
            pass
    return sorted(events, key=lambda e: e.get("time", ""))


def table(events):
    """One row per student and exercise (the last submission; also the students who opened a page without submitting)."""
    rows, opened = {}, {}
    for e in events:
        if e.get("kind") == "opened":
            opened.setdefault((e["student"], e.get("page", "")), e["time"])
    for e in events:
        if e.get("kind") != "submitted":
            continue
        row = dict(student=e["student"], exercise=e.get("title", e.get("exercise")), opened=e.get("started"),
                   submitted=e["time"], minutes=e.get("minutes"), score=e.get("summary"),
                   right=e.get("right"), questions=e.get("questions"), measurements=e.get("measurements"),
                   measured_seconds=e.get("measured_seconds"), comment=e.get("comment", ""))
        for q in e.get("answers", []):
            row[f"{q['id']} state"] = q["state"]
            row[f"{q['id']} tries"] = q["tries"]
            row[f"{q['id']} answers"] = " | ".join(map(str, q["answers"]))
        rows[(e["student"], e.get("exercise"))] = row
    for (s, page), t in opened.items():
        if not any(r["student"] == s for r in rows.values()):
            rows[(s, page)] = dict(student=s, exercise=page, opened=t, submitted="(not submitted)")
    return list(rows.values())


def write(rows, out):
    cols = []
    for r in rows:
        cols += [c for c in r if c not in cols]
    if out.lower().endswith(".xlsx"):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "results"
        ws.append(cols)
        for r in rows:
            ws.append([r.get(c, "") if not isinstance(r.get(c), (list, dict)) else json.dumps(r.get(c)) for c in cols])
        wb.save(out)
    else:
        import csv
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            wr.writerows(rows)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    rows = table(load(sys.argv[1]))
    print(f"{len(rows)} rows -> {write(rows, sys.argv[2])}")
