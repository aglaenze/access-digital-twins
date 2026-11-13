"""Interactive questions of the digital twins, for work without a teacher in the room (Voila pages and notebooks).

Every question can be answered several times. A wrong answer gets an explanation of why it is wrong; after a first
try the student can reveal the right answer and its explanation. Answers are kept in a small logbook
(TWIN_RUN_ROOT/progress/<user>/<quiz>.jsonl, <user> = the account of the app, TWIN_USER; without the app
TWIN_RUN_ROOT/progress/<quiz>.jsonl) and the student can download a report of the session. When the page or notebook is
opened again, the questions already answered right (or whose answer was shown) are shown as they were left.

    import quiz
    q = quiz.Quiz("odin_iron_bsc")                       # one per page or notebook
    q.choice("Which ...?", ["A", "B", "C"], answer=1,
             why={0: "A is wrong because ...", 2: "..."}, explanation="B, because ...")
    q.number("Which d?", value=2.027, tol=0.03, unit="Å",
             mistakes=[(4.054, "this is λ itself: λ_max = 2d")], hints=["Bragg: λ = 2 d sin θ"],
             explanation="d = λ_edge / 2 = ...")
    q.solution("Task 6.2", code="...", explanation="...")   # a worked solution behind a button (MSc)
    q.report()                                               # score and "Download my report"

Texts may contain $...$ formulas (rendered by MathJax in the app, by Jupyter in notebooks).
"""
import base64
import hashlib
import html
import json
import os
import random
import time

import ipywidgets as w
from IPython.display import display

# ipykernel with Python 3.14 sometimes logs "Task was destroyed but it is pending!" and "coroutine
# 'Kernel.shell_main' was never awaited" while the app runs the cells: harmless, but shown in red under a question
import logging as _logging
import warnings as _warnings
_logging.getLogger("asyncio").setLevel(_logging.CRITICAL)
_warnings.filterwarnings("ignore", message="coroutine .* was never awaited", category=RuntimeWarning)

GREEN, RED, GREY = "#E3F1EC", "#F8E5E1", "#F2F2F2"
CSS = """<style>
.twq {border: 1px solid #D9DDE5; border-radius: 10px; padding: 10px 16px; margin: 10px 0; background: #FBFBFD}
.twq-q {font-weight: 600; margin-bottom: 4px}
.twq-fb {border-radius: 8px; padding: 8px 12px; margin-top: 6px; line-height: 1.45}
.twq-ok {background: #E3F1EC; border-left: 4px solid #2A7D6F}
.twq-no {background: #F8E5E1; border-left: 4px solid #B4562B}
.twq-ans {background: #EEF1F7; border-left: 4px solid #1D2433}
.twq-sol pre {background: #F5F5F5; padding: 8px; border-radius: 6px; overflow-x: auto}
</style>"""
_css_shown = [False]


def _css():
    if not _css_shown[0]:
        display(w.HTML(CSS))
        _css_shown[0] = True


def _md(text):
    """Small markdown subset (bold, italic, code) to HTML, formulas left for MathJax."""
    try:
        import mistune
        return mistune.html(text)
    except Exception:
        return "<p>" + html.escape(text) + "</p>"


def _box(kind, text):
    return f'<div class="twq-fb twq-{kind}">{_md(text)}</div>'


def _hint(item, hints):
    """The hint for the current wrong try: the first one, then more and more precise ones (the last one repeats)."""
    if not hints:
        return ""
    n = sum(1 for a in item["answers"]) - (1 if item["state"] == "right" else 0)
    return "<br>**Hint:** " + hints[min(max(n, 1), len(hints)) - 1]


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def progress_dir(user=None):
    """Folder of the logbooks of one student: progress/<user> (the account of the app), or progress/ without the app."""
    user = os.environ.get("TWIN_USER", "") if user is None else user
    return os.path.join(_run_root(), "progress", *([user] if user else []))


