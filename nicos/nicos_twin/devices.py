"""NICOS devices of the digital twins: thin clients of the twin server (twin/twin_server.py).

The virtual instrument (McStas, hybrid model, NeXus writing) runs in its own process and Python environment; these
NICOS devices only send orders over HTTP (standard library), exactly like the console twin_console.py:
  * TwinMotor / TwinSwitch: a device of the twin (stage_x, shutter, choppers...) seen as a NICOS Moveable;
  * TwinReadable: a read-only value that follows from the settings (chopper speeds and delays...);
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
import time
import urllib.error
import urllib.request

import numpy as np

from nicos import session
from nicos.core import ArrayDesc, CommunicationError, DeviceMixinBase, HasLimits, InvalidValueError, Measurable, Moveable, NicosError, \
    Override, Param, Readable, Value, anytype, status
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


class TwinSampleChanger(TwinSwitch):
    """The sample changer: its list of samples comes from the twin (built-in samples, then the student's own samples
    of the current proposal, made with the sample builder), so a new sample can be mounted at once."""
    parameter_overrides = {"states": Override(mandatory=False, default=[])}

    def _sync(self):
        exp = session.experiment
        if exp and exp.propinfo.get("proposal"):
            try:
                _request(self.twinurl, "/folder", {"folder": proposal_folder()}, timeout=30)
            except InvalidValueError:
                pass
        return list(_request(self.twinurl, "/devices", timeout=30)[self.twindevice]["choices"] or [])

    def doIsAllowed(self, target):
        names = self._sync()
        if target in names:
            return True, ""
        return False, (f"samples available: {names} (your own samples: the sample builder, button of your starter "
                       "notebook, saved with the proposal applied in the Experiment panel)")

    def doStart(self, target):
        self._twin_move(target)
        try:                               # the sample of the experiment (Sample panel of the ESS GUI, file metadata)
            session.experiment.sample.samplename = str(target)
        except Exception:                  # noqa: BLE001 (no sample device in this setup)
            pass


class TwinReadable(TwinDevice, Readable):
    """A read-only value of the twin that follows from the settings (e.g. speed and delay of a chopper, set by the
    chopper mode), as the readback devices of the real instrument. read() always asks the twin (a value kept in the
    NICOS cache would lag behind a change of configuration); the poller refreshes the cache every 2 s for the device
    list of the GUI (maxage 5 s, set in the setups: NICOS keeps parameters in its cache between sessions)."""
    parameter_overrides = {"unit": Override(mandatory=False, default=""),
                           "maxage": Override(default=5),
                           "pollinterval": Override(default=2)}
    valuetype = anytype

    def read(self, maxage=None):
        # NICOS keeps the parameters (maxage included) in its cache between sessions: force a fresh read here
        return Readable.read(self, 0)

    def doRead(self, maxage=0):
        return _request(self.twinurl, "/status", timeout=10)["readings"][self.twindevice]

    def doStatus(self, maxage=0):
        return status.OK, ""


class TwinDetector(TwinDevice, Measurable):
    """The detector of the twin. Preset: t (seconds). Values: number of counts and file number. Array: the detector
    image (sent to the live-view panel by the LiveViewSink). The file title is the experiment title (as at ESS).

    stream = True (live data, as at ESS): in prepare, the twin computes the measurement and writes the file, then waits;
    in start, it streams the neutrons to Kafka in real time (one message per source pulse, 14 per second), while
    just-bin-it (detector "jbi", started by the same count) histograms them for the live display. The count lasts
    t seconds of real time, like on the instrument."""
    parameter_overrides = {"twindevice": Override(mandatory=False, default="detector")}
    parameters = {
        "imageshape": Param("(rows, columns) of the detector image", type=tuple, default=(128, 128)),
        "lastfile": Param("last data file written by the twin", type=str, default="", settable=True, internal=True),
        "stream": Param("stream the neutrons to Kafka during the count (live data)", type=bool, default=False,
                        settable=True),
    }

    def doInit(self, mode):
        self._preset = {"t": 1.0}
        self._thread = None
        self._result = None
        self._error = None
        self._preparing = False
        self._streaming = False

    def presetInfo(self):
        return {"t"}

    def doSetPreset(self, **preset):
        if "t" in preset:
            self._preset["t"] = float(preset["t"])

    def _launch(self, extra):
        self._result, self._error = None, None
        exp = session.experiment
        if not exp.propinfo.get("proposal"):          # as the ESS file-writer
            raise NicosError(self, "cannot start writing as proposal number not set: "
                                   "NewExperiment(<number>, '<title>') or the Experiment panel")
        args = dict({"t": self._preset["t"], "title": exp.title, "image": True, "folder": proposal_folder()}, **extra)

        def work():
            try:
                self._result = _request(self.twinurl, "/count", args)
            except Exception as e:      # reported by doStatus / doRead
                self._error = e
        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()

    def _live(self):
        """Stream only when just-bin-it is one of the detectors of the count (setup live loaded)."""
        return (self.stream and _EssJustBinItDetector is not None
                and any(isinstance(d, _EssJustBinItDetector) for d in session.experiment.detectors))

    def doPrepare(self):
        self._streaming = self._live()
        if self._streaming:             # compute now; the stream starts with the count (doStart)
            self._preparing = True
            self._launch({"stream": True, "hold": True})

    def doStart(self):
        if not self._streaming:
            self._launch({})
            return
        while self._preparing and self._thread.is_alive() and not self._ready():
            session.delay(0.2)
        self._preparing = False
        if self._error is None and self._thread.is_alive():
            _request(self.twinurl, "/go", {}, timeout=10)

    def _ready(self):
        try:
            return bool(_request(self.twinurl, "/status", timeout=10).get("ready"))
        except Exception:
            return False

    def doStatus(self, maxage=0):
        if self._error is not None:
            return status.ERROR, str(self._error)
        if self._thread is not None and self._thread.is_alive():
            if self._preparing:
                if self._ready():
                    return status.OK, "measurement computed, ready to stream"
                return status.BUSY, f"computing the measurement ({self._preset['t']:g} s)"
            return status.BUSY, (f"counting {self._preset['t']:g} s (streaming live)" if self._streaming
                                 else f"counting {self._preset['t']:g} s (simulation running)")
        return status.OK, "idle"

    def doIsCompleted(self):
        if self._preparing:             # after prepare, NICOS waits for isCompleted before starting the count
            return self._error is not None or not self._thread.is_alive() or self._ready()
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
        if self._streaming and self._thread is not None and self._thread.is_alive():
            _request(self.twinurl, "/stop", {}, timeout=10)      # ends the stream (the file is already written)
        else:
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


try:        # live data (Kafka): needs confluent-kafka, ess-streaming-data-types, keyring (optional for the twin)
    from nicos_ess.devices.datasources.just_bin_it import JustBinItDetector as _EssJustBinItDetector
except Exception:
    _EssJustBinItDetector = None

if _EssJustBinItDetector is not None:
    class TwinJustBinItDetector(_EssJustBinItDetector):
        """The just-bin-it detector of the ESS NICOS, with an explicit time window for the histograms: from 0.5 s before
        the count to 0.5 s after its end, instead of "interval" (just-bin-it would start it when it reads the command,
        a little after the twin has started streaming, and lose the first pulses). The twin keeps streaming empty pulses
        for a moment after the measurement, as a real detector streams all the time, so just-bin-it sees the end."""

        def _create_config(self, interval, identifier):
            config = super()._create_config(interval, identifier)
            if interval:
                now_ms = int(time.time() * 1000)
                config.pop("interval", None)
                config["start"] = now_ms - 500
                config["stop"] = now_ms + int(interval * 1000) + 500
            return config


class TwinExperiment(EssExperiment):
    """ESS experiment (proposal number, title, users, samples; data in <dataroot>/<instrument>/<year>/<proposal>/raw),
    without the "current" symlinks (not allowed for ordinary users on Windows).
    Proposals: as at ESS, from the twin's user office (user_office.py, written to the proposal cache cache_filepath
    by start_nicos.py): "Find my proposal" in the Experiment tab lists the proposals of the exercises and the student's own (free
    beamtimes, imported proposals) and fills in the number, title, users and samples. On a new proposal, its first
    sample is mounted on the sample changer (the student may mount another one). With start_nicos.py --no-proposals,
    any number can be typed in, as when the proposal system is unreachable at ESS. NewExperiment in a script accepts
    any number in both cases, as at ESS."""

    def doInit(self, mode):
        if os.environ.get("TWIN_PROPOSALS", "1") != "0" and os.path.isfile(self.cache_filepath):
            EssExperiment.doInit(self, mode)
            return
        Experiment.doInit(self, mode)
        self._client = None

    def new(self, proposal, title=None, localcontact=None, user=None, **kwds):
        EssExperiment.new(self, proposal, title, localcontact, user, **kwds)
        if self._client is None:
            return
        try:                               # the first sample of the proposal, mounted by default
            found = [p for p in self._client.all_proposals() if str(p.id) == str(proposal)]
            names = [s.name for s in found[0].samples] if found else []
            changer = session.getDevice("sample_holder") if names else None
        except Exception:                  # noqa: BLE001 (no proposal, or no sample changer in this setup)
            return
        if changer is not None:
            try:
                if changer.isAllowed(names[0])[0]:
                    changer.maw(names[0])
                    self.log.info("sample %r of proposal %s mounted (sample_holder); mount another one with "
                                  "move(sample_holder, '<name>')", names[0], proposal)
                else:
                    self.log.info("the samples of proposal %s are not on the sample changer yet: build them with "
                                  "the sample builder (same short names: %s)", proposal, ", ".join(names))
            except Exception as e:         # noqa: BLE001
                self.log.warning("sample %r not mounted: %s", names[0], e)

    def _canQueryProposals(self):
        return self._client is not None

    @property
    def scriptpath(self):
        """Folder of the user's scripts (default folder of Open/Save in the Scripting tab):
        <dataroot>/<instrument>/<year>/<proposal>/scripts, next to raw/. (The generic value, based on the
        proposalpath parameter that EssExperiment does not update, is a stale relative path.)"""
        proposal = self.propinfo.get("proposal") or self.proposal or "0"
        folder = os.path.join(self.dataroot, os.path.dirname(self.proposalpath_of(str(proposal))), "scripts")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        return folder.replace(os.sep, "/")

    @property
    def proposalsymlink(self):
        return ""

    @property
    def samplesymlink(self):
        return ""
