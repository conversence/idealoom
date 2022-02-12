"""Cornice API for posts"""
from __future__ import division
from builtins import next
from math import ceil
import logging
from collections import defaultdict
from itertools import chain

import simplejson as json
from cornice import Service
from pyramid.httpexceptions import (
    HTTPNotFound, HTTPUnauthorized, HTTPBadRequest)
from pyramid.i18n import TranslationStringFactory
from pyramid.settings import asbool
from pyramid.security import authenticated_userid, Everyone

from sqlalchemy import String, text

from sqlalchemy.orm import (aliased, subqueryload, joinedload)
from sqlalchemy.sql.expression import bindparam, and_, or_
from sqlalchemy.sql import cast, column, func, case

from jwzthreading.jwzthreading import SUBJECT_RE

import transaction

from assembl.lib.parsedatetime import parse_datetime
from assembl.lib.clean_input import sanitize_html, sanitize_text
from assembl.lib.config import get
from assembl.lib.text_search import (
    add_text_search, postgres_language_configurations)
from assembl.views.api import API_DISCUSSION_PREFIX
from assembl.auth import P_READ, P_ADD_POST
from assembl.tasks.translate import (
    translate_content,
    PrefCollectionTranslationTable)
from assembl.models import (
    Post, LocalPost, SynthesisPost,
    Synthesis, Discussion, Content, Idea, ViewPost, User,
    IdeaRelatedPostLink, AgentProfile, LikedPost, LangString,
    LanguagePreferenceCollection, LangStringEntry, Extract)
from assembl.models.post import deleted_publication_states
from assembl.lib.raven_client import capture_message

log = logging.getLogger(__name__)

posts = Service(name='posts', path=API_DISCUSSION_PREFIX + '/posts',
                description="Post API following SIOC vocabulary as much as possible",
                renderer='json')

post = Service(name='post', path=API_DISCUSSION_PREFIX + '/posts/{id:.+}',
               description="Manipulate a single post", renderer="json")

post_read = Service(name='post_read', path=API_DISCUSSION_PREFIX + '/post_read/{id:.+}',
               description="Signal that a post was read",
               renderer='json')

_ = TranslationStringFactory('assembl')


