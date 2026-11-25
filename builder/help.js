// The help of the sample builder (ODIN): "How to use" (a sheet with worked examples and pictures of the page,
// builder/help/*.webp, made by a headless browser on the real page) and "Tour" (the parts of the page shown one by
// one). The tour starts by itself at the first visit of this browser.
const $ = (id) => document.getElementById(id);
const IMG = (name, alt, wide = false) =>
  `<figure class="${wide ? "wide" : ""}"><img src="builder/static/help/${name}.webp" alt="${alt}" loading="lazy"><figcaption>${alt}</figcaption></figure>`;

const HOW = `
<section>
  <h3>What the sample builder is for</h3>
  <p>The twin needs a model of your sample: what it is made of and its exact shape. Here you make that model in three
    steps (the buttons at the top): <b>1. Sample</b>, the parts of the sample; <b>2. Holder</b>, what holds it in
    the beam; <b>3. Check &amp; save</b>. On the right you see it in 3D, or as the camera of ODIN would see it
    (<i>Beam's eye view</i>). What you save goes with your proposal: NICOS finds it on its sample changer.</p>
  ${IMG("overview", "The page: the steps at the top, the sample on the left, the views on the right.", true)}
</section>

<section>
  <h3>1. Start from something close</h3>
  <div class="row side"><div><p>Open <b>Start from</b> and pick the closest sample: it is faster to change a sample than to draw one. The
    starting points go from the simplest to the most complex: <b>simple shapes</b> (a plate, a step wedge),
    <b>several parts or grains</b> (a machined part with flaws, a polycrystal), <b>natural samples</b> (rocks and
    meteorites, with thousands of grains). The search box finds them by name (steel, rock...).</p></div>
  ${IMG("gallery", "The starting points, from the simplest to the most complex.")}</div>
</section>

<section>
  <h3>2. Worked example: a nickel ball inside an iron plate</h3>
  <p>The sample is a <b>tree of parts</b>: each part is one shape of one material, and a part <i>inside</i> another
    replaces its material there (an inclusion, a hole, a grain).</p>
  <ol>
    <li>Start from <b>Iron plate, 5 mm</b>. Its one part, <i>α-iron</i>, is selected.</li>
    <li>Click <b>+ Inside</b>: a small ball appears inside the plate.</li>
    <li>In <b>The selected part</b>, click <b>Change</b> next to its material, type <i>nickel</i> and pick it. Each
      card shows Σ, how strongly the material attenuates the beam.</li>
    <li>Set its <b>diameter</b> to 4 mm (the slider, or type the number).</li>
  </ol>
  <div class="row">${IMG("tree", "The parts: the nickel ball is inside the iron plate.")}${IMG("picker", "Choosing a material: type its name.")}</div>
  ${IMG("part", "The selected part: its name, material, shape, size and position (mm).")}
  <p>Now look at it. The <b>3D view</b> shows the ball inside the plate (drag to turn, wheel to zoom). The <b>Beam's
    eye view</b> shows what the camera would see: the ball is a darker disc, because nickel attenuates twice as
    much as iron at 3 Å (Σ = 2.23 against 1.11 per cm).</p>
  <div class="row">${IMG("insert_3d", "3D view: the ball (outlined) inside the plate, on its aluminium base.")}${IMG("beam", "Beam's eye view at 3 Å: the ball is darker than the iron around it.")}</div>
  <p class="tip"><b>Try it:</b> make the ball of <i>copper</i> instead. At 3 Å it disappears: copper and iron
    attenuate almost the same (Σ = 1.113 and 1.111 per cm). Move λ to 1.8 Å: it shows again, brighter than the iron
    (Σ = 0.93 against 1.20). A contrast depends on the wavelength: this is why ODIN measures many of them.</p>
</section>

<section>
  <h3>3. Grains placed at random</h3>
  <p>Many grains, pores or clasts are not drawn one by one: you describe a <b>population</b> and they are placed at
    random. Select the part that holds them, open <b>Grains placed at random in it</b> at the bottom of <i>The
    selected part</i>, and write one line per population, for example
    <code>- {material: copper, fraction: 0.02, size_mm: [0.1, 0.3]}</code> (2 % of the volume in copper grains of
    0.1 to 0.3 mm), then <b>Apply</b>. The example <i>Duplex stainless steel</i> fills its plate with 400 crystals,
    half ferrite and half austenite.</p>
  <div class="row">${IMG("grains_adv", "The grains of the selected part (the plate of the duplex steel), as text.")}${IMG("grains_3d", "The duplex steel: ferrite crystals (dark) and austenite crystals (light).")}</div>
  <p>A sample with many grains takes several seconds to build. Untick <b>grains</b> above the view while you change
    its shape: the view comes back at once; tick it again to see the grains.</p>
</section>

<section>
  <h3>4. The holder</h3>
  <p>Step <b>2. Holder</b>: choose what holds the sample (a pin, a base plate, a quartz cell, a vanadium can, tensile
    grips). It is placed for you from the size of the sample; only its size and material change. It is in the beam
    too, so the check of step 3 tells you if it shows in the images.</p>
  ${IMG("holder", "Step 2: the holders, then their size and material.")}
</section>

<section>
  <h3>5. Check and save</h3>
  <p>Step <b>3. Check &amp; save</b> gives traffic lights: <span class="dot g"></span> fine,
    <span class="dot a"></span> worth a look, <span class="dot r"></span> to fix before saving (a part outside its
    parent, two parts that overlap, a sample larger than the 14 mm field of view, a sample so thick that no neutron
    gets through). It also lists Σ of every material. Then give it a <b>short name</b> and <b>Save it with my
    proposal</b>. In NICOS: <code>move(sample_holder, 'your_short_name')</code>. <i>Save it as a model</i> lets
    anyone start from it.</p>
  ${IMG("check", "Step 3: the checks, Σ of the materials, and saving.")}
</section>

<section>
  <h3>Good to know</h3>
  <ul>
    <li><b>Hidden parts</b> (🔒) of an exercise stay hidden: what you have to find out is not shown, and is kept
      when you change the rest.</li>
    <li>Your work is kept in this browser as a <b>draft</b> until you save it: it is first in <i>Start from</i>.</li>
    <li>The 3D view is drawn on a grid, so the finest details look smoothed; the model itself, used by the twin,
      is exact.</li>
    <li><b>Advanced: the whole sample as text</b>, in three boxes that do not overlap: its materials, its components,
      and its parts with the rest (also what has no button: combined shapes, meshes, rotations about any axis, the
      sources of the numbers). Each box has its own <i>Apply</i>; <i>Copy the whole recipe</i> gives it as one text.</li>
  </ul>
</section>`;

