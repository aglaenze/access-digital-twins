// The sample builder page of the app (builder/index.html): edits a samplecraft recipe (the sample) and a holder
// chosen apart; the server (builder_api.py, through /twin/builder/api/...) builds, draws, checks and saves.
import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

// ------------------------------------------------------------------ server
const Q = new URLSearchParams(location.search);
const TOKEN = Q.get("token") || "";
const API = "builder/api/";
const INSTR = (Q.get("instrument") || "odin").toLowerCase();
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
const S = {
  info: null, proposal: (Q.get("proposal") || "").trim(), recipe: null, holder: { type: "none" }, sel: [0],
  start: null, lam: 3.0, colors: {}, sig: {}, catSig: {}, step: 1, grains: true, previewKey: 0,
};
const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else if (v !== undefined && v !== null) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const clone = (o) => JSON.parse(JSON.stringify(o));
const r4 = (x) => Math.round(x * 1e4) / 1e4;
function status(msg, err = false) { const s = $("status"); s.textContent = msg || ""; s.classList.toggle("err", !!err); }

// ------------------------------------------------------------------ the recipe tree
function body(path) { let b = S.recipe.bodies[path[0]]; for (const i of path.slice(1)) b = b.children[i]; return b; }
function siblings(path) { return path.length === 1 ? S.recipe.bodies : (body(path.slice(0, -1)).children ||= []); }
function* walk(bodies = S.recipe.bodies, path = []) {
  for (let i = 0; i < bodies.length; i++) { const p = [...path, i]; yield [p, bodies[i]]; yield* walk(bodies[i].children || [], p); }
}
const samePath = (a, b) => a && b && a.length === b.length && a.every((x, i) => x === b[i]);
const shapeName = (t) => (S.info.shapes.find((s) => s.type === t) || {}).label || ({ union: "combined shapes",
  difference: "shape with cuts", intersection: "intersection of shapes", mesh: "mesh from a file", prism: "prism" })[t] || t || "?";

function renderTree() {
  const ul = $("tree"); ul.innerHTML = "";
  for (const [p, b] of walk()) {
    const pad = 8 + 18 * (p.length - 1);
    if (b.sealed) {
      ul.append(el("li", { class: "locked", style: `padding-left:${pad}px` }, "🔒 ", b.name || "hidden part"));
      continue;
    }
    const what = b.use ? `copy of “${b.use}”` : shapeName((b.shape || {}).type);
    const nf = (b.fill || []).filter((f) => !f.sealed).length;
    const li = el("li", { class: samePath(p, S.sel) ? "on" : "", style: `padding-left:${pad}px`,
      onclick: () => { S.sel = p; renderTree(); renderPart(); highlight(); } },
      el("span", { class: "sw", style: `background:${S.colors[b.material] || "#ddd"}` }),
      el("span", { class: "nm" }, b.name || "(unnamed)"),
      el("span", { class: "mt" }, `${what}${b.material ? " · " + b.material : ""}`),
      nf ? el("span", { class: "tag" }, `${nf} kind${nf > 1 ? "s" : ""} of grains`) : null);
    ul.append(li);
  }
  const b = S.recipe.bodies.length ? body(S.sel) : null;
  for (const id of ["duplicate", "up", "down", "remove", "add-inside"]) $(id).disabled = !b;
}

function uniqueName(base) {
  const names = new Set([...walk()].map(([, b]) => b.name));
  if (!names.has(base)) return base;
  for (let k = 2; ; k++) if (!names.has(`${base} ${k}`)) return `${base} ${k}`;
}
function otherMaterial(not) {
  const ks = Object.keys(S.recipe.materials || {}).filter((k) => k !== not && !k.startsWith("holder: "));
  if (ks.length) return ks[0];
  S.recipe.materials.copper = { ncrystal: "Cu_sg225.ncmat" }; return "copper";
}
function treeAction(a) {
  const p = S.sel, sib = siblings(p), i = p[p.length - 1], b = body(p);
  if (a === "inside") {
    const ctr = (b.shape && b.shape.position) || b.position || [0, 0, 0];
    (b.children ||= []).push({ name: uniqueName("inclusion"), material: otherMaterial(b.material),
      shape: { type: "sphere", diameter: 1.0, position: [...ctr] } });
    S.sel = [...p, b.children.length - 1];
  } else if (a === "beside") {
    const ctr = (b.shape && b.shape.position) || [0, 0, 0];
    sib.splice(i + 1, 0, { name: uniqueName("part"), material: b.material || otherMaterial(),
      shape: { type: "box", size: [2, 2, 2], position: [r4(ctr[0] + 4), ctr[1], ctr[2]] } });
    S.sel = [...p.slice(0, -1), i + 1];
  } else if (a === "duplicate") {
    const c = clone(b); c.name = uniqueName(b.name || "part");
    const shift = (x) => { if (x.shape && x.shape.position) x.shape.position[0] = r4(x.shape.position[0] + 1); if (x.position) x.position[0] = r4(x.position[0] + 1); (x.children || []).forEach(shift); };
    shift(c); sib.splice(i + 1, 0, c); S.sel = [...p.slice(0, -1), i + 1];
  } else if (a === "up" || a === "down") {
    const j = a === "up" ? i - 1 : i + 1;
    if (j < 0 || j >= sib.length) return;
    [sib[i], sib[j]] = [sib[j], sib[i]]; S.sel = [...p.slice(0, -1), j];
  } else if (a === "remove") {
    if (!confirm(`Delete “${b.name}”${(b.children || []).length ? " and what is inside it" : ""}?`)) return;
    sib.splice(i, 1);
    if (!sib.length && p.length > 1) { delete body(p.slice(0, -1)).children; S.sel = p.slice(0, -1); }
    else S.sel = [...p.slice(0, -1), Math.max(0, i - 1)];
    if (!S.recipe.bodies.length) S.sel = [0];
  }
  changed();
}

