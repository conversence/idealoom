from pyramid.view import view_config
from pyramid.httpexceptions import (HTTPBadRequest, HTTPNotFound)
from pyramid.response import Response
from pyramid.security import authenticated_userid, Everyone
from pyramid.settings import asbool
import simplejson as json

from assembl.auth import (P_READ, P_EDIT_SYNTHESIS, CrudPermissions)
from assembl.models import (
    Discussion, Idea, SubGraphIdeaAssociation, Synthesis,
    LanguagePreferenceCollection)
from ..traversal import InstanceContext, CollectionContext
from . import check_permissions


@view_config(context=InstanceContext, renderer='json', request_method='GET',
             ctx_instance_class=Discussion, permission=P_READ,
             accept="application/json", name="notifications")
def discussion_notifications(request):
    return list(request.context._instance.get_notifications())


@view_config(context=CollectionContext, renderer='json', request_method='GET',
             ctx_named_collection="Discussion.syntheses", permission=P_READ,
             accept="application/json")
def get_syntheses(request, default_view='default'):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    check_permissions(ctx, user_id, CrudPermissions.READ, Synthesis)
    include_unpublished = P_EDIT_SYNTHESIS in permissions
    view = request.GET.get('view', None) or ctx.get_default_view() or default_view
    include_tombstones = asbool(request.GET.get('tombstones', False))
    discussion = ctx.get_instance_of_class(Discussion)
    q = discussion.get_all_syntheses_query(
        include_unpublished=include_unpublished,
        include_tombstones=include_tombstones)
    if view == 'id_only':
        q = q.with_entities(Synthesis.id)
        return [ctx.collection_class.uri_generic(x) for (x,) in q.all()]
    else:
        res = [i.generic_json(view, user_id, permissions) for i in q.all()]
        return [x for x in res if x is not None]


@view_config(context=CollectionContext, renderer='json', request_method='POST',
             ctx_named_collection="ExplicitSubGraphView.ideas",
             permission=P_EDIT_SYNTHESIS, accept="application/json")
def add_idea_to_synthesis(request):
    """Add an idea to an ExplictSubgraphView"""
    ctx = request.context
    graph_view = ctx.parent_instance
    if isinstance(graph_view, Synthesis) and not graph_view.is_next_synthesis:
        raise HTTPBadRequest("Synthesis is published")
    content = request.json
    idea_id = content.get('@id', None)
    if not idea_id:
        raise HTTPBadRequest("Post an idea with its @id")
    idea = Idea.get_instance(idea_id)
    if not idea:
        raise HTTPNotFound("Unknown idea")
    link = SubGraphIdeaAssociation(idea=idea, sub_graph=graph_view)
    duplicate = link.find_duplicate(False)
    if duplicate:
        link.db.expunge(link)
        return duplicate.idea.generic_json()
    graph_view.db.add(link)
    graph_view.db.expire(graph_view, ["idea_assocs"])
    graph_view.send_to_changes()
    # special location
    return Response(
        json.dumps(idea.generic_json(), ensure_ascii=False),
        201, content_type='application/json',
        charset="utf-8", location=request.url + "/" + str(idea.id))


@view_config(context=InstanceContext, renderer='json', request_method='DELETE',
             ctx_named_collection_instance="ExplicitSubGraphView.ideas",
             permission=P_EDIT_SYNTHESIS, accept="application/json")
def remove_idea_from_synthesis(request):
    """Remove an idea from an ExplictSubgraphView"""
    ctx = request.context
    graph_view = ctx.__parent__.parent_instance
    if isinstance(graph_view, Synthesis) and not graph_view.is_next_synthesis:
        raise HTTPBadRequest("Synthesis is published")
    idea = ctx._instance

    link_query = graph_view.db.query(
        SubGraphIdeaAssociation).filter_by(idea=idea, sub_graph=graph_view)
    if not link_query.count():
        raise HTTPNotFound("Idea not in view")

    link_query.delete(synchronize_session=False)

    # Send the view on the socket, and recalculate ideas linked to the view
    graph_view.db.expire(graph_view, ["idea_assocs"])
    graph_view.send_to_changes()
    return {
        "@tombstone": request.url
    }


@view_config(context=InstanceContext, request_method='GET',
             ctx_instance_class=Synthesis, permission=P_READ,
             accept="text/html", name="preview")
def html_export(request):
    from pyramid_jinja2 import IJinja2Environment
    jinja_env = request.registry.queryUtility(
        IJinja2Environment, name='.jinja2')
    lang_prefs = LanguagePreferenceCollection.getCurrent(request)
    return Response(request.context._instance.as_html(jinja_env, lang_prefs),
                    content_type='text/html', charset="utf-8")
