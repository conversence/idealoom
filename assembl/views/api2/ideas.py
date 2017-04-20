from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPUnauthorized)
from pyramid.security import authenticated_userid, Everyone

from ..traversal import (InstanceContext)
from assembl.auth import (CrudPermissions, P_EDIT_IDEA)
from assembl.models import (Idea)


@view_config(context=InstanceContext, request_method='DELETE', renderer='json',
             ctx_instance_class=Idea, permission=P_EDIT_IDEA)
def instance_del(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    idea = ctx._instance
    if not idea.user_can(user_id, CrudPermissions.DELETE, request.permissions):
        raise HTTPUnauthorized()
    for link in idea.source_links:
        link.is_tombstone = True
    idea.is_tombstone = True

    return {}