@posts.get(permission=P_READ)
def get_posts(request):
    """
    Query interface on posts
    Filters have two forms:
    only_*, is for filters that cannot be reversed (ex: only_synthesis, only_orphan)
    is_*, is for filters that can be reversed (ex:is_unread=true returns only unread message, is_unread=false returns only read messages)
    order: can be chronological, reverse_chronological, popularity
    root_post_id: all posts below the one specified.
    family_post_id: all posts below the one specified, and all its ancestors.
    post_reply_to: replies to a given post
    root_idea_id: all posts associated with the given idea
    ids: explicit message ids.
    posted_after_date, posted_before_date: date selection (ISO format)
    post_author: filter by author
    keyword: use full-text search
    locale: restrict to locale
    """
    localizer = request.localizer
    discussion = request.context

    discussion.import_from_sources()

    user_id = authenticated_userid(request) or Everyone
    permissions = request.permissions

    DEFAULT_PAGE_SIZE = 25
    page_size = DEFAULT_PAGE_SIZE

    filter_names = [
        filter_name for filter_name
        in request.GET.getone('filters').split(',')
        if filter_name
    ] if request.GET.get('filters') else []

    try:
        page = int(request.GET.getone('page'))
    except (ValueError, KeyError):
        page = 1

    keywords = request.GET.getall('keyword')

    order = request.GET.get('order')
    if order is None:
        order = 'chronological'
    assert order in ('chronological', 'reverse_chronological', 'score', 'popularity')
    if order == 'score' and not keywords:
        raise HTTPBadRequest("Cannot ask for a score without keywords")

    if page < 1:
        page = 1

    root_post_id = request.GET.getall('root_post_id')
    if root_post_id:
        root_post_id = Post.get_database_id(root_post_id[0])
    family_post_id = request.GET.getall('family_post_id')
    if family_post_id:
        family_post_id = Post.get_database_id(family_post_id[0])

    root_idea_id = request.GET.getall('root_idea_id')
    if root_idea_id:
        root_idea_id = Idea.get_database_id(root_idea_id[0])

    ids = request.GET.getall('ids[]')
    if ids:
        ids = [Post.get_database_id(id) for id in ids]

    view_def = request.GET.get('view') or 'default'

    only_synthesis = request.GET.get('only_synthesis')
    not_harvested = request.GET.get('not_harvested')

    post_author_id = request.GET.get('post_author')
    if post_author_id:
        post_author_id = AgentProfile.get_database_id(post_author_id)
        assert AgentProfile.get(post_author_id), "Unable to find agent profile with id " + post_author_id

    post_replies_to = request.GET.get('post_replies_to')
    if post_replies_to:
        post_replies_to = AgentProfile.get_database_id(post_replies_to)
        assert AgentProfile.get(post_replies_to), "Unable to find agent profile with id " + post_replies_to

    posted_after_date = request.GET.get('posted_after_date')
    posted_before_date = request.GET.get('posted_before_date')

    PostClass = SynthesisPost if only_synthesis == "true" else Post
    posts = discussion.db.query(Content).join(PostClass, PostClass.id == Content.id)

    posts = posts.filter(
        Content.discussion == discussion,
    )
    ##no_of_posts_to_discussion = posts.count()

    post_data = []

    # True means deleted only, False (default) means non-deleted only. None means both.

    deleted = request.GET.get('deleted', None)
    if deleted is None:
        if not ids:
            deleted = False
        else:
            deleted = None
    elif deleted.lower() == "any":
        deleted = None
    else:
        deleted = asbool(deleted)
    # if deleted is not in (False, True, None):
    #    deleted = False
    # end v4

    only_orphan = asbool(request.GET.get('only_orphan', False))
    if only_orphan:
        if root_idea_id:
            raise HTTPBadRequest(localizer.translate(
                _("Getting orphan posts of a specific idea isn't supported.")))
        orphans = Idea._get_orphan_posts_statement(
            discussion.id, True, include_deleted=deleted).subquery("orphans")
        posts = posts.join(orphans, Content.id == orphans.c.post_id)

    if root_idea_id:
        related = Idea.get_related_posts_query_c(
            discussion.id, root_idea_id, True, include_deleted=deleted)
        posts = posts.join(related, Content.id == related.c.post_id)
    elif not only_orphan:
        if deleted is not None:
            if deleted:
                posts = posts.filter(
                    Post.publication_state.in_(
                        deleted_publication_states))
            else:
                posts = posts.filter(
                    Content.tombstone_date == None)

    if root_post_id:
        root_post = Post.get(root_post_id)

        posts = posts.filter(
            (Post.ancestry.like(
            root_post.ancestry + cast(root_post.id, String) + ',%'
            ))
            |
            (Content.id==root_post.id)
            )
    elif family_post_id:
        root_post = Post.get(family_post_id)
        ancestor_ids = root_post.ancestor_ids()
        posts = posts.filter(
            (Post.ancestry.like(
            root_post.ancestry + cast(root_post.id, String) + ',%'
            ))
            |
            (Content.id==root_post.id)
            |
            (Content.id.in_(ancestor_ids))
            )
    else:
        root_post = None

    if ids:
        posts = posts.filter(Post.id.in_(ids))

    if posted_after_date:
        posted_after_date = parse_datetime(posted_after_date)
        if posted_after_date:
            posts = posts.filter(Content.creation_date >= posted_after_date)
        #Maybe we should do something if the date is invalid.  benoitg

    if posted_before_date:
        posted_before_date = parse_datetime(posted_before_date)
        if posted_before_date:
            posts = posts.filter(Content.creation_date <= posted_before_date)
        #Maybe we should do something if the date is invalid.  benoitg

    if post_author_id:
        posts = posts.filter(Post.creator_id == post_author_id)

    if post_replies_to:
        parent_alias = aliased(Content)
        posts = posts.join(parent_alias, Post.parent)
        posts = posts.filter(parent_alias.creator_id == post_replies_to)

    if keywords:
        # temporary: break up words. Ideally should find phrases...
        keywords = list(chain(*[keyword.split() for keyword in keywords]))
        locales = request.GET.getall('locale')
        posts, rank = add_text_search(
            posts, (Content.body_id,), keywords, locales, order == 'score')

    if not_harvested:
        # TODO: Add a flag for harvesting that does not result in extracts
        posts = posts.outerjoin(Extract).filter(Extract.id == None)

    # Post read/unread management
    is_unread = request.GET.get('is_unread')
    translations = None
    if user_id != Everyone:
        # This is horrible, but the join creates complex subqueries that
        # virtuoso cannot decode properly.
        read_posts = {v.post_id for v in discussion.db.query(
            ViewPost).filter(
                ViewPost.tombstone_condition(),
                ViewPost.actor_id == user_id,
                *ViewPost.get_discussion_conditions(discussion.id))}
        liked_posts = {l.post_id: l.id for l in discussion.db.query(
            LikedPost).filter(
                LikedPost.tombstone_condition(),
                LikedPost.actor_id == user_id,
                *LikedPost.get_discussion_conditions(discussion.id))}
        if is_unread != None:
            posts = posts.outerjoin(
                ViewPost, and_(
                    ViewPost.actor_id==user_id,
                    ViewPost.post_id==Content.id,
                    ViewPost.tombstone_date == None))
            if is_unread == "true":
                posts = posts.filter(ViewPost.id == None)
            elif is_unread == "false":
                posts = posts.filter(ViewPost.id != None)
        user = AgentProfile.get(user_id)
        service = discussion.translation_service()
        if service.canTranslate is not None:
            translations = PrefCollectionTranslationTable(
                service, LanguagePreferenceCollection.getCurrent(request))
    else:
        #If there is no user_id, all posts are always unread
        if is_unread == "false":
            raise HTTPBadRequest(localizer.translate(
                _("You must be logged in to view which posts are read")))

    # posts = posts.options(contains_eager(Post.source))
    # Horrible hack... But useful for structure load
    if view_def in ('partial_post', 'id_only'):
        pass  # posts = posts.options(defer(Post.body))
    else:
        ideaContentLinkQuery = posts.with_entities(
            Content.id, Post.idea_content_links_above_post)
        ideaContentLinkCache = dict(ideaContentLinkQuery.all())
        posts = posts.options(
            # undefer(Post.idea_content_links_above_post),
            joinedload(Post.creator),
            joinedload(Post.extracts),
            joinedload(Post.widget_idea_links),
            # joinedload(SynthesisPost.publishes_synthesis),
            subqueryload(Post.attachments))
        if len(discussion.discussion_locales) > 1:
            posts = posts.options(*Content.subqueryload_options())
        else:
            posts = posts.options(*Content.joinedload_options())

    if order == 'chronological':
        posts = posts.order_by(Content.creation_date)
    elif order == 'reverse_chronological':
        posts = posts.order_by(Content.creation_date.desc())
    elif order == 'score':
        posts = posts.order_by(rank.desc())
    elif order == 'popularity':
        # assume reverse chronological otherwise
        posts = posts.order_by(Content.like_count.desc(), Content.creation_date.desc())
    else:
        posts = posts.order_by(Content.id)
    # print str(posts)

    no_of_posts = 0
    no_of_posts_viewed_by_user = 0

    if deleted is True:
        # We just got deleted posts, now we want their ancestors for context
        post_ids = set()
        ancestor_ids = set()

        def add_ancestors(post):
            post_ids.add(post.id)
            ancestor_ids.update(
                [int(x) for x in post.ancestry.strip(",").split(",") if x])
        posts = list(posts)
        for post in posts:
            add_ancestors(post)
        ancestor_ids -= post_ids
        if ancestor_ids:
            ancestors = discussion.db.query(
                Content).filter(Content.id.in_(ancestor_ids))
            if view_def in ('partial_post', 'id_only'):
                pass  # ancestors = ancestors.options(defer(Post.body))
            else:
                ancestors = ancestors.options(
                    # undefer(Post.idea_content_links_above_post),
                    joinedload(Post.creator),
                    joinedload(Post.extracts),
                    joinedload(Post.widget_idea_links),
                    joinedload(SynthesisPost.publishes_synthesis),
                    subqueryload(Post.attachments))
                if len(discussion.discussion_locales) > 1:
                    ancestors = ancestors.options(
                        *Content.subqueryload_options())
                else:
                    ancestors = ancestors.options(
                        *Content.joinedload_options())
            posts.extend(ancestors.all())

    if view_def == 'id_only':
        posts = posts.with_entities(Content.id)

    for query_result in posts:
        score, viewpost, likedpost = None, None, None
        if not isinstance(query_result, (list, tuple)):
            query_result = [query_result]
        post = query_result[0]
        no_of_posts += 1
        if view_def == 'id_only':
            post_data.append(Content.uri_generic(post))
            continue
        if deleted is True:
            add_ancestors(post)

        if user_id != Everyone:
            viewpost = post.id in read_posts
            likedpost = liked_posts.get(post.id, None)
            if view_def not in ("partial_post", "id_only"):
                translate_content(
                    post, translation_table=translations, service=service)
        serializable_post = post.generic_json(
            view_def, user_id, permissions) or {}
        if order == 'score':
            score = query_result[1]
            serializable_post['score'] = score

        if viewpost:
            serializable_post['read'] = True
            no_of_posts_viewed_by_user += 1
        elif user_id != Everyone and root_post is not None and root_post.id == post.id:
            # Mark post read, we requested it explicitely
            viewed_post = ViewPost(
                actor_id=user_id,
                post=root_post
                )
            discussion.db.add(viewed_post)
            serializable_post['read'] = True
        else:
            serializable_post['read'] = False
        # serializable_post['liked'] = likedpost.uri() if likedpost else False
        serializable_post['liked'] = (
            LikedPost.uri_generic(likedpost) if likedpost else False)
        if view_def not in ("partial_post", "id_only"):
            serializable_post['indirect_idea_content_links'] = (
                post.indirect_idea_content_links_with_cache(
                    ideaContentLinkCache.get(post.id, None)))

        post_data.append(serializable_post)

    # Benoitg:  For now, this completely garbles threading without intelligent
    #handling of pagination.  Disabling
    #posts = posts.limit(page_size).offset(data['startIndex']-1)
    # This code isn't up to date.  If limiting the query by page, we need to 
    # calculate the counts with a separate query to have the right number of 
    # results
    #no_of_messages_viewed_by_user = discussion.db.query(ViewPost).join(
    #    Post
    #).filter(
    #    Post.discussion_id == discussion.id,
    #    ViewPost.actor_id == user_id,
    #).count() if user_id else 0

    data = {}
    data["page"] = page
    data["unread"] = no_of_posts - no_of_posts_viewed_by_user
    data["total"] = no_of_posts
    data["maxPage"] = max(1, ceil(data["total"]/page_size))
    #TODO:  Check if we want 1 based index in the api
    data["startIndex"] = (page_size * page) - (page_size-1)

    if data["page"] == data["maxPage"]:
        data["endIndex"] = data["total"]
    else:
        data["endIndex"] = data["startIndex"] + (page_size-1)
    data["posts"] = post_data

    return data


