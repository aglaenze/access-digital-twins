// ESS digital twins: the student app (Electron).
//   The window shows the shell (shell/index.html): sign in, the catalogue, and each open exercise in a tab (a
//   <webview> on the Jupyter server of backend.js: Voila pages and notebooks). The server starts with the app, while
//   the student signs in. Accounts: accounts.js (on this computer). The student's work: container/twin_app.py.
const { app, BrowserWindow, ipcMain, dialog, shell, session } = require("electron");
const fs = require("fs");
const path = require("path");
const { Accounts } = require("./accounts");
const { Backend } = require("./backend");

const TWIN_DIR = process.env.TWIN_DIR || path.resolve(__dirname, "..");   // (TWIN_DIR: a packaged app on the twin folder)
let win = null;
let backend = null;
let ready = null;          // promise of the server address
let status = { text: "Starting…", fraction: 0, error: null };
let current = null;        // the student signed in
const accounts = () => new Accounts(app.getPath("userData"));

function settings() {
  try { return JSON.parse(fs.readFileSync(path.join(app.getPath("userData"), "settings.json"), "utf-8")); } catch { return {}; }
}

function send(channel, ...a) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, ...a);
}

function startBackend() {
  backend = new Backend({
    dataDir: app.getPath("userData"), twinDir: TWIN_DIR, settings: settings(),
    onStatus: (text, fraction) => { status = { text, fraction, error: null }; send("status", status); },
  });
  ready = backend.start().catch((e) => {
    status = { text: e.message, fraction: 0, error: true, url: e.url || null };
    send("status", status);
    throw e;
  });
  ready.catch(() => {});
}

function createWindow() {
  win = new BrowserWindow({
    width: 1400, height: 900, minWidth: 960, minHeight: 640, backgroundColor: "#0B1626", show: false,
    title: "ESS digital twins", icon: path.join(__dirname, "icon.png"), autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, "preload.js"), webviewTag: true, contextIsolation: true,
                      // the self-test window is out of the screen: no slowed timers there
                      backgroundThrottling: !process.env.TWIN_APP_SELFTEST },
  });
  win.removeMenu();
  win.once("ready-to-show", () => win.show());
  win.loadFile(path.join(__dirname, "shell", "index.html"));
  win.on("close", (e) => {           // the open notebooks are saved first
    if (win.__closing) return;
    e.preventDefault();
    win.__closing = true;
    send("before-quit");
    setTimeout(() => win.destroy(), 1500);
  });
}

