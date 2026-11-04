description = 'LoKI digital twin: devices (each one relays its orders to the twin server)'
group = 'basic'

includes = ['system', 'choppers']

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
        description = 'collimation length: longer = smaller divergence (lower Q, better resolution), less flux',
        twinurl = URL, twindevice = 'collimation', states = ['3m', '5m', '8m'],
    ),
    pulse_skipping = device('nicos_twin.devices.TwinSwitch',
        description = 'on: choppers at 7 Hz, one source pulse in two, wavelength band 3-21.4 A (3 m collimation only)',
        twinurl = URL, twindevice = 'pulse_skipping', states = ['off', 'on'],
    ),
    detector_distance = device('nicos_twin.devices.TwinSwitch',
        description = 'distance sample -> rear detector bank (farther = lower Q)',
        twinurl = URL, twindevice = 'detector_distance', states = [5.0, 10.0], unit = 'm',
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
