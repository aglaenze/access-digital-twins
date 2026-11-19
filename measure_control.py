"""Measurements of the guided pages that can be stopped, with the settings locked while they run.

    import measure_control as mc
    ctl = mc.Control(odin, button, lock=[setup, shutter, sample, exposure, title])
    ctl.on_click(take)                    # instead of button.on_click(take); take(_) as before
    display(w.VBox([..., w.HBox([button, ctl.stop]), ctl.status, ...]))

While a measurement runs: the button and the settings in `lock` are disabled (the settings of a measurement cannot be
changed while it runs), a Stop button appears; Stop asks the instrument to cancel (VirtualOdin.cancel): the
measurement ends at its next step and nothing is recorded (no file, no line in the logbook; of a series, the images
already taken stay).

How: the measurement runs in a thread, so that the page (the kernel) still receives the click on Stop. A thread cannot
print into an Output widget of the page (its messages lose their way), so what it prints goes to `ctl.status`, an HTML
box under the button (a stdout that routes by thread); figures shown with live_view.FigureImage and the values of
widgets work from a thread as usual.
"""
import html
import io
import sys
import threading

import ipywidgets as w


class _ThreadStdout(io.TextIOBase):
    """sys.stdout that sends what a registered thread prints to its sink, and the rest where it went before."""

    def __init__(self, base):
        self.base, self.sinks = base, {}

    def write(self, s):
        sink = self.sinks.get(threading.get_ident())
        if sink is None:
            return self.base.write(s)
        sink(s)
        return len(s)

    def flush(self):
        try:
            self.base.flush()
        except Exception:
            pass

    def __getattr__(self, name):            # isatty, encoding... of the stream of the kernel
        return getattr(self.base, name)


_AFTER = []


def after_each(fn):
    """fn() is called after every measurement of the page (stopped or not): the lists of files refresh themselves
    (analysis_chain.file_viewer)."""
    _AFTER.append(fn)


def _router():
    if not isinstance(sys.stdout, _ThreadStdout):
        sys.stdout = _ThreadStdout(sys.stdout)
    return sys.stdout


def rename_box(instrument, refresh=None):
    """"Rename a measurement": the files of the session (newest first), a new title, a button. Only the title
    changes (instrument.rename: logbook and NeXus file); refresh() is called after (the page's list of files).
    Returns (box, update): call update() after each new measurement to refresh the choices."""
    import json
    import os
    pick = w.Dropdown(description="Measurement", layout=w.Layout(width="440px"), style={"description_width": "110px"})
    new = w.Text(placeholder="the right title", description="New title", layout=w.Layout(width="440px"),
                 style={"description_width": "110px"})
    go = w.Button(description="Rename", icon="pen", layout=w.Layout(width="auto"))
    msg = w.HTML()

    def update():
        opts = []
        try:
            with open(instrument.log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    d = e.get("details") or {}
                    if d.get("file"):
                        opts.append((f"{d['file']}: {d.get('title') or '(no title)'}", d["file"]))
        except OSError:
            pass
        seen, uniq = set(), []
        for label, f in reversed(opts):          # newest first; one entry per file (its last title)
            if f not in seen:
                seen.add(f)
                uniq.append((label, f))
        keep = pick.value
        pick.options = uniq
        if uniq:
            pick.value = keep if keep in [f for _, f in uniq] else uniq[0][1]

    def do(_):
        try:
            if not pick.value:
                raise ValueError("no measurement to rename yet")
            instrument.rename(pick.value, new.value)
            msg.value = f"<span style='color:#0E7C70'>Renamed: {html.escape(pick.value)} is now “{html.escape(new.value.strip())}”.</span>"
            new.value = ""
            update()
            if refresh:
                refresh()
        except Exception as e:
            msg.value = f"<span style='color:#9B2C1C'>{html.escape(str(e))}</span>"

    go.on_click(do)
    update()
    box = w.VBox([w.HTML("<b>Wrong title?</b> Rename a measurement (only its title: its settings and data cannot "
                         "be changed)."), pick, w.HBox([new, go]), msg])
    return box, update


class Control:
    def __init__(self, instrument, button, lock=(), stopped="Measurement stopped: nothing of it was recorded."):
        """stopped: the line written when Stop was used (None: the page writes its own, e.g. for a series whose
        images already taken stay)."""
        self.instrument, self.button, self.lock, self.stopped = instrument, button, list(lock), stopped
        self.stop = w.Button(description="Stop", icon="stop", button_style="danger",
                             tooltip="Stop this measurement: nothing of it is recorded",
                             layout=w.Layout(width="auto", display="none"))
        self.status = w.HTML()
        self.stop.on_click(self._stop)
        self.running = False

    def _stop(self, _=None):
        self.stop.disabled = True
        self.stop.description = "Stopping..."
        self.instrument.cancel()

    def say(self, text):
        """A line in the status box (from the measurement or from the page)."""
        lines = (self.status.value or "").replace("<pre class='tw-status'>", "").replace("</pre>", "")
        self.status.value = "<pre class='tw-status'>" + (lines + html.escape(text))[-4000:] + "</pre>"

    def clear(self):
        self.status.value = ""

    def on_click(self, fn):
        self.button.on_click(lambda b: self.start(fn, b))

    def start(self, fn, *args):
        if self.running:
            return
        self.running = True
        states = [(c, c.disabled) for c in [self.button, *self.lock]]
        for c, _ in states:
            c.disabled = True
        self.stop.disabled, self.stop.description = False, "Stop"
        self.stop.layout.display = None
        self.clear()
        self.instrument.reset_cancel()
        router = _router()

        def work():
            router.sinks[threading.get_ident()] = self.say
            try:
                fn(*args)
            except Exception as e:                 # the pages catch their errors; this is the last resort
                self.say(f"{type(e).__name__}: {e}\n")
            finally:
                router.sinks.pop(threading.get_ident(), None)
                if self.instrument._stop.is_set() and self.stopped:
                    self.say(self.stopped + "\n")
                for c, was in states:
                    c.disabled = was
                self.stop.layout.display = "none"
                self.running = False
                for f in _AFTER:
                    try:
                        f()
                    except Exception:
                        pass

        threading.Thread(target=work, daemon=True).start()
