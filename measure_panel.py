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

import ipywidgets as w
from IPython.display import clear_output, display

ROOT = os.path.dirname(os.path.abspath(__file__))
HIDE_NICOS = "<style>.jp-Cell:has(.twin-nicos), .jp-Notebook-cell:has(.twin-nicos) { display: none !important; }</style>"


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
                                   value=self._pref(), style={"button_width": "190px"})
        self.box = w.VBox()
        self.how.observe(lambda c: self._show(), "value")
        display(w.VBox([w.HTML("<b>How do you measure?</b> Either way, your files go to the folder of proposal "
                               f"{self.proposal}, and the rest of the notebook reads them."),
                        self.how, self.style, self.box]))
        self._show()

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
            self.style.value = HIDE_NICOS
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
        samples = self.samples or [st["sample"]]
        if st["sample"] not in samples:
            odin.move(sample=samples[0])
            st = odin.status()
        sample = w.Dropdown(options=samples, value=st["sample"], description="Sample")
        shutter = w.ToggleButtons(options=["closed", "open"], value=st["shutter"], description="Shutter")
        stage = w.BoundedFloatText(value=st["stage_x"] * 1000, min=-500, max=500, step=1, description="Stage x (mm)")
        choppers = w.Dropdown(options=[("WFM", "wfm"), ("natural (band-pass + T0)", "natural"), ("white (none)", "white")],
                              value=st["choppers"], description="Choppers")
        delta = w.Dropdown(options=[0.10, 0.30, 0.45], value=st["wfm_delta"], description="WFM δ (m)")
        pinhole = w.Dropdown(options=[0.01, 0.02, 0.03, 0.04], value=st["pinhole"], description="Pinhole (m)")
        import sample_library as sl
        lib = sl.load("odin")
        max_kN = max((float((lib.get(n) or {}).get("load", {}).get("max_kN", 0)) for n in samples), default=0)
        load = w.FloatSlider(value=float(st.get("load") or 0), min=0, max=max_kN or 1, step=1, readout_format=".0f",
                             description="Load (kN)", continuous_update=False, layout=w.Layout(width="420px"))
        t = w.BoundedFloatText(value=30, min=1, max=600, step=1, description="Time (s)")
        title = w.Text(placeholder="e.g. open beam", description="Title")
        go = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
        out = w.Output()

        def count(_):
            go.disabled = True
            with out:
                clear_output()
                try:
                    odin.move(sample=sample.value, shutter=shutter.value, stage_x=stage.value / 1000,
                              choppers=choppers.value, wfm_delta=delta.value, pinhole=pinhole.value)
                    if max_kN:
                        odin.move(load=float(load.value))
                    live = viz.LiveCount()
                    f = odin.count(float(t.value), title=title.value or "", progress=live.update)
                    live.done(f)
                    print(f"written in the folder of proposal {self.proposal}: {os.path.basename(f)}")
                except Exception as e:
                    print("Error:", e)
            go.disabled = False

        go.on_click(count)
        return w.VBox([w.HTML("The instrument, as in NICOS: set the devices, then <i>Count</i> (one file per count, "
                              "with its title). The dark, the open beam and the sample are three counts."),
                       sample, shutter, stage, choppers, delta, pinhole, *([load] if max_kN else []), t, title,
                       go, out])

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
        if st["sample"] not in samples:
            loki.move(sample=samples[0])
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
        for x in widgets.values():
            x.style = {"description_width": "110px"}
        t = w.BoundedFloatText(value=60, min=1, max=3600, step=1, description="Time (s)")
        title = w.Text(placeholder="e.g. empty cell", description="Title")
        go = w.Button(description="Count", button_style="primary", icon="play", layout=w.Layout(width="auto"))
        out = w.Output()

        def count(_):
            go.disabled = True
            with out:
                clear_output()
                try:
                    loki.move(**{k: x.value for k, x in widgets.items()})
                    print("Counting (the first count of a new setting is simulated first: a few minutes)...")
                    f = loki.count(float(t.value), title=title.value or "")
                    clear_output()
                    print(f"written in the folder of proposal {self.proposal}: {os.path.basename(f)} "
                          f"({loki.last_n_counts:,} neutrons)")
                except Exception as e:
                    print("Error:", e)
            go.disabled = False

        go.on_click(count)
        return w.VBox([w.HTML("The instrument, as in NICOS: set the devices, then <i>Count</i> (one file per count, "
                              "with its title)."), *widgets.values(), t, title, go, out])
