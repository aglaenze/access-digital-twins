"""The end of an exercise: "Submit your work" (pages, notebooks, beamtimes).

    import submit
    submit.Submit("odin/exercises/iron_bragg_edges", "bsc", quiz=q)      # q: the quiz.Quiz of the page, if any

The button makes the file to hand in for this exercise: a zip with a summary (who, what, when, the score of the
questions), the logbook of the questions, the logbook of the measurements and, for notebooks, the student's notebooks
of the exercise. The file is kept (TWIN_RUN_ROOT/submissions/<user>/) and offered for download, to send to the teacher
(email, course page). The catalogue of the app then shows the exercise as submitted. A student may submit again: the
newest file counts. progress_summary.py reads the logbooks of a class.
"""
import base64
import datetime
import glob
import html
import io
import json
import os
import zipfile

import ipywidgets as w
from IPython.display import display

ROOT = os.path.dirname(os.path.abspath(__file__))           # twin/


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def _who():
    uid = os.environ.get("TWIN_USER", "")
    acc = {}
    if uid:
        try:
            with open(os.path.join(_run_root(), "progress", uid, "account.json"), encoding="utf-8") as f:
                acc = json.load(f)
        except (OSError, ValueError):
            pass
    return uid, acc.get("name") or os.environ.get("TWIN_USER_NAME", ""), acc.get("email") or os.environ.get("TWIN_USER_EMAIL", "")


class Submit:
    def __init__(self, exercise, mode, quiz=None, title=None):
        self.exercise, self.mode, self.quiz = exercise.strip("/"), mode, quiz
        self.title = title or self._title()
        btn = w.Button(description="Submit my work", icon="paper-plane", button_style="primary", layout=w.Layout(width="auto"))
        out = w.HTML()
        btn.on_click(lambda _: setattr(out, "value", self.make()))
        uid, name, _ = _who()
        who = f"as <b>{html.escape(name)}</b>" if name else "(no account: the file will not carry your name)"
        display(w.VBox([w.HTML(f'<div class="twq-q" style="background:#22354F">Submit</div>'
                               f'<p>When you are done, submit your work {who}: a file is made with your answers, your '
                               f'measurements{" and your notebooks" if mode != "bsc" else ""}. Download it and send it to your '
                               f'teacher. You can submit again later: the newest file counts.'
                               + (" Save your notebook first (<i>Save</i> in the app, or Ctrl+S)." if mode != "bsc" else "")
                               + '</p>'),
                        btn, out]).add_class("twq"))

    def _title(self):
        try:
            import yaml
            with open(os.path.join(ROOT, self.exercise, "exercise.yml"), encoding="utf-8") as f:
                return yaml.safe_load(f).get("title", self.exercise)
        except Exception:
            return self.exercise

    def make(self):
        uid, name, email = _who()
        now = datetime.datetime.now()
        instr = self.exercise.split("/")[0]
        ex = os.path.basename(self.exercise)
        rr = _run_root()
        prog = os.path.join(rr, "progress", *([uid] if uid else []))
        summary = self.quiz.summary_text() if self.quiz is not None else "No questions on this page."
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("summary.html", (
                f"<html><head><meta charset='utf-8'><title>{html.escape(self.title)}</title></head>"
                f"<body style='font-family:sans-serif'><h2>{html.escape(self.title)} ({self.mode})</h2>"
                f"<p><b>{html.escape(name or '(no name)')}</b> {html.escape(email)} · account {html.escape(uid or '-')}</p>"
                f"<p>Submitted {now:%Y-%m-%d %H:%M}</p><p>{html.escape(summary)}</p></body></html>"))
            if self.quiz is not None:
                for ext in (".jsonl", ".meta.json"):
                    f = os.path.join(prog, self.quiz.name + ext)
                    if os.path.isfile(f):
                        z.write(f, "questions/" + os.path.basename(f))
            sess = os.environ.get(f"{instr.upper()}_SESSION") or uid
            f = os.path.join(rr, instr, sess, "log.jsonl") if sess else ""
            if f and os.path.isfile(f):
                z.write(f, f"measurements_{instr}.jsonl")
            if self.mode != "bsc" and uid:
                for f in glob.glob(os.path.join(ROOT, "work", uid, f"{instr}_{ex}", "*.ipynb")):
                    z.write(f, "notebooks/" + os.path.basename(f))
        data = buf.getvalue()
        fname = f"{uid or 'student'}_{instr}_{ex}_{self.mode}_{now:%Y%m%d_%H%M}.zip"
        try:
            d = os.path.join(rr, "submissions", uid or "no_account")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, fname), "wb") as f:
                f.write(data)
            if uid:
                os.makedirs(prog, exist_ok=True)
                p = os.path.join(prog, "submitted.json")
                done = {}
                if os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        done = json.load(f)
                done[f"{self.exercise}:{self.mode}"] = now.isoformat(timespec="minutes")
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(done, f)
        except (OSError, ValueError):
            pass
        b64 = base64.b64encode(data).decode()
        return (f'<div class="twq-fb twq-ok"><b>Submitted</b> {now:%Y-%m-%d %H:%M}. {html.escape(summary)}<br>'
                f'<a download="{fname}" href="data:application/zip;base64,{b64}"><b>Download the file</b></a> '
                f'({len(data) // 1024 + 1} kB) and send it to your teacher.</div>')
