from simplejson import dumps, loads

from pyramid.view import view_config
from pyramid.httpexceptions import (HTTPNotFound, HTTPBadRequest)
from pyramid.security import authenticated_userid
from pyramid.response import Response

from assembl.auth import (
    Permissions, Everyone, CrudPermissions)
from assembl.models import (
    User, Discussion, TombstonableMixin)
from assembl.models.user_key_values import *
from . import JSON_HEADER
from ..traversal import (
    PreferenceContext, PreferenceValueContext)


@view_config(context=PreferenceContext, renderer='json',
             request_method='GET', permission=Permissions.READ)
def view_dict(request):
    preferences = request.context.preferences
    return dict(preferences)


@view_config(context=PreferenceContext, renderer='json',
             request_method='PATCH', permission=Permissions.READ)
def patch_dict(request):
    preferences = request.context.preferences
    if not isinstance(request.json, dict):
        raise HTTPBadRequest()
    ctx = request.context
    permissions = ctx.get_permissions()

    try:
        for k, v in request.json.items():
            if v is None:
                preferences.safe_del(k, permissions)
            else:
                preferences.safe_set(k, v, permissions)
    except KeyError:
        raise HTTPNotFound()
    except (AssertionError, ValueError) as e:
        raise HTTPBadRequest(e)
    return dict(preferences)


@view_config(context=PreferenceValueContext, renderer='json',
             request_method='GET', permission=Permissions.READ)
def get_value(request):
    ctx = request.context
    preferences = ctx.collection
    try:
        return preferences[ctx.key]
    except KeyError:
        raise HTTPNotFound()


@view_config(context=PreferenceValueContext, renderer='json',
             request_method='PUT', permission=Permissions.READ, header=JSON_HEADER)
def put_value(request):
    ctx = request.context
    value = request.json
    preferences = ctx.collection
    try:
        preferences.safe_set(ctx.key, value, ctx.get_permissions())
    except KeyError:
        raise HTTPNotFound()
    except (AssertionError, ValueError) as e:
        raise HTTPBadRequest(e)
    return Response(
        dumps(preferences[ctx.key]), status_code=201,
        content_type='application/json', charset="utf-8")


@view_config(context=PreferenceValueContext, renderer='json',
             request_method='DELETE', permission=Permissions.READ)
def del_value(request):
    ctx = request.context
    preferences = ctx.collection
    try:
        preferences.safe_del(ctx.key, ctx.get_permissions())
    except KeyError:
        raise HTTPNotFound()
    except (AssertionError, ValueError) as e:
        raise HTTPBadRequest(e)
    return {}
