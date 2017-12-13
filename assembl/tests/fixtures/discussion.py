from __future__ import print_function
import pytest
from sqlalchemy import inspect

from assembl.auth import P_READ, R_PARTICIPANT


@pytest.fixture(scope="function")
def discussion(request, test_session, default_preferences,
               test_adminuser_webrequest):
    """An empty Discussion fixture with default preferences"""
    from assembl.models import Discussion
    from assembl.models.auth import create_default_permissions
    d = Discussion(
        topic=u"Jack Layton", slug="jacklayton2",
        subscribe_to_notifications_on_signup=False,
        creator=None)
    test_session.add(d)
    test_session.flush()
    d.apply_side_effects_without_json(
        request=test_adminuser_webrequest._base_pyramid_request)
    d.discussion_locales = ['en', 'fr', 'de']
    create_default_permissions(d)
    test_session.flush()

    def fin():
        print("finalizer discussion")
        discussion = d
        if inspect(discussion).detached:
            # How did this happen?
            discussion = test_session.query(Discussion).get(d.id)
        for acl in discussion.acls:
            test_session.delete(acl)
        test_session.delete(discussion.table_of_contents)
        test_session.delete(discussion.root_idea)
        test_session.delete(discussion.next_synthesis)
        preferences = discussion.preferences
        discussion.preferences = None
        discussion.preferences_id = None
        for ut in discussion.user_templates:
            for ns in ut.notification_subscriptions:
                ns.delete()
            ut.delete()
        test_session.delete(preferences)
        test_session.delete(discussion)
        test_session.flush()
    request.addfinalizer(fin)
    return d


@pytest.fixture(scope="function")
def discussion2(request, test_session, default_preferences,
                test_adminuser_webrequest):
    """An non-empty Discussion fixture with default preferences"""
    from assembl.models import Discussion
    d = Discussion(
        topic=u"Second discussion", slug="testdiscussion2", creator=None)
    test_session.add(d)
    test_session.flush()
    d.apply_side_effects_without_json(
        request=test_adminuser_webrequest._base_pyramid_request)
    test_session.flush()

    def fin():
        print("finalizer discussion2")
        test_session.delete(d.table_of_contents)
        test_session.delete(d.root_idea)
        test_session.delete(d.next_synthesis)
        for ut in d.user_templates:
            for ns in ut.notification_subscriptions:
                ns.delete()
            ut.delete()
        preferences = d.preferences
        d.preferences = None
        test_session.delete(preferences)
        test_session.delete(d)
        test_session.flush()
    request.addfinalizer(fin)
    return d


@pytest.fixture(scope="function")
def discussion_with_lang_prefs(request, test_session, discussion):
    """An empty Discussion fixture with locale preferences"""
    discussion.discussion_locales = ['en', 'fr', 'ja']
    test_session.commit()

    return discussion


@pytest.fixture(scope="function")
def closed_discussion(request, test_session, discussion):
    """An empty Discussion fixture restricted-to-social login"""
    from assembl.models import Role, DiscussionPermission, Permission
    discussion.preferences['authorization_server_backend'] = 'google-oauth2'
    role = test_session.query(Role).filter_by(name=R_PARTICIPANT).first()
    # Take the read for everyone, put it on participant
    dp = test_session.query(DiscussionPermission).join(Permission).filter(
        DiscussionPermission.discussion==discussion, Permission.name==P_READ).first()
    dp.role = role
    test_session.commit()

    return discussion
