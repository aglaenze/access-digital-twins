"""Model builders of the MSc notebooks: develop an analysis method without writing code.

The student chooses a model (from pictures), the range of the data it describes (a slider), the start values
(sliders: the model curve follows), then presses Fit. The page shows the fitted parameters with their uncertainties,
the residuals and the reduced χ², and keeps a table of every fit tried, so that models and ranges can be compared.
The Python lines that the choices wrote are shown under "See the code" (nothing has to be typed; the curious can
reuse them). The results are attributes of the builder, for the checks of the exercises.

    b = EdgeBuilder(lam, T, dT, expected=4.054)      # ODIN: one Bragg edge          -> b.lam_edge, b.dlam_edge
    b = GuinierBuilder(q, I, dI)                     # LoKI: Guinier analysis        -> b.rg, b.drg, b.i0
    b = ShapeBuilder(q, I, dI, start_radius=50)      # LoKI: a shape from sasmodels  -> b.radius, b.dradius, b.phi, b.dphi
"""
import html

import ipywidgets as w
import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from scipy.optimize import curve_fit, least_squares
from scipy.special import erfc

import live_view

STYLE = {"description_width": "170px"}


def _layout():
    """A new layout for each widget: a layout shared by several widgets would hide them all when one is hidden."""
    return w.Layout(width="520px")


def _slider(desc, value, lo, hi, step, fmt=".3f"):
    return w.FloatSlider(value=value, min=lo, max=hi, step=step, description=desc, readout_format=fmt,
                         continuous_update=True, layout=_layout(), style=STYLE)


def _pre(code):
    return w.HTML("<pre style='background:#F6F4EE;padding:8px;font-size:12px;line-height:1.35'>"
                  + html.escape(code) + "</pre>")


class _Builder:
    """Common frame: model choice, range, start values, Fit, results, history, code."""
    TITLE = ""

    def __init__(self):
        self.history = []                            # one row per fit
        self.out_plot, self.out_result = live_view.FigureImage(), w.Output()     # the plot follows the sliders
        self.code_box = w.VBox([])
        self.code_acc = w.Accordion(children=[self.code_box])
        self.code_acc.set_title(0, "See the code (what your choices wrote; nothing to type)")
        self.code_acc.selected_index = None
        self.fit_button = w.Button(description="Fit", button_style="success", icon="check")
        self.fit_button.on_click(lambda _: self.fit())
        self.fitted = None                           # the curve of the last fit (in the current settings)

    def _ui(self, choice_label, choice, extra):
        self.ui = w.VBox([w.HTML(f"<b>{choice_label}</b>"), choice, *extra, self.fit_button, self.out_plot,
                          self.out_result, self.code_acc])
        for c in self._controls():
            c.observe(live_view.throttled(self._changed), names="value")
        display(self.ui)
        self._changed()

    def _changed(self):
        self.fitted = None
        self._draw()
        self._show_code()

    def _show_code(self):
        self.code_box.children = [_pre(self.code())]

    def _history_html(self, cols):
        if not self.history:
            return ""
        head = "".join(f"<th style='padding:2px 8px;text-align:left'>{c}</th>" for c in cols)
        rows = "".join("<tr>" + "".join(f"<td style='padding:2px 8px'>{r.get(c, '')}</td>" for c in cols) + "</tr>"
                       for r in self.history)
        return f"<p><b>Your fits so far</b> (compare them):</p><table>{'<tr>' + head + '</tr>'}{rows}</table>"


# --------------------------------------------------------------------------- ODIN: a Bragg edge
EDGE_MODELS = {
    "sharp step": "a sudden jump at λ_edge, on a flat baseline",
    "step smoothed by the resolution": "the jump smoothed by the wavelength resolution (a Gaussian of width w): an "
                                       "error function, on a flat baseline",
    "smoothed step on a sloping baseline": "the same, on a baseline that varies slowly with λ (the other planes "
                                           "and the absorption)",
}
SHARP = 1e-4                                          # [Å] width of the "sharp" step (no resolution)


