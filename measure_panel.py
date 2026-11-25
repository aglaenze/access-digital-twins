"""How the student measures in an MSc notebook: in NICOS (as at ESS) or with a panel in the notebook (as on the BSc
pages), chosen inside the exercise and changed at any time.

    import measure_panel
    measure_panel.Panel("odin", proposal="1234", samples=["iron_plate"])

Either way the files go to the folder of the proposal (data/<instrument>/<year>/<proposal>/raw), read by the rest of
the notebook: NICOS writes odin_job_NNNNNN.hdf (the file writer), the panel odin_NNNNNN.nxs (the twin itself, as NICOS
where the file writer is not running); odin_reduction.data_files reads both.

The steps of NICOS are text cells of the notebook marked with <span class="twin-nicos"></span>: with the panel chosen,
a style sheet hides them (the question cells stay). The choice is kept with the student's progress.
"""
import datetime
import json
import os
import sys
import time

import ipywidgets as w
from IPython.display import clear_output, display

ROOT = os.path.dirname(os.path.abspath(__file__))
HIDE_NICOS = "<style>.jp-Cell:has(.twin-nicos), .jp-Notebook-cell:has(.twin-nicos) { display: none !important; }</style>"

# the look of the panel: cards of settings, the detectors with their buttons, the colors of the app
PANEL_CSS = """<style>
.tw-panel {gap: 14px; margin-top: 6px}
.tw-intro {color: #3A423B; line-height: 1.5}
.tw-grid {display: grid !important; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; width: 100%;
  overflow: visible !important}
.tw-card {background: #fff; border: 1px solid #D5D9D1; border-radius: 12px; padding: 12px 14px 14px; gap: 6px;
  box-shadow: 0 1px 3px rgba(11, 22, 38, .05); min-width: 0; overflow: visible !important}
.tw-card .widget-inline-hbox {width: auto !important; max-width: 100%; min-width: 0}
.tw-card .widget-inline-hbox input, .tw-card .widget-inline-hbox select {min-width: 0}
.tw-card .widget-toggle-buttons {display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
  align-items: center}
.tw-card .widget-toggle-buttons > .widget-label {display: block !important; text-align: right; flex: 0 0 auto;
  width: var(--tw-label, 110px); margin-right: 8px}
.tw-card .widget-toggle-buttons > div {display: flex; flex: 1 1 auto; flex-wrap: nowrap; min-width: 0}
.tw-card .widget-toggle-buttons .widget-toggle-button {width: auto; min-width: 72px; padding: 0 12px}
.tw-card.tw-act {border-top: 3px solid #F2C230}
.tw-h {font-weight: 700; font-size: 14px; letter-spacing: .6px; text-transform: uppercase; color: #1B1F24}
.tw-note {font-size: 15px; color: #566057; line-height: 1.45; margin-top: 2px}
.tw-panel .widget-label {color: #3A423B}
.tw-panel input, .tw-panel select {border: 1px solid #BFC5BC !important; border-radius: 8px !important; background: #fff}
.tw-panel .widget-toggle-buttons .widget-toggle-button {border: 1px solid #BFC5BC; background: #fff; color: #566057;
  font-weight: 600; border-radius: 8px; box-shadow: none; margin-right: 6px}
.tw-panel .widget-toggle-buttons .widget-toggle-button.mod-active {background: #FFF4D6; border-color: #1B1F24;
  color: #1B1F24; box-shadow: inset 0 -2px 0 #F2C230}
.tw-panel .jupyter-button:not(.widget-toggle-button) {height: 40px; border-radius: 10px; font-weight: 600; padding: 0 16px;
  border: 1px solid #BFC5BC; background: #fff; color: #1B1F24; box-shadow: none}
.tw-panel .jupyter-button.mod-primary {background: #1B1F24; border-color: #1B1F24; color: #fff}
.tw-panel .jupyter-button:disabled {opacity: .55}
.tw-panel .progress-bar {background-color: #2FB862 !important}
.tw-row {gap: 10px; align-items: center; flex-wrap: wrap}
.tw-out {background: #F4F5F1; border-left: 4px solid #F2C230; border-radius: 8px; padding: 2px 12px}
.tw-loading {padding: 18px; text-align: center; color: #566057; font-weight: 600}
</style>"""


