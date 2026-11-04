"""NICOS devices of the digital twins: thin clients of the twin server (twin/twin_server.py).

The virtual instrument (McStas, hybrid model, NeXus writing) runs in its own process and Python environment; these
NICOS devices only send orders over HTTP (standard library), exactly like the console twin_console.py:
  * TwinMotor / TwinSwitch: a device of the twin (stage_x, shutter, choppers...) seen as a NICOS Moveable;
  * TwinDetector: a NICOS Measurable; count(t=10) asks the twin to count, then returns the number of counts and the
    file number, and sends the detector image to the live-view panel of the GUI. As at ESS (file-writer), the file
    goes to the proposal folder <dataroot>/<instrument>/<year>/<proposal>/raw, with the experiment title, and a
    proposal number must be set first;
  * TwinExperiment: the ESS experiment (proposal, users, samples, as in the "Experiment" panel of the ESS GUI),
    without the "current" symlinks (Windows forbids symlinks to ordinary users).
"""
import json
import os
import threading
import urllib.error
import urllib.request

import numpy as np

from nicos import session
from nicos.core import ArrayDesc, CommunicationError, DeviceMixinBase, HasLimits, InvalidValueError, Measurable, Moveable, NicosError, \
    Override, Param, Value, anytype, status
from nicos.devices.experiment import Experiment
from nicos_ess.devices.experiment import EssExperiment


