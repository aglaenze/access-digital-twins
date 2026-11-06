"""For the teacher: the work submitted by a class, as one table (and a CSV file).

The students press *Submit my work* at the end of an exercise (submit.py): a zip file is made, which they send to the
teacher (email, course page). Put all the files received in one folder, then:

    python progress_summary.py <folder> [--csv summary.csv]

One line per submitted file (the newest file of a student for an exercise counts; older ones are listed with
"older"): name, email, exercise, level, date, questions answered right (at the first try), answers shown, solutions
opened. The folder may also hold unzipped folders with progress/<...>.jsonl (the "Export all my work" files, or the
data folder of a student, ~/McStas_runs/twin): they are read too, one line per logbook.
"""
import argparse
import csv
import glob
import io
import json
import os
import zipfile


def summarize(lines, total=None):
    """Logbook lines of quiz.py -> dict of counts."""
    q = {}
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        s = q.setdefault(e.get("question"), dict(tries=0, right=False, first=None, revealed=False, opened=False))
        if e.get("answer") == "opened":
            s["opened"] = True
            continue
        if e.get("answer") == "revealed":
            s["revealed"] = True
            continue
        s["tries"] += 1
        if s["first"] is None:
            s["first"] = bool(e.get("right"))
        s["right"] = s["right"] or bool(e.get("right"))
    answered = [s for s in q.values() if s["first"] is not None or s["revealed"]]
    return dict(questions=total or len(answered), right=sum(s["right"] for s in q.values()),
                first_try=sum(bool(s["first"]) for s in q.values()),
                shown=sum(s["revealed"] and not s["right"] for s in q.values()),
                solutions_opened=sum(s["opened"] for s in q.values()))


def from_zip(path):
    rows = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        sub = next((n for n in names if n.endswith("submission.json")), None)
        if sub:                                            # a file made by Submit
            info = json.loads(z.read(sub))
            logs = [n for n in names if n.startswith(os.path.dirname(sub)) and n.endswith(".jsonl") and "/questions/" in "/" + n]
            metas = [n for n in names if n.endswith(".meta.json")]
            total = json.loads(z.read(metas[0])).get("questions") if metas else None
            lines = [l for n in logs for l in io.TextIOWrapper(z.open(n), encoding="utf-8")]
            rows.append(dict(name=info.get("name", ""), email=info.get("email", ""), exercise=info.get("exercise", ""),
                             level=info.get("mode", ""), submitted=info.get("submitted", ""),
                             **(summarize(lines, total) if lines else dict(questions=0, right=0, first_try=0, shown=0,
                                                                          solutions_opened=0)),
                             file=os.path.basename(path)))
        else:                                              # a file of "Export all my work"
            for n in names:
                if "/progress/" in n and n.endswith(".jsonl"):
                    who = n.split("/")[0]
                    lines = list(io.TextIOWrapper(z.open(n), encoding="utf-8"))
                    rows.append(dict(name=who, email="", exercise=os.path.basename(n)[:-6], level="", submitted="",
                                     **summarize(lines), file=os.path.basename(path)))
    return rows


def from_folder(folder):
    rows = []
    for d in sorted(glob.glob(os.path.join(folder, "**", "progress"), recursive=True)):
        for f in sorted(glob.glob(os.path.join(d, "**", "*.jsonl"), recursive=True)):
            who = os.path.relpath(os.path.dirname(f), folder)
            with open(f, encoding="utf-8") as fh:
                rows.append(dict(name=who, email="", exercise=os.path.basename(f)[:-6], level="", submitted="",
                                 **summarize(fh), file=os.path.relpath(f, folder)))
    return rows


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("folder")
    a.add_argument("--csv")
    o = a.parse_args()
    rows = []
    for f in sorted(glob.glob(os.path.join(o.folder, "**", "*.zip"), recursive=True)):
        try:
            rows += from_zip(f)
        except (zipfile.BadZipFile, ValueError, KeyError) as e:
            print("skipped", f, e)
    rows += from_folder(o.folder)
    if not rows:
        print("nothing found under", o.folder)
        return
    newest = {}
    for r in rows:                                       # the newest submission of a student for an exercise counts
        k = (r["email"] or r["name"], r["exercise"], r["level"])
        if k not in newest or r["submitted"] > newest[k]["submitted"]:
            newest[k] = r
    for r in rows:
        r["status"] = "" if newest[(r["email"] or r["name"], r["exercise"], r["level"])] is r else "older"
    rows.sort(key=lambda r: (r["exercise"], r["level"], r["name"], r["submitted"]))
    cols = ["name", "email", "exercise", "level", "submitted", "questions", "right", "first_try", "shown",
            "solutions_opened", "status", "file"]
    w = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in cols}
    print("  ".join(k.ljust(w[k]) for k in cols))
    for r in rows:
        print("  ".join(str(r[k]).ljust(w[k]) for k in cols))
    if o.csv:
        with open(o.csv, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            wr.writerows(rows)
        print("written", o.csv)


if __name__ == "__main__":
    main()
