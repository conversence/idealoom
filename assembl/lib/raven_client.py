"""Abstract the existence and use of ravenJS"""
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from configparser import ConfigParser
from sentry_sdk import (
    init as sentry_init, capture_message, capture_exception, configure_scope, Hub)
from sentry_sdk.integrations.pyramid import PyramidIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from ..__version__ import version


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


def setup_raven(settings, settings_file=None, use_async=False, celery=False):
    """Setup raven client.

    Sentry is automatically setup in assembl,
    this is useful for other processes."""

    if isinstance(settings, ConfigParser):
        raven_url = settings.get('app:idealoom', 'raven_url')
    else:
        raven_url = settings.get('raven_url', '')
    if raven_url and len(raven_url) > 12:
        integrations = integrations = [
            PyramidIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ]
        if use_async:
            from sentry_sdk.integrations.aiohttp import AioHttpIntegration
            integrations.append(AioHttpIntegration())
        if celery:
            from sentry_sdk.integrations.celery import CeleryIntegration
            integrations.append(CeleryIntegration())

        sentry_init(
            raven_url, integrations=integrations, release=version(),
            server_name=settings.get('app:idealoom', 'public_hostname'))


def includeme(config):
    setup_raven(config.registry.settings)
