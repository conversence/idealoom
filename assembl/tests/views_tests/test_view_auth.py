# -*- coding: utf-8 -*-
from future import standard_library
standard_library.install_aliases()
from builtins import next
from collections import OrderedDict
import urllib.parse
from datetime import datetime

import pytest
import simplejson as json
from requests import Response
import mock
from pyramid.interfaces import ISessionFactory, IAuthorizationPolicy
from pyramid.request import Request

from assembl.models import SocialAuthAccount


def test_assembl_login(discussion, participant1_user,
                       test_app_no_login, request):
    url = test_app_no_login.app.request_factory({}).route_path(
        'contextual_login', discussion_slug=discussion.slug)
    # here we have to know it's "password", as the non-hashed password value
    # is not stored in the object.
    res = test_app_no_login.post(url, OrderedDict([
        ('identifier', participant1_user.get_preferred_email()),
        ('password', 'password')]))
    assert (res.status_code == 302 and urllib.parse.urlparse(
        res.location).path == '/' + discussion.slug + '/')
    assert test_app_no_login.app.registry.getUtility(
        IAuthorizationPolicy).remembered == participant1_user.id


def test_assembl_login_mixed_case(discussion, participant1_user,
                                  test_app_no_login, request):
    """Check that the login process works with weird case in email"""
    url = test_app_no_login.app.request_factory({}).route_path(
        'contextual_login', discussion_slug=discussion.slug)
    # here we have to know it's "password", as the non-hashed password value
    # is not stored in the object.
    res = test_app_no_login.post(url, OrderedDict([
        ('identifier',
         participant1_user.get_preferred_email().title()),
        ('password', 'password')]))
    assert (res.status_code == 302 and urllib.parse.urlparse(
        res.location).path == '/' + discussion.slug + '/')
    assert test_app_no_login.app.registry.getUtility(
        IAuthorizationPolicy).remembered == participant1_user.id


fake_facebook_locale_info = """<?xml version='1.0'?>
<locales>
<locale>
<englishName>English (US)</englishName>
<codes>
<code>
<standard>
<name>FB</name>
<representation>en_US</representation>
</standard>
</code>
</codes>
</locale>
</locales>"""


# keep coordinated with participant1_user in fixtures
p1_name = "A. Barking Loon"
p1_email = 'abloon@gmail.com'
p1_uid = '111111111111111111111'

fake_social_token = json.dumps({
    "access_token": "some_token",
    "token_type": "Bearer",
    "expires_in": 3600,
    "id_token": "some_other_token"})

fake_social_profile = json.dumps({
    'access_token': 'some_token',
    'profile': 'https://plus.google.com/'+p1_uid,
    'sub': p1_uid,
    'picture': 'https://lh5.googleusercontent.com/-ui-GqpNh5Ms/'
                   'AAAAAAAAAAI/AAAAAAAAAZw/a7puhHMO_fg/photo.jpg',
    'email': p1_email,
    'id': p1_uid,
    'id_token': 'some_other_token',
    'locale': 'en',
    'family_name': 'Loon',
    'given_name': 'A. Barking',
    'name': p1_name,
    'objectType': 'person',
    'email_verified': True,
})

fake_responses = {
    "https://accounts.google.com/o/oauth2/token": fake_social_token,
    "https://www.googleapis.com/oauth2/v3/userinfo": fake_social_profile,
    "https://www.facebook.com/translations/FacebookLocales.xml":
        fake_facebook_locale_info
}


def fake_response_handler(url=None, **kwargs):
    r = Response()
    r.status_code = 200
    r.encoding = "utf-8"
    assert url in fake_responses, "unknown URL: " + url
    r._content = fake_responses[url].encode("utf-8")
    return r


def test_social_login(
        test_session, test_app, discussion, google_identity_provider, request,
        test_webrequest):
    path = test_webrequest.route_path(
        'social.auth', backend=google_identity_provider.provider_type)
    res = test_app.get(path)
    assert res.status_code == 302  # Found
    url = urllib.parse.urlparse(res.location)
    qs = urllib.parse.parse_qs(url.query)
    state = qs['state']
    with mock.patch('requests.sessions.Session.request') as mock_request:
        mock_request.side_effect = fake_response_handler
        path = test_webrequest.route_path(
            'social.complete', backend=google_identity_provider.provider_type)
        code = 'code'
        session_state = 'session_state'
        res2 = test_app.get(path, {
            'state': state,
            'code': code,
            'authuser': '0',
            'session_state': session_state,
            'prompt': 'none'})
        assert res2.status_code == 302
        assert mock_request.call_count > 1
        urls_called = {call[1]['url'] for call in mock_request.call_args_list}
        assert "https://www.googleapis.com/oauth2/v3/userinfo" in urls_called
    account = test_session.query(SocialAuthAccount).filter_by(
        email=p1_email).first()
    assert account
    assert account.uid == p1_uid
    assert account.profile.name == p1_name
    account.delete()
    account.profile.delete()


