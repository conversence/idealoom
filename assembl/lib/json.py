""" JSON-related utilities. """

from __future__ import absolute_import

from datetime import date, datetime
from simplejson import dumps, JSONEncoder


class DateJSONEncoder(JSONEncoder):
    """A JSONEncoder that can encode datetime objects using iso8601"""
    def default(self, obj):
        if not isinstance(obj, (date, datetime)):
            return super(DateJSONEncoder, self).default(obj)
        if isinstance(obj, datetime) and obj.tzinfo:
            from pytz import UTC
            obj = obj.astimezone(UTC).replace(tzinfo=None)
        return obj.isoformat() + "Z"


def json_renderer_factory(info):
    """ Same factory from pyramid.renderers, but with a custom encoder. """
    def _render(value, system):
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'application/json'
        return dumps(value, cls=DateJSONEncoder)
    return _render
