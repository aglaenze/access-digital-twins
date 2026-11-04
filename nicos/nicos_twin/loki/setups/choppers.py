description = 'LoKI choppers (read-only): speed and opening delays, as set by the collimation configuration'
group = 'lowlevel'

URL = 'http://127.0.0.1:8765'

# Two pairs of discs in the official McStas model: bandwidth chopper (ch1, 6.5 m from the source) and frame-overlap
# chopper (ch2, 15.21 m). The NICOS of the real LoKI names them ch1_speed, ch1_phase... (nicos_ess/loki/setups/
# chopper_1.py); the twin shows the delay of each disc (a, b) after the source pulse, computed from the wavelength
# band with the formulas of the model (includes/loki_functions.c).
devices = dict(
    ch1_speed = device('nicos_twin.devices.TwinReadable',
        description = 'rotation speed of the bandwidth chopper',
        twinurl = URL, twindevice = 'ch1_speed', unit = 'Hz', fmtstr = '%.1f',
        maxage = 5, pollinterval = 2,
    ),
    ch1a_delay = device('nicos_twin.devices.TwinReadable',
        description = 'opening delay of disc a of the bandwidth chopper after the source pulse',
        twinurl = URL, twindevice = 'ch1a_delay', unit = 'ms', fmtstr = '%.3f',
        maxage = 5, pollinterval = 2,
    ),
    ch1b_delay = device('nicos_twin.devices.TwinReadable',
        description = 'opening delay of disc b of the bandwidth chopper after the source pulse',
        twinurl = URL, twindevice = 'ch1b_delay', unit = 'ms', fmtstr = '%.3f',
        maxage = 5, pollinterval = 2,
    ),
    ch2_speed = device('nicos_twin.devices.TwinReadable',
        description = 'rotation speed of the frame-overlap chopper',
        twinurl = URL, twindevice = 'ch2_speed', unit = 'Hz', fmtstr = '%.1f',
        maxage = 5, pollinterval = 2,
    ),
    ch2a_delay = device('nicos_twin.devices.TwinReadable',
        description = 'opening delay of disc a of the frame-overlap chopper after the source pulse',
        twinurl = URL, twindevice = 'ch2a_delay', unit = 'ms', fmtstr = '%.3f',
        maxage = 5, pollinterval = 2,
    ),
    ch2b_delay = device('nicos_twin.devices.TwinReadable',
        description = 'opening delay of disc b of the frame-overlap chopper after the source pulse',
        twinurl = URL, twindevice = 'ch2b_delay', unit = 'ms', fmtstr = '%.3f',
        maxage = 5, pollinterval = 2,
    ),
    wavelength_band = device('nicos_twin.devices.TwinReadable',
        description = 'wavelength band let through by the choppers',
        twinurl = URL, twindevice = 'wavelength_band', fmtstr = '%s',
        maxage = 5, pollinterval = 2,
    ),
)
