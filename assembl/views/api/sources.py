"""Cornice API for ContentSources"""
from pyramid.httpexceptions import HTTPNotFound
from pyramid.security import authenticated_userid, Everyone

from cornice import Service

from . import API_DISCUSSION_PREFIX

from assembl.models import Discussion

from assembl.auth import P_READ
from assembl.auth.util import get_permissions

sources = Service(
    name='sources',
    path=API_DISCUSSION_PREFIX + '/sources/',
    description="Manipulate a discussion's sources.",
    renderer='json',
)


@sources.get(permission=P_READ)
def get_sources(request):
    discussion = request.context
    view_def = request.GET.get('view') or 'default'

    if not discussion:
        raise HTTPNotFound(
            "Discussion with id '%s' not found." % discussion.id
        )

    user_id = authenticated_userid(request) or Everyone
    permissions = get_permissions(user_id, discussion.id)

    res = [source.generic_json(view_def, user_id, permissions)
           for source in discussion.sources]
    return [x for x in res if x is not None]
