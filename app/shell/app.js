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

// The opening screen (#splash): the steps of the start of the instruments (app/backend.js), the target whose beamlines
// light up, a fact about ESS; it fades out when the instruments are ready (or the student skips it after an error)
const FACTS = [
  "ESS sends 14 pulses of protons per second onto its tungsten target: each pulse makes the neutrons of all the instruments at once.",
  "A neutron that reaches ODIN\u2019s camera has flown about 60 m from the target; its time of flight tells its wavelength.",
  "Neutrons go through centimeters of steel but are stopped by a few millimeters of water: they see what X-rays miss.",
  "The target wheel of ESS turns one sector of 36 for each pulse, so that the heat of the protons is shared out.",
];
const splash = { t0: Date.now(), gone: false, fact: 0 };
if (T.titlebar) T.titlebar("splash");
function splashFact() { $("#sp-fact").textContent = FACTS[splash.fact++ % FACTS.length]; }
splashFact();
const factTimer = setInterval(() => { if (splash.gone) clearInterval(factTimer); else splashFact(); }, 7000);
setTimeout(() => { if (!splash.gone) $("#sp-skip").classList.remove("hidden"); }, 25000);
function hideSplash() {
  if (splash.gone) return;
  splash.gone = true;
  if (T.titlebar && $("#app").classList.contains("hidden")) T.titlebar("light");
  $("#splash").classList.add("out");
  setTimeout(() => $("#splash").classList.add("hidden"), 500);
}
$("#sp-skip").onclick = hideSplash;
function splashStatus(s) {
  if (splash.gone) return;
  const f = s.fraction || 0;
  const step = f >= 1 ? 3 : f >= 0.7 ? 2 : f >= 0.2 ? 1 : 0;
  const sp = $("#splash");
  sp.dataset.step = step;
  sp.classList.toggle("err", !!s.error);
  sp.querySelectorAll(".sp-steps li").forEach((li) => {
    const k = +li.dataset.step;                   // 0 engine, 1 instruments, 2 ready
    const done = k === 0 ? step >= 1 : k === 1 ? step >= 3 : step >= 3;
    const now = !s.error && !done && (k === 0 ? step === 0 : k === 1 ? step === 1 || step === 2 : false);
    li.classList.toggle("done", done); li.classList.toggle("now", now);
  });
  $("#sp-beam").textContent = step >= 1 ? "beam on" : "waiting";
  $("#sp-text").textContent = s.text || "";
  $("#sp-pct").textContent = s.error ? "" : Math.round(f * 100) + " %";
  $("#sp-bar").style.width = (s.error ? 100 : Math.round(f * 100)) + "%";
  $("#sp-link").classList.toggle("hidden", !s.url);
  $("#sp-link").onclick = (e) => { e.preventDefault(); T.openExternal(s.url); };
  if (s.error) $("#sp-skip").classList.remove("hidden");
  if (step >= 3) {
    $("#sp-title").textContent = "The beam is on. Welcome!";
    setTimeout(hideSplash, Math.max(900, 1600 - (Date.now() - splash.t0)));
  }
}

function showStatus(s) {
  splashStatus(s);
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
  $("#menu-name").textContent = user.name;
  $("#menu-email").textContent = user.email;
  applyTheme(pref("theme"));
  hideSplash();
  teacherMenu();
  renderMenu();
  activate("cat");
  loadCatalogue();
  if (Source) Source.load();
}

