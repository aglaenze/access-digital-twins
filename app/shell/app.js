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

// the launch of NICOS on this computer, step by step (nicos/start_nicos.py writes the step; GET /twin/nicos reads it)
async function followNicosLaunch(name) {
  const t0 = Date.now();
  toast(`Starting NICOS of ${name}…`, 600000);
  for (let i = 0; i < 240; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    const st = await T.api("GET", "/twin/nicos").catch(() => null);
    const s = Math.round((Date.now() - t0) / 1000);
    if (!st || !st.time || st.time * 1000 < t0 - 2000) {          // (a step of an earlier launch)
      toast(`Starting NICOS of ${name}… (${s} s)`, 600000);
      continue;
    }
    if (st.state === "ready") { toast(`NICOS of ${name} is ready: its window appears on your desktop in a few seconds, logged in. Close it to stop NICOS.`, 12000); return; }
    if (st.state === "error" || st.state === "closed") { toast(st.step || "NICOS stopped.", 15000); return; }
    toast(`NICOS of ${name}: ${st.step}… (${s} s)`, 600000);
  }
  toast(`NICOS of ${name} takes long to start: see its logs in McStas_runs/twin/nicos.`, 15000);
}

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

// order of the catalogue: the introduction, then by number (0, 0 bis, 1, 2...), the planned ones in their place
function byPlace(a, b) {
  const n = (e) => e.number === undefined ? 1e3 : parseFloat(e.number) + (/bis/.test(e.number) ? 0.5 : 0);
  return ((b.kind === "introduction") - (a.kind === "introduction")) || (n(a) - n(b)) ||
         ((a.status === "planned") - (b.status === "planned"));
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
  ex.sort(byPlace);
  const num = (e) => e.number !== undefined ? `Exercise ${esc(e.number)} · ` : "";
  $("#exercises").innerHTML = ex.map((e, i) => e.status === "planned"
    ? `<article class="ex planned${e.later ? " later" : ""}"><div><span class="tech">${num(e)}${esc(e.technique)} · ${e.later ? "later" : "in preparation"}</span><h3>${esc(e.title)}</h3></div>
       ${e.sample ? `<p class="smp">${esc(e.sample)}</p>` : ""}<p class="q">${esc(e.question)}</p></article>`
    : e.kind === "introduction" ? introCard(e, i)
    : `<article class="ex"><div><span class="tech">${num(e)}${esc(e.technique)}</span><h3>${esc(e.title)}</h3></div>
       ${e.mission ? `<div class="mission">${ICON_TARGET}<span><b>Your mission.</b> ${esc(e.mission)}</span></div>` : ""}
       <div class="levels">${Object.entries(e.modes || {}).map(([k, m]) => level(e, k, m, i)).join("")}</div></article>`).join("");
  $("#exercises").querySelectorAll("[data-act]").forEach((b) => b.onclick = () => {
    const pick = b.closest(".level, .ex") && b.closest(".level, .ex").querySelector(".variant-pick");
    act(pick ? { ...b.dataset, variant: pick.value } : b.dataset);
  });
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
  // MSc: opened with its code (to read and follow the method) or without (as a BSc page: text, widgets, plots, and
  // a button "Analyze my files"); the same notebook, the same work, either way
  else if (k === "msc") {
    acts = `<button class="btn go" data-act="open" data-view="code" ${d} title="${go}: the code of each step is shown (and locked)">With code</button>
      <button class="btn go" data-act="open" data-view="clean" ${d} title="${go}: as a page of the BSc level (text, widgets and plots, no code)">Without code</button>`;
  }
  else acts = `<button class="btn" data-act="sheet" data-i="${i}" data-k="${k}">Your proposal</button>
      <button class="btn go" data-act="open" data-what="analysis" ${d}>Starter notebook</button>`;
  const again = p.status === "new" ? "" :
    `<button class="again" data-act="reset" ${d} data-file="${esc(k === "beamtime" ? m.analysis || "" : m.file || "")}"
       data-page="${m.open === "voila" ? 1 : 0}" title="Your notebook, your answers and the state of this exercise are put aside: you start from the beginning. Your measurements stay.">Start again</button>`;
  // an exercise with a choice of samples: a menu above the buttons (the buttons open the sample chosen)
  const variants = m.variants && k !== "beamtime" ? `<label class="variant">Sample <select class="variant-pick">${
    m.variants.map((v, n) => `<option value="${n}">${esc(v.label)}</option>`).join("")}</select></label>` : "";
  return `<div class="level"><div class="row"><span class="chip ${k}">${LEVEL[k] || k}</span><span class="dur">${esc(m.duration || "")}${again}</span></div>
    <span class="label">${esc(m.label)}</span><span class="what" title="${esc(m.what)}">${esc(m.what)}</span>
    <div class="prog">${variants}<div class="row"><span>${esc(p.text)}</span><b>${p.pct ? p.pct + " %" : ""}</b></div>
      <div class="track"><div class="fill ${k}" style="width:${p.pct}%"></div></div></div>
    <div class="acts">${acts}</div></div>`;
}

