"""Some utilities for working with SQLAlchemy, and the definition of BaseOps."""

from __future__ import absolute_import
from __future__ import division

from builtins import bytes
from builtins import str as newstr
from builtins import next
from builtins import range
from builtins import object
import re
import sys
from datetime import datetime
import inspect as pyinspect
import types
from collections import Iterable, defaultdict
from contextlib import contextmanager
import atexit
from abc import abstractmethod
from time import sleep
from random import random
from threading import Thread
from itertools import chain
from functools import partial

from future.utils import string_types, as_native_str
from past.builtins import str as past_str, unicode as past_unicode, long
from enum import Enum
from anyjson import dumps, loads
from sqlalchemy import (
    DateTime, MetaData, engine_from_config, event, Column, Integer,
    inspect, or_, and_)
from sqlalchemy.exc import NoInspectionAvailable, OperationalError
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.ext.associationproxy import (
    AssociationProxy, ObjectAssociationProxyInstance)
from sqlalchemy.orm import scoped_session, sessionmaker, aliased
from sqlalchemy.orm.interfaces import MANYTOONE, ONETOMANY, MANYTOMANY
from sqlalchemy.orm.properties import RelationshipProperty
from sqlalchemy.orm.util import has_identity
from sqlalchemy.util import classproperty
from sqlalchemy.orm.session import object_session, Session
from sqlalchemy.engine import strategies
from sqla_rdfbridge.mapping import PatternIriClass
from sqlalchemy.engine.url import URL
from zope.sqlalchemy import register
from zope.sqlalchemy.datamanager import mark_changed as z_mark_changed
from pyramid.httpexceptions import HTTPUnauthorized, HTTPBadRequest
import transaction

from .parsedatetime import parse_datetime
from ..view_def import get_view_def
from .zmqlib import get_pub_socket, send_changes
from ..semantic.namespaces import QUADNAMES
from .config import CascadingSettings
from ..auth import (
    Everyone, Authenticated, CrudPermissions, MAYBE, P_READ, R_OWNER,
    P_SYSADMIN, P_READ_IDEA)
from .decl_enums import EnumSymbol, DeclEnumType
from .utils import get_global_base_url
from .config import get_config
from . import logging
from .read_write_session import ReadWriteSession

atexit_engines = []
log = logging.getLogger()


class CrudOperation(Enum):
    DELETE = -1
    UPDATE = 0
    CREATE = 1


class DuplicateHandling(Enum):
    """How to handle duplicates. Assumes that the unique_query is valid."""
    NO_CHECK = 1        # Don't look for duplicates
    ERROR = 2           # raise a ObjectNotUniqueError
    USE_ORIGINAL = 3    # Update the original value instead of a new one.
    TOMBSTONE = 4       # Tombstone the original value (assumes TombstonableMixin) and use new one
    TOMBSTONE_AND_COPY = 5  # Make a tombstone of original value, and reuse it


class ObjectNotUniqueError(ValueError):
    pass


class CleanupStrategy(strategies.PlainEngineStrategy):
    name = 'atexit_cleanup'

    def create(self, *args, **kwargs):
        engine = super(CleanupStrategy, self).create(*args, **kwargs)
        atexit_engines.append(engine)
        return engine

CleanupStrategy()


@atexit.register
def dispose_sqlengines():
    #print "ATEXIT", atexit_engines
    [e.dispose() for e in atexit_engines]

_TABLENAME_RE = re.compile('([A-Z]+)')

_session_maker = None
db_schema = None
_metadata = None
Base = None
class_registry = {}
aliased_class_registry = None


def get_target_class(column):
    global class_registry
    # There should be an easier way???
    fk = next(iter(column.foreign_keys))
    target_table = fk.column.table
    for cls in class_registry.values():
        mapper = getattr(cls, "__mapper__", None)
        if not mapper:
            continue
        if mapper.__table__ == target_table:
            return cls


def uses_list(prop):
    "is a property a list?"
    # Weird indirection
    uselist = getattr(prop, 'uselist', None)
    if uselist is not None:
        return uselist
    subprop = getattr(prop, 'property', None)
    if subprop:
        return subprop.uselist


class TableLockCreationThread(Thread):
    """Utility class to create objects as a side effect.
    Will use an exclusive table lock to ensure that the objects
    are created only once. Does it on another thread to minimize
    the time that the table is locked. Not all object creation should
    need this, but it should be used when many connexions might attempt
    to create the same unique objects.

    :param func object_generator: a function (w/o parameters) that will
        create the objects that need to be created (as iterable).
        They will be added and committed in a subtransaction.
        Will be called many times.
    :returns: Whether there was anything added (maybe not in this process)
    """
    def __init__(self, object_generator, lock_table_name, num_attempts=3):
        super(TableLockCreationThread, self).__init__()
        self.object_generator = object_generator
        self.lock_table_name = lock_table_name
        self.lock_id = hash(lock_table_name)
        self.num_attempts = num_attempts
        self.success = None
        self.created = False

    def run(self):
        session_maker = get_session_maker()
        try:
            for num in range(self.num_attempts):
                db = session_maker()
                if session_maker.is_zopish:
                    tm = transaction.manager
                else:
                    # Ad hoc transaction manager. TODO: Use existing machinery.
                    # This is only used in testing, though.

                    @contextmanager
                    def CommittingTm(db):
                        try:
                            yield
                        except Exception as e:
                            db.rollback()
                            raise e
                        db.commit()
                    tm = CommittingTm(db)
                with tm:
                    got_lock = (db.execute("SELECT pg_try_advisory_xact_lock(%d)" % (
                            self.lock_id,)).first(), )
                    if not got_lock:
                        log.info("Could not get the table lock in attempt %d"
                                 % (num,))
                        sleep(random() / 10.0)
                        continue
                    # recalculate needed objects.
                    # There may be none left after having obtained the lock.
                    to_be_created = self.object_generator()
                    for ob in to_be_created:
                        self.created = True
                        db.add(ob)
                # implicit commit of subtransaction clears the lock
                self.success = True
                break
            else:
                log.error("Never obtained lock")
                self.success = False
        except ObjectNotUniqueError as e:
            # Should not happen anymore. Log if so.
            self.success = False
            log.error("locked_object_creation: the generator created "
                      "a non-unique object despite locking." + str(e))
            self.exception = e
        except Exception as e:
            log.error(str(e))
            self.success = False
            self.exception = e


class SimpleObjectImporter(object):
    use_local = True

    def __init__(self):
        self.init_importer()

    def init_importer(self):
        self.instance_by_id = {}

    def __getitem__(self, oid):
        oid = self.normalize_id(oid)
        return self.instance_by_id.get(oid, None)

    def __contains__(self, oid):
        oid = self.normalize_id(oid)
        return oid in self.instance_by_id

    def __setitem__(self, oid, instance):
        oid = self.normalize_id(oid)
        existing = self.instance_by_id.get(oid, None)
        if existing:
            assert existing is instance, (
                "Conflicting association:", oid, self.instance_by_id[oid], instance)
            return existing
        self.instance_by_id[oid] = instance
        self.process_association(oid, instance)

    def normalize_id(self, oid):
        if isinstance(oid, dict):
            return oid.get('@id', None)
        return oid

    def get_object(self, oid, default=None):
        # note that this is not the same as __getitem__
        oid = self.normalize_id(oid)
        if not oid:
            return None
        item = self.instance_by_id.get(oid, default)
        if self.use_local and not item:
            item = get_named_object(oid)
        return item

    def process_association(self, oid, instance):
        pass

    def fulfilled(self, source):
        return True

    def apply(self, source, target_id_or_data, promise):
        target = self.get_object(target_id_or_data)
        if target is not None:
            promise(target)

    def pending(self):
        return False


class PromiseObjectImporter(SimpleObjectImporter):
    def init_importer(self):
        super(PromiseObjectImporter, self).init_importer()
        self.promises_by_source = defaultdict(set)
        self.promises_by_target_id = defaultdict(list)

    def __setitem__(self, oid, instance):
        exists = oid in self.instance_by_id
        super(PromiseObjectImporter, self).__setitem__(oid, instance)
        # if exists:
        #     return
        while self.promises_by_target_id[oid]:
            (source, promise) = self.promises_by_target_id[oid].pop()
            promise(instance)
            self.promises_by_source[source].discard(promise)
        del self.promises_by_target_id[oid]

    def fulfilled(self, source):
        return not (source in self.promises_by_source and
                    len(self.promises_by_source[source]))
    
    def apply(self, source, target_id_or_data, promise):
        target_id = self.normalize_id(target_id_or_data)
        target = self.get_object(target_id)
        if target is not None:
            promise(target)
        else:
            # this step may not be necessary.
            # if yes, when do we treat the data?
            self.promises_by_target_id[target_id].append((source, promise))
            self.promises_by_source[source].add(promise)

    def pending(self):
        for s in self.promises_by_target_id.values():
            if len(s):
                return True


