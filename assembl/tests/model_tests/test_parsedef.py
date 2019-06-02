# -*- coding: utf-8 -*-

from __future__ import print_function
from assembl.auth import Permissions


def _test_load_fixture(request, discussion, fixture):
    request.matchdict = {'discussion_slug': discussion.slug}
    json = fixture.generic_json(permissions=(Permissions.SYSADMIN, ))
    print(fixture.__dict__)
    request.populate()
    context = fixture.get_instance_context(request=request)
    fixture.update_from_json(json, context=context)
    print(fixture.__dict__)
    assert not discussion.db.is_modified(fixture, True)


def test_load_discussion(test_adminuser_webrequest, discussion):
    _test_load_fixture(test_adminuser_webrequest, discussion, discussion)


def test_load_participant1_user(
        test_adminuser_webrequest, discussion, participant1_user):
    _test_load_fixture(
        test_adminuser_webrequest, discussion, participant1_user)


def test_load_abstract_mailbox(
        test_adminuser_webrequest, discussion, abstract_mailbox):
    _test_load_fixture(
        test_adminuser_webrequest, discussion, abstract_mailbox)


def test_load_jack_layton_mailbox(
        test_adminuser_webrequest, discussion, jack_layton_mailbox):
    _test_load_fixture(
        test_adminuser_webrequest, discussion, jack_layton_mailbox)


def test_load_root_post_1(
        test_adminuser_webrequest, discussion, root_post_1):
    _test_load_fixture(
        test_adminuser_webrequest, discussion, root_post_1)


def test_load_subidea_1(test_adminuser_webrequest, discussion, subidea_1):
    _test_load_fixture(test_adminuser_webrequest, discussion, subidea_1)


def _test_load_synthesis_1(
        test_adminuser_webrequest, discussion, synthesis_1):
    _test_load_fixture(test_adminuser_webrequest, discussion, synthesis_1)


def _test_load_extract_post_1_to_subidea_1_1(
        test_adminuser_webrequest, discussion, admin_user,
        extract_post_1_to_subidea_1_1):
    _test_load_fixture(
        test_adminuser_webrequest, discussion, extract_post_1_to_subidea_1_1)


def test_load_mailbox(
        test_adminuser_webrequest, discussion, jack_layton_mailbox):
    _test_load_fixture(
        test_adminuser_webrequest, discussion, jack_layton_mailbox)
