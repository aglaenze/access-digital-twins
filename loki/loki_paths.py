"""Paths of the LoKI digital twin (imported first by every module of twin/loki/).

* LOKI_REPO: clone of the official McStas model of LoKI, https://git.esss.dk/dmsc-instrumentmodels/LOKI
  (file instr/LOKI_main.instr); environment variable LOKI_REPO, default ~/McStas_runs/LOKI;
* TWIN_RUN_ROOT: results of all the twins (variable TWIN_RUN_ROOT, default ~/McStas_runs/twin); no spaces allowed;
* RUN_ROOT: results of the LoKI twin (TWIN_RUN_ROOT/loki): upstream parts (front/), downstream parts, sessions;
* BUILD: folder where the McStas instruments of the twin are written and compiled;
* COMPONENTS: McStas components written for the twin (SANS_Iq_table).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
LOKI_REPO = os.environ.get("LOKI_REPO", os.path.join(HOME, "McStas_runs", "LOKI")).replace(os.sep, "/")
TWIN_RUN_ROOT = os.environ.get("TWIN_RUN_ROOT", os.path.join(HOME, "McStas_runs", "twin")).replace(os.sep, "/")
RUN_ROOT = f"{TWIN_RUN_ROOT}/loki"
BUILD = os.path.join(HERE, "build")
COMPONENTS = os.path.join(HERE, "components")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
if os.path.dirname(HERE) not in sys.path:      # twin/: mcstas_env
    sys.path.insert(0, os.path.dirname(HERE))
import mcstas_env  # noqa: E402,F401  (MCSTAS and mcrun, also without an activated environment)
