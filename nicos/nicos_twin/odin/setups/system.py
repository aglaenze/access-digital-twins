import os

# Same structure as nicos_ess/odin/setups/system.py (the NICOS of the real ODIN), without the Kafka services
# (forwarder status, SciChat): the twin writes the data files itself.
description = 'system setup'

group = 'lowlevel'

RUN_ROOT = os.environ.get('TWIN_RUN_ROOT', os.path.expanduser('~/McStas_runs/twin'))

sysconfig = dict(
    cache='localhost',
    instrument='ODIN',
    experiment='Exp',
    datasinks=['conssink', 'daemonsink', 'liveview'],
)

modules = ['nicos.commands.standard', 'nicos_twin.commands']

devices = dict(
    ODIN=device(
        'nicos.devices.instrument.Instrument',
        description='instrument object',
        instrument='ODIN',
        responsible='ACCESS digital twin <agrgl@dtu.dk>',
        website='https://europeanspallationsource.se/instruments/odin',
        facility='European Spallation Source (digital twin)',
    ),
    Sample=device(
        'nicos_ess.devices.sample.EssSample',
        description='The currently used sample',
    ),
    Exp=device(
        'nicos_twin.devices.TwinExperiment',
        description='experiment object',
        dataroot=RUN_ROOT + '/data',
        sample='Sample',
        cache_filepath=RUN_ROOT + '/nicos/cached_proposals.json',
    ),
    conssink=device(
        'nicos_ess.devices.datasinks.console_scan_sink.ConsoleScanSink'),
    daemonsink=device(
        'nicos.devices.datasinks.DaemonSink'
    ),
    liveview=device(
        'nicos.devices.datasinks.LiveViewSink'
    ),
)
