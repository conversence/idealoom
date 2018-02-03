from collections import OrderedDict
from plaster_pastedeploy import Loader as pLoader
try:
    from plaster_pastedeploy import NoSectionError
except ImportError:
    from plaster_pastedeploy.compat import configparser
    NoSectionError = configparser.NoSectionError


class Loader(pLoader):
    def get_settings(self, section=None, defaults=None):
        """
        Gets a named section from the configuration source.

        :param section: a :class:`str` representing the section you want to
            retrieve from the configuration source. If ``None`` this will
            fallback to the :attr:`plaster.PlasterURL.fragment`.
        :param defaults: a :class:`dict` that will get passed to
            :class:`configparser.ConfigParser` and will populate the
            ``DEFAULT`` section.
        :return: A :class:`collections.OrderedDict` with key value pairs as
            parsed by :class:`configparser.ConfigParser`.

        """
        section = self._maybe_get_default_name(section)
        if not self.pastedeploy_spec.startswith('config:'):
            return {}
        # defaults = self._get_defaults(defaults)
        parser = self._get_parser(defaults=defaults)
        try:
            d = OrderedDict(parser._sections.get(section, {}))
            d.pop('__name__', None)
            return d
        except NoSectionError:
            return {}
