description = 'execution daemon of the LoKI digital twin'
group = 'special'

import hashlib

devices = dict(
    Auth = device('nicos.services.daemon.auth.list.Authenticator',
        hashing = 'sha1',
        # Local teaching accounts (the daemon only listens on this computer: server = 'localhost')
        passwd = [
            ('guest', '', 'guest'),
            ('student', hashlib.sha1(b'student').hexdigest(), 'user'),
            ('admin', hashlib.sha1(b'admin').hexdigest(), 'admin'),
        ],
    ),
    Daemon = device('nicos.services.daemon.NicosDaemon',
        authenticators = ['Auth'],
        loglevel = 'info',
        server = 'localhost',
    ),
)
