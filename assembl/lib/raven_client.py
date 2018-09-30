"""Abstract the existence and use of ravenJS"""
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
import logging
from traceback import print_exc
import configparser
from raven.transport.threaded_requests import ThreadedRequestsHTTPTransport


log = logging.getLogger(__name__)

Raven = None


def capture_message(*args, **kwargs):
    global Raven
    if Raven:
        Raven.captureMessage(*args, **kwargs)
    else:
        print(*args, **kwargs)


def capture_exception(*args, **kwargs):
    global Raven
    if Raven:
        Raven.captureException(*args, **kwargs)
    else:
        print_exc()


def setup_raven(settings, settings_file=None):
    """Setup raven client.

    Raven is automatically setup in assembl,
    this is useful for other processes."""
    global Raven
    if Raven is not None:
        log.error("Calling setup_raven when raven is already set up.")
        return
    if isinstance(settings, configparser.ConfigParser):
        raven_url = settings.get('app:idealoom', 'raven_url')
    else:
        raven_url = settings.get('raven_url', '')
    if raven_url and len(raven_url) > 12:
        from raven.base import Raven as libRaven
        Raven = libRaven
        if not Raven:
            if not isinstance(settings, configparser.ConfigParser):
                settings_file = settings_file or settings.get('config_uri', None)
                assert settings_file
                settings = configparser.SafeConfigParser()
                settings.read(settings_file)
            raven_dsn = settings.get('filter:raven', 'dsn')
            from raven import Client
            Raven = Client(raven_dsn, transport=ThreadedRequestsHTTPTransport)
    if Raven:
        dsns = list(Raven._transport_cache.keys())
        if any((Raven._transport_cache[dsn]._transport_cls != ThreadedRequestsHTTPTransport for dsn in dsns)):
            Raven._transport_cache.clear()
            for dsn in dsns:
                Raven.set_dsn(dsn, ThreadedRequestsHTTPTransport)


def includeme(config):
    setup_raven(config.registry.settings)
