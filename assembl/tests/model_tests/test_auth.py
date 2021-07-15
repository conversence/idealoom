# -*- coding: utf-8 -*-
from datetime import datetime


def test_subscribe_to_discussion(
        test_session, discussion, participant2_user):
    test_session.flush()
    # Removing the following assert makes the test pass.  Obviously it has the side
    # effect that the nest time we use it, the data in the relationship is stale
    assert discussion not in participant2_user.participant_in_discussion, "The user should not already be subscribed to the discussion for this test"
    participant2_user.subscribe(discussion)
    test_session.flush()
    test_session.refresh(participant2_user)
    assert discussion in participant2_user.participant_in_discussion, "The user should now be subscribed to the discussion"
    participant2_user.unsubscribe(discussion)
    test_session.flush()
    assert discussion in participant2_user.participant_in_discussion, "The user should no longer be subscribed to the discussion"


def test_general_expiry(
        test_session, participant1_user, participant1_social_account, discussion):
    long_ago = datetime(2000, 1, 1)
    now = datetime.utcnow()
    # if all logins are old, our login is expired
    participant1_user.last_idealoom_login = long_ago
    participant1_social_account.last_checked = long_ago
    assert participant1_user.login_expired(discussion)
    # if either social or assembl login is recent, our login is valid
    participant1_user.last_idealoom_login = now
    test_session.flush()
    assert not participant1_user.login_expired(discussion)
    participant1_user.last_idealoom_login = long_ago
    participant1_social_account.last_checked = now
    test_session.flush()
    assert not participant1_user.login_expired(discussion)


def test_restricted_discussion_expiry(
        test_session, participant1_user, participant1_social_account,
        closed_discussion):
    long_ago = datetime(2000, 1, 1)
    now = datetime.utcnow()
    # if our logins are old, our login is still expired
    participant1_user.last_idealoom_login = long_ago
    participant1_social_account.last_checked = long_ago
    test_session.flush()
    assert participant1_user.login_expired(closed_discussion)
    # if our last login was through assembl, no change
    participant1_user.last_idealoom_login = now
    test_session.flush()
    assert participant1_user.login_expired(closed_discussion)
    # only appropriate social login counts
    participant1_user.last_idealoom_login = long_ago
    participant1_social_account.last_checked = now
    test_session.flush()
    assert not participant1_user.login_expired(closed_discussion)


def test_restricted_discussion_expiry_override(
        test_session, admin_user, admin_social_account, closed_discussion):
    long_ago = datetime(2000, 1, 1)
    now = datetime.utcnow()
    # if our logins are old, our login is still expired
    admin_user.last_idealoom_login = long_ago
    admin_social_account.last_checked = long_ago
    test_session.flush()
    assert admin_user.login_expired(closed_discussion)
    # if our last login was through assembl, works because override
    admin_user.last_idealoom_login = now
    test_session.flush()
    assert not admin_user.login_expired(closed_discussion)
    # appropriate social login still counts
    admin_user.last_idealoom_login = long_ago
    admin_social_account.last_checked = now
    test_session.flush()
    assert not admin_user.login_expired(closed_discussion)