// ------------------------------------------------------------------ "How to use"
function openHow() {
  let m = $("how");
  if (!m) {
    m = document.createElement("div");
    m.id = "how"; m.className = "modal hidden";
    m.innerHTML = `<div class="sheet how"><div class="sheet-head"><h2>How to use the sample builder</h2><span class="grow"></span>
      <button id="how-tour">Take the tour</button><button id="how-close">Close</button></div><div class="how-body">${HOW}</div></div>`;
    document.body.append(m);
    m.addEventListener("click", (e) => { if (e.target === m) m.classList.add("hidden"); });
    $("how-close").addEventListener("click", () => m.classList.add("hidden"));
    $("how-tour").addEventListener("click", () => { m.classList.add("hidden"); tour(); });
  }
  m.classList.remove("hidden");
}

// ------------------------------------------------------------------ "Tour"
const STOPS = [
  ["#steps", "The steps", "Make your sample: 1. the sample, 2. what holds it, 3. check and save. You can go back and forth."],
  ["#gallery-box", "Start from", "Start from the closest example or sample, from the simplest to the most complex, then change it."],
  [".box:has(#tree)", "The parts", "Your sample is a tree of parts, each one shape of one material. Click a part to change it; + Inside puts a new part inside it (an inclusion, a hole)."],
  ["#part-box", "The selected part", "Its material (Change: the materials with their Σ), its shape (the icons), its size and position in mm; at the bottom, the grains placed at random in it."],
  ["#advanced", "Advanced", "The whole sample as text, in three boxes that do not overlap: the materials, the components, the parts and the rest (also what has no button)."],
  [".vtabs", "The views", "The 3D view, and the Beam's eye view: what the camera of ODIN would see, at the wavelength you choose."],
  ["#grains-box", "Grains", "A sample with many grains is slow to build: untick this while you change its shape."],
  ["#help-btn", "Help", "How to use: a worked example with pictures. You can take this tour again from there."],
];
let at = -1;
function tour() { at = 0; show(); }
function endTour() {
  at = -1;
  for (const id of ["tour-hole", "tour-tip"]) { const e = $(id); if (e) e.remove(); }
  try { localStorage.setItem("twin-builder-toured", "1"); } catch (e) { /* private window */ }
}
function show() {
  const [sel, title, text] = STOPS[at];
  const t = document.querySelector(sel);
  if (!t) { if (at < STOPS.length - 1) { at++; show(); } else endTour(); return; }
  if (sel === "#gallery-box") t.open = true;
  t.scrollIntoView({ block: "nearest" });
  const r = t.getBoundingClientRect();
  let hole = $("tour-hole"), tip = $("tour-tip");
  if (!hole) {
    hole = document.createElement("div"); hole.id = "tour-hole"; document.body.append(hole);
    tip = document.createElement("div"); tip.id = "tour-tip"; document.body.append(tip);
  }
  Object.assign(hole.style, { left: `${r.left - 6}px`, top: `${r.top - 6}px`, width: `${r.width + 12}px`, height: `${r.height + 12}px` });
  tip.innerHTML = `<div class="k">${at + 1} / ${STOPS.length}</div><h4>${title}</h4><p>${text}</p>
    <div class="tb"><button id="tour-end">Close</button><span class="grow"></span>
    ${at ? '<button id="tour-back">Back</button>' : ""}<button class="primary" id="tour-next">${at < STOPS.length - 1 ? "Next" : "Done"}</button></div>`;
  const below = r.bottom + 200 < innerHeight;
  const left = Math.min(Math.max(12, r.left), innerWidth - 352);
  Object.assign(tip.style, { left: `${left}px`, top: below ? `${r.bottom + 14}px` : "", bottom: below ? "" : `${Math.max(12, innerHeight - r.top + 14)}px` });
  $("tour-end").onclick = endTour;
  $("tour-next").onclick = () => { if (at < STOPS.length - 1) { at++; show(); } else endTour(); };
  if ($("tour-back")) $("tour-back").onclick = () => { at--; show(); };
}
addEventListener("resize", () => { if (at >= 0) show(); });
addEventListener("keydown", (e) => { if (e.key === "Escape") { endTour(); const m = $("how"); if (m) m.classList.add("hidden"); } });

// ------------------------------------------------------------------ the buttons, and the first visit
const bar = document.createElement("div");
bar.className = "helpbar";
bar.innerHTML = '<button id="tour-btn" title="The parts of the page, one by one">Tour</button>'
  + '<button id="help-btn" class="primary" title="A worked example with pictures">? How to use</button>';
document.querySelector("header.top").append(bar);
$("help-btn").addEventListener("click", openHow);
$("tour-btn").addEventListener("click", tour);
let seen = "1";
try { seen = localStorage.getItem("twin-builder-toured"); } catch (e) { /* private window: no tour by itself */ }
if (!seen) {               // the first visit: the tour, once the page has drawn its parts
  const wait = setInterval(() => {
    if (document.querySelector("#tree li")) { clearInterval(wait); setTimeout(tour, 600); }
  }, 300);
  setTimeout(() => clearInterval(wait), 30000);
}