@post.get(permission=P_READ)
def get_post(request):
    post_id = request.matchdict['id']
    post = Post.get_instance(post_id)
    view_def = request.GET.get('view') or 'default'

    if not post:
        raise HTTPNotFound("Post with id '%s' not found." % post_id)
    discussion = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = request.permissions

    return post.generic_json(view_def, user_id, permissions)


@post_read.put(permission=P_READ)
def mark_post_read(request):
    """Mark this post as un/read. Return the read post count for all affected ideas."""
    discussion = request.context
    post_id = request.matchdict['id']
    post = Post.get_instance(post_id)
    if not post:
        raise HTTPNotFound("Post with id '%s' not found." % post_id)
    post_id = post.id
    user_id = authenticated_userid(request)
    if not user_id:
        raise HTTPUnauthorized()
    read_data = json.loads(request.body)
    db = discussion.db
    change = False
    with transaction.manager:
        if read_data.get('read', None) is False:
            view = db.query(ViewPost).filter_by(
                post_id=post_id, actor_id=user_id,
                tombstone_date=None).first()
            if view:
                change = True
                view.is_tombstone = True
        else:
            count = db.query(ViewPost).filter_by(
                post_id=post_id, actor_id=user_id,
                tombstone_date=None).count()
            if not count:
                change = True
                db.add(ViewPost(post=post, actor_id=user_id))

    new_counts = []
    if change:
        new_counts = Idea.idea_read_counts(discussion.id, post_id, user_id)

    return { "ok": True, "ideas": [
        {"@id": Idea.uri_generic(idea_id),
         "num_read_posts": read_posts
        } for (idea_id, read_posts) in new_counts] }


