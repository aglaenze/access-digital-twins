"""The twin's user office: the proposals of the beamtimes, as NICOS finds them at ESS.

At ESS a proposal (number, title, team, samples) is written and accepted in the user office system before the
beamtime. NICOS does not ask the user office itself: a service writes the proposals of the instrument to a cache file
(yuos_query), and EssExperiment reads it. In the Experiment tab, "Find my proposal" lists the proposals of the logged-in user and
"Apply" fills in the number, title, users and samples; the files then go to <instrument>/<year>/<proposal>/raw.

The twin holds three kinds of proposals:
  * exercise   the proposal of the beamtime of an exercise (modes.beamtime.proposal of its exercise.yml): its samples
               are those of the exercise, the first one mounted by default on Apply (the student may mount another);
  * free       a free beamtime: a new proposal each time a student starts one (numbers from 900001), no sample given;
  * imported   a real proposal (e.g. an ESS one) typed in by a student to try it on the twin: its number, title and
               samples (name, formula); each sample is then built with the sample builder, under the same short name.
The free and imported proposals belong to the student who made them (the account of the app) and are stored in
TWIN_RUN_ROOT/user_office/proposals.json: one user office per installation of the twin (see FEUILLE_DE_ROUTE: a
central one, shared by a course, is a later step).

    exercise_proposals(instrument)                      the proposals of the exercises
    create(instrument, title, owner, ...)               a free beamtime or an imported proposal; returns it
    proposals(instrument=None, owner=None)              exercise proposals + those of the owner (all owners: None)
    get(proposal_id)                                    one proposal, or None
    write_cache(instrument, path, owner=None)           the cache file of NICOS (format of yuos_query)

    python user_office.py <instrument> <cache path> [--owner ID]    writes the cache (start_nicos.py)
    python user_office.py --check <cache path>                      reads it back with yuos_query (NICOS environment)
"""
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORGANIZATION = "ACCESS course"
TEACHER = ["ACCESS", "teacher", "teacher", ORGANIZATION]     # proposer of the exercises (required by yuos_query)
LOGIN = "student"            # login of the NICOS daemon in the app (nicos_twin/<instrument>/setups/special/daemon.py)
ACCOUNTS = ("student", "guest")                             # the NICOS logins that see the proposals of the exercises
FIRST_FREE = 900001
INSTRUMENTS = ("odin", "loki")


def run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def store_path():
    return os.path.join(run_root(), "user_office", "proposals.json")


def _load():
    try:
        with open(store_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"next": FIRST_FREE, "proposals": {}}


def _save(db):
    os.makedirs(os.path.dirname(store_path()), exist_ok=True)
    tmp = store_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=1)
    os.replace(tmp, store_path())


def signed_in():
    """The student signed in to the app (container/twin_app.py writes it), or ""."""
    if os.environ.get("TWIN_USER"):
        return os.environ["TWIN_USER"]
    try:
        with open(os.path.join(run_root(), "user_office", "signed_in"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def set_signed_in(uid):
    os.makedirs(os.path.join(run_root(), "user_office"), exist_ok=True)
    with open(os.path.join(run_root(), "user_office", "signed_in"), "w", encoding="utf-8") as f:
        f.write(uid)


def short_name(text):
    """A short sample name as the sample builder and NICOS want it (lowercase, digits, _)."""
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    if not s or not s[0].isalpha():
        s = "s_" + s
    return s[:30].rstrip("_") or "sample"


def exercise_proposals(instrument=None):
    """{id: proposal} of the beamtimes of the exercises (exercise.yml: modes.beamtime.proposal)."""
    import yaml
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, "*", "exercises", "*", "exercise.yml"))):
        with open(f, encoding="utf-8") as fh:
            e = yaml.safe_load(fh) or {}
        p = ((e.get("modes") or {}).get("beamtime") or {}).get("proposal")
        if not p or (instrument and e.get("instrument") != instrument):
            continue
        pid = str(p["id"])
        out[pid] = dict(id=pid, title=p["title"], instrument=e["instrument"], kind="exercise", owner="",
                        exercise=os.path.relpath(os.path.dirname(f), HERE).replace(os.sep, "/"),
                        samples=[dict(name=k) for k in (e.get("samples") or {})])
    return out


def proposals(instrument=None, owner=None):
    """The proposals a student sees: those of the exercises, then their own (newest first); owner None: everybody's."""
    own = [p for p in _load()["proposals"].values()
           if (instrument is None or p["instrument"] == instrument) and (owner is None or p["owner"] == owner)]
    return list(exercise_proposals(instrument).values()) + sorted(own, key=lambda p: p["created"], reverse=True)


def get(proposal_id):
    pid = str(proposal_id)
    return exercise_proposals().get(pid) or _load()["proposals"].get(pid)