// ------------------------------------------------------------------ the selected part
const ICONS = {
  box: '<rect x="8" y="6" width="22" height="18" fill="#C9D3DF" stroke="#142033"/><path d="M8 6l6-4h22l-6 4M30 24l6-4V2" fill="none" stroke="#142033"/>',
  cylinder: '<ellipse cx="19" cy="6" rx="10" ry="3.5" fill="#C9D3DF" stroke="#142033"/><path d="M9 6v18a10 3.5 0 0 0 20 0V6" fill="#C9D3DF" stroke="#142033"/>',
  sphere: '<circle cx="19" cy="15" r="11" fill="#C9D3DF" stroke="#142033"/><ellipse cx="19" cy="15" rx="11" ry="3.5" fill="none" stroke="#8090A4"/>',
  ellipsoid: '<ellipse cx="19" cy="15" rx="15" ry="9" fill="#C9D3DF" stroke="#142033"/>',
  cone: '<path d="M10 26L19 3l9 23z" fill="#C9D3DF" stroke="#142033"/><ellipse cx="19" cy="26" rx="9" ry="2.5" fill="#C9D3DF" stroke="#142033"/>',
  torus: '<ellipse cx="19" cy="15" rx="15" ry="9" fill="#C9D3DF" stroke="#142033"/><ellipse cx="19" cy="15" rx="7" ry="3.5" fill="#fff" stroke="#142033"/>',
  superellipsoid: '<rect x="6" y="5" width="26" height="20" rx="7" fill="#C9D3DF" stroke="#142033"/>',
  blob: '<path d="M7 16c0-8 7-12 13-11s12 4 11 11-6 10-12 9-12-2-12-9z" fill="#C9D3DF" stroke="#142033"/>',
  sawn_piece: '<path d="M9 3h18l3 4-1 19H11l-3-5z" fill="#C9D3DF" stroke="#142033"/>',
};
function sliderRow(label, value, min, max, step, onset, unit = "mm") {
  const rng = el("input", { type: "range", min, max, step, value });
  const num = el("input", { type: "number", min, max, step, value: r4(value) });
  const set = (v, from) => { v = Number(v); if (!isFinite(v)) return; if (from !== rng) rng.value = v; if (from !== num) num.value = r4(v); onset(v); };
  rng.addEventListener("input", () => set(rng.value, rng));
  num.addEventListener("change", () => set(num.value, num));
  return el("div", { class: "slider" }, el("span", { class: "nm" }, label), rng, num, el("span", { class: "u" }, unit));
}
const XYZ = ["x", "y", "z"];