def edge_model(lam, lam_edge, width, base, slope, jump):
    """Transmission near a Bragg edge: a step of height `jump` at lam_edge, smoothed by a Gaussian of width `width`,
    on the baseline base + slope·(λ − lam_edge)."""
    return base + slope * (lam - lam_edge) + 0.5 * jump * erfc(-(lam - lam_edge) / (np.sqrt(2) * width))


class EdgeBuilder(_Builder):
    def __init__(self, lam, T, dT, expected, name="(110)"):
        super().__init__()
        ok = np.isfinite(T) & np.isfinite(dT) & (dT > 0)
        self.lam, self.T, self.dT = np.asarray(lam)[ok], np.asarray(T)[ok], np.asarray(dT)[ok]
        self.expected, self.name = float(expected), name
        self.lam_edge = self.dlam_edge = None
        e = self.expected
        near = (self.lam > e - 0.4) & (self.lam < e + 0.4)
        t_lo = float(np.median(self.T[near & (self.lam < e)])) if np.any(near & (self.lam < e)) else 0.5
        t_hi = float(np.median(self.T[near & (self.lam > e)])) if np.any(near & (self.lam > e)) else 0.7
        self.model = w.ToggleButtons(options=list(EDGE_MODELS), value="sharp step",
                                     style={"button_width": "250px"})
        self.model_help = w.HTML()
        self.window = w.FloatRangeSlider(value=(round(e - 1.0, 2), round(e + 1.0, 2)), min=round(e - 1.0, 2),
                                         max=round(e + 1.0, 2), step=0.01, description="range of λ [Å]",
                                         continuous_update=True, readout_format=".2f", layout=_layout(), style=STYLE)
        # start values: nothing chosen for the student (round values, not those of the data)
        self.p_edge = _slider("λ_edge (start) [Å]", round(e - 0.25, 1), e - 0.3, e + 0.3, 0.001)
        self.p_width = _slider("width w (start) [Å]", 0.1, 0.005, 0.2, 0.001)
        self.p_base = _slider("baseline (start)", 0.8, 0.0, 1.2, 0.005)
        self.p_slope = _slider("slope (start) [1/Å]", 0.0, -2.0, 2.0, 0.01)
        self.p_jump = _slider("jump (start)", 0.05, 0.0, 1.0, 0.005)
        self._ui("1 · Choose the shape of the edge", self.model,
                 [self.model_help, w.HTML("<b>2 · Choose the range of the data</b> (the edge, and a little on each "
                                          "side)"), self.window,
                  w.HTML("<b>3 · Start values</b> (move them until the dashed curve is close to the data), then Fit"),
                  self.p_edge, self.p_width, self.p_base, self.p_slope, self.p_jump])

    def _controls(self):
        return [self.model, self.window, self.p_edge, self.p_width, self.p_base, self.p_slope, self.p_jump]

    def _free(self):
        m = self.model.value
        return dict(width=m != "sharp step", slope=m == "smoothed step on a sloping baseline")

    def _params(self):
        f = self._free()
        return [self.p_edge.value, self.p_width.value if f["width"] else SHARP, self.p_base.value,
                self.p_slope.value if f["slope"] else 0.0, self.p_jump.value]

    def _changed(self):
        f = self._free()
        self.p_width.layout.display = None if f["width"] else "none"
        self.p_slope.layout.display = None if f["slope"] else "none"
        self.model_help.value = f"<i>{EDGE_MODELS[self.model.value]}.</i>"
        super()._changed()

    def _mask(self):
        a, b = self.window.value
        return (self.lam >= a) & (self.lam <= b)

    def _draw(self):
        m = self._mask()
        a, b = self.window.value
        view = (self.lam > a - 0.25) & (self.lam < b + 0.25)
        ll = np.linspace(a, b, 500)
        with self.out_plot:
            self.out_plot.clear_output(wait=True)
            fig, ax = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
            ax[0].errorbar(self.lam[view], self.T[view], self.dT[view], fmt=".", ms=3, lw=0.6, color="0.6")
            ax[0].errorbar(self.lam[m], self.T[m], self.dT[m], fmt=".", ms=3, lw=0.6, color="k", label="data used")
            ax[0].plot(ll, edge_model(ll, *self._params()), "--", color="tab:orange", lw=1.5, label="start values")
            if self.fitted is not None:
                ax[0].plot(ll, edge_model(ll, *self.fitted["p"]), color="tab:blue", lw=2, label="fit")
                r = (self.T[m] - edge_model(self.lam[m], *self.fitted["p"])) / self.dT[m]
                ax[1].plot(self.lam[m], r, ".", color="tab:blue", ms=3)
            ax[0].axvline(self.expected, color="0.7", ls=":", lw=1)
            ax[0].set(ylabel="transmission T", title=f"the {self.name} edge")
            ax[0].legend(loc="lower right"); ax[0].grid(alpha=0.3)
            ax[1].axhline(0, color="0.5", lw=0.8)
            for s in (-2, 2):
                ax[1].axhline(s, color="0.8", lw=0.8, ls="--")
            ax[1].set(xlabel="wavelength λ [Å]", ylabel="residual / σ")
            ax[1].grid(alpha=0.3)
            plt.tight_layout()

    def fit(self):
        m = self._mask()
        f = self._free()
        names = ["lam_edge"] + (["width"] if f["width"] else []) + ["base"] + (["slope"] if f["slope"] else []) + ["jump"]
        full = self._params()
        idx = {"lam_edge": 0, "width": 1, "base": 2, "slope": 3, "jump": 4}

        def model(lam, *x):
            p = list(full)
            for n, v in zip(names, x):
                p[idx[n]] = v
            return edge_model(lam, *p)

        p0 = [full[idx[n]] for n in names]
        lo = {"lam_edge": self.expected - 0.3, "width": 0.002, "base": -0.5, "slope": -5, "jump": 0.0}
        hi = {"lam_edge": self.expected + 0.3, "width": 0.3, "base": 2.0, "slope": 5, "jump": 2.0}
        with self.out_result:
            self.out_result.clear_output()
            if m.sum() < len(names) + 3:
                print("Too few data points in the range: widen it.")
                return
            try:
                x, cov = curve_fit(model, self.lam[m], self.T[m], p0=p0, sigma=self.dT[m], absolute_sigma=True,
                                   bounds=([lo[n] for n in names], [hi[n] for n in names]))
            except (RuntimeError, ValueError) as err:
                print(f"The fit did not converge ({err}). Move the start values closer to the data, or change the "
                      "range.")
                return
            err = np.sqrt(np.abs(np.diag(cov)))
            if not np.all(np.isfinite(err)) or err[0] > 0.05:
                print(f"The fit gives λ_edge = {x[0]:.4f} Å with an uncertainty of {err[0]:.3g} Å: it has not found a "
                      "well-defined edge (some parameters are not fixed by the data, e.g. a jump of almost zero, or "
                      "an edge at the border of the range). Look at the dashed curve: move the start values closer to "
                      "the data, narrow the range around one edge, then Fit again.")
                return
            p = list(full)
            for n, v in zip(names, x):
                p[idx[n]] = v
            chi2 = float(np.sum(((self.T[m] - edge_model(self.lam[m], *p)) / self.dT[m]) ** 2) / (m.sum() - len(names)))
            self.fitted = dict(p=p, names=names, x=x, err=err, chi2=chi2)
            self.lam_edge, self.dlam_edge = float(x[0]), float(err[0])
            a, b = self.window.value
            self.history.append({"model": self.model.value, "range [Å]": f"{a:.2f}–{b:.2f}",
                                 "λ_edge [Å]": f"{x[0]:.4f} ± {err[0]:.4f}", "χ²/n": f"{chi2:.2f}"})
            rows = "".join(f"<tr><td style='padding:2px 10px'>{n}</td><td>{v:.4f} ± {e:.4f}</td></tr>"
                           for n, v, e in zip(names, x, err))
            judge = ("good: the model describes the data within their error bars" if chi2 < 1.5 else
                     "the model misses something: look at the residuals (a pattern, not noise)")
            if not err[0] > 1e-6:
                judge += (". The position of a sharp step cannot really be fitted: moving it a little changes nothing "
                          "until it jumps over a data point, so its uncertainty (0) means nothing")
            display(w.HTML(f"<p><b>Fit</b> ({self.model.value}, {int(m.sum())} points)</p><table>{rows}</table>"
                           f"<p>reduced χ² = <b>{chi2:.2f}</b>: {judge}.</p>"
                           + self._history_html(["model", "range [Å]", "λ_edge [Å]", "χ²/n"])))
        self._draw()
        self._show_code()

    def code(self):
        f = self._free()
        a, b = self.window.value
        names = ["lam_edge"] + (["width"] if f["width"] else []) + ["base"] + (["slope"] if f["slope"] else []) + ["jump"]
        body = "base"
        if f["slope"]:
            body += " + slope * (lam - lam_edge)"
        w_ = "width" if f["width"] else f"{SHARP}"
        body += f" + 0.5 * jump * erfc(-(lam - lam_edge) / (np.sqrt(2) * {w_}))"
        p0 = {"lam_edge": self.p_edge.value, "width": self.p_width.value, "base": self.p_base.value,
              "slope": self.p_slope.value, "jump": self.p_jump.value}
        return "\n".join([
            "import numpy as np",
            "from scipy.optimize import curve_fit",
            "from scipy.special import erfc",
            "",
            f"# model: {self.model.value}",
            f"def edge(lam, {', '.join(names)}):",
            f"    return {body}",
            "",
            f"m = (lam >= {a:.2f}) & (lam <= {b:.2f}) & np.isfinite(T) & (dT > 0)      # the range you chose",
            f"p0 = [{', '.join(f'{p0[n]:.4g}' for n in names)}]      # your start values",
            "p, cov = curve_fit(edge, lam[m], T[m], p0=p0, sigma=dT[m], absolute_sigma=True)",
            "lam_edge, dlam_edge = p[0], np.sqrt(cov[0, 0])",
            f"chi2_n = np.sum(((T[m] - edge(lam[m], *p)) / dT[m]) ** 2) / (m.sum() - {len(names)})"])


