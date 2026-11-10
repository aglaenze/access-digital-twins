"""The twin's user office: the teaching proposals of an instrument, in the proposal cache that NICOS reads at ESS.

At ESS, NICOS does not ask the user office (YUOS) itself: a service writes the proposals of the instrument to a cache
file (yuos_query.YuosServer.update_cache), and EssExperiment reads it (yuos_query.YuosCacheClient). In the Experiment
tab, "Query" lists the proposals of the logged-in user (by facility user id), or all of them for an admin, and fills
in the number, title, users and samples. The proposal number and title can then no longer be typed in.

Here the proposals are those of nicos/proposals/<instrument>.yml (written by the teachers), their samples those of the
twin's sample library (<instrument>/samples/*.yml), their proposer the teacher, and their users the teaching accounts
of the NICOS daemon (student, guest). start_nicos.py --proposals writes the cache; without it, any proposal number
can be typed in.

    write_cache(instrument, path)    writes the cache file (format of yuos_query); returns the number of proposals
    check(path)                      reads it back with yuos_query (NICOS environment)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORGANIZATION = "ACCESS course"
PROPOSER = ["ACCESS", "teacher", "teacher", ORGANIZATION]   # the proposer: required by yuos_query
ACCOUNTS = ("student", "guest")          # logins of the NICOS daemon (nicos_twin/<instrument>/setups/special/daemon.py)
FORMULAS = {"silica": "SiO2", "gold": "Au"}


def proposals(instrument):
    path = os.path.join(HERE, "proposals", f"{instrument}.yml")
    if not os.path.isfile(path):
        return []
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _formula(spec):
    """Chemical formula of a sample of the library (as asked by the user office's sample form)."""
    if spec.get("formula"):
        return str(spec["formula"])
    if spec.get("volumes"):                                    # ODIN: the NCrystal materials (Fe_sg229_... -> Fe)
        return ", ".join(dict.fromkeys(v["material"].split("_")[0] for v in spec["volumes"]))
    if spec.get("empty"):
        return ""
    parts = [FORMULAS.get(p.get("particle", spec.get("particle")), p.get("particle", spec.get("particle")))
             for p in spec.get("populations", [spec]) if p.get("particle", spec.get("particle"))]
    d2o = (spec.get("solvent") or {}).get("d2o_fraction", 1.0)
    solvent = "D2O" if d2o == 1 else "H2O" if d2o == 0 else f"H2O/D2O ({100 * d2o:.0f} % D2O)"
    return " in ".join([", ".join(dict.fromkeys(parts)), solvent]) if parts else solvent


def write_cache(instrument, path):
    """Writes the proposal cache of the instrument, in the format of yuos_query (utils.serialise_proposals_to_json:
    what EssExperiment reads). Returns the number of proposals written."""
    import json
    sys.path.insert(0, os.path.dirname(HERE))
    import sample_library
    library = sample_library.load(instrument)
    out = {}
    for k, p in enumerate(proposals(instrument)):
        pid = str(p["id"])
        assert pid.isdigit(), f"proposal number {pid!r}: digits only"
        samples = [dict(name=library[s].get("name", s), formula=_formula(library[s]), number=1,
                        mass_or_volume=[0, ""], density=[0, "g/cm*3"]) for s in p.get("samples", [])]
        users = [["ACCESS", login, login, ORGANIZATION] for login in ACCOUNTS]    # first, last, fed id, organization
        out[pid] = dict(id=pid, title=p["title"], proposer=PROPOSER, users=users, db_id=k + 1, samples=samples)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4)
    return len(out)


def check(path):
    """Reads the cache back with yuos_query (the NICOS environment): [(id, title, samples, fed ids)] of the proposals
    of the account "student"."""
    from yuos_query.yuos_client import YuosCacheClient
    client = YuosCacheClient.create(path)
    client.update_cache()
    return [(p.id, p.title, [(s.name, s.formula) for s in p.samples], [u[2] for u in p.users])
            for p in client.proposals_for_user("student")], len(client.all_proposals())


if __name__ == "__main__":
    # python user_office.py <instrument> <path>   writes the cache;   python user_office.py --check <path>   reads it
    if sys.argv[1] == "--check":
        mine, n = check(sys.argv[2])
        print(chr(10).join(map(str, mine)))
        assert mine and len(mine) == n
    else:
        print(write_cache(sys.argv[1], sys.argv[2]), "proposals written to", sys.argv[2])
