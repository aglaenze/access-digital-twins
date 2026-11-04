"""Games of the ODIN digital twin: missions with a beamtime budget, troubleshooting, logbook review.

* Mission "unknown metals": three plates of unknown metals (codes sample_A, sample_B, sample_C), drawn among
  Fe, V, Nb (body-centered cubic) and Cu, Ni, Al (face-centered cubic). The student measures their Bragg-edge spectra
  within a beamtime budget and submits, for each sample, the metal and its lattice parameter a. Score: 100 points per
  correct metal, +50 if a is within 0.5 %, + 1 point per 5 s of beamtime left (only with at least one correct metal).
  Why it works (edges 2d computed with NCrystal): the first edges of Fe (4.055 Å) and Ni (4.069 Å), or of Nb
  (4.667 Å) and Al (4.676 Å), are almost at the same place, but the second edges differ (2.868 / 3.524 Å;
  3.300 / 4.050 Å); V has almost no Bragg edge (incoherent scatterer) and an attenuation that grows with λ; Al is very
  transparent (T ≈ 0.94 for 5 mm): its edges are a few % high and need statistics -> beamtime choices matter.
* Troubleshooting: the instrument has a hidden fault (odin_virtual.FAULTS); the student finds it from the data.
* review_log(): automatic check of good experimental practice from the session log, with badges.

The secrets are stored in the session folder (mission.json), base64-encoded so that they are not read by accident.
"""
import base64
import json
import os

import numpy as np

import odin_virtual as ov

METALS = {   # name: (NCrystal file, structure, lattice parameter a [Å] from the NCrystal file)
    "Fe": ("Fe_sg229_Iron-alpha.ncmat", "bcc", 2.8676), "V": ("V_sg229.ncmat", "bcc", 3.0240),
    "Nb": ("Nb_sg229.ncmat", "bcc", 3.3004), "Cu": ("Cu_sg225.ncmat", "fcc", 3.6150),
    "Ni": ("Ni_sg225.ncmat", "fcc", 3.5239), "Al": ("Al_sg225.ncmat", "fcc", 4.0496),
}
CODES = ("sample_A", "sample_B", "sample_C")


