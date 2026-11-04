description = 'poller of the LoKI digital twin: reads the devices regularly and puts their values in the cache (GUI)'
group = 'special'

sysconfig = dict(
    cache = 'localhost'
)

devices = dict(
    Poller = device('nicos.services.poller.Poller',
        alwayspoll = ['loki'],
        neverpoll = [],
        blacklist = ['det'],      # the detector is read by the counts themselves
    ),
)