// ------------------------------------------------------------------ the beam status of the source (source_power.py)
// A chip of the top bar ("Beam 2 MW") opens the beam status screen, as the screens in the halls of ESS: the power and
// what follows from it (current, protons per pulse, pulses), for every user. The power can be changed there outside a
// class; while a class is open on this computer, its power (always fixed by the teacher) is shown, locked.
var Source = (() => {
  const HZ = 14, Q2 = 2e6 / 2e9 / 14 * 1e6, PULSE_MS = 2.857;           // twin: 2 GeV protons, 71.4 µC per pulse at 2 MW (odin_nexus.py)
  let st = null, timer = null;
  const esc = (x) => String(x == null ? "" : x).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function pulseSvg(q) {            // two periods of the time structure: 2.86 ms pulses every 71.4 ms (to scale)
    const W = 600, x0 = 20, per = 260, w = Math.max(per * PULSE_MS / (1000 / HZ), 3), h = 14 + 34 * q / (Q2 * 2.5);
    let s = `<line x1="${x0}" y1="52" x2="${W - 10}" y2="52" stroke="#2C3644"/>`;
    for (let k = 0; k < 3; k++) {
      const x = x0 + k * per;
      if (x + w > W - 10) break;
      s += `<rect x="${x}" y="${52 - h}" width="${w}" height="${h}" fill="#4ADE80"/>`;
    }
    s += `<text x="${x0 + per / 2}" y="66" fill="#97A2B3" font-size="11" font-family="IBM Plex Mono, monospace" text-anchor="middle">71.4 ms between pulses (14 Hz)</text>`;
    s += `<text x="${x0 + w + 6}" y="${52 - h + 10}" fill="#97A2B3" font-size="11" font-family="IBM Plex Mono, monospace">pulse of 2.86 ms, ${q.toFixed(0)} µC</text>`;
    return s;
  }
  function tick() {
    const now = new Date(), midnight = new Date(now); midnight.setHours(0, 0, 0, 0);
    $("#beam-pulses").textContent = Math.floor((now - midnight) / 1000 * HZ).toLocaleString("en-US");
    $("#beam-clock").textContent = now.toLocaleTimeString("en-GB");
  }
  function render() {
    if (!st) return;
    const p = st.power_mw, q = Q2 * p / 2;
    $("#src-txt").textContent = `Beam ${p} MW`;
    $("#beam-power").textContent = p.toFixed(1);
    $("#beam-current").textContent = (q * HZ / 1000).toFixed(2);
    $("#beam-charge").textContent = `${q.toFixed(1)} µC`;
    $("#beam-peak").textContent = `${(q / PULSE_MS).toFixed(1)} mA`;
    $("#beam-pulse").innerHTML = pulseSvg(q);
    $("#beam-opts").innerHTML = st.choices.map(([label, v]) =>
      `<label class="${v === p ? "on" : ""}"><input type="radio" name="beam-p" value="${v}"${v === p ? " checked" : ""}${st.fixed_by ? " disabled" : ""}> <span>${esc(label)}</span></label>`).join("");
    $("#beam-note").textContent = st.fixed_by
      ? `Fixed by the class "${st.fixed_by}", open on this computer: it can be changed again when the class is closed.`
      : "Applies to the next measurements of every page and of NICOS on this computer; the open pages show it within a few seconds.";
    for (const r of document.querySelectorAll('input[name="beam-p"]')) r.onchange = () => set(Number(r.value));
  }
  async function load() {
    try { st = await T.api("GET", "/twin/source_power"); render(); } catch (err) { /* older server */ }
    if (typeof renderBeamRow === "function" && catalogue) { renderBeamRow(); const hb = $("#hall-beam"); if (hb) hb.textContent = beamText(); }
  }
  function open() { load(); tick(); clearInterval(timer); timer = setInterval(tick, 250); $("#beam").showModal(); }
  async function set(mw) {
    try {
      const r = await T.api("POST", "/twin/source_power", { power_mw: mw });
      if (r && r.error) throw new Error(r.error);
      toast(`Beam power: ${mw} MW for the next measurements.`);
    } catch (err) { toast(err.message || String(err)); }
    load();
  }
  $("#src").onclick = open;
  $("#beam-close").onclick = () => $("#beam").close();
  $("#beam").addEventListener("close", () => { clearInterval(timer); timer = null; });
  $("#beam").addEventListener("click", (e) => { if (e.target === $("#beam")) $("#beam").close(); });
  return { load, open, get: () => st };
})();
if (!$("#app").classList.contains("hidden")) Source.load();     // (app entered before this script part ran)

