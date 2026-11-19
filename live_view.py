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
    closed). clear_output() is accepted and does nothing (it can replace an Output widget).
    The figure is drawn at twice its resolution and shown at its normal size: sharp on every screen. The widget is
    hidden while it has no image (an empty image showed the icon of a broken picture)."""

    def __init__(self, dpi=100, **kw):
        kw.setdefault("layout", w.Layout(max_width="100%", display="none"))
        super().__init__(format="png", **kw)
        self.dpi = dpi

    def _set(self, fig):
        data = png(fig, 2 * self.dpi)
        width = int.from_bytes(data[16:20], "big") // 2              # PNG header: width in pixels, at normal size
        self.value = data
        self.layout.width = f"{width}px"
        self.layout.display = None

    def __enter__(self):
        self._before = set(plt.get_fignums())
        return self

    def __exit__(self, exc_type, exc, tb):
        new = [n for n in plt.get_fignums() if n not in self._before]
        if exc_type is None and new:
            self._set(plt.figure(new[-1]))
        for n in new:
            plt.close(n)
        return False

    def clear_output(self, wait=False):
        pass

    def show(self, fig):
        self._set(fig)


class FastFrame(w.Image):
    """Images that change many times per second (the slices of a tomography under the sliders): the matplotlib
    figure (axes, ticks, labels, colorbar) is drawn ONCE; each update only colors the arrays and puts them in the
    boxes of the axes, plus a few marks (lines, crosses), and sends the PNG: about 0.03 s instead of 0.5 s for a new
    figure.

        fig, (a, b) = plt.subplots(...); a.set(xlim=..., ylim=..., xlabel=...); a.set_aspect("equal"); ...
        fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 2), cmap="magma"), ax=[a, b])
        view = FastFrame(fig, [a, b], cmap="magma", vmin=0, vmax=2)
        view.draw([(array_a, extent_a), (array_b, extent_b)],
                  marks=[[("hline", z), ("cross", x, z)], [("hline", y), ("cross", x, y)]])
    array: rows along y from the bottom (origin "lower"), covering `extent` (x0, x1, y0, y1)."""

    def __init__(self, fig, axes, cmap="magma", vmin=0.0, vmax=1.0, dpi=150, **kw):
        import numpy as np
        kw.setdefault("layout", w.Layout(max_width="100%"))
        super().__init__(format="png", **kw)
        fig.set_dpi(dpi)
        fig.canvas.draw()
        bg = np.asarray(fig.canvas.buffer_rgba())[..., :3]
        H, W = bg.shape[:2]
        # cropped to what is drawn, plus a small margin (as bbox_inches="tight")
        tb = fig.get_tightbbox(fig.canvas.get_renderer())
        pad = int(0.08 * dpi)
        cx0, cx1 = max(0, int(tb.x0 * dpi) - pad), min(W, int(np.ceil(tb.x1 * dpi)) + pad)
        cy0, cy1 = max(0, int(H - tb.y1 * dpi) - pad), min(H, int(np.ceil(H - tb.y0 * dpi)) + pad)
        self.bg = bg[cy0:cy1, cx0:cx1].copy()
        self.boxes = []
        for ax in axes:
            bb = ax.get_window_extent()
            x0, x1 = int(round(bb.x0)) - cx0, int(round(bb.x1)) - cx0
            y0, y1 = int(round(H - bb.y1)) - cy0, int(round(H - bb.y0)) - cy0     # top-left origin
            self.boxes.append((x0, x1, y0, y1, ax.get_xlim(), ax.get_ylim()))
        self.lut = (plt.get_cmap(cmap)(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)
        self.vmin, self.vmax = vmin, vmax
        self.layout.width = f"{self.bg.shape[1] * 100 // dpi}px"           # shown at the size of a 100-dpi figure
        plt.close(fig)

    def draw(self, panels, marks=None):
        import numpy as np
        from PIL import Image, ImageDraw
        img = self.bg.copy()
        for (x0, x1, y0, y1, xl, yl), (a, ext) in zip(self.boxes, panels):
            a = np.asarray(a, float)
            ny, nx = a.shape
            xs = xl[0] + (np.arange(x0, x1) + 0.5 - x0) / (x1 - x0) * (xl[1] - xl[0])
            ys = yl[1] - (np.arange(y0, y1) + 0.5 - y0) / (y1 - y0) * (yl[1] - yl[0])
            ci = np.clip(((xs - ext[0]) / (ext[1] - ext[0]) * nx).astype(int), 0, nx - 1)
            ri = np.clip(((ys - ext[2]) / (ext[3] - ext[2]) * ny).astype(int), 0, ny - 1)
            u = np.clip((a - self.vmin) / (self.vmax - self.vmin), 0, 1)
            u = np.nan_to_num(u * 255).astype(np.uint8)
            img[y0:y1, x0:x1] = self.lut[u[ri[:, None], ci[None, :]]]
        pil = Image.fromarray(img)
        d = ImageDraw.Draw(pil)
        for (x0, x1, y0, y1, xl, yl), mk in zip(self.boxes, marks or []):
            px = lambda x: x0 + (x - xl[0]) / (xl[1] - xl[0]) * (x1 - x0)
            py = lambda y: y1 - (y - yl[0]) / (yl[1] - yl[0]) * (y1 - y0)
            s = max(2, (x1 - x0) // 300)
            for m in mk:
                if m[0] == "hline":
                    y = py(m[1])
                    for xa in range(x0, x1, 12):                                # dashed
                        d.line([(xa, y), (min(xa + 6, x1), y)], fill=(255, 255, 255), width=1)
                elif m[0] == "cross":
                    cx, cy, r = px(m[1]), py(m[2]), 9 * s
                    d.line([(cx - r, cy), (cx + r, cy)], fill=(0, 255, 255), width=s)
                    d.line([(cx, cy - r), (cx, cy + r)], fill=(0, 255, 255), width=s)
        buf = io.BytesIO()
        pil.save(buf, format="PNG", compress_level=1)
        self.value = buf.getvalue()


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
