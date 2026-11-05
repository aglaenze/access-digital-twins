"""ESS file-writing commands for the digital twins: same names and same use as nicos_ess.commands.

At ESS, the NeXus files are written by the file-writer (a separate service fed by Kafka), which NICOS starts and
stops. The usual way to record data in a script is

    with nexusfile_open('iron plate, 5 mm'):
        count(t=60)

Here the twin writes the files itself, one per count, in the proposal folder, with the experiment title; these
commands set that title and keep the list of "jobs", so that ESS scripts run unchanged. Difference with ESS: at
ESS, everything recorded inside one nexusfile_open block (several counts, a scan) goes into ONE file; the twin
writes one file per count.
"""
import os
import time
from contextlib import contextmanager

from nicos import session
from nicos.commands import helparglist, usercommand
from nicos.utils import printTable

from nicos_twin.devices import proposal_folder

__all__ = ["nexusfile_open", "start_filewriting", "stop_filewriting", "list_filewriting_jobs", "sample_info"]

_JOBS = []          # dicts: number, title, start, stop, files


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
    _JOBS.append(dict(number=len(_JOBS) + 1, title=exp.title, start=time.time(), stop=None, folder=folder,
                      before=_data_files(folder), files=[]))
    session.log.info('Filewriting started')


@usercommand
@helparglist('job_number')
def stop_filewriting(job_number=None):
    """Stop a file-writing job."""
    active = _active()
    if job_number is not None:
        active = [j for j in active if j["number"] == job_number]
    for j in active:
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
    for line in r["text"].splitlines():
        session.log.info(line)
    session.log.info("drawing of the sample: %s (open it in JupyterLab)", r["png"])
