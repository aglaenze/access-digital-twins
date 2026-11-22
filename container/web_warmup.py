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
# the class session (odin/exercises/meteorite_imaging/ODIN_meteorite_class.ipynb): white beam, the camera 6 mm from
# the axis, the meteorite; Timepix3 counts with the 1 cm pinhole, then the tomography with the 3 cm pinhole (60 angles,
# 512 pixels). Without this, the first count of each student would prepare this beam itself (minutes), and the first
# tomography would compute the thickness maps of the meteorite at each angle (kept on disk for all the students).
odin.move(choppers="white", pinhole=0.01, sample="meteorite_nwa7034", stage_x=0.0, detector_distance=0.006)
odin.count(1, title="warm-up", write=False)
odin.move(pinhole=0.03)
for a in range(0, 180, 3):
    odin.move(stage_rot=float(a))
    odin.camera(1, title="warm-up", write=False, pixels=512)
odin.move(stage_rot=0.0)
print(f"online version ready (beam prepared in {time.time() - t:.0f} s)")
