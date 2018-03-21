"""
The core fixtures that will:
    1) create the test database
    2) create the tables
    3) create the schema, based on the models
    4) drop the tables (upon completion)
    5) create a pyramid test application
    6) create a databse session
    7) A fixture for a headless browser
"""
from __future__ import print_function

from datetime import datetime

import pytest
import transaction
from webtest import TestApp
from pkg_resources import get_distribution
from pyramid.threadlocal import manager
from pyramid import testing
from pytest_localserver.http import WSGIServer
from splinter import Browser
import traceback

import assembl
from assembl.lib.config import get_config
from assembl.lib.migration import bootstrap_db, bootstrap_db_data
from assembl.lib.sqla import get_session_maker
from assembl.tasks import configure as configure_tasks
from assembl.auth import R_SYSADMIN
from ..utils import PyramidWebTestRequest
from ..utils import clear_rows, drop_tables


@pytest.fixture(scope="session")
def session_factory(request):
    """An SQLAlchemy Session Maker fixture"""

    # Get the zopeless session maker,
    # while the Webtest server will use the
    # default session maker, which is zopish.
    session_factory = get_session_maker()

    def fin():
        print("finalizer session_factory")
        session_factory.remove()
    request.addfinalizer(fin)
    return session_factory


@pytest.fixture(scope="session")
def empty_db(request, session_factory):
    """An SQLAlchemy Session Maker fixture with all tables dropped"""
    session = session_factory()
    drop_tables(get_config(), session)
    return session_factory


@pytest.fixture(scope="session")
def db_tables(request, empty_db):
    """An SQLAlchemy Session Maker fixture with all tables
    based on testing.ini"""

    app_settings_file = request.config.getoption('test_settings_file')
    assert app_settings_file
    from assembl.conftest import engine
    bootstrap_db(app_settings_file, engine)
    transaction.commit()

    def fin():
        print("finalizer db_tables")
        session = empty_db()
        drop_tables(get_config(), session)
        transaction.commit()
    request.addfinalizer(fin)
    return empty_db  # session_factory


@pytest.fixture(scope="session")
def base_registry(request):
    """A Zope registry that is configured by with the testing.ini"""
    from assembl.views.traversal import root_factory
    from assembl.lib.logging import includeme as configure_logging
    from pyramid.config import Configurator
    from zope.component import getGlobalSiteManager
    registry = getGlobalSiteManager()
    config = Configurator(registry)
    config.setup_registry(
        settings=get_config(), root_factory=root_factory)
    configure_logging(config)
    configure_tasks(registry, 'assembl')
    config.add_tween('assembl.tests.utils.committing_session_tween_factory')
    return registry


@pytest.fixture(scope="module")
def test_app_no_perm(request, base_registry, db_tables):
    """A configured IdeaLoom fixture with no permissions"""
    global_config = {
        '__file__': request.config.getoption('test_settings_file'),
        'here': get_distribution('assembl').location
    }
    config = dict(get_config())
    config['nosecurity'] = True
    app = TestApp(assembl.main(global_config, **config))
    app.PyramidWebTestRequest = PyramidWebTestRequest
    PyramidWebTestRequest._pyramid_app = app.app
    PyramidWebTestRequest.registry = base_registry
    return app


@pytest.fixture(scope="function")
def test_webrequest(request, test_app_no_perm, base_registry):
    """A Pyramid request fixture with no user authorized"""
    req = PyramidWebTestRequest.blank('/', method="GET")

    def fin():
        print("finalizer test_webrequest")
        # The request was not called
        manager.pop()
    request.addfinalizer(fin)
    return req


@pytest.fixture(scope="module")
def db_default_data(
        request, db_tables, base_registry):
    """An SQLAlchemy Session Maker fixture that is preloaded
    with all platform tables, constraints, relationships, etc."""

    bootstrap_db_data(db_tables)
    transaction.commit()

    def fin():
        print("finalizer db_default_data")
        session = db_tables()
        clear_rows(get_config(), session)
        transaction.commit()
    request.addfinalizer(fin)
    return db_tables  # session_factory


@pytest.fixture(scope="function")
def test_session(request, db_default_data):
    """An SQLAlchemy Session Maker fixture (A DB connection session)-
    Use this session fixture for all fixture purposes"""

    session = db_default_data()

    def fin():
        print("finalizer test_session")
        try:
            session.commit()
            #session.close()
        except Exception as e:
            traceback.print_exc()
            # import pdb; pdb.post_mortem()
            session.rollback()
    request.addfinalizer(fin)
    return session


@pytest.fixture(scope="function")
def admin_user(request, test_session, db_default_data):
    """A User fixture with R_SYSADMIN role"""

    from assembl.models import User, UserRole, Role
    u = User(name=u"Mr. Administrator", type="user",
        verified=True, last_idealoom_login=datetime.utcnow())
    from assembl.models import EmailAccount
    account = EmailAccount(email="admin@assembl.com", profile=u, verified=True)

    test_session.add(u)
    r = Role.get_role(R_SYSADMIN, test_session)
    ur = UserRole(user=u, role=r)
    test_session.add(ur)
    test_session.flush()
    uid = u.id

    def fin():
        print("finalizer admin_user")
        # I often get expired objects here, and I need to figure out why
        user = test_session.query(User).get(uid)
        user_role = user.roles[0]
        test_session.delete(user_role)
        test_session.delete(user)
        test_session.flush()
    request.addfinalizer(fin)
    return u


