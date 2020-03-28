"""Cornice API for Synthesis"""
import json

from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest
from pyramid.security import authenticated_userid, Everyone
from cornice import Service

from . import API_DISCUSSION_PREFIX
from assembl.auth import P_READ, P_EDIT_SYNTHESIS
from assembl.auth.util import get_permissions
from assembl.models import Synthesis, LangString


syntheses = Service(name='syntheses',
    path=API_DISCUSSION_PREFIX + '/explicit_subgraphs/synthesis',
    description="List of synthesis", renderer='json')

synthesis = Service(name='ExplicitSubgraphs',
    path=API_DISCUSSION_PREFIX + '/explicit_subgraphs/synthesis/{id:.+}',
    description="Manipulate a single synthesis", renderer='json')


@syntheses.get(permission=P_READ)
def get_syntheses(request):
    discussion = request.context
    user_id = authenticated_userid(request) or Everyone
    syntheses = discussion.get_all_syntheses_query()
    view_def = request.GET.get('view') or 'default'
    res = [synthesis.generic_json(view_def, user_id, request.permissions)
           for synthesis in syntheses]
    return [x for x in res if x is not None]


@synthesis.get(permission=P_READ)
def get_synthesis(request):
    synthesis_id = request.matchdict['id']
    discussion = request.context
    if synthesis_id == 'next_synthesis':
        synthesis = discussion.get_next_synthesis()
    else:
        synthesis = Synthesis.get_instance(synthesis_id)
    if not synthesis:
        raise HTTPNotFound("Synthesis with id '%s' not found." % synthesis_id)

    view_def = request.GET.get('view') or 'default'
    user_id = authenticated_userid(request) or Everyone

    return synthesis.generic_json(view_def, user_id, request.permissions)


# Update
@synthesis.put(permission=P_EDIT_SYNTHESIS)
def save_synthesis(request):
    synthesis_id = request.matchdict['id']
    discussion = request.context
    if synthesis_id == 'next_synthesis':
        synthesis = discussion.get_next_synthesis()
    else:
        synthesis = Synthesis.get_instance(synthesis_id)
    if not synthesis:
        raise HTTPBadRequest("Synthesis with id '%s' not found." % synthesis_id)

    ctx = synthesis.get_instance_context(request=request)
    synthesis_data = json.loads(request.body)
    user_id = authenticated_userid(request)
    permissions = get_permissions(user_id, discussion.id, synthesis)

    for key in ('subject', 'introduction', 'conclusion'):
        if key in synthesis_data:
            current = getattr(synthesis, key)
            ls_data = synthesis_data[key]
            subcontext = synthesis.get_collection_context(key, ctx)
            if ls_data:
                assert isinstance(ls_data, dict)
            if current:
                if ls_data:
                    current.update_from_json(
                        ls_data, context=subcontext, permissions=permissions)
                else:
                    current.delete()
            elif ls_data:
                current = LangString.create_from_json(ls_data, context=subcontext)
                setattr(synthesis, key, current._instance)

    Synthesis.default_db.add(synthesis)
    Synthesis.default_db.flush()

    return {'ok': True, 'id': synthesis.uri()}
