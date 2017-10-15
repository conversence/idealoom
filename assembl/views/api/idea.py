"""Cornice API for ideas"""
from collections import defaultdict
from datetime import datetime

import simplejson as json
from cornice import Service
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPNoContent
from pyramid.security import authenticated_userid, Everyone
from sqlalchemy import and_
from sqlalchemy.orm import (joinedload, subqueryload, undefer)

from assembl.views.api import API_DISCUSSION_PREFIX
from assembl.models import (
    get_database_id, Idea, RootIdea, IdeaLink, Discussion,
    Extract, SubGraphIdeaAssociation, LangString)
from assembl.auth import (P_READ, P_ADD_IDEA, P_EDIT_IDEA)


ideas = Service(name='ideas', path=API_DISCUSSION_PREFIX + '/ideas',
                description="The ideas collection",
                renderer='json')

idea = Service(name='idea', path=API_DISCUSSION_PREFIX + '/ideas/{id:.+}',
               description="Manipulate a single idea", renderer='json')

idea_extracts = Service(
    name='idea_extracts',
    path=API_DISCUSSION_PREFIX + '/ideas_extracts/{id:.+}',
    description="Get the extracts of a single idea")


langstring_fields = {
    "longTitle": "synthesis_title",
    "shortTitle": "title",
    "definition": "description"
}


# Create
@ideas.post(permission=P_ADD_IDEA)
def create_idea(request):
    discussion = request.context
    session = discussion.db
    user_id = authenticated_userid(request)
    permissions = request.permissions
    idea_data = json.loads(request.body)
    now = datetime.utcnow()

    kwargs = {
        "discussion": discussion,
        "creation_date": now,
    }

    for key, attr_name in langstring_fields.items():
        if key in idea_data:
            ls_data = idea_data[key]
            if ls_data is None:
                continue
            assert isinstance(ls_data, dict)
            current = LangString.create_from_json(
                ls_data, user_id, permissions=permissions)
            kwargs[attr_name] = current

    new_idea = Idea(**kwargs)

    session.add(new_idea)

    if idea_data['parentId']:
        parent = Idea.get_instance(idea_data['parentId'])
    else:
        parent = discussion.root_idea
    session.add(IdeaLink(
        source=parent, target=new_idea, creation_date=now,
        order=idea_data.get('order', 0.0)))

    session.flush()

    return {'ok': True, '@id': new_idea.uri()}


@idea.get(permission=P_READ)
def get_idea(request):
    idea_id = request.matchdict['id']
    idea = Idea.get_instance(idea_id)
    view_def = request.GET.get('view')
    discussion = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = request.permissions

    if not idea:
        raise HTTPNotFound("Idea with id '%s' not found." % idea_id)

    return idea.generic_json(view_def, user_id, permissions)


def _get_ideas_real(request, view_def=None, ids=None, user_id=None):
    discussion = request.discussion
    user_id = user_id or Everyone
    # optimization: Recursive widget links.
    from assembl.models import (
        Widget, IdeaWidgetLink, IdeaDescendantsShowingWidgetLink)
    universal_widget_links = []
    by_idea_widget_links = defaultdict(list)
    widget_links = discussion.db.query(IdeaWidgetLink
        ).join(Widget).join(Discussion
        ).filter(
            Widget.test_active(),
            Discussion.id == discussion.id,
            IdeaDescendantsShowingWidgetLink.polymorphic_filter()
        ).options(joinedload(IdeaWidgetLink.idea)).all()
    for wlink in widget_links:
        if isinstance(wlink.idea, RootIdea):
            universal_widget_links.append({
                '@type': wlink.external_typename(),
                'widget': Widget.uri_generic(wlink.widget_id)})
        else:
            for id in wlink.idea.get_all_descendants(True):
                by_idea_widget_links[Idea.uri_generic(id)].append({
                    '@type': wlink.external_typename(),
                    'widget': Widget.uri_generic(wlink.widget_id)})

    next_synthesis_id = discussion.get_next_synthesis_id()
    ideas = discussion.db.query(Idea).filter_by(
        discussion=discussion
    )

    ideas = ideas.outerjoin(
        SubGraphIdeaAssociation,
        and_(SubGraphIdeaAssociation.sub_graph_id == next_synthesis_id,
             SubGraphIdeaAssociation.idea_id == Idea.id))

    ideas = ideas.outerjoin(
        IdeaLink, IdeaLink.target_id == Idea.id)

    ideas = ideas.order_by(IdeaLink.order, Idea.creation_date)

    if ids:
        ids = [get_database_id("Idea", id) for id in ids]
        ideas = ideas.filter(Idea.id.in_(ids))
    # remove tombstones
    ideas = ideas.filter(and_(*Idea.base_conditions()))
    ideas = ideas.options(
        joinedload(Idea.source_links),
        subqueryload(Idea.attachments).joinedload("document"),
        subqueryload(Idea.widget_links),
        joinedload(Idea.title).subqueryload("entries"),
        joinedload(Idea.synthesis_title).subqueryload("entries"),
        joinedload(Idea.description).subqueryload("entries"),
        undefer(Idea.num_children))

    permissions = request.permissions
    Idea.prepare_counters(discussion.id, True)
    # ideas = list(ideas)
    # import cProfile
    # cProfile.runctx('''retval = [idea.generic_json(None, %d, %s)
    #           for idea in ideas]''' % (user_id, permissions),
    #           globals(), locals(), 'json_stats')
    retval = [idea.generic_json(view_def, user_id, permissions)
              for idea in ideas]
    retval = [x for x in retval if x is not None]
    for r in retval:
        if r.get('widget_links', None) is not None:
            links = r['widget_links'][:]
            links.extend(universal_widget_links)
            links.extend(by_idea_widget_links[r['@id']])
            r['active_widget_links'] = links
    return retval


