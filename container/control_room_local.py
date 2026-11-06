"""The control room of the local app (twins installed by hand, no container: the app in local mode, app/README.md): the choice
of the instrument (given with --instrument by the button, otherwise control_room.py in a window), then NICOS with its window (nicos/start_nicos.py), stopped when the
NICOS window is closed. Started by the button "Open NICOS" of the catalogue, through container/open_nicos.ipynb.
Does nothing if NICOS is already running (its daemon answers on port 1301)."""
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NICOS_PY = os.environ.get("NICOS_PYTHON") or (
    os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "nicos", "python.exe") if os.name == "nt"
    else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(sys.executable))), "nicos", "bin", "python"))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def nicos_running():
    try:
        socket.create_connection(("localhost", 1301), timeout=1).close()
        return True
    except OSError:
        return False


def main():
    if nicos_running():
        return
    instr = sys.argv[sys.argv.index("--instrument") + 1] if "--instrument" in sys.argv else ""
    if not instr:      # (no instrument given: the choice in a window)
        env = dict(os.environ, CONTROL_ROOM_WINDOWED="1")
        instr = subprocess.run([NICOS_PY, os.path.join(HERE, "control_room.py")], capture_output=True, text=True,
                               env=env, creationflags=NO_WINDOW).stdout.strip()
    if instr:
        subprocess.run([sys.executable, os.path.join(ROOT, "nicos", "start_nicos.py"), "--instrument", instr,
                        "--until-gui-closes"], cwd=ROOT, creationflags=NO_WINDOW,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
