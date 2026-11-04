"""Runs NICOS commands on the daemon of a twin from the command line, and prints what the daemon says.

    python run_nicos_script.py -c "read(); move(shutter, 'open', stage_x, 500); count(t=5)"
    python run_nicos_script.py my_session.py
    python run_nicos_script.py --user student --password student my_session.py

Like the NICOS GUI, but without a window: useful in the container (no GUI there), on a server, or in tests.
Run it with the Python of the "nicos" environment (it imports the NICOS client library from NICOS_ROOT).
Exit code: 0 if the script ran to the end, 1 if NICOS reported an error.
"""
import argparse
import os
import sys
import threading
import time

NICOS_ROOT = os.environ.get("NICOS_ROOT", os.path.join(os.path.expanduser("~"), "McStas_runs", "nicos_src"))
sys.path.insert(0, NICOS_ROOT)
from nicos.clients.base import ConnectionData, NicosClient  # noqa: E402
from nicos.utils.loggers import ACTION  # noqa: E402

STATUS_RUNNING, STATUS_IDLEEXC = 0, -2


class ScriptClient(NicosClient):
    def __init__(self):
        super().__init__(print)
        self.started = False
        self.failed = False
        self.done = threading.Event()

    def signal(self, name, *args):
        if name == "message":
            msg = args[0]
            if msg[2] != ACTION:
                print(msg[3].rstrip(), flush=True)
        elif name == "status":
            st = args[0][0]
            if st == STATUS_RUNNING:
                self.started = True
            elif st < 0 and self.started:          # idle again: the script is finished
                self.failed |= st == STATUS_IDLEEXC
                self.done.set()
        elif name in ("error", "failed", "broken"):
            print(f"[{name}] {args}", flush=True)
            self.failed = True
            self.done.set()


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("script", nargs="?", help="file with NICOS commands")
    a.add_argument("-c", "--code", help="NICOS commands given directly")
    a.add_argument("--host", default="localhost")
    a.add_argument("--port", type=int, default=1301)
    a.add_argument("--user", default="student")
    a.add_argument("--password", default="student")
    a.add_argument("--timeout", type=float, default=3600, help="maximum duration [s]")
    o = a.parse_args()
    code = o.code if o.code else open(o.script, encoding="utf-8").read() if o.script else None
    if not code:
        a.error("give a script file or -c 'commands'")
    c = ScriptClient()
    c.connect(ConnectionData(o.host, o.port, o.user, o.password))
    if not c.isconnected:
        print("could not connect to the NICOS daemon (is it running? user and password?)")
        return 1
    time.sleep(1)
    c.run(code)
    t_end = time.time() + o.timeout
    while True:
        if not c.done.wait(max(t_end - time.time(), 0)):
            print("timeout")
            c.failed = True
            break
        # the daemon may report "idle" for a moment between the blocks of a script (e.g. inside a with block):
        # finished only if it is still idle with nothing queued a moment later
        time.sleep(1.5)
        st = c.ask("getstatus", quiet=True) or {}
        status = st.get("status", (-1,))[0]
        if status < 0 and not st.get("requests"):
            break
        c.done.clear()
        c.started = True
    time.sleep(1)
    c.disconnect()
    return 1 if c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
