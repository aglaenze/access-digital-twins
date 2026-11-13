// "Open (without code)" of an MSc notebook: the notebook shown as a page of the BSc level. Run inside the notebook
// (Notebook 7), by the shell of the app (applyView in app.js): __twinCleanView(true) or __twinCleanView(false).
//   - no header, no menu bar, no toolbar (hidden as widgets: the layout closes the gap);
//   - code cells show their outputs only; no prompts, no cell selection, no collapsers, no cell toolbar;
//   - the keys that act on cells (a, b, d d, x, Enter, ...) do nothing outside the fields of the widgets;
//   - a button "Analyze my files" runs the whole notebook again (the newest files, the model, the answers).
window.__twinCleanView = function (on) {
  const a = window.jupyterapp;
  if (!a) return "no app";
  const sh = a.shell;
  try { on ? sh.collapseTop() : sh.expandTop(); } catch (e) { /* older API */ }
  try { if (sh.menu) { on ? sh.menu.hide() : sh.menu.show(); } } catch (e) { /* */ }
  const w = sh.currentWidget;
  try { if (w && w.toolbar) { on ? w.toolbar.hide() : w.toolbar.show(); } } catch (e) { /* */ }
  let st = document.getElementById("twin-clean-css");
  if (on && !st) {
    st = document.createElement("style");
    st.id = "twin-clean-css";
    st.textContent = `
      .jp-CodeCell .jp-Cell-inputWrapper { display: none !important; }
      .jp-InputPrompt, .jp-OutputPrompt, .jp-Collapser, .jp-InputCollapser, .jp-OutputCollapser,
      .jp-cell-toolbar, .jp-cell-menu, .jp-Notebook-footer { display: none !important; }
      .jp-Notebook .jp-Cell, .jp-Notebook .jp-Cell.jp-mod-selected, .jp-Notebook .jp-Cell.jp-mod-active,
      .jp-Notebook.jp-mod-commandMode .jp-Cell.jp-mod-active.jp-mod-selected,
      .jp-Notebook.jp-mod-editMode .jp-Cell.jp-mod-active { background: transparent !important; box-shadow: none !important;
        border-color: transparent !important; outline: none !important; }
      .jp-Notebook .jp-Cell::before, .jp-Notebook .jp-Cell::after { display: none !important; }
      .jp-Notebook .jp-Cell .jp-InputArea, .jp-Notebook .jp-Cell .jp-Cell-inputArea, .jp-Notebook .jp-Cell .jp-InputArea-editor,
      .jp-Notebook .jp-Cell .jp-MarkdownOutput, .jp-Notebook .jp-Cell:focus, .jp-Notebook .jp-Cell *:focus:not(input):not(textarea):not(select) {
        border-color: transparent !important; box-shadow: none !important; outline: none !important; }
      .jp-MarkdownCell .jp-RenderedHTMLCommon { cursor: default; user-select: text; }
      .jp-Cell-outputWrapper { margin-top: 2px; }`;
    document.head.append(st);
  } else if (!on && st) {
    st.remove();
  }
  window.__twinClean = on;
  if (!window.__twinCleanKeys) {
    window.__twinCleanKeys = true;
    window.addEventListener("keydown", (e) => {
      if (!window.__twinClean) return;
      const typing = e.target && e.target.closest &&
        e.target.closest("input, textarea, select, [contenteditable='true'], .widget-text, .widget-textarea");
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;     // the widgets' fields; Ctrl+S, copy...
      e.stopPropagation();                                          // not to the commands of the notebook
    }, true);
    window.addEventListener("dblclick", (e) => { if (window.__twinClean && !e.target.closest(".jp-OutputArea")) e.stopPropagation(); }, true);
  }
  let b = document.getElementById("twin-analyze");
  if (!on) { if (b) b.remove(); return "code shown"; }
  if (!b) {
    b = document.createElement("button");
    b.id = "twin-analyze";
    b.textContent = "▶  Analyze my files";
    b.title = "Runs the notebook again: your newest files, your model, your answers";
    b.style.cssText = "position:fixed;right:24px;bottom:24px;z-index:1000;background:#0E7C70;color:#fff;border:0;" +
      "border-radius:10px;padding:11px 18px;font:600 14px system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.2);cursor:pointer";
    b.onclick = async () => {
      b.disabled = true; b.textContent = "Analyzing…";
      try { await window.jupyterapp.commands.execute("notebook:run-all-cells"); }
      finally { b.disabled = false; b.textContent = "▶  Analyze my files"; }
    };
    document.body.append(b);
  }
  return "code hidden";
};