class BaseOps(object):
    """Base class for SQLAlchemy models in IdeaLoom.

    Many protocols are defined here.

    """


    # @declared_attr
    # def __tablename__(cls):
    #     """Return a table name made out of the model class name."""
    #     return _TABLENAME_RE.sub(r'_\1', cls.__name__).strip('_').lower()

    @classproperty
    def default_db(cls):
        """Return the global SQLAlchemy db session maker object.

        We often use this when we have no instance.db available;
        but it may be a different session and create instances on that other
        session, leading to obscure bugs in object relationships.
        Try to pass a session around if you need to rely on relationships.
        """
        assert _session_maker is not None
        return _session_maker

    @property
    def db(self):
        """Return the SQLAlchemy db session object. (per-http-request)"""
        return inspect(self).session or self.default_db()

    @property
    def object_session(self):
        return object_session(self)

    @classproperty
    def full_schema(cls):
        config = get_config()
        return config.get('db_schema')

    def __iter__(self, **kwargs):
        """Return a generator that iterates through model columns."""
        return self.iteritems(**kwargs)

    def iteritems(self, include=None, exclude=None):
        """Return a generator that iterates through model columns.

        Fields iterated through can be specified with include/exclude.

        """
        if include is not None and exclude is not None:
            include = set(include) - set(exclude)
            exclude = None
        for c in self.__table__.columns:
            if ((not include or c.name in include)
                    and (not exclude or c.name not in exclude)):
                yield(c.name, getattr(self, c.name))

    @classmethod
    def _col_names(cls):
        """Return a list of the columns, as a set."""
        return set(cls.__table__.c.keys())

    @classmethod
    def _pk_names(cls):
        """Return a list of the primary keys, as a set."""
        return set(cls.__table__.primary_key.columns.keys())

    @property
    def is_new_instance(self):
        """Return True if the instance wasn't fetched from the database."""
        return not has_identity(self)

    @classmethod
    def create(cls, obj=None, flush=False, **values):
        """Create an instance. Not used."""
        if obj is None:
            obj = cls(**values)
        else:
            obj.update(**values)
        obj.save(flush)
        return obj

    @classmethod
    def get_by(cls, raise_=False, **criteria):
        """Return the record corresponding to the criteria.

        Throw an exception on record not found and `raise_` == True, else
        return None.
        """
        q = _session_maker.query(cls).filter_by(**criteria)
        return raise_ and q.one() or q.first()

    @classmethod
    def get(cls, id, session=None):
        """Return the record by id."""
        session = session or cls.default_db
        return session.query(cls).get(id)

    @classmethod
    def find(cls, **criteria):
        return _session_maker.query(cls).filter_by(**criteria).all()

    def delete(self):
        _session_maker.delete(self)

    @classmethod
    def polymorphic_identities(cls):
        """Return the list of polymorphic identities defined in subclasses."""
        return [k for (k, v) in cls.__mapper__.polymorphic_map.items()
                if issubclass(v.class_, cls)]

    @classmethod
    def polymorphic_filter(cls):
        """Return a SQLA expression that tests for subclasses of this class"""
        return cls.__mapper__.polymorphic_on.in_(cls.polymorphic_identities())

    def update(self, **values):
        fields = self._col_names()
        for name, value in values.items():
            if name in fields:
                setattr(self, name, value)

    def save(self, flush=False):
        """Encapsulate db.add()."""
        if self.is_new_instance:
            _session_maker.add(self)
        if flush:
            _session_maker.flush()

    @classmethod
    def inject_api(cls, name, as_object=False):
        """Inject common methods in an API module. Unused."""
        class API(object):
            pass
        container = API() if as_object else sys.modules[name]

        for attr in 'create', 'get', 'find', 'validator':
            setattr(container, attr, getattr(cls, attr))

        if as_object:
            return container

    def get_id_as_str(self):
        """Return the primary key as a string."""
        id = getattr(self, 'id', None)
        if id is None:
            if 'id' not in self.__class__.__dict__:
                raise NotImplementedError("get_id_as_str on " +
                    self.__class__.__name__)
            return None
        return str(id)

    def tombstone(self):
        """Return a :py:class:`Tombstone` object.

        This object will be sent on the websocket
        and will express that this object has been deleted."""
        return Tombstone(self)

    def send_to_changes(self, connection=None, operation=CrudOperation.UPDATE,
                        discussion_id=None, view_def="changes"):
        """Ask for this object to be sent on the changes websocket.

        See :py:mod:`assembl.tasks.changes_router`."""
        if not connection:
            # WARNING: invalidate has to be called within an active transaction.
            # This should be the case in general, no need to add a transaction manager.
            connection = self.db.connection()
        if 'cdict' not in connection.info:
            connection.info['cdict'] = {}
        connection.info['cdict'][(self.uri(), view_def)] = (
            discussion_id, self)

    @classmethod
    def external_typename(cls):
        """What is the class name that will be sent on the API, as @type.

        Will use a class-local name defined as ``__external_typename``,
        otherwise will use the python class name directly."""
        name = cls.__name__
        return getattr(cls, '_%s__external_typename' % (name,), name)

    @classmethod
    def external_typename_list(cls):
        mro = cls.mro()
        for i, c in enumerate(mro):
            if c.__module__.startswith('sqlalchemy'):
                mro = mro[:i]
                break
        return [c.external_typename() for c in mro
                if getattr(c, 'external_typename', False)]

    @as_native_str()
    def __repr__(self):
        return "<%s id=%d >" % (
            self.external_typename(), getattr(self, 'id', None) or -1)

    @classmethod
    def base_tablename(cls):
        tablename = None
        for c in cls.mro():
            tablename = getattr(c, '__tablename__', tablename)
        return tablename

    @classmethod
    def base_concrete_class(cls):
        for c in cls.mro():
            if getattr(c, '__dict__', {}).get('__tablename__', None):
                cls = c
        return cls

    @classmethod
    def base_polymorphic_class(cls):
        """Returns the base class of this class above Base."""
        mapper_args = getattr(cls, '__mapper_args__', {})
        if mapper_args.get('polymorphic_identity', None) is not None:
            for nextclass in cls.mro():
                if getattr(nextclass, '__mapper__', None) is None:
                    continue
                if nextclass.__mapper__.polymorphic_identity is not None:
                    cls = nextclass
        return cls

    @classmethod
    def external_typename_with_inheritance(cls):
        """Returns the :py:meth:`external_typename` of the root class below this one."""
        return cls.base_polymorphic_class().external_typename()

    @classmethod
    def uri_generic(cls, id, base_uri='local:'):
        """Return the identity of this object as a URI in the `local:` namespace

        Composed from the root type name and database Id.
        The local: namespace actually corresponds to the server name,
        and is intended to become the basis of a LOD architecture."""
        if id is None:
            return None
        return base_uri + cls.external_typename_with_inheritance() + "/" + str(id)

    @classmethod
    def iri_class(cls):
        """Return an IRI pattern for instances of this class.

        The :py:meth:`uri_generic` will follow this pattern.
        Used for Virtuoso RDF-Relational mapping; disabled for now."""
        if getattr(cls, '_iri_class', 0) == 0:
            id_column = getattr(cls, 'id', None)
            if id_column is None:
                cls._iri_class = None
                return
            clsname = cls.external_typename_with_inheritance()
            iri_name = clsname + "_iri"
            cls._iri_class = PatternIriClass(
                getattr(QUADNAMES, iri_name),
                get_global_base_url() + '/data/'+clsname+'/%d',
                None, ('id', Integer, False))
        return cls._iri_class

    def container_url(self):
        """What is the URL where we expect to find this resource"""
        return '/data/' + self.__class__.external_typename()
        # Often but not always equivalent to
        # resource_path(self.get_default_parent_context())

    @classmethod
    def base_conditions(cls, alias=None, alias_maker=None):
        """Return a list of SQLA expressions that will filter out
        instances of this class

        Mostly used to exclude archived versions; see :py:mod:`assembl.lib.history_mixin`
        The exclusion pattern is used by the traversal API, and by the RDF mapping."""
        return None

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        """Returns a list of quad map patterns for RDF mapping,
        beyond those defined by introspection.

        Important: If defined somewhere, override in subclasses to avoid inheritance."""
        return []

    @classmethod
    def get_instance(cls, identifier, session=None):
        """Get an instance of this class using a numeric ID or URI."""
        try:
            # temporary hack
            num = int(identifier)
        except ValueError:
            num = cls.get_database_id(identifier)
        if num:
            # reimplement get, because can be subclassed
            session = session or cls.default_db
            return session.query(cls).get(num)

    @classmethod
    def get_database_id(cls, uri):
        """Parse a URI to extract the database ID"""
        if isinstance(uri, string_types):
            if not uri.startswith('local:') or '/' not in uri:
                return
            uriclsname, num = uri[6:].split('/', 1)
            uricls = get_named_class(uriclsname)
            if not uricls:
                return
            if uricls == cls or uricls in cls.mro() or cls in uricls.mro():
                try:
                    return int(num)
                except ValueError:
                    pass

    def uri(self, base_uri='local:'):
        """The URI of this instance.

        It may be a LOD URL if the namespace is resolved."""
        return self.uri_generic(self.get_id_as_str(), base_uri)

    @classmethod
    def get_subclasses(cls):
        """Return the list of subclasses of this class"""
        global class_registry
        from inspect import isclass
        return (c for c in class_registry.values()
                if isclass(c) and issubclass(c, cls))

    @classmethod
    def get_inheritance(cls):
        """Return a dictionary of external class names to their parent classe's name."""
        name = cls.external_typename()
        inheritance = {}
        for subclass in cls.get_subclasses():
            subclass_name = subclass.external_typename()

            if subclass_name == name:
                continue
            for supercls in subclass.mro()[1:]:
                if not supercls.__dict__.get('__mapper_args__', {}).get('polymorphic_identity', None):
                    continue
                superclass_name = supercls.external_typename()
                inheritance[subclass_name] = superclass_name
                if (superclass_name == name
                        or superclass_name in inheritance):
                    break
                subclass_name = superclass_name
        return inheritance

    @staticmethod
    def get_inheritance_for(classnames, with_ontology=True):
        """Return :py:meth:`get_inheritance` for some classes"""
        inheritance = {}
        classnames = set(classnames)
        for name in classnames:
            cls = get_named_class(name)
            inheritance.update(cls.get_inheritance())
            inheritance[name] = None
        if with_ontology:
            from assembl.semantic.inference import get_inference_store
            store = get_inference_store()
            inheritance = store.combined_inheritance(inheritance)
        inheritance = {k: v for (k, v) in inheritance.items() if v and v[0]}
        return inheritance

    @staticmethod
    def get_json_inheritance_for(classnames, with_ontology=True):
        """Return :py:meth:`get_inheritance` as a json string"""
        return dumps(Base.get_inheritance_for(classnames, with_ontology=with_ontology))

    retypeable_as = ()
    """If it is possible to mutate the class of this object after its creation,
    using :py:meth:BaseOps.change_class,
    declare here the list of classes it can be retyped into"""

    def change_class(self, newclass, json=None, **kwargs):
        """Change the class of an instance, deleting and creating table rows as needed."""
        def table_list(cls):
            tables = []
            for cls in cls.mro():
                try:
                    m = inspect(cls)
                    t = m.local_table
                    if (not tables) or tables[-1] != t:
                        tables.append(t)
                except NoInspectionAvailable:
                    break
            return tables
        oldclass_tables = table_list(self.__class__)
        newclass_tables = table_list(newclass)
        newclass_mapper = inspect(newclass)
        if newclass_tables[-1] != oldclass_tables[-1]:
            raise TypeError()
        while (newclass_tables and oldclass_tables and
                newclass_tables[-1] == oldclass_tables[-1]):
            newclass_tables.pop()
            oldclass_tables.pop()
        newclass_tables.reverse()
        setattr(self, newclass_mapper.polymorphic_on.key,
                newclass_mapper.polymorphic_identity)
        db = self.db
        id = self.id
        db.flush()
        db.expunge(self)
        for table in oldclass_tables:
            db.execute(table.delete().where(table.c.id == id))
        json = json or {}

        for table in newclass_tables:
            col_names = {c.key for c in table.c if not c.primary_key}
            local_kwargs = {k: kwargs.get(k, json.get(k, None))
                            for k in col_names}
            db.execute(table.insert().values(id=id, **local_kwargs))

        new_object = db.query(newclass).get(id)
        new_object.send_to_changes()
        return new_object

    @classmethod
    def expand_view_def(cls, view_def):
        """Return the full view_def specification for this class.

        Follows the @extend links and the _default view."""
        local_view = None
        for cls in cls.mro():
            if cls.__name__ == 'Base':
                return None
            if not issubclass(cls, BaseOps):
                # mixin
                continue
            my_typename = cls.external_typename()
            local_view = view_def.get(my_typename, None)
            if local_view is False:
                return False
            if local_view is not None:
                break
        else:
            # we never found a view
            return None
        assert isinstance(local_view, dict),\
            "in viewdef, definition for class %s is not a dict" % (
                my_typename)
        if '_default' not in local_view:
            view = local_view
            views = [view]
            local_view = dict(view_def.get('_default', {'_default': False}))
            while '@extends' in view:
                ex = view['@extends']
                assert ex in view_def,\
                    "In viewdef @extends reference to missing %s." % (ex,)
                view = view_def[ex]
                views.append(view)
            for view in reversed(views):
                local_view.update(view)
            if '@extends' in local_view:
                del local_view['@extends']
            view_def[my_typename] = local_view
        return local_view

    _methods_by_class = {}
    _props_by_class = {}
    @classmethod
    def get_single_arg_methods(cls):
        if cls not in cls._methods_by_class:
            cls._methods_by_class[cls] = dict(pyinspect.getmembers(
                cls, lambda m: (
                    pyinspect.ismethod(m) or pyinspect.isfunction(m))
                    and m.__code__.co_argcount == 1))
        return cls._methods_by_class[cls]

    @classmethod
    def get_props_of(cls):
        if cls not in cls._props_by_class:
            cls._props_by_class[cls] = dict(pyinspect.getmembers(
                cls, lambda p: pyinspect.isdatadescriptor(p)))
        return cls._props_by_class[cls]

    @property
    def imported_from_id(self):
        record = getattr(self, 'import_record', None)
        if record:
            return record.external_id

    @property
    def imported_from_url(self):
        record = getattr(self, 'import_record', None)
        if record:
            return record.source.external_id_to_uri(record.external_id)

    @property
    def imported_from_source_name(self):
        record = getattr(self, 'import_record', None)
        if record:
            return record.source.name

    def generic_json(
            self, view_def_name='default', user_id=None,
            permissions=(P_READ, P_READ_IDEA), base_uri='local:'):
        """Return a representation of this object as a JSON object,
        according to the given view_def and access control."""
        user_id = user_id or Everyone
        if not self.user_can(user_id, CrudPermissions.READ, permissions):
            return None
        view_def = get_view_def(view_def_name or 'default')
        my_typename = self.external_typename()
        result = {}
        local_view = self.expand_view_def(view_def)
        if not local_view:
            return None
        mapper = self.__class__.__mapper__
        relns = {r.key: r for r in mapper.relationships}
        cols = {c.key: c for c in mapper.columns}
        fkeys = {c for c in mapper.columns if c.foreign_keys}
        reln_of_fkeys = {
            frozenset(r._calculated_foreign_keys): r
            for r in mapper.relationships
        }
        fkey_of_reln = {r.key: r._calculated_foreign_keys
                        for r in mapper.relationships}
        methods = self.__class__.get_single_arg_methods()
        properties = self.__class__.get_props_of()
        known = set()
        for name, spec in local_view.items():
            vals = None
            if name == "_default":
                continue
            if name == "@update":
                update_dict = getattr(self, spec)
                if pyinspect.ismethod(update_dict):
                    update_dict = update_dict()
                assert isinstance(update_dict, dict)
                result.update(update_dict)
                continue
            elif spec is False:
                known.add(name)
                continue
            elif type(spec) is list:
                if not spec:
                    spec = [True]
                assert len(spec) == 1,\
                    "in viewdef %s, class %s, name %s, len(list) > 1" % (
                        view_def_name, my_typename, name)
                subspec = spec[0]
            elif type(spec) is dict:
                assert len(spec) == 1,\
                    "in viewdef %s, class %s, name %s, len(dict) > 1" % (
                        view_def_name, my_typename, name)
                assert "@id" in spec,\
                    "in viewdef %s, class %s, name %s, key should be '@id'" % (
                        view_def_name, my_typename, name)
                subspec = spec["@id"]
            else:
                subspec = spec
            if subspec is True:
                prop_name = name
                view_name = None
            else:
                assert isinstance(subspec, string_types),\
                    "in viewdef %s, class %s, name %s, spec not a string" % (
                        view_def_name, my_typename, name)
                if subspec[0] == "'":
                    # literals.
                    result[name] = loads(subspec[1:])
                    continue
                if ':' in subspec:
                    prop_name, view_name = subspec.split(':', 1)
                    if not view_name:
                        view_name = view_def_name
                    if not prop_name:
                        prop_name = name
                else:
                    prop_name = subspec
                    view_name = None
            if view_name:
                assert get_view_def(view_name),\
                    "in viewdef %s, class %s, name %s, unknown viewdef %s" % (
                        view_def_name, my_typename, name, view_name)
            #print prop_name, name, view_name

            def translate_to_json(v):
                if isinstance(v, Base):
                    p = getattr(v, 'user_can', None)
                    if p and not v.user_can(
                            user_id, CrudPermissions.READ, permissions):
                        return None
                    if view_name:
                        return v.generic_json(
                            view_name, user_id, permissions, base_uri)
                    else:
                        return v.uri(base_uri)
                elif isinstance(v, (
                        string_types, int, long, float, bool, type(None))):
                    return v
                elif isinstance(v, EnumSymbol):
                    return v.name
                elif isinstance(v, datetime):
                    return v.isoformat() + "Z"
                elif isinstance(v, dict):
                    v = {translate_to_json(k): translate_to_json(val)
                         for k, val in v.items()}
                    return {k: val for (k, val) in v.items()
                            if val is not None}
                elif isinstance(v, Iterable):
                    v = [translate_to_json(i) for i in v]
                    return [x for x in v if x is not None]
                else:
                    raise NotImplementedError("Cannot translate", v)

            if prop_name == 'self':
                if view_name:
                    r = self.generic_json(
                        view_name, user_id, permissions, base_uri)
                    if r is not None:
                        result[name] = r
                else:
                    result[name] = self.uri()
                continue
            elif prop_name == '@view':
                result[name] = view_def_name
                continue
            elif prop_name[0] == '&':
                prop_name = prop_name[1:]
                assert prop_name in methods,\
                    "in viewdef %s, class %s, name %s, unknown method %s" % (
                        view_def_name, my_typename, name, prop_name)
                # Function call. PLEASE RETURN JSON, Base objects,
                # or list or dicts thereof
                val = getattr(self, prop_name)()
                result[name] = translate_to_json(val)
                continue
            elif prop_name in cols:
                assert not view_name,\
                    "in viewdef %s, class %s, viewdef for literal property %s" % (
                        view_def_name, my_typename, prop_name)
                assert not isinstance(spec, list),\
                    "in viewdef %s, class %s, list for literal property %s" % (
                        view_def_name, my_typename, prop_name)
                assert not isinstance(spec, dict),\
                    "in viewdef %s, class %s, dict for literal property %s" % (
                        view_def_name, my_typename, prop_name)
                known.add(prop_name)
                val = getattr(self, prop_name)
                if val is not None:
                    val = translate_to_json(val)
                if val is not None:
                    result[name] = val
                continue
            elif prop_name in properties:
                known.add(prop_name)
                if view_name or (prop_name not in fkey_of_reln) or (
                        relns[prop_name].direction != MANYTOONE):
                    val = getattr(self, prop_name)
                    if val is not None:
                        val = translate_to_json(val)
                    if val is not None:
                        result[name] = val
                else:
                    fkeys = list(fkey_of_reln[prop_name])
                    assert(len(fkeys) == 1)
                    fkey = fkeys[0]
                    result[name] = relns[prop_name].mapper.class_.uri_generic(
                        getattr(self, fkey.key))

                continue
            elif isinstance(getattr(self.__class__, prop_name, None),
                    (AssociationProxy, ObjectAssociationProxyInstance)):
                vals = getattr(self, prop_name)
            else:
                assert prop_name in relns,\
                        "in viewdef %s, class %s, prop_name %s not a column, property or relation" % (
                            view_def_name, my_typename, prop_name)
                known.add(prop_name)
                # Add derived prop?
                reln = relns[prop_name]
                if reln.uselist:
                    vals = getattr(self, prop_name)
            if vals is not None:
                known.add(prop_name)
                if view_name:
                    if isinstance(spec, dict):
                        result[name] = {
                            ob.uri(base_uri):
                            ob.generic_json(
                                view_name, user_id, permissions, base_uri)
                            for ob in vals
                            if ob.user_can(
                                user_id, CrudPermissions.READ, permissions)}
                    else:
                        result[name] = [
                            ob.generic_json(
                                view_name, user_id, permissions, base_uri)
                            for ob in vals
                            if ob.user_can(
                                user_id, CrudPermissions.READ, permissions)]
                else:
                    assert not isinstance(spec, dict),\
                        "in viewdef %s, class %s, dict without viewname for %s" % (
                            view_def_name, my_typename, name)
                    result[name] = [
                        ob.uri(base_uri) for ob in vals
                        if ob.user_can(
                            user_id, CrudPermissions.READ, permissions)]
                continue
            assert not isinstance(spec, dict),\
                "in viewdef %s, class %s, dict for non-list relation %s" % (
                    view_def_name, my_typename, prop_name)
            if view_name:
                ob = getattr(self, prop_name)
                if ob and ob.user_can(
                        user_id, CrudPermissions.READ, permissions):
                    val = ob.generic_json(
                        view_name, user_id, permissions, base_uri)
                    if val is not None:
                        if isinstance(spec, list):
                            result[name] = [val]
                        else:
                            result[name] = val
                else:
                    if isinstance(spec, list):
                        result[name] = []
                    else:
                        result[name] = None
            else:
                uri = None
                if len(reln._calculated_foreign_keys) == 1 \
                        and reln._calculated_foreign_keys < fkeys:
                    # shortcut, avoid fetch
                    fkey = list(reln._calculated_foreign_keys)[0]
                    ob_id = getattr(self, fkey.name)
                    if ob_id:
                        uri = reln.mapper.class_.uri_generic(
                            ob_id, base_uri)
                else:
                    ob = getattr(self, prop_name)
                    if ob:
                        uri = ob.uri(base_uri)
                if uri:
                    if isinstance(spec, list):
                        result[name] = [uri]
                    else:
                        result[name] = uri
                else:
                    if isinstance(spec, list):
                        result[name] = []
                    else:
                        result[name] = None

        if local_view.get('_default') is not False:
            for name, col in cols.items():
                if name in known:
                    continue  # already done
                as_rel = reln_of_fkeys.get(frozenset((col, )))
                if as_rel:
                    name = as_rel.key
                    if name in known:
                        continue
                    else:
                        ob_id = getattr(self, col.key)
                        if ob_id:
                            result[name] = as_rel.mapper.class_.uri_generic(
                                ob_id, base_uri)
                        else:
                            result[name] = None
                else:
                    ob = getattr(self, name)
                    if ob:
                        if type(ob) == datetime:
                            ob = ob.isoformat() + "Z"
                        result[name] = ob
                    else:
                        result[name] = None
        return result

    def locked_object_creation(
            self, object_generator, lock_table_cls=None, num_attempts=3):
        """Utility method to create objects as a side effect.
        Will use an exclusive table lock to ensure that the objects
        are created only once. Not all object creation should need this,
        but it should be used when many connexions might attempt to create
        the same unique objects.

        :param func object_generator: a function (w/o parameters) that will
            create the objects that need to be created (as iterable).
            They will be added and committed in a subtransaction.
            Will be called many times.
        :returns: Whether there was anything added (maybe not in this process)
        """
        lock_table_cls = lock_table_cls or self.__class__
        lock_table_name = lock_table_cls.__mapper__.local_table.name
        to_be_created = object_generator()
        if to_be_created:
            for ob in to_be_created:
                if inspect(ob).pending:
                    self.db.expunge(ob)
        else:
            return False
        # Do this on another thread to minimize lock time.
        operation = TableLockCreationThread(
            object_generator, lock_table_name, num_attempts)
        operation.start()
        operation.join()
        if operation.success is False:
            raise operation.exception
        return operation.created

    def _create_subobject_from_json(
            self, json, target_cls, parse_def,
            context, accessor_name, object_importer):
        instance = None
        target_type = json.get('@type', None)
        if target_type:
            new_target_cls = get_named_class(target_type)
            if new_target_cls:
                if target_cls is not None and \
                        not issubclass(new_target_cls, target_cls):
                    raise HTTPBadRequest(
                        "Type %s was assigned to %s.%s" % (
                            target_type, self.__class__.__name__,
                            accessor_name))
                target_cls = new_target_cls
        if not target_cls:
            # Not an instance
            return None
        target_id = json.get('@id', None)
        if target_id is not None and isinstance(target_id, string_types):
            instance = object_importer.get_object(target_id)
        if instance is not None:
            # Interesting that it works here and not upstream
            sub_context = instance.get_instance_context(context)
            log.info("Chaining context from %s -> %s" % (context, sub_context))
            # NOTE: Here we could tombstone the instance if tombstonable.
            instance = instance._do_update_from_json(
                json, parse_def, sub_context,
                DuplicateHandling.USE_ORIGINAL, object_importer)
            instance = instance.handle_duplication(
                json, parse_def, sub_context,
                DuplicateHandling.USE_ORIGINAL, object_importer)
            instance_ctx = sub_context
        else:
            instance_ctx = target_cls._do_create_from_json(
                json, parse_def, context,
                DuplicateHandling.USE_ORIGINAL, object_importer)
            if instance_ctx is None:
                raise HTTPBadRequest(
                    "Could not find or create object %s" % (
                        dumps(json),))
            if instance_ctx._instance:
                context.on_new_instance(instance_ctx._instance)
        return instance_ctx

    # If a duplicate is created, do we use the original? (Error otherwise)
    default_duplicate_handling = DuplicateHandling.ERROR

    # Cases: Create -> no duplicate. Sub-elements are created or found.
    # Update-> no duplicate. Sub-elements are created or found.
    # We need to give the parse_def (by name or by value?)
    @classmethod
    def create_from_json(
            cls, json, context=None, object_importer=None,
            parse_def_name='default_reverse', duplicate_handling=None):
        """Create an object from its JSON representation."""
        object_importer = object_importer or SimpleObjectImporter()
        parse_def = get_view_def(parse_def_name)
        context = context or cls.get_class_context()
        with cls.default_db.no_autoflush:
            # We need this to allow db.is_modified to work well
            return cls._do_create_from_json(
                json, parse_def, context, duplicate_handling, object_importer)

    @classmethod
    def _do_create_from_json(
            cls, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        user_id = context.get_user_id()
        permissions = context.get_permissions()
        duplicate_handling = \
            duplicate_handling or cls.default_duplicate_handling
        can_create = cls.user_can_cls(
            user_id, CrudPermissions.CREATE, permissions)
        if duplicate_handling == DuplicateHandling.ERROR and not can_create:
            raise HTTPUnauthorized(
                "User id <%s> cannot create a <%s> object" % (
                    user_id, cls.__name__))
        # creating an object can be a weird way to find an object by attributes
        inst = cls()
        i_context = inst.get_instance_context(context)
        result = inst._do_update_from_json(
            json, parse_def, i_context,
            duplicate_handling, object_importer)

        # Now look for missing relationships
        result.populate_from_context(context)
        result = result.handle_duplication(
            json, parse_def, context, duplicate_handling, object_importer)

        if result is inst and not can_create:
            raise HTTPUnauthorized(
                "User id <%s> cannot create a <%s> object" % (
                    user_id, cls.__name__))
        elif result is not inst and \
            not result.user_can(
                user_id, CrudPermissions.UPDATE, permissions
                ) and cls.default_db.is_modified(result, False):
            raise HTTPUnauthorized(
                "User id <%s> cannot modify a <%s> object" % (
                    user_id, cls.__name__))
        if result is not inst:
            i_context = result.get_instance_context(context)
            cls.default_db.add(result)
        if '@id' in json and json['@id'] != result.uri():
            object_importer[json['@id']] = result
        return i_context

    def update_from_json(
            self, json, user_id=None, context=None, object_importer=None,
            permissions=None, parse_def_name='default_reverse'):
        """Update (patch) an object from its JSON representation."""
        object_importer = object_importer or SimpleObjectImporter()
        parse_def = get_view_def(parse_def_name)
        context = context or self.get_instance_context()
        user_id = context.get_user_id()
        from assembl.models import DiscussionBoundBase, Discussion
        discussion = context.get_instance_of_class(Discussion)
        if not discussion and isinstance(self, DiscussionBoundBase):
            discussion = Discussion.get(self.get_discussion_id())
        if permissions is None:
            permissions = context.get_permissions()
        if not self.user_can(
                user_id, CrudPermissions.UPDATE, permissions):
            raise HTTPUnauthorized(
                "User id <%s> cannot modify a <%s> object" % (
                    user_id, self.__class__.__name__))
        with self.db.no_autoflush:
            # We need this to allow db.is_modified to work well
            self._do_update_from_json(
                json, parse_def, context, None, object_importer)
            return self.handle_duplication(
                json, parse_def, context, None, object_importer)


    def _assign_subobject(self, instance, accessor):
        if isinstance(accessor, RelationshipProperty):
            # Let it throw an exception if reln not nullable?
            # Or would that come too late?
            setattr(self, accessor.key, instance)
            # Note: also set the column, because that's what is used
            # to compute the output json.
            local_columns = accessor.local_columns
            # filter out Datetime field
            if len(local_columns) > 1:
                local_columns = [c for c in local_columns if c.foreign_keys]
            if len(local_columns) == 1:
                for col in local_columns:
                    setattr(self, col.name, instance.id)
            else:
                raise RuntimeError("Multiple column relationship not handled yet")
        elif isinstance(accessor, property):
            accessor.fset(self, instance)
        elif isinstance(accessor, Column):
            # Seems not to happen in practice
            if instance is None:
                if not accessor.nullable:
                    raise HTTPBadRequest(
                        "%s is not nullable" % (accessor.key,))
            else:
                fk = next(iter(accessor.foreign_keys))
                instance_key = getattr(instance, fk.column.key)
                if instance_key is not None:
                    setattr(self, accessor.key, instance_key)
                else:
                    # Maybe delay and flush after identity check?
                    raise NotImplementedError()
        elif isinstance(accessor,
                (AssociationProxy, ObjectAssociationProxyInstance)):
            # only for lists, I think
            assert False, "we should not get here"
        else:
            assert False, "we should not get here"

    def _do_update_from_json(
            self, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        from .history_mixin import TombstonableMixin
        is_creating = self.id is None
        # Note: maybe pass as argument, and distinguish case of recasting
        # Special case of recasts
        typename = json.get("@type", None)
        if typename and typename != self.external_typename() and \
                typename in self.retypeable_as:
            # MORE security checks?
            new_cls = get_named_class(typename)
            assert new_cls
            recast = self.change_class(new_cls, json)
            recast = recast._do_update_from_json(
                json, parse_def, context,
                duplicate_handling, object_importer)
            recast.populate_from_context(context)
            return recast.handle_duplication(
                json, parse_def, context, duplicate_handling, object_importer)

        # populate_locally (incl. links to existing objects)
        #  identifying future sub-objects
        subobject_changes = self._do_local_update_from_json(
            json, parse_def, context,
            duplicate_handling, object_importer)
        if is_creating:
            self.populate_from_context(context)
        # handle duplicates
        dup = self.handle_duplication(
            json, parse_def, context, duplicate_handling, object_importer)
        if dup is not self:
            return dup
        side_effects = {}
        if is_creating:
            # populate context with new object
            context.on_new_instance(self)
            # [C] apply side-effects (sub-object creation)
            for sub_i_ctx in context.__parent__.creation_side_effects(context):
                sub_collection_name = sub_i_ctx.__parent__.__name__
                sub_instance = sub_i_ctx._instance
                side_effects[sub_collection_name] = sub_instance
                # Can I assume that the objects created as side effects are already
                # bound to their parent?
                collection = sub_i_ctx.__parent__.collection
                parent_instance = sub_i_ctx.__parent__.parent_instance
                attr = collection.get_attribute(parent_instance)
                if isinstance(attr, list):
                    if sub_instance not in attr:
                        collection.on_new_instance(self, sub_instance)
                elif attr != sub_instance:
                    collection.on_new_instance(self, sub_instance)
                self.db.add(sub_instance)

        #
        # update existing sub-objects (may reassign)
        for (accessor_name, (
                value, accessor, target_cls, s_parse_def, c_context)
             ) in subobject_changes.items():
                if isinstance(value, list):
                    from_context = side_effects.get(accessor_name, None)
                    if from_context:
                        assert len(value) == 1, "conflict between side effects and sub-objects"
                        value = value[0]
                        assert isinstance(value, dict), "this should be an object description"
                        val_id = value.get('@id', None)
                        assert not val_id, "sub-object is a reference, conflicts with side-effect"
                        i_context = from_context.get_instance_context(c_context)
                        from_context2 = from_context._do_update_from_json(
                            value, s_parse_def, i_context,
                            duplicate_handling, object_importer)
                        if from_context is not from_context2:
                            # TODO: remove old object, add new one, but maybe other objects are ok...
                            raise NotImplementedError()
                        continue
                    values = value
                    instances = []
                    current_instances = []
                    if isinstance(accessor, property):
                        current_instances = property.fget(self)
                        return
                    elif isinstance(accessor, Column):
                        raise HTTPBadRequest(
                            "%s cannot have multiple values" % (accessor.key, ))
                    elif isinstance(accessor, RelationshipProperty):
                        if accessor.back_populates:
                            current_instances = getattr(self, accessor.key)
                    elif isinstance(accessor,
                            (AssociationProxy, ObjectAssociationProxyInstance)):
                        current_instances = accessor.__get__(self, self.__class__)
                    current_instances = set(current_instances)
                    remaining_instances = set(current_instances)
                    for value in values:
                        val_id = None
                        existing = None
                        if isinstance(value, string_types):
                            val_id = value
                        elif isinstance(value, dict):
                            val_id = value.get('@id', None)
                            if val_id:
                                if val_id in object_importer:
                                    # import pdb
                                    # pdb.set_trace()
                                    log.error("this reference was present in two objects: "+val_id)
                                    existing = object_importer[val_id]
                        else:
                            raise NotImplementedError()
                        if val_id and not existing:
                            existing = get_named_object(val_id)
                        if existing and inspect(existing).persistent:
                            # existing object, so we did not go through delayed creation
                            sub_i_ctx = existing.get_instance_context(c_context)
                            existing2 = existing._do_update_from_json(
                                value, s_parse_def, sub_i_ctx,
                                duplicate_handling, object_importer)
                            if existing is not existing2:
                                # delete existing? Or will that be implicit?
                                existing = existing2
                            remaining_instances.discard(existing)
                        elif val_id:
                            def process(instance, accessor_name):
                                done = False
                                rel = self.__class__.__mapper__.relationships.get(accessor_name, None)
                                if rel:
                                    back_properties = list(getattr(rel, '_reverse_property', ()))
                                    if back_properties:
                                        back_rel = next(iter(back_properties))
                                        setattr(instance, back_rel.key, self)
                                        done = True
                                if not done:
                                    # maybe it's an association proxy?
                                    getattr(self, accessor_name).append(instance)
                                if inspect(instance).persistent and isinstance(value, dict):
                                    # existing object, so we did not go through delayed creation
                                    sub_i_ctx = instance.get_instance_context(c_context)
                                    instance2 = instance._do_update_from_json(
                                        value, s_parse_def, sub_i_ctx,
                                        duplicate_handling, object_importer)
                                    if instance is not instance2:
                                        # delete instance? Or will that be implicit?
                                        instance = instance2
                            object_importer.apply(self, val_id, partial(process, accessor_name=accessor_name))
                        elif isinstance(value, dict):
                            # just create the subobject
                            instance_ctx = self._create_subobject_from_json(
                                value, target_cls, parse_def,
                                c_context, accessor_name, object_importer)
                            if not instance_ctx:
                                raise HTTPBadRequest("Could not create " + dumps(value))
                            instance = instance_ctx._instance
                            assert instance is not None
                            best_match = instance.find_best_sibling(self, remaining_instances)
                            if best_match:
                                self.db.expunge(instance)
                                sub_i_ctx = best_match.get_instance_context(c_context)
                                existing = best_match._do_update_from_json(
                                    value, s_parse_def, sub_i_ctx,
                                    duplicate_handling, object_importer)
                                remaining_instances.remove(existing)
                            else:
                                # create sub_i_ctx?
                                instance = instance.handle_duplication(
                                    value, parse_def, context, duplicate_handling,
                                    object_importer)
                                instances.append(instance)
                        else:
                            assert False, "We should not get here"
                    # self._assign_subobject_list(
                    #     instances, accessor, context.get_user_id(),
                    #     context.get_permissions())
                    if instances and isinstance(accessor,
                            (AssociationProxy, ObjectAssociationProxyInstance)):
                        for instance in instances:
                            accessor.add(instance)
                    if remaining_instances:
                        if isinstance(accessor, RelationshipProperty):
                            remote_columns = list(accessor.remote_side)
                            if len(accessor.remote_side) > 1:
                                if issubclass(accessor.mapper.class_, TombstonableMixin):
                                    remote_columns = list(filter(lambda c: c.name != 'tombstone_date', remote_columns))
                            assert len(remote_columns) == 1
                            remote = remote_columns[0]
                            if remote.nullable:
                                # TODO: check update permissions on that object.
                                for inst in remaining_instances:
                                    setattr(inst, remote.key, None)
                            else:
                                for inst in remaining_instances:
                                    if inspect(inst).pending:
                                        self.db.expunge(inst)
                                    elif not inst.user_can(
                                            context.get_user_id(), CrudPermissions.DELETE,
                                            context.get_permissions()):
                                        raise HTTPUnauthorized(
                                            "Cannot delete object %s", inst.uri())
                                    else:
                                        if isinstance(inst, TombstonableMixin):
                                            inst.is_tombstone = True
                                        else:
                                            self.db.delete(inst)
                        elif isinstance(accessor,
                                (AssociationProxy, ObjectAssociationProxyInstance)):
                            for instance in remaining_instances:
                                accessor.delete(instance)

                elif isinstance(accessor, property):
                    # instance would have been treated above,
                    # this is a json thingy.
                    # Unless it's a real list? How to know?
                    self._assign_subobject(value, accessor)
                elif isinstance(value, dict):
                    val_id = value.get('@id', None)
                    from_context = side_effects.get(accessor_name, None)
                    existing = from_context or getattr(self, accessor_name, None)
                    if not existing and val_id:
                        existing = object_importer.get_object(val_id)
                        if existing:
                            # import pdb
                            # pdb.set_trace()
                            log.error("this reference was present in two objects: "+val_id)
                    if existing:
                        assert isinstance(existing, Base)
                        if (val_id and val_id.startswith('local:') and
                                existing.id and existing.uri() != val_id and
                                existing != object_importer.get_object(val_id)):
                            # import pdb
                            # pdb.set_trace()
                            assert False, "conflict for %s: we have %s\nreplacing with %s" % (
                                accessor_name, existing.uri(), val_id)
                        # object exists, or was just created as side-effect, update it.
                        sub_i_ctx = existing.get_instance_context(c_context)
                        existing2 = existing._do_update_from_json(
                                value, s_parse_def, sub_i_ctx,
                                duplicate_handling, object_importer)
                        if existing is not existing2:
                            existing = existing2
                            self._assign_subobject(existing, accessor)
                            self.db.add(existing)
                        if val_id:
                            object_importer[val_id] = existing
                    else:
                        # just create the subobject
                        instance_ctx = self._create_subobject_from_json(
                            value, target_cls, parse_def,
                            c_context, accessor_name, object_importer)
                        if not instance_ctx:
                            raise HTTPBadRequest("Could not create " + dumps(value))
                        if instance_ctx._instance is not None:
                            instance = instance_ctx._instance
                            if instance is not None:
                                # create sub_i_ctx?
                                instance = instance.handle_duplication(
                                    value, parse_def, context, duplicate_handling,
                                    object_importer)
                                self._assign_subobject(instance, accessor)
                                if val_id:
                                    object_importer[val_id] = instance
                else:
                    # should not get here
                    import pdb
                    pdb.set_trace()

        if not object_importer.fulfilled(self):
            log.error("not fulfilled: "+str(self))
            # import pdb
            # pdb.set_trace()
        return self.handle_duplication(
            json, parse_def, context, duplicate_handling, object_importer)

    def apply_side_effects_without_json(self, context=None, request=None):
        """Apply side-effects in non-json context"""
        if context is None:
            context = self.get_instance_context(request=request)
        for sub_i_ctx in context.__parent__.creation_side_effects(context):
            sub_instance = sub_i_ctx._instance
            # Can I assume that the objects created as side effects are already
            # bound to their parent?
            collection = sub_i_ctx.__parent__.collection
            parent_instance = sub_i_ctx.__parent__.parent_instance
            attr = collection.get_attribute(parent_instance)
            if (
                (isinstance(attr, list) and sub_instance not in attr) or
                (not isinstance(attr, list) and attr != sub_instance)
            ):
                collection.on_new_instance(self, sub_instance)
            self.db.add(sub_instance)

    def find_best_sibling(self, parent, siblings):
        # self is a non-persistent object created from json,
        # and a corresponding persistent object may already exist in parent
        # define when list-to-list assignment is likely
        console.warn("find_best_sibling on class "+self.__class__.__name__)
        return None

    # TODO: Add security by attribute?
    # Some attributes may be settable only on create.
    def _do_local_update_from_json(
            self, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        user_id = context.get_user_id()

        local_view = self.expand_view_def(parse_def)
        # False means it's illegal to get this.
        assert local_view is not False
        # None means no specific instructions.
        local_view = local_view or {}
        mapper = inspect(self.__class__)
        subobject_changes = {}
        # Also: Pre-visit the json to associate @ids to dicts
        # because the object may not be ready in the object_importer yet
        for key, value in json.items():
            if key in local_view:
                parse_instruction = local_view[key]
            else:
                parse_instruction = local_view.get('_default', False)
            if parse_instruction is False:
                # Ignore
                continue
            elif parse_instruction is True:
                pass
            elif isinstance(parse_instruction, list):
                # List specification is redundant in parse_defs.
                # These cases should always be handled as relations.
                raise NotImplementedError()
            elif parse_instruction[0] == '&':
                setter = getattr(
                    self.__class__, parse_instruction[1:], None)
                if not setter:
                    raise HTTPBadRequest("No setter %s in class %s" % (
                        parse_instruction[1:], self.__class__.__name__))
                if pyinspect.isdatadescriptor(setter):
                    setter = setter.fset
                    if not setter:
                        raise HTTPBadRequest("No setter %s in class %s" % (
                            parse_instruction[1:], self.__class__.__name__))
                elif not (pyinspect.ismethod(setter) or pyinspect.isfunction(setter)):
                    raise HTTPBadRequest("Not a setter: %s in class %s" % (
                        parse_instruction[1:], self.__class__.__name__))
                num_params = len([
                    p for p in pyinspect.signature(setter).parameters.values()
                    if p.default == pyinspect._empty])
                if num_params != 2:
                    raise HTTPBadRequest(
                        "Wrong number of args: %s(%d) in class %s" % (
                            parse_instruction[1:], num_params,
                            self.__class__.__name__))
                setter(self, value)
                continue
            elif parse_instruction[0] == "'":
                if value != parse_instruction[1:]:
                    raise HTTPBadRequest("%s should be %s'" % (
                        key, parse_instruction))
            else:
                key = parse_instruction
            accessor = None
            accessor_name = key
            target_cls = None
            can_be_list = False
            must_be_list = False
            instance = None
            instances = []
            # First treat scalars
            if key in mapper.c:
                col = mapper.c[key]
                if value is None:
                    if not col.nullable:
                        raise HTTPBadRequest(
                            "%s is not nullable" % (key,))
                    setattr(self, key, value)
                    continue
                if not col.foreign_keys:
                    if isinstance(value, string_types):
                        target_type = col.type.__class__
                        if target_type == DateTime:
                            setattr(self, key, parse_datetime(value, True))
                        elif isinstance(col.type, DeclEnumType):
                            setattr(self, key, col.type.enum.from_string(value))
                        elif col.type.python_type is past_unicode \
                                and isinstance(value, past_str):  # python2
                            setattr(self, key, value.decode('utf-8'))
                        elif col.type.python_type is past_str \
                                and isinstance(value, past_unicode):  # python2
                            setattr(self, key, value.encode('ascii'))  # or utf-8?
                        elif col.type.python_type is bool \
                                and value.lower() in ("true", "false"):
                            # common error... tolerate.
                            setattr(self, key, value.lower() == "true")
                        elif issubclass(col.type.python_type, string_types):
                            setattr(self, key, value)
                        elif issubclass(col.type.python_type, float):
                            setattr(self, key, float(value))
                        elif issubclass(col.type.python_type, int):
                            setattr(self, key, int(value))
                        else:
                            assert False, "can't assign json type %s"\
                                " to column %s of class %s" % (
                                    type(value).__name__, col.key,
                                    self.__class__.__name__)
                    elif isinstance(value, col.type.python_type):
                        setattr(self, key, value)
                    elif isinstance(value, int) and col.type.python_type == float:
                        # upcast
                        setattr(self, key, float(value))
                    else:
                        assert False, "can't assign json type %s"\
                            " to column %s of class %s" % (
                                type(value).__name__, col.key,
                                self.__class__.__name__)
                    continue
                else:
                    # Non-scalar
                    # TODO: Keys spanning multiple columns
                    fk = next(iter(col.foreign_keys))
                    orm_relns = [
                        r for r in mapper.relationships
                        if col in r.local_columns and r.secondary is None]
                    assert(len(orm_relns) <= 1)
                    if orm_relns:
                        accessor = next(iter(orm_relns))
                        accessor_name = accessor.key
                        target_cls = accessor.mapper.class_
                    else:
                        accessor = col
                        # Costly. TODO: Optimize.
                        target_cls = get_target_class(col)
            elif key in mapper.relationships:
                accessor = mapper.relationships[key]
                target_cls = accessor.mapper.class_
                if accessor.direction == MANYTOMANY:
                    raise NotImplementedError()
                elif accessor.direction == ONETOMANY and accessor.uselist:
                    can_be_list = must_be_list = True
            elif getattr(self.__class__, key, None) is not None and\
                    isinstance(getattr(self.__class__, key), property) and\
                    getattr(getattr(
                        self.__class__, key), 'fset', None) is None:
                raise HTTPBadRequest(
                    "No setter for property %s of type %s" % (
                        key, json.get('@type', '?')))
            elif getattr(self.__class__, key, None) is not None and\
                    isinstance(getattr(self.__class__, key), property):
                accessor = getattr(self.__class__, key)
                can_be_list = True
            elif getattr(self.__class__, key, None) is not None\
                    and isinstance(getattr(self.__class__, key),
                        (AssociationProxy, ObjectAssociationProxyInstance)):
                accessor = getattr(self.__class__, key)
                # Target_cls?
                can_be_list = must_be_list = True
            elif not value:
                log.info("Ignoring unknown empty value for "\
                    "attribute %s in json id %s (type %s)" % (
                        key, json.get('@id', '?'), json.get('@type', '?')))
                continue
            else:
                raise HTTPBadRequest(
                    "Unknown attribute %s in json id %s (type %s)" % (
                        key, json.get('@id', '?'), json.get('@type', '?')))

            # We have an accessor, let's treat the value.
            # Build a context
            c_context = self.get_collection_context(key, context) or context
            log.debug("Chaining context from %s to %s" % (context, c_context))
            if c_context is context:
                log.info("Could not find collection context: %s %s" % (self, key))
            if isinstance(value, string_types):
                assert not must_be_list
                target_id = value
                if target_cls is not None:
                    # TODO: Keys spanning multiple columns
                    object_importer.apply(
                        self, target_id,
                        partial(
                            lambda i, a: self._assign_subobject(i, a),
                            a=accessor))
                    continue
                else:
                    # Possibly just a string
                    instance = target_id
            elif isinstance(value, dict):
                assert not must_be_list
                subobject_changes[accessor_name] = (
                    value, accessor, target_cls, parse_def, c_context)
                continue
            elif isinstance(value, list):
                assert can_be_list
                subobject_changes[accessor_name] = (
                    value, accessor, target_cls, parse_def, c_context)
                continue
            elif isinstance(accessor, property):
                # Property can be any target type.
                # Hence we do not handle well the case of simple
                # string or dict properties
                setattr(self, accessor_name, value)
                continue
            elif value is None:
                # We used to not clear. That was silly, but doing it may
                # be dangerous.
                setattr(self, accessor_name, None)
                # Note: also null the column, because that's what is used
                # to compute the output json.
                for col in accessor.local_columns:
                    # check because otherwise it's spuriously set as modified
                    if getattr(self, col.name, None):
                        setattr(self, col.name, None)
                continue
            else:
                assert False, "can't assign json type %s"\
                    " to relationship %s of class %s" % (
                        type(value).__name__, accessor_name,
                        self.__class__.__name__)

            # Now we have an instance and an accessor, let's assign.
            # Case of list taken care of.
            self._assign_subobject(instance, accessor)

        return subobject_changes

    def populate_from_context(self, context):
        """If object created in this context, populate some relations from that context.

        This is the magic fallback, ideally define the relationships you want populated
        explicitly in subclasses of this."""
        relations = self.__class__.__mapper__.relationships
        non_nullables = []
        nullables = []
        related_objects = set()
        for reln in relations:
            if reln.direction in (ONETOMANY, MANYTOMANY):
                continue
            if reln.viewonly:
                continue
            obj = getattr(self, reln.key, None)
            if obj is not None:
                # This was already set, assume it was set correctly
                related_objects.add(obj)
                continue
            # Do not decorate nullable relations
            nullable_keys = [
                local for (local, remote) in reln.local_remote_pairs
                if local.foreign_keys and local.nullable]
            if nullable_keys:
                nullables.append(reln)
            else:
                non_nullables.append(reln)
        for reln in non_nullables:
            inst = context.get_instance_of_class(reln.mapper.class_)
            if inst:
                if inst in related_objects:
                    # no need to duplicate
                    log.debug("populate_from_context magic on %s.%s: duplicate" % (
                        self.__class__.__name__, reln.key))
                    continue
                log.debug("populate_from_context magic on %s.%s" % (
                    self.__class__.__name__, reln.key))
                setattr(self, reln.key, inst)
                related_objects.add(inst)
        # if an object in the context is not related,
        # and there is an appropriate nullable column, we might want
        # to add it. Let's record for now.
        if nullables:
            for instance in context.get_all_instances():
                if instance in related_objects:
                    continue
                candidates = [r.key for r in nullables if issubclass(
                    instance.__class__, r.mapper.class_)]
                for rname in candidates:
                    log.debug("populate_from_context magic: could populate nullable %s.%s with %s" % (
                        self.__class__.__name__, rname, instance))

    def creation_side_effects(self, context):
        return ()

    def handle_duplication(
                self, json={}, parse_def={}, context=None,
                duplicate_handling=None, object_importer=None):
        """Look for duplicates of this object.

        Some uniqueness is handled in the database, but it is difficult to do
        across tables. Often we will use the classe's unique_query to find an
        duplicate, and react appropriately here. Appropriateness depends on
        the classe's `default_duplicate_handling`, which can be overridden."""
        from .history_mixin import TombstonableMixin, HistoryMixin
        if duplicate_handling is None:
            duplicate_handling = self.default_duplicate_handling
        if duplicate_handling == DuplicateHandling.NO_CHECK:
            return
        # Issue: unique_query MAY trigger a flush, which will
        # trigger an error if columns are missing, including in a call above.
        # But without the flush, some relations will not be interpreted
        # correctly. Strive to avoid the flush in most cases.
        unique_query, usable = self.unique_query()
        if usable:
            others = unique_query.all()
            if self in others:
                others.remove(self)
            if others:
                if duplicate_handling == DuplicateHandling.TOMBSTONE:
                    for other in others:
                        assert isinstance(other, TombstonableMixin)
                        other.is_tombstone = True
                elif duplicate_handling == DuplicateHandling.TOMBSTONE_AND_COPY:
                    for other in others:
                        assert isinstance(other, HistoryMixin)
                        other.is_tombstone = True
                    self.base_id = others[0].base_id
                elif duplicate_handling in (
                        DuplicateHandling.USE_ORIGINAL,
                        DuplicateHandling.ERROR):
                    other = others[0]
                    if inspect(self).pending:
                        other.db.expunge(self)
                    if duplicate_handling == DuplicateHandling.ERROR:
                        raise ObjectNotUniqueError(
                            "Duplicate of <%s> created" % (other.uri()))
                    # TODO: Check if there's a risk of infinite recursion here?
                    if json is None:
                        # TODO: Use the logic in api2.instance_put_form
                        raise NotImplementedError()
                    # TODO: check the CrudPermissions on subobject,
                    # UNLESS it's they're inherited (eg Langstring)
                    other = other._do_update_from_json(
                        json, parse_def, context,
                        duplicate_handling, object_importer)
                    return other.handle_duplication(
                        json, parse_def, context,
                        duplicate_handling, object_importer)
                else:
                    raise ValueError("Invalid value of duplicate_handling")
        return self

    def unique_query(self):
        """returns a couple (query, usable), with a sqla query for conflicting similar objects.
        usable is true if the query has to be enforced; sometimes it makes sense to
        return un-usable query that will be used to construct queries of subclasses.
        Note that when a duplicate is found, you'll often want to expunge the original.
        """
        # To be reimplemented in subclasses with a more intelligent check.
        # See notification for example.
        return self.db.query(self.__class__), False

    def find_duplicate(self, expunge=True, must_define_uniqueness=False):
        """Verifies that no other object exists that would conflict.
        See unique_query for usable flag."""
        query, usable = self.unique_query()
        if must_define_uniqueness:
            assert usable, "Class %s needs a valid unique_query" % (
                self.__class__.__name__)
        if not usable:
            # This used to be True, meaning uniqueness test "succeeded".
            # But most invocations have a usable query, or force
            # must_define_uniqueness, so this case never actually arises,
            # and many downstream usage tests for None in a way that would.
            # fail with True. TODO: Cleanup must_define_uniqueness
            return None
        with self.db.no_autoflush:
            for other in query:
                if other is self:
                    continue
                if expunge and inspect(self).pending:
                    other.db.expunge(self)
                return other

    def get_unique_from_db(self, expunge=True):
        """Returns the object, or a unique object from the DB"""
        return self.find_duplicate(expunge, True) or self

    def assert_unique(self):
        """Assert this object is unique"""
        duplicate = self.find_duplicate()
        if duplicate is not None:
            raise ObjectNotUniqueError("Duplicate of <%s> created" % (duplicate.uri()))

    @classmethod
    def extra_collections_dict(cls):
        """Returns a dictionary of (named) collections of objects related to an instance of this class

        Many collections can be obtained by introspection on
        SQLAlchemy relationships, but collections here go beyond this."""
        extra_collections = []
        for cls in reversed(cls.mro()):
            if not issubclass(cls, Base):
                continue
            if '_extra_collections_cache' not in cls.__dict__:
                if 'extra_collections' in cls.__dict__:
                    cls._extra_collections_cache = cls.extra_collections()
                else:
                    cls._extra_collections_cache = ()
            extra_collections.extend(cls._extra_collections_cache)
        return {coll.name: coll for coll in extra_collections}

    @classmethod
    def get_collections(cls):
        if '_collections_cache' not in cls.__dict__:
            from assembl.views.traversal import RelationCollectionDefinition
            collections = cls.extra_collections_dict()
            relations = cls.__mapper__.relationships
            for rel in relations:
                if rel.key not in collections:
                    collections[rel.key] = RelationCollectionDefinition(
                        cls, rel)
            cls._collections_cache = collections
        return cls._collections_cache

    @staticmethod
    def get_api_context(request=None, user_id=None):
        from assembl.views.traversal import app_root_factory
        from pyramid.threadlocal import get_current_request
        request = request or get_current_request()
        root = app_root_factory(request, user_id)
        return root['data']

    @classmethod
    def get_class_context(cls, request=None, user_id=None):
        api_context = cls.get_api_context(request, user_id)
        return api_context[cls.external_typename()]

    def get_default_parent_context(self, request=None, user_id=None):
        return self.get_class_context(request, user_id)

    def get_instance_context(self, parent_context=None, request=None, user_id=None):
        from assembl.views.traversal import InstanceContext
        return InstanceContext(
            parent_context or self.get_default_parent_context(
                request, user_id), self)

    def get_collection_context(
            self, relation_name, parent_context=None, request=None, user_id=None):
        from assembl.views.traversal import CollectionContext
        collection = self.get_collections().get(relation_name, None)
        if collection:
            parent_context = parent_context or self.get_instance_context(
                request=request, user_id=user_id)
            return CollectionContext(parent_context, collection, self)

    def is_owner(self, user_id):
        """The user owns this ressource, and has more permissions."""
        return False

    def principals_with_read_permission(self):
        permissions = self.crud_permissions
        if permissions.read == P_READ:
            return None  # i.e. everyone
        # make this into a protocol!
        creator_id = getattr(self, 'creator_id', None)
        if creator_id:
            from ..models import User
            return [User.uri_generic(creator_id)]
        return []

    @classmethod
    def restrict_to_owners(cls, query, user_id, alias=None):
        """filter query according to object owners"""
        (query, condition) = cls.restrict_to_owners_condition(query, user_id, alias)
        if condition is not None:
            query = query.filter(condition)
        return query

    @classmethod
    def restrict_to_owners_condition(cls, query, user_id, alias=None, alias_maker=None):
        """filter query according to object owners"""
        return (query, None)


    @classmethod
    def pubflowid_from_discussion(cls, discussion):
        return None

    @classmethod
    def local_role_class_and_fkey(cls):
        return (None, None)

    @classmethod
    def query_filter_with_permission(
            cls, discussion, user_id, permission=P_READ,
            query=None, base_permissions=None, roles=None, clsAlias=None,
            owner_permission=None):
        from ..models.permissions import Role, Permission, DiscussionPermission
        from ..models.publication_states import PublicationState, StateDiscussionPermission
        # here are all the ways you can have a permission:
        # 1. (global or Local)UserRole + DiscussionPermission (common)
        # 2. (global or Local)UserRole+State+StateDiscussionPermission (factorable)
        # 3. ownership + DiscussionPermission
        # 4. ownership + State + StateDiscussionPermission
        # 5. LocalUserRole + DiscussionPermission (factorable)
        # 6. LocalUserRole + State + StateDiscussionPermission
        if not discussion:
            # TODO
            return query
        db = discussion.db
        assert permission, "Please specify a permission"
        clsAlias = clsAlias or cls
        owner_permission = owner_permission or permission
        owner_permissions = list({permission, owner_permission})
        pubflow_id = cls.pubflowid_from_discussion(discussion)
        # TODO: Add ownership!

        query = query or db.query(clsAlias)
        base_permissions = base_permissions or ()
        if permission in base_permissions or P_SYSADMIN in base_permissions: # 1 shortcut
            return query
        roles_with_d_permission_q = db.query(Role.id).join(
            DiscussionPermission).join(Permission).filter(
                (Permission.name == permission) &
                (DiscussionPermission.discussion == discussion)
            ).subquery()
        local_role_class, lrc_fk = cls.local_role_class_and_fkey()
        (query, ownership_condition) = cls.restrict_to_owners_condition(query, user_id, clsAlias)
        conditions = []
        if ownership_condition is not None:  # 3
            owner_has_permission = db.query(DiscussionPermission
                ).filter_by(discussion_id=discussion.id
                ).join(Role).filter_by(name=R_OWNER
                ).join(Permission).filter_by(name=owner_permission).limit(1).count()
            if owner_has_permission:
                conditions.append(ownership_condition)
        if local_role_class:    # 5
            ilur_dp = aliased(local_role_class)

            query = query.outerjoin(
                    ilur_dp,
                    (getattr(ilur_dp, lrc_fk)==clsAlias.id) &
                    (ilur_dp.profile_id==user_id) &
                    ilur_dp.role_id.in_(roles_with_d_permission_q)
                )
            conditions.append(ilur_dp.id != None)

        if pubflow_id:
            # TODO: Could this be simplified with a view?
            states_with_permission_q = db.query(PublicationState.id  # 2
                ).filter(PublicationState.flow_id == pubflow_id
                ).join(StateDiscussionPermission,
                    (StateDiscussionPermission.pub_state_id==PublicationState.id) &
                    (StateDiscussionPermission.discussion_id==discussion.id)
                ).join(Role,
                    (StateDiscussionPermission.role_id == Role.id) &
                    Role.name.in_(roles)
                ).join(Permission,
                    (StateDiscussionPermission.permission_id==Permission.id) &
                    (Permission.name == permission))
            conditions.append(clsAlias.pub_state_id.in_(states_with_permission_q))
            if ownership_condition is not None:  # 4
                states_with_owner_permission_q = db.query(PublicationState.id
                    ).filter(PublicationState.flow_id == pubflow_id
                    ).join(StateDiscussionPermission,
                        (StateDiscussionPermission.pub_state_id==PublicationState.id) &
                        (StateDiscussionPermission.discussion_id==discussion.id)
                    ).join(Permission,
                        (StateDiscussionPermission.permission_id==Permission.id) &
                        Permission.name.in_(owner_permissions)
                    ).join(Role,
                        (StateDiscussionPermission.role_id==Role.id) &
                        (Role.name == R_OWNER))
                conditions.append(ownership_condition & clsAlias.pub_state_id.in_(states_with_owner_permission_q))

            if local_role_class:  # 6
                ilur_ip = aliased(local_role_class)
                sdp_ilocal = aliased(StateDiscussionPermission)
                permissionO = Permission.getByName(permission)  # avoid an outerjoin

                query = query.outerjoin(
                        ilur_ip,
                        (getattr(ilur_ip, lrc_fk)==clsAlias.id) &
                        (ilur_ip.profile_id==user_id)
                    ).outerjoin(
                        sdp_ilocal,
                        (sdp_ilocal.role_id==ilur_ip.role_id) &
                        (sdp_ilocal.pub_state_id==clsAlias.pub_state_id) &
                        (sdp_ilocal.permission_id==permissionO.id)
                    )
                conditions.append((ilur_ip.id != None) & (sdp_ilocal.id != None))
        if conditions:
            query = query.filter(or_(*conditions))
        return query

    @classmethod
    def query_filter_with_permission_req(
            cls, request, permission=P_READ, query=None, clsAlias=None):
        return cls.query_filter_with_permission(
            request.discussion, request.authenticated_userid, permission,
            query, request.base_permissions, request.roles, clsAlias)

    @classmethod
    def query_filter_with_crud_op_req(
            cls, request, crud_op=CrudPermissions.READ, query=None, clsAlias=None):
        (permission, owner_permission) = cls.crud_permissions.crud_permissions(crud_op)
        return cls.query_filter_with_permission(
            request.discussion, request.authenticated_userid, permission,
            query, request.base_permissions, request.roles, clsAlias, owner_permission)

    def local_roles(self, user_id):
        from ..models.permissions import Role
        roles = []
        if self.is_owner(user_id):
            roles.append(R_OWNER)
        (local_role_class, fkey) = self.local_role_class_and_fkey()
        if local_role_class:
            query = self.db.query(Role.name).join(local_role_class).filter(
                getattr(local_role_class, fkey)==self.id,
                local_role_class.profile_id==user_id)
            roles.extend((x for (x,) in query))
        return roles

    def get_role_query(self, user_id, discussion_id=None):
        from ..models.permissions import Role, LocalUserRole, UserRole
        user_id = user_id or Everyone
        session = self.db
        if user_id == Everyone:
            return session.query(Role).filter(Role.name == user_id)
        elif user_id == Authenticated:
            return session.query(Role).filter(Role.name.in_((Authenticated, Everyone)))
        base_roles = [Authenticated, Everyone]
        if user_id and self.is_owner(user_id):
            base_roles.append(R_OWNER)
        clauses = []
        roles = session.query(Role).join(UserRole).filter(
                UserRole.profile_id == user_id)
        if discussion_id:
            clauses.append(session.query(Role).join(LocalUserRole).filter(and_(
                        LocalUserRole.profile_id == user_id,
                        LocalUserRole.requested == False,
                        LocalUserRole.discussion_id == discussion_id)))
        clauses.append(session.query(Role).filter(Role.name.in_(base_roles)))
        (local_role_class, fkey) = self.local_role_class_and_fkey()
        if local_role_class:
            clauses.append(session.query(Role).join(local_role_class).filter(
                getattr(local_role_class, fkey)==self.id,
                local_role_class.profile_id==user_id))
        roles = roles.union(*clauses)
        return roles.distinct()

    def local_permissions(self, user_id, discussion=None, include_global=False):
        # here are all the ways you can have a permission:
        # 1. (global or Local)UserRole + DiscussionPermission (common, ignore here)
        # 2. (global or Local)UserRole+State+StateDiscussionPermission (factorable)
        # 3. ownership + DiscussionPermission
        # 4. ownership + State + StateDiscussionPermission
        # 5. LocalUserRole + DiscussionPermission (factorable)
        # 6. LocalUserRole + State + StateDiscussionPermission
        from ..models.permissions import DiscussionPermission, Permission, Role
        from ..models.publication_states import PublicationState, StateDiscussionPermission
        session = self.db
        if not discussion:
            return []
        roles = self.get_role_query(user_id, discussion.id
            ).with_entities(Role.id).subquery()
        queries = []
        if include_global:
            queries.append(
                session.query(Permission.name).join(
                    DiscussionPermission
                ).join(Role
                ).filter(Role.id.in_(roles)))
        elif self.is_owner(user_id):
            queries.append(
                session.query(Permission.name).join(
                    DiscussionPermission
                ).join(Role
                ).filter(Role.name == R_OWNER))
        pub_state_id = getattr(self, 'pub_state_id', None)
        if pub_state_id:
            queries.append(
                session.query(Permission.name).join(
                    StateDiscussionPermission,
                    (Permission.id==StateDiscussionPermission.permission_id) &
                    (StateDiscussionPermission.pub_state_id==pub_state_id) &
                    (StateDiscussionPermission.discussion_id==discussion.id) &
                    StateDiscussionPermission.role_id.in_(roles)
                )
            )
        if not len(queries):
            return []
        query = queries.pop(0)
        if queries:
            query = query.union(*queries)
        return [x for (x,) in query.distinct()]

    def local_permissions_req(self, request=None, include_global=False):
        # TODO: Cache in request
        from ..models import Discussion
        from pyramid.threadlocal import get_current_request
        request = request or get_current_request()
        assert request
        discussion = request.discussion
        if not discussion:
            return []
        return self.local_permissions(request.authenticated_userid, discussion, include_global)

    def has_permission_req(self, permission, request=None):
        from pyramid.threadlocal import get_current_request
        request = request or get_current_request()
        assert request
        if permission in request.base_permissions:
            return True
        if P_SYSADMIN in request.base_permissions:
            return True
        return permission in self.local_permissions_req(request)

    """The permissions to create, read, update, delete an object of this class.
    Also separate permissions for the owners to update or delete."""
    crud_permissions = CrudPermissions()

    @classmethod
    def user_can_cls(cls, user_id, operation, permissions):
        """Whether the user, with the given permissions,
        can perform the given Crud operation on instances of this class."""
        perm = cls.crud_permissions.can(operation, permissions)
        user_id = user_id or Everyone
        if perm == MAYBE and user_id == Everyone:
            return False
        return perm

    def user_can(self, user_id, operation, permissions):
        """Whether the user, with the given permissions,
        can perform the given Crud operation on this instance."""
        user_id = user_id or Everyone
        perm, owner_perm = self.crud_permissions.crud_permissions(operation)
        if perm in permissions:
            return perm
        if P_SYSADMIN in permissions:
            return True
        is_owner = self.is_owner(user_id)
        if is_owner and owner_perm in permissions:
            return owner_perm
        local_perms = self.local_permissions(user_id)
        if perm in local_perms:
            return perm
        if is_owner and owner_perm in local_perms:
            return owner_perm
        return False

    def user_can_req(self, operation, request=None):
        from pyramid.threadlocal import get_current_request
        request = request or get_current_request()
        assert request
        return self.user_can(request.authenticated_userid, operation, request.base_permissions)


class TimestampedMixin(object):
    @declared_attr
    def last_modified(cls):
        return Column(DateTime, nullable=False, default=datetime.utcnow)

    def was_changed(self):
        return self.db.is_modified(self, False)


def make_session_maker(zope_tr=True, autoflush=True):
    session = scoped_session(sessionmaker(
        autoflush=autoflush,
        class_=ReadWriteSession))
    if zope_tr:
        register(session)
    session.is_zopish = zope_tr
    return session


def initialize_session_maker(zope_tr=True, autoflush=True):
    "Initialize the application global sessionmaker object"
    global _session_maker
    assert _session_maker is None
    session_maker = make_session_maker(zope_tr, autoflush)
    if _session_maker is None:
        # The global object is the first one initialized
        _session_maker = session_maker
    return session_maker


def session_maker_is_initialized():
    global _session_maker
    return _session_maker is not None


def get_session_maker():
    "Get the application global sessionmaker object"
    global _session_maker
    assert _session_maker is not None
    return _session_maker


class PrivateObjectMixin(object):
    "marker class for objects that should be sent to owner"
    @abstractmethod
    def get_user_uri(self):
        return ""


class Tombstone(object):
    def __init__(self, ob, **kwargs):
        self.typename = ob.external_typename()
        self.uri = ob.uri()
        self.extra_args = kwargs
        privacy_info = ob.principals_with_read_permission()
        if privacy_info:
            self.extra_args['@private'] = privacy_info

    def generic_json(self, *vargs, **kwargs):
        args = {"@type": self.typename,
                "@id": self.uri,
                "@tombstone": True}
        args.update(self.extra_args)
        return args

    def send_to_changes(self, connection, operation=CrudOperation.DELETE,
                        discussion_id=None, view_def="changes"):
        assert connection
        if 'cdict' not in connection.info:
            connection.info['cdict'] = {}
        connection.info['cdict'][(self.uri, view_def)] = (
            discussion_id, self)


def orm_update_listener(mapper, connection, target):
    if getattr(target, '__history_table__', None):
        return
    session = object_session(target)
    if session.is_modified(target, include_collections=False):
        target.send_to_changes(connection, CrudOperation.UPDATE)


def orm_insert_listener(mapper, connection, target):
    if getattr(target, '__history_table__', None):
        return
    target.send_to_changes(connection, CrudOperation.CREATE)


def orm_delete_listener(mapper, connection, target):
    if 'cdict' not in connection.info:
        connection.info['cdict'] = {}
    if getattr(target, '__history_table__', None):
        return
    target.tombstone().send_to_changes(connection, CrudOperation.DELETE)


def before_flush_listener(session, flush_context, instances):
    for target in session.identity_map.values():
        if isinstance(target, TimestampedMixin) and target.was_changed():
            target.last_modified = datetime.now()


def before_commit_listener(session):
    """Create the Json representation of changed objects which will be
    sent to the :py:mod:`assembl.tasks.changes_router`

    We have to do this before commit, while objects are still attached."""
    # If there hasn't been a flush yet, make sure any sql error occur BEFORE
    # we send changes to the socket.
    session.flush()
    info = session.connection().info
    if 'cdict' in info:
        changes = defaultdict(list)
        for ((uri, view_def), (discussion, target)) in \
                info['cdict'].items():
            discussion = discussion or "*"
            json = target.generic_json(view_def)
            if json:
                changes[discussion].append(json)
        del info['cdict']
        session.cdict2 = changes
    else:
        log.debug("EMPTY CDICT!")


def after_commit_listener(session):
    """After commit, actually send the Json representation of changed objects
    to the :py:mod:`assembl.tasks.changes_router`, through 0MQ."""
    if not getattr(session, 'zsocket', None):
        session.zsocket = get_pub_socket()
    if getattr(session, 'cdict2', None):
        for discussion, changes in session.cdict2.items():
            send_changes(session.zsocket, discussion, changes)
        del session.cdict2


def session_rollback_listener(session):
    """In case of rollback, forget about object changes."""
    if getattr(session, 'cdict2', None):
        del session.cdict2


def engine_rollback_listener(connection):
    """In case of rollback, forget about object changes."""
    info = getattr(connection, 'info', None)
    if info and 'cdict' in info:
        del info['cdict']


event.listen(BaseOps, 'after_insert', orm_insert_listener, propagate=True)
event.listen(BaseOps, 'after_update', orm_update_listener, propagate=True)
event.listen(BaseOps, 'after_delete', orm_delete_listener, propagate=True)


def connection_url(settings, prefix='db_'):
    db_host = settings.get(prefix + 'host', None)
    db_user = settings.get(prefix + 'user', None)
    db_database = settings.get(prefix + 'database', None)
    rds_iam_role = settings.get(prefix + 'iam_role', None)
    if not (db_host or db_user or db_database or rds_iam_role):
        return None
    # fallback to base prefix
    db_host = db_host or settings.get('db_host')
    db_user = db_user or settings.get('db_user')
    db_database = db_database or settings.get('db_database')
    rds_iam_role = rds_iam_role or settings.get('db_iam_role')
    if rds_iam_role:
        from .rds_token_url import IamRoleRdsTokenUrl
        region = settings.get("aws_region", 'eu-west-1')
        certificate = settings.get('rds_certificate', None)
        if certificate:
            query = {'sslmode': 'verify-full', 'sslrootcert': certificate}
        else:
            query = {'sslmode': 'require'}
        return IamRoleRdsTokenUrl(
            'postgresql+psycopg2', rds_iam_role, region, db_user,
            db_host, database=db_database, query=query)
    else:
        query = {'sslmode': 'disable' if db_host == 'localhost' else 'require'}
        password = settings.get(prefix + 'password', None) or settings.get('db_password')
        return URL(
            'postgresql+psycopg2', db_user, password, db_host, 5432, db_database, query)


def configure_engine(settings, zope_tr=True, autoflush=True, session_maker=None,
                     **engine_kwargs):
    """Return an SQLAlchemy engine configured as per the provided config."""
    if session_maker is None:
        if session_maker_is_initialized():
            log.error("ERROR: Initialized twice.")
            session_maker = get_session_maker()
        else:
            session_maker = initialize_session_maker(zope_tr, autoflush)
    engine = session_maker.session_factory.kw['bind']
    if engine:
        return engine
    url = connection_url(CascadingSettings(settings))
    settings['sqlalchemy.url'] = url
    if hasattr(url, 'aws_region'):
        entrypoint = url._get_entrypoint()
        dialect_cls = entrypoint.get_dialect_cls(url)
        dbapi = dialect_cls.dbapi()
        dialect = dialect_cls(dbapi=dbapi)

        def creator(*args, **kwargs):
            return dialect.connect(
                host=url.host, user=url.username, database=url.database,
                password=url.password, port=url.port, **url.query)
        engine_kwargs['creator'] = creator

    engine = engine_from_config(settings, 'sqlalchemy.', **engine_kwargs)
    read_url = connection_url(settings, "dbro_")
    if read_url:
        settings = dict(settings)
        settings['sqlalchemy.url'] = read_url
        read_engine = engine_from_config(settings, 'sqlalchemy.', **engine_kwargs)
    else:
        read_engine = None
    session_maker.configure(bind=engine, read_bind=read_engine)
    global db_schema, _metadata, Base, class_registry
    db_schema = settings['db_schema']
    _metadata = MetaData(schema=db_schema)
    Base = declarative_base(cls=BaseOps, metadata=_metadata,
                            class_registry=class_registry)
    event.listen(Session, 'before_commit', before_commit_listener)
    event.listen(Session, 'before_flush', before_flush_listener)
    event.listen(Session, 'after_commit', after_commit_listener)
    event.listen(Session, 'after_rollback', session_rollback_listener)
    event.listen(engine, 'rollback', engine_rollback_listener)
    return engine


def mark_changed(session=None):
    session = session or get_session_maker()()
    z_mark_changed(session)


def get_metadata():
    global _metadata
    return _metadata


# TODO: Initialize this in assembl.models
legacy_typenames = {
    "Content": "SPost",
    "Idea": "GenericIdeaNode",
    "Discussion": "Conversation",
}


def get_named_class(typename):
    global aliased_class_registry
    if not aliased_class_registry:
        aliased_class_registry = {
            cls.external_typename(): cls
            for cls in class_registry.values()
            if getattr(cls, 'external_typename', None)
        }
        for k, v in legacy_typenames.items():
            aliased_class_registry[k] = aliased_class_registry[v]
    return aliased_class_registry.get(typename, None)


# In theory, the identifier should be enough... at some point.
def get_named_object(identifier, typename=None):
    "Get an object given a typename and identifier"
    if typename is None:
        typename = identifier.split(':')[-1].split('/')[-2]
    cls = get_named_class(typename)
    if cls:
        return cls.get_instance(identifier)


def get_database_id(typename, identifier):
    try:
        return int(identifier)
    except ValueError:
        cls = get_named_class(typename)
        if cls:
            return cls.get_database_id(identifier)


def includeme(config):
    """Initialize SQLAlchemy at app start-up time."""
    configure_engine(config.registry.settings)