function renderPart() {
  const box = $("part"); box.innerHTML = "";
  if (!S.recipe.bodies.length) { box.append(el("p", { class: "lead" }, "No part yet: + Beside adds one.")); return; }
  const b = body(S.sel);
  $("part-title").textContent = `The selected part: ${b.name || ""}`;
  if (b.sealed) { box.append(el("p", { class: "note-box" }, "A hidden part of the exercise: it stays as it is.")); return; }
  // name
  const nm = el("input", { value: b.name || "" });
  nm.addEventListener("change", () => { b.name = nm.value.trim() || b.name; changed(); });
  box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Name"), nm));
  // material
  const mb = el("div", { class: "matcard" },
    el("span", { class: "sw", style: `background:${S.colors[b.material] || "#ddd"}` }),
    el("div", { class: "grow" }, el("div", { class: "t" }, b.material || "(no material)"),
      el("div", { class: "s" }, matLine(b.material))),
    el("button", { onclick: () => openPicker((name) => { b.material = name; changed(); }) }, "Change"));
  box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Material"), mb));
  if (b.use) {   // a copy of a component
    box.append(el("p", { class: "lead" }, `A copy of the component “${b.use}” (Advanced shows the components).`));
    b.position ||= [0, 0, 0];
    const pos = el("div");
    XYZ.forEach((a, k) => pos.append(sliderRow(`${a}`, b.position[k], -15, 15, 0.05, (v) => { b.position[k] = v; changed(); })));
    box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Position (center)"), pos));
    box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Size"),
      sliderRow("scale", b.scale ?? 1, 0.1, 5, 0.05, (v) => { b.scale = v; changed(); }, "×")));
    return;
  }
  const sh = (b.shape ||= { type: "box", size: [4, 4, 2] });
  const known = S.info.shapes.find((s) => s.type === sh.type);
  // shape icons
  const icons = el("div", { class: "shapes" });
  for (const s of S.info.shapes) {
    icons.append(el("button", { class: "shape" + (s.type === sh.type ? " on" : ""), title: s.label, onclick: () => {
      if (s.type === sh.type) return;
      const keep = { position: sh.position, rotation: sh.rotation };
      for (const k of Object.keys(sh)) delete sh[k];
      sh.type = s.type;
      for (const f of s.fields) sh[f.key] = clone(f.default);
      if (keep.position) sh.position = keep.position;
      if (keep.rotation) sh.rotation = keep.rotation;
      changed(); renderPart();
    } }, el("span", { html: `<svg viewBox="0 0 38 30">${ICONS[s.type] || ""}</svg>` }), s.label));
  }
  box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Shape"), icons));
  if (!known) {
    box.append(el("p", { class: "note-box" }, `This part is a ${shapeName(sh.type)}: change its shape in Advanced → the recipe as text (or choose a simple shape above).`));
  } else {
    const dims = el("div");
    for (const f of known.fields) {
      const step = f.key === "seed" ? 1 : (f.max <= 1 ? 0.01 : 0.05);
      const unit = ["seed", "wobble", "exponent"].includes(f.key) ? "" : "mm";
      if (f.n === 3) {
        if (!Array.isArray(sh[f.key])) sh[f.key] = clone(f.default);
        const parts = f.label.split(/,\s*/);
        const names = parts.length === 3 ? parts.map((x, k) => k === 0 ? x.split(" ").pop() : x) : XYZ;
        const base = parts.length === 3 ? parts[0].split(" ").slice(0, -1).join(" ") : f.label;
        names.forEach((a, k) => dims.append(sliderRow(`${k === 0 ? base + " " : ""}${a}`.trim(), sh[f.key][k], f.min, f.max, step,
          (v) => { sh[f.key][k] = v; changed(); }, unit)));
      } else {
        if (sh[f.key] === undefined) sh[f.key] = f.default;
        dims.append(sliderRow(f.label, sh[f.key], f.min, f.max, step, (v) => { sh[f.key] = v; changed(); }, unit));
      }
    }
    box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Size"), dims));
  }
  sh.position ||= [0, 0, 0];
  const pos = el("div");
  XYZ.forEach((a, k) => pos.append(sliderRow(`${a}${a === "z" ? " (along the beam)" : a === "y" ? " (up)" : ""}`,
    sh.position[k], -15, 15, 0.05, (v) => { sh.position[k] = v; changed(); })));
  box.append(el("div", { class: "field" }, el("div", { class: "lbl" }, "Position of its center"), pos));
  const rot = sh.rotation || {};
  const turn = el("details", { class: "sub-box" }, el("summary", {}, "Turn it"));
  if (rot.axis || rot.matrix) {
    turn.append(el("p", { class: "small" }, "Turned about an axis or by a matrix: change it in Advanced → the recipe as text."));
  } else {
    const e = rot.euler_deg || [0, 0, 0];
    [["about z (the beam)", 0], ["about x", 1], ["about y (vertical)", 2]].forEach(([lab, k]) =>
      turn.append(sliderRow(lab, e[k], -180, 180, 1, (v) => { sh.rotation = { euler_deg: [...(sh.rotation?.euler_deg || [0, 0, 0])] }; sh.rotation.euler_deg[k] = v; changed(); }, "°")));
    if (e.some((x) => x)) turn.open = true;
  }
  box.append(turn);
}
function matLine(name) {
  const s = S.sig[name];
  return s ? `Σ = ${s.sigma[1].toFixed(3)} cm⁻¹ at 3 Å (${s.sigma[0].toFixed(3)} at 1.8 Å) · ${s.how}` : "";
}