# --------------------------------------------------------------------------- LoKI: Guinier
PLOTS = {"I against Q": ("Q [Å⁻¹]", "I [cm⁻¹]"), "log I against log Q": ("Q [Å⁻¹]", "I [cm⁻¹] (log-log)"),
         "ln I against Q²": ("Q² [Å⁻²]", "ln I")}


class GuinierBuilder(_Builder):
    def __init__(self, q, I, dI):
        super().__init__()
        ok = np.isfinite(I) & np.isfinite(dI) & (dI > 0) & (I > 0)
        self.q, self.I, self.dI = np.asarray(q)[ok], np.asarray(I)[ok], np.asarray(dI)[ok]
        self.rg = self.drg = self.i0 = None
        qmin = float(self.q.min())
        self.plot = w.ToggleButtons(options=list(PLOTS), value="I against Q", style={"button_width": "170px"})
        self.window = w.FloatRangeSlider(value=(round(qmin, 4), 0.15), min=round(qmin, 4), max=0.15, step=0.001,
                                         description="range of Q [Å⁻¹]", continuous_update=True,
                                         readout_format=".3f", layout=_layout(), style=STYLE)
        self._ui("1 · Which plot turns the Guinier law I = I(0)·exp(−Q²Rg²/3) into a straight line?", self.plot,
                 [w.HTML("<b>2 · Choose the range of Q</b> (the law holds for Q·Rg ≲ 1.3), then Fit a straight line"),
                  self.window])

    def _controls(self):
        return [self.plot, self.window]

    def _mask(self):
        a, b = self.window.value
        return (self.q >= a) & (self.q <= b)

    def _draw(self):
        m = self._mask()
        view = self.q < 0.2
        kind = self.plot.value
        with self.out_plot:
            self.out_plot.clear_output(wait=True)
            fig, ax = plt.subplots(figsize=(9, 4.6))
            if kind == "ln I against Q²":
                x, y, dy = self.q ** 2, np.log(self.I), self.dI / self.I
                ax.errorbar(x[view], y[view], dy[view], fmt=".", ms=3, lw=0.6, color="0.6")
                ax.errorbar(x[m], y[m], dy[m], fmt=".", ms=4, lw=0.6, color="k", label="data used")
                if self.fitted is not None:
                    xx = np.linspace(0, x[m].max() * 1.05, 100)
                    ax.plot(xx, self.fitted["p"][1] + self.fitted["p"][0] * xx, color="tab:blue", lw=2, label="fit")
                xmax = (1.8 * self.window.value[1]) ** 2          # the range chosen, and as much again around it
                vis = x <= xmax
                ax.set_xlim(0, xmax)
                if vis.any():
                    lo, hi = np.nanmin(y[vis] - dy[vis]), np.nanmax(y[vis] + dy[vis])
                    ax.set_ylim(lo - 0.1 * (hi - lo), hi + 0.1 * (hi - lo))
            else:
                ax.errorbar(self.q[view], self.I[view], self.dI[view], fmt=".", ms=3, lw=0.6, color="0.6")
                ax.errorbar(self.q[m], self.I[m], self.dI[m], fmt=".", ms=4, lw=0.6, color="k", label="data used")
                if kind == "log I against log Q":
                    ax.set(xscale="log", yscale="log")
            xl, yl = PLOTS[kind]
            ax.set(xlabel=xl, ylabel=yl)
            ax.legend(); ax.grid(alpha=0.3, which="both")
            plt.tight_layout()

    def fit(self):
        m = self._mask()
        with self.out_result:
            self.out_result.clear_output()
            if self.plot.value != "ln I against Q²":
                print(f"In the plot '{self.plot.value}' the Guinier law is not a straight line: a straight-line fit "
                      "there means nothing. Which plot makes it straight? (ln I = ln I(0) − (Rg²/3)·Q²)")
                return
            if m.sum() < 4:
                print("Too few points in the range: widen it.")
                return
            x, y, sy = self.q[m] ** 2, np.log(self.I[m]), self.dI[m] / self.I[m]
            p, cov = np.polyfit(x, y, 1, w=1 / sy, cov="unscaled")
            if p[0] >= 0:
                print("The line goes up: no Guinier decrease in this range. Choose the lowest Q.")
                return
            rg = float(np.sqrt(-3 * p[0]))
            drg = float(1.5 * np.sqrt(cov[0, 0]) / rg)
            i0 = float(np.exp(p[1]))
            chi2 = float(np.sum(((y - np.polyval(p, x)) / sy) ** 2) / (m.sum() - 2))
            self.fitted = dict(p=p)
            self.rg, self.drg, self.i0 = rg, drg, i0
            qrg = float(self.q[m].max() * rg)
            a, b = self.window.value
            self.history.append({"range [Å⁻¹]": f"{a:.3f}–{b:.3f}", "Rg [Å]": f"{rg:.1f} ± {drg:.1f}",
                                 "I(0) [cm⁻¹]": f"{i0:.2f}", "Q_max·Rg": f"{qrg:.2f}", "χ²/n": f"{chi2:.2f}"})
            warn = ("<span style='color:#B4501F'><b>Outside the validity of the law:</b> Q_max·Rg = "
                    f"{qrg:.2f} > 1.3. Lower the upper limit of the range, then fit again.</span>" if qrg > 1.3 else
                    f"Q_max·Rg = {qrg:.2f} ≤ 1.3: inside the validity of the law.")
            display(w.HTML(f"<p><b>Fit</b> ({int(m.sum())} points): Rg = <b>{rg:.1f} ± {drg:.1f} Å</b>, "
                           f"I(0) = {i0:.3f} cm⁻¹, reduced χ² = {chi2:.2f}</p><p>{warn}</p>"
                           + self._history_html(["range [Å⁻¹]", "Rg [Å]", "I(0) [cm⁻¹]", "Q_max·Rg", "χ²/n"])))
        self._draw()
        self._show_code()

    def code(self):
        a, b = self.window.value
        return "\n".join([
            "import numpy as np",
            f"# plot: {self.plot.value}",
            f"m = (q >= {a:.4f}) & (q <= {b:.4f}) & (I > 0) & (dI > 0)      # the range you chose",
            "x, y = q[m] ** 2, np.log(I[m])                  # ln I against Q²: a straight line",
            "p, cov = np.polyfit(x, y, 1, w=I[m] / dI[m], cov='unscaled')    # weights 1/σ(ln I) = I/dI",
            "rg = np.sqrt(-3 * p[0])                          # slope = −Rg²/3",
            "drg = 1.5 * np.sqrt(cov[0, 0]) / rg",
            "i0 = np.exp(p[1])",
            "print('Q_max·Rg =', q[m].max() * rg, '(must be ≲ 1.3)')"])


