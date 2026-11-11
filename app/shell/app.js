// The shell of the app: sign in, the catalogue (GET /twin/catalogue), the open exercises as tabs (<webview>).
const T = window.twins;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let server = null;          // {base, token}
let user = null;
let catalogue = null;
let instr = localStorage.getItem("instr") || "odin";
const tabs = new Map();     // key -> {btn, pane, view, kind, path}
let activeKey = "cat";

function toast(text, ms = 5000) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.add("on");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("on"), ms);
}

// ------------------------------------------------------------------ sign in
let creating = false, resetting = false;
const GO = () => (resetting ? "Set my new password" : creating ? "Create my account" : "Sign in");
function setMode(c, reset = false) {
  creating = c && !reset;
  resetting = reset;
  $("#auth").classList.toggle("new", creating);
  $("#auth").classList.toggle("reset", resetting);
  $("#tab-in").classList.toggle("on", !creating);
  $("#tab-new").classList.toggle("on", creating);
  $("#go").textContent = GO();
  $("#f-pw-label").textContent = resetting ? "New password" : "Password";
  $("#f-pw").autocomplete = creating || resetting ? "new-password" : "off";
  $("#auth-error").textContent = "";
}
$("#tab-in").onclick = () => setMode(false);
$("#tab-new").onclick = () => setMode(true);
$("#forgot").onclick = (e) => { e.preventDefault(); setMode(false, true); };
$("#back-in").onclick = (e) => { e.preventDefault(); setMode(false); };

function showStatus(s) {
  const pct = Math.round((s.fraction || 0) * 100);
  $("#boot-text").textContent = s.error ? s.text : s.text;
  $("#boot-pct").textContent = s.error ? "" : (pct >= 100 ? "Ready" : pct + " %");
  $("#boot-bar").style.width = (s.error ? 100 : pct) + "%";
  $(".boot").classList.toggle("err", !!s.error);
  $("#boot-link").classList.toggle("hidden", !s.url);
  $("#boot-link").onclick = (e) => { e.preventDefault(); T.openExternal(s.url); };
}
T.on("status", showStatus);
T.status().then(showStatus);

// The student who did not sign out is signed in again at once; otherwise an empty form (no remembered email)
(async () => {
  const s = await T.session();
  if (!s) { if (!(await T.hasAccounts())) setMode(true); return; }
  $("#auth").classList.add("hidden");
  $("#boot-text").textContent = `Welcome back, ${s.name}: starting the instruments…`;
  try {
    const r = await T.resume();
    if (r && r.user) { server = { base: r.base, token: r.token }; user = r.user; enterApp(); return; }
  } catch { /* the form below */ }
  $("#auth").classList.remove("hidden");
})();

$("#auth").onsubmit = async (e) => {
  e.preventDefault();
  const form = { name: $("#f-name").value, email: $("#f-email").value, password: $("#f-pw").value,
                 code: $("#f-code").value };
  $("#go").disabled = true;
  $("#go").textContent = "Starting the instruments…";
  try {
    const r = resetting ? await T.resetPassword(form) : creating ? await T.createAccount(form) : await T.signIn(form);
    if (r.error) { $("#auth-error").textContent = r.error; return; }
    if (r.recovery) {                     // a new account: its recovery code, shown once
      $("#recovery-code").textContent = r.recovery;
      $("#recovery").showModal();
      await new Promise((ok) => $("#recovery").addEventListener("close", ok, { once: true }));
    }
    server = { base: r.base, token: r.token };
    user = r.user;
    $("#f-pw").value = "";
    $("#f-code").value = "";
    setMode(false);
    enterApp();
  } catch (err) {
    $("#auth-error").textContent = "The instruments did not start: " + (err.message || err);
  } finally {
    $("#go").disabled = false;
    $("#go").textContent = GO();
  }
};

// ------------------------------------------------------------------ the app
function enterApp() {
  // straight into the app (no fade: its timers and animation frames could hold the sign-in screen, 2026-11-10)
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  const initials = user.name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  $("#avatar").textContent = initials;
  $("#me-name").textContent = user.name;
  $("#menu-email").textContent = user.email;
  activate("cat");
  loadCatalogue();
}

$("#me").onclick = (e) => { e.stopPropagation(); $("#menu").classList.toggle("hidden"); };
document.addEventListener("click", () => $("#menu").classList.add("hidden"));
$("#signout").onclick = async () => {
  saveAll();
  for (const key of [...tabs.keys()]) closeTab(key);
  await T.signOut();
  user = null;
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  $("#auth").reset();
  $("#auth").classList.remove("hidden");
  setMode(false);
};
$("#handin").onclick = async () => {
  saveAll();
  await new Promise((r) => setTimeout(r, 800));
  const r = await T.handIn();
  if (r.file) toast(`Saved: ${r.file}. To hand in one exercise, use Submit at the end of the exercise.`, 9000);
  else if (r.error) toast(r.error);
};