// ------------------------------------------------------------------ material picker
let pickCb = null;
function openPicker(cb) { pickCb = cb; $("picker").classList.remove("hidden"); $("mat-search").value = ""; renderPicker(); $("mat-search").focus(); }
function closePicker() { $("picker").classList.add("hidden"); pickCb = null; }
function renderPicker() {
  const q = $("mat-search").value.trim().toLowerCase();
  const list = $("mat-list"); list.innerHTML = "";
  const groups = [["In this sample", Object.keys(S.recipe.materials || {}).filter((k) => !k.startsWith("holder: ")).map((k) => ({
    label: k, own: true, sigma: S.sig[k] ? S.sig[k].sigma[1] : null, color: S.colors[k], formula: S.sig[k]?.label !== k ? S.sig[k]?.label : "" }))]];
  for (const [g, items] of Object.entries(S.info.materials)) groups.push([g, items.map((it) => ({ ...it, sigma: S.catSig[it.label] }))]);
  for (const [g, items] of groups) {
    const shown = items.filter((it) => !q || (it.label + " " + (it.formula || "")).toLowerCase().includes(q));
    if (!shown.length) continue;
    const cards = el("div", { class: "mcards" });
    for (const it of shown) {
      cards.append(el("button", { class: "mcard", onclick: () => pick(it) },
        el("span", { class: "sw", style: `background:${it.color || "#E7EBF0"}` }),
        el("span", {}, el("div", { class: "t" }, it.label),
          el("div", { class: "s" }, [it.formula, it.sigma != null ? `Σ(3 Å) = ${Number(it.sigma).toFixed(3)} cm⁻¹` : ""].filter(Boolean).join(" · ")))));
    }
    list.append(el("div", { class: "mgroup" }, el("h3", {}, g), cards));
  }
  list.append(el("p", { class: "small" }, "A mixture, a formula and density, or a material calibrated on a measured Σ: Advanced → materials (text)."));
}
function pick(it) {
  let name = it.label;
  if (!it.own) {
    name = it.label.replace(/\s*\(.*\)\s*$/, "").trim();
    const mats = S.recipe.materials ||= {};
    if (mats[name] && JSON.stringify(mats[name]) !== JSON.stringify(it.spec)) { let k = 2; while (mats[`${name} ${k}`]) k++; name = `${name} ${k}`; }
    if (!mats[name]) mats[name] = clone(it.spec);
  }
  const cb = pickCb; closePicker(); if (cb) cb(name);
}

// ------------------------------------------------------------------ advanced
async function renderAdvanced() {
  const adv = $("adv"); adv.innerHTML = "";
  if (!S.recipe.bodies.length) return;
  const b = body(S.sel);
  const sec = (title, text, obj, apply, rows = 8) => {
    const ta = el("textarea", { class: "code", rows });
    api("yaml", { obj }).then((d) => { ta.value = d.text; }).catch(() => {});
    const msg = el("div", { class: "msg" });
    const btn = el("button", { onclick: async () => {
      try { const d = await api("parse", { text: ta.value }); apply(d.obj); msg.className = "msg ok"; msg.textContent = "Applied."; changed(); renderAll(); }
      catch (e) { msg.className = "msg err"; msg.textContent = e.message; }
    } }, "Apply");
    return el("div", { class: "adv-sec" }, el("h2", {}, title), el("p", { class: "lead" }, text), ta, el("div", { class: "toolbar" }, btn), msg);
  };
  if (!b.sealed) {
    adv.append(sec(`Grains placed at random in “${b.name}”`,
      "Populations of grains (count or volume fraction, sizes, shapes, clusters), Voronoi polycrystals, pores. One item per population; hidden ones are not shown. Example: - {material: copper, fraction: 0.02, size_mm: [0.1, 0.3], grain: {type: blob, wobble: 0.1}}",
      (b.fill || []).filter((f) => !f.sealed), (v) => { const sealed = (b.fill || []).filter((f) => f.sealed); b.fill = [...(Array.isArray(v) ? v : []), ...sealed]; if (!b.fill.length) delete b.fill; }, 6));
  }
  adv.append(sec("Materials (text)", "Each material: a crystal of NCrystal (ncrystal), minerals by volume (minerals), a formula and density, a mixture of the other materials (mix), or a base calibrated on a measured Σ (calibrate); density_factor below 1 for pores; source: where the numbers come from.",
    Object.fromEntries(Object.entries(S.recipe.materials || {}).filter(([k]) => !k.startsWith("holder: "))),
    (v) => { if (v && typeof v === "object" && !Array.isArray(v)) S.recipe.materials = v; }, 8));
  adv.append(sec("Components", "Bodies with their own parts, used several times (by a part with use: <name>, or by a population of grains).",
    S.recipe.components || {}, (v) => { if (v && typeof v === "object" && !Array.isArray(v)) S.recipe.components = v; }, 6));
  adv.append(sec("The whole recipe (text)", "Everything: every shape (also combined shapes: union, difference, intersection; meshes), rotation, material, grains, the sources and assumptions. Hidden parts stay hidden (sealed).",
    S.recipe, (v) => { if (v && Array.isArray(v.bodies)) { S.recipe = v; S.sel = [0]; } }, 14));
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
    const pic = s.kind === "scratch" ? el("div", { class: "ph" }, "+") : s.kind === "draft" ? el("div", { class: "ph" }, "✎")
      : el("img", { loading: "lazy", src: thumbUrl(s), alt: "" });
    g.append(el("button", { class: "card" + (S.start && S.start.kind === s.kind && S.start.ref === s.ref ? " on" : ""),
      title: s.title, onclick: () => startFrom(s) }, pic, el("div", { class: "t" }, s.title), el("div", { class: "w" }, s.what)));
  }
}
async function startFrom(s) {
  if (S.recipe && S.dirty && !confirm("Start again from this one? Your changes are lost (unless saved).")) return;
  try {
    status("Loading…");
    let d;
    if (s.kind === "draft") d = loadDraft();
    else d = await api("load", { kind: s.kind, ref: s.ref });
    S.recipe = d.recipe; S.holder = d.holder || { type: "none" }; S.sel = [0]; S.start = s;
    if (d.title !== undefined) $("f-title").value = d.title || "";
    if (d.description !== undefined) $("f-desc").value = d.description || "";
    if (d.name) $("f-name").value = d.name;
    $("start-now").textContent = `· now: ${s.title}`;
    $("gallery-box").open = false;
    S.dirty = false; S.grains = true; $("grains").checked = true;
    renderAll(); refreshViews(true); refreshSigmas();
  } catch (e) { status(e.message, true); }
}

