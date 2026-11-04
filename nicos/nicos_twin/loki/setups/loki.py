description = 'LoKI digital twin: devices (each one relays its orders to the twin server)'
group = 'basic'

includes = ['system']

URL = 'http://127.0.0.1:8765'

# Names as in nicos_ess/loki/setups (the NICOS of the real LoKI) where they exist: heavy_shutter, fast_shutter.
devices = dict(
    heavy_shutter = device('nicos_twin.devices.TwinSwitch',
        description = 'Main shutter',
        twinurl = URL, twindevice = 'heavy_shutter', states = ['Open', 'Closed'],
        mapping = {'Open': 'open', 'Closed': 'closed'},
    ),
    fast_shutter = device('nicos_twin.devices.TwinSwitch',
        description = 'Shutter just before the sample',
        twinurl = URL, twindevice = 'shutter', states = ['Open', 'Closed'],
        mapping = {'Open': 'open', 'Closed': 'closed'},
    ),
    collimation = device('nicos_twin.devices.TwinSwitch',
        description = 'collimation length (the rear detector distance follows: 5 m for 3 m)',
        twinurl = URL, twindevice = 'collimation', states = ['3m'],
    ),
    sample_holder = device('nicos_twin.devices.TwinSwitch',
        description = 'sample in the beam (1 mm cell)',
        twinurl = URL, twindevice = 'sample', states = ['silica_spheres'],
    ),
    det = device('nicos_twin.devices.TwinDetector',
        description = 'the 9 tube panels of LoKI; image: rear panel; preset: t in seconds',
        twinurl = URL, imageshape = (392, 250),
    ),
)