// ------------------------------------------------------------------ catalogue
const ICON_TARGET = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="5"></circle><circle cx="12" cy="12" r="1"></circle></svg>';
const LEVEL = { bsc: "BSc", msc: "MSc", beamtime: "Beamtime", all: "All levels" };

async function loadCatalogue() {
  try {
    catalogue = await T.api("GET", "/twin/catalogue");
  } catch (e) {
    $("#exercises").innerHTML = `<p class="error">The catalogue could not be read: ${esc(e.message)}</p>`;
    return;
  }
  renderCatalogue();
}

function renderCatalogue() {
  const c = catalogue;
  // the introduction of an instrument (kind: introduction) is shown first and is not counted as an exercise
  const count = (k) => c.exercises.filter((e) => e.instrument === k && e.status !== "planned" && e.kind !== "introduction").length;
  if (!count(instr)) instr = Object.keys(c.instruments).find((k) => count(k)) || "odin";
  $("#instruments").innerHTML = Object.entries(c.instruments).map(([k, i]) => {
    const n = count(k);
    return `<button class="instr ${k === instr ? "on" : ""}" data-k="${k}" ${n ? "" : "disabled"}>
      <span class="top"><span class="name">${esc(i.name)}</span><span class="badge">${n ? n + (n > 1 ? " exercises" : " exercise") : "Later"}</span></span>
      <span class="kind">${esc(i.kind)}</span><span class="text">${esc(i.text)}</span></button>`;
  }).join("");
  $("#instruments").querySelectorAll(".instr").forEach((b) => b.onclick = () => {
    instr = b.dataset.k; localStorage.setItem("instr", instr); renderCatalogue();
  });
  const I = c.instruments[instr];
  $("#ex-title").textContent = `Exercises on ${I.name}`;
  const ex = c.exercises.filter((e) => e.instrument === instr);
  ex.sort((a, b) => ((b.kind === "introduction") - (a.kind === "introduction")) || ((a.status === "planned") - (b.status === "planned")));
  $("#exercises").innerHTML = ex.map((e, i) => e.status === "planned"
    ? `<article class="ex planned"><div><span class="tech">${esc(e.technique)} · planned</span><h3>${esc(e.title)}</h3></div><p class="q">${esc(e.question)}</p></article>`
    : `<article class="ex${e.kind === "introduction" ? " intro-card" : ""}"><div><span class="tech">${esc(e.technique)}</span><h3>${esc(e.title)}</h3></div>
       ${e.kind === "introduction" ? `<p class="q">${esc(e.question)} Start here: it takes about ${esc((e.modes.all || {}).duration || "40 min")}.</p>` : ""}
       ${e.mission ? `<div class="mission">${ICON_TARGET}<span><b>Your mission.</b> ${esc(e.mission)}</span></div>` : ""}
       <div class="levels">${Object.entries(e.modes || {}).map(([k, m]) => level(e, k, m, i)).join("")}</div></article>`).join("");
  $("#exercises").querySelectorAll("[data-act]").forEach((b) => b.onclick = () => act(b.dataset));
  const free = c.free[instr];
  // each free beamtime is a new proposal of the twin's user office (user_office.py); a real proposal can be imported
  const mine = (c.proposals || {})[instr] || [];
  const rows = mine.map((p) => `<li><span class="pid">${esc(p.id)}</span><span class="pt">${esc(p.title)}</span>
      <span class="pk">${p.kind === "imported" ? "imported" : "free"} · ${esc((p.created || "").slice(0, 10))}</span>
      <button class="btn" data-act="file" data-file="${esc(free)}" data-kind="notebook" data-proposal="${esc(p.id)}"
        data-label="${esc(I.name)} · ${esc(p.id)}">Continue</button></li>`).join("");
  $("#free").innerHTML = free ? `<article class="free"><div class="txt"><span class="tech">No exercise · MSc and beyond</span>
      <h3>Free beamtime on ${esc(I.name)}</h3><p>Your own question, your own samples, your own measurements: as in a real beamtime at ESS.
      Each free beamtime is a new proposal (its own number and data folder), found in NICOS with <i>Find my proposal</i>; no sample
      is imposed. Preparing a real beamtime? Import your proposal and try it on the twin.</p>
      ${rows ? `<ul class="props">${rows}</ul>` : ""}</div>
      <div class="acts"><button class="btn go" data-act="newfree">New free beamtime</button>
        <button class="btn" data-act="import">Import a proposal</button></div></article>` : "";
  $("#free").querySelectorAll("[data-act]").forEach((b) => b.onclick = () => act(b.dataset));
}