// ------------------------------------------------------------------ holder (step 2)
const HOLDER_PICS = {
  none: '<rect x="62" y="16" width="36" height="44" fill="#9AA6B6" stroke="#142033"/>',
  pin: '<rect x="62" y="10" width="36" height="40" fill="#9AA6B6" stroke="#142033"/><rect x="75" y="50" width="10" height="30" fill="#D5DCE5" stroke="#142033"/>',
  base: '<rect x="62" y="16" width="36" height="40" fill="#9AA6B6" stroke="#142033"/><rect x="50" y="56" width="60" height="12" fill="#D5DCE5" stroke="#142033"/>',
  cell: '<rect x="54" y="8" width="52" height="66" rx="3" fill="#E8F1F8" stroke="#5B87A8" stroke-width="3"/><rect x="62" y="18" width="36" height="48" fill="#9AA6B6" stroke="#142033"/>',
  can: '<path d="M52 14v58a28 7 0 0 0 56 0V14" fill="#EEF0F4" stroke="#6B7689" stroke-width="2"/><ellipse cx="80" cy="14" rx="28" ry="7" fill="#F7F8FA" stroke="#6B7689" stroke-width="2"/><rect x="66" y="22" width="28" height="44" fill="#9AA6B6" stroke="#142033"/>',
  grips: '<rect x="20" y="22" width="36" height="40" fill="#B9C1CC" stroke="#142033"/><rect x="104" y="22" width="36" height="40" fill="#B9C1CC" stroke="#142033"/><rect x="56" y="32" width="48" height="20" fill="#9AA6B6" stroke="#142033"/>',
  custom: '<rect x="62" y="16" width="36" height="40" fill="#9AA6B6" stroke="#142033"/><path d="M58 56h44l-6 18H64z" fill="#D5DCE5" stroke="#142033"/>',
};
function renderHolders() {
  const g = $("holders"); g.innerHTML = "";
  const cat = { ...S.info.holders };
  if (S.holder.type === "custom") cat.custom = { title: "As it came", text: S.holder.title || "the holder of this sample, unchanged", params: [] };
  for (const [k, h] of Object.entries(cat)) {
    g.append(el("button", { class: "holder" + (S.holder.type === k ? " on" : ""), onclick: () => {
      if (k === S.holder.type) return;
      if (k === "custom") return;
      const nh = { type: k };
      if (h.material) nh.material = h.material;
      for (const p of h.params) nh[p.key] = p.default;
      S.holder = nh; renderHolders(); changed();
    } }, el("span", { html: `<svg viewBox="0 0 160 84"><path d="M0 42h160" stroke="#F0C9B5" stroke-dasharray="4 4"/>${HOLDER_PICS[k] || ""}</svg>` }),
      el("div", { class: "t" }, h.title), el("div", { class: "x" }, h.text)));
  }
  const box = $("holder-params"); box.innerHTML = "";
  const h = S.info.holders[S.holder.type];
  $("holder-params-box").classList.toggle("hidden", !h || !h.params.length);
  if (!h) return;
  for (const p of h.params) box.append(sliderRow(p.label, S.holder[p.key] ?? p.default, p.min, p.max, 0.05, (v) => { S.holder[p.key] = v; changed(); }));
  if (h.material) {
    const sel = el("select", {}, ...["aluminium", "steel", "titanium", "vanadium", "copper", "fused silica"].map((m) =>
      el("option", { value: m, ...(m === (S.holder.material || h.material) ? { selected: "" } : {}) }, m)));
    sel.addEventListener("change", () => { S.holder.material = sel.value; changed(); });
    box.append(el("div", { class: "slider" }, el("span", { class: "nm" }, "material"), sel));
  }
}