@ideas.get(permission=P_READ)
def get_ideas(request):
    user_id = authenticated_userid(request) or Everyone
    discussion = request.context
    view_def = request.GET.get('view')
    ids = request.GET.getall('ids')
    return _get_ideas_real(request, view_def=view_def,
                           ids=ids, user_id=user_id)


@idea.put(permission=P_EDIT_IDEA)
def save_idea(request):
    """Update this idea.

    In case the ``parentId`` is changed, handle all
    ``IdeaLink`` changes and send relevant ideas on the socket."""
    discussion = request.context
    user_id = authenticated_userid(request)
    permissions = request.permissions
    idea_id = request.matchdict['id']
    idea_data = json.loads(request.body)
    # Idea.default_db.execute('set transaction isolation level read committed')
    # Special items in TOC, like unsorted posts.
    if idea_id in ['orphan_posts']:
        return {'ok': False, 'id': Idea.uri_generic(idea_id)}

    idea = Idea.get_instance(idea_id)
    if not idea:
        raise HTTPNotFound("No such idea: %s" % (idea_id))
    if isinstance(idea, RootIdea):
        raise HTTPBadRequest("Cannot edit root idea.")
    if(idea.discussion_id != discussion.id):
        raise HTTPBadRequest(
            "Idea from discussion %s cannot be saved from different discussion (%s)." % (
                idea.discussion_id, discussion.id))

    for key, attr_name in langstring_fields.items():
        if key in idea_data:
            current = getattr(idea, attr_name)
            ls_data = idea_data[key]
            # TODO: handle legacy string instance?
            assert isinstance(ls_data, (dict, type(None)))
            if current:
                if ls_data:
                    current.update_from_json(
                        ls_data, user_id, permissions=permissions)
                else:
                    current.delete()
            elif ls_data:
                current = LangString.create_from_json(
                    ls_data, user_id, permissions=permissions)
                setattr(idea, attr_name, current)

    if 'parentId' in idea_data and idea_data['parentId'] is not None:
        # TODO: Make sure this is sent as a list!
        parent = Idea.get_instance(idea_data['parentId'])
        # calculate it early to maximize contention.
        prev_ancestors = parent.get_all_ancestors()
        new_ancestors = set()

        order = idea_data.get('order', 0.0)
        if not parent:
            raise HTTPNotFound("Missing parentId %s" % (idea_data['parentId']))

        for parent_link in idea.source_links:
            # still assuming there's only one.
            pl_parent = parent_link.source
            pl_ancestors = pl_parent.get_all_ancestors()
            new_ancestors.update(pl_ancestors)
            if parent_link.source != parent:
                parent_link.copy(True)
                parent_link.source = parent
                parent.db.expire(parent, ['target_links'])
                parent.db.expire(pl_parent, ['target_links'])
                for ancestor in pl_ancestors:
                    if ancestor in prev_ancestors:
                        break
                    ancestor.send_to_changes()
                for ancestor in prev_ancestors:
                    if ancestor in new_ancestors:
                        break
                    ancestor.send_to_changes()
            parent_link.order = order
            parent_link.db.expire(parent_link.source, ['target_links'])
            parent_link.source.send_to_changes()
            parent_link.db.flush()

    if 'subtype' in idea_data:
        idea.rdf_type = idea_data['subtype']
    idea.send_to_changes()

    return {'ok': True, 'id': idea.uri()}


@idea.delete(permission=P_EDIT_IDEA)
def delete_idea(request):
    idea_id = request.matchdict['id']
    idea = Idea.get_instance(idea_id)

    if not idea:
        raise HTTPNotFound("Idea with id '%s' not found." % idea_id)
    if isinstance(idea, RootIdea):
        raise HTTPBadRequest("Cannot delete root idea.")
    num_childrens = len(idea.children)
    if num_childrens > 0:
        raise HTTPBadRequest("Idea cannot be deleted because it still has %d child ideas." % num_childrens)
    num_extracts = len(idea.extracts)
    if num_extracts > 0:
        raise HTTPBadRequest("Idea cannot be deleted because it still has %d extracts." % num_extracts)
    for link in idea.source_links:
        link.is_tombstone = True
    idea.is_tombstone = True
    # Maybe return tombstone() ?
    request.response.status = HTTPNoContent.code
    return HTTPNoContent()


@idea_extracts.get(permission=P_READ)
def get_idea_extracts(request):
    discussion = request.context
    idea_id = request.matchdict['id']
    idea = Idea.get_instance(idea_id)
    view_def = request.GET.get('view') or 'default'
    user_id = authenticated_userid(request) or Everyone
    permissions = request.permissions

    if not idea:
        raise HTTPNotFound("Idea with id '%s' not found." % idea_id)

    extracts = Extract.default_db.query(Extract).filter(
        Extract.idea_id == idea.id
    ).order_by(Extract.order.desc())

    return [extract.generic_json(view_def, user_id, permissions)
            for extract in extracts]