function short(title) {
  const t = title.replace(/\?$/, "").replace(/^How (far apart are|big are) /, "").replace(/ \(game\)$/, "").replace(/^Introduction to .*/, "Introduction");
  return t.length > 28 ? t.slice(0, 27) + "…" : t;
}

function level(e, k, m, i) {
  const p = m.progress || { status: "new", text: "Not started", pct: 0 };
  const label = `${catalogue.instruments[e.instrument].name} · ${short(e.title)} · ${LEVEL[k] || k}`;
  const d = `data-dir="${esc(e.dir)}" data-mode="${k}" data-label="${esc(label)}"`;
  const go = p.status === "new" ? "Start" : (p.status === "done" ? "Open again" : "Continue");
  let acts;
  if (k === "bsc" || k === "all") acts = `<button class="btn go" data-act="open" ${d}>${go}</button>`;
  // (NICOS and the sample builder are opened from the notebook itself: measuring is part of the exercise)
  else if (k === "msc") acts = `<button class="btn go" data-act="open" ${d}>${go === "Start" ? "Open the notebook" : go}</button>`;
  else acts = `<button class="btn" data-act="sheet" data-i="${i}" data-k="${k}">Your proposal</button>
      <button class="btn go" data-act="open" data-what="analysis" ${d}>Starter notebook</button>`;
  const again = p.status === "new" ? "" :
    `<button class="again" data-act="reset" ${d} data-file="${esc(k === "beamtime" ? m.analysis || "" : m.file || "")}"
       data-page="${m.open === "voila" ? 1 : 0}" title="Your notebook, your answers and the state of this exercise are put aside: you start from the beginning. Your measurements stay.">Start again</button>`;
  return `<div class="level"><div class="row"><span class="chip ${k}">${LEVEL[k] || k}</span><span class="dur">${esc(m.duration || "")}${again}</span></div>
    <span class="label">${esc(m.label)}</span><span class="what">${esc(m.what)}</span>
    <div class="prog"><div class="row"><span>${esc(p.text)}</span><b>${p.pct ? p.pct + " %" : ""}</b></div>
      <div class="track"><div class="fill ${k}" style="width:${p.pct}%"></div></div></div>
    <div class="acts">${acts}</div></div>`;
}

async function act(d) {
  try {
    if (d.act === "open") {
      const r = await T.api("POST", "/twin/open", { dir: d.dir, mode: d.mode, what: d.what || "file" });
      openTab(r.url, r.kind, d.what === "analysis" ? d.label.replace(/Beamtime$/, "Beamtime notebook") : d.label);
    } else if (d.act === "file") {
      const r = await T.api("POST", "/twin/open", { file: d.file, kind: d.kind, proposal: d.proposal || "" });
      openTab(r.url, r.kind, d.label);
    } else if (d.act === "newfree" || d.act === "import") {
      const p = await askProposal(d.act === "import");
      if (!p) return;
      const I = catalogue.instruments[instr];
      toast(`Proposal ${p.id} is in the user office: in NICOS, tab Experiment, Find my proposal, choose it, Apply.`, 9000);
      const r = await T.api("POST", "/twin/open", { file: catalogue.free[instr], kind: "notebook", proposal: p.id });
      openTab(r.url, r.kind, `${I.name} · ${p.id}`);
      loadCatalogue();
    } else if (d.act === "nicos") {
      const r = await T.api("POST", "/twin/nicos", { instrument: d.instr });
      const name = catalogue.instruments[d.instr].name;
      if (r.where === "remote") openTab(r.url, "desktop", `NICOS · ${name}`);
      else toast(`NICOS of ${name} opens on your desktop in about a minute, logged in. Close its window to stop it.`, 9000);
    } else if (d.act === "reset") {
      const what = d.page === "1" ? "your answers to the questions" : "your notebook and your answers";
      if (!confirm(`Start "${d.label}" again?\n\n${what[0].toUpperCase() + what.slice(1)} are put aside (kept in a ` +
                   `folder, not deleted) and you start from the beginning. Your measurements stay.`)) return;
      // its tab is closed first, without saving (otherwise the old notebook would be written again)
      const url = d.page === "1" ? `/voila/render/${d.file}`
        : `/notebooks/work/${user.id}/${d.dir.split("/")[0]}_${d.dir.split("/").pop()}/${d.file.split("/").pop()}`;
      if (tabs.has(url)) closeTab(url, { save: false });
      await new Promise((r) => setTimeout(r, 800));
      const r = await T.api("POST", "/twin/reset", { dir: d.dir, mode: d.mode });
      toast(r.put_aside && r.put_aside.length ? `Started again. Your previous work is kept in ${r.folder}.` : "Started again.", 8000);
      loadCatalogue();
    } else if (d.act === "sheet") {
      const e = catalogue.exercises.filter((x) => x.instrument === instr)
        .sort((a, b) => (a.status === "planned") - (b.status === "planned"))[+d.i];
      $("#sheet .sheet-body").innerHTML = e.modes[d.k].sheet || "";
      $("#sheet").showModal();
    }
  } catch (e) {
    toast("Could not open: " + (e.message || e), 8000);
  }
}