// ------------------------------------------------------------------ check and save (step 3)
async function renderChecks() {
  $("checks").innerHTML = '<li class="wait">Checking (building the whole sample)…</li>';
  try {
    const d = await api("check", { recipe: S.recipe, holder: S.holder });
    $("checks").innerHTML = "";
    for (const it of d.items) $("checks").append(el("li", { class: it.status }, el("span", { class: "dot" }),
      el("div", {}, el("div", { class: "t" }, it.title), el("div", { class: "x" }, it.text))));
  } catch (e) { $("checks").innerHTML = `<li class="red"><span class="dot"></span><div><div class="t">Not possible to build it</div><div class="x">${esc(e.message)}</div></div></li>`; }
  renderSigTable();
}
function renderSigTable() {
  const rows = Object.values(S.sig);
  $("sigmas").innerHTML = rows.length ? `<table class="sig"><tr><th>material</th><th>Σ at 1.8 Å</th><th>Σ at 3 Å</th><th>from</th></tr>${rows.map((r) =>
    `<tr><td><span class="sw" style="background:${r.color}"></span>${esc(r.label)}</td><td class="n">${r.sigma[0].toFixed(3)}</td><td class="n">${r.sigma[1].toFixed(3)}</td><td class="small">${esc(r.how)}</td></tr>`).join("")}</table>` : "";
}
async function save() {
  const m = $("save-msg"); m.className = "msg"; m.textContent = "Saving (building the whole sample)…";
  S.proposal = $("f-proposal").value.trim();
  try {
    const d = await api("save", { recipe: S.recipe, holder: S.holder, name: $("f-name").value.trim(), title: $("f-title").value.trim(),
      description: $("f-desc").value.trim() });
    m.className = "msg ok"; m.innerHTML = `Saved with proposal ${esc(S.proposal)}. In NICOS: <code>${esc(d.nicos)}</code>`;
    S.dirty = false; clearDraft();
  } catch (e) { m.className = "msg err"; m.textContent = "Not saved: " + e.message; }
}
async function saveModel() {
  const m = $("model-msg"); m.className = "msg"; m.textContent = "Saving…";
  try {
    await api("save_model", { recipe: S.recipe, holder: S.holder, model: $("f-model").value.trim(), title: $("f-title").value.trim(),
      description: $("f-desc").value.trim() });
    m.className = "msg ok"; m.textContent = "Saved as a model: anyone can now start from it (Start from).";
    S.info.starts = (await api("info", {})).starts; renderGallery();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
}
async function download() {
  const d = await api("yaml", { obj: { title: $("f-title").value, description: $("f-desc").value, holder: S.holder, recipe: S.recipe } });
  const a = el("a", { href: URL.createObjectURL(new Blob([d.text], { type: "text/yaml" })), download: `${$("f-name").value.trim() || "sample"}_recipe.yml` });
  document.body.append(a); a.click(); a.remove();
}

// ------------------------------------------------------------------ steps
function go(n) {
  S.step = n;
  for (const k of [1, 2, 3]) $(`step${k}`).classList.toggle("hidden", k !== n);
  document.querySelectorAll("#steps button").forEach((b) => b.classList.toggle("on", Number(b.dataset.step) === n));
  $("panel").scrollTop = 0;
  if (n === 2) renderHolders();
  if (n === 3) { if (!$("f-proposal").value) $("f-proposal").value = S.proposal; renderChecks(); }
}

// ------------------------------------------------------------------ 3D view
const V = { renderer: null, scene: null, camera: null, controls: null, group: null, box: null, bounds: null, fitted: false };
function init3d() {
  const host = $("three");
  V.renderer = new THREE.WebGLRenderer({ antialias: true });
  V.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  V.renderer.setClearColor(0xffffff);
  host.append(V.renderer.domElement);
  V.scene = new THREE.Scene();
  V.camera = new THREE.PerspectiveCamera(32, 1, 0.1, 2000);
  V.controls = new OrbitControls(V.camera, V.renderer.domElement);
  V.controls.enableDamping = true;
  V.scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.1));
  const d1 = new THREE.DirectionalLight(0xffffff, 1.4); d1.position.set(30, 50, -20); V.scene.add(d1);
  const d2 = new THREE.DirectionalLight(0xffffff, 0.5); d2.position.set(-30, -10, 40); V.scene.add(d2);
  V.group = new THREE.Group(); V.scene.add(V.group);
  V.helpers = new THREE.Group(); V.scene.add(V.helpers);
  const resize = () => { const w = host.clientWidth, h = host.clientHeight; if (!w || !h) return; V.renderer.setSize(w, h); V.camera.aspect = w / h; V.camera.updateProjectionMatrix(); };
  new ResizeObserver(resize).observe(host); resize();
  const loop = () => { V.controls.update(); V.renderer.render(V.scene, V.camera); requestAnimationFrame(loop); };
  loop();
}
function b64(s, T) { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new T(u.buffer); }
function textSprite(text, color, height) {
  const c = document.createElement("canvas"); c.width = 512; c.height = 64;
  const g = c.getContext("2d"); g.font = "600 30px Segoe UI, sans-serif"; g.fillStyle = color; g.fillText(text, 4, 42);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false }));
  s.center.set(0, 0.5); s.scale.set(8 * height, height, 1); return s;
}
function drawMeshes(d) {
  V.group.clear(); V.helpers.clear();
  const solid = d.meshes.filter((m) => !m.holder);
  const main = solid.length > 1 ? solid.reduce((a, b) => (b.share > a.share ? b : a)) : null;
  for (const m of d.meshes) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(b64(m.vertices, Float32Array), 3));
    g.setIndex(new THREE.BufferAttribute(b64(m.faces, Uint32Array), 1));
    g.computeVertexNormals();
    const see = m.holder || (main && m.material === main.material);
    const mat = new THREE.MeshStandardMaterial({ color: m.color, roughness: 0.75, metalness: 0.05, side: THREE.DoubleSide,
      transparent: see, opacity: m.holder ? 0.35 : see ? 0.25 : 1, depthWrite: !see });
    const mesh = new THREE.Mesh(g, mat); mesh.renderOrder = see ? 2 : 1;
    V.group.add(mesh);
  }
  // the field of view (14 mm square, across the beam) and the beam
  const [lo, hi] = d.sample_bounds; const h = S.info.field_mm / 2;
  const zf = lo[2] - 2;
  const sq = new THREE.BufferGeometry().setFromPoints([[-h, -h], [h, -h], [h, h], [-h, h], [-h, -h]].map(([x, y]) => new THREE.Vector3(x, y, zf)));
  const line = new THREE.Line(sq, new THREE.LineDashedMaterial({ color: 0x2A7D6F, dashSize: 0.8, gapSize: 0.5 }));
  line.computeLineDistances(); V.helpers.add(line);
  const L = 12, z0 = zf - L;
  V.helpers.add(new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, z0), L - 0.5, 0xB4562B, 1.6, 0.9));
  const nb = textSprite("neutrons", "#B4562B", 1.2); nb.position.set(0.3, 1.2, zf - 4); V.helpers.add(nb);
  V.bounds = d.bounds;
  if (!V.fitted) fit(d);
  highlight();
  // legend
  const leg = $("legend"); leg.innerHTML = "";
  for (const m of d.meshes) leg.append(el("span", {}, el("span", { class: "sw", style: `background:${m.color};${m.holder ? "opacity:.6" : ""}` }), (m.holder ? "holder: " : "") + (m.label || m.material).replace(/^holder: /, "")));
  leg.append(el("span", {}, el("span", { class: "sw", style: "border:1.5px dashed #2A7D6F;background:none" }), "field of view of the camera (14 mm)"));
}
function fit(d) {
  const [lo, hi] = d.sample_bounds;
  const c = new THREE.Vector3((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2);
  const r = Math.max(8, Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]));
  V.controls.target.copy(c);
  V.camera.position.set(c.x + 1.6 * r, c.y + 0.9 * r, c.z - 1.9 * r);
  V.camera.near = r / 100; V.camera.far = r * 100; V.camera.updateProjectionMatrix();
  V.fitted = true;
}
function highlight() {
  if (V.box) { V.helpers.remove(V.box); V.box = null; }
  if (!V.bounds || !S.recipe || !S.recipe.bodies.length) return;
  const b = V.bounds[S.sel.join(".")];
  if (!b) return;
  V.box = new THREE.Box3Helper(new THREE.Box3(new THREE.Vector3(...b[0]), new THREE.Vector3(...b[1])), 0xE0A000);
  V.helpers.add(V.box);
}

