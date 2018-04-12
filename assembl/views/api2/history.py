from future import standard_library
standard_library.install_aliases()
from urllib.parse import urlencode
from datetime import datetime

from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPUnauthorized, HTTPBadRequest, HTTPSeeOther, HTTPNotAcceptable,
    HTTPInternalServerError)
from pyramid.security import authenticated_userid, Everyone
from pyramid.response import Response
from pyramid.renderers import render

from assembl.lib.parsedatetime import parse_datetime
from ..traversal import InstanceContext
from assembl.auth import (CrudPermissions, P_READ)
from assembl.lib.history_mixin import (
    OriginMixin, HistoryMixin, HistoryMixinWithOrigin, HistoricalProxy)


RFC1123 = "%a, %d %b %Y %H:%M:%S GMT"
LINK = '<%s>; rel="%s"'
LLINK = 'Link: ' + LINK
LINKDT = LINK+'; datetime="%s"'

def links_as_headers(links):
    return ["Link: <%s>;rel=%s" % (v, k) for (k, v) in links.items()]


@view_config(context=InstanceContext, name="timegate",
             request_method='GET', accept="application/json")
def timegate(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    request.logger().info('timegate', instance=instance, _name='assembl.views.api2')
    if not instance.user_can(user_id, CrudPermissions.READ, permissions):
        raise HTTPUnauthorized()
    ts = request.GET.get('ts', None)
    if ts:
        try:
            ts = parse_datetime(ts, True)  # iso 8601
        except Error as e:
            raise HTTPBadRequest(e)
        hproxy = HistoricalProxy.proxy_instance(instance, ts)
        if not hproxy:
            if isinstance(instance, OriginMixin):
                if instance.creation_date > ts:
                    raise HTTPNotAcceptable("Too early: resource starts at " +
                        instance.creation_date.strftime(RFC1123))
            raise HTTPInternalServerError()
        # Not sure about this.
        if isinstance(instance, (HistoryMixin, OriginMixin)):
            # TODO: valid_from needs to look at dependent objects.
            valid_from = hproxy.valid_from()
            if valid_from != ts:
                args = dict(request.GET)
                args['ts'] = valid_from.isoformat()
                return HTTPSeeOther(request.path_url+"?"+urlencode(args))
        view = ctx.get_default_view() or 'default'
        view = request.GET.get('view', view)
        json = hproxy.generic_json(view, user_id, permissions)
        links = [
            ("Link", LINK % (request.path_url[:-9], 'original'))
        ]
        json = render("json", json, request)
        resp = Response(json, content_type="application/json", charset="utf-8")
        resp.headerlist.extend(links)
        return resp
    else:
        ts = request.headers.get('accept-datetime', None)
        if not ts:
            return HTTPBadRequest("please specify Accept-Datetime")
        try:
            ts = datetime.strptime(ts, RFC1123)
        except Error as e:
            raise HTTPBadRequest(e)
        hproxy = HistoricalProxy.proxy_instance(instance, ts)
        if isinstance(instance, (HistoryMixin, OriginMixin)):
            ts = hproxy.valid_from()
        args = dict(request.GET)
        args['ts'] = valid_from.isoformat()
        return HTTPSeeOther(request.path_url+"?"+urlencode(args))


@view_config(context=InstanceContext, renderer='json', name="timemap",
             request_method='GET')
def timemap(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    request.logger().info('timemap', instance=instance, _name='assembl.views.api2')
    if not instance.user_can(user_id, CrudPermissions.READ, permissions):
        raise HTTPUnauthorized()
    base_url = request.path_url[:-8]
    timegate = base_url + "/timegate"
    timegatets = timegate + "?ts="
    start_dates = instance.start_dates()
    links = [
        LINK % (base_url, "original"),
        LINK % (timegate, "timegate"),
        LINK % (request.path_url, "self") + "; ".join(('',
            'type="application/link-format"',
            'from="%s"' % start_dates[0].strftime(RFC1123),
            'until="%s"' % datetime.now().strftime(RFC1123))),
    ]
    for (i, ts) in enumerate(start_dates):
        if i == 0:
            rel = "first memento"
        elif i == len(start_dates) - 1:
            rel = "last memento"
        else:
            rel = "memento"
        links.append(LINKDT % (timegatets+ts.isoformat(), rel, ts.strftime(RFC1123)))
    return Response(",\n".join(links).encode('ascii'), content_type="application/link-format")

