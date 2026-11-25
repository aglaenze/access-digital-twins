"""Buttons and checks for the notebooks of the exercises (MSc, beamtime, free beamtime).

    import nb_tools
    nb_tools.nicos("odin")                         # the button Open NICOS (MSc: part 0, measure yourself)
    nb_tools.proposal("odin/exercises/iron_bragg_edges/beamtime.md")   # the proposal sheet, folded
    nb_tools.sample_builder("odin", "1234")           # the sample builder of this instrument and proposal
    nb_tools.proposal_sample("odin/exercises/meteorite_imaging")   # the sample of the proposal, drawn; change it
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
try:                     # the conda environment on the PATH, even in a kernel started without activating it (NCrystal)
    import sys as _sys
    if ROOT not in _sys.path:
        _sys.path.insert(0, ROOT)
    import mcstas_env as _env
    _env.setup(compiler=False)
except Exception:
    pass
NAMES = {"odin": "ODIN", "loki": "LoKI"}
STYLE = ("display:inline-block; padding:9px 16px; margin:4px 8px 4px 0; border-radius:6px; font-weight:600; "
         "font-size:14px; text-decoration:none; font-family:'IBM Plex Sans', 'Segoe UI', sans-serif;")
MAIN = STYLE + "background:#1B1F24; color:#fff; border:1px solid #1B1F24;"
SECOND = STYLE + "background:#fff; color:#1B1F24; border:1px solid #BFC5BC;"


def _button(label, href, main=False):
    return f'<a href="{href}" target="_blank" style="{MAIN if main else SECOND}">{html.escape(label)}</a>'


def _centered(button, note):
    display(HTML(f'<div style="text-align:center; margin:28px 0 30px">{button}'
                 f'<div style="color:#566057; font-size:13px; margin-top:6px">{html.escape(note)}</div></div>'))


def nicos(instr):
    """The button Open NICOS of an instrument (centered)."""
    _centered(_button(f"Open NICOS ({NAMES.get(instr, instr)})",
                      f"/voila/render/container/open_nicos.ipynb?instrument={instr}", main=True),
              "NICOS opens in about a minute, logged in.")


def builder_url(instr):
    """The sample builder of an instrument: the page of the app (builder/, served by container/twin_app.py; ODIN:
    builder/index.html, LoKI: builder/loki.html, chosen by ?instrument=)."""
    return "/twin/builder"


def sample_builder(instr, proposal=""):
    """The button Sample builder (centered), for this instrument and proposal: nothing to choose on the page."""
    _centered(_button("Sample builder", f"{builder_url(instr)}?instrument={instr}&proposal={proposal}",
                      main=True),
              "Design your sample (a piece of any shape, objects in it, grains placed at random; or kinds of particles), "
              "start from an example or a model, then save it "
              "with your proposal: it appears on the sample changer of NICOS.")


def sample_picture(instr, spec, hidden=()):
    """(error, picture) of a sample: the drawing of sample_library.draw as an IPython Image (twice the resolution,
    shown at its normal size, as sample_library.show), or the error as text (its type, message and the place in the
    code where it happened). The figure is always closed: an empty figure is never left to the page."""
    import sys
    import contextlib
    import io
    import struct
    import traceback
    import warnings
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import sample_library as sl
    import matplotlib.pyplot as plt
    from IPython.display import Image
    fig = plt.figure(figsize=(10, 3.8))
    try:
        # the messages of the libraries (e.g. "NCrystal WARNING: Discarding 52 edges...") are not for the students
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()),                 contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            sl.draw(instr, spec, hidden=hidden, fig=fig)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=2 * fig.dpi, bbox_inches="tight")
        data = buf.getvalue()
        return None, Image(data=data, width=struct.unpack(">I", data[16:20])[0] // 2)
    except Exception as e:
        where = traceback.extract_tb(e.__traceback__)[-1]
        return f"{type(e).__name__}: {e} ({os.path.basename(where.filename)}, line {where.lineno})", None
    finally:
        plt.close(fig)


def draw_error(instr, spec, hidden=(), show=True):
    """Draws a sample and shows it (show=True); returns None, or the error as text (sample_picture)."""
    err, img = sample_picture(instr, spec, hidden)
    if img is not None and show:
        display(img)
    return err


def _mime(obj):
    """An output of an ipywidgets Output (the format of its .outputs) from a display object."""
    from IPython.core.interactiveshell import InteractiveShell
    data, metadata = InteractiveShell.instance().display_formatter.format(obj)
    return dict(output_type="display_data", data=data, metadata=metadata)


_WATCHERS = {}                  # {exercise: threading.Event}: the watcher of the samples of each notebook section


def proposal_sample(exercise, watch=True):
    """Top of a beamtime notebook (expert level): the sample(s) of the proposal of the exercise (exercise.yml:
    samples, modes.beamtime.proposal), drawn and described as NICOS will mount them (hidden properties not shown);
    the samples the student made for this proposal too; then the button *Change the sample*, which opens the sample
    builder starting from it (the new sample is saved with the proposal and appears on the sample changer).
    watch=True: the section follows the folder of the student's samples (<proposal>/samples, checked every 2 s): a
    sample saved or changed in the sample builder is drawn at once, marked "just saved", without running the cell
    again."""
    import sys
    import datetime
    import threading
    from urllib.parse import quote
    import yaml
    import ipywidgets as w
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import sample_library as sl
    import user_office
    with open(os.path.join(ROOT, exercise, "exercise.yml"), encoding="utf-8") as f:
        ex = yaml.safe_load(f)
    instr = ex["instrument"]
    prop = str(((ex.get("modes") or {}).get("beamtime") or {}).get("proposal", {}).get("id", ""))
    folder = os.path.join(user_office.run_root(), "data", instr, str(datetime.date.today().year), prop, "raw")
    mine_dir = sl.user_folder(folder) if prop else None
    given = list(ex.get("samples") or {})

    def state():
        """The student's sample files and their dates: what the section shows depends on nothing else."""
        if not mine_dir or not os.path.isdir(mine_dir):
            return ()
        return tuple(sorted((n, os.path.getmtime(os.path.join(mine_dir, n)))
                            for n in os.listdir(mine_dir) if n.endswith(".yml")))

    def items(new=()):
        """What the section shows, as display objects (made in full before the section is changed): the sample that
        is the student's choice now (the last one they saved; before that, the sample(s) of the proposal), a line with
        the others still on the sample changer, and the button Change the sample, which starts from the one shown."""
        lib = sl.load(instr, folder if prop else None)
        own = [n for n, s in lib.items() if s.get("source") == "student"]
        own.sort(key=lambda n: os.path.getmtime(lib[n]["file"]) if lib[n].get("file") and os.path.exists(lib[n]["file"]) else 0)
        current = [own[-1]] if own else [n for n in given if n in lib]
        others = [n for n in given + own if n in lib and n not in current]
        out = []
        for n in current:
            spec = lib[n]
            hidden = (ex.get("samples") or {}).get(n, {}).get("hidden") or spec.get("hidden") or []
            who = "the sample of your proposal" if n in given else "the sample you made for this proposal"
            mark = " · **just saved**" if n in new else ""
            out.append(Markdown(f"**{spec.get('name', n)}** (`{n}`, {who}){mark}"))
            err, img = sample_picture(instr, spec, hidden)
            out.append(img if img is not None else Markdown(
                f"*(The drawing of this sample could not be made: {html.escape(err)}. Please tell your teacher.)*"))
            if spec.get("description"):
                out.append(Markdown(spec["description"]))
        if current:                  # the first command in NICOS: nothing is mounted until the student mounts it
            cmds = "".join(f'<div style="font-family:&quot;IBM Plex Mono&quot;,Consolas,monospace; font-size:15px; background:#fff; '
                           f'border:1px solid #BFC5BC; border-radius:6px; padding:6px 10px; margin:6px 0; '
                           f'user-select:all">move(sample_holder, \'{html.escape(n)}\')</div>' for n in current)
            several = len(current) > 1
            out.append(HTML(
                '<div style="background:#FFF4D6; border-radius:10px; padding:12px 16px; margin:14px 0">'
                f'<b>First step in NICOS: mount your sample{"s, one at a time" if several else ""}.</b> Nothing is '
                f'on the sample stage until you do it: type{" the command of the sample you want to measure" if several else ""}'
                f' in the command line of NICOS:{cmds}'
                '<span style="color:#566057; font-size:13px">If you change the sample in the sample builder, this '
                'command changes here too: mount the new one the same way. <code>sample_info()</code> tells you which '
                'sample is mounted.</span></div>'))
        if others:
            out.append(Markdown("Also on the sample changer of NICOS: " + ", ".join(
                f"*{lib[n].get('name', n)}* (`{n}`{', the sample of your proposal' if n in given else ''})"
                for n in others) + "."))
        start = current[0] if current else ""
        out.append(HTML(f'<div style="text-align:center; margin:28px 0 30px">'
                        f'{_button("Change the sample", f"{builder_url(instr)}?instrument={instr}&proposal={prop}&start={quote(start)}")}'
                        f'<div style="color:#566057; font-size:13px; margin-top:6px">Your question needs another sample, '
                        f'or this one changed? The sample builder starts from it; what you save there goes with your '
                        f'proposal, on the sample changer of NICOS, and is shown here as soon as it is saved.</div></div>'))
        return out

    box = w.Output()
    box.outputs = tuple(_mime(x) for x in items())
    display(box)
    if not (watch and mine_dir):
        return
    old = _WATCHERS.pop(exercise, None)               # the cell run again: one watcher only
    if old:
        old.set()
    stop = _WATCHERS[exercise] = threading.Event()

    def follow(last):
        while not stop.wait(2.0):
            try:
                now = state()
                if now == last:
                    continue
                before = dict(last)
                new = {n[:-4] for n, t in now if before.get(n) != t}
                shown = items(new)                      # drawn first, then swapped: the section never flickers empty
                box.outputs = tuple(_mime(x) for x in shown)
                last = now
            except Exception:                           # noqa: BLE001  (a sample being written: next time)
                pass

    threading.Thread(target=follow, args=(state(),), daemon=True).start()


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
            href = (f"{builder_url(instr)}?instrument={instr}&proposal={proposal}"
                    f"&name={quote(s['name'])}&title={quote(s.get('title') or '')}")
            rows.append(f"<li>{label}: {_button('Build it', href)}</li>")
    display(HTML(f'<div style="margin:0 0 24px"><b>The samples of your proposal {html.escape(str(proposal))}</b> '
                 f'(the twin needs a model of each one: what it is made of, its shape):<ul>{"".join(rows)}</ul>'
                 f'<span style="color:#566057; font-size:13px">Save each one under the short name given: NICOS then '
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
            display(HTML('<details style="margin-top:8px; border:1px solid #D5D9D1; border-radius:10px; padding:8px 14px">'
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
