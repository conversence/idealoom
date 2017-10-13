"""This module contains view_defs, each of which specifies how to represent model instances in JSON.

They are used by :py:meth:`assembl.lib.sqla.BaseOps.generic_json`. There is also a reverse view_def,
which allows to specify how to create/update the instance from the JSON. The view_def syntax follows.

generic syntax: { "name": "property:viewdef" }

variants:

  - { "name": false } -> nothing.
  - { "name": "literal_property" } -> { "name": "property:literal" }
  - { "name": "relation" } -> { "name": "relation:@id" }
  - { "name": "relation:" } -> { "name": "relation:<same viewdef>" }
  - { "property": true } -> { "property": "property:literal or @id" }
  - { "property": ":viewdef" } -> { "property": "property:viewdef" }
  - { "name": ["relation:viewdef"] } will give the relation as an array in all cases.
      Same shortcuts apply (ommitting relation or same viewdef.) In particular:
  - { "name": [true] } will give an array of @id.
  - { "name": {"@id":"relation:viewdef"} } will give the relation as a dict, indexed by @id.
      Same shortcuts apply (ommitting relation or same viewdef. No viewdef makes no sense.)
  - { "name": "&method_name:viewdef" } will call the method with no arguments.
      DANGER! PLEASE RETURN JSON or a Base object (in which case viewdef or url applies.)
  - { "name": "'<json literal>"} This allows to specify literal values.

``@id``, ``@type`` and ``@view`` will always be defined.
Unspecified relation will be given as URL
Unspecified literal attribute will be present (unless also given as relation.)
Unspecified back relation will be ommitted.

IDs will always take the form ``local:<classname>/<object_id>``
"""

import traceback
from os.path import exists, join, dirname, getmtime

import simplejson
from pyramid.settings import asbool

_def_cache = {}
_cache_age = {}
_check_modified = False


def get_view_def(name):
    global _def_cache, _check_modified, _cache_age
    if name in _def_cache and not _check_modified:
        return _def_cache[name]

    fname = join(dirname(__file__), name+".json")
    if _check_modified:
        modified = getmtime(fname)
        previous = _cache_age.get(name, 0)
        if modified > previous:
            _def_cache.pop(name, None)
        _cache_age[name] = modified
    if name not in _def_cache:
        try:
            with open(fname) as f:
                _def_cache[name] = simplejson.load(f)
        except:
            traceback.print_exc()
    return _def_cache.get(name, None)


def includeme(config):
    global _check_modified
    _check_modified = not asbool(config.registry.settings.get('cache_viewdefs', True))