def _card(title, *children, note="", action=False):
    """A card of the panel: its title, an optional short text, its widgets."""
    head = [w.HTML(f'<div class="tw-h">{title}</div>' + (f'<div class="tw-note">{note}</div>' if note else ""))]
    box = w.VBox(head + list(children))
    box.add_class("tw-card")
    if action:
        box.add_class("tw-act")
    return box


def _fit(*widgets, label=110):
    """Widgets of a card: as wide as the card, their labels aligned."""
    for x in widgets:
        x.style.description_width = f"{label}px"
    return list(widgets)


def _row(*widgets):
    r = w.HBox(list(widgets))
    r.add_class("tw-row")
    return r


def _grid(*cards):
    g = w.Box(list(cards))
    g.add_class("tw-grid")
    return g


def _layout(intro, *parts):
    v = w.VBox([w.HTML(PANEL_CSS + f'<div class="tw-intro">{intro}</div>'), *parts])
    v.add_class("tw-panel")
    return v


def _run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def proposal_folder(instrument, proposal):
    return os.path.join(_run_root(), "data", instrument, str(datetime.date.today().year), str(proposal), "raw")


def _pref_file(instrument, proposal):
    user = os.environ.get("TWIN_USER", "")
    return os.path.join(_run_root(), "progress", *([user] if user else []), f"measure_{instrument}_{proposal}.json")