def create(instrument, title, owner, kind="free", proposal_id=None, samples=(), owner_name=""):
    """A new free beamtime (a new number each time) or an imported proposal (its own number). samples (imported):
    [{"name": ..., "formula": ...}]. Returns the proposal."""
    if instrument not in INSTRUMENTS:
        raise ValueError(f"instrument: one of {INSTRUMENTS}")
    if kind not in ("free", "imported"):
        raise ValueError("kind: free or imported")
    title = (title or "").strip()
    if not title:
        raise ValueError("a title is needed (your question, or the title of the proposal)")
    db = _load()
    if kind == "free":
        pid = str(max(int(db.get("next", FIRST_FREE)), FIRST_FREE))
        while pid in db["proposals"] or pid in exercise_proposals():
            pid = str(int(pid) + 1)
        db["next"] = int(pid) + 1
        samples = []
    else:
        pid = str(proposal_id or "").strip()
        if not pid.isdigit():
            raise ValueError("proposal number: digits only (as at ESS)")
        if pid in exercise_proposals():
            raise ValueError(f"{pid} is the proposal of an exercise: give the number of your own proposal")
        if pid in db["proposals"] and db["proposals"][pid]["owner"] != owner:
            raise ValueError(f"proposal {pid} was already imported by another account on this computer")
        seen, clean = set(), []
        for s in samples or ():
            name = (s.get("name") or "").strip()
            if not name:
                continue
            key = short_name(name)
            while key in seen:
                key = key[:27] + f"_{len(seen)}"
            seen.add(key)
            clean.append(dict(name=key, title=name, formula=(s.get("formula") or "").strip()))
        samples = clean
    p = dict(id=pid, title=title, instrument=instrument, kind=kind, owner=owner, owner_name=owner_name,
             created=datetime.datetime.now().isoformat(timespec="seconds"), samples=samples)
    db["proposals"][pid] = p
    _save(db)
    return p


def _library():
    sys.path.insert(0, HERE)
    import sample_library
    return sample_library


def _formula(spec):
    """Chemical formula of a sample of the library (as asked by the sample form of the user office)."""
    if spec.get("formula"):
        return str(spec["formula"])
    if spec.get("volumes"):                                    # ODIN: the NCrystal materials (Fe_sg229_... -> Fe)
        return ", ".join(dict.fromkeys(v["material"].split("_")[0] for v in spec["volumes"]))
    if spec.get("empty"):
        return ""
    names = {"silica": "SiO2", "gold": "Au"}
    parts = [names.get(p.get("particle", spec.get("particle")), p.get("particle", spec.get("particle")))
             for p in spec.get("populations", [spec]) if p.get("particle", spec.get("particle"))]
    d2o = (spec.get("solvent") or {}).get("d2o_fraction", 1.0)
    solvent = "D2O" if d2o == 1 else "H2O" if d2o == 0 else f"H2O/D2O ({100 * d2o:.0f} % D2O)"
    return " in ".join([", ".join(dict.fromkeys(parts)), solvent]) if parts else solvent


def _person(owner, owner_name):
    first, _, last = (owner_name or owner or "student").partition(" ")
    return [first, last or first, LOGIN, ORGANIZATION]


def write_cache(instrument, path, owner=None):
    """Writes the proposal cache of NICOS for the instrument (format of yuos_query, utils.serialise_proposals_to_json:
    what EssExperiment reads): the proposals of the exercises and those of the student signed in (all students if
    nobody is). The sample names are the short names of the sample changer. Returns the number of proposals."""
    owner = signed_in() if owner is None else owner
    library = _library().load(instrument)
    out = {}
    for k, p in enumerate(proposals(instrument, owner or None)):
        samples = []
        for s in p["samples"]:
            spec = library.get(s["name"], {})
            samples.append(dict(name=s["name"], formula=s.get("formula") or _formula(spec), number=1,
                                mass_or_volume=[0, ""], density=[0, "g/cm*3"]))
        if p["kind"] == "exercise":
            users, proposer = [["ACCESS", login, login, ORGANIZATION] for login in ACCOUNTS], TEACHER
        else:
            # the student is the proposer (yuos_query lists a proposal twice if its proposer is also in its users)
            users, proposer = [], _person(p["owner"], p.get("owner_name"))
        out[p["id"]] = dict(id=p["id"], title=p["title"], proposer=proposer, users=users, db_id=k + 1, samples=samples)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4)
    return len(out)


def check(path):
    """Reads the cache back with yuos_query (the NICOS environment): ([(id, title, samples, fed ids)] of the account
    "student", number of proposals)."""
    from yuos_query.yuos_client import YuosCacheClient
    client = YuosCacheClient.create(path)
    client.update_cache()
    return [(p.id, p.title, [(s.name, s.formula) for s in p.samples], [u[2] for u in p.users])
            for p in client.proposals_for_user(LOGIN)], len(client.all_proposals())


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        mine, n = check(sys.argv[2])
        print(chr(10).join(map(str, mine)))
        assert mine and len(mine) == n
    else:
        who = sys.argv[sys.argv.index("--owner") + 1] if "--owner" in sys.argv else None
        print(write_cache(sys.argv[1], sys.argv[2], who), "proposals written to", sys.argv[2])
