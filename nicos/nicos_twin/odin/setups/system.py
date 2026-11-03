import os

description = 'system setup of the ODIN digital twin'
group = 'lowlevel'

sysconfig = dict(
    cache = 'localhost',
    instrument = 'ODIN',
    experiment = 'Exp',
    datasinks = ['conssink', 'dmnsink', 'livesink'],
    notifiers = [],
)

modules = ['nicos.commands.standard']

devices = dict(
    ODIN = device('nicos.devices.instrument.Instrument',
        description = 'ODIN digital twin (McStas simulation of the ESS imaging instrument)',
        instrument = 'ODIN (digital twin)',
        responsible = 'ACCESS digital twin <agrgl@dtu.dk>',
        operators = ['ACCESS project'],
        facility = 'European Spallation Source (virtual)',
        website = 'https://ess.eu/instruments/odin',
    ),
    Sample = device('nicos.devices.sample.Sample',
        description = 'sample object',
    ),
    Exp = device('nicos_twin.devices.TwinExperiment',
        description = 'experiment object',
        dataroot = os.environ.get('TWIN_RUN_ROOT', os.path.expanduser('~/McStas_runs/twin')) + '/nicos/data',
        sample = 'Sample',
    ),
    conssink = device('nicos.devices.datasinks.ConsoleScanSink'),
    dmnsink = device('nicos.devices.datasinks.DaemonSink'),
    livesink = device('nicos.devices.datasinks.LiveViewSink',
        description = 'sends the detector image to the live-view panel',
    ),
)