$("#me").onclick = (e) => { e.stopPropagation(); $("#menu").classList.toggle("hidden"); };
$("#menu").onclick = (e) => { if (!e.target.closest("#teach, #handin, #signout")) e.stopPropagation(); };
document.addEventListener("click", () => $("#menu").classList.add("hidden"));
// the teacher view: entered with the teacher code (menu of the account), left from the same menu
$("#teach").onclick = async () => {
  if (user.teacher) {
    const r = await T.teacher("", false);
    if (r.user) { user = r.user; if (pref("level") === "all") pref("level", "bsc"); }
    teacherMenu(); renderMenu(); renderCatalogue(); toast("You see the catalogue as a student again.");
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
  teacherMenu(); renderMenu(); renderCatalogue();
  toast("Teacher view: every exercise at every level. Choose another grade in this menu to see the catalogue as a student does.", 8000);
};
// the expected durations: for the teacher only (class of 2026-11-23: a duration on the page puts the students under
// pressure, and they rarely match; the teacher needs them to plan)
function durOf(m, fallback = "") { return user && user.teacher ? (m.duration || fallback) : ""; }
function durSpan(m) { const d = durOf(m); return d ? `<span><i>Duration</i>${esc(d)}</span>` : ""; }
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
  applyTheme("light");
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
    $("#requests").innerHTML = `<p class="error" style="padding:16px">The catalogue could not be read: ${esc(e.message)}</p>`;
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

// The level of the student = their grade in the team of the story (STORY.md), chosen in the menu of the account and kept
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

// ---- the menu of the account: the grade (the only place it is chosen; MSc: notebooks with or without code), light or dark
function applyTheme(th) {
  document.documentElement.dataset.theme = th === "dark" ? "dark" : "light";
  if (T.titlebar && !$("#app").classList.contains("hidden")) T.titlebar(th === "dark" ? "night" : "dark");
}
function renderMenu() {
  const lvl = currentLevel();
  const keys = ["bsc", "msc", "beamtime"].concat(user && user.teacher ? ["all"] : []);
  $("#menu-grades").innerHTML = keys.map((k) => `<button type="button" data-level="${k}" class="${k === lvl ? "on" : ""}"
    title="${esc(ROLES[k].text)}">${esc(ROLES[k].grade)}</button>`).join("");
  const view = pref("mscview") === "clean" ? "clean" : "code";
  $("#menu-mscview").classList.toggle("hidden", lvl !== "msc");
  $("#menu-mscview").innerHTML = [["code", "Notebooks with code"], ["clean", "Without code"]].map(([v, l]) =>
    `<button type="button" data-view="${v}" class="${v === view ? "on" : ""}">${l}</button>`).join("");
  const th = pref("theme") === "dark" ? "dark" : "light";
  $("#menu-theme").innerHTML = [["light", "Light", "#ECEEE8"], ["dark", "Dark", "#11161D"]].map(([v, l, c]) =>
    `<button type="button" data-theme="${v}" class="${v === th ? "on" : ""}"><i style="background:${c}"></i>${l}</button>`).join("");
  $("#menu-grades").querySelectorAll("button").forEach((b) => b.onclick = () => { pref("level", b.dataset.level); renderMenu(); renderCatalogue(); });
  $("#menu-mscview").querySelectorAll("button").forEach((b) => b.onclick = () => { pref("mscview", b.dataset.view); renderMenu(); renderCatalogue(); });
  $("#menu-theme").querySelectorAll("button").forEach((b) => b.onclick = () => { pref("theme", b.dataset.theme); applyTheme(b.dataset.theme); renderMenu(); });
  $("#me-name").textContent = user ? user.name + (lvl ? " · " + ROLES[lvl].grade : "") : "";
}

// ---- the world of the story (STORY.md): the clients, the scientists of the instruments, the hall
const TEAM_ICON = {
  energy: "M12 12v9 M12 12 7 4.5 M12 12l8.5 1.5 M12 12 4.5 16 M10 21h4",
  planets: "M12 5a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M3 14c3 2 15 0 18-4",
  instrument: "M14.5 6.5a3.5 3.5 0 0 0-4.6 4.4L4 16.8 7.2 20l5.9-5.9a3.5 3.5 0 0 0 4.4-4.6l-2.2 2.2-2.4-.6-.6-2.4z",
};
const vig = (t, small) => `<span class="vig ${small ? "s " : ""}${t}-bg"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${TEAM_ICON[t] || ""}"/></svg></span>`;
const TEAMS = {
  energy: { kind: "Energy consortium", short: "Wind, hydrogen, batteries and recycling, on an island in the Kattegat.",
    life: "Fyrø is an artificial island in the Kattegat. Around it turn the turbines of an offshore wind farm; on the island, part of the power becomes hydrogen, part is stored in batteries, and the old blades and towers are taken apart for recycling. Four departments run it, Structures, Hydrogen plant, Storage and Circularity, and each has a problem it cannot see into: steel that must last decades at sea, electrodes that age inside a closed cell, resins full of nanoparticles.",
    help: "Neutrons cross centimeters of steel and see light elements such as lithium and hydrogen. ODIN maps the strain inside a loaded steel part and follows the lithium inside a working battery; LoKI measures the nanoparticles of the blade resin." },
  planets: { kind: "Planetary scientists", short: "Meteorites that tell about the water and the magnetic field of early Mars.",
    life: "A small group of planetary scientists and paleomagnetists who keep a collection of Martian meteorites. They want to know what early Mars was like: was there water, where did it go, and did the planet have a magnetic field? Their pieces are rare and precious: they cannot be cut, ground or dissolved to find out.",
    help: "Neutrons see hydrogen, so water, through a rock without harming it, and a tomography shows where it is held inside. Polarized neutrons see the magnetic field inside a sample." },
  instrument: { kind: "Inside ESS", short: "Maja, Tomas and the workshop: the instruments themselves.",
    life: "Maja Holm runs ODIN and Tomas Berg runs LoKI: they are instrument scientists, and your mentors. With them works the workshop, which builds sample holders, load frames and coils. Before each user arrives the instruments must be ready, tested and understood.",
    help: "Their requests are the everyday work of an instrument scientist: check a new coil before it goes on ODIN, find a fault in the data before the next user comes." },
};
const PREFIX = { energy: "E", planets: "M", instrument: "I" };
const SCIENTIST = {
  odin: { name: "Maja Holm", initials: "MH", role: "instrument scientist, ODIN" },
  loki: { name: "Tomas Berg", initials: "TB", role: "instrument scientist, LoKI" },
};
const PARTS = {
  odin: [["source", 0], ["choppers", 24], ["pinhole", 56], ["sample", 82], ["camera", 100]],
  loki: [["source", 0], ["choppers", 20], ["collimation", 50], ["sample", 76], ["detectors", 100]],
};
// the hall (schematic, % of its box): the target, the instruments at the end of their beamline, other beamlines in grey
const TARGET = [50, 56];
const HALL = { odin: [20, 18], loki: [83, 36], dream: [24, 90], bifrost: [80, 92] };
const GREY = [[50, 98], [97, 72], [3, 74], [60, 3]];
const Q2 = 2e6 / 2e9 / 14 * 1e6;               // µC per pulse at 2 MW (2 GeV protons, 14 Hz)
function beamPower() { const st = Source.get(); return st ? st.power_mw : 5; }
function beamText() { return `${beamPower()} MW · 14 Hz`; }
function pulsesToday() {
  const now = new Date(), midnight = new Date(now); midnight.setHours(0, 0, 0, 0);
  return Math.floor((now - midnight) / 1000 * 14).toLocaleString("en-US");
}

function chapterProgress(s, m) {
  return (s.variant !== undefined && m.variants ? (m.variants[s.variant] || {}).progress : m.progress) ||
         { status: "new", text: "Not started", pct: 0 };
}
const ICON_PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg>';

// the requests of one instrument at one level: one per exercise, or one per sample when its samples belong to two
// threads (exercise 7); numbered along their thread; the next one is marked
function requestCards(ex, lvl) {
  const cards = [];
  for (const e of ex) {
    const m = (e.modes || {})[lvl];
    let st = Array.isArray(e.story) ? e.story : e.story ? [e.story] : [];
    if (!(m && m.variants)) st = st.filter((x, n) => x.variant === undefined || n === 0)
      .map((x) => x.variant === undefined ? x : { thread: x.thread, client: x.client });
    if (!st.length) st = [{ thread: "instrument", client: "" }];
    for (const s of st) {
      const key = e.dir ? e.dir + (s.variant !== undefined ? "#" + s.variant : "") : "planned:" + e.title;
      const live = !!m && e.status !== "planned";
      cards.push({ e, s, m, key, live, p: live ? chapterProgress(s, m) : null });
    }
  }
  for (const t of Object.keys(PREFIX)) cards.filter((x) => (x.s.thread || "instrument") === t).forEach((x, i) => { x.num = i + 1; });
  const playable = cards.filter((x) => x.live);
  const open = (x) => !(x.p.submitted || x.p.status === "done");
  const last = playable.find((x) => x.key === pref(`last:${instr}:${lvl}`));
  const next = (last && open(last) ? last : null) || playable.find((x) => x.p.status === "started") ||
               playable.find((x) => x.p.status === "new");
  if (next) next.next = true;
  return cards;
}

let cards = [];          // the requests of the table now shown
function renderCatalogue() {
  if (!catalogue) return;
  const c = catalogue;
  const lvl = currentLevel();
  const count = (k) => c.exercises.filter((e) => e.instrument === k && e.status !== "planned" && e.kind !== "introduction").length;
  if (!count(instr)) instr = Object.keys(c.instruments).find((k) => count(k)) || "odin";
  const I = c.instruments[instr];
  const ex = c.exercises.filter((e) => e.instrument === instr).sort(byPlace);
  const intro = ex.find((e) => e.kind === "introduction");
  const rest = ex.filter((e) => e.kind !== "introduction");
  cards = lvl && lvl !== "all" ? requestCards(rest, lvl) : [];
  renderHall(count, lvl);
  renderBeamRow();
  renderTeams();
  $("#inst-head").innerHTML = `<h1>${esc(I.name)}</h1><span>${esc(I.text)}</span>`;
  renderMentor(intro, lvl);
  $("#intro").innerHTML = intro ? introBar(intro) : "";
  const live = cards.filter((x) => x.live);
  $("#req-title").textContent = lvl === "all" ? `Every exercise on ${I.name}, at every level` : `Requests for ${I.name}`;
  $("#req-count").textContent = lvl && lvl !== "all" ? `${live.filter((x) => x.p.submitted || x.p.status === "done").length} / ${live.length} answered` : "";
  if (!lvl) gradePicker();
  else if (lvl === "all") {
    $("#requests").innerHTML = `<div class="r-scroll" id="r-scroll"></div>`;
    renderAll(rest);
    $("#r-scroll").querySelectorAll("[data-act]").forEach((b) => b.onclick = () => {
      const pick = b.closest(".level, .ex") && b.closest(".level, .ex").querySelector(".variant-pick");
      act(pick ? { ...b.dataset, variant: pick.value } : b.dataset);
    });
  } else renderTable(lvl);
  if ($("#free")) renderFree(lvl);
  $("#intro").querySelectorAll("[data-act]").forEach((b) => b.onclick = () => act(b.dataset));
}

// the hall: the target, the beamlines; the instruments of the twin are buttons at the end of theirs
function renderHall(count, lvl) {
  const c = catalogue;
  const keys = Object.keys(c.instruments).filter((k) => HALL[k]);
  const avail = keys.filter((k) => count(k)), later = keys.filter((k) => !count(k));
  const line = (p, cls) => `<path class="${cls}" d="M${TARGET[0]} ${TARGET[1]} L${p[0]} ${p[1]}" vector-effect="non-scaling-stroke"/>`;
  const svg = `<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
    ${GREY.concat(later.map((k) => HALL[k])).map((p) => line(p, "gl")).join("")}
    ${avail.map((k) => line(HALL[k], "il")).join("")}${avail.includes(instr) ? line(HALL[instr], "fl") : ""}</svg>`;
  const progress = (k) => {
    if (!lvl || lvl === "all") return `${count(k)} requests`;
    const ex = c.exercises.filter((e) => e.instrument === k && e.kind !== "introduction");
    const saved = instr; instr = k;                      // (the next request is found per instrument)
    const live = requestCards(ex, lvl).filter((x) => x.live);
    instr = saved;
    return `${live.filter((x) => x.p.submitted || x.p.status === "done").length} of ${live.length} answered`;
  };
  $("#hall").innerHTML = `${svg}<div class="monolith"></div><div class="target"><b>TARGET</b><span id="hall-beam">${esc(beamText())}</span></div>
    ${avail.map((k) => `<button type="button" class="hut ${k === instr ? "on" : ""}" data-k="${k}" style="left:${HALL[k][0]}%;top:${HALL[k][1]}%"
      aria-pressed="${k === instr}"><b>${esc(c.instruments[k].name)}</b><span>${esc(c.instruments[k].kind.toLowerCase())}</span>
      <span>${esc(progress(k))}</span></button>`).join("")}
    ${later.map((k) => `<span class="later" style="left:${HALL[k][0]}%;top:${HALL[k][1]}%">${esc(c.instruments[k].name)} · later</span>`).join("")}
    <span class="legend">grey: the other instruments of ESS, not in the twin yet · schematic</span>`;
  $("#hall").querySelectorAll(".hut").forEach((b) => b.onclick = () => {
    instr = b.dataset.k; localStorage.setItem("instr", instr); renderCatalogue();
  });
}

// the beam status under the hall (the beam status screen when clicked)
function renderBeamRow() {
  const p = beamPower(), q = Q2 * p / 2;
  $("#beamrow").innerHTML = `<span class="on"><i></i>BEAM ON TARGET</span>
    <span class="v"><b>${p.toFixed(1)}</b><span>MW</span></span><span class="v"><b>${(q * 14 / 1000).toFixed(2)}</b><span>mA</span></span>
    <span class="v"><b>${q.toFixed(0)}</b><span>µC / pulse</span></span><span class="v"><b id="br-pulses">${pulsesToday()}</b><span>pulses today</span></span>
    <span class="clock" id="br-clock">${new Date().toLocaleTimeString("en-GB")} ›</span>`;
}
$("#beamrow").onclick = () => Source.open();
setInterval(() => {
  const a = $("#br-pulses");
  if (a && activeKey === "cat") { a.textContent = pulsesToday(); $("#br-clock").textContent = new Date().toLocaleTimeString("en-GB") + " ›"; }
}, 1000);

// the clients of the story: a card each, their story in a dialog
function renderTeams() {
  const c = catalogue;
  $("#teams").innerHTML = Object.entries(c.threads || {}).map(([k, t]) => `<button type="button" class="team" data-t="${k}">
      <span class="t-top">${vig(k)}<b>${esc(t.client)}</b></span><span class="t-what">${esc((TEAMS[k] || {}).short || t.text)}</span>
      <span class="t-go">Meet them ›</span></button>`).join("");
  $("#teams").querySelectorAll(".team").forEach((b) => b.onclick = () => openTeam(b.dataset.t));
}
function openTeam(k) {
  const c = catalogue, t = c.threads[k], T2 = TEAMS[k] || {};
  $("#team-band").className = `team-band ${k}-bg`;
  $("#team-band").innerHTML = `${vig(k)}<div><small>${esc((T2.kind || "").toUpperCase())}</small><b>${esc(t.client)}</b></div>`;
  $("#team-life").textContent = T2.life || t.text;
  $("#team-help").textContent = T2.help || "";
  const n = (i) => c.exercises.filter((e) => e.instrument === i && e.kind !== "introduction" && e.status !== "planned" &&
    (Array.isArray(e.story) ? e.story : e.story ? [e.story] : []).some((x) => x.thread === k)).length;
  $("#team-counts").innerHTML = Object.entries(c.instruments).filter(([i]) => n(i)).map(([i, I]) =>
    `<span>${n(i)} request${n(i) > 1 ? "s" : ""} on ${esc(I.name)}</span>`).join("");
  $("#team").showModal();
}

// the scientist of the instrument writes to the student: what to do now
function renderMentor(intro, lvl) {
  const S = SCIENTIST[instr];
  if (!S) { $("#mentor").innerHTML = ""; return; }
  const I = catalogue.instruments[instr];
  const ip = intro ? (((intro.modes || {}).all || {}).progress || { status: "new" }) : { status: "done" };
  const next = cards.find((x) => x.next), live = cards.filter((x) => x.live);
  let msg;
  if (ip.status === "new") msg = `Welcome on ${I.name}! Start with the introduction just below: it shows how the instrument works. Then the requests are yours.`;
  else if (!lvl) msg = "Choose your grade in the team: the requests, and the way you work on them, follow from it.";
  else if (lvl === "all") msg = `Teacher view: every exercise on ${I.name}, at every level.`;
  else if (next) msg = `${next.s.client || "A client"} is waiting for your answer: \u201c${next.e.title}\u201d ` +
    (lvl === "bsc" ? "I have set up the instrument for you." : lvl === "msc" ? "They need a method they can trust and repeat." :
     "Your proposal was accepted: the beamtime is yours.");
  else if (live.length) msg = `Every request on ${I.name} is answered at this grade. Well done!`;
  else msg = `No request on ${I.name} at this grade yet.`;
  $("#mentor").innerHTML = `<div class="av">${esc(S.initials)}<i aria-label="new message"></i></div><div class="m-txt">
    <div class="who"><b>${esc(S.name)}</b> <span>${esc(S.role)} · message</span></div><div class="bub">${esc(msg)}</div></div>`;
}

// the introduction of the instrument: a bar, its parts drawn as a line that a neutron runs along
function introBar(e) {
  const m = (e.modes || {}).all || {};
  const p = m.progress || { status: "new", text: "Not started", pct: 0 };
  const label = `${catalogue.instruments[e.instrument].name} · Introduction`;
  const d = `data-dir="${esc(e.dir)}" data-mode="all" data-label="${esc(label)}"`;
  const badge = p.status === "new" ? ["start", "START HERE ›"] : p.status === "done" ? ["cont", "OPEN AGAIN ›"] : ["cont", "CONTINUE ›"];
  const parts = (PARTS[e.instrument] || []).map(([n, x]) => `<span class="part" style="left:${x}%"></span><span class="lab" style="left:${x}%">${n}</span>`).join("");
  const again = p.status === "new" ? "" :
    `<button type="button" class="ib-badge again2" data-act="reset" ${d} data-file="${esc(m.file || "")}" data-page="${m.open === "voila" ? 1 : 0}"
       title="Your answers and the state of this introduction are put aside: you start from the beginning.">START AGAIN</button>`;
  const state = p.status === "done" ? "done ✓" : p.status === "started" ? `started · ${p.pct || 0} %` : "";
  return `<div class="ib-main"><button type="button" class="ib-open" data-act="open" ${d}>
      <span class="ib-txt"><b>Introduction${durOf(m) ? " · " + esc(durOf(m)) : ""}${state ? ` <em>${state}</em>` : ""}</b><span>how the instrument works</span></span>
      <span class="ib-line" aria-hidden="true"><span class="rail"></span>${parts}<span class="dot"></span></span></button>
      <span class="ib-acts"><button type="button" class="ib-badge ${badge[0]}" data-act="open" ${d}>${badge[1]}</button>${again}</span></div>`;
}

// no grade yet: choose it (then it is in the menu of the account)
function gradePicker() {
  $("#requests").innerHTML = `<div class="req-empty"><h3>Choose your grade in the team</h3>
    <p>The requests, and the way you work on them, follow from it. You can change it at any time in the menu of your
      account (top right): your work at each grade is kept.</p>
    <div class="grade-pick">${["bsc", "msc", "beamtime"].map((k) => `<button type="button" data-level="${k}"><b>${esc(ROLES[k].grade)}</b>
      <span>${esc(ROLES[k].text)}</span></button>`).join("")}</div></div>`;
  $("#requests").querySelectorAll("[data-level]").forEach((b) => b.onclick = () => { pref("level", b.dataset.level); renderMenu(); renderCatalogue(); });
}

// the table of the requests (REF, FROM, REQUEST, STATUS); a click opens the briefing under the row
function renderTable(lvl) {
  const c = catalogue;
  const sel = pref(`sel:${instr}:${lvl}`);
  const openKey = sel === "none" ? null : cards.some((x) => x.key === sel) ? sel : (cards.find((x) => x.next) || {}).key;
  const row = (x) => {
    const { e, s, p } = x;
    const t = s.thread || "instrument";
    const st = !x.live ? (e.status === "planned" ? "planned" : "off") : (p.submitted || p.status === "done") ? "done" : x.next ? "next" : p.status;
    const label = { planned: e.later ? "LATER" : "IN PREPARATION", off: "OTHER LEVEL", done: "ANSWERED", next: "NEXT",
                    started: `STARTED · ${p ? p.pct || 0 : 0} %` }[st] || "NEW";
    const vl = s.variant !== undefined && x.m && x.m.variants ? (x.m.variants[s.variant] || {}).label : "";
    const open = x.key === openKey;
    return `<button type="button" class="r-row${st === "done" ? " done" : ""}${st === "planned" ? " dim" : ""}${open ? " open" : ""}"
        data-key="${esc(x.key)}" aria-expanded="${open}">
      <span class="r-ref ${t}-fg">${PREFIX[t] || "X"}-${String(x.num).padStart(2, "0")}</span>
      <span class="r-from">${vig(t, true)}<span>${esc((c.threads[t] || {}).client || String(s.client || "").split(" · ")[0])}</span></span>
      <span class="r-title">${esc(e.title)}${vl ? `<small>${esc(vl)}</small>` : ""}</span>
      <span class="r-st ${st}">${label}</span></button>${open ? `<div class="r-detail" data-key="${esc(x.key)}">${detail(x, lvl)}</div>` : ""}`;
  };
  const prev = $("#r-scroll") ? $("#r-scroll").scrollTop : 0;
  $("#requests").innerHTML = `<div class="r-head"><span>REF</span><span>FROM</span><span>REQUEST</span><span>STATUS</span></div>
    <div class="r-scroll" id="r-scroll">${cards.map(row).join("") || `<div class="req-empty"><p>No request on this instrument at this grade yet.</p></div>`}
      <div id="free"></div></div>`;
  $("#r-scroll").scrollTop = prev;
  $("#requests").querySelectorAll(".r-row").forEach((b) => b.onclick = () => {
    pref(`sel:${instr}:${lvl}`, b.dataset.key === openKey ? "none" : b.dataset.key);
    renderTable(lvl);
    if ($("#free")) renderFree(lvl);
  });
  const box = $("#requests").querySelector(".r-detail");
  if (box) box.querySelectorAll("[data-act]").forEach((b) => b.onclick = () => {
    // a request opened or started again: it stays open in the table, and becomes the next one (until submitted)
    if (b.dataset.act === "open" || b.dataset.act === "reset") { pref(`sel:${instr}:${lvl}`, box.dataset.key); pref(`last:${instr}:${lvl}`, box.dataset.key); }
    act(b.dataset);
  });
}

// the briefing of one request: its mission, where the student is, the buttons
function detail(x, lvl) {
  const { e, s, m } = x;
  const mission = (m && m.mission) || s.mission || e.mission || e.question;
  if (e.status === "planned") return `<p class="b-mission">${esc(e.question)}</p>
    <div class="b-intel"><span><i>Technique</i>${esc(e.technique || "")}</span><span><i>Status</i>${e.later ? "Later" : "In preparation"}</span></div>`;
  if (!m) {          // no version at this level (a game: a guided page only)
    const other = Object.keys(e.modes || {})[0];
    const om = (e.modes || {})[other] || {};
    const label = `${catalogue.instruments[e.instrument].name} · ${short(e.title)} · ${LEVEL[other] || other}`;
    return `<p class="b-mission">${esc(mission)}</p>
      <div class="b-intel"><span><i>Format</i>${esc(om.label || "Guided page")}</span>${durSpan(om)}
        <span><i>Level</i>Only as a ${esc(LEVEL[other] || other)} page</span></div>
      <div class="b-acts"><button class="btn go" data-act="open" data-dir="${esc(e.dir)}" data-mode="${other}" data-label="${esc(label)}">${ICON_PLAY}Open</button></div>`;
  }
  const p = x.p;
  const vlabel = s.variant !== undefined && m.variants ? (m.variants[s.variant] || {}).label : "";
  const short2 = vlabel ? " · " + vlabel.split(" (")[0].replace(/^The /, "") : "";
  const label = `${catalogue.instruments[e.instrument].name} · ${short(e.title)}${short2} · ${LEVEL[lvl] || lvl}`;
  const d = `data-dir="${esc(e.dir)}" data-mode="${lvl}" data-label="${esc(label)}"` +
            (s.variant !== undefined && m.variants ? ` data-variant="${s.variant}"` : "");
  const go = p.status === "new" ? "Start" : (p.status === "done" ? "Open again" : "Continue");
  let acts;
  if (lvl === "bsc") acts = `<button class="btn go" data-act="open" ${d}>${ICON_PLAY}${go}</button>`;
  else if (lvl === "msc") {
    const view = pref("mscview") === "clean" ? "clean" : "code";
    acts = `<button class="btn go" data-act="open" data-view="${view}" ${d}>${ICON_PLAY}${go}</button>`;
  } else acts = `<button class="btn go" data-act="open" data-what="analysis" ${d}>${ICON_PLAY}Starter notebook</button>
      <button class="btn" data-act="sheet" data-dir="${esc(e.dir)}" data-k="${lvl}">Your proposal</button>`;
  const again = p.status === "new" ? "" :
    `<button class="btn" data-act="reset" ${d} data-file="${esc(lvl === "beamtime" ? m.analysis || "" : m.file || "")}"
       data-page="${m.open === "voila" ? 1 : 0}" title="Your notebook, your answers and the state of this exercise are put aside: you start from the beginning. Your measurements stay.">Start again</button>`;
  const where = p.submitted ? `Submitted on ${esc(p.submitted)}` : p.status === "new" ? "" :
    esc(String(p.text || "").replace(/^Started /, "Started on "));
  return `<p class="b-mission">${esc(mission)}</p>${durSpan(m) ? `<div class="b-intel">${durSpan(m)}</div>` : ""}
    ${where ? `<span class="b-where">${where}</span>` : ""}
    <div class="b-acts">${acts}${again}</div>`;
}

function renderAll(ex) {
  const num = (e) => e.number !== undefined ? `Exercise ${esc(e.number)} · ` : "";
  $("#r-scroll").innerHTML = ex.map((e, i) => e.status === "planned"
    ? `<article class="ex planned${e.later ? " later" : ""}"><div><span class="tech">${num(e)}${esc(e.technique)} · ${e.later ? "later" : "in preparation"}</span><h3>${esc(e.title)}</h3></div>
       ${e.sample ? `<p class="smp">${esc(e.sample)}</p>` : ""}<p class="q">${esc(e.question)}</p></article>`
    : e.kind === "introduction" ? ""
    : `<article class="ex"><div><span class="tech">${num(e)}${esc(e.technique)}</span><h3>${esc(e.title)}</h3></div>
       ${e.mission ? `<div class="mission">${ICON_TARGET}<span><b>Your mission.</b> ${esc(e.mission)}</span></div>` : ""}
       <div class="levels">${Object.entries(e.modes || {}).map(([k, m]) => level(e, k, m, i)).join("")}</div></article>`).join("") + `<div id="free"></div>`;
}

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
  return `<div class="level"><div class="row"><span class="chip ${k}">${LEVEL[k] || k}</span><span class="dur">${esc(durOf(m))}${again}</span></div>
    <span class="label">${esc(m.label)}</span><span class="what" title="${esc(m.what)}">${esc(m.what)}</span>
    <div class="prog">${variants}<div class="row"><span>${esc(p.text)}</span><b>${p.pct ? p.pct + " %" : ""}</b></div>
      <div class="track"><div class="fill ${k}" style="width:${p.pct}%"></div></div></div>
    <div class="acts">${acts}</div></div>`;
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
      // the fonts and the ink of the app (the catalogue); the theme of JupyterLab otherwise
      view.insertCSS(`@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap");
        :root, body { --jp-ui-font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
          --jp-content-font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
          --jp-code-font-family: "IBM Plex Mono", Consolas, monospace; --jp-content-font-color1: #1B1F24;
          --jp-brand-color1: #1B1F24; --jp-brand-color0: #000; --jp-brand-color2: #566057; }
        .jp-RenderedHTMLCommon h1, .jp-RenderedHTMLCommon h2, .jp-RenderedHTMLCommon h3 {
          font-family: "IBM Plex Sans Condensed", "Segoe UI", system-ui, sans-serif; font-weight: 700; }`).catch(() => {});
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
    Source.load();
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
    const power = c.settings && c.settings.power_mw ? `${c.settings.power_mw} MW` : "not fixed (older class)";
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
      <div class="cls-acts"><button class="btn" id="cls-edit">${c.n_students ? "Add pages" : "Edit this class"}</button>
        <span class="hint">${c.n_students ? `${c.n_students} student(s) already worked in it: you can add pages, not change the rest.`
                                          : "No student has opened it yet: everything can be changed."}</span></div>
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
    on("cls-edit", () => form(c));
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
  // the form of a class: new (c null) or changed (c: everything if no student opened it yet, otherwise new pages only)
  let editing = null;
  function form(c) {
    editing = c;
    const locked = !!(c && c.n_students);
    const box = $("#nc-pages"); box.innerHTML = "";
    let instr = "";
    for (const p of data.offer) {
      if (p.instrument !== instr) { instr = p.instrument; box.insertAdjacentHTML("beforeend", `<h4>${esc(instr.toUpperCase())}</h4>`); }
      const has = c && c.pages.includes(p.id);
      box.insertAdjacentHTML("beforeend", `<label><input type="checkbox" value="${esc(p.id)}"${has ? " checked" : ""}${has && locked ? " disabled" : ""}> <div>${esc(p.title)}
        <span>· ${esc(p.level_name)}${p.duration ? " · " + esc(p.duration) : ""}</span></div></label>`);
    }
    $("#nc-title").value = c ? c.title : "";
    $("#nc-power").value = c && c.settings && c.settings.power_mw ? String(c.settings.power_mw) : "5";
    document.querySelector(`input[name="nc-id"][value="${c ? c.identity : "anonymous"}"]`).checked = true;
    for (const e of [$("#nc-title"), $("#nc-power"), ...document.querySelectorAll('input[name="nc-id"]')]) e.disabled = locked;
    $("#nc-head").textContent = !c ? "New class" : locked ? "Add pages to the class" : "Edit the class";
    $("#nc-submit").textContent = !c ? "Create the class" : "Save";
    $("#nc-locked").textContent = locked ? `${c.n_students} student(s) already worked in this class: you can add pages; ` +
      "the title, the students, the power and the pages already given stay (the results refer to them)." : "";
    $("#nc-locked").classList.toggle("hidden", !locked);
    $("#nc-error").textContent = "";
    $("#newclass").showModal();
  }
  $("#cls-new").onclick = () => form(null);
  $("#nc-cancel").onclick = () => $("#newclass").close();
  $("#nc-form").onsubmit = async (ev) => {
    ev.preventDefault();
    let pages = [...document.querySelectorAll("#nc-pages input:checked")].map((i) => i.value);
    if (editing) pages = [...editing.pages.filter((id) => pages.includes(id)), ...pages.filter((id) => !editing.pages.includes(id))];
    if (!pages.length) { $("#nc-error").textContent = "Choose at least one page."; return; }
    try {
      const c = await api("POST", "/twin/classes", { code: editing ? editing.code : undefined, title: $("#nc-title").value, pages,
        identity: document.querySelector('input[name="nc-id"]:checked').value, power_mw: Number($("#nc-power").value) });
      selected = c.code; $("#newclass").close();
      toast(editing ? "Class saved." + (data.open && data.open.code === c.code ? " The students see the new pages when they reload the start page." : "")
                    : "Class created. Open it when the students are ready.");
      load();
    } catch (err) { $("#nc-error").textContent = err.message || String(err); }
  };
  return {
    show() { load(); clearInterval(timer); timer = setInterval(poll, 5000); },
    hide() { clearInterval(timer); timer = null; },
  };
})();