// a new free beamtime (its question) or an imported proposal (number, title, samples): the twin's user office
function askProposal(imported) {
  const dlg = $("#proposal");
  dlg.querySelector("h2").textContent = imported ? "Import a proposal" : "New free beamtime";
  dlg.querySelectorAll(".only-import").forEach((e) => e.classList.toggle("hidden", !imported));
  $("#p-title-label").textContent = imported ? "Title of the proposal" : "Your question";
  $("#p-title").value = ""; $("#p-id").value = ""; $("#p-samples").value = ""; $("#p-error").textContent = "";
  dlg.showModal();
  return new Promise((resolve) => {
    $("#p-cancel").onclick = () => { dlg.close(); resolve(null); };
    $("#p-form").onsubmit = async (ev) => {
      ev.preventDefault();
      const samples = $("#p-samples").value.split("\n").map((l) => l.trim()).filter(Boolean)
        .map((l) => { const [name, formula] = l.split(";"); return { name: name.trim(), formula: (formula || "").trim() }; });
      try {
        const p = await T.api("POST", "/twin/proposal", { instrument: instr, kind: imported ? "imported" : "free",
          title: $("#p-title").value, proposal: $("#p-id").value, samples });
        dlg.close(); resolve(p);
      } catch (e) {
        const m = /"error": "([^"]*)"/.exec(String(e.message || e));
        $("#p-error").textContent = m ? m[1] : String(e.message || e);
      }
    };
  });
}

// ------------------------------------------------------------------ tabs
function activate(key) {
  activeKey = key;
  $("#tab-cat").classList.toggle("on", key === "cat");
  $("#pane-cat").classList.toggle("on", key === "cat");
  for (const [k, t] of tabs) {
    t.btn.classList.toggle("on", k === key);
    t.pane.classList.toggle("on", k === key);
  }
  const t = tabs.get(key);
  $("#save").classList.toggle("hidden", !(t && t.kind === "notebook"));
  $("#saved").textContent = !t ? "" : t.kind === "notebook" ? (t.savedAt ? `Saved ${t.savedAt}` : "") :
    t.kind === "page" ? "Your answers are saved as you go" : "";
  if (key === "cat" && user) loadCatalogue();
}
$("#tab-cat").onclick = () => activate("cat");

