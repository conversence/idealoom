"""Abstract the existence and use of ravenJS"""
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from configparser import ConfigParser
from sentry_sdk import (
    init as sentry_init, capture_message, capture_exception, configure_scope, Hub)
from sentry_sdk.integrations.pyramid import PyramidIntegration


def sentry_context(user_id=None, **kwargs):
    with configure_scope() as scope:
        if user_id:
            scope.user = {"id": user_id}
        if kwargs:
            for k, v in kwargs.items():
                if v is None:
                    continue
                scope.set_extra(k, v)


def flush(timeout=2.0):
    client = Hub.current.client
    if client is not None:
        client.flush(timeout=timeout)


def setup_raven(settings, settings_file=None):
    """Setup raven client.

    Sentry is automatically setup in assembl,
    this is useful for other processes."""

    if isinstance(settings, ConfigParser):
        raven_url = settings.get('app:idealoom', 'raven_url')
    else:
        raven_url = settings.get('raven_url', '')
    if raven_url and len(raven_url) > 12:
        sentry_init(
            raven_url,
            integrations=[PyramidIntegration()]
        )


def includeme(config):
    setup_raven(config.registry.settings)
