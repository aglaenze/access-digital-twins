// The shell of the app: sign in, the catalogue (GET /twin/catalogue), the open exercises as tabs (<webview>).
const T = window.twins;
const $ = (s) => document.querySelector(s);
if (T && T.platform === "darwin") document.documentElement.classList.add("mac");   // room for its window buttons
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
  if (T.titlebar) T.titlebar("dark");
  const initials = user.name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  $("#avatar").textContent = initials;
  $("#me-name").textContent = user.name;
  $("#menu-email").textContent = user.email;
  teacherMenu();
  activate("cat");
  loadCatalogue();
}

$("#me").onclick = (e) => { e.stopPropagation(); $("#menu").classList.toggle("hidden"); };
document.addEventListener("click", () => $("#menu").classList.add("hidden"));
// the teacher view: entered with the teacher code (menu of the account), left from the same menu
$("#teach").onclick = async () => {
  if (user.teacher) {
    const r = await T.teacher("", false);
    if (r.user) { user = r.user; if (pref("level") === "all") pref("level", "bsc"); }
    teacherMenu(); renderCatalogue(); toast("You see the catalogue as a student again.");
    return;
  }
  $("#t-code").value = ""; $("#t-error").textContent = "";
  $("#teacher").showModal();
};
$("#t-cancel").onclick = () => $("#teacher").close();
$("#t-form").onsubmit = async (ev) => {
  ev.preventDefault();
  const r = await T.teacher($("#t-code").value, true);
  if (r.error) { $("#t-error").textContent = r.error; return; }
  user = r.user;
  pref("level", "all");
  $("#teacher").close();
  teacherMenu(); renderCatalogue();
  toast("Teacher view: every exercise at every level. Choose a role to see the catalogue as a student does.", 8000);
};
function teacherMenu() {
  $("#teach").textContent = user && user.teacher ? "Leave the teacher view" : "Teacher view…";
  // the classes are part of the teacher view
  $("#tab-classes").classList.toggle("hidden", !(user && user.teacher));
  if (!(user && user.teacher) && activeKey === "classes") activate("cat");
}
$("#signout").onclick = async () => {
  saveAll();
  for (const key of [...tabs.keys()]) closeTab(key);
  await T.signOut();
  user = null;
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  if (T.titlebar) T.titlebar("light");
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

// The level of the student = their grade in the team of the story (STORY.md), chosen with the instrument and kept
// (per account, on this computer). A teacher (teacher code) also has "All levels": every exercise at every level.
const ROLES = {
  bsc: { grade: "Trainee", chip: "BSc", text: "The instrument is set up for you: measure, then answer the client. Guided pages, no code." },
  msc: { grade: "Method scientist", chip: "MSc", text: "The client needs a method they can trust: you choose and justify each step." },
  beamtime: { grade: "Lead scientist", chip: "On your own", text: "Your proposal was accepted: plan and run the beamtime in NICOS, then analyze your files." },
  all: { grade: "All levels", chip: "Teacher", text: "Every exercise at every level, on one page." },
};
function pref(k, v) {               // a choice of this student, kept on this computer
  const key = `${k}:${user ? user.id : ""}`;
  try {
    if (v === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, v);
  } catch { /* no storage: the choice lasts until the page is closed */ }
  return v;
}
function currentLevel() {
  const l = pref("level");
  if (l === "all" && !(user && user.teacher)) return null;
  return ROLES[l] ? l : null;
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
  const lvl = currentLevel();
  const I = c.instruments[instr];
  const ex = c.exercises.filter((e) => e.instrument === instr);
  ex.sort(byPlace);
  // the introduction of the instrument comes first, before the role: it is the same for every level
  $("#intro").innerHTML = ex.filter((e) => e.kind === "introduction").map((e, i) => introCard(e, i)).join("");
  renderRoles();
  const rest = ex.filter((e) => e.kind !== "introduction");
  $("#ex-title").textContent = lvl === "all" ? `Exercises on ${I.name}` : "";
  $("#ex-title").classList.toggle("hidden", lvl !== "all");
  if (lvl === "all") renderAll(rest);
  else renderStory(rest, lvl);
  for (const box of ["#intro", "#exercises"]) {
    $(box).querySelectorAll("[data-act]").forEach((b) => b.onclick = () => {
      const pick = b.closest(".level, .ex") && b.closest(".level, .ex").querySelector(".variant-pick");
      act(pick ? { ...b.dataset, variant: pick.value } : b.dataset);
    });
  }
  renderFree(lvl);
}

// the choice of the role (the level), after the introduction; MSc: with or without code
function renderRoles() {
  const lvl = currentLevel();
  const keys = ["bsc", "msc", "beamtime"].concat(user && user.teacher ? ["all"] : []);
  const view = pref("mscview") === "clean" ? "clean" : "code";
  $("#roles").innerHTML = `<div class="roles-head"><h2>Your role in the team</h2>
      <p>${lvl ? "You can change it at any time: your work at each level is kept." :
        "Choose it first: the requests, and the way you work on them, follow from it."}</p></div>
    <div class="role-grid n${keys.length}">${keys.map((k) => `<button class="role ${k}${k === lvl ? " on" : ""}" data-level="${k}">
      <span class="top"><span class="grade">${ROLES[k].grade}</span><span class="chip ${k}">${ROLES[k].chip}</span></span>
      <span class="text">${ROLES[k].text}</span>
      ${k === "msc" ? `<span class="seg view" role="group" aria-label="Notebooks">
        <span role="button" data-view="code" class="${view === "code" ? "on" : ""}" title="The code of each step is shown (and locked)">With code</span>
        <span role="button" data-view="clean" class="${view === "clean" ? "on" : ""}" title="As a guided page: text, widgets and plots, no code">Without code</span></span>` : ""}
      </button>`).join("")}</div>`;
  $("#roles").querySelectorAll(".role").forEach((b) => b.onclick = (ev) => {
    const v = ev.target.closest("[data-view]");
    if (v) pref("mscview", v.dataset.view);
    pref("level", b.dataset.level);
    renderCatalogue();
  });
}

// the progress of one chapter: of its sample when the chapter is one sample of an exercise (exercise 7)
function chapterProgress(s, m) {
  return (s.variant !== undefined && m.variants ? (m.variants[s.variant] || {}).progress : m.progress) ||
         { status: "new", text: "Not started", pct: 0 };
}

// emblems of the threads (the clients of the story) and of the grades
const EMBLEM = {
  energy: '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 22v20M19 42h10"/><circle cx="24" cy="20" r="2.6"/><path d="M24 17.4C23 11 23.5 7 24 4c1.6 3.4 2 8 .9 13.6M26.3 21.4c5.6 2.6 8.8 5.2 10.8 7.6-3.8.3-8.2-.7-12.6-4.4M21.6 21.6c-4.9 3.7-8.7 5.1-11.7 5.6 1.7-3.4 5-6.6 10.4-8.4"/></svg>',
  planets: '<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="10"/><path d="M14.6 27.6C7.4 31.3 4 34.6 5.2 36.2c2 2.7 12.6-.9 23.6-8.1S44.9 14.5 42.9 11.8c-1.1-1.5-5.3-.6-10.6 1.9"/><circle cx="38" cy="36" r="1.6"/><circle cx="9" cy="12" r="1.2"/></svg>',
  instrument: '<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="6"/><path d="M24 6v6M24 36v6M6 24h6M36 24h6M11.3 11.3l4.2 4.2M32.5 32.5l4.2 4.2M11.3 36.7l4.2-4.2M32.5 15.5l4.2-4.2"/></svg>',
};
const ICON_CHECK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.2 4.2L19 7"/></svg>';
const ICON_PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg>';

let mapCards = [];        // the chapters of the map now shown (for the briefing)

// the student's view: the map of the requests of the chosen level, one lane per thread of the story (STORY.md), and
// the briefing of the chapter chosen on the map (its mission, its progress, the buttons)
function renderStory(ex, lvl) {
  const c = catalogue;
  if (!lvl) {
    $("#exercises").innerHTML = `<div class="pick-role">Choose your role above: the requests that wait for you appear here.</div>`;
    return;
  }
  // the chapters: one per exercise, or one per sample when its samples belong to two threads (exercise 7)
  const cards = [];
  const loose = [];
  for (const e of ex) {
    const m = (e.modes || {})[lvl];
    let st = Array.isArray(e.story) ? e.story : e.story ? [e.story] : [];
    // no choice of sample at this level (the beamtime has both samples): one chapter, with the mission of the exercise
    if (!(m && m.variants)) st = st.filter((x, n) => x.variant === undefined || n === 0)
      .map((x) => x.variant === undefined ? x : { thread: x.thread, client: x.client });
    if (!st.length) { loose.push(e); continue; }
    for (const s of st) {
      const key = e.dir ? e.dir + (s.variant !== undefined ? "#" + s.variant : "") : "planned:" + e.title;
      const live = !!m && e.status !== "planned";
      cards.push({ e, s, m, key, live, p: live ? chapterProgress(s, m) : null });
    }
  }
  mapCards = cards;
  const threads = Object.keys(c.threads || {}).filter((t) => cards.some((x) => x.s.thread === t));
  // the chapters are numbered along their thread (1, 2, 3...), in the order of the catalogue; the numbers of the
  // exercises (the themes of ODIN) are only in the teacher's view
  for (const t of threads) cards.filter((x) => x.s.thread === t).forEach((x, i) => { x.num = String(i + 1); });
  // the next request: the one the student opened or started again last, while it is not finished; else the first
  // started (not submitted), else the first not started
  const playable = cards.filter((x) => x.live);
  const open = (x) => !(x.p.submitted || x.p.status === "done");
  const last = playable.find((x) => x.key === pref(`last:${instr}:${lvl}`));
  const next = (last && open(last) ? last : null) || playable.find((x) => x.p.status === "started") ||
               playable.find((x) => x.p.status === "new");
  let sel = pref(`sel:${instr}:${lvl}`);
  if (!cards.some((x) => x.key === sel)) sel = (next || playable[0] || cards[0] || {}).key;
  // the record of the student at this level: requests answered (submitted), questions right at the first try
  const live = playable.map((x) => x.p);
  const sum = (k) => live.reduce((a, p) => a + (p[k] || 0), 0);
  const answered = live.filter((p) => p.submitted).length;
  const done = sum("right") + sum("revealed");
  const hud = `<div class="hud"><div class="rank"><span class="rank-badge ${lvl}">${esc(ROLES[lvl].chip)}</span>
      <span class="rank-txt"><b>${esc(ROLES[lvl].grade)}</b><span>Neutron Solutions Team · ${esc(c.instruments[instr].name)}</span></span></div>
    <div class="stats"><div class="stat"><span class="v">${answered}<small> / ${live.length}</small></span><span class="k">requests answered</span>
        <span class="mini"><i style="width:${live.length ? 100 * answered / live.length : 0}%"></i></span></div>
      ${lvl !== "beamtime" && done ? `<div class="stat"><span class="v">${sum("first")}<small> / ${done}</small></span><span class="k">right at the first try</span>
        <span class="mini"><i style="width:${done ? 100 * sum("first") / done : 0}%"></i></span></div>` : ""}</div></div>`;
  const lanes = threads.map((t) => {
    const T = c.threads[t];
    const mine = cards.filter((x) => x.s.thread === t);
    const ok = mine.filter((x) => x.live && x.p.submitted).length;
    const n = mine.filter((x) => x.live).length;
    return `<section class="lane ${t}"><div class="lane-head"><span class="emblem">${EMBLEM[t] || ""}</span>
        <span class="lane-txt"><span class="tname">${esc(T.name)}</span><b>${esc(T.client)}</b>
        <span class="lane-n">${ok} of ${n} answered</span></span></div>
      <div class="nodes">${mine.map((x) => node(x, x.key === sel, next && x.key === next.key)).join("")}</div></section>`;
  }).join("");
  $("#exercises").innerHTML = `<div class="campaign">${hud}<div class="camp-body"><div class="map">${lanes}
      ${loose.length ? `<div class="loose"><span class="tech">Also in preparation</span>${loose.map((e) =>
        `<span>${esc(e.title)}</span>`).join("")}</div>` : ""}</div>
    <aside class="brief" id="brief"></aside></div></div>`;
  $("#exercises").querySelectorAll(".node").forEach((b) => b.onclick = () => {
    pref(`sel:${instr}:${lvl}`, b.dataset.key);
    $("#exercises").querySelectorAll(".node").forEach((x) => x.classList.toggle("sel", x === b));
    brief(b.dataset.key, lvl);
    $("#brief").classList.add("anim");       // (animated when the student picks a chapter, not at each refresh)
  });
  brief(sel, lvl);
}

// one chapter on the map: a ring that fills with the progress, a check when the work is submitted
function node(x, sel, next) {
  const { e, s, p } = x;
  const name = s.short || e.short || e.title;
  const st = !x.live ? (e.status === "planned" ? "planned" : "off") : p.submitted || p.status === "done" ? "done" : p.status;
  const inner = st === "done" ? ICON_CHECK : `<span class="n">${esc(x.num)}</span>`;
  return `<button class="node ${st}${sel ? " sel" : ""}${next ? " next" : ""}" data-key="${esc(x.key)}" style="--p:${x.live ? p.pct || 0 : 0}"
      title="${esc(e.title)}"><span class="orb">${inner}</span>${next ? `<span class="flag">Next</span>` : ""}
    <span class="nt">${esc(name)}</span><span class="nsub">${st === "planned" ? (e.later ? "Later" : "In preparation")
      : st === "off" ? "Guided page only" : st === "done" ? "Answered" : st === "started" ? `${p.pct || 0} %` : "New"}</span></button>`;
}

// the briefing of the chosen chapter: who asks, what, how far the student is, and the buttons
function brief(key, lvl) {
  const x = mapCards.find((y) => y.key === key);
  const box = $("#brief");
  if (!x) { box.innerHTML = ""; return; }
  const { e, s, m } = x;
  box.className = `brief ${s.thread || ""}`;
  const num = `${esc((catalogue.threads[s.thread] || {}).name || "")} · Chapter ${esc(x.num)}`;
  const vlabel = s.variant !== undefined && m && m.variants ? (m.variants[s.variant] || {}).label : "";
  const head = `<div class="b-kicker"><span>${num}</span><span>${esc(s.client || "")}</span></div>
    <h3>${esc(e.title)}</h3>${vlabel ? `<span class="b-sample">${esc(vlabel)}</span>` : ""}`;
  const mission = (m && m.mission) || s.mission || e.mission || e.question;
  if (e.status === "planned") {
    box.innerHTML = `${head}<p class="b-mission">${esc(e.question)}</p>
      <div class="b-intel"><span><i>Technique</i>${esc(e.technique || "")}</span><span><i>Status</i>${e.later ? "Later" : "In preparation"}</span></div>`;
    return;
  }
  if (!m) {          // this request has no version at this level (a game: a guided page only)
    const other = Object.keys(e.modes || {})[0];
    const om = (e.modes || {})[other] || {};
    const label = `${catalogue.instruments[e.instrument].name} · ${short(e.title)} · ${LEVEL[other] || other}`;
    box.innerHTML = `${head}<p class="b-mission">${esc(mission)}</p>
      <div class="b-intel"><span><i>Format</i>${esc(om.label || "Guided page")}</span><span><i>Duration</i>${esc(om.duration || "")}</span>
        <span><i>Level</i>Only as a ${esc(LEVEL[other] || other)} page</span></div>
      <div class="b-acts"><button class="btn go" data-act="open" data-dir="${esc(e.dir)}" data-mode="${other}" data-label="${esc(label)}">${ICON_PLAY}Open</button></div>`;
    wire(box, key, lvl);
    return;
  }
  const p = x.p;
  const short2 = vlabel ? " · " + vlabel.split(" (")[0].replace(/^The /, "") : "";
  const label = `${catalogue.instruments[e.instrument].name} · ${short(e.title)}${short2} · ${LEVEL[lvl] || lvl}`;
  const d = `data-dir="${esc(e.dir)}" data-mode="${lvl}" data-label="${esc(label)}"` +
            (s.variant !== undefined && m.variants ? ` data-variant="${s.variant}"` : "");
  const go = p.status === "new" ? "Start" : (p.status === "done" ? "Open again" : "Continue");
  let acts;
  if (lvl === "bsc") acts = `<button class="btn go" data-act="open" ${d}>${ICON_PLAY}${go}</button>`;
  else if (lvl === "msc") {
    const view = pref("mscview") === "clean" ? "clean" : "code";
    // (with or without code: chosen once on the role card, not repeated on the button)
    acts = `<button class="btn go" data-act="open" data-view="${view}" ${d}>${ICON_PLAY}${go}</button>`;
  } else acts = `<button class="btn go" data-act="open" data-what="analysis" ${d}>${ICON_PLAY}Starter notebook</button>
      <button class="btn" data-act="sheet" data-dir="${esc(e.dir)}" data-k="${lvl}">Your proposal</button>`;
  const again = p.status === "new" ? "" :
    `<button class="again" data-act="reset" ${d} data-file="${esc(lvl === "beamtime" ? m.analysis || "" : m.file || "")}"
       data-page="${m.open === "voila" ? 1 : 0}" title="Your notebook, your answers and the state of this exercise are put aside: you start from the beginning. Your measurements stay.">Start again</button>`;
  const first = p.total && (p.right || p.revealed) ? `<span><i>First try</i>${p.first || 0} of ${p.total} questions</span>` : "";
  box.innerHTML = `${head}<p class="b-mission">${esc(mission)}</p>
    <div class="b-intel"><span><i>Format</i>${esc(m.label || "")}</span><span><i>Duration</i>${esc(m.duration || "")}</span>
      ${first}${p.submitted ? `<span><i>Submitted</i>${esc(p.submitted)}</span>` : ""}</div>
    <div class="prog"><div class="row"><span>${esc(p.text)}</span>${again}</div>
      <div class="track"><div class="fill" style="width:${p.pct}%"></div></div></div>
    <div class="b-acts">${acts}</div>`;
  wire(box, key, lvl);
}
// the buttons of the briefing; a chapter opened stays the chosen one on the map (when the student comes back)
function wire(box, key, lvl) {
  box.querySelectorAll("[data-act]").forEach((b) => b.onclick = () => {
    // a chapter opened or started again: it stays chosen on the map, and becomes the next request (until submitted)
    if (b.dataset.act === "open" || b.dataset.act === "reset") { pref(`sel:${instr}:${lvl}`, key); pref(`last:${instr}:${lvl}`, key); }
    act(b.dataset);
  });
}

// the teacher's view: every exercise with all its levels (the catalogue as it was before the roles)
function renderAll(ex) {
  const num = (e) => e.number !== undefined ? `Exercise ${esc(e.number)} · ` : "";
  $("#exercises").innerHTML = ex.map((e, i) => e.status === "planned"
    ? `<article class="ex planned${e.later ? " later" : ""}"><div><span class="tech">${num(e)}${esc(e.technique)} · ${e.later ? "later" : "in preparation"}</span><h3>${esc(e.title)}</h3></div>
       ${e.sample ? `<p class="smp">${esc(e.sample)}</p>` : ""}<p class="q">${esc(e.question)}</p></article>`
    : e.kind === "introduction" ? introCard(e, i)
    : `<article class="ex"><div><span class="tech">${num(e)}${esc(e.technique)}</span><h3>${esc(e.title)}</h3></div>
       ${e.mission ? `<div class="mission">${ICON_TARGET}<span><b>Your mission.</b> ${esc(e.mission)}</span></div>` : ""}
       <div class="levels">${Object.entries(e.modes || {}).map(([k, m]) => level(e, k, m, i)).join("")}</div></article>`).join("");
}

// the free beamtime: for the students on their own (and in the teacher's view)
function renderFree(lvl) {
  const c = catalogue;
  const I = c.instruments[instr];
  const free = (lvl === "beamtime" || lvl === "all") ? c.free[instr] : null;
  // each free beamtime is a new proposal of the twin's user office (user_office.py); a real proposal can be imported
  const mine = (c.proposals || {})[instr] || [];
  const rows = mine.map((p) => `<li><span class="pid">${esc(p.id)}</span><span class="pt">${esc(p.title)}</span>
      <span class="pk">${p.kind === "imported" ? "imported" : "free"} · ${esc((p.created || "").slice(0, 10))}</span>
      <button class="btn" data-act="file" data-file="${esc(free)}" data-kind="notebook" data-proposal="${esc(p.id)}"
        data-label="${esc(I.name)} · ${esc(p.id)}">Continue</button>
      <button class="btn del" data-act="delprop" data-proposal="${esc(p.id)}" data-title="${esc(p.title)}"
        title="Delete this proposal">Delete</button></li>`).join("");
  $("#free").innerHTML = free ? `<article class="free"><div class="txt"><span class="tech">No exercise · your own project</span>
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
  else acts = `<button class="btn" data-act="sheet" data-dir="${esc(e.dir)}" data-k="${k}">Your proposal</button>
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
    } else if (d.act === "delprop") {
      if (!confirm(`Delete proposal ${d.proposal}, "${d.title}"?

NICOS will no longer list it. Its notebook is put ` +
                   `aside (kept in a folder, not deleted) and your measured files stay.`)) return;
      // its tab is closed first, without saving (otherwise the notebook would be written again)
      const f = catalogue.free[instr];
      const url = `/notebooks/work/${user.id}/${instr}_free_beamtime_${d.proposal}/${f.split("/").pop()}`;
      if (tabs.has(url)) closeTab(url, { save: false });
      await new Promise((r) => setTimeout(r, 800));
      await T.api("DELETE", `/twin/proposal?id=${encodeURIComponent(d.proposal)}`);
      toast(`Proposal ${d.proposal} deleted.`, 6000);
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
      const e = catalogue.exercises.find((x) => x.dir === d.dir);
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
  $("#tab-classes").classList.toggle("on", key === "classes");
  $("#pane-classes").classList.toggle("on", key === "classes");
  if (Classes) { if (key === "classes") Classes.show(); else Classes.hide(); }
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
$("#tab-classes").onclick = () => activate("classes");

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
  let ready = null;          // (a notebook: the check of its first run)
  const done = () => { clearInterval(tick); clearInterval(ready); cover.remove(); btn.querySelector(".dot").classList.remove("loading"); };
  // a page (Voila) comes whole from the server: shown when loaded. A notebook is built in the browser and its first
  // cells run after: it stays covered until they have run and it is back at its top (no cells appearing one by one)
  if (kind !== "notebook") view.addEventListener("did-stop-loading", done, { once: true });
  else setTimeout(done, 240000);          // (never covered for good, whatever happens)
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
        l.href = "${server.base}/voila/templates/twin/static/twin.css?v=" + Date.now();      // (never an old copy)
        document.head.append(l); })()`).catch(() => {});
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
      cover.querySelector("span").textContent = `Preparing ${label}: its first cells are running…`;
      ready = setInterval(() => {
        view.executeJavaScript("!!window.__twinReady").then((r) => { if (r) done(); }).catch(() => {});
      }, 400);
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
            // the widgets saved with the notebook (buttons, panels, pictures in an output area) cannot be drawn
            // again without the kernel that made them: they would show "Loading widget..." forever. Their outputs
            // are cleared; the cells run again (at opening, or with "Analyze my files") draw them anew.
            for (const c of cells) {
              if (c.model.type !== "code" || !c.model.outputs) continue;
              const outs = c.model.outputs.toJSON();
              if (outs.some((o) => o.data && o.data["application/vnd.jupyter.widget-view+json"])) c.model.outputs.clear();
            }
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
            // the first outputs drawn at the top: the notebook is shown (the cover of the app is removed)
            await top();
            await new Promise((r) => setTimeout(r, 800));
            window.__twinReady = true;
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
        done();
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
  // hidden at once (it stays a moment, out of sight, for its last save): the catalogue shows without it on top
  t.pane.classList.remove("on");
  t.pane.style.visibility = "hidden";
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
    : u.pathname.endsWith("/twin/builder") ? "Sample builder" : file;
  openTab(p, u.pathname.startsWith("/notebooks/") ? "notebook" : "page", name);
});


// ------------------------------------------------------------------ the teacher's classes (classes.py, /twin/classes)
// Prepare a class (its pages, anonymous or named, the power of the source), open it (web_class.py on this computer:
// the students get one link, also as a QR code), follow it live (where each student is, read every 5 s).
var Classes = (() => {
  let data = { classes: [], offer: [], open: null }, selected = null, timer = null, liveRows = [];
  const esc = (x) => String(x == null ? "" : x).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ago = (iso) => {
    if (!iso) return "";
    const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    return m < 1 ? "now" : m < 60 ? `${m} min ago` : `${Math.floor(m / 60)} h ${m % 60} min ago`;
  };
  async function api(method, path, body) {
    const r = await T.api(method, path, body);
    if (r && r.error) throw new Error(r.error);
    return r;
  }
  async function load() {
    try { data = await api("GET", "/twin/classes"); } catch (err) { toast("Classes: " + (err.message || err)); return; }
    if (!selected && data.classes.length) selected = (data.open && data.open.code) || data.classes[0].code;
    renderList(); renderDetail(); poll();
  }
  function renderList() {
    const box = $("#cls-list"); box.innerHTML = "";
    if (!data.classes.length) box.innerHTML = '<p class="hint">No class yet.</p>';
    for (const c of data.classes) {
      const b = document.createElement("button");
      b.className = "cls-item" + (c.code === selected ? " on" : "");
      const isOpen = data.open && data.open.code === c.code;
      b.innerHTML = `<b>${isOpen ? '<i class="live-dot"></i>' : ""}${esc(c.title)}</b>` +
        `<span>${esc(c.created.slice(0, 10))} · ${c.pages.length} page(s) · ${c.identity === "named" ? "named" : "anonymous"}${isOpen ? " · open" : ""}</span>`;
      b.onclick = () => { selected = c.code; liveRows = []; renderList(); renderDetail(); poll(); };
      box.appendChild(b);
    }
  }
  function qr(link) {
    try { const q = qrcode(0, "M"); q.addData(link); q.make(); return q.createDataURL(6, 2); } catch (err) { return ""; }
  }
  function renderDetail() {
    const box = $("#cls-detail");
    const c = data.classes.find((x) => x.code === selected);
    if (!c) { box.innerHTML = '<p class="hint">Choose a class, or make a new one.</p>'; return; }
    const byId = Object.fromEntries(data.offer.map((p) => [p.id, p]));
    const open = data.open && data.open.code === c.code ? data.open : null;
    const power = c.settings && c.settings.power_mw ? `${c.settings.power_mw} MW (fixed)` : "free";
    let openHtml;
    if (!open) {
      openHtml = `<div class="cls-acts"><button class="primary" id="cls-open">Open the class</button>
        <label><input type="checkbox" id="cls-tunnel" checked> through the tunnel (students outside this network)</label></div>
        <p class="hint">Opening starts the pages on this computer: the link works after a few seconds (up to half a minute through the tunnel); the beams are prepared meanwhile.
        ${data.open ? `It closes the class open now (<b>${esc(data.open.title)}</b>).` : ""}</p>`;
    } else if (!open.link) {
      openHtml = `<p>Starting… the link appears here in a few seconds.</p><div class="cls-acts"><button class="btn" id="cls-close">Close the class</button></div>`;
    } else {
      openHtml = `<div class="cls-open"><div class="qr"><img alt="QR code of the link" src="${qr(open.link)}"></div>
        <div style="flex:1;min-width:260px;display:flex;flex-direction:column;gap:10px">
          <b>Link for the students</b><div class="cls-link">${esc(open.link)}</div>
          <div class="cls-acts"><button class="btn" id="cls-copy">Copy the link</button>
            <button class="btn" id="cls-try">Open it here (as a student)</button>
            <button class="btn danger" id="cls-close">Close the class</button></div>
          <p class="hint">Open since ${esc(open.started.slice(11, 16))}. ${open.tunnel ? "The tunnel's address changes at each opening." : "Local only: this computer and its network."}
          Keep this computer on and awake.</p></div></div>`;
    }
    box.innerHTML = `<h1>${esc(c.title)}</h1>
      <div class="cls-meta"><span class="chip ${c.identity === "named" ? "named" : ""}">${c.identity === "named" ? "Named students" : "Anonymous students"}</span>
        <span class="chip">Power of the source: ${esc(power)}</span><span class="chip">Code ${esc(c.code)}</span></div>
      <div class="cls-card"><h3>${open ? "Open now" : "Closed"}</h3>${openHtml}</div>
      <div class="cls-card"><h3>Pages of the class</h3><ol>${c.pages.map((id) => {
        const p = byId[id];
        return p ? `<li>${esc(p.title)} <span>· ${esc(p.level_name)} · ${esc(p.instrument.toUpperCase())}</span></li>`
                 : `<li>${esc(id)} <span>(no longer offered)</span></li>`;
      }).join("")}</ol></div>
      <div class="cls-card"><h3>Live</h3><div id="cls-live"><p class="hint">Reading…</p></div></div>
      <div class="cls-acts"><button class="btn danger" id="cls-delete">Delete this class</button>
        <span class="hint">Deleting removes the class only: the work of its students stays on this computer.</span></div>`;
    const on = (id, f) => { const e = document.getElementById(id); if (e) e.onclick = f; };
    on("cls-open", async () => {
      try { data.open = await api("POST", "/twin/classes/open", { code: c.code, tunnel: $("#cls-tunnel").checked }); }
      catch (err) { toast("The class did not open: " + (err.message || err)); return; }
      renderList(); renderDetail(); poll();
    });
    on("cls-close", async () => {
      if (!confirm("Close the class? The students can no longer open its pages (their work is kept).")) return;
      await api("POST", "/twin/classes/close", {}); data.open = null; renderList(); renderDetail();
    });
    on("cls-copy", () => { navigator.clipboard.writeText(open.link); toast("Link copied."); });
    on("cls-try", () => T.openExternal(open.link));
    on("cls-delete", async () => {
      if (!confirm(`Delete the class "${c.title}"? The work of its students stays on this computer.`)) return;
      try { await api("DELETE", "/twin/classes?code=" + c.code); } catch (err) { toast(err.message || err); return; }
      selected = null; load();
    });
    renderLive();
  }
  function renderLive() {
    const box = document.getElementById("cls-live");
    if (!box) return;
    const rows = liveRows;
    if (!rows.length) { box.innerHTML = '<p class="hint">No student yet. Their progress appears here as they work (every 5 s).</p>'; return; }
    const students = new Set(rows.map((r) => r.student));
    const active = new Set(rows.filter((r) => r.idle_min != null && r.idle_min < 5).map((r) => r.student));
    const done = rows.filter((r) => r.submitted).length;
    const stuckCount = {};
    for (const r of rows) for (const q of r.stuck) stuckCount[q] = (stuckCount[q] || 0) + 1;
    const worst = Object.entries(stuckCount).sort((a, b) => b[1] - a[1])[0];
    box.innerHTML = `<div class="cls-summary">
        <div><b>${students.size}</b><span>students</span></div>
        <div><b>${active.size}</b><span>active (last 5 min)</span></div>
        <div><b>${done}</b><span>submitted</span></div>
        <div><b>${worst ? esc(worst[0]) : "–"}</b><span>${worst ? `most stuck: ${worst[1]} student(s)` : "nobody stuck"}</span></div></div>
      <table class="live"><thead><tr><th>Student</th><th>Page</th><th>Answered</th><th>At</th><th>Right</th><th>1st try</th><th>Stuck on</th>
        <th>Measurements</th><th>Last activity</th><th></th></tr></thead><tbody>${rows.map((r) => {
          const pct = r.questions ? Math.round(100 * r.answered / r.questions) : 0;
          const cls = (r.idle_min != null && r.idle_min > 10 ? "idle " : "") + (r.stuck.length ? "stuck" : "");
          return `<tr class="${cls}"><td>${esc(r.name || "anonymous " + r.student.slice(5, 9))}</td><td>${esc(r.title)}</td>
            <td><span class="meter"><i style="width:${pct}%"></i></span>${r.answered}/${r.questions || "?"}</td>
            <td>${esc(r.last_question || "–")}</td><td>${r.right}</td>
            <td>${r.first_try}</td><td class="tag-stuck">${esc(r.stuck.join(", "))}</td><td>${r.measurements}</td>
            <td>${esc(ago(r.last_activity))}</td><td>${r.submitted ? '<span class="tag-ok">✓ submitted</span>' : ""}</td></tr>`;
        }).join("")}</tbody></table>`;
  }
  async function poll() {
    if (!selected) return;
    try {
      const r = await api("GET", "/twin/classes/live?code=" + selected);
      liveRows = r.rows || [];
      const was = data.open && data.open.link;
      data.open = r.open;
      if ((data.open && data.open.link) !== was) { renderList(); renderDetail(); } else renderLive();
    } catch (err) { /* the next poll tries again */ }
  }
  // the form of a new class: the pages offered, grouped by instrument
  $("#cls-new").onclick = () => {
    const box = $("#nc-pages"); box.innerHTML = "";
    let instr = "";
    for (const p of data.offer) {
      if (p.instrument !== instr) { instr = p.instrument; box.insertAdjacentHTML("beforeend", `<h4>${esc(instr.toUpperCase())}</h4>`); }
      box.insertAdjacentHTML("beforeend", `<label><input type="checkbox" value="${esc(p.id)}"> <div>${esc(p.title)}
        <span>· ${esc(p.level_name)}${p.duration ? " · " + esc(p.duration) : ""}</span></div></label>`);
    }
    $("#nc-title").value = ""; $("#nc-power").value = ""; $("#nc-error").textContent = "";
    document.querySelector('input[name="nc-id"][value="anonymous"]').checked = true;
    $("#newclass").showModal();
  };
  $("#nc-cancel").onclick = () => $("#newclass").close();
  $("#nc-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const pages = [...document.querySelectorAll("#nc-pages input:checked")].map((i) => i.value);
    if (!pages.length) { $("#nc-error").textContent = "Choose at least one page."; return; }
    try {
      const c = await api("POST", "/twin/classes", { title: $("#nc-title").value, pages,
        identity: document.querySelector('input[name="nc-id"]:checked').value, power_mw: $("#nc-power").value || null });
      selected = c.code; $("#newclass").close(); toast("Class created. Open it when the students are ready."); load();
    } catch (err) { $("#nc-error").textContent = err.message || String(err); }
  };
  return {
    show() { load(); clearInterval(timer); timer = setInterval(poll, 5000); },
    hide() { clearInterval(timer); timer = null; },
  };
})();
