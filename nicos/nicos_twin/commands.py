"""ESS file-writing commands for the digital twins: same names and same use as nicos_ess.commands.

At ESS, the NeXus files are written by the file-writer (a separate service fed by Kafka), which NICOS starts and
stops. The usual way to record data in a script is

    with nexusfile_open('iron plate, 5 mm'):
        count(t=60)

Here the twin writes the files itself, one per count, in the proposal folder, with the experiment title; these
commands set that title and keep the list of "jobs", so that ESS scripts run unchanged. Difference with ESS: at
ESS, everything recorded inside one nexusfile_open block (several counts, a scan) goes into ONE file; the twin
writes one file per count.

With the ESS file-writer (TWIN_FILEWRITER=1 for NICOS; Linux, filewriter/README.md): as at ESS, start_filewriting
starts a job of the file-writer (through the twin server, POST /filewriter/start) and everything recorded until
stop_filewriting goes into ONE file of the file-writer (<instrument>_job_NNNNNN.hdf in the proposal folder); the twin
writes its own files of the counts apart (<proposal>/.twin), and stop_filewriting compares them with the file-writer's.
"""
import os
import time
from contextlib import contextmanager

from nicos import session
from nicos.commands import helparglist, usercommand
from nicos.utils import printTable

from nicos_twin.devices import proposal_folder

__all__ = ["nexusfile_open", "start_filewriting", "stop_filewriting", "list_filewriting_jobs", "sample_info",
           "radiograph", "tomography", "tof_histogram", "polarimetry", "polarization_matrix"]

_JOBS = []          # dicts: number, title, start, stop, files


def _filewriter():
    """True if the ESS file-writer writes the files (TWIN_FILEWRITER=1)."""
    return os.environ.get("TWIN_FILEWRITER") == "1"


def _twin(path, args, timeout):
    from nicos_twin.devices import _request
    return _request(session.getDevice("sample_holder").twinurl, path, args, timeout=timeout)


def _data_files(folder):
    if not os.path.isdir(folder):
        return set()
    return {f for f in os.listdir(folder) if f.endswith((".nxs", ".h5", ".hdf"))}


def _active():
    return [j for j in _JOBS if j["stop"] is None]


@usercommand
@helparglist('experiment_title')
@contextmanager
def nexusfile_open(experiment_title=None):
    """Records data in NeXus files for as long as the indented block runs.

    >>> with nexusfile_open('open beam'):
    >>>     count(t=10)
    """
    nested = bool(_active())
    if nested:
        session.log.warning('Filewriter already running. Will not start a new file with title: %s',
                            experiment_title)
    else:
        start_filewriting(experiment_title)
    try:
        yield
    finally:
        if not nested:
            stop_filewriting()


@usercommand
@helparglist('experiment_title')
def start_filewriting(experiment_title=None):
    """Start a file-writing job (the title becomes the experiment title)."""
    exp = session.experiment
    if not exp.propinfo.get('proposal'):
        raise RuntimeError('cannot start writing as proposal number not set')
    if _active():
        raise RuntimeError('cannot start writing as writing already in progress')
    if experiment_title is not None:
        session.log.info('Setting experiment title to: %s', experiment_title)
        exp.update(title=experiment_title)
    folder = proposal_folder()
    job = dict(number=len(_JOBS) + 1, title=exp.title, start=time.time(), stop=None, folder=folder,
               before=_data_files(folder), files=[], fw=None)
    if _filewriter():
        r = _twin("/filewriter/start", {"title": exp.title, "proposal": str(exp.propinfo.get('proposal')),
                                         "folder": folder}, timeout=300)
        job["fw"] = r["file"]
        session.log.info('file-writer job %s: %s', r["job"], r["file"])
    _JOBS.append(job)
    session.log.info('Filewriting started')


@usercommand
@helparglist('job_number')
def stop_filewriting(job_number=None):
    """Stop a file-writing job."""
    active = _active()
    if job_number is not None:
        active = [j for j in active if j["number"] == job_number]
    for j in active:
        if j.get("fw"):
            r = _twin("/filewriter/stop", {}, timeout=900)
            if r.get("error"):
                session.log.error('file-writer: %s', r["error"])
            else:
                session.log.info('file written by the file-writer: %s', r["file"])
            if "differences" in r:
                (session.log.info if r["differences"] == 0 else session.log.warning)(
                    'compared with the %d file(s) of the twin: %s', len(r["twin_files"]),
                    'same data' if r["differences"] == 0 else '%d difference(s)' % r["differences"])
                for line in r.get("report", []):
                    session.log.info(line)
        j["stop"] = time.time()
        j["files"] = sorted(_data_files(j["folder"]) - j["before"])
        if j["files"]:
            session.log.info('job %d (%s): %s', j["number"], j["title"], ', '.join(j["files"]))
        if not j["files"]:
            session.log.warning('no data recorded in this job (no count inside the block)')
    session.log.info('Filewriting stopped')


@usercommand
def list_filewriting_jobs():
    """List current and recent file-writing jobs."""
    fmt = '%Y-%m-%d %H:%M:%S'
    items = [[str(j["number"]), 'written' if j["stop"] else 'writing', j["title"],
              time.strftime(fmt, time.localtime(j["start"])),
              time.strftime(fmt, time.localtime(j["stop"])) if j["stop"] else '', ', '.join(j["files"])]
             for j in _JOBS]
    printTable(['job', 'status', 'title', 'start time', 'stop time', 'files'], items, session.log.info)


