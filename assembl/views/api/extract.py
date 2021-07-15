"""Cornice API for extracts"""

from cornice import Service
from pyramid.security import authenticated_userid, Everyone
from pyramid.httpexceptions import (
    HTTPNotFound, HTTPBadRequest, HTTPForbidden, HTTPServerError,
    HTTPNoContent, HTTPClientError)
from sqlalchemy import Unicode
from sqlalchemy.sql.expression import cast
from sqlalchemy.orm import joinedload
import simplejson as json

from assembl.views.api import API_DISCUSSION_PREFIX
from assembl.auth import (
    P_READ, P_ADD_EXTRACT, P_EDIT_EXTRACT, P_ASSOCIATE_EXTRACT)
from assembl.auth.util import get_permissions
from assembl.models import (
    AgentProfile, Extract, TextFragmentIdentifier, IdeaExtractLink,
    AnnotatorSource, Post, Webpage, Idea, AnnotationSelector)
from assembl.auth.util import user_has_permission
from assembl.lib.web_token import decode_token
from assembl.lib import sqla

cors_policy = dict(
    enabled=True,
    headers=('Location', 'Content-Type', 'Content-Length'),
    origins=('*',),
    credentials=True,
    max_age=86400)


extracts = Service(
    name='extracts',
    path=API_DISCUSSION_PREFIX + '/extracts',
    description="An extract from Content that is an expression of an Idea",
    renderer='json',
    cors_policy=cors_policy
)

extract = Service(
    name='extract',
    path=API_DISCUSSION_PREFIX + '/extracts/{id:.+}',
    description="Manipulate a single extract",
    renderer='json',
    cors_policy=cors_policy
)

search_extracts = Service(
    name='search_extracts',
    path=API_DISCUSSION_PREFIX + '/search_extracts',
    description="search for extracts matching a URL",
    renderer='json', cors_policy=cors_policy
)


@extract.get(permission=P_READ)
def get_extract(request):
    extract_id = request.matchdict['id']
    extract = Extract.get_instance(extract_id)
    view_def = request.GET.get('view') or 'default'
    user_id = authenticated_userid(request) or Everyone
    permissions = request.permissions

    if extract is None:
        raise HTTPNotFound(
            "Extract with id '%s' not found." % extract_id)

    return extract.generic_json(view_def, user_id, permissions)


def _get_extracts_real(request, view_def='default', ids=None, user_id=None):
    discussion = request.discussion
    user_id = user_id or Everyone
    all_extracts = discussion.db.query(Extract).filter(
        Extract.discussion_id == discussion.id
    )
    if ids:
        ids = [Extract.get_database_id(id) for id in ids]
        all_extracts = all_extracts.filter(Extract.id.in_(ids))

    all_extracts = all_extracts.options(joinedload(
        Extract.idea_content_links))
    all_extracts = all_extracts.options(
        joinedload(Extract.selectors).joinedload(
            AnnotationSelector.extract, innerjoin=True))
    permissions = request.permissions

    return [extract.generic_json(view_def, user_id, permissions)
            for extract in all_extracts]


@extracts.get(permission=P_READ)
def get_extracts(request):
    view_def = request.GET.get('view', 'default')
    ids = request.GET.getall('ids')

    return _get_extracts_real(
        request, view_def, ids, authenticated_userid(request))


@extracts.post()
def post_extract(request):
    """
    Create a new extract.
    """
    extract_data = json.loads(request.body)
    discussion = request.context
    db = discussion.db
    user_id = authenticated_userid(request)
    if not user_id:
        # Straight from annotator
        token = request.headers.get('X-Annotator-Auth-Token')
        if token:
            token = decode_token(
                token, request.registry.settings['session.secret'])
        if token:
            user_id = token['userId']
        user_id = user_id or Everyone
        permissions = get_permissions(user_id, discussion.id)
    else:
        permissions = request.permissions
    if P_ADD_EXTRACT not in permissions:
        #TODO: maparent:  restore this code once it works:
        #raise HTTPForbidden(result=ACLDenied(permission=P_ADD_EXTRACT))
        raise HTTPForbidden()
    if not user_id or user_id == Everyone:
        # TODO: Create an anonymous user.
        raise HTTPServerError("Anonymous extracts are not implemeted yet.")
    content = None
    uri = extract_data.get('uri')
    important = extract_data.get('important', False)
    annotation_text = extract_data.get('text')
    target = extract_data.get('target')
    if not uri:
        # Extract from an internal post
        if not target:
            raise HTTPBadRequest("No target")

        target_class = sqla.get_named_class(target.get('@type'))
        if issubclass(target_class, Post):
            post_id = target.get('@id')
            post = Post.get_instance(post_id)
            if not post:
                raise HTTPNotFound(
                    "Post with id '%s' not found." % post_id)
            content = post
        elif issubclass(target_class, Webpage):
            uri = target.get('url')
    if uri and not content:
        content = Webpage.get_instance(uri)
        if not content:
            # TODO: maparent:  This is actually a singleton pattern, should be
            # handled by the AnnotatorSource now that it exists...
            source = db.query(AnnotatorSource).filter_by(
                discussion=discussion).filter(
                cast(AnnotatorSource.name, Unicode) == 'Annotator').first()
            if not source:
                source = AnnotatorSource(
                    name='Annotator', discussion=discussion)
                db.add(source)
            content = Webpage(url=uri, discussion=discussion)
            db.add(content)
    extract_body = extract_data.get('quote', None)

    new_extract = Extract(
        creator_id=user_id,
        discussion=discussion,
        important=important,
        annotation_text=annotation_text,
        content=content
    )
    db.add(new_extract)

    icls = extract_data.get('ideaLinks', [])
    if icls and P_ASSOCIATE_EXTRACT not in permissions:
        raise HTTPForbidden()

    for icl in icls:
        # TODO: Check idCreator matches if present
        idea_id = icl.get("idIdea", None)
        if not idea_id:
            raise HTTPBadRequest("idea_content_link without idIdea")
        idea = Idea.get_instance(idea_id)
        if(idea.discussion.id != discussion.id):
            raise HTTPBadRequest(
                "Extract from discussion %s cannot be associated with an idea from a different discussion." % extract.get_discussion_id())
        link = IdeaExtractLink(
            creator_id=user_id,
            content=content,
            idea=idea,
            extract=new_extract
        )
        db.add(link)

    for range_data in extract_data.get('ranges', []):
        range = TextFragmentIdentifier(
            extract=new_extract,
            body=extract_body,
            xpath_start=range_data['start'],
            offset_start=range_data['startOffset'],
            xpath_end=range_data['end'],
            offset_end=range_data['endOffset'])
        db.add(range)
    db.flush()

    return {'ok': True, '@id': new_extract.uri()}


