"""Abstract the existence and use of ravenJS"""
from future import standard_library
standard_library.install_aliases()
import logging
from traceback import print_exc
import configparser
from raven.transport.threaded_requests import ThreadedRequestsHTTPTransport


log = logging.getLogger(__name__)


def get_raven_client():
    from raven.base import Raven
    if Raven:
        dsns = list(Raven._transport_cache.keys())
        if any((Raven._transport_cache[dsn]._transport_cls != ThreadedRequestsHTTPTransport for dsn in dsns)):
            Raven._transport_cache.clear()
            for dsn in dsns:
                Raven.set_dsn(dsn, ThreadedRequestsHTTPTransport)
        return Raven


def capture_message(*args, **kwargs):
    client = get_raven_client()
    if client:
        client.captureMessage(*args, **kwargs)


def capture_exception(*args, **kwargs):
    client = get_raven_client()
    if client:
        client.captureException(*args, **kwargs)
    else:
        print_exc()


def setup_raven(settings):
    """Setup raven client.

    Raven is automatically setup in assembl,
    this is useful for other processes."""
    from raven.base import Raven
    if Raven is not None:
        log.error("Calling setup_raven when raven is already set up.")
        return
    try:
        pipeline = settings.get('pipeline:main', 'pipeline').split()
        if 'raven' in pipeline:
            raven_dsn = settings.get('filter:raven', 'dsn')
            from raven import Client
            Client(raven_dsn, transport=ThreadedRequestsHTTPTransport)
    except configparser.Error:
        pass
