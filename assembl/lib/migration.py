"""Basic infrastructure for alembic migration"""
from __future__ import absolute_import

import sys
from contextlib import contextmanager

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.environment import EnvironmentContext
from alembic.script import ScriptDirectory
import transaction

from ..lib.sqla import (
    get_metadata, get_session_maker, mark_changed, is_zopish)
from ..lib.text_search import update_indices


def has_tables(db):
    (num_tables,) = db.query(
        """COUNT(table_name) FROM information_schema.tables
        WHERE table_schema='public'""").first()
    # don't count alembic
    return num_tables > 1


@contextmanager
def locked_transaction(db, num):
    # use a pg_advisory_lock to make sure that the transaction is locked.
    # Do it on another connection, so errors will not leave the lock dangling.
    cnx = db.session_factory.kw['bind'].connect()
    cnx.execute("select pg_advisory_lock(%d)" % num).first()
    try:
        session = db()
        with transaction.manager:
            session = db()
            yield session
            mark_changed(session)
    finally:
        cnx.execute("select pg_advisory_unlock(%d)" % num)
        cnx.close()


def bootstrap_db(config_uri, with_migration=True):
    """Bring a blank database to a functional state."""
    config = Config(config_uri)
    script_dir = ScriptDirectory.from_config(config)
    heads = script_dir.get_heads()

    if len(heads) > 1:
        sys.stderr.write('Error: migration scripts have more than one '
                         'head.\nPlease resolve the situation before '
                         'attempting to bootstrap the database.\n')
        sys.exit(2)
    elif len(heads) == 0:
        sys.stderr.write('Error: migration scripts have no head.\n')
        sys.exit(2)
    head = heads[0]
    db = get_session_maker()
    db.flush()
    if not has_tables(db()):
        with locked_transaction(db, 1234) as session:
            context = MigrationContext.configure(session.connection())
            if not has_tables(session):
                import assembl.models
                get_metadata().create_all(session.connection())
                assert has_tables(session)
                context._ensure_version_table()
                context.stamp(script_dir, head)
    elif with_migration:
        context = MigrationContext.configure(db().connection())
        db_version = context.get_current_revision()
        # artefact: in tests, db_version may be none.
        if db_version and db_version != head:
            def migration_fn(heads, context):
                with locked_transaction(db, 1235) as session:
                    context = MigrationContext.configure(session.connection())
                    db_version = context.get_current_revision()
                    if db_version != head:
                        return script_dir._upgrade_revs(head, db_version)
                    session.commit()

            with EnvironmentContext(
                config,
                script_dir,
                fn=migration_fn,
                as_sql=False,
                destination_rev=head
            ):
                script_dir.run_env()
            context = MigrationContext.configure(db().connection())
            db_version = context.get_current_revision()
            assert db_version == head
    return db


def bootstrap_db_data(db, mark=True):
    from .config import get
    if get('in_alembic'):
        return
    # import after session to delay loading of BaseOps
    from assembl.models import (
        Permission, Role, IdentityProvider, LocaleLabel, URIRefDb)
    from .generic_pointer import init_dbtype
    from .database_functions import ensure_functions
    with locked_transaction(db, 1236) as session:
        for cls in (Permission, Role, IdentityProvider, LocaleLabel, URIRefDb):
            cls.populate_db(session)
        ensure_functions(session)
        update_indices(session)
        init_dbtype(session)
        mark_changed(session)


def ensure_db_version(config_uri, session_maker):
    """Exit if database is not up-to-date."""
    config = Config(config_uri)
    script_dir = ScriptDirectory.from_config(config)
    heads = script_dir.get_heads()

    if len(heads) > 1:
        sys.stderr.write('Error: migration scripts have more than one head.\n'
                         'Please resolve the situation before attempting to '
                         'start the application.\n')
        sys.exit(2)
    else:
        repo_version = heads[0] if heads else None

    context = MigrationContext.configure(session_maker()().connect())
    db_version = context.get_current_revision()

    if not db_version:
        sys.stderr.write('Database not initialized.\n'
                         'Try this: "idealoom-db-manage %s bootstrap".\n'
                         % config_uri)
        sys.exit(2)

    if db_version != repo_version:
        sys.stderr.write('Stopping: DB version (%s) not up-to-date (%s).\n'
                         % (db_version, repo_version))
        sys.stderr.write('Try this: "idealoom-db-manage %s upgrade head".\n'
                         % config_uri)
        sys.exit(2)


def is_migration_script():
    """Determine weather the current process is a migration script."""
    return 'alembic' in sys.argv[0] or 'idealoom-db-manage' in sys.argv[0]


def includeme(config):
    """Initialize Alembic-related stuff at app start-up time."""
    skip_migration = config.registry.settings.get('app.skip_migration')
    if not skip_migration and not is_migration_script():
        ensure_db_version(
            config.registry.settings['config_uri'], get_session_maker())
