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


def _web():
    return os.environ.get("TWIN_WEB") == "1"


def _measurements(log):
    """Number of measurements and their total time (s), from the logbook of the measurements."""
    n, t = 0, 0.0
    try:
        with open(log, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("action") in ("count", "camera"):
                    n += 1
                    t += float(e.get("details", {}).get("t", 0) or 0)
    except OSError:
        pass
    return n, t


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
        self.comment = w.Textarea(placeholder="What did you think of this exercise? What was clear, what was hard, what "
                                              "would you change? (optional)",
                                  layout=w.Layout(width="100%", height="110px"))
        uid, name, _ = _who()
        if _web():
            text = ('<p>When you are done, write what you thought of the exercise below (optional) and click '
                    '<b>Submit my work</b>: your answers, the time you spent and your comment are sent to your teacher. '
                    '<b>Everything is anonymous</b>: no name is asked or kept, your comment is read without knowing who '
                    'wrote it. You can submit again later: the newest submission counts.</p>')
        else:
            who = f"as <b>{html.escape(name)}</b>" if name else "(no account: the file will not carry your name)"
            text = (f'<p>When you are done, you may write what you thought of the exercise below (optional), then '
                    f'submit your work {who}: a file is made with your answers, your '
                    f'measurements{" and your notebooks" if mode != "bsc" else ""}. Download it and send it to your '
                    f'teacher. You can submit again later: the newest file counts.'
                    + (" Save your notebook first (<i>Save</i> in the app, or Ctrl+S)." if mode != "bsc" else "")
                    + '</p>')
        display(w.VBox([w.HTML('<div class="twq-q">Submit</div>' + text),
                        w.HTML("<b>Your comments on the exercise</b>"
                               + (" (anonymous)" if _web() else "")), self.comment,
                        w.HBox([btn]), out]).add_class("twq"))      # (in a row: the button keeps its own width)

    def _send_web(self, uid, now, summary, comment, rr, instr):
        """Online version: the anonymous record of this submission for the statistics of the class (web_results)."""
        import web_results
        import web_user
        qs = [i for i in (self.quiz.items if self.quiz is not None else []) if i["kind"] != "solution"]
        page = os.path.basename(self.exercise)
        started = web_user.opened(page) or web_user.opened(self.exercise)
        minutes = None
        if started:
            minutes = round((now - datetime.datetime.fromisoformat(started)).total_seconds() / 60, 1)
        n, t = _measurements(os.path.join(rr, instr, os.environ.get(f"{instr.upper()}_SESSION") or uid, "log.jsonl"))
        web_results.send("submitted", uid, dict(
            exercise=self.exercise, mode=self.mode, title=self.title, started=started, minutes=minutes,
            summary=summary, questions=len(qs), right=sum(i["state"] == "right" for i in qs),
            measurements=n, measured_seconds=t, comment=comment,
            answers=[dict(id=i["id"], text=i["text"][:200], state=i["state"], tries=i["tries"],
                          answers=[str(a)[:80] for a in i["answers"]]) for i in (self.quiz.items if self.quiz else [])]))
        took = f" You worked on it for {minutes:.0f} minutes." if minutes else ""
        return (f'<div class="twq-fb twq-ok"><b>Thank you!</b> Your work was sent (anonymously) at {now:%H:%M}. '
                f'{html.escape(summary)}{took} You may change your answers or your comment and submit again.</div>')

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
        comment = self.comment.value.strip()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("summary.html", (
                f"<html><head><meta charset='utf-8'><title>{html.escape(self.title)}</title></head>"
                f"<body style='font-family:sans-serif'><h2>{html.escape(self.title)} ({self.mode})</h2>"
                f"<p><b>{html.escape(name or '(no name)')}</b> {html.escape(email)} · account {html.escape(uid or '-')}</p>"
                f"<p>Submitted {now:%Y-%m-%d %H:%M}</p><p>{html.escape(summary)}</p>"
                f"<h3>Comments on the exercise</h3><p>{html.escape(comment) or '(none)'}</p></body></html>"))
            z.writestr("submission.json", json.dumps(dict(            # read by progress_summary.py (teachers)
                name=name, email=email, account=uid, exercise=self.exercise, mode=self.mode, title=self.title,
                submitted=now.isoformat(timespec="minutes"), quiz=self.quiz.name if self.quiz is not None else None,
                summary=summary, comment=comment), indent=1))
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
        if _web():
            return self._send_web(uid, now, summary, comment, rr, instr)
        b64 = base64.b64encode(data).decode()
        return (f'<div class="twq-fb twq-ok"><b>Submitted</b> {now:%Y-%m-%d %H:%M}. {html.escape(summary)}<br>'
                f'A window opens to save the file: save it, then send it to your teacher (email, course page). '
                f'If no window opens: <a download="{fname}" href="data:application/zip;base64,{b64}" '
                f'data-twin-autodownload="1"><b>download the file</b></a> ({len(data) // 1024 + 1} kB).</div>')
