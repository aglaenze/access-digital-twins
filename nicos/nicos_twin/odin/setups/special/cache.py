import os

description = 'cache server of the ODIN digital twin'
group = 'special'

devices = dict(
    DB = device('nicos.services.cache.database.FlatfileCacheDatabase',
        storepath = os.environ.get('TWIN_RUN_ROOT', os.path.expanduser('~/McStas_runs/twin')) + '/nicos/odin/cache',
        loglevel = 'info',
    ),
    Server = device('nicos.services.cache.server.CacheServer',
        db = 'DB',
        server = 'localhost',
        loglevel = 'info',
    ),
)
