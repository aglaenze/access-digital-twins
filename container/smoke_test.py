"""Smoke test of the container (run by GitHub Actions after each build): `bash container/start.sh test`.

1. tools: mcrun, mpiexec, h5repack in the twin environment; NICOS importable in its own environment;
2. a short measurement with the virtual ODIN (WFM δ = 0.10 m, the smallest upstream part, downloaded from the
   release; hybrid mode): dark, open beam, iron plate; reduction with essimaging; transmission of the plate compared
   with NCrystal (Beer–Lambert, 5 mm of α-iron) between 2.2 and 3.8 Å (below the first Bragg edge, 4.05 Å);
3. NICOS services started headless with the launcher (twin server, cache, poller, daemon), then stopped.
Exit code 0 if everything works.
"""
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TWIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TWIN, "odin"))
FRONT = "wfm_delta0.10_N2e+08"
ok = True


def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    ok &= bool(cond)


def step(title):
    print(f"\n=== {title}", flush=True)


step("tools")
for exe in ("mcrun", "mpiexec", "h5repack"):
    check(shutil.which(exe), f"{exe} found: {shutil.which(exe)}")
nicos_py = os.path.join(os.environ.get("CONDA_ROOT", "/opt/conda"), "envs", "nicos", "bin", "python")
r = subprocess.run([nicos_py, "-c", "import nicos, nicospyctl, numpy; print(nicos.__version__, numpy.__version__)"],
                   cwd=os.environ.get("NICOS_ROOT", "."), capture_output=True, text=True)
check(r.returncode == 0, f"NICOS environment: {r.stdout.strip() or r.stderr.strip()[-300:]}")

step("upstream part")
r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_fronts.py"), FRONT])
check(r.returncode == 0, f"upstream part {FRONT} downloaded")

step("measurement with the virtual ODIN (hybrid mode)")
t0 = time.time()
import numpy as np                                    # noqa: E402
import NCrystal as NC                                 # noqa: E402
import odin_virtual as ov                             # noqa: E402
import odin_reduction as red                          # noqa: E402
odin = ov.VirtualOdin(session="ci_smoke_test", mpi=int(os.environ.get("TWIN_MPI", "4")))
odin.move(choppers="wfm", wfm_delta=0.10)
dark = odin.count(5, title="dark")
odin.move(shutter="open", stage_x=0.5)
ob = odin.count(20, title="open beam")
odin.move(stage_x=0.0)
smp = odin.count(20, title="iron plate")
print(f"three counts in {time.time() - t0:.0f} s (including the first McStas compilation and open-beam simulation)")
out = red.reduce(smp, ob, dark=dark)
spec = out["spectrum"]
edges = spec.coords["wavelength"].values
lam = 0.5 * (edges[1:] + edges[:-1])
band = (lam > 2.2) & (lam < 3.8)
T = spec.values[band]
m = NC.load("Fe_sg229_Iron-alpha.ncmat")
sigma = (m.scatter.xsect(wl=lam[band]) + m.absorption.xsect(wl=lam[band])) * m.info.getNumberDensity()   # cm^-1
T_nc = np.exp(-sigma * 0.5)
dev = np.mean(T) - np.mean(T_nc)
print(f"transmission 2.2–3.8 Å: measured {np.mean(T):.3f}, NCrystal {np.mean(T_nc):.3f}")
check(abs(dev) < 0.03, f"iron plate transmission agrees with NCrystal (difference {dev:+.3f})")

step("NICOS services (headless)")
p = subprocess.Popen([sys.executable, os.path.join(TWIN, "nicos", "start_odin_nicos.py"), "--no-gui", "--background",
                      "--session", "ci_nicos"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
ready, lines, t0 = False, [], time.time()
while time.time() - t0 < 300:
    line = p.stdout.readline()
    if not line:
        break
    lines.append(line.rstrip())
    print("  " + line.rstrip(), flush=True)
    if "Services ready" in line:
        ready = True
        break
check(ready, "NICOS cache, poller and daemon started with the twin server")
p.send_signal(signal.SIGINT)
try:
    p.wait(60)
except subprocess.TimeoutExpired:
    p.kill()
logs = os.path.join(os.environ.get("TWIN_RUN_ROOT", ""), "nicos")
if not ready and os.path.isdir(logs):
    for f in sorted(os.listdir(logs)):
        if f.endswith(".log"):
            print(f"--- {f}\n" + open(os.path.join(logs, f), errors="replace").read()[-3000:])

print("\nALL PASSED" if ok else "\nSOME CHECKS FAILED")
sys.exit(0 if ok else 1)