// ------------------------------------------------------------------ refreshing
let timer = null, beamTimer = null, busy = 0;
function changed() {
  S.dirty = true; saveDraft(); renderTree(); clearTimeout(timer);
  timer = setTimeout(() => { refreshViews(); refreshSigmas(); }, 650);
}
async function refreshViews(first = false) {
  const my = ++S.previewKey;
  busy++; status(S.grains ? "Building the sample…" : "Building (without the grains)…");
  const t0 = performance.now();
  try {
    const d = await api("preview", { recipe: S.recipe, holder: S.holder, grains: S.grains, n: 56 });
    if (my !== S.previewKey) return;
    if (first) V.fitted = false;
    drawMeshes(d);
    const sec = (performance.now() - t0) / 1000;
    let note = d.problems.length ? `To fix: ${d.problems.slice(0, 2).join("; ")}` : "";
    if (S.grains && sec > 8 && d.n_fills) {
      S.grains = false; $("grains").checked = false;
      note = `A large sample (${sec.toFixed(0)} s to place its grains): the grains are left out while you edit (tick “grains” to see them).`;
    }
    status(note, d.problems.length > 0);
  } catch (e) { if (my === S.previewKey) status(e.message, true); }
  finally { busy--; }
  if (!$("beam").classList.contains("hidden")) refreshBeam();
}
async function refreshBeam() {
  clearTimeout(beamTimer);
  beamTimer = setTimeout(async () => {
    $("radio").style.opacity = 0.4;
    try { const d = await api("radiograph", { recipe: S.recipe, holder: S.holder, lam: S.lam }); $("radio").src = "data:image/png;base64," + d.png; }
    catch (e) { status(e.message, true); }
    $("radio").style.opacity = 1;
  }, 250);
}
async function refreshSigmas() {
  try {
    const d = await api("sigmas", { recipe: S.recipe, holder: S.holder, lams: [1.8, 3.0] });
    S.sig = Object.fromEntries(d.rows.map((r) => [r.material, r]));
    S.colors = Object.fromEntries(d.rows.map((r) => [r.material, r.color]));
    renderTree(); if (S.step === 1) renderPart(); if (S.step === 3) renderSigTable();
  } catch (e) { /* shown by the preview */ }
}

