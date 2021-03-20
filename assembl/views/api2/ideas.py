from io import BytesIO

from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPUnauthorized, HTTPBadRequest, HTTPFound)
from pyramid.security import authenticated_userid, Everyone
from sqlalchemy.orm import aliased

from ..traversal import (InstanceContext, CollectionContext)
from . import instance_view
from assembl.auth import (CrudPermissions, P_READ, P_EDIT_IDEA)
from assembl.lib.text_search import add_text_search
from assembl.models import (
    Idea, LangString, LangStringEntry, LanguagePreferenceCollection, Discussion)
from .discussion import request_to_graph_mimetype, pygraphviz_formats

@view_config(context=InstanceContext, request_method='DELETE', renderer='json',
             ctx_instance_class=Idea, permission=P_EDIT_IDEA)
def instance_del(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    idea = ctx._instance
    if not idea.user_can(
            user_id, CrudPermissions.DELETE, ctx.get_permissions()):
        raise HTTPUnauthorized()
    for link in idea.source_links:
        link.is_tombstone = True
    idea.is_tombstone = True

    return {}


@view_config(context=InstanceContext, request_method='GET', renderer='json',
             ctx_instance_class=Idea, accept="text/html")
def redirect_idea_html(request):
    if (request.accept.quality('text/html') or 0) > max(
            request.accept.quality('application/json') or 0,
            request.accept.quality('application/ld+json') or 0):
        idea = request.context._instance
        return HTTPFound(request.route_url(
            'purl_idea', discussion_slug=idea.discussion.slug,
            remainder='/'+str(idea.id)))
    return instance_view(request)


@view_config(context=InstanceContext, request_method='POST', renderer='json',
             ctx_instance_class=Idea, name="do_transition")
def pub_state_transition(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    idea = ctx._instance
    discussion = idea.discussion
    flow = discussion.idea_publication_flow
    if not flow:
        raise HTTPBadRequest("discussion has no flow set")
    transition = flow.transition_by_label(request.json['transition'])
    if not transition:
        raise HTTPBadRequest("Cannot find this transition")
    if transition.source_id != idea.pub_state_id:
        raise HTTPBadRequest("Idea is not in source state")
    if transition.requires_permission.name not in request.permissions:
        raise HTTPUnauthorized()
    idea.pub_state_id = transition.target_id
    return {"pub_state_name": transition.target.label}


@view_config(context=InstanceContext, name="mindmap",
             ctx_instance_class=Idea, request_method='GET',
             permission=P_READ)
def as_mind_map(request):
    """Provide a mind-map like representation of the table of ideas"""
    mimetype = request_to_graph_mimetype(request)
    idea = request.context._instance
    G = idea.local_mind_map()
    io = BytesIO()
    G.draw(io, format=pygraphviz_formats[mimetype])
    io.seek(0)
    return Response(body_file=io, content_type=mimetype)


@view_config(context=CollectionContext, renderer='json',
             ctx_collection_class=Idea, name='autocomplete', permission=P_READ)
def autocomplete(request):
    discussion = request.context.get_instance_of_class(Discussion)
    keywords = request.GET.get('q')
    if not keywords:
        raise HTTPBadRequest("please specify search terms (q)")
    locales = request.GET.getall('locale')
    user_prefs = LanguagePreferenceCollection.getCurrent()
    if not locales:
        locales = user_prefs.known_languages()
        if not set(locales).intersection(discussion.discussion_locales):
            locales.extend(discussion.discussion_locales)
    include_description = bool(request.GET.get('description'))
    match_lse = aliased(LangStringEntry)
    title_ls = aliased(LangString)
    query = Idea.default_db.query(
        Idea.id, title_ls, match_lse.langstring_id, match_lse.locale
    ).join(title_ls, title_ls.id == Idea.title_id
    ).filter(
        Idea.discussion_id == discussion.id)
    limit = int(request.GET.get('limit') or 5)
    columns = [Idea.title_id]
    if include_description:
        columns.append(Idea.description_id)
    query, rank = add_text_search(
        query, columns, keywords.split(), locales, True, match_lse)
    query = query.order_by(rank.desc()).limit(limit).all()
    results = []
    if not query:
        return results
    for (idea_id, title, ls_id, lse_locale, rank) in query:
        title_entry = title.best_lang(user_prefs, False)
        r = {'id': Idea.uri_generic(idea_id),
             'title_locale': title_entry.locale,
             'match_locale': lse_locale,
             'text': title_entry.value
             }
        if include_description:
            r['match_field'] = 'shortTitle' if ls_id == title.id else 'definition'
        results.append(r)
    return {'results': results}




@view_config(context=InstanceContext, request_method='GET',
             ctx_instance_class=Idea, permission=P_READ,
             accept="text/html", name="html_view")
def html_export(request):
    from pyramid_jinja2 import IJinja2Environment
    jinja_env = request.registry.queryUtility(
        IJinja2Environment, name='.jinja2')
    lang_prefs = LanguagePreferenceCollection.getCurrent(request)
    return Response(request.context._instance.as_html(jinja_env, lang_prefs),
                    content_type='text/html', charset="utf-8")
