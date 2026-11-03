"""Paths of the ODIN digital twin (imported first by every module of twin/odin/).

* TWIN_RUN_ROOT: results of all the twins (environment variable TWIN_RUN_ROOT, default ~/McStas_runs/twin, i.e.
  C:/Users/<user>/McStas_runs/twin on Windows). Must not contain spaces (McStas command line), hence not in OneDrive;
* RUN_ROOT: results of the ODIN twin (TWIN_RUN_ROOT/odin): upstream parts (front/), simulations, sessions;
* BUILD: folder where the McStas instruments of the twin are written and compiled;
* COMPONENTS: McStas components written for the twin.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TWIN_RUN_ROOT = os.environ.get("TWIN_RUN_ROOT",
                               os.path.join(os.path.expanduser("~"), "McStas_runs", "twin")).replace(os.sep, "/")
RUN_ROOT = f"{TWIN_RUN_ROOT}/odin"
BUILD = os.path.join(HERE, "build")
COMPONENTS = os.path.join(HERE, "components")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