def test_add_social_account(
        test_session, test_app, discussion, admin_user,
        google_identity_provider, base_registry, test_webrequest):
    session_factory = base_registry.getUtility(ISessionFactory)
    path = test_webrequest.route_path(
        'social.auth', backend=google_identity_provider.provider_type)
    res = test_app.get(path)
    assert res.status_code == 302  # Found
    url = urllib.parse.urlparse(res.location)
    qs = urllib.parse.parse_qs(url.query)
    state = qs['state']
    cookie = next(iter(test_app.cookiejar))
    beaker_session = session_factory(Request.blank(
        "/", cookies={cookie.name: cookie.value}))
    beaker_session["add_account"] = True
    beaker_session.persist()

    with mock.patch('requests.sessions.Session.request') as mock_request:
        mock_request.side_effect = fake_response_handler
        path = test_webrequest.route_path(
            'social.complete', backend=google_identity_provider.provider_type)
        code = 'code'
        session_state = 'session_state'
        res2 = test_app.get(path, {
            'state': state,
            'code': code,
            'authuser': '0',
            'session_state': session_state,
            'prompt': 'none'})
        assert res2.status_code == 302
        assert mock_request.call_count > 1
        urls_called = {call[1]['url'] for call in mock_request.call_args_list}
        assert "https://www.googleapis.com/oauth2/v3/userinfo" in urls_called
    account = test_session.query(SocialAuthAccount).filter_by(
        email=p1_email).first()
    assert account
    assert account.uid == p1_uid
    assert account.profile == admin_user
    account.delete()


def test_merge_social_account(
        test_session, test_app, discussion, participant1_user,
        google_identity_provider, base_registry, test_webrequest):
    path = test_webrequest.route_path(
        'social.auth', backend=google_identity_provider.provider_type)
    res = test_app.get(path)
    assert res.status_code == 302  # Found
    url = urllib.parse.urlparse(res.location)
    qs = urllib.parse.parse_qs(url.query)
    state = qs['state']
    with mock.patch('requests.sessions.Session.request') as mock_request:
        mock_request.side_effect = fake_response_handler
        path = test_webrequest.route_path(
            'social.complete', backend=google_identity_provider.provider_type)
        code = 'code'
        session_state = 'session_state'

        res2 = test_app.get(path, {
            'state': state,
            'code': code,
            'authuser': '0',
            'session_state': session_state,
            'prompt': 'none'})
        assert res2.status_code == 302
        assert mock_request.call_count > 1
        urls_called = {call[1]['url'] for call in mock_request.call_args_list}
        assert "https://www.googleapis.com/oauth2/v3/userinfo" in urls_called
    account = test_session.query(SocialAuthAccount).filter_by(
        email=p1_email).first()
    assert account
    assert account.uid == p1_uid
    assert account.profile == participant1_user
    account.delete()


def test_autologin(
        test_session, test_app_participant1, closed_discussion, participant1_user,
        participant1_social_account, google_identity_provider, request,
        test_participant1_webrequest):
    # as a logged in participant, I can see the discussion
    long_ago = datetime(2000, 1, 1)
    now = datetime.utcnow()
    participant1_user.last_idealoom_login = now
    participant1_social_account.last_checked = now
    path = test_participant1_webrequest.route_path(
        'home', discussion_slug=closed_discussion.slug)
    reply = test_app_participant1.get(path)
    assert reply.status_code == 200
    # unless my social login is expired
    participant1_social_account.last_checked = long_ago
    reply = test_app_participant1.get(path)
    assert reply.status_code == 307
    assert test_participant1_webrequest.route_path(
        'contextual_social.auth',
        discussion_slug=closed_discussion.slug,
        backend=google_identity_provider.name
    ) == urllib.parse.urlparse(reply.location).path


def test_autologin_override(
        test_session, test_app, closed_discussion, admin_user,
        admin_social_account, google_identity_provider, request,
        test_adminuser_webrequest):
    # as an admin, I can see the discussion based on my assembl login
    long_ago = datetime(2000, 1, 1)
    now = datetime.utcnow()
    admin_social_account.last_checked = long_ago
    admin_user.last_idealoom_login = now
    path = test_adminuser_webrequest.route_path(
        'home', discussion_slug=closed_discussion.slug)
    reply = test_app.get(path)
    assert reply.status_code == 200
    # unless my assembl login is also expired
    admin_user.last_idealoom_login = long_ago
    reply = test_app.get(path)
    assert reply.status_code == 307
    assert test_adminuser_webrequest.route_path(
        'contextual_social.auth',
        discussion_slug=closed_discussion.slug,
        backend=google_identity_provider.name
    ) == urllib.parse.urlparse(reply.location).path
