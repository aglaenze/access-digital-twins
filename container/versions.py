"""The fixed versions of the software of the image, and the latest ones published (container/UPDATES.md).

    python container/versions.py                      # table: fixed version, latest version, where it is fixed
    python container/versions.py --apply build-args   # writes the latest versions of the "followed" software into
                                                      # environment-mcstas.yml, and the build arguments of the
                                                      # Containerfile into the file build-args (KEY=value lines)
    python container/versions.py --markdown           # the table in Markdown (summary of the GitHub run)

Followed (tested with their latest version every week by .github/workflows/latest.yml): the ESS reduction software of
the twins (scipp, scippneutron, scippnexus, tof, plopp, essreduce, essimaging, esssans, sciline), sasmodels, esslivedata,
NICOS, just-bin-it. Reported only (changing them is a decision, not a routine update): the McStas models of ODIN and
LoKI (the precomputed upstream parts depend on them), McStas and NCrystal (the physics), the ESS file-writer (its image
is built by filewriter.yml from a chosen commit), Kafka.
Only reads public package indexes and git servers (no account needed).
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "environment-mcstas.yml")
CONTAINERFILE = os.path.join(HERE, "Containerfile")
FILEWRITER_WF = os.path.join(os.path.dirname(HERE), ".github", "workflows", "filewriter.yml")

CONDA = ("scipp", "scippneutron", "scippnexus", "tof", "plopp")          # conda-forge, in environment-mcstas.yml
PIP = ("essreduce", "essimaging", "esssans", "sciline", "sasmodels")    # PyPI, pip section of environment-mcstas.yml
REPORT_CONDA = ("mcstas", "ncrystal", "mcpl")


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "access-digital-twins versions.py"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def pypi_latest(name):
    return json.loads(_get(f"https://pypi.org/pypi/{name}/json"))["info"]["version"]


def conda_latest(name):
    return json.loads(_get(f"https://api.anaconda.org/package/conda-forge/{name}"))["latest_version"]


def github_release(repo):
    return json.loads(_get(f"https://api.github.com/repos/{repo}/releases/latest"))["tag_name"]


def git_head(url, branch=None):
    ref = f"refs/heads/{branch}" if branch else "HEAD"
    out = subprocess.run(["git", "ls-remote", url, ref], capture_output=True, text=True, timeout=60).stdout.split()
    return out[0] if out else "?"


def fixed():
    """{name: (fixed version, where)} read from the files of this folder."""
    env, cf = open(ENV).read(), open(CONTAINERFILE).read()
    out = {}
    for n in CONDA + REPORT_CONDA:
        m = re.search(rf"^\s+- {n}=([^\s#]+)", env, re.M)
        out[n] = (m.group(1) if m else "?", "environment-mcstas.yml")
    for n in PIP:
        m = re.search(rf"^\s+- {n}==([^\s#]+)", env, re.M)
        out[n] = (m.group(1) if m else "?", "environment-mcstas.yml (pip)")
    for arg in ("LIVEDATA_VERSION", "NICOS_COMMIT", "JBI_COMMIT", "ODIN_COMMIT", "LOKI_COMMIT", "KAFKA_VERSION"):
        m = re.search(rf"^ARG {arg}=(\S+)", cf, re.M)
        out[arg] = (m.group(1) if m else "?", "Containerfile")
    m = re.search(r"kafka-to-nexus (\w+)", cf)
    out["kafka-to-nexus"] = (m.group(1) if m else "?", "Containerfile (image of filewriter.yml)")
    return out


LATEST = {
    **{n: (lambda n=n: conda_latest(n)) for n in CONDA + REPORT_CONDA},
    **{n: (lambda n=n: pypi_latest(n)) for n in PIP},
    "LIVEDATA_VERSION": lambda: github_release("scipp/esslivedata"),
    "NICOS_COMMIT": lambda: git_head("https://github.com/mlz-ictrl/nicos.git", "master"),
    "JBI_COMMIT": lambda: git_head("https://github.com/ess-dmsc/just-bin-it.git"),
    "ODIN_COMMIT": lambda: git_head("https://git.esss.dk/dmsc-instrumentmodels/odin.git"),
    "LOKI_COMMIT": lambda: git_head("https://git.esss.dk/dmsc-instrumentmodels/LOKI.git"),
    # ECDC's GitLab needs an account; its GitHub mirror is public (it may lag behind)
    "kafka-to-nexus": lambda: git_head("https://github.com/ess-dmsc/kafka-to-nexus.git"),
    "KAFKA_VERSION": lambda: "(see kafka.apache.org)",
}
FOLLOWED = set(CONDA + PIP) | {"LIVEDATA_VERSION", "NICOS_COMMIT", "JBI_COMMIT"}


def _unknown(v):
    return str(v).startswith(("?", "("))


def _same(a, b):
    a, b = str(a), str(b)
    return a == b or (len(a) >= 7 and len(b) >= 7 and (a.startswith(b) or b.startswith(a)))


def table():
    rows = []
    for name, (ver, where) in fixed().items():
        try:
            new = LATEST[name]()
        except Exception as e:                          # noqa: BLE001  (a server down: reported, not fatal)
            new = f"? ({type(e).__name__})"
        rows.append((name, ver, new, where, "followed" if name in FOLLOWED else "reported only", _same(ver, new)))
    return rows


def apply(rows, build_args):
    """Writes the latest versions of the followed software into environment-mcstas.yml and build-args."""
    env = open(ENV).read()
    args = []
    for name, ver, new, where, kind, same in rows:
        if kind != "followed" or same or _unknown(new):
            continue
        if name in CONDA:
            env = re.sub(rf"^(\s+- {name}=)[^\s#]+", rf"\g<1>{new}", env, flags=re.M)
        elif name in PIP:
            env = re.sub(rf"^(\s+- {name}==)[^\s#]+", rf"\g<1>{new}", env, flags=re.M)
        else:
            args.append(f"{name}={new}")
            if name == "NICOS_COMMIT":
                args.append(f"NICOS_VERSION=latest+g{new[:7]}")
    open(ENV, "w").write(env)
    with open(build_args, "w") as f:
        f.write("\n".join(args) + ("\n" if args else ""))
    return args


def markdown(rows):
    lines = ["| Software | Fixed | Latest | Where | |", "|---|---|---|---|---|"]
    for name, ver, new, where, kind, same in rows:
        mark = "same" if same else "unknown" if _unknown(new) else (
            "**newer**" if kind == "followed" else "newer (reported only)")
        lines.append(f"| {name} | `{ver[:12]}` | `{str(new)[:12]}` | {where} | {mark} |")
    return "\n".join(lines)


def main():
    rows = table()
    if "--markdown" in sys.argv:
        print(markdown(rows))
    else:
        for name, ver, new, where, kind, same in rows:
            state = "same" if same else "?" if _unknown(new) else "NEWER"
            print(f"{name:18} {ver[:14]:16} {str(new)[:14]:16} {state:6} {kind:14} {where}")
    if "--apply" in sys.argv:
        path = sys.argv[sys.argv.index("--apply") + 1]
        args = apply(rows, path)
        print(f"latest versions written: environment-mcstas.yml; build arguments ({path}): {args}")


if __name__ == "__main__":
    main()
