""" Indirection layer to enable getting at the config while not littering the
codebase with thread-local access code. """
import logging

from pyramid.threadlocal import get_current_registry
from plaster_pastedeploy import ConfigDict

_settings = None
log = logging.getLogger()


def set_config(settings, reconfig=False):
    """ Set the settings object. """
    global _settings
    if reconfig or not _settings:
        _settings = settings
    else:
        _settings.update(settings)
        log.debug("combined settings:" + repr(_settings))
    return _settings


def get_config():
    """ Return the whole settings object. """
    global _settings
    return _settings or get_current_registry().settings


def get(name, default=None):
    """ Return a specific setting. """
    return get_config().get(name, default)


class CascadingSettings(ConfigDict):
    def __init__(self, config_dict):
        return super(CascadingSettings, self).__init__(
            config_dict.items(),
            getattr(config_dict, 'global_conf', {}),
            getattr(config_dict, 'loader', None))

    def get(self, key, default=None):
        r = super(CascadingSettings, self).get(key, self)
        if r is self:
            return self.global_conf.get(key, default)
        return r