@posts.post(permission=P_ADD_POST)
def create_post(request):
    """
    Create a new post in this discussion.

    We use post, not put, because we don't know the id of the post
    """
    localizer = request.localizer
    request_body = json.loads(request.body)
    user_id = authenticated_userid(request)
    if not user_id:
        raise HTTPUnauthorized()

    body = request_body.get('body', None)
    html = request_body.get('html', None)  # BG: Is this used now? I cannot see it.
    reply_id = request_body.get('reply_id', None)
    idea_id = request_body.get('idea_id', None)
    subject = request_body.get('subject', None)
    publishes_synthesis_id = request_body.get('publishes_synthesis_id', None)

    if not body and not publishes_synthesis_id:
        # Should we allow empty messages otherwise?
        raise HTTPBadRequest(localizer.translate(
                _("Your message is empty")))

    if reply_id:
        in_reply_to_post = Post.get_instance(reply_id)
    else:
        in_reply_to_post = None

    if idea_id:
        in_reply_to_idea = Idea.get_instance(idea_id)
    else:
        in_reply_to_idea = None

    discussion = request.context

    ctx = discussion.get_instance_context(request=request)
    if html:
        log.warning("Still using html")
        # how to guess locale in this case?
        body = LangString.create(sanitize_html(html))
        # TODO: LocalPosts are pure text right now.
        # Allowing HTML requires changes to the model.
    elif body:
        # TODO: Accept HTML body.
        for e in body['entries']:
            e['value'] = sanitize_text(e['value'])
        body_ctx = LangString.create_from_json(body, context=ctx)
        body = body_ctx._instance
    else:
        body = LangString.EMPTY(discussion.db)

    if subject:
        for e in subject['entries']:
            e['value'] = sanitize_text(e['value'])
        subject_ctx = LangString.create_from_json(subject, context=ctx)
        subject = subject_ctx._instance
    else:
        from assembl.models import LocaleLabel
        locale = LocaleLabel.UNDEFINED
        # print(in_reply_to_post.subject, discussion.topic)
        if in_reply_to_post and in_reply_to_post.get_title():
            original_subject = in_reply_to_post.get_title().first_original()
            if original_subject:
                locale = original_subject.locale_code
                subject = (
                    original_subject.value or ''
                    if in_reply_to_post.get_title() else '')
        elif in_reply_to_idea:
            # TODO:  THis should use a cascade like the frontend
            # also, some ideas have extra langstring titles
            subject = (in_reply_to_idea.short_title
                       if in_reply_to_idea.short_title else '')
            locale = discussion.main_locale
        else:
            subject = discussion.topic if discussion.topic else ''
            locale = discussion.main_locale
        # print subject
        if subject is not None and len(subject):
            new_subject = "Re: " + SUBJECT_RE.sub('', subject).strip()
            if (in_reply_to_post and new_subject == subject and
                    in_reply_to_post.get_title()):
                # reuse subject and translations
                subject = in_reply_to_post.get_title().clone(discussion.db)
            else:
                # how to guess locale in this case?
                subject = LangString.create(new_subject, locale)
        else:
            capture_message(
                "A message is about to be written to the database with an "
                "empty subject.  This is not supposed to happen.")
            subject = LangString.EMPTY(discussion.db)

    post_constructor_args = {
        'discussion': discussion,
        'creator_id': user_id,
        'subject': subject,
        'body': body
    }

    if publishes_synthesis_id:
        published_synthesis = Synthesis.get_instance(publishes_synthesis_id)
        post_constructor_args['publishes_synthesis'] = published_synthesis
        new_post = SynthesisPost(**post_constructor_args)
        new_post.finalize_publish()
    else:
        new_post = LocalPost(**post_constructor_args)
    new_post.guess_languages()
    service = discussion.translation_service()
    if service.canTranslate is not None:
        # pre-translate in discussion languages
        translate_content(new_post, service=service)

    discussion.db.add(new_post)
    discussion.db.flush()

    if in_reply_to_post:
        new_post.set_parent(in_reply_to_post)
    if in_reply_to_idea:
        idea_post_link = IdeaRelatedPostLink(
            creator_id=user_id,
            content=new_post,
            idea=in_reply_to_idea
        )
        discussion.db.add(idea_post_link)
        idea = in_reply_to_idea
        while idea:
            idea.send_to_changes()
            parents = idea.get_parents()
            idea = next(iter(parents)) if parents else None
    else:
        discussion.root_idea.send_to_changes()
    for source in discussion.sources:
        if 'send_post' in dir(source):
            source.send_post(new_post)
    permissions = request.permissions

    return new_post.generic_json('default', user_id, permissions)
