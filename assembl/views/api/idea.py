"""Cornice API for ideas"""
from collections import defaultdict
from datetime import datetime
from functools import partial

import simplejson as json
from cornice import Service
from pyramid.httpexceptions import (
    HTTPNotFound, HTTPBadRequest, HTTPNoContent, HTTPUnauthorized)
from pyramid.security import authenticated_userid, Everyone
from sqlalchemy import and_
from sqlalchemy.orm import (joinedload, subqueryload, undefer)

from assembl.lib.parsedatetime import parse_datetime
from assembl.models import (
    Idea, RootIdea, IdeaLink, Discussion,
    Extract, SubGraphIdeaAssociation, LangString)
from assembl.auth import (
    CrudPermissions, P_READ, P_ADD_IDEA, P_EDIT_IDEA, P_READ_IDEA,
    P_ASSOCIATE_IDEA)
from . import (
    API_DISCUSSION_PREFIX, instance_check_op, instance_check_permission,
    instance_check_permission_id)


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


def idea_check_permission(request, permission=P_READ_IDEA, **kwargs):
    return instance_check_permission(request, permission, Idea)


def idea_check_op(request, op=CrudPermissions.READ, **kwargs):
    return instance_check_op(request, op, Idea)


def check_add_on_parent(request, **kwargs):
    idea_data = request.json_body or {}
    parent_id = idea_data.get('parentId', None)
    if parent_id:
        return instance_check_permission_id(
            request, P_ADD_IDEA, Idea, parent_id)
    elif P_ADD_IDEA in request.base_permissions:
        return True
    else:
        request.errors.add("querystring", 'permissions', "Cannot add idea")
        request.errors.status = 403
        return False
    return True


# Create
@ideas.post(validators=check_add_on_parent)
def create_idea(request):
    discussion = request.context
    session = discussion.db
    user_id = authenticated_userid(request)
    permissions = request.permissions
    idea_data = request.json_body
    now = datetime.utcnow()

    pub_state = None
    pub_flow = discussion.idea_publication_flow
    if pub_flow:
        pub_state_name = discussion.preferences['default_idea_pub_state']
        pub_state = pub_flow.state_by_label(pub_state_name)
    kwargs = {
        "discussion": discussion,
        "creation_date": now,
        "pub_state": pub_state,
        "creator_id": user_id,
    }

    new_idea = Idea(**kwargs)

    session.add(new_idea)

    context = new_idea.get_instance_context(request=request)
    for key, attr_name in langstring_fields.items():
        if key in idea_data:
            ls_data = idea_data[key]
            if ls_data is None:
                continue
            subcontext = new_idea.get_collection_context(key, context)
            current = LangString.create_from_json(
                ls_data, context=subcontext)
            setattr(new_idea, attr_name, current._instance)

    if idea_data['parentId']:
        parent = Idea.get_instance(idea_data['parentId'])
    else:
        parent = discussion.root_idea
    session.add(IdeaLink(
        source=parent, target=new_idea, creation_date=now,
        order=idea_data.get('order', 0.0)))

    session.flush()

    return {'ok': True, '@id': new_idea.uri()}


@idea.get(validators=idea_check_op)
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


def _get_ideas_real(request, view_def=None, ids=None, user_id=None,
                    modified_after=None):
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
    ideas = Idea.query_filter_with_crud_op_req(request).filter(
        Idea.discussion==discussion)
    if modified_after:
        ideas = ideas.filter(Idea.last_modified > modified_after)

    ideas = ideas.outerjoin(
        SubGraphIdeaAssociation,
        and_(SubGraphIdeaAssociation.sub_graph_id == next_synthesis_id,
             SubGraphIdeaAssociation.idea_id == Idea.id))

    ideas = ideas.outerjoin(
        IdeaLink, IdeaLink.target_id == Idea.id)

    ideas = ideas.order_by(IdeaLink.order, Idea.creation_date)

    if ids:
        ids = [Idea.get_database_id(id) for id in ids]
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
        joinedload(Idea.import_record),
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
    modified_after = request.GET.get('modified_after')
    if modified_after:
        modified_after = parse_datetime(modified_after, True)
    return _get_ideas_real(
        request, view_def=view_def, ids=ids, user_id=user_id,
        modified_after=modified_after)