class Panel:
    def __init__(self, instrument, proposal, samples=None):
        self.instrument, self.proposal = instrument, str(proposal)
        self.samples = list(samples or [])
        self.folder = proposal_folder(instrument, proposal)
        self.style = w.HTML()
        self.how = w.ToggleButtons(options=[("In NICOS (as at ESS)", "nicos"), ("Here, with a panel", "panel")],
                                   value=self._pref(), style={"button_width": "260px", "font_weight": "600"})
        self.how.add_class("twin-how")
        self.box = w.VBox()
        self.how.observe(lambda c: self._show(), "value")
        # the two choices side by side, large, in the middle of the page (as the button that opens NICOS below them)
        css = ("<style>.twin-how .widget-toggle-buttons, .twin-how.widget-toggle-buttons {flex-wrap: nowrap}"
               ".twin-how button.widget-toggle-button {height: 46px; font-size: 15px; border-radius: 10px; margin: 0 6px}"
               "</style>")
        display(w.VBox([w.HTML(css + "<b>How do you measure?</b> Either way, your files go to the folder of proposal "
                               f"{self.proposal}, and the rest of the notebook reads them."),
                        w.HBox([self.how], layout=w.Layout(justify_content="center", margin="8px 0 4px 0")),
                        self.style, self.box]))
        self._show()

    def _ipython_display_(self):
        # the panel shows itself when made: nothing more when it is the last line of a cell (no "<Panel at 0x...>")
        pass

    def _pref(self):
        try:
            with open(_pref_file(self.instrument, self.proposal), encoding="utf-8") as f:
                return json.load(f).get("how", "nicos")
        except (OSError, ValueError):
            return "nicos"

    def _save_pref(self):
        p = _pref_file(self.instrument, self.proposal)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"how": self.how.value}, f)
        except OSError:
            pass

    def _show(self):
        self._save_pref()
        if self.how.value == "nicos":
            self.style.value = ""
            out = w.Output()
            with out:
                import nb_tools
                nb_tools.nicos(self.instrument)
            self.box.children = [w.HTML("Follow the steps below, in the window of NICOS."), out]
        else:
            # the button of NICOS gone at once, a word while the panel is built (the instrument takes a few seconds)
            self.style.value = HIDE_NICOS
            self.box.children = [w.HTML('<div class="tw-loading">Loading the panel of the instrument…</div>')]
            panel = {"odin": self._odin_panel, "loki": self._loki_panel}.get(self.instrument)
            self.box.children = [panel() if panel else w.HTML(f"No panel for {self.instrument}: measure in NICOS.")]

    # ------------------------------------------------------------------ ODIN
    def _odin_panel(self):
        for p in (ROOT, os.path.join(ROOT, "odin")):
            if p not in sys.path:
                sys.path.insert(0, p)
        from odin_virtual import VirtualOdin
        import odin_viz as viz
        if not hasattr(self, "odin"):
            self.odin = VirtualOdin(session=os.environ.get("ODIN_SESSION", "student"))
            self.odin.use_folder(self.folder)
        odin = self.odin
        st = odin.status()
        # nothing mounted for the student: mounting the sample is the first step (a sample of another exercise
        # still on the stage is taken off)
        samples = self.samples or [n for n in odin.samples() if n != "none"]
        if st["sample"] not in samples and st["sample"] != "none":
            odin.move(sample="none")
            st = odin.status()
        sample = w.Dropdown(options=[("— none (nothing mounted) —", "none")] + [(n, n) for n in samples],
                            value=st["sample"], description="Sample")
        shutter = w.ToggleButtons(options=["closed", "open"], value=st["shutter"], description="Shutter")
        stage = w.BoundedFloatText(value=st["stage_x"] * 1000, min=-500, max=500, step=1, description="Stage x (mm)")
        choppers = w.Dropdown(options=[("WFM", "wfm"), ("natural (band-pass + T0)", "natural"), ("white (none)", "white")],
                              value=st["choppers"], description="Choppers")
        delta = w.Dropdown(options=[0.10, 0.30, 0.45], value=st["wfm_delta"], description="WFM δ (m)")
        pinhole = w.Dropdown(options=[0.01, 0.02, 0.03, 0.04], value=st["pinhole"], description="Pinhole (m)")
        import source_power                  # the power of the source: read-only (the teacher, or the app)
        power = source_power.control(odin, width="auto")
        import sample_library as sl
        lib = sl.load("odin")
        max_kN = max((float((lib.get(n) or {}).get("load", {}).get("max_kN", 0)) for n in samples), default=0)
        load = w.FloatSlider(value=float(st.get("load") or 0), min=0, max=max_kN or 1, step=1, readout_format=".0f",
                             description="Load (kN)", continuous_update=False)
        t = w.BoundedFloatText(value=30, min=1, max=3600, step=1, description="Time (s)")
        title = w.Text(placeholder="e.g. open beam", description="Title")
        go = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
        # every measurement runs through measure_control (a Stop button, the settings locked while it runs; it runs
        # in a thread: what it prints goes to `status`, the live image to a FigureImage, not to an Output)
        import live_view
        from odin_virtual import Cancelled
        status = w.HTML()
        live_lab = w.HTML()
        live_img = live_view.FigureImage()
        out = w.VBox([status, live_lab, live_img]).add_class("tw-out")
        last_draw = [0.0]

        def live_update(image, toa, t_done, t_total, step):
            """The detector image and the arrival times filling up during a count (as odin_viz.LiveCount)."""
            import matplotlib.pyplot as plt
            import numpy as np
            if step == "preparing":
                live_lab.value = "Counting... (the first count of a session prepares the instrument: a few seconds)"
            elif step == "writing":
                live_lab.value = f"Counted {t_total:.0f} s: writing the file..."
            else:
                live_lab.value = f"Counting... {t_done:.0f} s / {t_total:.0f} s"
            if step == "counting" and t_done < t_total and time.time() - last_draw[0] < 0.8:
                return
            last_draw[0] = time.time()
            with live_img:
                fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[1, 1.4]))
                im = ax[0].imshow(image, origin="lower", extent=[-7.05, 7.05, -7.05, 7.05], cmap="inferno", vmin=0,
                                  vmax=max(float(np.max(image)), 1.0))
                ax[0].set(xlabel="x (mm)", ylabel="y (mm)",
                          title=f"Detector after {t_done:.1f} s ({float(np.sum(image)):,.0f} neutrons)")
                fig.colorbar(im, ax=ax[0], label="counts per pixel")
                edges = np.linspace(0, viz.PULSE_MS, len(toa) + 1)
                ax[1].step(0.5 * (edges[1:] + edges[:-1]), toa, where="mid", color="tab:blue")
                ax[1].set(xlabel="time since the last pulse (ms)", ylabel="counts",
                          ylim=(0, max(float(np.max(toa)), 1) * 1.05), title="Arrival times (raw data, before reduction)")
                ax[1].grid(alpha=0.3)
                plt.tight_layout()

        def count(_):
            try:
                settings()
                f = odin.count(float(t.value), title=title.value or "", progress=live_update)
                live_lab.value = f"File written: {os.path.basename(f)}"
                print(f"written in the folder of proposal {self.proposal}: {os.path.basename(f)}")
            except Cancelled:
                live_lab.value = ""
            except Exception as e:
                print("Error:", e)
        # the integrating camera (white-beam radiography, tomography): as radiograph() and tomography() in NICOS
        cam = w.Button(description="Camera image", icon="camera", button_style="primary", layout=w.Layout(width="auto"))
        cam_px = w.Dropdown(options=[("standard (128 px, 110 µm)", 128), ("high resolution (512 px, 27.5 µm)", 512)],
                            value=128, description="Resolution")
        step = w.Dropdown(options=[("12° (15 images)", 12.0), ("6° (30 images)", 6.0), ("3° (60 images)", 3.0)],
                          value=6.0, description="Tomography", layout=w.Layout(width="250px"))
        tomo = w.Button(description="Run the tomography", icon="sync", layout=w.Layout(width="auto"))
        bar = w.IntProgress(value=0, min=0, max=1, layout=w.Layout(width="160px", display="none"))

        def settings():
            odin.move(sample=sample.value, shutter=shutter.value, stage_x=stage.value / 1000, choppers=choppers.value,
                      wfm_delta=delta.value, pinhole=pinhole.value)
            if max_kN:
                odin.move(load=float(load.value))

        def image(_):
            try:
                settings()
                f = odin.camera(float(t.value), title=title.value or "", pixels=cam_px.value)
                print(f"camera image written in the folder of proposal {self.proposal}: {os.path.basename(f)} "
                      f"({odin.last_n_counts:,} counts)")
            except Cancelled:
                pass
            except Exception as e:
                print("Error:", e)

        def tomography(_):
            angles = [k * step.value for k in range(int(round(180 / step.value)))]
            done = []
            try:
                settings()
                bar.max, bar.value, bar.layout.display = len(angles), 0, ""
                bar.style.description_width = "initial"
                t_start = time.time()

                def advance(k, n, f):
                    done.append(f)
                    bar.value = k
                    el = time.time() - t_start
                    fmt = lambda s: f"{int(s // 60)} min {int(s % 60):02d} s" if s >= 60 else f"{int(s)} s"
                    bar.description = f"{k}/{n}" + (f" · {fmt(el / k * (n - k))} left" if 0 < k < n else "")
                try:
                    files = odin.tomography(angles, float(t.value), title=title.value or "tomography",
                                            progress=advance, pixels=cam_px.value)
                finally:
                    odin.move(stage_rot=0.0)
                print(f"{len(files)} images of {float(t.value):g} s written ({os.path.basename(files[0])} to "
                      f"{os.path.basename(files[-1])})")
            except Cancelled:
                print(f"Tomography stopped after {len(done)} of {len(angles)} images (those stay in the folder).")
            except Exception as e:
                print("Error:", e)

        # the Timepix3 in histogram mode (long exposures: counts per wavelength bin), as tof_histogram() in NICOS
        hist = w.Button(description="Histogram image (Timepix3)", icon="th-large", layout=w.Layout(width="auto"))

        def histogram(_):
            try:
                settings()
                f = odin.tof_image(float(t.value), title=title.value or "")
                print(f"histogram image written in the folder of proposal {self.proposal}: {os.path.basename(f)} "
                      f"({odin.last_n_counts:,} counts)")
            except Cancelled:
                pass
            except Exception as e:
                print("Error:", e)

        t.max = 4 * 3600
        actions = [(go, count), (hist, histogram), (cam, image), (tomo, tomography)]     # Control: further down
        locked = [sample, shutter, stage, choppers, delta, pinhole, *([load] if max_kN else []), t, title, cam_px, step,
                  *source_power.lockable(power)]
        # operando samples (a battery on its cycler): the time of the cycle, and a film of the cycle with the camera
        operando = [n for n in samples if (lib.get(n) or {}).get("operando")]
        op_box = []
        if operando:
            cyc = w.BoundedFloatText(value=float(st.get("cycle_time", 0.0)), min=0, max=55, step=0.5,
                                     description="Cycle time (h)")
            every = w.Dropdown(options=[("every 5 h", 5.0), ("every 2.5 h", 2.5), ("every hour", 1.0)], value=2.5,
                               description="Film", layout=w.Layout(width="250px"))
            film = w.Button(description="Film the cycle (camera)", icon="film", layout=w.Layout(width="auto"))
            fbar = w.IntProgress(value=0, min=0, max=1, layout=w.Layout(width="160px", display="none"))

            def film_cycle(_):
                try:
                    settings()
                    times = [round(k * every.value, 2) for k in range(int(55 / every.value + 1e-9) + 1)]
                    fbar.max, fbar.value, fbar.layout.display = len(times), 0, ""
                    for tc in times:
                        odin.move(cycle_time=float(tc))
                        odin.camera(float(t.value), title=f"{title.value or 'cell'} {tc:g} h", pixels=cam_px.value)
                        fbar.value += 1
                    cyc.value = times[-1]
                    print(f"{len(times)} camera images of {float(t.value):g} s, from 0 to {times[-1]:g} h of the cycle")
                except Cancelled:
                    print(f"Film stopped after {fbar.value} images (those stay in the folder).")
                except Exception as e:
                    print("Error:", e)

            actions.append((film, film_cycle))
            locked += [cyc, every]
            cyc.observe(lambda c: odin.move(cycle_time=float(c["new"])), "value")
            op_box = [_card("Battery cycler", *_fit(cyc), _row(every, film, fbar),
                            note="The time since the start of the cycle (the state of the cell), and a film of the "
                                 "cycle: one camera image of the time set above at each step.")]
        # polarized imaging (samples with a field map): as polarimetry() and polarization_matrix() in NICOS
        magnetic = [n for n in samples if (lib.get(n) or {}).get("field")]
        pol_box = []
        if magnetic:
            rot = w.BoundedFloatText(value=float(st["stage_rot"]), min=-180, max=180, step=1, description="Rotation (°)")
            polz = w.ToggleButtons(options=["out", "in"], value=st["polarizer"], description="Polarizer")
            s_in = w.Dropdown(options=["+x", "-x", "+y", "-y", "+z", "-z"], value=st["spin_in"], description="Spin in")
            s_out = w.Dropdown(options=["x", "y", "z"], value=st["spin_out"], description="Analyzer")
            one = w.Button(description="Polarized image", icon="compass", layout=w.Layout(width="auto"))
            full = w.Button(description="Polarization matrix (18 images)", icon="th", layout=w.Layout(width="auto"))
            pbar = w.IntProgress(value=0, min=0, max=18, layout=w.Layout(width="160px", display="none"))

            def pol_settings():
                settings()
                odin.move(stage_rot=float(rot.value), polarizer=polz.value, spin_in=s_in.value, spin_out=s_out.value)

            def pol_one(_):
                try:
                    pol_settings()
                    f = odin.polarimetry(float(t.value), title=title.value or "")
                    print(f"polarized image written in the folder of proposal {self.proposal}: {os.path.basename(f)} "
                          f"(spin in {s_in.value}, analyzer {s_out.value}, {odin.last_n_counts:,} counts)")
                except Cancelled:
                    pass
                except Exception as e:
                    print("Error:", e)

            def pol_full(_):
                try:
                    polz.value = "in"
                    pbar.value, pbar.layout.display = 0, ""
                    pol_settings()
                    files = odin.polarization_matrix(float(t.value), title=title.value or "",
                                                     progress=lambda k, n, f: setattr(pbar, "value", k))
                    print(f"18 polarized images of {float(t.value):g} s written "
                          f"({os.path.basename(files[('+x', 'x')])} to {os.path.basename(files[('-z', 'z')])})")
                except Cancelled:
                    print(f"Matrix stopped after {pbar.value} of 18 images (those stay in the folder).")
                except Exception as e:
                    print("Error:", e)

            actions += [(one, pol_one), (full, pol_full)]
            locked += [rot, polz, s_in, s_out]
            one.button_style = "primary"
            pol_box = [_card("Polarized imaging", *_fit(rot, polz, s_in, s_out), _row(one, full, pbar), action=True,
                             note="Timepix3, counts per wavelength. <i>Polarization matrix</i> takes the 18 images "
                                  "(spin in ±x, ±y, ±z; analyzer x, y, z), each of the time set above.")]
        # Stop and locked settings: each button through measure_control (one status box for all, the Stop button of
        # the measurement under way next to the box)
        import measure_control as mc
        buttons = [b for b, _ in actions]
        stops = []
        for b, fn in actions:
            ctl = mc.Control(odin, b, lock=locked + [x for x in buttons if x is not b],
                             stopped=None if fn.__name__ in ("tomography", "film_cycle", "pol_full")   # (they say it)
                             else "Measurement stopped: nothing of it was recorded.")
            ctl.status = status
            ctl.on_click(fn)
            stops.append(ctl.stop)
        out.children = [w.HBox(stops), *out.children]
        settings_cards = _grid(
            _card("Sample", *_fit(sample, stage, *([load] if max_kN else []))),
            _card("Beam", *_fit(shutter, choppers, delta, pinhole, power)),
            _card("Each measurement", *_fit(t, title), note="One file per measurement, with its title."))
        detector_cards = _grid(
            _card("Timepix3 · time of flight", _row(go, hist), action=True,
                  note="<i>Count</i>: every neutron with its time of flight (Bragg edges, wavelengths). "
                       "<i>Histogram image</i>: long exposures, counts per wavelength bin."),
            _card("Camera · white beam", *_fit(cam_px), _row(cam), _row(step, tomo, bar), action=True,
                  note="Images of all the wavelengths together (radiography); the tomography takes one image at "
                       "each angle over 180°."))
        return _layout("The instrument, as in NICOS: set the devices, then measure. Your files go to the folder of "
                       f"proposal {self.proposal}.", settings_cards, detector_cards, *op_box, *pol_box, out)

    # ------------------------------------------------------------------ LoKI
    def _loki_panel(self):
        for p in (ROOT, os.path.join(ROOT, "loki")):
            if p not in sys.path:
                sys.path.insert(0, p)
        from virtual_loki import VirtualLoki
        if not hasattr(self, "loki"):
            self.loki = VirtualLoki(session=os.environ.get("LOKI_SESSION", "student"))
            self.loki.use_folder(self.folder)
        loki = self.loki
        st, ch = loki.state, loki.choices
        samples = self.samples or list(ch["sample"])
        if "empty_beam" not in samples:            # nothing in the beam: the start, and the empty-beam measurement
            samples = ["empty_beam"] + samples
        if st["sample"] not in samples:
            loki.move(sample="empty_beam")
            st = loki.state
        widgets = {
            "sample": w.Dropdown(options=samples, value=st["sample"], description="Sample"),
            "heavy_shutter": w.ToggleButtons(options=list(ch["heavy_shutter"]), value=st["heavy_shutter"],
                                             description="Heavy shutter"),
            "shutter": w.ToggleButtons(options=list(ch["shutter"]), value=st["shutter"], description="Fast shutter"),
            "collimation": w.Dropdown(options=list(ch["collimation"]), value=st["collimation"], description="Collimation"),
            "pulse_skipping": w.ToggleButtons(options=list(ch["pulse_skipping"]), value=st["pulse_skipping"],
                                              description="Pulse skipping"),
            "detector_distance": w.Dropdown(options=list(ch["detector_distance"]), value=st["detector_distance"],
                                            description="Detector (m)"),
        }
        _fit(*widgets.values(), label=120)
        import source_power                  # the power of the source: read-only (the teacher, or the app)
        power = source_power.control(loki, width="auto")
        t = w.BoundedFloatText(value=60, min=1, max=3600, step=1, description="Time (s)")
        title = w.Text(placeholder="e.g. empty cell", description="Title")
        go = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
        import measure_control as mc
        from virtual_loki import Cancelled
        # Stop and locked settings (measure_control): the count stops once its simulation is done, before writing
        ctl = mc.Control(loki, go, lock=[*widgets.values(), t, title, *source_power.lockable(power)])
        out = w.VBox([ctl.stop, ctl.status]).add_class("tw-out")

        def count(_):
            try:
                loki.move(**{k: x.value for k, x in widgets.items()})
                print("Counting (the first count of a new setting is simulated first: a few minutes)...")
                f = loki.count(float(t.value), title=title.value or "")
                print(f"written in the folder of proposal {self.proposal}: {os.path.basename(f)} "
                      f"({loki.last_n_counts:,} neutrons)")
            except Cancelled:
                pass
            except Exception as e:
                print("Error:", e)

        ctl.on_click(count)
        k = list(widgets)
        return _layout(
            f"The instrument, as in NICOS: set the devices, then count. Your files go to the folder of proposal "
            f"{self.proposal}.",
            _grid(_card("Sample and beam", *[widgets[n] for n in k if n in ("sample", "heavy_shutter", "shutter")],
                        power),
                  _card("Collimation and detector", *[widgets[n] for n in k if n not in ("sample", "heavy_shutter",
                                                                                       "shutter")]),
                  _card("Each measurement", *_fit(t, title, label=120), _row(go), action=True,
                        note="One file per count, with its title.")),
            out)
