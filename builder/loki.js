// The LoKI sample builder page of the app (builder/loki.html): particles in a H2O/D2O liquid, in a quartz cell.
// The server (builder_loki.py, through /twin/builder/api/... with "instrument": "loki") computes what the sample
// scatters (sample_library.loki_cross_section), checks and saves; this page edits the state and draws.

// ------------------------------------------------------------------ server
const Q = new URLSearchParams(location.search);
const TOKEN = Q.get("token") || "";
const API = "builder/api/";
const INSTR = "loki";
function cookie(n) { const m = document.cookie.match(new RegExp("(?:^|; )" + n + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
async function api(what, body = {}) {
  const h = { "Content-Type": "application/json" };
  if (TOKEN) h.Authorization = "token " + TOKEN; else h["X-XSRFToken"] = cookie("_xsrf");
  const r = await fetch(API + what, { method: "POST", headers: h, credentials: "same-origin",
    body: JSON.stringify({ instrument: INSTR, proposal: S.proposal, ...body }) });
  if (!r.ok) throw new Error(`${what}: HTTP ${r.status}`);
  const d = await r.json();
  if (d.error) throw new Error(d.error);
  return d;
}
const thumbUrl = (s) => `${API}thumb?instrument=${INSTR}&kind=${encodeURIComponent(s.kind)}&ref=${encodeURIComponent(s.ref)}`
  + `&proposal=${encodeURIComponent(S.proposal)}` + (TOKEN ? `&token=${encodeURIComponent(TOKEN)}` : "");

// ------------------------------------------------------------------ state
const S = { info: null, proposal: (Q.get("proposal") || "").trim(), state: null, start: null, step: 1, view: null, viewKey: 0, dirty: false };
const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const clone = (o) => JSON.parse(JSON.stringify(o));
const sealed = (v) => v && typeof v === "object" && "sealed" in v;
const kindSealed = (k) => ["model", "particle", "core_particle", "volume_fraction"].some((f) => sealed(k[f]))
  || Object.values(k.parameters || {}).some(sealed);
function status(msg, err = false) { const s = $("status"); s.textContent = msg || ""; s.classList.toggle("err", !!err); }
const fmt = (x, n = 3) => String(Number(Number(x).toPrecision(n)));
const sup = (n) => String(n).replace(/-/g, "⁻").replace(/\d/g, (d) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[d]);
const MAT_COLORS = { silica: "#DCD3C0", polystyrene: "#F4B183", "deuterated polystyrene": "#E07A5F", gold: "#E3B21C",
  silver: "#C3CAD2", "iron oxide (magnetite)": "#4B4B55", "protein (average)": "#8DBF7F", "lipid (tails)": "#EBCB6B", PMMA: "#A8D8DC" };
const matColor = (m) => MAT_COLORS[m] || "#CBD3DE";
const kindColor = (i) => S.info.colors[i % S.info.colors.length];
const solventSld = () => { const x = S.state.d2o; return x * S.info.sld.D2O + (1 - x) * S.info.sld.H2O; };
const model = (t) => S.info.models.find((m) => m.type === t);
const liquid = () => S.state.medium === "liquid";

// ------------------------------------------------------------------ sliders
function sliderRow(label, value, min, max, onset, o = {}) {
  const log = !!o.log, step = o.step ?? (log ? 0.001 : 0.01);
  const toR = (v) => (log ? Math.log10(v / min) / Math.log10(max / min) : (v - min) / (max - min)) * 1000;
  const fromR = (r) => { const t = r / 1000; return log ? min * Math.pow(max / min, t) : min + t * (max - min); };
  const rnd = o.round || ((v) => Number(fmt(v, 3)));
  const rng = el("input", { type: "range", min: 0, max: 1000, step: 1, value: toR(value) });
  const num = el("input", { type: "number", min, max, step: o.numStep ?? "any", value: rnd(value) });
  const extra = el("span", { class: "u" }, (o.unit || "") + (o.extra ? " " + o.extra(value) : ""));
  const set = (v, from) => {
    v = Number(v); if (!isFinite(v)) return; v = Math.min(max, Math.max(min, v)); v = rnd(v);
    if (from !== rng) rng.value = toR(v); if (from !== num) num.value = v;
    extra.textContent = (o.unit || "") + (o.extra ? " " + o.extra(v) : ""); onset(v);
  };
  rng.addEventListener("input", () => set(fromR(Number(rng.value)), rng));
  num.addEventListener("change", () => set(num.value, num));
  return el("div", { class: "slider wide" }, el("span", { class: "nm" }, label), rng, num, extra);
}
const nmText = (v) => `(${fmt(v / 10, 3)} nm)`;

// ------------------------------------------------------------------ step 1: the liquid
function renderLiquid() {
  const m = $("medium"); m.innerHTML = "";
  const opts = [["liquid", "H2O / D2O mixture", "a liquid, with or without particles"],
    ["air", "Air (nothing)", "the empty cell, or the empty beam: the reference measurements"]];
  for (const [k, t, x] of opts) {
    m.append(el("button", { class: "opt" + (S.state.medium === k ? " on" : ""), onclick: () => {
      if (S.state.medium === k) return;
      S.state.medium = k;
      if (k === "liquid" && S.state.holder.type === "none") S.state.holder = { type: "cell", gap_mm: 1.0 };
      changed(true);
    } }, el("div", { class: "t" }, t), el("div", { class: "x" }, x)));
  }
  const box = $("liquid"); box.innerHTML = "";
  $("kinds-box").classList.toggle("hidden", !liquid());
  if (!liquid()) {
    box.append(el("p", { class: "note-box" }, S.state.holder.type === "none"
      ? "Nothing on the sample position: the empty beam (step 2: no cell)."
      : "The empty cell: air between the quartz windows (step 2: the cell; choose “no cell” for the empty beam)."));
    return;
  }
  box.append(sliderRow("D2O fraction", Math.round(S.state.d2o * 100), 0, 100, (v) => { S.state.d2o = v / 100; changed(); },
    { unit: "%", round: (v) => Math.round(v), numStep: 1 }));
  box.append(sliderRow("liquid thickness", S.state.holder.gap_mm ?? 1, S.info.cell.gap_min, S.info.cell.gap_max,
    (v) => { S.state.holder.gap_mm = v; changed(); }, { unit: "mm", round: (v) => Math.round(v * 100) / 100 }));
  box.append(el("div", { class: "sldline", id: "sld-line" }));
  renderSldScale();
}
function renderSldScale() {
  const host = $("sld-line"); if (!host) return;
  const rs = solventSld(), x = S.state.d2o;
  const bg = x * S.info.solvent_inc.D2O + (1 - x) * S.info.solvent_inc.H2O;
  const W = 520, lo = -1.2, hi = 7.4, X = (v) => 20 + (v - lo) / (hi - lo) * (W - 40);
  let s = `<line x1="20" y1="44" x2="${W - 20}" y2="44" stroke="#9AA6B6"/>`;
  for (let v = -1; v <= 7; v++) s += `<line x1="${X(v)}" y1="41" x2="${X(v)}" y2="47" stroke="#9AA6B6"/><text x="${X(v)}" y="60" class="ax">${v}</text>`;
  s += `<text x="${W - 4}" y="74" style="font-size:11px;fill:var(--mute);text-anchor:end">ρ [10⁻⁶ Å⁻²]</text>`;
  s += `<text x="${X(S.info.sld.H2O)}" y="30" class="lb">H2O</text><text x="${X(S.info.sld.D2O)}" y="30" class="lb">D2O</text>`;
  const anchor = X(rs) > W - 70 ? "end" : X(rs) < 70 ? "start" : "middle";
  s += `<rect x="${X(rs) - 4}" y="36" width="8" height="16" rx="2" fill="#2F6FB0"/><text x="${X(rs) + (anchor === "end" ? 6 : anchor === "start" ? -6 : 0)}" y="14" class="lb b" style="fill:#2F6FB0;text-anchor:${anchor}">your liquid ${fmt(rs, 3)}</text>`;
  const seen = new Set();
  (S.state.kinds || []).forEach((k, i) => {
    for (const m of [k.particle, k.model === "core_shell_sphere" ? k.core_particle : null]) {
      if (!m || sealed(m) || seen.has(m)) continue; seen.add(m);
      const v = S.info.sld[m];
      s += `<circle cx="${X(v)}" cy="44" r="5.5" fill="${matColor(m)}" stroke="${kindColor(i)}" stroke-width="2"/>`
        + `<text x="${X(v)}" y="88" class="lb" fill="${kindColor(i)}">${esc(m)}</text>`;
    }
  });
  host.innerHTML = `<svg viewBox="0 0 ${W} 96">${s}</svg><div class="small">Liquid: ρ = ${fmt(rs, 3)}·10⁻⁶ Å⁻²; flat
    incoherent background ${fmt(bg, 2)} cm⁻¹ sr⁻¹ (H2O scatters ${fmt(S.info.solvent_inc.H2O / S.info.solvent_inc.D2O, 2)} times more than D2O).
    The farther a material from your liquid on this line, the brighter its particles.</div>`;
}

// ------------------------------------------------------------------ step 1: the kinds of particles
const MODEL_ICONS = {
  sphere: '<circle cx="19" cy="15" r="11" fill="#C9D3DF" stroke="#142033"/>',
  cylinder: '<rect x="4" y="10" width="30" height="10" rx="2" fill="#C9D3DF" stroke="#142033"/>',
  core_shell_sphere: '<circle cx="19" cy="15" r="12" fill="#E7EDF4" stroke="#142033"/><circle cx="19" cy="15" r="7" fill="#9AA6B6" stroke="#142033"/>',
};
function renderKinds() {
  const host = $("kinds"); host.innerHTML = "";
  const kinds = S.state.kinds || [];
  if (!kinds.length) host.append(el("p", { class: "note-box" }, "No particles: the liquid alone (the solvent, or “background”, measurement of a SANS experiment). Add a kind below."));
  kinds.forEach((k, i) => host.append(kindCard(k, i)));
  const add = $("add-kinds"); add.innerHTML = "";
  for (const m of S.info.models) add.append(el("button", { onclick: () => {
    S.state.kinds.push({ model: m.type, particle: "silica", parameters: Object.fromEntries(m.params.map((p) => [p.key, p.default])),
      volume_fraction: 0.005, core_particle: null });
    changed(true);
  } }, `+ ${m.label}`));
  phiTotal();
}
function kindCard(k, i) {
  const m = sealed(k.model) ? null : model(k.model);
  const head = el("div", { class: "khead" },
    el("span", { class: "sw", style: `background:${kindColor(i)}` }),
    el("b", {}, `Kind ${i + 1}: ${m ? m.label : "hidden shape"}`), el("span", { class: "grow" }),
    el("button", { class: "danger small-btn", onclick: () => { if (confirm(`Remove kind ${i + 1}?`)) { S.state.kinds.splice(i, 1); changed(true); } } }, "Remove"));
  const card = el("div", { class: "kind", style: `border-left:4px solid ${kindColor(i)}` }, head);
  // shape
  const icons = el("div", { class: "shapes" });
  if (!m) icons.append(lockRow("shape", "model", k, () => { k.model = "sphere"; k.parameters = { radius: 50 }; }));
  else for (const mm of S.info.models) {
    icons.append(el("button", { class: "shape" + (mm.type === k.model ? " on" : ""), onclick: () => {
      if (mm.type === k.model) return;
      const r = k.parameters.radius;
      k.model = mm.type; k.parameters = Object.fromEntries(mm.params.map((p) => [p.key, p.key === "radius" && !sealed(r) && r ? r : p.default]));
      if (mm.type !== "core_shell_sphere") k.core_particle = null;
      changed(true);
    } }, el("span", { html: `<svg viewBox="0 0 38 30">${MODEL_ICONS[mm.type]}</svg>` }), mm.label));
  }
  card.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Shape"), icons));
  // material(s)
  const mats = el("div", { class: "field" }, el("div", { class: "lbl" }, k.model === "core_shell_sphere" ? "Materials" : "Material"));
  mats.append(matCard(k, "particle", k.model === "core_shell_sphere" ? "shell" : ""));
  if (k.model === "core_shell_sphere") mats.append(matCard(k, "core_particle", "core"));
  card.append(mats);
  // sizes
  const dims = el("div", { class: "field" }, el("div", { class: "lbl" }, "Size"));
  if (m) for (const p of m.params) {
    const v = k.parameters[p.key];
    if (sealed(v)) dims.append(lockRow(p.label, p.key, k.parameters, () => { k.parameters[p.key] = p.default; }));
    else dims.append(sliderRow(p.label, v, p.min, p.max, (x) => { k.parameters[p.key] = x; changed(); }, { log: true, unit: "Å", extra: nmText }));
  }
  card.append(dims);
  // amount
  const amt = el("div", { class: "field" }, el("div", { class: "lbl" }, "Amount"));
  if (sealed(k.volume_fraction)) amt.append(lockRow("volume fraction", "volume_fraction", k, () => { k.volume_fraction = 0.005; }));
  else amt.append(sliderRow("volume fraction", k.volume_fraction * 100, 0.01, S.info.max_fraction * 100,
    (x) => { k.volume_fraction = x / 100; changed(); }, { log: true, unit: "%" }));
  card.append(amt);
  return card;
}
function lockRow(label, key, obj, replace) {
  return el("div", { class: "lock" }, el("span", {}, `🔒 ${label}: hidden (what the exercise asks you to measure)`),
    el("button", { class: "small-btn", onclick: () => { if (confirm("Replace the hidden value by one of your own? The hidden one is then gone from this sample.")) { replace(); changed(true); } } }, "Use my own value"));
}
function matCard(k, field, role) {
  const m = k[field];
  if (sealed(m)) return lockRow(role ? `${role} material` : "material", field, k, () => { k[field] = "silica"; });
  const name = m || k.particle;
  const same = field === "core_particle" && !m;
  const rho = S.info.sld[name], d = rho - solventSld();
  return el("div", { class: "matcard", "data-field": field },
    el("span", { class: "sw", style: `background:${matColor(name)}` }),
    el("div", { class: "grow" }, el("div", { class: "t" }, (role ? `${role}: ` : "") + (same ? `as the shell (${name})` : name)),
      el("div", { class: "s" }, `ρ = ${fmt(rho, 3)}·10⁻⁶ Å⁻² · contrast Δρ = ${d >= 0 ? "+" : ""}${fmt(d, 2)} against your liquid`),
      contrastBar(d)),
    el("button", { onclick: () => openPicker(role ? `${role[0].toUpperCase()}${role.slice(1)} material` : "Material of the particles",
      (x) => { k[field] = x; changed(true); }) }, "Change"));
}
function contrastBar(d) {
  const w = Math.min(100, (d * d) / 49 * 100);   // Δρ² against 7² (the most the H2O/D2O line allows)
  const c = Math.abs(d) < 0.3 ? "var(--red)" : Math.abs(d) < 1 ? "#E9A23B" : "var(--green)";
  return el("div", { class: "cbar", title: "contrast Δρ²: what sets the brightness" }, el("span", { style: `width:${Math.max(1.5, w)}%;background:${c}` }));
}

// ------------------------------------------------------------------ material picker
let pickCb = null;
function openPicker(title, cb) { pickCb = cb; $("picker-title").textContent = title; $("picker").classList.remove("hidden"); renderPicker(); }
function closePicker() { $("picker").classList.add("hidden"); pickCb = null; }
function renderPicker() {
  const list = $("mat-list"); list.innerHTML = "";
  const rs = solventSld();
  const cards = el("div", { class: "mcards" });
  for (const it of S.info.materials) {
    const d = it.sld - rs;
    cards.append(el("button", { class: "mcard", onclick: () => { const cb = pickCb; closePicker(); if (cb) cb(it.label); } },
      el("span", { class: "sw", style: `background:${matColor(it.label)}` }),
      el("span", { class: "grow" }, el("div", { class: "t" }, it.label),
        el("div", { class: "s" }, `ρ = ${fmt(it.sld, 3)} · Δρ = ${d >= 0 ? "+" : ""}${fmt(d, 2)} (10⁻⁶ Å⁻²)`), contrastBar(d))));
  }
  list.append(el("p", { class: "lead" }, `Scattering length densities ρ (usual values, NIST SLD calculator). Your liquid: ρ = ${fmt(rs, 3)}·10⁻⁶ Å⁻² (${Math.round(S.state.d2o * 100)} % D2O). The bar: the contrast Δρ², which sets how bright the particles are.`), cards);
}

// ------------------------------------------------------------------ gallery
function renderGallery() {
  const q = $("gallery-search").value.trim().toLowerCase();
  const g = $("gallery"); g.innerHTML = "";
  const items = [...S.info.starts];
  const draft = loadDraft();
  if (draft) items.unshift({ kind: "draft", ref: "", title: "Your unsaved draft", what: draft.when });
  for (const s of items) {
    if (q && !(`${s.title} ${s.what}`).toLowerCase().includes(q)) continue;
    const pic = s.kind === "draft" ? el("div", { class: "ph" }, "✎") : el("img", { loading: "lazy", src: thumbUrl(s), alt: "" });
    g.append(el("button", { class: "card" + (S.start && S.start.kind === s.kind && S.start.ref === s.ref ? " on" : ""),
      title: s.title, onclick: () => startFrom(s) }, pic, el("div", { class: "t" }, s.title), el("div", { class: "w" }, s.what)));
  }
}
async function startFrom(s) {
  if (S.state && S.dirty && !confirm("Start again from this one? Your changes are lost (unless saved).")) return;
  try {
    status("Loading…");
    const d = s.kind === "draft" ? loadDraft() : await api("load", { kind: s.kind, ref: s.ref });
    S.state = d.state; S.start = s;
    if (d.title !== undefined) $("f-title").value = d.title || "";
    if (d.description !== undefined) $("f-desc").value = d.description || "";
    if (d.name) $("f-name").value = d.name;
    $("start-now").textContent = `· now: ${s.title}`;
    $("gallery-box").open = false;
    S.dirty = false; status("");
    renderAll(); refreshView();
  } catch (e) { status(e.message, true); }
}

// ------------------------------------------------------------------ step 2: the holder
function cellSvg(gap, big) {
  // side view, to scale along the beam (z): window 1.25 mm, gap, window; height not to scale
  const w = S.info.cell.window_mm, tot = 2 * w + gap;
  const W = big ? 520 : 260, H = big ? 200 : 120, x0 = big ? 150 : 70, span = big ? 300 : 150;
  const k = span / 7.5;                      // px per mm (the widest cell: 2.5 + 5 mm)
  const y0 = big ? 30 : 18, h = big ? 130 : 78, cx = x0 + (span - tot * k) / 2;
  const x = S.state.d2o, liq = liquid() ? `rgb(${Math.round(255 * (0.90 - 0.10 * x))},${Math.round(255 * (0.96 - 0.06 * x))},${Math.round(255 * (0.90 + 0.10 * x))})` : "#FFFFFF";
  const fs = big ? 13 : 10;
  let s = `<defs><marker id="ar${big ? 1 : 0}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#B4562B"/></marker></defs>`;
  s += `<line x1="8" y1="${y0 + h / 2}" x2="${cx - 6}" y2="${y0 + h / 2}" stroke="#B4562B" stroke-width="2.5" marker-end="url(#ar${big ? 1 : 0})"/>`;
  s += `<text x="8" y="${y0 + h / 2 - 8}" font-size="${fs}" fill="#B4562B">neutrons</text>`;
  s += `<rect x="${cx}" y="${y0}" width="${w * k}" height="${h}" fill="#DCEBF6" stroke="#5B87A8"/>`;
  s += `<rect x="${cx + w * k}" y="${y0}" width="${gap * k}" height="${h}" fill="${liq}" stroke="#334155" stroke-width=".8"/>`;
  s += `<rect x="${cx + (w + gap) * k}" y="${y0}" width="${w * k}" height="${h}" fill="#DCEBF6" stroke="#5B87A8"/>`;
  s += `<line x1="${cx + tot * k + 4}" y1="${y0 + h / 2}" x2="${W - 8}" y2="${y0 + h / 2}" stroke="#B4562B" stroke-width="2.5" stroke-dasharray="5 4" marker-end="url(#ar${big ? 1 : 0})"/>`;
  const yb = y0 + h + (big ? 22 : 16);
  if (big) {
    s += `<text x="${cx + w * k / 2}" y="${yb}" font-size="${fs}" text-anchor="middle" fill="#5B6779">${w}</text>`;
    s += `<text x="${cx + (1.5 * w + gap) * k}" y="${yb}" font-size="${fs}" text-anchor="middle" fill="#5B6779">${w}</text>`;
    s += `<text x="${cx + (w + gap / 2) * k}" y="${yb + 16}" font-size="${fs}" text-anchor="middle" font-weight="600" fill="#142033">${fmt(gap, 3)} mm</text>`;
  } else {
    s += `<text x="${cx + (w + gap / 2) * k}" y="${yb}" font-size="${fs}" text-anchor="middle" fill="#142033"><tspan font-weight="600">${fmt(gap, 3)} mm</tspan> of ${liquid() ? "liquid" : "air"}</text>`;
    s += `<text x="${cx + (w + gap / 2) * k}" y="${y0 - 5}" font-size="${fs}" text-anchor="middle" fill="#5B87A8">quartz windows ${w} mm</text>`;
  }
  if (big) {
    s += `<text x="${cx + w * k / 2}" y="${y0 - 8}" font-size="12" text-anchor="middle" fill="#5B87A8">quartz</text>`;
    s += `<text x="${cx + (w + gap / 2) * k}" y="${y0 - 8}" font-size="12" text-anchor="middle" fill="#142033">${liquid() ? "liquid" : "air"}</text>`;
    s += `<text x="${cx + (1.5 * w + gap) * k}" y="${y0 - 8}" font-size="12" text-anchor="middle" fill="#5B87A8">quartz</text>`;
  }
  return s;
}
function renderHolders() {
  const g = $("holders"); g.innerHTML = "";
  const opts = [["cell", "Quartz cell", "Fused quartz windows, 1.25 mm each; the liquid between them (the gap). As the usual SANS cells.",
    '<rect x="58" y="12" width="10" height="60" fill="#DCEBF6" stroke="#5B87A8"/><rect x="68" y="12" width="24" height="60" fill="#D5E6F7" stroke="#334155"/><rect x="92" y="12" width="10" height="60" fill="#DCEBF6" stroke="#5B87A8"/>'],
  ["none", "No cell", "Nothing on the sample position: the empty beam (only with air: a liquid needs its cell).", ""]];
  for (const [k, t, x, pic] of opts) {
    const off = k === "none" && liquid();
    g.append(el("button", { class: "holder" + (S.state.holder.type === k ? " on" : ""), disabled: off ? "" : null, onclick: () => {
      if (k === S.state.holder.type || off) return;
      S.state.holder = k === "cell" ? { type: "cell", gap_mm: 1.0 } : { type: "none" };
      changed(true);
    } }, el("span", { html: `<svg viewBox="0 0 160 84"><path d="M0 42h160" stroke="#F0C9B5" stroke-dasharray="4 4"/>${pic}</svg>` }),
      el("div", { class: "t" }, t), el("div", { class: "x" }, x)));
  }
  const cell = S.state.holder.type === "cell";
  $("cell-box").classList.toggle("hidden", !cell);
  if (!cell) return;
  const p = $("cell-params"); p.innerHTML = "";
  p.append(sliderRow(liquid() ? "gap (liquid thickness)" : "gap (air)", S.state.holder.gap_mm, S.info.cell.gap_min, S.info.cell.gap_max,
    (v) => { S.state.holder.gap_mm = v; changed(); $("cell-big").innerHTML = cellSvg(v, true); }, { unit: "mm", round: (v) => Math.round(v * 100) / 100 }));
  p.append(el("div", { class: "slider wide" }, el("span", { class: "nm" }, "windows"), el("span", { class: "fixed" }, `2 × ${S.info.cell.window_mm} mm of fused quartz (fixed)`)));
  $("cell-big").innerHTML = cellSvg(S.state.holder.gap_mm, true);
}

// ------------------------------------------------------------------ step 3: check and save
async function renderChecks() {
  $("checks").innerHTML = '<li class="wait">Checking…</li>';
  try {
    const d = await api("check", { state: S.state });
    $("checks").innerHTML = "";
    for (const it of d.items) $("checks").append(el("li", { class: it.status }, el("span", { class: "dot" }),
      el("div", {}, el("div", { class: "t" }, it.title), el("div", { class: "x" }, it.text))));
  } catch (e) { $("checks").innerHTML = `<li class="red"><span class="dot"></span><div><div class="t">Not possible to check it</div><div class="x">${esc(e.message)}</div></div></li>`; }
}
async function save() {
  const m = $("save-msg"); m.className = "msg"; m.textContent = "Saving…";
  S.proposal = $("f-proposal").value.trim();
  try {
    const d = await api("save", { state: S.state, name: $("f-name").value.trim(), title: $("f-title").value.trim(), description: $("f-desc").value.trim() });
    m.className = "msg ok"; m.innerHTML = `Saved with proposal ${esc(S.proposal)}. In NICOS: <code>${esc(d.nicos)}</code>`;
    S.dirty = false; clearDraft();
  } catch (e) { m.className = "msg err"; m.textContent = "Not saved: " + e.message; }
}
async function saveModel() {
  const m = $("model-msg"); m.className = "msg"; m.textContent = "Saving…";
  try {
    const d = await api("save_model", { state: S.state, model: $("f-model").value.trim(), title: $("f-title").value.trim(), description: $("f-desc").value.trim() });
    m.className = "msg ok"; m.textContent = "Saved as a model: anyone can now start from it (Start from)." +
      (d.left_out ? ` The ${d.left_out} kind(s) of particles with hidden properties are left out of it.` : "");
    S.info.starts = (await api("info", {})).starts; renderGallery();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
}
async function download() {
  try {
    const d = await api("download", { state: S.state, title: $("f-title").value, description: $("f-desc").value });
    const a = el("a", { href: URL.createObjectURL(new Blob([d.text], { type: "text/yaml" })), download: `${$("f-name").value.trim() || "sample"}.yml` });
    document.body.append(a); a.click(); a.remove();
  } catch (e) { const m = $("save-msg"); m.className = "msg err"; m.textContent = e.message; }
}

// ------------------------------------------------------------------ steps
function go(n) {
  S.step = n;
  for (const k of [1, 2, 3, 4]) $(`step${k}`).classList.toggle("hidden", k !== n);
  document.querySelectorAll("#steps button").forEach((b) => b.classList.toggle("on", Number(b.dataset.step) === n));
  $("panel").scrollTop = 0;
  if (n === 2) renderHolders();
  if (n === 3) { if (!$("f-proposal").value) $("f-proposal").value = S.proposal; renderChecks(); }
  if (n === 4) renderFit();
}

// ------------------------------------------------------------------ step 4: fit the sample to the measurements
// builder_loki.fit_files / fit_params / fit_run: I(Q) of the sample minus the solvent (esssans), against the cross
// section of the kinds of particles
let FIT = null;
async function renderFit() {
  const box = $("fit-files");
  $("fit-result").classList.add("hidden");
  if (!S.proposal) { box.innerHTML = "<p class='note-box'>Open the builder from a beamtime notebook: the fit uses the files measured for your proposal.</p>"; return; }
  box.innerHTML = "<p class='small'>Reading the files of your proposal…</p>";
  let rows;
  try { rows = (await api("fit_files")).rows; } catch (e) { box.innerHTML = ""; box.append(el("p", { class: "msg err" }, e.message)); return; }
  const has = (k) => rows.some((r) => r.kind === k);
  if (!has("sample") || !has("solvent") || !has("empty beam")) {
    box.innerHTML = "";
    box.append(el("p", { class: "note-box" }, `Not everything is measured yet in proposal ${S.proposal}: the fit needs your sample, the`
      + " solvent alone (the same cell) and the empty beam, measured in NICOS with the same settings."));
    return;
  }
  const pick = (kind, id, label) => {
    const opts = rows.filter((r) => r.kind === kind);
    const sel = el("select", { id }, ...opts.map((r) => el("option", { value: r.file }, `${r.file} · ${r.title} · ${r.collimation || ""} · ${r.t_s} s`)));
    sel.value = opts[opts.length - 1].file;
    return el("label", { class: "fit-file" }, el("span", {}, label), sel);
  };
  box.innerHTML = "";
  box.append(pick("sample", "fit-sample", "Sample"), pick("solvent", "fit-solvent", "Solvent"), pick("empty beam", "fit-empty", "Empty beam"));
  const pbox = $("fit-params");
  let params;
  try { params = (await api("fit_params", { state: S.state })).params; } catch (e) { pbox.innerHTML = ""; pbox.append(el("p", { class: "msg err" }, e.message)); return; }
  pbox.innerHTML = "";
  if (!params.length) { pbox.append(el("p", { class: "note-box" }, "No particles to fit: add a kind of particles in step 1.")); return; }
  for (const p of params) {
    pbox.append(el("div", { class: "fit-param", "data-key": p.key, "data-label": p.label },
      el("label", { class: "fit-tick" }, el("input", { type: "checkbox" }), el("span", {}, p.label)),
      el("span", { class: "small" }, `now ${+p.value.toPrecision(4)}`),
      el("label", { class: "small" }, "from ", el("input", { type: "number", class: "fit-min", value: p.min, step: "any" })),
      el("label", { class: "small" }, "to ", el("input", { type: "number", class: "fit-max", value: p.max, step: "any" }))));
  }
}
async function runFit() {
  const params = [...document.querySelectorAll("#fit-params .fit-param")].filter((r) => r.querySelector("input[type=checkbox]").checked)
    .map((r) => ({ key: r.dataset.key, label: r.dataset.label, min: Number(r.querySelector(".fit-min").value), max: Number(r.querySelector(".fit-max").value) }));
  const msg = $("fit-msg");
  if (!$("fit-sample")) { msg.className = "msg err"; msg.textContent = "Nothing measured to fit (above)."; return; }
  if (!params.length) { msg.className = "msg err"; msg.textContent = "Tick at least one number to fit."; return; }
  $("fit-run").disabled = true; msg.className = "msg"; msg.textContent = "Reducing your files and fitting… up to a minute.";
  try {
    const d = await api("fit_run", { state: S.state, sample: $("fit-sample").value, solvent: $("fit-solvent").value,
      empty_beam: $("fit-empty").value, params });
    FIT = d;
    $("fit-plot").src = "data:image/png;base64," + d.png;
    $("fit-report").textContent = d.report + (d.chi2_red > 3 ? "\n\nχ²/dof well above 1: the model does not describe the data within"
      + " their errors (another shape, a second kind of particles, polydispersity?)." : "");
    $("fit-result").classList.remove("hidden"); $("fit-apply-msg").textContent = "";
    msg.className = "msg ok"; msg.textContent = d.success ? "Done." : "The fit stopped before converging: see the result.";
  } catch (e) { msg.className = "msg err"; msg.textContent = e.message; }
  $("fit-run").disabled = false;
}
function applyFit() {
  if (!FIT) return;
  for (const v of FIT.values) {
    const [i, ...rest] = v.key.split(".");
    let node = S.state.kinds[Number(i)];
    for (const r of rest.slice(0, -1)) node = node[r];
    node[rest[rest.length - 1]] = Number(v.value.toPrecision(5));
  }
  changed(true);
  const m = $("fit-apply-msg"); m.className = "msg ok";
  m.textContent = "Done: your sample has the fitted values. Look at it (step 1), then save it (step 3).";
}

// ------------------------------------------------------------------ the live view
function drawPlot() {
  const svg = $("plot"), wrap = $("plotwrap");
  const W = Math.max(300, wrap.clientWidth), H = Math.max(220, wrap.clientHeight);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("width", W); svg.setAttribute("height", H);
  const v = S.view;
  if (!v) { svg.innerHTML = ""; return; }
  const L = 64, R = 14, T = 24, B = 44, pw = W - L - R, ph = H - T - B;
  const xl = [Math.log10(v.q[0]), Math.log10(v.q[v.q.length - 1])];
  let s = "";
  if (v.empty) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" font-size="15" fill="#5B6779">Empty beam: nothing on the sample position, nothing scattered.</text>`;
    return;
  }
  const curves = [v.total, ...(v.kinds || []).map((k) => k.curve)];
  let ymax = Math.max(...curves.flat().filter((y) => y > 0));
  let ymin = Math.min(...v.total.filter((y) => y > 0));
  const floor = Math.min(v.background || ymin, ymin);
  ymin = Math.max(floor / 5, ymax * 1e-7);
  const yl = [Math.floor(Math.log10(ymin)), Math.ceil(Math.log10(ymax * 2))];
  if (yl[1] - yl[0] < 2) { yl[0] -= 1; yl[1] += 1; }
  const X = (q) => L + (Math.log10(q) - xl[0]) / (xl[1] - xl[0]) * pw;
  const Y = (y) => T + (yl[1] - Math.log10(Math.max(y, 10 ** yl[0]))) / (yl[1] - yl[0]) * ph;
  S.plotMap = { X, Y, L, R, T, B, W, H, xl, yl, pw, ph };
  // LoKI's range
  const [qa, qb] = v.q_range;
  s += `<rect x="${X(qa)}" y="${T}" width="${X(qb) - X(qa)}" height="${ph}" fill="#E3F2EF" opacity=".75"/>`;
  s += `<text x="${(X(qa) + X(qb)) / 2}" y="${T + 14}" text-anchor="middle" font-size="11.5" fill="#0E7C70">LoKI's Q range (${qa}–${qb} Å⁻¹)</text>`;
  // grid and axes
  for (let e = Math.ceil(xl[0]); e <= Math.floor(xl[1]); e++) {
    for (let m = 1; m < 10; m++) { const q = m * 10 ** e; if (Math.log10(q) > xl[1] + 1e-9) break; if (Math.log10(q) < xl[0]) continue;
      s += `<line x1="${X(q)}" x2="${X(q)}" y1="${T}" y2="${T + ph}" stroke="${m === 1 ? "#D5DBE3" : "#EEF1F5"}"/>`; }
    s += `<text x="${X(10 ** e)}" y="${T + ph + 16}" text-anchor="middle" class="ax">10${sup(e)}</text>`;
  }
  for (let e = yl[0]; e <= yl[1]; e++) {
    s += `<line x1="${L}" x2="${L + pw}" y1="${Y(10 ** e)}" y2="${Y(10 ** e)}" stroke="#D5DBE3"/>`;
    s += `<text x="${L - 6}" y="${Y(10 ** e) + 4}" text-anchor="end" class="ax">10${sup(e)}</text>`;
  }
  s += `<rect x="${L}" y="${T}" width="${pw}" height="${ph}" fill="none" stroke="#9AA6B6"/>`;
  s += `<text x="${L + pw / 2}" y="${H - 8}" text-anchor="middle" class="axl">Q [Å⁻¹]</text>`;
  s += `<text transform="translate(16 ${T + ph / 2}) rotate(-90)" text-anchor="middle" class="axl">dΣ/dΩ [cm⁻¹ sr⁻¹]</text>`;
  const path = (ys) => "M" + v.q.map((q, i) => `${X(q).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join("L");
  // background, kinds, total
  const leg = [];
  if (v.background && !v.empty_cell) {
    s += `<line x1="${L}" x2="${L + pw}" y1="${Y(v.background)}" y2="${Y(v.background)}" stroke="#7C8796" stroke-dasharray="6 4" stroke-width="1.4"/>`;
    leg.push(["#7C8796", "incoherent background of the liquid", "6 4"]);
  }
  for (const k of v.kinds || []) {
    s += `<path d="${path(k.curve)}" fill="none" stroke="${k.color}" stroke-width="1.6" opacity=".9"/>`;
    leg.push([k.color, `kind ${k.index + 1}`, ""]);
  }
  s += `<path d="${path(v.total)}" fill="none" stroke="#142033" stroke-width="2.4"/>`;
  leg.unshift(["#142033", v.empty_cell ? "the empty cell (almost nothing)" : "your sample (all together)", ""]);
  for (const i of v.hidden || []) leg.push(["#9CA3AF", `kind ${i + 1}: hidden properties, not drawn`, "2 3"]);
  // the legend, bottom left (where a SANS curve seldom goes: high intensities are at low Q, the background at high Q)
  const lw = Math.max(...leg.map((l) => l[1].length)) * 6.3 + 36, lh = leg.length * 17 + 8;
  const lx = L + 8 + lw; let ly = T + ph - lh - 8 + 14;
  s += `<rect x="${lx - lw}" y="${ly - 14}" width="${lw}" height="${lh}" rx="6" fill="#fff" opacity=".92" stroke="#E2E7EE"/>`;
  for (const [c, t, da] of leg) {
    s += `<line x1="${lx - lw + 8}" x2="${lx - lw + 28}" y1="${ly - 4}" y2="${ly - 4}" stroke="${c}" stroke-width="2.4" ${da ? `stroke-dasharray="${da}"` : ""}/>`;
    s += `<text x="${lx - lw + 34}" y="${ly}" font-size="11.5" fill="#142033">${esc(t)}</text>`; ly += 17;
  }
  s += `<line id="cross" x1="0" x2="0" y1="${T}" y2="${T + ph}" stroke="#0E7C70" stroke-width="1" opacity="0"/>`;
  svg.innerHTML = s;
}
function hover(e) {
  const v = S.view, m = S.plotMap, tip = $("tip");
  if (!v || !m || v.empty) { tip.classList.add("hidden"); return; }
  const r = $("plot").getBoundingClientRect(), px = e.clientX - r.left;
  if (px < m.L || px > m.L + m.pw) { tip.classList.add("hidden"); $("cross")?.setAttribute("opacity", 0); return; }
  const lq = m.xl[0] + (px - m.L) / m.pw * (m.xl[1] - m.xl[0]), q = 10 ** lq;
  let i = 0; while (i < v.q.length - 1 && v.q[i] < q) i++;
  tip.classList.remove("hidden");
  tip.style.left = `${Math.min(px + 12, r.width - 190)}px`; tip.style.top = `${m.T + 30}px`;
  tip.innerHTML = `Q = ${fmt(v.q[i], 3)} Å⁻¹ <span class="small">(sees ≈ 2π/Q = ${fmt(2 * Math.PI / v.q[i] / 10, 3)} nm)</span><br>dΣ/dΩ = ${fmt(v.total[i], 3)} cm⁻¹ sr⁻¹`;
  const c = $("cross"); c.setAttribute("x1", m.X(v.q[i])); c.setAttribute("x2", m.X(v.q[i])); c.setAttribute("opacity", 0.6);
}
function drawNumbers() {
  const v = S.view, n = $("numbers");
  if (!v) { n.innerHTML = ""; return; }
  if (v.empty) { n.innerHTML = "<span>Transmission 1 (nothing in the beam)</span>"; return; }
  const parts = [`<span><b>Transmission</b> ${fmt(v.transmission[0], 2)} at ${v.lams[0]} Å, ${fmt(v.transmission[1], 2)} at ${v.lams[1]} Å</span>`];
  if (v.background && !v.empty_cell) parts.push(`<span><b>Background</b> ${fmt(v.background, 2)} cm⁻¹ sr⁻¹</span>`);
  if (v.kinds && v.kinds.length) parts.push(`<span><b>At Q = ${v.q_range[0]} Å⁻¹</b> ${fmt(v.total[v.q.findIndex((q) => q >= v.q_range[0])], 3)} cm⁻¹ sr⁻¹</span>`);
  n.innerHTML = parts.join("");
}
function drawScale() {
  const svg = $("scale"); const W = Math.max(200, svg.clientWidth || 260), H = 120;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  if (!liquid()) { svg.innerHTML = `<text x="${W / 2}" y="60" text-anchor="middle" font-size="12" fill="#5B6779">no particles (air)</text>`; return; }
  const kinds = S.state.kinds || [];
  if (!kinds.length) { svg.innerHTML = `<text x="${W / 2}" y="60" text-anchor="middle" font-size="12" fill="#5B6779">no particles: the liquid alone</text>`; return; }
  // the extent (Å) of each kind: width x height of its drawing
  const ext = kinds.map((k) => {
    if (kindSealed(k)) return null;
    const p = k.parameters;
    if (k.model === "cylinder") return [p.length, 2 * p.radius];
    const R = p.radius + (k.model === "core_shell_sphere" ? p.thickness : 0); return [2 * R, 2 * R];
  });
  const slotW = (W - 10) / kinds.length, maxH = 72;
  const k = Math.min(...ext.filter(Boolean).map((e) => Math.min((slotW - 12) / e[0], maxH / e[1])), Infinity);
  let s = "";
  kinds.forEach((kd, i) => {
    const cx = 5 + slotW * (i + 0.5), cy = 46, col = kindColor(i);
    const e = ext[i];
    if (!e) {
      s += `<circle cx="${cx}" cy="${cy}" r="18" fill="#E5E7EB" stroke="#9CA3AF" stroke-dasharray="3 3"/><text x="${cx}" y="${cy + 5}" text-anchor="middle" font-size="15" fill="#6B7280">?</text>`;
      s += `<text x="${cx}" y="${H - 14}" text-anchor="middle" font-size="11" fill="#5B6779">kind ${i + 1}: hidden</text>`;
      return;
    }
    const p = kd.parameters, mc = sealed(kd.particle) ? "#E5E7EB" : matColor(kd.particle);
    if (kd.model === "cylinder") {
      const w = Math.max(2, p.length * k), h = Math.max(1.5, 2 * p.radius * k);
      s += `<rect x="${cx - w / 2}" y="${cy - h / 2}" width="${w}" height="${h}" rx="${Math.min(h / 4, 3)}" fill="${mc}" stroke="${col}" stroke-width="2"/>`;
    } else {
      const R = Math.max(1.2, e[0] / 2 * k);
      s += `<circle cx="${cx}" cy="${cy}" r="${R}" fill="${mc}" stroke="${col}" stroke-width="2"/>`;
      if (kd.model === "core_shell_sphere") {
        const cc = kd.core_particle && !sealed(kd.core_particle) ? matColor(kd.core_particle) : mc;
        s += `<circle cx="${cx}" cy="${cy}" r="${Math.max(0.8, p.radius * k)}" fill="${cc}" stroke="${col}" stroke-width=".8" stroke-dasharray="2 2"/>`;
      }
    }
    const size = kd.model === "cylinder" ? `${fmt(p.length / 10, 3)} × ${fmt(2 * p.radius / 10, 3)} nm` : `⌀ ${fmt(e[0] / 10, 3)} nm`;
    s += `<text x="${cx}" y="${H - 14}" text-anchor="middle" font-size="11" fill="${col}">kind ${i + 1}: ${size}</text>`;
  });
  // a scale bar
  if (isFinite(k)) {
    const target = 60 / k; const p10 = 10 ** Math.floor(Math.log10(target));
    const bar = [1, 2, 5, 10].map((m) => m * p10).filter((b) => b <= target).pop() || p10;
    s += `<line x1="8" x2="${8 + bar * k}" y1="${H - 3}" y2="${H - 3}" stroke="#142033" stroke-width="2"/>`;
    s += `<text x="${12 + bar * k}" y="${H - 0}" font-size="10" fill="#142033">${fmt(bar / 10, 3)} nm</text>`;
  }
  svg.innerHTML = s;
}
function drawCell() {
  const svg = $("cell");
  if (S.state.holder.type !== "cell") { svg.innerHTML = `<text x="130" y="60" text-anchor="middle" font-size="12" fill="#5B6779">no cell: the empty beam</text>`; return; }
  svg.innerHTML = cellSvg(S.state.holder.gap_mm, false);
}
function drawAll() { drawPlot(); drawNumbers(); drawScale(); drawCell(); }

// ------------------------------------------------------------------ refreshing
let timer = null;
function changed(rerender = false) {
  S.dirty = true; saveDraft();
  if (rerender) renderAll(); else { renderSldScale(); if (S.step === 1) refreshCards(); }
  drawScale(); drawCell();
  clearTimeout(timer); timer = setTimeout(refreshView, 250);
}
function refreshCards() {   // the contrasts change with the D2O fraction: the material cards again (keeping the sliders)
  document.querySelectorAll("#kinds .kind").forEach((card, i) => {
    const k = S.state.kinds[i]; if (!k) return;
    card.querySelectorAll(".matcard[data-field]").forEach((m) => {
      const f = m.dataset.field;
      m.replaceWith(matCard(k, f, k.model === "core_shell_sphere" ? (f === "particle" ? "shell" : "core") : ""));
    });
  });
  phiTotal();
}
function phiTotal() {
  const kinds = S.state.kinds || [];
  const open = kinds.filter((k) => !sealed(k.volume_fraction));
  const phi = open.reduce((a, k) => a + Number(k.volume_fraction || 0), 0);
  const limits = `the twin accepts up to ${S.info.max_fraction * 100} % in all, and particles start to feel one another above ~1 %.`;
  $("phi-total").textContent = !kinds.length ? "" : !open.length ? `The amount of particles is hidden (what you measure); ${limits}`
    : `In all: ${fmt(phi * 100, 3)} % of the volume is particles${open.length < kinds.length ? " (plus the hidden amount)" : ""}; ${limits}`;
}
async function refreshView() {
  const my = ++S.viewKey;
  try {
    const d = await api("view", { state: S.state });
    if (my !== S.viewKey) return;
    S.view = d; status(""); drawAll();
  } catch (e) { if (my === S.viewKey) status(e.message, true); }
}

// ------------------------------------------------------------------ draft (this computer only)
const DRAFT = `twin-builder:${INSTR}:${S.proposal || "none"}`;
function saveDraft() { try { localStorage.setItem(DRAFT, JSON.stringify({ state: S.state, title: $("f-title").value, description: $("f-desc").value, name: $("f-name").value, when: new Date().toLocaleString() })); } catch { /* no storage */ } }
function loadDraft() { try { const d = JSON.parse(localStorage.getItem(DRAFT) || "null"); return d && d.state ? d : null; } catch { return null; } }
function clearDraft() { try { localStorage.removeItem(DRAFT); } catch { /* no storage */ } }

function renderAll() { renderLiquid(); if (liquid()) renderKinds(); if (S.step === 2) renderHolders(); drawScale(); drawCell(); }

// ------------------------------------------------------------------ start
async function main() {
  $("where").textContent = `LoKI · small-angle scattering${S.proposal ? ` · proposal ${S.proposal}` : ""}`;
  document.querySelectorAll("#steps button").forEach((b) => b.addEventListener("click", () => go(Number(b.dataset.step))));
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(Number(b.dataset.go))));
  $("gallery-search").addEventListener("input", renderGallery);
  $("picker-close").addEventListener("click", closePicker);
  $("picker").addEventListener("click", (e) => { if (e.target.id === "picker") closePicker(); });
  $("save").addEventListener("click", save);
  $("fit-run").addEventListener("click", runFit);
  $("fit-apply").addEventListener("click", applyFit);
  $("save-model").addEventListener("click", saveModel);
  $("download").addEventListener("click", download);
  $("plot").addEventListener("mousemove", hover);
  $("plot").addEventListener("mouseleave", () => { $("tip").classList.add("hidden"); $("cross")?.setAttribute("opacity", 0); });
  new ResizeObserver(() => { if (S.state) { drawPlot(); drawScale(); } }).observe($("plotwrap"));
  ["f-title", "f-desc", "f-name"].forEach((id) => $(id).addEventListener("change", saveDraft));
  $("f-name").value = Q.get("name") || ""; $("f-title").value = Q.get("title") || "";
  $("f-proposal").value = S.proposal;
  status("Opening…");
  try { S.info = await api("info", { start: Q.get("start") || "" }); }
  catch (e) { status("The builder cannot reach the server: " + e.message, true); return; }
  renderGallery();
  const given = Q.get("start");
  const st = given ? S.info.starts.find((s) => s.kind === "sample" && s.ref === given) : null;
  if (st) {
    await startFrom(st);
    if (!$("f-name").value) $("f-name").value = `${given}_changed`.slice(0, 31);
    if (Q.get("title")) $("f-title").value = Q.get("title");
  } else {
    await startFrom(S.info.starts.find((s) => s.kind === "scratch"));
    $("gallery-box").open = true; $("start-now").textContent = "";
  }
}
main();
