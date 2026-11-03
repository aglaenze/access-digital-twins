"""3D view of the neutrons flying through ODIN (McStas mcdisplay, WebGL viewer in the browser).

    python show_3d.py                       # WFM mode, view generated once, then served and opened in the browser
    python show_3d.py --mode natural -n 1500
    python show_3d.py --mode wfm --regenerate --inspect guide_exit   # only neutrons reaching the guide exit
    python show_3d.py --no-browser          # generate only

The view shows the official McStas model of ODIN from the ESS source to the guide exit (60 m: bispectral extraction,
guides, chopper cascade); each line is one simulated neutron, stopped where it is absorbed (e.g. by a chopper disc).
Generated with McStas's `mcdisplay` (WebGL); the instrument file is written by odin_mcstas.build_front.
Views are stored in McStas_runs/twin/odin/display/<mode>/view (a few MB).
"""
import argparse
import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading
import webbrowser

import odin_paths
import odin_mcstas as tw

MODES = sorted(tw.MODES)


def generate(mode, n, inspect=None):
    folder = f"{odin_paths.RUN_ROOT}/display/{mode}"
    os.makedirs(folder, exist_ok=True)
    lmin, lmax = tw.FRONT_LAM[mode]
    model = tw.build_front(mode, folder, lam_min=lmin, lam_max=lmax)   # McStas needs a path without spaces
    model.write_full_instrument()
    instr = model.name + ".instr"
    shutil.rmtree(os.path.join(folder, "view"), ignore_errors=True)
    mcdisplay = os.path.join(os.path.dirname(sys.executable), "share", "mcstas", "tools", "Python", "mcdisplay",
                             "webgl", "mcdisplay.py")
    cmd = [sys.executable, mcdisplay, instr, "--nobrowse", "--default", "-n", str(n), "--dirname", "view",
           "--timeout", "1"] + (["--inspect", inspect] if inspect else [])
    print(f"Generating the 3D view ({n} neutrons, {mode} mode)...", flush=True)
    r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True)
    view = os.path.join(folder, "view")
    if not os.path.isfile(os.path.join(view, "particles.json")):
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise RuntimeError("mcdisplay failed")
    return view


def serve(view, port=8790, browser=True):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=view)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"3D view served at {url}  (Ctrl+C to stop)", flush=True)
    if browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--mode", default="wfm", choices=MODES)
    a.add_argument("-n", type=int, default=1500, help="number of neutrons drawn")
    a.add_argument("--inspect", help="show only neutrons reaching this component (e.g. guide_exit)")
    a.add_argument("--regenerate", action="store_true")
    a.add_argument("--no-browser", action="store_true", help="generate the view only")
    a.add_argument("--port", type=int, default=8790)
    o = a.parse_args()
    view = f"{odin_paths.RUN_ROOT}/display/{o.mode}/view"
    if o.regenerate or o.inspect or not os.path.isfile(os.path.join(view, "particles.json")):
        view = generate(o.mode, o.n, o.inspect)
    if o.no_browser:
        print("view ready:", view)
        return
    serve(view, o.port)


if __name__ == "__main__":
    main()