@idea.put(validators=partial(idea_check_op, op=CrudPermissions.UPDATE))
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
    db = idea.db
    if not idea:
        raise HTTPNotFound("No such idea: %s" % (idea_id))
    if isinstance(idea, RootIdea):
        raise HTTPBadRequest("Cannot edit root idea.")
    if(idea.discussion_id != discussion.id):
        raise HTTPBadRequest(
            "Idea from discussion %s cannot be saved from different discussion (%s)." % (
                idea.discussion_id, discussion.id))

    context = idea.get_instance_context(request=request)
    for key, attr_name in langstring_fields.items():
        if key in idea_data:
            current = getattr(idea, attr_name)
            ls_data = idea_data[key]
            # TODO: handle legacy string instance?
            if isinstance(ls_data, str):
                tr_service = discussion.translation_service()
                locale = tr_service.identify(ls_data)[0]
                ls_data = {
                    '@type': 'LangString',
                    'entries': [{
                        '@type': 'LangStringEntry',
                        '@language': locale,
                        'value': ls_data}]}
            elif isinstance(ls_data, dict):
                for e in ls_data['entries']:
                    if e['@language'] == 'und':
                        e['@language'] = tr_service.identify(e['value'])[0]
            subcontext = idea.get_collection_context(key, context)
            if current:
                if ls_data:
                    current.update_from_json(
                        ls_data, context=subcontext, permissions=permissions)
                else:
                    current.delete()
            elif ls_data:
                current = LangString.create_from_json(ls_data, context=subcontext)
                setattr(idea, attr_name, current._instance)

    new_parent_id = idea_data.get('parentId', None)
    if new_parent_id:
        # TODO: Make sure this is sent as a list!
        # Actually, use embedded links to do this properly...
        new_parent_ids = {new_parent_id}
        old_parent_ids = {Idea.uri_generic(l.source_id) for l in idea.source_links}
        if new_parent_ids != old_parent_ids:
            added_parent_ids = new_parent_ids - old_parent_ids
            removed_parent_ids = old_parent_ids - new_parent_ids
            added_parents = [Idea.get_instance(id) for id in added_parent_ids]
            current_parents = idea.get_parents()
            removed_parents = [p for p in current_parents 
                if p.uri() in removed_parent_ids]
            if None in added_parents:
                missing = [id for id in added_parent_ids if not Idea.get_instance(id)]
                raise HTTPNotFound("Missing parentId %s" % (','.join(missing)))
            if not idea.has_permission_req(P_ASSOCIATE_IDEA):
                raise HTTPUnauthorized("Cannot associate idea "+idea.uri())
            for parent in added_parents + removed_parents:
                if not parent.has_permission_req(P_ASSOCIATE_IDEA):
                    raise HTTPUnauthorized("Cannot associate parent idea "+idea.uri())
            old_ancestors = set()
            new_ancestors = set()
            for parent in current_parents:
                old_ancestors.add(parent)
                old_ancestors.update(parent.get_all_ancestors())
            kill_links = {l for l in idea.source_links
                if Idea.uri_generic(l.source_id) in removed_parent_ids}
            order = idea_data.get('order', 0.0)
            for parent in added_parents:
                if kill_links:
                    link = kill_links.pop()
                    db.expire(link.source, ['target_links'])
                    link.copy(True)
                    link.order = order
                    link.source = parent
                else:
                    link = IdeaLink(source=source, target=idea, order=order)
                    db.add(link)
                db.expire(parent, ['target_links'])
                order += 1.0
            for link in kill_links:
                db.expire(link.source, ['target_links'])
                kill_links.is_tombstone = True
            db.expire(idea, ['source_links'])
            db.flush()
            for parent in idea.get_parents():
                new_ancestors.add(parent)
                new_ancestors.update(parent.get_all_ancestors())
            for ancestor in new_ancestors ^ old_ancestors:
                ancestor.send_to_changes()
        else:
            order = idea_data.get('order', None)
            if order is not None:
                new_parent_id = Idea.get_database_id(new_parent_id)
                parent_links = [link for link in idea.source_links
                                if link.source_id == new_parent_id]
                assert len(parent_links) == 1
                parent_links[0].order = idea_data.get('order', 0.0)

    if 'subtype' in idea_data:
        idea.rdf_type = idea_data['subtype']
    idea.send_to_changes()

    return {'ok': True, 'id': idea.uri()}


@idea.delete(validators=partial(idea_check_op, op=CrudPermissions.DELETE))
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


@idea_extracts.get(validators=idea_check_op)
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
