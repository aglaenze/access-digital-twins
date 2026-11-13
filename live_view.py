"""Figures that follow the sliders while they move (pages and notebooks of the twins).

    view = live_view.FigureImage()             # an image widget, drawn from a matplotlib figure
    def draw(_=None):
        with view:                             # the figure made inside the block becomes the image
            fig, ax = plt.subplots(); ...
    slider = w.FloatSlider(..., continuous_update=True)
    slider.observe(live_view.throttled(draw), "value")

A slider sends its value many times per second while it is dragged; drawing a figure takes about 0.1 s. throttled()
draws once per short delay, with the newest values (the positions in between are skipped), so that the image follows
the hand without falling behind. The figure is sent as a PNG image (no flicker: the old image stays until the new one
is ready), instead of being shown in an output area that is cleared and filled again.
"""
import io
import sys
import traceback

import ipywidgets as w
import matplotlib.pyplot as plt


def png(fig, dpi=100):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


class FigureImage(w.Image):
    """An image widget drawn from the matplotlib figure made inside `with view:` (the last one; the others are
    closed). clear_output() is accepted and does nothing (it can replace an Output widget)."""

    def __init__(self, dpi=100, **kw):
        kw.setdefault("layout", w.Layout(max_width="100%"))
        super().__init__(format="png", **kw)
        self.dpi = dpi

    def __enter__(self):
        self._before = set(plt.get_fignums())
        return self

    def __exit__(self, exc_type, exc, tb):
        new = [n for n in plt.get_fignums() if n not in self._before]
        if exc_type is None and new:
            self.value = png(plt.figure(new[-1]), self.dpi)
        for n in new:
            plt.close(n)
        return False

    def clear_output(self, wait=False):
        pass

    def show(self, fig):
        self.value = png(fig, self.dpi)


def throttled(fn, delay=0.05):
    """A callback for observe(): runs fn() once per `delay` seconds at most while the values change, with the
    newest values; at once where no event loop runs (a script, a test)."""
    pending = []

    def run():
        pending.clear()
        try:
            fn()
        except Exception:
            traceback.print_exc(file=sys.stderr)

    def callback(_=None):
        if pending:
            return
        try:
            from tornado.ioloop import IOLoop
            loop = IOLoop.current(instance=False)
        except Exception:
            loop = None
        if loop is None:
            run()
            return
        pending.append(1)
        loop.call_later(delay, run)

    return callback
