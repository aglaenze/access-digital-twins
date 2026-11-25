"""The power of the source, in every page and notebook that measures: a menu, or the value fixed by the teacher.

ESS starts at 2 MW and is designed for 5 MW. The power sets the protons per pulse (71.4 µC at 2 MW), and the neutrons
made are proportional to it (VirtualOdin.power_mw, VirtualLoki.power_mw). Every measurement writes the proton charge
it received, and the reductions divide by it: measurements at different powers compare.

    import source_power
    power = source_power.control(odin)          # a Dropdown; put it with the other settings of the measurement
    ctl = mc.Control(odin, button, lock=[...] + source_power.lockable(power))

When the teacher fixed the power for the class (classes.py, settings.power_mw), the menu shows it, locked ("set by your
teacher"), and the instrument starts with it anyway (default()).

NICOS (twin_server.py): the device source_power (1, 2 or 5 MW) sets the power of the simulations that NICOS starts; the
teacher's value wins (fixed_here(): the class of the server, or else the class open on this computer), read again
before each simulation. ESS NICOS has no such device (the accelerator sets the power): it is a device of the twin.
"""
CHOICES = [("1 MW", 1.0), ("2 MW (ESS at the start)", 2.0), ("5 MW (ESS design)", 5.0)]
DEFAULT_MW = 2.0


def fixed():
    """The power fixed by the teacher for the class of this server (MW), or None."""
    try:
        import classes
        v = classes.setting("power_mw")
        return float(v) if v else None
    except Exception:
        return None


def fixed_here():
    """fixed(), or else the power fixed for the class open on this computer (the twin server of NICOS is started
    outside the class, without TWIN_CLASS)."""
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


def default():
    """The power an instrument starts with: the teacher's, or 2 MW."""
    return fixed() or DEFAULT_MW


def control(instrument, description="Source power", width="360px"):
    """A menu of the power of the source that sets instrument.power_mw (locked at the teacher's value if fixed)."""
    import ipywidgets as w
    f = fixed()
    opts = [(f"{f:g} MW (set by your teacher)", f)] if f else CHOICES
    value = f or (instrument.power_mw if instrument.power_mw in [v for _, v in CHOICES] else DEFAULT_MW)
    dd = w.Dropdown(options=opts, value=value, description=description, disabled=bool(f),
                    style={"description_width": "initial"}, layout=w.Layout(width=width))
    instrument.power_mw = float(dd.value)
    dd.observe(lambda ch: setattr(instrument, "power_mw", float(ch["new"])), names="value")
    return dd


def lockable(dd):
    """[dd] if the student may change it (to lock it during a measurement), [] if fixed by the teacher (the lock of a
    measurement would unlock it at the end)."""
    return [] if dd.disabled else [dd]