def _encode(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def _decode(txt):
    return json.loads(base64.b64decode(txt.encode()).decode())


def register_samples(secret):
    """Adds the mystery plates (10 × 10 × 5 mm, centered) to the samples of the virtual ODIN."""
    for code, metal in secret.items():
        ov.SAMPLES[code] = dict(volumes=[(METALS[metal][0], (0.0, 0.0, 0.0), (0.010, 0.010, 0.005))],
                                name=code.replace("_", " "), formula="?")


class MetalMission:
    """Mission "unknown metals" for one session (one student or group)."""

    def __init__(self, session, budget_s=300.0, seed=None):
        self.session = session
        self.folder = f"{ov.RUN_ROOT}/{session}"
        os.makedirs(self.folder, exist_ok=True)
        self.file = os.path.join(self.folder, "mission.json")
        if os.path.isfile(self.file):                       # resume the mission of this session
            d = json.load(open(self.file, encoding="utf-8"))
        else:
            rng = np.random.default_rng(seed)
            metals = rng.choice(sorted(METALS), size=len(CODES), replace=False)
            d = dict(kind="unknown_metals", budget_s=budget_s, secret=_encode(dict(zip(CODES, map(str, metals)))),
                     submissions=[])
            json.dump(d, open(self.file, "w", encoding="utf-8"), indent=1)
        self.data = d
        register_samples(_decode(d["secret"]))

    def instrument(self, **kw):
        """The virtual ODIN of this mission (beamtime budget, mystery samples available)."""
        return ov.VirtualOdin(session=self.session, budget_s=self.data["budget_s"], **kw)

    def brief(self):
        rows = "\n".join(f"| {m} | {s} | {a:.4f} |" for m, (_, s, a) in METALS.items())
        return (f"Three plates ({', '.join(CODES)}), 10 × 10 × 5 mm, of unknown metals. Candidates:\n\n"
                f"| metal | structure | a (Å) |\n|---|---|---|\n{rows}\n\n"
                f"Beamtime budget: {self.data['budget_s']:.0f} s of counting with the shutter open (dark runs are "
                f"free). For each sample, submit the metal and the lattice parameter a you measured.")

    def submit(self, answers, beam_used):
        """answers: {code: (metal, a in Å or None)}. Returns (score, table of results)."""
        secret = _decode(self.data["secret"])
        rows, score = [], 0
        for code in CODES:
            metal, a = answers.get(code, (None, None))
            truth = secret[code]
            ok = metal == truth
            a_true = METALS[truth][2]
            close = ok and a is not None and abs(a - a_true) / a_true < 0.005
            pts = (100 if ok else 0) + (50 if close else 0)
            score += pts
            rows.append(dict(sample=code, answer=metal, a=a, correct=ok, a_within_0_5_percent=close, points=pts))
        left = max(self.data["budget_s"] - beam_used, 0.0)
        # Beamtime bonus only with at least one correct metal (no points for answering at random without measuring)
        bonus = int(left // 5) if any(r["correct"] for r in rows) else 0
        score += bonus
        self.data["submissions"].append(dict(rows=rows, beamtime_bonus=bonus, score=score))
        json.dump(self.data, open(self.file, "w", encoding="utf-8"), indent=1)
        return score, rows, bonus

    def reveal(self):
        """For the teacher: the true metals."""
        return _decode(self.data["secret"])


class Troubleshooting:
    """A hidden instrument fault to diagnose (one per session)."""

    def __init__(self, session, seed=None):
        self.session = session
        self.folder = f"{ov.RUN_ROOT}/{session}"
        os.makedirs(self.folder, exist_ok=True)
        self.file = os.path.join(self.folder, "fault.json")
        if os.path.isfile(self.file):
            self.data = json.load(open(self.file, encoding="utf-8"))
        else:
            fault = str(np.random.default_rng(seed).choice(sorted(ov.FAULTS)))
            self.data = dict(secret=_encode(fault), guesses=[])
            json.dump(self.data, open(self.file, "w", encoding="utf-8"), indent=1)

    def instrument(self, **kw):
        return ov.VirtualOdin(session=self.session, faults=(_decode(self.data["secret"]),), **kw)

    def guess(self, fault):
        right = fault == _decode(self.data["secret"])
        self.data["guesses"].append(dict(guess=fault, right=right))
        json.dump(self.data, open(self.file, "w", encoding="utf-8"), indent=1)
        return right

    def reveal(self):
        return _decode(self.data["secret"])


# --------------------------------------------------------------------------- logbook review
def _config(state):
    return (state["choppers"], state["wfm_delta"] if state["choppers"] == "wfm" else None, state["pinhole"],
            state["diffuser"])


def review_log(log_file, budget_s=None):
    """Checks good experimental practice from a session log. Returns (list of (ok, message), list of badges)."""
    counts = [json.loads(l)["details"] for l in open(log_file, encoding="utf-8") if '"action": "count"' in l]
    checks, badges = [], []
    if not counts:
        return [(False, "No measurement yet.")], badges
    darks = [c for c in counts if c["state"]["shutter"] == "closed"]
    beams = [c for c in counts if c["state"]["shutter"] == "open"]
    ob = [c for c in beams if abs(c["state"]["stage_x"]) > 0.02]
    smp = [c for c in beams if abs(c["state"]["stage_x"]) <= 0.02]
    checks.append((bool(darks), "Dark run measured (detector background)." if darks else
                   "No dark run: the detector background (gamma rays, fast neutrons) cannot be subtracted."))
    ob_cfg = {_config(c["state"]) for c in ob}
    missing = sorted({_config(c["state"]) for c in smp} - ob_cfg)
    checks.append((not missing, "Every sample measurement has an open beam with the same choppers, pinhole and "
                   "diffuser." if not missing else
                   f"Sample measured without an open beam in the same configuration: {missing}."))
    if smp and ob:
        t_s = np.mean([c["t"] for c in smp]); t_o = np.mean([c["t"] for c in ob])
        checks.append((t_o >= 0.5 * t_s, f"Open beam counted long enough ({t_o:.0f} s vs {t_s:.0f} s on the samples)."
                       if t_o >= 0.5 * t_s else f"Open beam much shorter than the sample runs ({t_o:.0f} s vs "
                       f"{t_s:.0f} s): its noise will dominate the transmission."))
    odd = [c["file"] for c in darks if any(w in (c["title"] or "").lower() for w in ("open", "sample", "plate", "beam"))]
    checks.append((not odd, "Shutter state consistent with the titles." if not odd else
                   f"Measured with the shutter closed although the title suggests a beam measurement: {odd}."))
    titled = sum(1 for c in counts if c["title"]) / len(counts)
    checks.append((titled == 1, "Every run has a title." if titled == 1 else
                   f"{(1 - titled):.0%} of the runs have no title: hard to find them back in the logbook."))
    if all(ok for ok, _ in checks):
        badges.append("Careful experimenter")
    if titled == 1:
        badges.append("Logbook keeper")
    if budget_s:
        used = sum(c["t"] for c in beams)
        if used <= 0.7 * budget_s:
            badges.append("Efficient (≥ 30 % of the beamtime left)")
    if any(c["state"]["choppers"] != "wfm" for c in beams) and any(c["state"]["choppers"] == "wfm" for c in beams):
        badges.append("Explorer (tried several chopper modes)")
    return checks, badges
