import os

description = 'ODIN digital twin: devices (each one relays its orders to the twin server)'
group = 'basic'

includes = ['system', 'choppers']

URL = 'http://127.0.0.1:8765'

devices = dict(
    choppers = device('nicos_twin.devices.TwinSwitch',
        description = 'chopper mode: wfm (wavelength frame multiplication), natural (band-pass + T0), white (none)',
        twinurl = URL, twindevice = 'choppers', states = ['wfm', 'natural', 'white'],
    ),
    wfm_delta = device('nicos_twin.devices.TwinSwitch',
        description = 'separation of the two WFM discs: smaller = better resolution, less flux',
        twinurl = URL, twindevice = 'wfm_delta', states = [0.1, 0.3, 0.45], unit = 'm',
    ),
    shutter = device('nicos_twin.devices.TwinSwitch',
        description = 'experiment shutter, just upstream of the sample',
        twinurl = URL, twindevice = 'shutter', states = ['open', 'closed'],
    ),
    pinhole = device('nicos_twin.devices.TwinSwitch',
        description = 'side D of the square pinhole at 50 m (L = 10.5 m to the sample)',
        twinurl = URL, twindevice = 'pinhole', states = [0.01, 0.02, 0.03, 0.04], unit = 'm',
    ),
    diffuser = device('nicos_twin.devices.TwinSwitch',
        description = 'graphite diffuser after the pinhole',
        twinurl = URL, twindevice = 'diffuser', states = ['in', 'out'],
    ),
    stage_x = device('nicos_twin.devices.TwinMotor',
        description = 'horizontal sample translation (out of the beam: 500 mm)',
        twinurl = URL, twindevice = 'stage_x', unit = 'mm', scale = 1e-3, abslimits = (-500, 500),
    ),
    stage_rot = device('nicos_twin.devices.TwinMotor',
        description = 'sample rotation about the vertical axis',
        twinurl = URL, twindevice = 'stage_rot', unit = 'deg', scale = 1.0, abslimits = (-180, 180),
    ),
    sample_holder = device('nicos_twin.devices.TwinSampleChanger',
        description = 'sample mounted on the stage: built-in samples and your own (sample builder); sample_info()',
        twinurl = URL, twindevice = 'sample',
    ),
    det = device('nicos_twin.devices.TwinDetector',
        description = 'Timepix3 imaging detector of the twin (14 mm field of view); preset: t in seconds',
        twinurl = URL,
    ),
)

# With the EPICS layer (start_nicos.py --epics), the sample stage is driven as at ESS: through the EPICS motor records
# of the real instrument (served by the soft IOC of the twin, epics/ioc.py), with the motor class of ESS
if os.environ.get('TWIN_EPICS') == '1':
    for name, record in (('stage_x', 'ODIN-SpSt1:MC-LinY-01:Mtr'), ('stage_rot', 'ODIN-SpSt1:MC-RotZ-01:Mtr')):
        devices[name] = device('nicos_ess.devices.epics.pva.motor.EpicsMotor',
            description = devices[name][1]['description'] + ' (EPICS motor record %s)' % record,
            motorpv = record, monitor = True, pva = True, has_powerauto = False, has_errormsg = False,
            has_errorbit = False, has_reseterror = False,
        )

