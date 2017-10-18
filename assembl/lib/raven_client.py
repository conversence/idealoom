"""Abstract the existence and use of ravenJS"""
from future import standard_library
standard_library.install_aliases()
import logging
from traceback import print_exc
import configparser
from raven.transport.threaded_requests import ThreadedRequestsHTTPTransport


_raven_client = None
log = logging.getLogger(__name__)


def get_raven_client():
    from raven.base import Raven
    return Raven or _raven_client


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
    global _raven_client
    if _raven_client is not None:
        log.error("Calling setup_raven when raven is already set up.")
        return
    try:
        pipeline = settings.get('pipeline:main', 'pipeline').split()
        if 'raven' in pipeline:
            raven_dsn = settings.get('filter:raven', 'dsn')
            from raven import Client
            _raven_client = Client(
                raven_dsn, transport=ThreadedRequestsHTTPTransport)
    except configparser.Error:
        pass
