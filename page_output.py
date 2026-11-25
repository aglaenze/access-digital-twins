"""Filling an ipywidgets Output widget safely on the Voila pages.

    from page_output import into
    with into(out):            # instead of "with out: clear_output(...)"
        print("...")
        sl.show(fig)

"with out:" captures each output as it comes; when the page is first executed by Voila (nbclient), each captured output
is sent back to the kernel, and with images this exchange can block: the page then never appears (seen on Windows,
2026-11-06). Here the outputs are collected in the kernel and the widget gets them all at once (its "outputs" trait),
which also replaces the previous ones (no flicker). Use it for quick content; for long tasks that print their progress,
keep "with out:" in the callbacks of buttons (they run after the page is shown).
"""
from contextlib import contextmanager


def gate(text="The rest of the page appears once this step is done."):
    """A barrier in the page: while it is shown, every cell after the one that displays it is hidden (twin.css:
    .jp-Cell:has(.twin-gate) ~ .jp-Cell), so that a result is not seen before the student computed it. open(gate)
    removes it. Returns the widget, to display at the end of the cell of the step."""
    import html as _html
    import os
    import ipywidgets as w
    if os.environ.get("TWIN_TEACHER") == "1" and os.environ.get("TWIN_WEB") != "1":
        # the teacher view of the app: the whole page at once (the step is not needed to see what follows)
        return w.HTML("<div class='twin-teacher-note' style='margin:10px 0;padding:8px 14px;border-radius:10px;"
                      "border:1px dashed #F2C230;background:#FFF4D6;color:#7A5A00;font-size:14px'>Teacher view: the rest of the page is shown without this step "
                      "(as a student, it appears once the step is done).</div>")
    return w.HTML(f"<div class='twin-gate'>🔒 {_html.escape(text)}</div>")


def open_gate(g):
    """The step is done: the rest of the page appears."""
    g.value = ""


@contextmanager
def collapsed(title):
    """A section folded by default, opened by a click on its title (the bonus rounds): what the block prints and
    displays (text, Markdown, questions) goes inside.

        with collapsed("Bonus round: for X-ray experts"):
            display(Markdown("..."))
            q.number(...)
    """
    import ipywidgets as w
    from IPython.display import display
    out = w.Output()
    with into(out):
        yield
    acc = w.Accordion(children=[out], selected_index=None)
    acc.set_title(0, title)
    display(acc.add_class("twin-collapsed"))


@contextmanager
def into(out):
    """Collects what is printed and displayed in the block (text first, then the figures) and puts it in `out`,
    even if the block fails (the error itself is raised as usual)."""
    from IPython.utils.capture import capture_output
    capture = capture_output(display=True)
    cap = capture.__enter__()
    try:
        yield
    finally:
        capture.__exit__(None, None, None)
        outs = []
        if cap.stdout:
            outs.append({"output_type": "stream", "name": "stdout", "text": cap.stdout})
        if cap.stderr:
            outs.append({"output_type": "stream", "name": "stderr", "text": cap.stderr})
        for o in cap.outputs:
            outs.append({"output_type": "display_data", "data": dict(o.data), "metadata": dict(o.metadata or {})})
        out.outputs = tuple(outs)
