"""The power of the source: a state of the facility, read by the students, never set by them.

ESS starts its user programme at 2 MW and is designed for 5 MW. The power sets the protons per pulse (71.4 µC at
2 MW, 14 pulses per second), and the neutrons made are proportional to it (VirtualOdin.power_mw, VirtualLoki.power_mw).
Every measurement writes the proton charge it received, and the reductions divide by it: measurements at different
powers compare.

As at ESS, the user of the instrument does not choose it (the accelerator delivers it). Who sets it:
  * in a class, the teacher (classes.py, settings.power_mw);
  * otherwise the setting of the twin on this computer (the teacher view of the app: /twin/source_power, written in
    TWIN_RUN_ROOT/source_power.json);
  * 2 MW by default.
current() is read again at each measurement (VirtualOdin.power_mw and VirtualLoki.power_mw follow it, in the pages and
in the twin server driven by NICOS, where source_power is a read-only value), so a change applies to the next
measurement.

    import source_power
    power = source_power.control(odin)          # a read-only line: the power today and what it means
"""
import json
import os

CHOICES = [("2 MW (ESS at the start of its user programme)", 2.0), ("5 MW (ESS design power)", 5.0)]
DEFAULT_MW = 2.0


def _file():
    root = os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))
    return os.path.join(root, "source_power.json")


def fixed():
    """The power fixed by the teacher for the class of this server (MW), or None."""
    try:
        import classes
        v = classes.setting("power_mw")
        return float(v) if v else None
    except Exception:
        return None


def fixed_here():
    """fixed(), or else the power fixed for the class open on this computer (the twin server of NICOS and the pages
    of the app are started outside the class, without TWIN_CLASS)."""
    f = fixed()
    if f:
        return f
    try:
        import classes
        st = classes.open_status()
        v = classes.load(st["code"]).get("settings", {}).get("power_mw") if st else None
        return float(v) if v else None
    except Exception:
        return None


def machine():
    """The power set for the twin on this computer (teacher view of the app), or None."""
    try:
        with open(_file(), encoding="utf-8") as f:
            v = json.load(f).get("power_mw")
        return float(v) if v else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def set_machine(mw):
    """Sets the power of the twin on this computer (outside a class that fixes it)."""
    mw = float(mw)
    if mw not in [v for _, v in CHOICES]:
        raise ValueError(f"source power: one of {[v for _, v in CHOICES]} MW")
    os.makedirs(os.path.dirname(_file()), exist_ok=True)
    with open(_file(), "w", encoding="utf-8") as f:
        json.dump({"power_mw": mw}, f)
    return mw


def current():
    """The power of the source now (MW): the teacher's for the class, else the setting of this computer, else 2 MW."""
    return fixed_here() or machine() or DEFAULT_MW


def default():
    return current()


def describe(mw=None):
    """What the student reads: the power, who set it, what it means."""
    mw = current() if mw is None else mw
    what = {2.0: "ESS at the start of its user programme", 5.0: "the design power of ESS"}.get(mw, "")
    who = "set by your teacher" if fixed_here() else "the power of the source today"
    return (f"<b>{mw:g} MW</b>{' (' + what + ')' if what else ''}: {who}. The protons hit the target in 14 pulses "
            f"per second of {71.4 * mw / 2:.0f} µC each; the neutrons, and so your counts, are proportional to the "
            "power. As at ESS, you do not choose it: the accelerator delivers it.")


def control(instrument, description="Source power", width="100%"):
    """A read-only line: the power of the source today and what it means (instrument.power_mw follows current())."""
    import ipywidgets as w
    return w.HTML(value=describe(), description=description, style={"description_width": "initial"},
                  layout=w.Layout(width=width))


def lockable(widget):
    """Nothing to lock: the student does not set the power (kept for the pages that call it)."""
    return []
