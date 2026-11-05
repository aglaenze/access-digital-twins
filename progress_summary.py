"""Follow-up of a class (teachers): the answers of the students to the interactive questions (quiz.py), read from
their progress files, as a table and a CSV file.

Each student (or group) has a run folder (TWIN_RUN_ROOT: in the container the volume /data/twin, on a laptop
~/McStas_runs/twin) with progress/<quiz>.jsonl. Collect the folders of the class in one place (one sub-folder per
student, e.g. unzipped from their submissions), then:

    python progress_summary.py <folder of the class> [--csv summary.csv]
    python progress_summary.py ~/McStas_runs/twin                        # one student: yourself

For each student and each quiz: questions answered right, right at the first try, answers shown, solutions opened.
"""
import argparse
import csv
import glob
import json
import os


def read(progress_dir):
    out = {}
    for f in sorted(glob.glob(os.path.join(progress_dir, "*.jsonl"))):
        q = {}
        for line in open(f, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            s = q.setdefault(e["question"], dict(tries=0, right=False, first=None, opened=False))
            s["tries"] += 1
            if e.get("answer") == "opened":
                s["opened"] = True
                continue
            if s["first"] is None:
                s["first"] = bool(e.get("right"))
            s["right"] = s["right"] or bool(e.get("right"))
        out[os.path.splitext(os.path.basename(f))[0]] = q
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("folder")
    a.add_argument("--csv")
    o = a.parse_args()
    dirs = sorted(glob.glob(os.path.join(o.folder, "**", "progress"), recursive=True))
    rows = []
    for d in dirs:
        student = os.path.relpath(os.path.dirname(d), o.folder) or "."
        for quiz, qs in read(d).items():
            answered = [s for s in qs.values() if s["first"] is not None]
            rows.append(dict(student=student, quiz=quiz, questions=len(answered),
                             right=sum(s["right"] for s in answered), first_try=sum(bool(s["first"]) for s in answered),
                             solutions_opened=sum(s["opened"] for s in qs.values())))
    if not rows:
        print("no progress files found under", o.folder)
        return
    w = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in rows[0]}
    print("  ".join(k.ljust(w[k]) for k in w))
    for r in rows:
        print("  ".join(str(r[k]).ljust(w[k]) for k in w))
    if o.csv:
        with open(o.csv, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
        print("written", o.csv)


if __name__ == "__main__":
    main()
