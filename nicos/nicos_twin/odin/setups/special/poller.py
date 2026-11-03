description = 'poller of the ODIN digital twin: reads the devices regularly and puts their values in the cache (GUI)'
group = 'special'

sysconfig = dict(
    cache = 'localhost'
)

devices = dict(
    Poller = device('nicos.services.poller.Poller',
        alwayspoll = ['odin'],
        neverpoll = [],
        blacklist = ['det'],      # the detector is read by the counts themselves
    ),
)