function openTab(url, kind, label) {
  const key = url.split("?")[0] + (url.includes("instrument=") ? "?" + url.split("?")[1] : "");   // (NICOS: one tab per instrument)
  if (tabs.has(key)) { activate(key); return; }
  const btn = document.createElement("button");
  btn.className = "tab";
  btn.innerHTML = `<span class="dot loading"></span><span>${esc(label)}</span><span class="x" role="button" aria-label="Close ${esc(label)}">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg></span>`;
  const pane = document.createElement("section");
  pane.className = "pane";
  const view = document.createElement("webview");
  view.setAttribute("partition", "persist:twins");
  view.setAttribute("allowpopups", "");
  view.src = server.base + url + (url.includes("?") ? "&" : "?") + "token=" + server.token;
  const cover = document.createElement("div");
  cover.className = "loading";
  cover.innerHTML = `<div class="spinner"></div><span>Opening ${esc(label)}…</span><span class="small" data-t></span>`;
  pane.append(view, cover);
  $("#stage").append(pane);
  $("#tabs").append(btn);
  const t0 = Date.now();
  const tick = setInterval(() => { cover.querySelector("[data-t]").textContent = Math.round((Date.now() - t0) / 1000) + " s"; }, 1000);
  const done = () => { clearInterval(tick); cover.remove(); btn.querySelector(".dot").classList.remove("loading"); };
  view.addEventListener("did-stop-loading", done, { once: true });
  view.addEventListener("did-fail-load", (e) => { if (e.errorCode !== -3) { done(); toast("The page did not load: " + e.errorDescription); } });
  const path = kind === "notebook" ? decodeURIComponent(key.replace(/^\/notebooks\//, "")) : null;
  const t = { btn, pane, view, kind, path, label };
  if (kind === "notebook") {
    // a notebook opens already run: all its cells are executed once the kernel is ready (Notebook 7 exposes its
    // commands: exposeAppInBrowser in container/app_config/labconfig/page_config.json)
    view.addEventListener("did-stop-loading", () => {
      t.running = true;
      if (tabs.get(activeKey) === t) $("#saved").textContent = "Running the notebook…";
      view.executeJavaScript(`(async () => {
        for (let i = 0; i < 240; i++) {
          const a = window.jupyterapp, w = a && a.shell && a.shell.currentWidget;
          if (w && w.sessionContext && w.content && w.content.widgets && w.content.widgets.length) {
            await w.sessionContext.ready;
            // only the cells before the measurements run at opening: they stop at the cell marked
            // {"twin": {"run_at_open": "stop"}} (the generators of the MSc notebooks); without a mark, all of them
            const cells = w.content.widgets;
            const stop = cells.findIndex((c) => {
              const m = c.model.getMetadata ? c.model.getMetadata("twin") : (c.model.metadata || {}).twin;
              return m && m.run_at_open === "stop";
            });
            if (stop > 0) {
              w.content.activeCellIndex = stop;
              await a.commands.execute("notebook:run-all-above");
            } else {
              await a.commands.execute("notebook:run-all-cells");
            }
            // always back to the top of the notebook
            try {
              w.content.activeCellIndex = 0;
              await w.content.scrollToCell(cells[0], "start");
            } catch (e) { /* older API */ }
            try { w.content.node.scrollTop = 0; } catch (e) { /* */ }
            return "done";
          }
          await new Promise((r) => setTimeout(r, 500));
        }
        return "no notebook";
      })()`).catch(() => "error").then(() => {
        t.running = false;
        if (tabs.get(activeKey) === t) $("#saved").textContent = t.savedAt ? `Saved ${t.savedAt}` : "Ready";
      });
    }, { once: true });
  }
  tabs.set(key, t);
  btn.onclick = (e) => { if (e.target.closest(".x")) closeTab(key); else activate(key); };
  activate(key);
}

function save(t) {
  if (t.kind !== "notebook") return;
  try {
    t.view.focus();
    t.view.sendInputEvent({ type: "keyDown", keyCode: "S", modifiers: ["control"] });
    t.view.sendInputEvent({ type: "keyUp", keyCode: "S", modifiers: ["control"] });
    t.savedAt = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (tabs.get(activeKey) === t) $("#saved").textContent = `Saved ${t.savedAt}`;
  } catch { /* not loaded yet */ }
}
function saveAll() { for (const t of tabs.values()) save(t); }
$("#save").onclick = () => { const t = tabs.get(activeKey); if (t) save(t); };
setInterval(saveAll, 120000);
T.on("before-quit", saveAll);

function closeTab(key, { save: doSave = true } = {}) {
  const t = tabs.get(key);
  if (!t) return;
  if (doSave) save(t);
  setTimeout(() => {
    t.pane.remove();
    if (t.path) T.closeNotebook(t.path);
  }, t.kind === "notebook" ? 700 : 0);
  t.btn.remove();
  tabs.delete(key);
  if (activeKey === key) activate("cat");
}

// links of the pages that open a new window: a new tab
T.on("open-url", (url) => {
  if (!server) return;
  const u = new URL(url);
  const p = u.pathname + (u.search ? u.search.replace(/([?&])token=[^&]*&?/, "$1").replace(/[?&]$/, "") : "");
  const instr = u.searchParams.get("instrument");
  const file = decodeURIComponent(u.pathname.split("/").pop() || "Page").replace(/\.ipynb$/, "");
  // the button Open NICOS of a notebook: the same as the button of the catalogue. On this computer (local app) NICOS
  // opens as its own window: a short message, no tab. In the container: the tab of the control room.
  if (file === "open_nicos" && instr) {
    act({ act: "nicos", instr });
    return;
  }
  const name = file === "open_nicos" ? `NICOS · ${({ odin: "ODIN", loki: "LoKI" })[instr] || ""}`
    : file === "Sample_builder" ? "Sample builder" : file;
  openTab(p, u.pathname.startsWith("/notebooks/") ? "notebook" : "page", name);
});