def _request(url, path, data=None, timeout=3600):
    req = urllib.request.Request(url + path, method="POST" if data is not None else "GET",
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = json.loads(e.read()).get("error", str(e))
        if e.code == 400:
            raise InvalidValueError(msg) from None
        raise NicosError(msg) from None
    except urllib.error.URLError:
        raise CommunicationError(f"no answer from the twin server at {url}: is it running?") from None


def proposal_folder():
    """Raw-data folder of the current proposal, as the ESS file-writer: <dataroot>/<instrument>/<year>/<proposal>/raw."""
    exp = session.experiment
    return os.path.join(exp.dataroot, exp.proposalpath_of(exp.propinfo.get("proposal"))).replace(os.sep, "/")


class TwinDevice(DeviceMixinBase):
    """Common parameters: server address and name of the device in the twin."""
    parameters = {
        "twinurl": Param("URL of the twin server", type=str, default="http://127.0.0.1:8765"),
        "twindevice": Param("name of the device in the twin", type=str, mandatory=True),
    }

    def _twin_value(self):
        return _request(self.twinurl, "/status", timeout=10)["devices"][self.twindevice]

    def _twin_move(self, value):
        _request(self.twinurl, "/move", {self.twindevice: value}, timeout=60)


class TwinMotor(TwinDevice, HasLimits, Moveable):
    """A numeric device of the twin (e.g. stage_x in m, stage_rot in degrees). Virtual motors arrive at once."""
    parameters = {"scale": Param("factor from NICOS units to twin units (e.g. 1e-3: mm -> m)", type=float, default=1.0)}
    parameter_overrides = {"unit": Override(mandatory=False, default="mm")}
    valuetype = float

    def doRead(self, maxage=0):
        return float(self._twin_value()) / self.scale

    def doStart(self, target):
        self._twin_move(float(target) * self.scale)

    def doStatus(self, maxage=0):
        return status.OK, ""


class TwinSwitch(TwinDevice, Moveable):
    """A device of the twin with a list of allowed values (e.g. shutter: open/closed; choppers: wfm/natural/white).
    mapping: NICOS value -> twin value, when the ESS name of a value differs (e.g. "Open" -> "open")."""
    parameters = {"states": Param("allowed values", type=list, mandatory=True),
                  "mapping": Param("NICOS value -> value in the twin", type=dict, default={})}
    parameter_overrides = {"unit": Override(mandatory=False, default="")}
    valuetype = anytype

    def doIsAllowed(self, target):
        for s in self.states:
            if target == s or (isinstance(s, float) and isinstance(target, (int, float))
                               and abs(float(target) - s) < 1e-9):
                return True, ""
        return False, f"allowed values: {self.states}"

    def doStart(self, target):
        for s in self.states:          # send the canonical value (e.g. 0.3 for 0.30)
            if isinstance(s, float) and isinstance(target, (int, float)) and abs(float(target) - s) < 1e-9:
                target = s
        self._twin_move(self.mapping.get(target, target))

    def doRead(self, maxage=0):
        v = self._twin_value()
        for k, tv in self.mapping.items():
            if tv == v:
                return k
        return v

    def doStatus(self, maxage=0):
        return status.OK, ""


class TwinDetector(TwinDevice, Measurable):
    """The detector of the twin. Preset: t (seconds). Values: number of counts and file number. Array: the detector
    image (sent to the live-view panel by the LiveViewSink). The file title is the experiment title (as at ESS)."""
    parameter_overrides = {"twindevice": Override(mandatory=False, default="detector")}
    parameters = {
        "imageshape": Param("(rows, columns) of the detector image", type=tuple, default=(128, 128)),
        "lastfile": Param("last data file written by the twin", type=str, default="", settable=True, internal=True),
    }

    def doInit(self, mode):
        self._preset = {"t": 1.0}
        self._thread = None
        self._result = None
        self._error = None

    def presetInfo(self):
        return {"t"}

    def doSetPreset(self, **preset):
        if "t" in preset:
            self._preset["t"] = float(preset["t"])

    def doStart(self):
        self._result, self._error = None, None
        exp = session.experiment
        if not exp.propinfo.get("proposal"):          # as the ESS file-writer
            raise NicosError(self, "cannot start writing as proposal number not set: "
                                   "NewExperiment(<number>, '<title>') or the Experiment panel")
        t = self._preset["t"]
        args = {"t": t, "title": exp.title, "image": True, "folder": proposal_folder()}

        def work():
            try:
                self._result = _request(self.twinurl, "/count", args)
            except Exception as e:      # reported by doStatus / doRead
                self._error = e
        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()

    def doStatus(self, maxage=0):
        if self._thread is not None and self._thread.is_alive():
            return status.BUSY, f"counting {self._preset['t']:g} s (simulation running)"
        if self._error is not None:
            return status.ERROR, str(self._error)
        return status.OK, "idle"

    def doIsCompleted(self):
        return self._thread is None or not self._thread.is_alive()

    def doFinish(self):
        if self._thread is not None:
            self._thread.join()
        if self._error is not None:
            raise NicosError(self, str(self._error))
        if self._result:
            self._setROParam("lastfile", self._result["file"])
            self.log.info("file written: %s", self._result["file"])

    def doStop(self):
        self.log.warning("a count of the twin cannot be interrupted; waiting for it to finish")
        self.doFinish()

    def valueInfo(self):
        return (Value("counts", type="counter", fmtstr="%d", unit="cts"),
                Value("file", type="other", fmtstr="%d", unit=""))

    def doRead(self, maxage=0):
        if not self._result:
            return [0, 0]
        return [int(self._result.get("n_counts") or 0), int(self._result.get("number") or 0)]

    def arrayInfo(self):
        return (ArrayDesc("image", shape=tuple(self.imageshape), dtype=np.uint32),)

    def doReadArrays(self, quality):
        if not self._result or "image" not in self._result:
            return [np.zeros(tuple(self.imageshape), dtype=np.uint32)]
        return [np.asarray(self._result["image"], dtype=np.uint32)]


class TwinExperiment(EssExperiment):
    """ESS experiment (proposal number, title, users, samples; data in <dataroot>/<instrument>/<year>/<proposal>/raw),
    without the "current" symlinks (not allowed for ordinary users on Windows). The look-up of real ESS proposals
    (user office) is not available: any number can be used."""

    def doInit(self, mode):
        # no connection to the ESS user office: the proposal number and title are typed in (Experiment panel, or
        # NewExperiment), as when the proposal system is unreachable at ESS
        Experiment.doInit(self, mode)
        self._client = None

    def _canQueryProposals(self):
        return False

    @property
    def proposalsymlink(self):
        return ""

    @property
    def samplesymlink(self):
        return ""