@extract.put()
def put_extract(request):
    """
    Updating an Extract
    """
    extract_id = request.matchdict['id']
    user_id = authenticated_userid(request)
    discussion = request.context

    if not user_id:
        # Straight from annotator
        token = request.headers.get('X-Annotator-Auth-Token')
        if token:
            token = decode_token(
                token, request.registry.settings['session.secret'])
        if token:
            user_id = token['userId']
        user_id = user_id or Everyone

    extract = Extract.get_instance(extract_id)
    if not extract:
        raise HTTPNotFound("Extract with id '%s' not found." % extract_id)
    permissions = get_permissions(user_id, discussion.id, extract)

    if P_EDIT_EXTRACT not in permissions:
        raise HTTPForbidden()

    updated_extract_data = json.loads(request.body)

    extract.creator_id = user_id or AgentProfile.get_database_id(extract.creator_id)
    # extract.order = updated_extract_data.get('order', extract.order)
    extract.important = updated_extract_data.get('important', extract.important)

    icls = updated_extract_data.get('ideaLinks', None)
    change_icls = False
    if icls:
        existing = set(extract.idea_content_links)
        for icl in icls:
            # TODO: Check idCreator matches if present
            idea_id = icl.get("idIdea", None)
            if not idea_id:
                raise HTTPBadRequest("idea_content_link without idIdea")
            idea = Idea.get_instance(idea_id)
            if(idea.discussion.id != discussion.id):
                raise HTTPBadRequest(
                    "Extract from discussion %s cannot be associated with an idea from a different discussion." % extract.get_discussion_id())
            if '@id' in icl:
                icl = IdeaExtractLink.get_instance(icl['@id'])
                if icl.idea_id != idea.id:
                    icl.idea_id = idea.id
                    change_icls = True
                existing.remove(icl)
            else:
                link = IdeaExtractLink(
                    creator_id=user_id,
                    idea=idea,
                    content_id=extract.content_id,
                    extract=extract
                )
                extract.db.add(link)
                change_icls = True
        for icl in existing:
            icl.delete()
            change_icls = True
    if change_icls and P_ASSOCIATE_EXTRACT not in permissions:
        raise HTTPForbidden()

    Extract.default_db.add(extract)
    #TODO: Merge ranges. Sigh.

    return {'ok': True}


@extract.delete(permission=P_READ)
def delete_extract(request):
    user_id = authenticated_userid(request)
    discussion = request.context

    if not user_id:
        # Straight from annotator
        token = request.headers.get('X-Annotator-Auth-Token')
        if token:
            token = decode_token(
                token, request.registry.settings['session.secret'])
        if token:
            user_id = token['userId']
        user_id = user_id or Everyone

    extract_id = request.matchdict['id']
    extract = Extract.get_instance(extract_id)
    permissions = get_permissions(user_id, discussion.id, extract)
    if P_EDIT_EXTRACT not in permissions:
        raise HTTPForbidden()

    if not extract:
        return HTTPNoContent()

    # TODO: Tombstonable extracts???
    extract.delete()
    return HTTPNoContent()


@search_extracts.get()
def do_search_extracts(request):
    uri = request.GET.get('uri', None)
    if not uri:
        raise HTTPClientError("Please specify a URI")
    view_def = request.GET.get('view') or 'default'
    discussion = request.context
    user_id = authenticated_userid(request)
    if not user_id:
        # Straight from annotator
        token = request.headers.get('X-Annotator-Auth-Token')
        if token:
            token = decode_token(
                token, request.registry.settings['session.secret'])
        if token:
            user_id = token['userId']
    user_id = user_id or Everyone
    if not user_has_permission(discussion.id, user_id, P_READ):
        raise HTTPForbidden()
    permissions = [P_READ]

    if not uri:
        raise HTTPBadRequest("Please specify a search uri")
    content = Webpage.get_by(url=uri)
    if content:
        extracts = Extract.default_db.query(Extract).filter_by(content=content).all()
        rows = [
            extract.generic_json(view_def, user_id, permissions)
            for extract in extracts]
        return {"total": len(extracts), "rows": rows}
    return {"total": 0, "rows": []}
