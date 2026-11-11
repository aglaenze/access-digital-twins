"""Buttons and checks for the notebooks of the exercises (MSc, beamtime, free beamtime).

    import nb_tools
    nb_tools.nicos("odin")                         # the button Open NICOS (MSc: part 0, measure yourself)
    nb_tools.proposal("odin/exercises/iron_bragg_edges/beamtime.md")   # the proposal sheet, folded
    nb_tools.sample_builder("odin", "1234")           # the sample builder of this instrument and proposal
    nb_tools.imported_samples("odin", "2025123")    # an imported proposal: a button per sample still to build
    nb_tools.need_measurements(FOLDER, "odin")     # stops the notebook, clearly, while there is nothing to analyze

The buttons are links: in the app they open a tab (NICOS: on the desktop of this computer, or the control room of the
container; the sample builder: its page); in a browser, a new tab.
"""
import glob
import html
import os

from IPython.display import HTML, Markdown, display

ROOT = os.path.dirname(os.path.abspath(__file__))
NAMES = {"odin": "ODIN", "loki": "LoKI"}
STYLE = ("display:inline-block; padding:9px 16px; margin:4px 8px 4px 0; border-radius:9px; font-weight:600; "
         "font-size:14px; text-decoration:none; font-family:Inter, 'Segoe UI', sans-serif;")
MAIN = STYLE + "background:#0E7C70; color:#fff; border:1px solid #0E7C70;"
SECOND = STYLE + "background:#fff; color:#142033; border:1px solid #CBD3DE;"


def _button(label, href, main=False):
    return f'<a href="{href}" target="_blank" style="{MAIN if main else SECOND}">{html.escape(label)}</a>'


def _centered(button, note):
    display(HTML(f'<div style="text-align:center; margin:28px 0 30px">{button}'
                 f'<div style="color:#5B6779; font-size:13px; margin-top:6px">{html.escape(note)}</div></div>'))


def nicos(instr):
    """The button Open NICOS of an instrument (centered)."""
    _centered(_button(f"Open NICOS ({NAMES.get(instr, instr)})",
                      f"/voila/render/container/open_nicos.ipynb?instrument={instr}", main=True),
              "NICOS opens in about a minute, logged in.")


def sample_builder(instr, proposal=""):
    """The button Sample builder (centered), for this instrument and proposal: nothing to choose on the page."""
    _centered(_button("Sample builder", f"/voila/render/Sample_builder.ipynb?instrument={instr}&proposal={proposal}",
                      main=True),
              "Design your sample (as many blocks, cylinders, spheres or kinds of particles as you want), then save it "
              "with your proposal: it appears on the sample changer of NICOS.")


def imported_samples(instr, proposal):
    """An imported proposal (a real one, typed in the app): its samples, each with a button that opens the sample
    builder with its short name and title filled in, until it is built. Nothing for the other proposals."""
    import sys
    from urllib.parse import quote
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import user_office
    import sample_library
    p = user_office.get(proposal)
    if not p or p.get("kind") != "imported" or not p.get("samples"):
        return
    import datetime
    folder = os.path.join(user_office.run_root(), "data", instr, str(datetime.date.today().year), str(proposal), "raw")
    built = sample_library.load(instr, folder)
    rows = []
    for s in p["samples"]:
        label = html.escape(f"{s.get('title') or s['name']}" + (f" ({s['formula']})" if s.get("formula") else ""))
        if s["name"] in built:
            rows.append(f"<li>{label}: built, <code>move(sample_holder, '{s['name']}')</code></li>")
        else:
            href = (f"/voila/render/Sample_builder.ipynb?instrument={instr}&proposal={proposal}"
                    f"&name={quote(s['name'])}&title={quote(s.get('title') or '')}")
            rows.append(f"<li>{label}: {_button('Build it', href)}</li>")
    display(HTML(f'<div style="margin:0 0 24px"><b>The samples of your proposal {html.escape(str(proposal))}</b> '
                 f'(the twin needs a model of each one: what it is made of, its shape):<ul>{"".join(rows)}</ul>'
                 f'<span style="color:#5B6779; font-size:13px">Save each one under the short name given: NICOS then '
                 f'mounts the first one when you apply the proposal. Run this cell again to see what is built.</span>'
                 f'</div>'))


def beamtime_tools(instr, proposal=None):
    """Your proposal (folded), then the sample builder and NICOS (older notebooks)."""
    if proposal:
        globals()["proposal"](proposal)
    sample_builder(instr)
    nicos(instr)


def proposal(path):
    """The proposal sheet (beamtime.md of the exercise), folded."""
    if path:
        try:
            import mistune
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                sheet = mistune.html(f.read())
            display(HTML('<details style="margin-top:8px; border:1px solid #E2E7EE; border-radius:10px; padding:8px 14px">'
                         '<summary style="cursor:pointer; font-weight:600">Your proposal (click to open)</summary>'
                         f'{sheet}</details>'))
        except OSError:
            pass


class MeasureFirst(Exception):
    """No data yet: shown as a short message, not as a traceback."""

    def _render_traceback_(self):
        return ["\x1b[1;33m" + str(self) + "\x1b[0m"]


def need_measurements(folder, instr):
    files = sorted(glob.glob(os.path.join(folder, f"{instr}_*.nxs")) + glob.glob(os.path.join(folder, f"{instr}_job_*.hdf")))
    if not files:
        raise MeasureFirst(
            f"No measurement yet in {folder}.\n"
            f"Measure in NICOS first (button Open NICOS of this notebook), with the proposal of PROPOSAL applied in the "
            f"Experiment tab; then run this notebook again: "
            f"menu Run > Run All Cells.")
    return files