@pytest.fixture(scope="function")
def test_adminuser_webrequest(request, admin_user, test_app_no_perm, base_registry):
    """A Pyramid request fixture with an ADMIN user authorized"""
    req = PyramidWebTestRequest.blank('/', method="GET")
    req.authenticated_userid = admin_user.id

    def fin():
        # The request was not called
        manager.pop()
    request.addfinalizer(fin)
    return req


@pytest.fixture(scope="function")
def testing_configurator(request, test_app_no_perm):
    """The testing configurator"""

    return testing.setUp(
        registry=test_app_no_perm.app.registry,
        settings=get_config(),
    )


@pytest.fixture(scope="function")
def admin_auth_policy(request, admin_user, testing_configurator):
    """A Dummy authorization/authentication policy
    with the admin user logged in"""

    return testing_configurator.testing_securitypolicy(
        userid=admin_user.id, permissive=True)


@pytest.fixture(scope="function")
def participant_auth_policy(request, participant1_user, testing_configurator):
    """A Dummy authorization/authentication policy
    with a participant user logged in"""

    return testing_configurator.testing_securitypolicy(
        userid=participant1_user.id, permissive=True)


@pytest.fixture(scope="function")
def nologin_auth_policy(request, participant1_user, testing_configurator):
    """A Dummy authorization/authentication policy
    with no user logged in"""

    return testing_configurator.testing_securitypolicy(
        userid=None, permissive=False)


@pytest.fixture(scope="function")
def test_app(
        request, test_app_no_perm, testing_configurator, admin_auth_policy):
    """A configured IdeaLoom fixture with permissions
    and an admin user logged in"""

    testing_configurator.set_authorization_policy(admin_auth_policy)
    testing_configurator.set_authentication_policy(admin_auth_policy)
    return test_app_no_perm


@pytest.fixture(scope="function")
def test_app_no_login(
        request, test_app_no_perm, testing_configurator, nologin_auth_policy):
    """A configured IdeaLoom fixture with permissions
    and no user logged in"""
    testing_configurator.set_authorization_policy(nologin_auth_policy)
    testing_configurator.set_authentication_policy(nologin_auth_policy)
    return test_app_no_perm


@pytest.fixture(scope="function")
def test_server(request, test_app, empty_db):
    """A uWSGI server fixture with permissions, admin user logged in"""

    server = WSGIServer(application=test_app.app)
    server.start()

    def fin():
        print("finalizer test_server")
        server.stop()
    request.addfinalizer(fin)
    return server


@pytest.fixture(scope="module")
def browser(request):
    """A Splinter-based browser fixture - used for integration
    testing"""

    import sys
    import os
    from os.path import exists, join
    if sys.platform in ('linux', 'linux2'):
        for path in ('/usr/lib/chromium-browser',  # ubuntu
                     '/usr/lib/chromium'):  # debian jessie (on stretch it's /usr/bin/chromedriver)
            if exists(join(path, 'chromedriver')):  # ubuntu
                os.environ["PATH"] += ":" + path
                os.environ["LD_LIBRARY_PATH"] = path
                break
    browser = Browser('chrome', headless=True)

    def fin():
        print("finalizer browser")
        browser.quit()
    request.addfinalizer(fin)

    return browser


@pytest.fixture(scope="function")
def json_representation_of_fixtures(
        request, discussion, jack_layton_linked_discussion, test_app):
    from assembl.tests.utils import RecordingApp, base_fixture_dirname

    from shutil import rmtree
    from os.path import isdir
    base_fixture_dir = base_fixture_dirname()
    if isdir(base_fixture_dir + "api"):
        rmtree(base_fixture_dir + "api")
    if isdir(base_fixture_dir + "data"):
        rmtree(base_fixture_dir + "data")

    rec_app = RecordingApp(test_app)
    rec_app.get("/api/v1/discussion/%d/ideas" % discussion.id)
    rec_app.get("/api/v1/discussion/%d/posts" % discussion.id,
                {"view": "partial_post"})
    rec_app.get("/api/v1/discussion/%d/explicit_subgraphs/synthesis" % discussion.id)
    rec_app.get("/data/Conversation/%d/idea_links" % discussion.id)
    rec_app.get("/data/Conversation/%d/widgets" % discussion.id)
    rec_app.get("/data/Conversation/%d/settings/default_table_of_ideas_collapsed_state" % discussion.id)
    rec_app.get("/data/Conversation/%d/user_ns_kv/expertInterface_group_0_table_of_ideas_collapsed_state" % discussion.id)
    rec_app.get("/data/Conversation/%d/all_users/current/language_preference" % discussion.id)

    return None
