description = 'Live data, as at ESS: the twin streams its neutrons to Kafka, just-bin-it histograms them'
group = 'optional'

# Needs the Kafka broker and just-bin-it of the twin (python nicos/start_nicos.py --instrument loki --live). Devices of
# the ESS NICOS (nicos_ess.devices.datasources.just_bin_it); jbi: the ESS JustBinItDetector with an explicit time
# window (nicos_twin.devices.TwinJustBinItDetector), listed first so that just-bin-it is configured before the stream.
# The twin streams the neutrons of the rear detector panel (392 x 250 pixels, ids 1 + row * 250 + column), a random
# sample of them (at most 1e5 per second: a LoKI measurement gives millions per second); the file holds everything.
BROKERS = ['127.0.0.1:9092']

devices = dict(
    live_image = device('nicos_ess.devices.datasources.just_bin_it.JustBinItImage',
        description = 'live image of the rear detector panel (sample of the neutrons)',
        hist_topic = 'loki_visualisation', data_topic = 'loki_detector', brokers = BROKERS,
        unit = 'evts', hist_type = '2-D DET', det_width = 250, det_height = 392, det_range = (1, 98001),
    ),
    live_tof = device('nicos_ess.devices.datasources.just_bin_it.JustBinItImage',
        description = 'live spectrum of the arrival times after the source pulse (0-71.4 ms), rear panel',
        hist_topic = 'loki_visualisation', data_topic = 'loki_detector', brokers = BROKERS,
        unit = 'evts', hist_type = '1-D TOF', tof_range = (0, 71428571), num_bins = 300, det_range = (1, 98001),
    ),
    jbi = device('nicos_twin.devices.TwinJustBinItDetector',
        description = 'the just-bin-it histogrammer (live data)',
        brokers = BROKERS, unit = '',
        command_topic = 'loki_jbi_commands', response_topic = 'loki_jbi_responses',
        statustopic = 'loki_jbi_heartbeat', images = ['live_image', 'live_tof'],
        hist_schema = 'hs01', event_schema = 'ev44', liveinterval = 1,
    ),
)

startupcode = '''
det.stream = True
SetDetectors(jbi, det)
printinfo("Live data on: during a count the image of the rear panel and the arrival-time spectrum fill up (tab "
          "Detector image); they show a sample of the neutrons (at most 100 000 per second), the file holds all.")
'''
