"""The results of a class served by a Kubernetes cluster (kubernetes.yaml, e.g. UCloud): copies the folder web_results of
the server (on the volume of the cluster) to this computer, then makes the table of the class (web_results.py).

    python container/class_results.py                           # -> ~/McStas_runs/twin/class_results/results.csv
    python container/class_results.py --kubeconfig <file> --out <folder>

Needs kubectl and the kubeconfig of the cluster (default: ~/.kube/ucloud-access-twins.yaml). The cluster must be on:
the copy reads the files of the running server. Each run copies everything again (the newest state).
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def kubectl():
    exe = shutil.which("kubectl")
    if exe:
        return exe
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")   # winget install
    for root, _, files in os.walk(base):
        if "kubectl.exe" in files:
            return os.path.join(root, "kubectl.exe")
    sys.exit("kubectl not found (Windows: winget install Kubernetes.kubectl)")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--kubeconfig", default=os.path.join(os.path.expanduser("~"), ".kube", "ucloud-access-twins.yaml"))
    p.add_argument("--out", default=os.path.join(os.path.expanduser("~"), "McStas_runs", "twin", "class_results"))
    a = p.parse_args()
    k = [kubectl(), "--kubeconfig", a.kubeconfig]
    r = subprocess.run(k + ["get", "pod", "-l", "app=twin-web", "-o", "jsonpath={.items[0].metadata.name}",
                            "--request-timeout=30s"], capture_output=True, text=True)
    pod = r.stdout.strip()
    if r.returncode or not pod:
        sys.exit("The cluster does not answer: " + (r.stderr.strip() or "no server pod") +
                 "\nIs it on? (UCloud: Power on both machines, wait until the cluster is ready, then run this again.)")
    os.makedirs(a.out, exist_ok=True)
    shutil.rmtree(os.path.join(a.out, "web_results"), ignore_errors=True)
    # a relative destination: on Windows "C:\..." would be read as a pod named C
    subprocess.run(k + ["cp", f"{pod}:/data/twin/web_results", "web_results", "-c", "twin"], cwd=a.out, check=True)
    n = sum(len(f) for _, _, f in os.walk(os.path.join(a.out, "web_results")))
    print(f"{n} files copied from {pod} to {a.out}")
    subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "web_results.py"),
                    os.path.join(a.out, "web_results"), os.path.join(a.out, "results.xlsx")], check=True)


if __name__ == "__main__":
    main()
