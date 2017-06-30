from collections import OrderedDict
from plaster_pastedeploy import Loader as pLoader
from plaster_pastedeploy.compat import configparser


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
        if self.pastedeploy_scheme != 'config':
            return {}
        # defaults = self._get_defaults(defaults)
        parser = self._get_parser(defaults=defaults)
        try:
            d = OrderedDict(parser._sections.get(section, None))
            d.pop('__name__')
            return d
        except configparser.NoSectionError:
            return {}
