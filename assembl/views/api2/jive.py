import simplejson as json
from pyramid.view import view_config
from pyramid.security import authenticated_userid
from pyramid.httpexceptions import HTTPUnauthorized

from assembl.models import JiveGroupSource
from assembl.models.jive.setup import (jive_addon_registration_route,
                                       jive_addon_creation,
                                       compress)
from assembl.auth import P_READ, Everyone
from assembl.auth.util import get_permissions
from ..traversal import InstanceContext
from . import JSON_HEADER


@view_config(context=InstanceContext, request_method='POST',
             ctx_instance_class=JiveGroupSource, permission=P_READ,
             renderer='json', name=jive_addon_creation)
def generate_jive_addon(request):
    # Instead of storing the zip file locally, use a StringIO object
    # Add the UUID in a db setting somewhere - look in user_key_values
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = get_permissions(user_id, ctx.get_discussion_id())
    if P_READ not in permissions:
        raise HTTPUnauthorized("Only a registered user can request for\
            this resource. Please sign up to continue")
    # get the full URL here and call compress
    zipfile = compress('full-path-of-resource')
    return zipfile


@view_config(context=InstanceContext, request_method='POST',
             ctx_instance_class=JiveGroupSource, header=JSON_HEADER,
             renderer='json', name=jive_addon_registration_route)
def register_jive_addon(request):
    data = request.json_body
    if not data:
        # TODO: Log this as a failure!
        return {'error': 'There was no discussion sent'}
    ctx = request.context
    source = ctx._instance
    db = JiveGroupSource.default_db

    # TODO: Ensure this is from a genuine Jive instance
    # https://community.jivesoftware.com/docs/DOC-99941
    json_data = json.dumps(data)
    source.settings = json_data
    db.add(source)
    db.flush()  # is this even necessary?