// the introduction of an instrument: one block (title, one line, progress and the button on the right)
function introCard(e, i) {
  const m = (e.modes || {}).all || {};
  const p = m.progress || { status: "new", text: "Not started", pct: 0 };
  const label = `${catalogue.instruments[e.instrument].name} · ${short(e.title)}`;
  const d = `data-dir="${esc(e.dir)}" data-mode="all" data-label="${esc(label)}"`;
  const go = p.status === "new" ? "Start" : (p.status === "done" ? "Open again" : "Continue");
  const again = p.status === "new" ? "" :
    `<button class="again" data-act="reset" ${d} data-file="${esc(m.file || "")}" data-page="${m.open === "voila" ? 1 : 0}"
       title="Your answers and the state of this introduction are put aside: you start from the beginning.">Start again</button>`;
  return `<article class="ex intro-card"><div class="intro-txt"><span class="tech">${esc(e.technique)} · ${esc(m.duration || "40 min")}</span>
      <h3>${esc(e.title)}</h3><p class="q">${esc(m.what || e.question)}</p></div>
    <div class="intro-act"><span class="st">${esc(p.text)}${p.pct ? " · " + p.pct + " %" : ""} ${again}</span>
      <button class="btn go" data-act="open" ${d}>${go}</button></div></article>`;
}