@usercommand
def sample_info():
    """Describes the sample mounted on the instrument (material, shape, sizes) and saves its drawing.

    >>> sample_info()
    """
    from nicos_twin.devices import _request
    dev = session.getDevice("sample_holder")
    if session.experiment.propinfo.get("proposal"):
        _request(dev.twinurl, "/folder", {"folder": proposal_folder()}, timeout=30)
    r = _request(dev.twinurl, "/sample", timeout=120)
    ascii_ = {"α": "alpha", "γ": "gamma", "×": "x", "Å": "A", "²": "2", "₂": "2", "⁻": "-", "¹": "1", "ρ": "rho",
              "φ": "phi"}                        # the NICOS log of a Windows console cannot write them
    for line in r["text"].splitlines():
        session.log.info("".join(ascii_.get(c, c) for c in line))
    session.log.info("drawing of the sample: %s (open it in JupyterLab)", r["png"])


# --------------------------------------------------------------------------- ODIN: the camera of white-beam imaging
@usercommand
@helparglist('t[, title, pixels]')
def radiograph(t, title='', pixels=128):
    """One image with the integrating camera of ODIN (scintillator + camera, as for white-beam radiography and
    tomography): t seconds of exposure, no time of flight. The file (odin_NNNNNN.nxs, entry/instrument/camera/data)
    goes to the folder of the proposal. pixels: 128 (110 µm, the standard camera) or 512 (27.5 µm, high resolution).

    >>> move(choppers, 'white', shutter, 'open', stage_x, 0)
    >>> radiograph(2, 'meteorite 0 deg')
    """
    folder = proposal_folder() if session.experiment.propinfo.get("proposal") else None
    r = _twin("/camera", {"t": float(t), "title": title, "folder": folder, "pixels": int(pixels)}, timeout=600)
    session.log.info("camera image: %s (%d counts)", os.path.basename(r["file"]), r["n_counts"])
    return r["file"]


@usercommand
@helparglist('t[, title, pixels]')
def tof_histogram(t, title='', pixels=128):
    """The Timepix3 camera in histogram mode: t seconds, the counts summed per pixel and per wavelength bin of 0.01 A
    (2.7 to 4.5 A) instead of neutron by neutron, for long exposures (choppers 'wfm' or 'natural'). The file
    (entry/instrument/camera/data: counts (wavelength, y, x); .../wavelength: the bin edges) goes to the folder of
    the proposal.

    >>> move(choppers, 'wfm', wfm_delta, 0.3, shutter, 'open', stage_x, 0)
    >>> tof_histogram(3600, 'standards')
    """
    folder = proposal_folder() if session.experiment.propinfo.get("proposal") else None
    r = _twin("/tof_histogram", {"t": float(t), "title": title, "folder": folder, "pixels": int(pixels)}, timeout=900)
    session.log.info("histogram image: %s (%d counts)", os.path.basename(r["file"]), r["n_counts"])
    return r["file"]


@usercommand
@helparglist('t[, title, pixels]')
def polarimetry(t, title='', pixels=128):
    """Polarized imaging (polarizer in): t seconds with the Timepix3 camera, the neutrons sorted by wavelength
    (16 bins from 1.5 to 6 Å). The spin enters the sample along spin_in, the analyzer passes the spin along spin_out.
    The file (entry/instrument/camera/data: counts (wavelength, y, x)) goes to the folder of the proposal.

    >>> move(polarizer, 'in', spin_in, '+y', spin_out, 'y')
    >>> polarimetry(150, 'solenoid +y y')
    """
    folder = proposal_folder() if session.experiment.propinfo.get("proposal") else None
    r = _twin("/polarimetry", {"t": float(t), "title": title, "folder": folder, "pixels": int(pixels)}, timeout=900)
    session.log.info("polarized image: %s (%d counts)", os.path.basename(r["file"]), r["n_counts"])
    return r["file"]


@usercommand
@helparglist('t[, title, pixels]')
def polarization_matrix(t, title='', pixels=128):
    """The 18 images of the full polarization matrix: spin_in along +x, -x, +y, -y, +z, -z for each spin_out x, y, z,
    t seconds each (polarizer in): P_ij = (N(+i, j) - N(-i, j)) / (N(+i, j) + N(-i, j)).

    >>> polarization_matrix(150, 'solenoid 0 deg')     # 18 x 150 s = 45 min, as at RADEN
    """
    session.getDevice("polarizer").maw("in")
    files = []
    for j in "xyz":
        for i in ("+x", "-x", "+y", "-y", "+z", "-z"):
            session.getDevice("spin_in").maw(i)
            session.getDevice("spin_out").maw(j)
            files.append(polarimetry(t, ("%s %s %s" % (title, i, j)).strip(), pixels))
    return files


@usercommand
@helparglist('t[, step, title, pixels]')
def tomography(t, step=6.0, title='tomography', pixels=128):
    """A tomography with the camera: one radiograph(t) at each angle of stage_rot from 0 to 180 degrees (excluded) in
    steps of `step` degrees, then stage_rot back to 0. Measure first an open beam and a dark with radiograph().

    >>> tomography(1, 6)          # 30 images of 1 s
    """
    rot = session.getDevice("stage_rot")
    n = int(round(180.0 / float(step)))
    files = []
    for k in range(n):
        a = k * float(step)
        rot.maw(a)
        files.append(radiograph(t, '%s rot=%g' % (title, a), pixels))
        session.log.info("tomography: image %d of %d", k + 1, n)
    rot.maw(0)
    return files