// ------------------------------------------------------------------ draft (this computer only)
const DRAFT = `twin-builder:${INSTR}:${S.proposal || "none"}`;
function saveDraft() { try { localStorage.setItem(DRAFT, JSON.stringify({ recipe: S.recipe, holder: S.holder, title: $("f-title").value, description: $("f-desc").value, name: $("f-name").value, when: new Date().toLocaleString() })); } catch { /* no storage */ } }
function loadDraft() { try { return JSON.parse(localStorage.getItem(DRAFT) || "null"); } catch { return null; } }
function clearDraft() { try { localStorage.removeItem(DRAFT); } catch { /* no storage */ } }

function renderAll() { renderTree(); renderPart(); if ($("advanced").open) renderAdvanced(); if (S.step === 2) renderHolders(); }

// ------------------------------------------------------------------ start
async function main() {
  $("where").textContent = `${INSTR.toUpperCase()}${S.proposal ? ` · proposal ${S.proposal}` : ""}`;
  init3d();
  document.querySelectorAll("#steps button").forEach((b) => b.addEventListener("click", () => go(Number(b.dataset.step))));
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(Number(b.dataset.go))));
  for (const [id, a] of [["add-inside", "inside"], ["add-beside", "beside"], ["duplicate", "duplicate"], ["up", "up"], ["down", "down"], ["remove", "remove"]])
    $(id).addEventListener("click", () => treeAction(a));
  $("gallery-search").addEventListener("input", renderGallery);
  $("mat-search").addEventListener("input", renderPicker);
  $("picker-close").addEventListener("click", closePicker);
  $("picker").addEventListener("click", (e) => { if (e.target.id === "picker") closePicker(); });
  $("advanced").addEventListener("toggle", () => { if ($("advanced").open) renderAdvanced(); });
  $("save").addEventListener("click", save);
  $("save-model").addEventListener("click", saveModel);
  $("download").addEventListener("click", download);
  $("grains").addEventListener("change", () => { S.grains = $("grains").checked; refreshViews(); });
  $("reset-view").addEventListener("click", () => { V.fitted = false; refreshViews(true); });
  document.querySelectorAll(".vtabs [data-view]").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".vtabs [data-view]").forEach((x) => x.classList.toggle("on", x === b));
    const beam = b.dataset.view === "beam";
    $("beam").classList.toggle("hidden", !beam); $("three").classList.toggle("hidden", !beam ? false : true);
    if (beam) refreshBeam();
  }));
  $("lam").addEventListener("input", () => { S.lam = Number($("lam").value); $("lam-v").textContent = `${S.lam.toFixed(1)} Å`; refreshBeam(); });
  ["f-title", "f-desc", "f-name"].forEach((id) => $(id).addEventListener("change", saveDraft));
  $("f-name").value = Q.get("name") || ""; $("f-title").value = Q.get("title") || "";
  $("f-proposal").value = S.proposal;
  status("Opening…");
  try { S.info = await api("info", { start: Q.get("start") || "" }); }
  catch (e) { status("The builder cannot reach the server: " + e.message, true); return; }
  api("catalogue_sigmas", { lam: 3.0 }).then((d) => { S.catSig = d.sigma; }).catch(() => {});
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
