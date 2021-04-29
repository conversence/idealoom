"""Background tasks for running IdeaLoom.

Tasks are kept running by Circus_.
Short-lived tasks are written as Celery_ tasks; long-running tasks are
mostly ad hoc at this point: the :py:mod:`source_reader`
and :py:mod:`changes_router`.

.. _Circus: http://circus.readthedocs.io/en/latest/
.. _Celery: http://www.celeryproject.org/
"""
from __future__ import absolute_import

from future import standard_library
standard_library.install_aliases()
standard_library.install_hooks()
from os import getcwd
from os.path import join, dirname, realpath, exists
import logging
import configparser

from pyramid.paster import get_appsettings
from pyramid.path import DottedNameResolver
from datetime import timedelta
from celery import Celery
from pyramid_mailer import mailer_factory_from_settings

from ..lib.sqla import configure_engine
from ..lib.zmqlib import configure_zmq
from ..lib.raven_client import setup_raven
from ..lib.config import get, set_config
from zope.component import getGlobalSiteManager
from ..lib.model_watcher import configure_model_watcher
from ..lib.logging import getLogger


_settings = None
log = logging.getLogger(__name__)
resolver = DottedNameResolver(__package__)


def configure(registry, task_name):
    global _settings, celery
    from .threaded_model_watcher import configure_threaded_watcher
    settings = registry.settings
    if _settings is None:
        _settings = settings
    # temporary solution
    configure_threaded_watcher(settings)
    configure_model_watcher(registry, task_name)
    region = get('aws_region', 'us-east-1')
    config = {
        "task_serializer": 'json',
        "task_acks_late": True,
        "cache_backend": settings.get('celery_tasks.broker', ''),
        "result_backend": settings.get('celery_tasks.broker', ''),
        "task_store_errors_even_if_ignored": True,
        "broker_transport_options": {'region': region},
    }
    config['broker_url'] = settings.get('celery_tasks.broker')
    celery.config_from_object(config, force=True)


CELERYBEAT_SCHEDULE = {
    'resend-every-10-minutes': {
        'task': 'assembl.tasks.notify.process_pending_notifications',
        'schedule': timedelta(seconds=600),
        'options': {
            'routing_key': 'notify',
            'exchange': 'notify'
        }
    },
}

# Minimum delay between emails sent to a domain.
# For this to work, you need to have a SINGLE celery process for notification.
SMTP_DOMAIN_DELAYS = {
    '': timedelta(0)
}

# INI file values with this prefix will be used to populate SMTP_DOMAIN_DELAYS.
# Anything after the last dot is a domain name (including empty).
# Use seconds (float) as values.
SETTINGS_SMTP_DELAY = "celery_tasks.notify.smtp_delay."


class CeleryWithConfig(Celery):
    "A Celery task that can receive settings"

    _preconf = {
        "CELERYBEAT_SCHEDULE": CELERYBEAT_SCHEDULE
    }

    def on_configure(self):
        global _settings
        if _settings is None:
            # i.e. includeme not called, i.e. not from pyramid
            self.init_from_celery()

    def init_from_celery(self):
        # A task is called through celery, so it may not have basic
        # configuration setup. Go through that setup the first time.
        global _settings, SMTP_DOMAIN_DELAYS
        rootdir = getcwd()
        settings_file = join(rootdir, 'local.ini')
        if not exists(settings_file):
            settings_file = join(rootdir, 'production.ini')
        if not exists(settings_file):
            rootdir = dirname(dirname(dirname(realpath(__file__))))
            settings_file = join(rootdir, 'local.ini')
        if not exists(settings_file):
            settings_file = join(rootdir, 'production.ini')
        if not exists(settings_file):
            raise RuntimeError("Missing settings file")
        _settings = settings = get_appsettings(settings_file, 'idealoom')
        configure_zmq(settings['changes_socket'], False)
        config = configparser.SafeConfigParser()
        config.read(settings_file)
        registry = getGlobalSiteManager()
        registry.settings = settings
        setup_raven(settings, settings_file, celery=True)
        set_config(settings)
        configure_engine(settings, True)
        if settings.get('celery_tasks_debug_signal', False):
            from assembl.lib import signals
            signals.listen()
        configure(registry, 'celery_tasks')
        from .threaded_model_watcher import ThreadDispatcher
        threaded_watcher_class_name = settings.get(
            'celery_tasks.threadedmodelwatcher',
            "assembl.lib.model_watcher.BaseModelEventWatcher")
        ThreadDispatcher.mw_class = resolver.resolve(
            threaded_watcher_class_name)
        self.mailer = mailer_factory_from_settings(settings)
        # setup SETTINGS_SMTP_DELAY
        for name, val in settings.items():
            if name.startswith(SETTINGS_SMTP_DELAY):
                try:
                    val = timedelta(seconds=float(val))
                except ValueError:
                    log.error("Not a valid value for %s: %s" % (name, val))
                    continue
                SMTP_DOMAIN_DELAYS[name[len(SETTINGS_SMTP_DELAY):]] = val
        getLogger().info("SMTP_DOMAIN_DELAYS", delays=SMTP_DOMAIN_DELAYS)
        import assembl.tasks.imap
        import assembl.tasks.notify
        import assembl.tasks.notification_dispatch
        import assembl.tasks.translate


celery = CeleryWithConfig('celery_tasks')


def includeme(config):
    global _settings
    _settings = config.registry.settings
    config.include('.threaded_model_watcher')
    configure(config.registry, 'idealoom')
    config.include('.source_reader')