def _previous(log):
    """What the logbook says of each question: {id: {"right": bool, "revealed": bool, "answer": last, "tries": n}}."""
    out = {}
    try:
        with open(log, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                s = out.setdefault(e.get("question"), dict(right=False, revealed=False, answer=None, tries=0))
                if e.get("answer") == "revealed":
                    s["revealed"] = True
                    continue
                s["tries"] += 1
                if e.get("right"):
                    s["right"], s["answer"] = True, e.get("answer")
    except OSError:
        pass
    return out


class Quiz:
    """The questions of one page or notebook."""

    def __init__(self, name):
        self.name = name
        self.items = []          # dicts: id, kind, text, state ("open", "right", "revealed"), tries, answers
        self.log = os.path.join(progress_dir(), f"{name}.jsonl")
        self.before = _previous(self.log)       # the answers of earlier sessions

    # ------------------------------------------------------------------ bookkeeping
    def _record(self, item, answer, right):
        item["tries"] += 1
        item["answers"].append(answer)
        if right and item["state"] == "open":
            item["state"] = "right"
        try:
            os.makedirs(os.path.dirname(self.log), exist_ok=True)
            with open(self.log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "question": item["id"],
                                    "answer": answer, "right": right}) + "\n")
        except OSError:
            pass

    def _revealed(self, item):
        if item["state"] == "open":
            item["state"] = "revealed"
            try:
                os.makedirs(os.path.dirname(self.log), exist_ok=True)
                with open(self.log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "question": item["id"],
                                        "answer": "revealed", "right": False}) + "\n")
            except OSError:
                pass

    def _new(self, kind, text):
        item = dict(id=f"Q{len(self.items) + 1}", kind=kind, text=text, state="open", tries=0, answers=[])
        self.items.append(item)
        if kind != "solution":          # the number of questions, for the progress shown in the catalogue of the app
            n = sum(i["kind"] != "solution" for i in self.items)
            meta = self.log[:-len(".jsonl")] + ".meta.json"
            try:
                old = 0
                if os.path.isfile(meta):
                    with open(meta, encoding="utf-8") as f:
                        old = json.load(f).get("questions", 0)
                if n > old:
                    os.makedirs(os.path.dirname(meta), exist_ok=True)
                    with open(meta, "w", encoding="utf-8") as f:
                        json.dump({"questions": n}, f)
            except (OSError, ValueError):
                pass
        b = self.before.get(item["id"])
        if b:
            item["tries"] = b["tries"]
            item["state"] = "right" if b["right"] else ("revealed" if b["revealed"] else "open")
        return item

    # ------------------------------------------------------------------ question types
    def choice(self, text, options, answer, why=None, hints=(), explanation="", title=None):
        """Multiple choice. answer: index of the right option (or a set of indices: several right options, ticked
        with checkboxes). why: {index of a wrong option: why it is wrong}. hints: clues toward the right answer, one
        more precise at each wrong try. explanation: shown when right or revealed."""
        _css()
        item = self._new("choice", text)
        multi = not isinstance(answer, int)
        right = set(answer) if multi else {answer}
        why = why or {}
        # the options in a shuffled order (the right one is not always first), the same at every opening: drawn from
        # the name of the quiz and the question
        rng = random.Random(hashlib.sha256(f"{self.name}|{text}".encode()).hexdigest())
        order = list(range(len(options)))
        rng.shuffle(order)
        if not multi:
            # the right option at the place used least so far in this quiz (ties drawn): over a page, the right
            # answers are spread over all the places, never first every time
            used = getattr(self, "_right_places", {})
            n = len(options)
            least = min(used.get(k, 0) for k in range(n))
            place = rng.choice([k for k in range(n) if used.get(k, 0) == least])
            used[place] = used.get(place, 0) + 1
            self._right_places = used
            wrong = [k for k in order if k != answer]
            order = wrong[:place] + [answer] + wrong[place:]
        new_index = {old: new for new, old in enumerate(order)}
        options = [options[k] for k in order]
        right = {new_index[k] for k in right}
        why = {new_index[k]: v for k, v in why.items()}
        head = w.HTMLMath(f'<div class="twq-q">{html.escape(title or item["id"])}</div>{_md(text)}')
        if multi:
            boxes = [w.Checkbox(description=o, indent=False, layout=w.Layout(width="auto")) for o in options]
            picker = w.VBox(boxes)
            chosen = lambda: {k for k, b in enumerate(boxes) if b.value}
        else:
            picker = w.RadioButtons(options=list(options), value=None, layout=w.Layout(width="auto"))
            chosen = lambda: set() if picker.index is None else {picker.index}
        check = w.Button(description="Check", button_style="primary", icon="check")
        reveal = w.Button(description="Show the answer", icon="eye", layout=w.Layout(display="none"))
        fb = w.HTMLMath()

        def on_check(_):
            c = chosen()
            if not c:
                fb.value = _box("no", "Choose an answer first.")
                return
            ok = c == right
            self._record(item, sorted(options[k] for k in c), ok)
            if ok:
                fb.value = _box("ok", "**Right.** " + explanation)
                reveal.layout.display = "none"
                return
            parts = [why[k] for k in sorted(c) if k in why]
            if multi and c < right:
                parts.append("Some right answers are missing.")
            elif multi and not parts:
                parts.append("At least one of the ticked answers is wrong.")
            fb.value = _box("no", "**Not quite.** " + " ".join(parts or ["Think again, and try another answer."])
                            + _hint(item, hints))
            reveal.layout.display = ""

        def show_answer():
            good = "; ".join(f"**{options[k]}**" for k in sorted(right))
            fb.value = _box("ans", f"Answer: {good}. {explanation}")
            reveal.layout.display = "none"

        def on_reveal(_):
            self._revealed(item)
            show_answer()

        check.on_click(on_check)
        reveal.on_click(on_reveal)
        b = self.before.get(item["id"])
        if item["state"] == "right":            # answered right in an earlier session
            given = b["answer"] or []
            if multi:
                for k, box_ in enumerate(boxes):
                    box_.value = options[k] in given
            elif given and given[0] in options:
                picker.value = given[0]
            fb.value = _box("ok", "**Right** (answered earlier). " + explanation)
        elif item["state"] == "revealed":
            show_answer()
        elif b and b["tries"]:
            reveal.layout.display = ""
        display(w.VBox([head, picker, w.HBox([check, reveal]), fb]).add_class("twq"))

    def number(self, text, value, tol, unit="", mistakes=(), hints=(), explanation="", rel=False, title=None):
        """A value to compute. tol: accepted distance to value (relative if rel). mistakes: [(value of a typical
        wrong answer, what went wrong)], recognized within the same tolerance. hints: given one by one, try after try."""
        _css()
        item = self._new("number", text)
        head = w.HTMLMath(f'<div class="twq-q">{html.escape(title or item["id"])}</div>{_md(text)}')
        box = w.Text(placeholder="your value", layout=w.Layout(width="140px"))     # empty at first; 4,05 = 4.05
        check = w.Button(description="Check", button_style="primary", icon="check")
        reveal = w.Button(description="Show the answer", icon="eye", layout=w.Layout(display="none"))
        fb = w.HTMLMath()
        close = lambda x, v: abs(x - v) <= (tol * abs(v) if rel else tol)

        def on_check(_):
            try:
                x = float(box.value.strip().replace(",", ".").replace(" ", "").replace("−", "-"))
            except ValueError:
                fb.value = _box("no", "Type a number first (for example 4.05).")
                return
            ok = close(x, value)
            self._record(item, x, ok)
            if ok:
                fb.value = _box("ok", f"**Right** ({value:.4g} {unit}). " + explanation)
                reveal.layout.display = "none"
                return
            known = next((txt for v, txt in mistakes if close(x, v)), None)
            msg = known or ("too large." if x > value else "too small.")
            msg = msg if msg.rstrip()[-1:] in ".!?" else msg + "."
            fb.value = _box("no", f"**Not quite**: {x:g} {unit} is {msg}" + _hint(item, hints))
            reveal.layout.display = ""

        def show_answer():
            fb.value = _box("ans", f"Answer: **{value:.4g} {unit}**. {explanation}")
            reveal.layout.display = "none"

        def on_reveal(_):
            self._revealed(item)
            show_answer()

        check.on_click(on_check)
        reveal.on_click(on_reveal)
        b = self.before.get(item["id"])
        if item["state"] == "right":            # answered right in an earlier session
            box.value = f"{b['answer']:g}" if isinstance(b["answer"], (int, float)) else ""
            fb.value = _box("ok", f"**Right** ({value:.4g} {unit}, answered earlier). " + explanation)
        elif item["state"] == "revealed":
            show_answer()
        elif b and b["tries"]:
            reveal.layout.display = ""
        display(w.VBox([head, w.HBox([box, w.Label(unit)]), w.HBox([check, reveal]), fb]).add_class("twq"))

    def solution(self, title, code="", explanation=""):
        """A worked solution behind a button (MSc notebooks: after a check cell). Opening it is recorded."""
        _css()
        item = self._new("solution", title)
        btn = w.Button(description=f"Show the solution ({title})", icon="lightbulb-o", layout=w.Layout(width="auto"))
        out = w.HTMLMath()

        def on_click(_):
            item["state"] = "revealed"
            self._record(item, "opened", False)
            body = _md(explanation) if explanation else ""
            if code:
                body += f"<pre>{html.escape(code.strip())}</pre>"
            out.value = f'<div class="twq-fb twq-ans twq-sol">{body}</div>'
            btn.layout.display = "none"

        btn.on_click(on_click)
        display(w.VBox([btn, out]))

    # ------------------------------------------------------------------ the session
    def summary_text(self):
        qs = [i for i in self.items if i["kind"] != "solution"]
        right = sum(i["state"] == "right" for i in qs)
        first = sum(i["state"] == "right" and i["tries"] == 1 for i in qs)
        revealed = sum(i["state"] == "revealed" for i in qs)
        return (f"{right} of {len(qs)} questions answered right ({first} at the first try), {revealed} answers shown, "
                f"{sum(i['kind'] == 'solution' and i['state'] == 'revealed' for i in self.items)} solutions opened.")

    def report(self, extra=""):
        """Score and a "Download my report" link (an HTML file: questions, answers given, logbook text in extra)."""
        _css()
        btn = w.Button(description="My results", icon="list", button_style="info")
        out = w.HTML()

        def on_click(_):
            rows = "".join(
                f"<tr><td>{i['id']}</td><td>{html.escape(i['text'][:140])}</td><td>{i['state']}</td>"
                f"<td>{i['tries']}</td><td>{html.escape(str(i['answers'][-3:]))}</td></tr>" for i in self.items)
            doc = (f"<html><head><meta charset='utf-8'><title>{self.name}</title></head><body style='font-family:"
                   f"sans-serif'><h2>{self.name}</h2><p>{time.strftime('%Y-%m-%d %H:%M')}</p><p>{self.summary_text()}"
                   f"</p><table border=1 cellpadding=4 style='border-collapse:collapse'><tr><th>#</th><th>question"
                   f"</th><th>state</th><th>tries</th><th>last answers</th></tr>{rows}</table>"
                   f"<pre>{html.escape(extra)}</pre></body></html>")
            b64 = base64.b64encode(doc.encode("utf-8")).decode()
            out.value = (f'<div class="twq-fb twq-ans">{html.escape(self.summary_text())} '
                         f'<a download="{self.name}_report.html" href="data:text/html;base64,{b64}">'
                         f'<b>Download my report</b></a></div>')

        btn.on_click(on_click)
        display(w.VBox([btn, out]))
