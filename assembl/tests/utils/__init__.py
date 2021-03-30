"""
All utility methods, classes and functions needed for testing applications
"""

from builtins import str
from builtins import object
from itertools import chain

from webtest import TestRequest
from webob.request import environ_from_url
from pyramid.request import apply_request_extensions
from pyramid.threadlocal import manager

from assembl.lib.sqla import (
    get_session_maker, get_metadata, mark_changed)
from assembl.lib import logging


log = logging.getLogger('pytest.assembl')


class PyramidWebTestRequest(TestRequest):
    """
    A mock Pyramid web request this pushes itself onto the threadlocal stack
    that also contains the user_id according to authentication model.
    This is very useful because throughout the model logic, a request is often
    required to determine the current_user, but outside of a Pyramid view. The
    way a request is injected is via the current_thread from threadlocal.
    """
    def __init__(self, *args, **kwargs):
        super(PyramidWebTestRequest, self).__init__(*args, **kwargs)
        manager.push({'request': self, 'registry': self.registry})
        self._base_pyramid_request = self._pyramid_app.request_factory(
            self.environ)
        self._base_pyramid_request.registry = self.registry
        apply_request_extensions(self)

    def populate(self):
        # This happens if the request is used through the app
        # but sometimes we need to simulate that
        routes_mapper = self._pyramid_app.routes_mapper
        info = routes_mapper(self)
        match, route = info['match'], info['route']
        if route:
            self.matchdict = match
            self.matched_route = route

        traverser = self._traverser()
        self.__dict__.update(traverser(self))

    @property
    def session(self):
        return self._base_pyramid_request.session

    def _traverser(self):
        from pyramid.traversal import ResourceTreeTraverser
        ctx_root = self._pyramid_app.root_factory(self)
        return ResourceTreeTraverser(ctx_root)

    def get_response(self, app, catch_exc_info=True):
        try:
            super(PyramidWebTestRequest, app).get_response(
                catch_exc_info=catch_exc_info)
        finally:
            manager.pop()

    def route_path(self, name, *args, **kwargs):
        return self._base_pyramid_request.route_path(
            name, *args, **kwargs)

    def route_url(self, name, *args, **kwargs):
        return self._base_pyramid_request.route_url(
            name, *args, **kwargs)

    # TODO: Find a way to change user here
    authenticated_userid = None
    unauthenticated_userid = None

    # How come this is missing in TestRequest?
    # TODO: Use the negotiator
    locale_name = 'en'


def committing_session_tween_factory(handler, registry):
    # This ensures that the app has the latest state
    def committing_session_tween(request):
        get_session_maker().commit()
        # Discussion may have been reified too early on request
        for item in ('discussion', 'discussion_id'):
            if request.__dict__.get(item, item) is None:
                del request.__dict__[item]
        resp = handler(request)
        get_session_maker().flush()
        return resp

    return committing_session_tween


def as_boolean(s):
    if isinstance(s, bool):
        return s
    return str(s).lower() in ['true', '1', 'on', 'yes']


def get_all_tables(app_settings, session, reversed=True):
    schema = app_settings.get('db_schema', 'assembl_test')
    # TODO: Quote schema name!
    res = session.execute(
        "SELECT table_name FROM "
        "information_schema.tables WHERE table_schema = "
        "'%s' ORDER BY table_name" % (schema,)).fetchall()
    res = {row[0] for row in res}
    # get the ordered version to minimize cascade.
    # cascade does not exist on virtuoso.
    import assembl.models
    ordered = [t.name for t in get_metadata().sorted_tables
               if t.name in res]
    ordered.extend([t for t in res if t not in ordered])
    if reversed:
        ordered.reverse()
    log.debug('Current tables: %s' % str(ordered))
    return ordered


def self_referential_columns(table):
    return [fk.parent for fk in chain(*[
                c.foreign_keys for c in table.columns])
            if fk.column.table == table]


def clear_rows(app_settings, session):
    log.info('Clearing database rows.')
    tables_by_name = {
        t.name: t for t in get_metadata().sorted_tables}
    for table_name in get_all_tables(app_settings, session):
        log.debug("Clearing table: %s" % table_name)
        table = tables_by_name.get(table_name, None)
        if table is not None:
            cols = self_referential_columns(table)
            if len(cols):
                for col in cols:
                    session.execute("UPDATE %s SET %s=NULL" % (table_name, col.key))
                session.flush()
        session.execute("DELETE FROM \"%s\"" % table_name)
    session.commit()
    session.transaction.close()


def drop_tables(app_settings, session):
    log.info('Dropping all tables.')
    # postgres. Thank you to
    # http://stackoverflow.com/questions/5408156/how-to-drop-a-postgresql-database-if-there-are-active-connections-to-it
    session.close()
    # session.execute(
    #     """SELECT pg_terminate_backend(pg_stat_activity.pid)
    #         FROM pg_stat_activity
    #         WHERE pg_stat_activity.datname = '%s'
    #           AND pid <> pg_backend_pid()""" % (
    #             app_settings.get("db_database")))

    try:
        for row in get_all_tables(app_settings, session):
            log.debug("Dropping table: %s" % row)
            session.execute("drop table \"%s\"" % row)
            session.commit()
        mark_changed()
    except Exception as e:
        raise Exception('Error dropping tables: %s' % e)


def base_fixture_dirname():
    from os.path import dirname
    return dirname(dirname(dirname(dirname(__file__)))) +\
        "/assembl/static/js/app/tests/fixtures/"


def api_call_to_fname(api_call, method="GET", **args):
    """Translate an API call to a filename containing most of the call information

    Used in :js:func:`ajaxMock`"""    
    import os
    import os.path
    base_fixture_dir = base_fixture_dirname()
    api_dir, fname = api_call.rsplit("/", 1)
    api_dir = base_fixture_dir + api_dir
    if not os.path.isdir(api_dir):
        os.makedirs(api_dir)
    args = list(args.items())
    args.sort()
    args = "_".join("%s_%s" % x for x in args)
    if args:
        fname += "_" + args
    if method != "GET":
        fname = method + "_" + fname
    fname += ".json"
    return os.path.join(api_dir, fname)


class RecordingApp(object):
    "Decorator for the test_app"
    def __init__(self, test_app):
        self.app = test_app

    def __getattribute__(self, name):
        if name not in {
                "get", "post", "post_json", "put", "put_json",
                "delete", "patch", "patch_json"}:
            return super(RecordingApp, self).__getattribute__(name)

        def appmethod(url, params=None, headers=None):
            r = getattr(self.app, name)(url, params, headers)
            assert 200 <= r.status_code < 300
            params = params or {}
            methodname = name.split("_")[0].upper()
            with open(api_call_to_fname(url, methodname, **params), "wb") as f:
                f.write(r.body)
            return r
        return appmethod
