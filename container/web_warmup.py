"""Prepares the online version before the first student (container/start.sh web): the beam of the setting used by
the guided pages (WFM, discs 0.30 m apart, pinhole 3 cm, diffuser in; and the white beam of the camera images of
exercise 1) is simulated once (McStas, a few minutes) and kept, so that the first count of a student starts at once."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "odin")]
from odin_virtual import VirtualOdin  # noqa: E402

t = time.time()
odin = VirtualOdin(session="_warmup")
odin.move(choppers="wfm", wfm_delta=0.30, pinhole=0.03, diffuser="in", shutter="open", stage_x=0.5)
odin.count(2, title="warm-up", write=False)
odin.move(choppers="white")
odin.camera(1, title="warm-up", write=False)
print(f"online version ready (beam prepared in {time.time() - t:.0f} s)")
