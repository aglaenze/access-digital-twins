"""Downloads the precomputed McStas upstream parts of the twins (GitHub release of this repository) into
<TWIN_RUN_ROOT>/odin/front/ and <TWIN_RUN_ROOT>/loki/front/.

    python container/fetch_fronts.py                 # all the upstream parts used by the twins (~1.6 GB)
    python container/fetch_fronts.py wfm_delta0.10_N2e+08 natural_delta0.30_N2e+08
    python container/fetch_fronts.py --instrument loki      # only those of one instrument (odin, loki)
    python container/fetch_fronts.py --list

The upstream parts (source -> guides -> choppers -> guide exit, or sample aperture for LoKI) take from minutes to an
hour to compute (odin_mcstas.front, loki_mcstas.front), so they are computed once and published as release assets (tag RELEASE). An upstream part that
is already complete on disk is not downloaded again. The repository is public: no token is needed (a GitHub token
in GITHUB_TOKEN or GH_TOKEN is used if present: higher API rate limit, or a private fork).
Variables: TWIN_ASSETS_REPO (default aglaenze/access-digital-twins), TWIN_FRONTS_RELEASE (default fronts-v1).
"""
import hashlib
import json
import os
import sys
import tarfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
for _instr in ("odin", "loki"):
    sys.path.insert(0, os.path.join(HERE, "..", _instr))
import odin_paths  # noqa: E402
import loki_paths  # noqa: E402

REPO = os.environ.get("TWIN_ASSETS_REPO", "aglaenze/access-digital-twins")
RELEASE = os.environ.get("TWIN_FRONTS_RELEASE", "fronts-v1")
FRONT_DIRS = {"odin": f"{odin_paths.RUN_ROOT}/front", "loki": f"{loki_paths.RUN_ROOT}/front"}


def wanted(instruments=("odin", "loki")):
    """{folder name: (instrument, release asset)} of the upstream parts used by the twins (odin_virtual.FRONTS,
    virtual_loki.CONFIGS). ODIN assets are front_<name>.tar, LoKI assets loki_front_<name>.tar ('+' removed)."""
    out = {}
    if "odin" in instruments:
        import odin_mcstas as tw
        import odin_virtual as ov
        for (mode, _), (delta, n) in ov.FRONTS.items():
            name = os.path.basename(tw.front_folder(mode, n, delta))
            out[name] = ("odin", f"front_{name.replace('+', '')}.tar")
    if "loki" in instruments:
        import loki_mcstas as lm
        import virtual_loki as vl
        for c in vl.CONFIGS.values():
            name = os.path.basename(lm.front_folder(**c["front"]))
            out[name] = ("loki", f"loki_front_{name.replace('+', '')}.tar")
    return out


def complete(folder):
    f = os.path.join(folder, "mccode.sim")
    return os.path.isfile(f) and "begin data" in open(f, errors="ignore").read()


def _request(url, accept):
    h = {"Accept": accept, "User-Agent": "access-digital-twins"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60)


def assets():
    with _request(f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE}", "application/vnd.github+json") as r:
        return {a["name"]: a["url"] for a in json.load(r)["assets"]}


def download(url, dest):
    sha = hashlib.sha256()
    with _request(url, "application/octet-stream") as r, open(dest + ".part", "wb") as f:
        size, done = int(r.headers.get("Content-Length", 0)), 0
        while chunk := r.read(1 << 22):
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if size:
                print(f"\r  {done / 1e6:7.0f} / {size / 1e6:.0f} MB", end="", flush=True)
    print()
    os.replace(dest + ".part", dest)
    return sha.hexdigest()


def main():
    args = sys.argv[1:]
    instruments = ("odin", "loki")
    if "--instrument" in args:
        i = args.index("--instrument")
        instruments = (args[i + 1],)
        del args[i:i + 2]
    known = wanted(instruments)
    if args[:1] == ["--list"]:
        print("\n".join(f"{v[0]}: {n}" for n, v in known.items()))
        return
    for n in args:
        if n not in known:
            raise SystemExit(f"unknown upstream part {n}; known: {list(known)}")
    names = args or list(known)
    todo = [n for n in names if not complete(os.path.join(FRONT_DIRS[known[n][0]], n))]
    if not todo:
        print("upstream parts already present in " + ", ".join(FRONT_DIRS[i] for i in instruments))
        return
    available = assets()
    sums = {}
    if "SHA256SUMS" in available:
        tmp = os.path.join(FRONT_DIRS[known[todo[0]][0]], "SHA256SUMS")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        download(available["SHA256SUMS"], tmp)
        sums = {l.split()[1]: l.split()[0] for l in open(tmp) if l.strip()}
    for n in todo:
        instr, asset = known[n]
        FRONT_DIR = FRONT_DIRS[instr]
        os.makedirs(FRONT_DIR, exist_ok=True)
        if asset not in available:
            raise SystemExit(f"{asset} is not in release {RELEASE} of {REPO}")
        print(f"downloading {asset} ...")
        tar = os.path.join(FRONT_DIR, asset)
        digest = download(available[asset], tar)
        if asset in sums and sums[asset] != digest:
            os.remove(tar)
            raise SystemExit(f"checksum mismatch for {asset}")
        with tarfile.open(tar) as t:
            t.extractall(FRONT_DIR, filter="data")
        os.remove(tar)
        if not complete(os.path.join(FRONT_DIR, n)):
            raise SystemExit(f"{n}: incomplete after extraction")
        print(f"  -> {FRONT_DIR}/{n}")


if __name__ == "__main__":
    main()
