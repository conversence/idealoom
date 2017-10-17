from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPUnauthorized, HTTPBadRequest)
from pyramid.security import authenticated_userid, Everyone
from sqlalchemy.orm import aliased

from ..traversal import (InstanceContext, CollectionContext)
from assembl.auth import (CrudPermissions, P_READ, P_EDIT_IDEA)
from assembl.lib.text_search import add_text_search
from assembl.models import (
    Idea, LangString, LangStringEntry, LanguagePreferenceCollection, Discussion)


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