// links that open a new window in a page (target=_blank): a new tab of the app, or the browser for other sites
app.on("web-contents-created", (_e, wc) => {
  wc.setWindowOpenHandler(({ url }) => {
    if (backend && backend.base && url.startsWith(backend.base)) send("open-url", url);
    else if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
});

ipcMain.handle("status", () => status);
// The open session: the student signed in and not signed out (session.json); the app reopens it at the next start
const sessionFile = () => path.join(app.getPath("userData"), "session.json");
function openSession() {
  try {
    const id = JSON.parse(fs.readFileSync(sessionFile(), "utf-8")).id;
    return accounts().get(id);
  } catch { return null; }
}
ipcMain.handle("session", () => { const u = openSession(); return u ? { name: u.name } : null; });
ipcMain.handle("has-accounts", () => accounts().recent(1).length > 0);
ipcMain.handle("resume", async () => { const u = openSession(); return u ? signedIn(u) : null; });
ipcMain.handle("open-external", (_e, url) => shell.openExternal(url));

async function signedIn(user) {
  await ready;
  await backend.request("POST", "/twin/user", user);
  current = user;
  fs.writeFileSync(sessionFile(), JSON.stringify({ id: user.id }));
  return { user, base: backend.base, token: backend.token };
}

ipcMain.handle("create-account", async (_e, form) => {
  const r = accounts().create(form);
  return r.error ? r : { ...(await signedIn(r.user)), recovery: r.recovery };
});
ipcMain.handle("reset-password", async (_e, form) => {
  const r = accounts().reset(form);
  return r.error ? r : signedIn(r.user);
});
ipcMain.handle("sign-in", async (_e, form) => {
  const r = accounts().signIn(form);
  return r.error ? r : signedIn(r.user);
});
ipcMain.handle("sign-out", async () => { current = null; fs.rmSync(sessionFile(), { force: true }); return true; });

ipcMain.handle("api", async (_e, method, p, body) => {
  await ready;
  return backend.request(method, p, body, { timeout: 120000 });
});

// a notebook tab closed: its kernel stops (a Voila page stops its own)
ipcMain.handle("close-notebook", async (_e, nbPath) => {
  try {
    const ss = await backend.request("GET", "/api/sessions");
    for (const s of ss) if (s.path === nbPath) await backend.request("DELETE", "/api/sessions/" + s.id);
  } catch { /* nothing to stop */ }
});

ipcMain.handle("hand-in", async () => {
  if (!current) return { error: "Sign in first." };
  const { buf } = await backend.request("GET", "/twin/handin", undefined, { raw: true, timeout: 120000 });
  const name = `${current.id}_${new Date().toISOString().slice(0, 10)}.zip`;
  const r = await dialog.showSaveDialog(win, {
    title: "Export all my work", defaultPath: path.join(app.getPath("documents"), name),
    filters: [{ name: "Zip file", extensions: ["zip"] }],
    message: "Save the file, then send it to your teacher (email, or the course page).",
  });
  if (r.canceled || !r.filePath) return { canceled: true };
  fs.writeFileSync(r.filePath, buf);
  shell.showItemInFolder(r.filePath);
  return { file: r.filePath, size: buf.length };
});

// Self-test without showing anything (TWIN_APP_SELFTEST=<folder for the screenshots>, TWIN_APP_DATA=<data folder>):
// creates an account, shows the catalogue, opens the first BSc page, saves screenshots, quits.
if (process.env.TWIN_APP_DATA) app.setPath("userData", process.env.TWIN_APP_DATA);

async function selftest(out) {
  const wc = win.webContents;
  const shot = async (name) => fs.writeFileSync(path.join(out, name + ".png"),
    (await wc.capturePage()).toPNG());
  const js = (code) => wc.executeJavaScript(code);
  const wait = async (cond, s) => { for (let i = 0; i < s * 2; i++) { if (await js(cond)) return true; await new Promise((r) => setTimeout(r, 500)); } return false; };
  const log = (m) => fs.appendFileSync(path.join(out, "selftest.log"), new Date().toISOString().slice(11, 19) + " " + m + "\n");
  let failed = false;
  const check = (what, ok, t) => { log(`${what}: ${ok} (${(Date.now() - t) / 1000} s)`); if (!ok) failed = true; };
  fs.mkdirSync(out, { recursive: true });
  try {
    await new Promise((r) => setTimeout(r, 1500));
    await shot("1_login");
    if (await js(`document.querySelector("#auth").classList.contains("hidden")`)) {   // a session was open
      const t = Date.now();
      check("resumed without signing in", await wait(`!document.querySelector("#app").classList.contains("hidden")`, 1200), t);
      await new Promise((r) => setTimeout(r, 1500));
      await shot("1b_resumed");
      await js(`document.querySelector("#signout").click(); true`);
      await new Promise((r) => setTimeout(r, 1500));
      check("signed out, empty form", await js(`!document.querySelector("#login").classList.contains("hidden") &&
        document.querySelector("#f-email").value === "" && !document.querySelector("#auth").classList.contains("hidden")`), t);
      throw { stack: "end of the resume test (not an error)", resume: true };
    }
    await js(`document.querySelector("#tab-new").click(); document.querySelector("#f-name").value = "Sam Selftest";
      document.querySelector("#f-email").value = "sam.selftest@example.org"; document.querySelector("#f-pw").value = "selftest-123";
      document.querySelector("#auth").requestSubmit(); true`);
    await wait(`document.querySelector("#recovery").open || document.querySelector("#auth-error").textContent !== ""`, 1200);
    const code = await js(`document.querySelector("#recovery").open ? document.querySelector("#recovery-code").textContent : ""`);
    check("recovery code shown (" + code + ")", /^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code), Date.now());
    await shot("1c_recovery");
    await js(`document.querySelector("#recovery form button").click(); true`);
    const t0 = Date.now();
    await wait(`(!document.querySelector("#app").classList.contains("hidden") && document.querySelectorAll(".ex").length > 0)
      || document.querySelector("#auth-error").textContent !== ""`, 3000);   // (container: the first start downloads GB)
    const err = await js(`document.querySelector("#auth-error").textContent`);
    if (err) log("error shown: " + err);
    check("signed in", await js(`!document.querySelector("#app").classList.contains("hidden")`), t0);
    await new Promise((r) => setTimeout(r, 1500));
    await shot("2_catalogue");
    check("the introduction of the instrument is the first card of the catalogue",
      await js(`(() => { const c = document.querySelector(".ex"); return !!c && c.classList.contains("intro-card")
        && !!c.querySelector('[data-act="open"][data-mode="all"]'); })()`), Date.now());
    const t1 = Date.now();
    await js(`document.querySelector('[data-act="open"][data-mode="bsc"]').click(); true`);
    check("page loaded", await wait(`document.querySelectorAll(".pane .loading").length === 0 && document.querySelectorAll(".pane webview").length === 1`, 300), t1);
    await new Promise((r) => setTimeout(r, 4000));
    await shot("3_exercise");
    await js(`document.querySelector(".pane.on webview").executeJavaScript(
      "var q = document.querySelectorAll('.twq')[1]; if (q) { q.scrollIntoView(); var i = q.querySelector('input');" +
      " i.value = '4.05'; i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true}));" +
      " setTimeout(function () { q.querySelector('button').click(); }, 500); } !!q")`);
    await new Promise((r) => setTimeout(r, 3500));
    await shot("3b_question");
    await js(`document.querySelector(".pane.on webview").executeJavaScript(
      "var i = document.querySelector('img[alt]'); if (i) i.scrollIntoView(); !!(i && i.naturalWidth)").then(String)`)
      .then((r) => log("figure shown: " + r));
    await new Promise((r) => setTimeout(r, 1000));
    await shot("3c_figure");
    await js(`document.querySelector(".pane.on webview").executeJavaScript(
      "var b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('Submit my work'));" +
      " if (b) { b.scrollIntoView(); b.click(); } b ? true : [...document.querySelectorAll('button')].slice(-3).map(x => x.textContent).join(' | ')")`)
      .then((r) => log("submit button: " + r));
    await new Promise((r) => setTimeout(r, 3000));
    await shot("3d_submitted");
    const zips = fs.readdirSync(out).filter((f) => f.startsWith("download_") && f.endsWith(".zip"));
    check(`Submit my work: the file to save is offered at once (${zips.join(", ") || "nothing downloaded"})`, zips.length > 0, Date.now());
    await js(`document.querySelector("#tab-cat").click(); true`);
    await new Promise((r) => setTimeout(r, 1500));
    const t2 = Date.now();
    await js(`document.querySelector('[data-act="open"][data-mode="msc"]').click(); true`);
    check("notebook loaded", await wait(`document.querySelectorAll(".pane .loading").length === 0 && document.querySelectorAll(".pane webview").length === 2`, 300), t2);
    const t3 = Date.now();
    // at opening: the cells before the measurements run (up to the cell marked run_at_open: stop), none after;
    // every code cell read-only (MSc: nothing to write); the notebook shown from its top
    const nbState = `document.querySelectorAll(".pane.on webview")[0].executeJavaScript("(() => { const w = window.jupyterapp && window.jupyterapp.shell.currentWidget; if (!w || !w.content) return 'none'; const all = w.content.widgets; const k = all.findIndex(c => { const m = c.model.getMetadata ? c.model.getMetadata('twin') : null; return m && m.run_at_open === 'stop'; }); const stop = k < 0 ? all.length : k; const code = (a) => a.filter(c => c.model.type === 'code' && c.model.sharedModel.source.trim()); const before = code(all.slice(0, stop)), after = code(all.slice(stop)).filter(c => { const t = c.model.getMetadata ? c.model.getMetadata('twin') : null; return !(t && t.run_at_open === 'always'); }); const done = before.filter(c => c.model.executionCount).length; const late = after.filter(c => c.model.executionCount).length; const errs = before.filter(c => c.model.outputs.toJSON().some(o => o.output_type === 'error')).length; const ro = code(all).filter(c => c.readOnly).length; return done + '/' + before.length + ' errors ' + errs + ' after ' + late + ' readonly ' + ro + '/' + code(all).length + ' active ' + w.content.activeCellIndex; })()")`;
    let st = "";
    for (let i = 0; i < 300; i++) {
      st = await js(nbState).catch(() => "?");
      const m = /^(\d+)\/(\d+)/.exec(st);
      if (m && +m[1] === +m[2] && +m[2] > 0) break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    await new Promise((r) => setTimeout(r, 2000));
    st = await js(nbState).catch(() => "?");
    const m = /^(\d+)\/(\d+) errors (\d+) after (\d+) readonly (\d+)\/(\d+) active (\d+)/.exec(st);
    check(`notebook at opening: the cells before the measurements run, none after (${st})`,
      !!m && m[1] === m[2] && m[3] === "0" && m[4] === "0", t3);
    check(`MSc notebook: every code cell locked (${m ? m[5] + "/" + m[6] : "?"})`, !!m && m[5] === m[6], t3);
    check(`notebook shown from its top (active cell ${m ? m[7] : "?"})`, !!m && m[7] === "0", t3);
    // typed as a student would: click into a code cell, type; its code must not change
    const cellSrc = `document.querySelectorAll(".pane.on webview")[0].executeJavaScript("(() => { const w = window.jupyterapp.shell.currentWidget; const c = w.content.widgets.find(c => c.model.type === 'code' && c.model.sharedModel.source.trim()); return c.model.sharedModel.source; })()")`;
    const srcBefore = await js(cellSrc).catch(() => "?");
    await js(`document.querySelectorAll(".pane.on webview")[0].executeJavaScript("(() => { const w = window.jupyterapp.shell.currentWidget; const i = w.content.widgets.findIndex(c => c.model.type === 'code' && c.model.sharedModel.source.trim()); w.content.activeCellIndex = i; w.content.mode = 'edit'; w.content.widgets[i].editor.focus(); return i; })()")`);
    await new Promise((r) => setTimeout(r, 500));
    await js(`document.querySelectorAll(".pane.on webview")[0].focus(); true`);
    const inEditor = await js(`document.querySelectorAll(".pane.on webview")[0].executeJavaScript("!!(document.activeElement && document.activeElement.closest('.cm-content'))")`).catch(() => false);
    await js(`(() => { const v = document.querySelectorAll(".pane.on webview")[0];
      for (const ch of "TYPED") { v.sendInputEvent({ type: "keyDown", keyCode: ch }); v.sendInputEvent({ type: "char", keyCode: ch }); v.sendInputEvent({ type: "keyUp", keyCode: ch }); }
      v.sendInputEvent({ type: "keyDown", keyCode: "Backspace" }); v.sendInputEvent({ type: "keyUp", keyCode: "Backspace" });
      v.insertText("PASTED"); return true; })()`);
    await new Promise((r) => setTimeout(r, 1500));
    const srcAfter = await js(cellSrc).catch(() => "?");
    check(`MSc notebook: keys typed in a code cell change nothing (cursor in the cell: ${inEditor}; ${srcAfter === srcBefore ? "unchanged" : "the cell was changed"})`,
      inEditor === true && srcBefore !== "?" && srcAfter === srcBefore, t3);
    await js(`document.querySelectorAll(".pane.on webview")[0].executeJavaScript("(() => { const w = window.jupyterapp.shell.currentWidget; w.content.mode = 'command'; w.content.activeCellIndex = 0; w.content.scrollToCell(w.content.widgets[0]); return true; })()")`);
    await new Promise((r) => setTimeout(r, 2000));
    await shot("5_notebook");
    // the sample builder, opened for ODIN and a proposal (as from a beamtime notebook): a block, + a sphere, + a cylinder
    const t4 = Date.now();
    await js(`openTab("/voila/render/Sample_builder.ipynb?instrument=odin&proposal=1234", "page", "Sample builder"); true`);
    check("sample builder loaded", await wait(`document.querySelectorAll(".pane .loading").length === 0`, 180), t4);
    await new Promise((r) => setTimeout(r, 3000));
    const sb = (code) => js(`document.querySelector(".pane.on webview").executeJavaScript(${JSON.stringify(code)})`);
    const setX = (row, val) => `(() => { const rows = [...document.querySelectorAll('.widget-hbox')].filter(r => r.querySelector('.jupyter-button [class*=trash], .jupyter-button .fa-trash')); const i = rows[${row}].querySelector('input[type=number]'); i.value = '${val}'; i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true})); return rows.length; })()`;
    const click = (label) => `(() => { const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '${label}'); if (b) b.click(); return !!b; })()`;
    log("no instrument choice: " + await sb(`!document.body.innerText.includes('Instrument') || document.body.innerText.includes('Instrument: ODIN')`));
    for (let i = 0; i < 60; i++) {           // the widgets of the page come after its loading
      if (await sb(`[...document.querySelectorAll('button')].some(x => x.textContent.trim() === 'Add a sphere')`)) break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    log("add sphere: " + await sb(click("Add a sphere")));
    await new Promise((r) => setTimeout(r, 1500));
    log("add cylinder: " + await sb(click("Add a cylinder")));
    await new Promise((r) => setTimeout(r, 1500));
    log("rows: " + await sb(setX(1, 8)) + " " + await sb(setX(2, -8)));
    await new Promise((r) => setTimeout(r, 1000));
    await sb(click("Show my sample"));
    await new Promise((r) => setTimeout(r, 8000));
    log("shown: " + await sb(`['block 1:', 'sphere 2:', 'cylinder 3:', 'To fix'].map(k => k + ' ' + document.body.innerText.includes(k)).join(', ')`));
    await sb(`window.scrollTo(0, document.body.scrollHeight); true`);
    await new Promise((r) => setTimeout(r, 1000));
    await shot("6_sample_builder");
    await js(`document.querySelector("#tab-cat").click(); true`);
    await new Promise((r) => setTimeout(r, 2500));
    await shot("4_catalogue_again");
    log("progress: " + await js(`[...document.querySelectorAll(".prog .row span")].slice(0, 3).map(s => s.textContent).join(" | ")`));
    // Start again: the BSc (submitted) and the MSc (a notebook copy): back to "Not started"
    await js(`window.confirm = () => true; true`);
    for (const mode of ["bsc", "msc"]) {
      const ok = await js(`(() => { const b = document.querySelector('.again[data-mode="${mode}"]'); if (b) b.click(); return !!b; })()`);
      await new Promise((r) => setTimeout(r, 4000));
      log(`start again ${mode}: button ${ok}`);
    }
    const after = await js(`[...document.querySelectorAll(".prog .row span")].slice(0, 2).map(s => s.textContent).join(" | ")`);
    check("started again (" + after + ")", after === "Not started | Not started", Date.now());
    await shot("7_started_again");
    // the free beamtime: a new proposal each time (user office of the twin), then an imported proposal
    const t5 = Date.now();
    const newProposal = async (act, title, id, samples) => {
      await js(`document.querySelector('#free [data-act="${act}"]').click(); true`);
      await new Promise((r) => setTimeout(r, 800));
      await js(`document.querySelector("#p-title").value = ${JSON.stringify(title)};
        document.querySelector("#p-id").value = ${JSON.stringify(id)};
        document.querySelector("#p-samples").value = ${JSON.stringify(samples)};
        document.querySelector("#p-form").requestSubmit(); true`);
      return wait(`!document.querySelector("#proposal").open || document.querySelector("#p-error").textContent !== ""`, 60);
    };
    await newProposal("newfree", "Does a weld change the texture of steel?", "", "");
    const tabsAfter = await js(`[...document.querySelectorAll(".tab span:nth-child(2)")].map(s => s.textContent).join(" | ")`);
    check("free beamtime: a new proposal, its notebook opened (" + tabsAfter + ")", /ODIN · 9\d{5}/.test(tabsAfter), t5);
    await wait(`document.querySelectorAll(".pane .loading").length === 0`, 300);
    await new Promise((r) => setTimeout(r, 4000));
    const nbFree = await js(`document.querySelector(".pane.on webview").executeJavaScript("(() => { const w = window.jupyterapp && window.jupyterapp.shell.currentWidget; return w && w.content ? w.content.widgets.map(c => c.model.sharedModel.source).filter(s => s.includes('PROPOSAL = ')).join('') : 'none'; })()")`).catch(() => "?");
    check("free beamtime: the notebook has its number (" + nbFree.split("\n").filter((l) => l.startsWith("PROPOSAL")).join("") + ")",
          /PROPOSAL = "9\d{5}"/.test(nbFree), t5);
    await shot("8_free_beamtime");
    await js(`document.querySelector("#tab-cat").click(); true`);
    await new Promise((r) => setTimeout(r, 2000));
    await newProposal("newfree", "A second free beamtime", "", "");
    await js(`document.querySelector("#tab-cat").click(); true`);
    await new Promise((r) => setTimeout(r, 2000));
    const ids = await js(`[...document.querySelectorAll("#free .props .pid")].map(s => s.textContent).join(" ")`);
    check("free beamtime: each one is a new proposal, listed (" + ids + ")", ids.split(" ").filter(Boolean).length === 2
          && new Set(ids.split(" ")).size === 2, t5);
    await newProposal("import", "Residual strain in a turbine blade", "2025123", "Turbine blade, nickel alloy; Ni");
    await js(`document.querySelector("#tab-cat").click(); true`);
    await new Promise((r) => setTimeout(r, 2000));
    const listed = await js(`[...document.querySelectorAll("#free .props li")].map(li => [...li.querySelectorAll("span")].map(x => x.textContent.trim()).join(" ")).join(" / ")`);
    check("imported proposal listed (" + listed + ")", /2025123 Residual strain in a turbine blade imported/.test(listed), t5);
    await newProposal("import", "Again", "1234", "");
    const refused = await js(`document.querySelector("#p-error").textContent`);
    check("the number of an exercise cannot be imported (" + refused + ")", /proposal of an exercise/.test(refused), t5);
    await new Promise((r) => setTimeout(r, 500));
    await shot("9b_import_refused");
    await js(`document.querySelector("#p-cancel").click(); true`);
    await new Promise((r) => setTimeout(r, 500));
    await js(`document.querySelector("#free").scrollIntoView({ block: "center" }); true`);
    await new Promise((r) => setTimeout(r, 7000));      // (after the toasts)
    await shot("9_proposals");
  } catch (e) {
    if (e && e.resume) log(e.stack);
    else { log("ERROR " + e.stack); failed = true; }
  }
  log(failed ? "SELFTEST FAILED" : "SELFTEST PASSED");
  process.exitCode = failed ? 1 : 0;
  win.__closing = true;
  win.destroy();
}

app.setAppUserModelId("dk.dtu.access.twins");   // its own icon and group in the Windows taskbar
app.whenReady().then(() => {
  session.fromPartition("persist:twins").on("will-download", (_e, item) => {
    if (process.env.TWIN_APP_SELFTEST) {     // self-test: no window, the file goes to the folder of the screenshots
      item.setSavePath(path.join(process.env.TWIN_APP_SELFTEST, "download_" + item.getFilename()));
      return;
    }
    item.setSaveDialogOptions({ title: "Save the file for your teacher",
                                defaultPath: path.join(app.getPath("documents"), item.getFilename()) });
  });
  startBackend();
  createWindow();
  if (process.env.TWIN_APP_SELFTEST) {   // painted, but out of the screen and out of the taskbar
    win.setSkipTaskbar(true);
    win.setPosition(-20000, 0);
    const show = win.showInactive.bind(win);
    win.show = () => show();
    win.once("ready-to-show", () => selftest(process.env.TWIN_APP_SELFTEST));
  }
});

app.on("window-all-closed", async () => {
  if (backend) await backend.stop();
  app.exit(process.exitCode || 0);
});

if (!app.requestSingleInstanceLock()) app.quit();
else app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