async function act(d) {
  try {
    if (d.act === "open") {
      const r = await T.api("POST", "/twin/open", { dir: d.dir, mode: d.mode, what: d.what || "file",
                                                     variant: d.variant ?? "" });
      const clean = d.mode === "msc" && (d.what || "file") === "file" && d.view === "clean";
      openTab(r.url, r.kind, d.what === "analysis" ? d.label.replace(/Beamtime$/, "Beamtime notebook") : d.label, { clean });
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
      else if (r.already) toast(`NICOS is already open: its window is on your desktop (one instrument at a time).`, 8000);
      else followNicosLaunch(name);
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
        .sort(byPlace)[+d.i];
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
  if (!imported) {        // a free beamtime: the first free number, which the student may change
    T.api("GET", "/twin/proposal").then((r) => { if (!$("#p-id").value) $("#p-id").value = r.next; }).catch(() => {});
  }
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

// MSc "Without code": the notebook shown as a page of the BSc level (clean_view.js: no header, menus or
// toolbar, outputs only, cells not selectable, a button "Analyze my files"); the choice can change while the tab is open
async function applyView(t) {
  if (t.kind !== "notebook" || (!t.clean && !t.cleanApplied)) return;     // with code: nothing to change
  t.cleanApplied = true;
  const cleanViewJs = "window.__twinCleanView = " + window.__twinCleanView.toString();   // (clean_view.js, loaded here)
  // the app of the notebook is ready only after a while: try again for up to a minute
  for (let k = 0; k < 60; k++) {
    const r = await t.view.executeJavaScript(`${cleanViewJs}; window.__twinCleanView(${!!t.clean})`).catch(() => "error");
    if (r !== "no app" && r !== "error") return;
    await new Promise((res) => setTimeout(res, 1000));
  }
}

function openTab(url, kind, label, { clean = false } = {}) {
  const key = url.split("?")[0] + (url.includes("instrument=") ? "?" + url.split("?")[1] : "");   // (NICOS: one tab per instrument)
  if (tabs.has(key)) {
    const t = tabs.get(key);
    if (t.kind === "notebook" && t.clean !== clean) { t.clean = clean; applyView(t); }
    activate(key);
    return;
  }
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
  // "Submit my work" (submit.py): its download link is clicked at once, so the window to save the file opens by itself
  view.addEventListener("dom-ready", () => {
    view.executeJavaScript(`(() => {
      if (window.__twinAutoDownload) return;
      window.__twinAutoDownload = true;
      new MutationObserver(() => {
        document.querySelectorAll("a[data-twin-autodownload]:not([data-twin-done])").forEach((a) => {
          a.setAttribute("data-twin-done", "1");
          a.click();
        });
      }).observe(document.documentElement, { childList: true, subtree: true });
    })()`).catch(() => {});
  });
  $("#stage").append(pane);
  $("#tabs").append(btn);
  const t0 = Date.now();
  const tick = setInterval(() => { cover.querySelector("[data-t]").textContent = Math.round((Date.now() - t0) / 1000) + " s"; }, 1000);
  const done = () => { clearInterval(tick); cover.remove(); btn.querySelector(".dot").classList.remove("loading"); };
  view.addEventListener("did-stop-loading", done, { once: true });
  view.addEventListener("did-fail-load", (e) => { if (e.errorCode !== -3) { done(); toast("The page did not load: " + e.errorDescription); } });
  const path = kind === "notebook" ? decodeURIComponent(key.replace(/^\/notebooks\//, "")) : null;
  const t = { btn, pane, view, kind, path, label, clean };
  if (kind === "notebook") {
    // a notebook opens already run: all its cells are executed once the kernel is ready (Notebook 7 exposes its
    // commands: exposeAppInBrowser in container/app_config/labconfig/page_config.json)
    view.addEventListener("did-stop-loading", () => {
      // the look of the app on the notebooks too (the questions, Submit, the buttons): the stylesheet of the pages
      view.executeJavaScript(`(() => { if (document.getElementById("twin-css")) return;
        const l = document.createElement("link"); l.id = "twin-css"; l.rel = "stylesheet";
        l.href = "${server.base}/voila/templates/twin/static/twin.css"; document.head.append(l); })()`).catch(() => {});
      applyView(t);
      // a locked text cell stays rendered: no raw markdown on a double click or on Enter (it could not be changed anyway)
      view.executeJavaScript(`(() => { if (window.__twinKeepRendered) return; window.__twinKeepRendered = true;
        const nb = () => { const w = window.jupyterapp && window.jupyterapp.shell.currentWidget; return w && w.content; };
        const locked = (c) => c && c.model.type === "markdown" && c.readOnly;
        window.addEventListener("dblclick", (e) => { const n = nb(); if (!n) return;
          const c = n.widgets.find((x) => x.node.contains(e.target));
          if (locked(c)) { e.stopPropagation(); e.preventDefault(); } }, true);
        window.addEventListener("keydown", (e) => { const n = nb(); if (!n || e.key !== "Enter" || n.mode !== "command") return;
          if (locked(n.activeCell)) { e.stopPropagation(); e.preventDefault(); } }, true); })()`).catch(() => {});
      // locked code cells look locked: gray, no blinking cursor, a "locked" mark (they cannot be changed anyway)
      view.insertCSS(`.jp-InputArea-editor.jp-mod-readOnly { background: #EEF0F3 !important; position: relative; }
        .jp-InputArea-editor.jp-mod-readOnly .cm-content { caret-color: transparent; cursor: default; }
        .jp-Cell-inputWrapper:has(.jp-InputPlaceholder) { display: none !important; }   /* hidden code (questions, buttons): not even its folded bar */
        .jp-InputArea-editor.jp-mod-readOnly::after { content: "\\1F512  locked"; position: absolute; top: 3px; right: 8px;
          font-size: 11px; color: #7A8190; pointer-events: none; }`).catch(() => {});
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
              // the questions after the mark need no measurement ({"twin": {"run_at_open": "always"}}): they run too,
              // so the student sees each question, never a cell to run
              for (let i = stop + 1; i < cells.length; i++) {
                const m = cells[i].model.getMetadata ? cells[i].model.getMetadata("twin") : (cells[i].model.metadata || {}).twin;
                if (m && m.run_at_open === "always") {
                  w.content.activeCellIndex = i;
                  await a.commands.execute("notebook:run-cell");
                }
              }
            } else {
              await a.commands.execute("notebook:run-all-cells");
            }
            // always back to the top of the notebook, and kept there while the outputs finish rendering (widgets
            // grow, JupyterLab scrolls to the cells it ran), unless the student scrolls or clicks first
            let touched = false;
            const stopIt = () => { touched = true; };
            for (const ev of ["wheel", "mousedown", "keydown", "touchstart"]) window.addEventListener(ev, stopIt, { once: true, capture: true });
            const top = async () => {
              try {
                w.content.activeCellIndex = 0;
                await w.content.scrollToCell(cells[0], "start");
              } catch (e) { /* older API */ }
              for (const n of [w.content.node, w.content.node.querySelector(".jp-WindowedPanel-outer"),
                               document.querySelector("#main-panel"), document.scrollingElement]) {
                try { if (n) n.scrollTop = 0; } catch (e) { /* */ }
              }
              window.dispatchEvent(new Event("resize"));      // the cells in view drawn again (as on showing the tab)
            };
            for (let k = 0; k < 16 && !touched; k++) {
              await top();
              await new Promise((r) => setTimeout(r, 500));
            }
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
