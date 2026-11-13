"""The online version for a class, served from a teacher's computer (Windows, Linux, macOS), with a free public
address (a Cloudflare "quick tunnel": no account, the address changes at each start).

    python web_class.py --password <class password>                  # in the "mcstas" environment
    python web_class.py --password <class password> --no-tunnel      # this computer / local network only

The same server as the container (container/start.sh web): Voila alone serves the start page and the guided pages
(no notebook, no code, no NICOS), behind the class password, each student anonymous (web_user.py). It prints the
address to give to the students; Ctrl+C stops everything. The computer must stay on (and awake) during the class.

The results of the class (pages opened, submissions: answers, times, comments) are kept on this computer, in
TWIN_RUN_ROOT/web_results (and also sent to a dataset of Hugging Face if HF_TOKEN and TWIN_RESULTS_REPO are set).
The table of the class:  python web_results.py <TWIN_RUN_ROOT>/web_results results.xlsx

cloudflared (the tunnel) is looked for on the PATH, then in ~/McStas_runs/tools/; download it from
https://github.com/cloudflare/cloudflared/releases (one executable).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def run_root():
    return os.environ.get("TWIN_RUN_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "twin"))


def cloudflared():
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    for name in ("cloudflared.exe", "cloudflared"):
        p = os.path.join(os.path.expanduser("~"), "McStas_runs", "tools", name)
        if os.path.isfile(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--password", required=True, help="the class password, asked once by the site")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--no-tunnel", action="store_true", help="no public address")
    ap.add_argument("--no-warmup", action="store_true", help="do not prepare the beams first")
    a = ap.parse_args()

    env = dict(os.environ, TWIN_WEB="1", PYTHONIOENCODING="utf-8", TWIN_HEAVY_SLOTS=os.environ.get("TWIN_HEAVY_SLOTS", "2"),
               JUPYTER_PATH=os.path.join(HERE, "container", "app_data"),
               PYTHONPATH=os.pathsep.join([os.path.join(HERE, "container")] +
                                          ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])))
    if not a.no_warmup:
        print("Preparing the beams (a few seconds, or minutes the very first time)...")
        subprocess.run([sys.executable, os.path.join(HERE, "container", "web_warmup.py")], env=env, check=False)
    voila = subprocess.Popen(
        [sys.executable, "-m", "voila", "--no-browser", "--Voila.ip=0.0.0.0", f"--port={a.port}", "--template=twin",
         f"--Voila.root_dir={HERE}", "--Voila.tornado_settings={'websocket_ping_interval': 30000}",
         "--MappingKernelManager.cull_idle_timeout=7200", "--MappingKernelManager.cull_interval=300",
         f"--token={a.password}", "--Voila.identity_provider_class=web_login.ClassPassword"],
        env=env, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace")
    log = open(os.path.join(run_root(), "web_class.log"), "a", encoding="utf-8")
    ready = threading.Event()

    def pump(proc, tag, pattern=None, found=None):
        for line in proc.stdout:
            log.write(f"{tag} {line}")
            log.flush()
            if "is running at" in line:
                ready.set()
            if pattern and found is not None and not found and re.search(pattern, line):
                found.append(re.search(pattern, line).group(0))

    threading.Thread(target=pump, args=(voila, "[voila]"), daemon=True).start()
    if not ready.wait(120):
        print("The server did not start: see", log.name)
        voila.terminate()
        return 1
    print(f"Server ready on this computer: http://localhost:{a.port}/  (password: {a.password})")
    tunnel, url = None, []
    if not a.no_tunnel:
        exe = cloudflared()
        if not exe:
            print("cloudflared not found: no public address (see the help of this script).")
        else:
            tunnel = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{a.port}"],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                      errors="replace")
            threading.Thread(target=pump, args=(tunnel, "[tunnel]", r"https://[a-z0-9-]+\.trycloudflare\.com", url),
                             daemon=True).start()
            for _ in range(60):
                if url:
                    break
                time.sleep(1)
            if url:
                print("\n" + "=" * 70 + f"\n  Address for the students:  {url[0]}\n  Class password:            "
                      f"{a.password}\n" + "=" * 70 + "\n")
            else:
                print("No public address from cloudflared after 60 s: see", log.name)
    print("Results of the class:", os.path.join(run_root(), "web_results"))
    print("Ctrl+C to stop.")
    try:
        while voila.poll() is None:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    for p in (tunnel, voila):
        if p is not None and p.poll() is None:
            p.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
