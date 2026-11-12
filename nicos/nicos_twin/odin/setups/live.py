description = 'Live data, as at ESS: the twin streams its neutrons to Kafka, just-bin-it histograms them'
group = 'optional'

# Needs the Kafka broker and just-bin-it of the twin (python nicos/start_nicos.py --live, or kafka/start_kafka.py and
# just-bin-it started by hand). Devices of the ESS NICOS (nicos_ess.devices.datasources.just_bin_it), configured as
# for YMIR (nicos_ess/ymir/setups/just-bin-it.py); jbi: the ESS JustBinItDetector with an explicit time window
# (nicos_twin.devices.TwinJustBinItDetector), listed first so that just-bin-it is configured before the stream.
# The twin streams the Timepix3 pixels grouped in blocks of 32 x 32 (128 x 128 superpixels, ids 1..16384) to keep
# the live histograms small; the files keep the full pixels.
# source = 'odin_detector': only these superpixel events; with the ESS file-writer (filewriter/), the twin also
# publishes the full pixels on the same topic, as source 'timepix3' (the name in the real ODIN file).
BROKERS = ['127.0.0.1:9092']

devices = dict(
    live_image = device('nicos_twin.devices.TwinJustBinItImage',
        description = 'live detector image (128 x 128 superpixels of 32 x 32 Timepix3 pixels)',
        hist_topic = 'odin_visualisation', data_topic = 'odin_detector', source = 'odin_detector',
        brokers = BROKERS,
        unit = 'evts', hist_type = '2-D DET', det_width = 128, det_height = 128, det_range = (1, 16385),
    ),
    live_tof = device('nicos_twin.devices.TwinJustBinItImage',
        description = 'live spectrum of the arrival times after the source pulse (0-71.4 ms)',
        hist_topic = 'odin_visualisation', data_topic = 'odin_detector', source = 'odin_detector',
        brokers = BROKERS,
        unit = 'evts', hist_type = '1-D TOF', tof_range = (0, 71428571), num_bins = 300, det_range = (1, 16385),
    ),
    jbi = device('nicos_twin.devices.TwinJustBinItDetector',
        description = 'the just-bin-it histogrammer (live data)',
        brokers = BROKERS, unit = '',
        command_topic = 'odin_jbi_commands', response_topic = 'odin_jbi_responses',
        statustopic = 'odin_jbi_heartbeat', images = ['live_image', 'live_tof'],
        hist_schema = 'hs01', event_schema = 'ev44', liveinterval = 1,
    ),
)

startupcode = '''
det.stream = True
SetDetectors(jbi, det)
printinfo("Live data on: during a count the image and the arrival-time spectrum fill up (tab Detector image).")
'''
