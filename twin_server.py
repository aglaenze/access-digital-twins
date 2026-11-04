"""Digital-twin server: a virtual instrument (e.g. VirtualOdin) in its own process, driven over the network.

Why: on a real instrument, the control station (NICOS) and what it drives are separate processes. Here too: NICOS
cannot live in the McStas environment (it requires numpy < 2; essimaging and scipp use numpy 2). The NICOS devices
(nicos/nicos_twin) send their orders to this server, as the console `twin_console.py` does.

    python twin_server.py --instrument odin [--session NAME] [--port 8765] [--mode hybrid|mcstas]

Instruments: see INSTRUMENTS below (one sub-folder of twin/ per instrument, with a class exposing move, count, scan,
status, devices, log_file, number, folder, mode).

JSON over http://127.0.0.1:<port> (local connections only):
    GET  /status                         -> device state, busy or not, number of the last file
    GET  /devices                        -> description of the devices (unit, limits, choices, help)
    GET  /log                            -> actions of the session
    POST /move   {"device": value, ...}
    POST /count  {"t": 10, "title": "...", "image": false, "write": true, "folder": null}
                 -> {"file", "number", "n_counts", ["image": detector image for live displays]}
                 write=false: no file (live image only), as a count outside a file-writing job at ESS;
                 folder: where to write the files (NICOS: the proposal folder), default the session folder
    POST /scan   {"device": ..., "values": [...], "t": 10, "title": "..."}   -> {"files": [...]}
One measurement at a time (as on the instrument): a command received during a measurement is refused (code 409,
"instrument busy"), but /status always answers.
"""
import argparse
import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
# instrument name -> (sub-folder of twin/, module, class)
INSTRUMENTS = {"odin": ("odin", "odin_virtual", "VirtualOdin"),
               "loki": ("loki", "virtual_loki", "VirtualLoki")}

INSTR = None
LOCK = threading.Lock()
RUNNING = {"action": None}


def _json(v):
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    return v.item() if hasattr(v, "item") else v


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, content):
        body = json.dumps(content, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):            # server log: one line per request
        sys.stderr.write("[server] " + fmt % args + "\n")

    def do_GET(self):
        if self.path == "/status":
            return self._reply(200, dict(devices=INSTR.status(), busy=LOCK.locked(), running=RUNNING["action"],
                                         last_number=INSTR.number, folder=INSTR.folder, mode=INSTR.mode))
        if self.path == "/devices":
            return self._reply(200, {n: dict(value=d.value, unit=d.unit, limits=d.limits,
                                             choices=_json(d.choices) if d.choices else None, help=d.help)
                                     for n, d in INSTR.devices.items()})
        if self.path == "/log":
            lines = []
            if os.path.isfile(INSTR.log_file):
                lines = [json.loads(l) for l in open(INSTR.log_file, encoding="utf-8")]
            return self._reply(200, lines)
        self._reply(404, dict(error=f"unknown: {self.path}"))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            args = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError as e:
            return self._reply(400, dict(error=f"invalid JSON: {e}"))
        if not LOCK.acquire(blocking=False):
            return self._reply(409, dict(error=f"instrument busy ({RUNNING['action']})"))
        try:
            RUNNING["action"] = self.path
            if self.path == "/move":
                INSTR.move(**args)
                return self._reply(200, dict(devices=INSTR.status()))
            if self.path == "/count":
                if args.get("folder"):
                    if not os.path.isabs(args["folder"]):
                        raise ValueError(f"folder must be an absolute path: {args['folder']}")
                    INSTR.use_folder(args["folder"])
                f = INSTR.count(float(args["t"]), title=args.get("title", ""), write=args.get("write", True))
                out = dict(file=f, number=INSTR.number, n_counts=getattr(INSTR, "last_n_counts", None))
                if args.get("image"):                          # detector image for live displays (NICOS)
                    out["image"] = INSTR.last_image.tolist()
                return self._reply(200, out)
            if self.path == "/scan":
                files = INSTR.scan(args["device"], args["values"], float(args["t"]), title=args.get("title", ""))
                return self._reply(200, dict(files=files))
            return self._reply(404, dict(error=f"unknown command: {self.path}"))
        except (ValueError, KeyError, TypeError) as e:         # user error: impossible setting...
            return self._reply(400, dict(error=str(e)))
        except Exception as e:                                 # twin error
            traceback.print_exc()
            return self._reply(500, dict(error=f"{type(e).__name__}: {e}"))
        finally:
            RUNNING["action"] = None
            LOCK.release()


def main():
    global INSTR
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--instrument", default="odin", choices=sorted(INSTRUMENTS))
    p.add_argument("--session", default=os.environ.get("TWIN_SESSION", "console"))
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--mode", default="hybrid", choices=("hybrid", "mcstas"))
    a = p.parse_args()
    folder, module, cls = INSTRUMENTS[a.instrument]
    sys.path.insert(0, os.path.join(HERE, folder))
    import importlib
    INSTR = getattr(importlib.import_module(module), cls)(session=a.session, mode=a.mode)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Virtual {a.instrument.upper()} ready: http://127.0.0.1:{a.port}  (session {a.session}, files in {INSTR.folder})",
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
