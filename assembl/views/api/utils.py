"""Utility APIs"""
from future import standard_library
standard_library.install_aliases()
from builtins import str
import re
from urllib.parse import urlparse
from os import path
from os.path import join, dirname

import requests
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid_dogpile_cache import get_region
from pyoembed import oEmbed

from assembl.lib import config
from assembl.models import File
from assembl.lib.config import get_config


dogpile_fname = join(
    dirname(dirname(dirname(dirname(__file__)))),
    get_config().get('dogpile_cache.arguments.filename'))

oembed_cache = get_region(
    'oembed', **{"arguments.filename": dogpile_fname})


@view_config(route_name='mime_type', request_method='HEAD',
             permission=NO_PERMISSION_REQUIRED)
def mime_type(request):
    url = request.params.get('url', None)
    if not url:
        raise HTTPBadRequest("Missing 'url' parameter")
    parsed = urlparse(url)
    if not parsed or parsed.scheme not in ('http', 'https'):
        raise HTTPBadRequest("Wrong scheme")
    if parsed.netloc.split(":")[0] == config.get('public_hostname'):
        # is it one of our own documents?
        # If so, detect it and shortcut to avoid the pyramid handler calling
        # another pyramid handler, as this exhausts pyramid threads rapidly
        # and can deadlock the whole application
        r = re.match(
            r'^https?://[\w\.]+(?:\:\d+)?/data/.*/documents/(\d+)/data(?:\?.*)?$',
            url)
        if r:
            document_id = r.groups(0)[0]
            from sqlalchemy.sql.functions import func
            mimetype, create_date, file_identity = File.default_db.query(
                File.mime_type, File.creation_date, File.file_identity
                ).filter_by(id=int(document_id)).first()
            size = path.getsize(File.path_of(file_identity))
            return Response(
                body=None, content_type=str(mimetype),
                content_length=size, last_modified=create_date)
    try:
        result = requests.head(url, timeout=15)
    except requests.ConnectionError:
        return Response(
            status=503,
            location=url)

    return Response(
        content_type=result.headers.get('Content-Type', None),
        status=result.status_code,
        location=result.url)


@oembed_cache.cache_on_arguments()
def oembed_cached(url, maxwidth=None, maxheight=None):
    return oEmbed(url, maxwidth=None, maxheight=maxheight)


@view_config(
    route_name='oembed', permission=NO_PERMISSION_REQUIRED, renderer='json')
def oembed(request):
    url = request.params.get('url', None)
    if not url:
        raise HTTPBadRequest("Please give a URL")
    maxheight = request.params.get('height', None)
    maxwidth = request.params.get('width', None)
    try:
        return oembed_cached(url, maxwidth, maxheight)
    except:
        # Cache failures
        return {}