# --------------------------------------------------------------------------- LoKI: a shape (sasmodels)
SLD, SLD_SOLVENT = 3.47, 6.36                        # silica in D2O [1e-6 Å⁻²]
SHAPES = {"sphere": ("sphere", "a ball of radius R", [("radius", "radius R [Å]", 10, 200)]),
          "cylinder": ("cylinder", "a rod of radius R and length L",
                       [("radius", "radius R [Å]", 10, 200), ("length", "length L [Å]", 20, 1000)]),
          "ellipsoid": ("ellipsoid", "an ellipsoid of revolution (polar and equatorial radii)",
                        [("radius_polar", "polar radius [Å]", 10, 300), ("radius_equatorial", "equatorial radius [Å]",
                                                                         10, 300)])}


class ShapeBuilder(_Builder):
    def __init__(self, q, I, dI, start_radius=50.0):
        super().__init__()
        ok = np.isfinite(I) & np.isfinite(dI) & (dI > 0)
        self.q, self.I, self.dI = np.asarray(q)[ok], np.asarray(I)[ok], np.asarray(dI)[ok]
        self.radius = self.dradius = self.phi = self.dphi = None
        r0 = float(start_radius) if start_radius else 50.0
        self.shape = w.ToggleButtons(options=list(SHAPES), value="cylinder", style={"button_width": "130px"})
        self.shape_help = w.HTML()
        self.window = w.FloatRangeSlider(value=(float(self.q.min()), float(self.q.max())),
                                         min=float(self.q.min()), max=float(self.q.max()), step=0.001,
                                         description="range of Q [Å⁻¹]", continuous_update=True,
                                         readout_format=".3f", layout=_layout(), style=STYLE)
        self.p_scale = _slider("volume fraction φ (start)", 0.01, 0.0005, 0.05, 0.0005, ".4f")
        self.p_bg = _slider("background (start) [cm⁻¹]", 0.0, -0.05, 0.2, 0.001)
        self.use_bg = w.Checkbox(value=True, description="fit a flat background too", style=STYLE)
        self.sizes = {}
        for name, (_, _, pars) in SHAPES.items():
            for p, desc, lo, hi in pars:
                if p not in self.sizes:
                    v = min(max(r0 if "radius" in p else 4 * r0, lo), hi)
                    self.sizes[p] = _slider(f"{desc} (start)", round(v, 1), lo, hi, 0.5, ".1f")
        self._kernels = {}
        self._ui("1 · Choose the shape of the particles", self.shape,
                 [self.shape_help, w.HTML("<b>2 · Choose the range of Q</b>"), self.window,
                  w.HTML("<b>3 · Start values</b> (move them until the dashed curve is close to the data), then Fit"),
                  self.p_scale, *self.sizes.values(), self.use_bg, self.p_bg])

    def _controls(self):
        return [self.shape, self.window, self.p_scale, self.p_bg, self.use_bg, *self.sizes.values()]

    def _names(self):
        return [p for p, *_ in SHAPES[self.shape.value][2]]

    def _changed(self):
        names = self._names()
        for p, s in self.sizes.items():
            s.layout.display = None if p in names else "none"
        self.p_bg.layout.display = None if self.use_bg.value else "none"
        self.shape_help.value = f"<i>{SHAPES[self.shape.value][1]}; silica in D₂O (sld {SLD} and {SLD_SOLVENT}).</i>"
        super()._changed()

    def _mask(self):
        a, b = self.window.value
        return (self.q >= a) & (self.q <= b)

    def _model(self, q, values):
        from sasmodels.core import load_model
        from sasmodels.direct_model import call_kernel
        key = (self.shape.value, len(q), float(q[0]), float(q[-1]))
        if key not in self._kernels:
            self._kernels[key] = load_model(SHAPES[self.shape.value][0]).make_kernel([q])
        pars = dict(sld=SLD, sld_solvent=SLD_SOLVENT, **values)
        return call_kernel(self._kernels[key], pars)

    def _start(self):
        v = dict(scale=self.p_scale.value, background=self.p_bg.value if self.use_bg.value else 0.0)
        v.update({p: self.sizes[p].value for p in self._names()})
        return v

    def _draw(self):
        m = self._mask()
        with self.out_plot:
            self.out_plot.clear_output(wait=True)
            fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
            ax[0].errorbar(self.q, self.I, self.dI, fmt=".", ms=3, lw=0.6, color="0.65")
            ax[0].errorbar(self.q[m], self.I[m], self.dI[m], fmt=".", ms=3, lw=0.6, color="k", label="data used")
            qq = np.logspace(np.log10(self.q.min()), np.log10(self.q.max()), 300)
            try:
                ax[0].plot(qq, self._model(qq, self._start()), "--", color="tab:orange", lw=1.5, label="start values")
                if self.fitted is not None:
                    ax[0].plot(qq, self._model(qq, self.fitted["values"]), color="tab:blue", lw=2, label="fit")
                    r = (self.I[m] - self._model(self.q[m], self.fitted["values"])) / self.dI[m]
                    ax[1].plot(self.q[m], r, ".", color="tab:blue", ms=3)
            except Exception as err:                 # noqa: BLE001 (a model that cannot be computed)
                ax[0].set_title(f"model not computed: {err}")
            ax[0].set(xscale="log", yscale="log", ylabel="dΣ/dΩ [cm⁻¹ sr⁻¹]", ylim=(max(self.I[self.I > 0].min() / 3,
                                                                                         1e-4), None))
            ax[0].legend(loc="lower left"); ax[0].grid(alpha=0.3, which="both")
            ax[1].axhline(0, color="0.5", lw=0.8)
            for s in (-2, 2):
                ax[1].axhline(s, color="0.8", lw=0.8, ls="--")
            ax[1].set(xlabel="Q [Å⁻¹]", ylabel="residual / σ"); ax[1].grid(alpha=0.3, which="both")
            plt.tight_layout()

    def fit(self):
        m = self._mask()
        names = ["scale"] + self._names() + (["background"] if self.use_bg.value else [])
        start = self._start()
        x0 = np.array([start[n] for n in names])
        scale = np.array([0.01 if n == "scale" else (0.01 if n == "background" else 10.0) for n in names])
        q, I, dI = self.q[m], self.I[m], self.dI[m]

        def res(x):
            v = dict(start)
            v.update(zip(names, x))
            if not self.use_bg.value:
                v["background"] = 0.0
            return (self._model(q, v) - I) / dI

        with self.out_result:
            self.out_result.clear_output()
            if m.sum() < len(names) + 3:
                print("Too few points in the range: widen it.")
                return
            lo = [0.0 if n == "scale" else (-1.0 if n == "background" else 1.0) for n in names]
            hi = [1.0 if n == "scale" else (10.0 if n == "background" else 5000.0) for n in names]
            fit = least_squares(res, x0, x_scale=scale, bounds=(lo, hi))
            try:
                cov = np.linalg.inv(fit.jac.T @ fit.jac)
                err = np.sqrt(np.diag(cov))
            except np.linalg.LinAlgError:
                err = np.full(len(names), np.nan)
            chi2 = float(np.sum(fit.fun ** 2) / (m.sum() - len(names)))
            values = dict(start)
            values.update(zip(names, fit.x))
            if not self.use_bg.value:
                values["background"] = 0.0
            self.fitted = dict(values=values)
            res_ = dict(zip(names, zip(fit.x, err)))
            if self.shape.value == "sphere":
                self.radius, self.dradius = float(res_["radius"][0]), float(res_["radius"][1])
                self.phi, self.dphi = float(res_["scale"][0]), float(res_["scale"][1])
            a, b = self.window.value
            size = ", ".join(f"{n} = {v:.1f} ± {e:.1f} Å" for n, (v, e) in res_.items() if n not in ("scale", "background"))
            self.history.append({"shape": self.shape.value, "range [Å⁻¹]": f"{a:.3f}–{b:.3f}", "sizes": size,
                                 "φ": f"{res_['scale'][0]:.4f} ± {res_['scale'][1]:.4f}",
                                 "background": "fitted" if self.use_bg.value else "none", "χ²/n": f"{chi2:.2f}"})
            rows = "".join(f"<tr><td style='padding:2px 10px'>{n}</td><td>{v:.4g} ± {e:.2g}</td></tr>"
                           for n, (v, e) in res_.items())
            judge = ("good: the model describes the data within their error bars" if chi2 < 2 else
                     "the model misses something: look at the residuals (a pattern, not noise)")
            display(w.HTML(f"<p><b>Fit</b> ({self.shape.value}, {int(m.sum())} points)</p><table>{rows}</table>"
                           f"<p>reduced χ² = <b>{chi2:.2f}</b>: {judge}.</p>"
                           + self._history_html(["shape", "range [Å⁻¹]", "sizes", "φ", "background", "χ²/n"])))
        self._draw()
        self._show_code()

    def code(self):
        names = ["scale"] + self._names() + (["background"] if self.use_bg.value else [])
        start = self._start()
        a, b = self.window.value
        fixed = "" if self.use_bg.value else ", background=0.0"
        return "\n".join([
            "import numpy as np",
            "from scipy.optimize import least_squares",
            "from sasmodels.core import load_model",
            "from sasmodels.direct_model import call_kernel",
            "",
            f"m = (q >= {a:.4f}) & (q <= {b:.4f}) & np.isfinite(I) & (dI > 0)      # the range you chose",
            f"kernel = load_model('{SHAPES[self.shape.value][0]}').make_kernel([q[m]])",
            f"names = {names}",
            "",
            "def residuals(x):",
            f"    pars = dict(zip(names, x), sld={SLD}, sld_solvent={SLD_SOLVENT}{fixed})",
            "    return (call_kernel(kernel, pars) - I[m]) / dI[m]",
            "",
            f"x0 = [{', '.join(f'{start[n]:.4g}' for n in names)}]      # your start values",
            "fit = least_squares(residuals, x0)",
            "cov = np.linalg.inv(fit.jac.T @ fit.jac)             # uncertainties from the Jacobian",
            "for n, v, e in zip(names, fit.x, np.sqrt(np.diag(cov))):",
            "    print(n, v, '±', e)",
            "print('reduced chi2', np.sum(fit.fun ** 2) / (m.sum() - len(names)))"])
