"""Mixin classes for keeping old versions of data structures"""
from builtins import str
from builtins import object
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Integer, UniqueConstraint, event, Table, ForeignKey,
    Sequence, Index, asc)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql.expression import join, nullslast
from sqlalchemy.orm import relationship, Query
from sqlalchemy.sql.elements import (
    BinaryExpression, BooleanClauseList, operators, True_)
from sqlalchemy.sql.visitors import ReplacingCloningVisitor
from sqlalchemy.ext.associationproxy import AssociationProxy

from .sqla import DuplicateHandling
from ..semantic.virtuoso_mapping import QuadMapPatternS
from ..semantic.namespaces import ASSEMBL
from ..semantic.namespaces import DCTERMS


class TombstonableMixin(object):
    """Mixin class for objects that can be tombstoned

    These objects can be killed, leaving a tombstone behind,
    i.e. an inactive row.
    TODO: Generate a DB view on live objects."""

    # Note on tombstone_date: Virtuoso can test for its being null, but not non-null.
    tombstone_date = Column(DateTime, server_default=None, default=None)

    @property
    def is_tombstone(self):
        return self.tombstone_date is not None

    # Most tombstonable objects cannot be resurrected.
    can_be_resurrected = False

    @is_tombstone.setter
    def is_tombstone(self, value):
        """Set the tombstone property to True. (normally irreversible)"""
        if not value:
            if self.tombstone_date is not None:
                if self.can_be_resurrected:
                    self.tombstone_date = None
                else:
                    raise ValueError("Cannot resurrect " + str(self))
            return
        if self.tombstone_date is None:
            self.tombstone_date = datetime.utcnow()

    @classmethod
    def base_conditions(cls, alias=None, alias_maker=None):
        """By default exclude tombstones"""
        return (cls.tombstone_condition(alias),)

    @classmethod
    def tombstone_condition(cls, alias=None):
        cls = alias or cls
        return cls.tombstone_date == None

    @classmethod
    def not_tombstone_condition(cls, alias=None):
        cls = alias or cls
        return cls.tombstone_date != None

    def unique_query(self):
        query, valid = super(TombstonableMixin, self).unique_query()
        if self.default_duplicate_handling == DuplicateHandling.ERROR:
            # we only care about unicity of non-tombstones
            query = query.filter_by(
                tombstone_date=None)
        return query, valid


class HistoryMixin(TombstonableMixin):
    """Mixin class for objects with history

    It is possible to take a snapshot of objects of this class
    to have a record of earlier states. The snapshot is invoked
    explicitly (through :py:meth:`copy(True)`), not every time
    the object is changed. Mainly used for synthesis snapshots.
    """

    @declared_attr
    def id_sequence_name(cls):
        return cls.__tablename__ + '_idsequence'

    @declared_attr
    def id_sequence(cls):
        return Sequence(
            cls.id_sequence_name, schema=cls.metadata.schema)

    @declared_attr
    def idtable_name(cls):
        return cls.__tablename__ + '_idtable'

    @classmethod
    def base_id_live_index(cls):
        # eg:
        # CREATE UNIQUE INDEX idea_vote_base_id_live_ix
        # ON idea_vote (base_id) WHERE tombstone_date IS NULL
        # This can be called again, make sure to create index once.
        idx_name = cls.__tablename__ + "_base_id_live_ix"
        table = getattr(cls, '__table__', None)
        if table is not None:
            for idx in table.indexes:
                if idx.name == idx_name:
                    return idx
        return Index(
            idx_name,
            cls.base_id,
            postgresql_where=(cls.tombstone_date == None),
            unique=True)

    @classmethod
    def __declare_last__(cls):
        if cls == cls.base_polymorphic_class():
            # Compute at least once.
            cls.base_id_live_index()

    @declared_attr
    def __table_args__(cls):
        if cls == cls.base_polymorphic_class():
            return (UniqueConstraint('base_id', 'tombstone_date'), )

    @declared_attr
    def identity_table(cls):
        return Table(cls.idtable_name,
            cls.metadata,
            Column('id', Integer, primary_key=True))

    @declared_attr
    def id(cls):
        return Column(Integer, cls.id_sequence, primary_key=True)

    @declared_attr
    def base_id(cls):
        return Column(Integer,
            ForeignKey(cls.idtable_name + ".id"),
            nullable=False,
            info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})

    @classmethod
    def identity_join(cls):
        return join(cls, cls.identity_table,
            (cls.identity_table.c.id == cls.base_id) & (cls.tombstone_date == None))

    @classmethod
    def identity_join_r(cls):
        return join(cls.identity_table, cls,
            (cls.identity_table.c.id == cls.base_id) & (cls.tombstone_date == None))

    @classmethod
    def atemporal_relationship(cls, **kwargs):
        return relationship(cls,
            secondary=cls.identity_join_r,
            uselist=False, viewonly=True, **kwargs)

    def _before_insert(self):
        if self.using_virtuoso:
            (id,) = self.db.execute(
                self.id_sequence.next_value().select()).first()
            self.id = id
            if not self.base_id:
                self.db.execute(self.identity_table.insert().values(id=id))
                self.base_id = id
        else:
            if self.base_id:
                (id,) = self.db.execute(
                    self.id_sequence.next_value().select()).first()
                self.id = id
            else:
                res = self.db.execute(
                    self.identity_table.insert().values(
                        id=self.id_sequence.next_value()))
                self.id = self.base_id = res.inserted_primary_key[0]

    @declared_attr
    def _before_insert_set_event(cls):
        @event.listens_for(cls, 'before_insert', propagate=True)
        def receive_before_insert(mapper, connection, target):
            target._before_insert()

    @property
    def original_uri(self):
        return self.uri_generic(self.base_id)

    @declared_attr
    def live(cls):
        "The live version of this object, if any."
        # The base_id and tombstone_date are not initialized yet.
        def delay():
            return ((cls.identity_table.c.id == cls.base_id)
                    & (cls.tombstone_date==None))
        return relationship(
            cls, secondary=cls.identity_table, uselist=False, viewonly=True,
            secondaryjoin=delay)

    @property
    def latest(self):
        "The latest object in this series; may not be live."
        cls = self.__class__
        return self.db.query(cls
            ).filter(cls.base_id==self.base_id
            ).order_by(cls.tombstone_date.desc().nullsfirst()
            ).first()

    @classmethod
    def version_at_time_q(cls, base_id, timestamp, db=None):
        db = db or cls.default_db
        # Version that can be used without first
        # return db.query(cls).distinct(cls.base_id).filter(
        #     cls.base_id == self.base_id,
        #     (cls.tombstone_date == None) || (cls.tombstone_date > timestamp)
        #     ).order_by(cls.base_id, nullslast(asc(cls.tombstone_date)))
        return db.query(cls).filter(
            cls.base_id == base_id,
            (cls.tombstone_date == None) | (cls.tombstone_date > timestamp)
        ).order_by(nullslast(asc(cls.tombstone_date)))

    def version_at_time(self, timestamp):
        """The object that existed at that time, if any.
        Note that without a creation date, we may get an object that did not exist.
        """
        return self.version_at_time_q(self.base_id, timestamp, self.db).first()

    def copy(self, tombstone=None, db=None, **kwargs):
        """Clone object, optionally as tombstone (aka snapshot)
        reuse base_id. Redefine in subclasses to define arguments"""
        if tombstone is True or self.tombstone_date is not None:
            tombstone = datetime.utcnow()
        retval = self.__class__(
            base_id=self.base_id,
            tombstone_date=tombstone,
            **kwargs
        )
        db = db or self.db
        db.add(retval)
        return retval


class OriginMixin(object):
    creation_date = Column(DateTime, nullable=False, default=datetime.utcnow,
                           info={'rdf': QuadMapPatternS(None, DCTERMS.created)})

    def version_at_time(self, timestamp):
        if self.creation_date <= timestamp:
            return self


class TombstonableOriginMixin(TombstonableMixin, OriginMixin):
    def version_at_time(self, timestamp):
        if self.creation_date <= timestamp and (
                self.tombstone_date is None or
                self.tombstone_date > timestamp):
            return self


class HistoryMixinWithOrigin(HistoryMixin, OriginMixin):
    @classmethod
    def version_at_time_q(cls, base_id, timestamp, db=None):
        """The object that existed at that time, if any.
        """
        return super(HistoryMixinWithOrigin, cls).version_at_time_q(
            base_id, timestamp, db).filter(cls.creation_date <= timestamp)


class Dehistoricizer(ReplacingCloningVisitor):
    """remove refs to tombstone_date in an expression"""
    def __init__(self, *target_classes):
        self.tscols = set([
            target_cls.__mapper__.columns["tombstone_date"]
            for target_cls in target_classes
            if issubclass(target_cls, HistoryMixin)])

    def replace(self, elem):
        if isinstance(elem, BinaryExpression):
            if elem.left in self.tscols or elem.right in self.tscols:
                return True_()
            return elem
        elif isinstance(elem, BooleanClauseList):
            clauses = [self.replace(c) for c in elem.clauses if not isinstance(c, True_)]
            assert len(clauses)
            if len(clauses) == 1:
                return clauses[0]
            elif elem.operator == operators.or_:
                return BooleanClauseList.or_(*clauses)
            elif elem.operator == operators.and_:
                return BooleanClauseList.and_(*clauses)
            raise RuntimeError(elem.operator)
        return elem


def reln_in_history(self, name, timestamp):
    """read a relation at a given timestamp

    monkey-patched as a method of Base in modules.__init__"""
    my_cls = self.__class__
    reln = my_cls.__mapper__.relationships.get(name, None)
    if not reln:
        # AssociationProxy
        raise NotImplementedError()
    if reln.secondary:
        raise NotImplementedError()
    target_cls = reln.mapper.class_
    if not (issubclass(target_cls, (OriginMixin, TombstonableMixin)) or
            isinstance(my_cls, (OriginMixin, TombstonableMixin))):
        return getattr(self, name)
    h = Dehistoricizer(target_cls, my_cls)
    join_condition = h.traverse(reln.primaryjoin)
    if isinstance(self, HistoryMixin):
        filter = my_cls.base_id == self.base_id
    else:
        filter = my_cls.id == self.id
    if isinstance(self, TombstonableMixin):
        filter = filter & (
            (my_cls.tombstone_date == None) |
            (my_cls.tombstone_date > timestamp))
    if isinstance(self, OriginMixin):
        filter = filter & (my_cls.creation_date <= timestamp)
    if issubclass(target_cls, TombstonableMixin):
        filter = filter & (
            (target_cls.tombstone_date == None) |
            (target_cls.tombstone_date > timestamp))
    if issubclass(target_cls, OriginMixin):
        filter = filter & (target_cls.creation_date <= timestamp)
    if issubclass(target_cls, HistoryMixin):
        results = self.db.query(target_cls).distinct(target_cls.base_id).join(
            my_cls, join_condition).filter(filter).order_by(
            target_cls.base_id, nullslast(asc(target_cls.tombstone_date))).all()
    else:
        results = self.db.query(target_cls).join(
            my_cls, join_condition).filter(filter).all()
    if reln.uselist:
        return results
    else:
        assert len(results) <= 1
        if results:
            return results[0]


class HistoricalProxy(object):
    """A proxy for base objects, that will wrap an object and related objects
        with their version at a given time."""
    def __init__(self, target, timestamp, assume_in_time=False):
        ""
        # We expect the target to already belong to the right period
        # avoid setattr
        self.__dict__["_target"] = target
        self.__dict__["_timestamp"] = timestamp

    @classmethod
    def proxy_instance(cls, instance, timestamp, assume_in_time=False):
        if (not assume_in_time) and isinstance(
                instance, (HistoryMixin, OriginMixin)):
            instance = instance.version_at_time(timestamp)
            if instance is None:
                return None
        return cls(instance, timestamp)

    def _wrap(self, value, assume_in_time=False):
        from assembl.models import Base
        if isinstance(value, Base):
            return self.proxy_instance(value, self._timestamp, assume_in_time)
        elif isinstance(value, (list, tuple)):
            return list(filter(
                lambda x: x is not None,
                [self._wrap(x, assume_in_time) for x in value]))
        elif isinstance(value, dict):
            return {k: self._wrap(v, assume_in_time) for (k, v) in value.iteritems()}
        elif isinstance(value, Query):
            # punt. I think I could alter the query, but it requires looking into entities
            raise NotImplementedError()
        return value

    def __getattr__(self, name):
        if (name in self._target.__class__.__mapper__.relationships or
                isinstance(getattr(self._target.__class__, name),
                           AssociationProxy)):
            return self._wrap(
                self._target.reln_in_history(name, self._timestamp), True)
        return self._wrap(getattr(self._target, name))

    def __setattr__(self, name, value):
        raise RuntimeError("HistoricalProxies are read-only")

    def __call__(self, name, *args, **kwargs):
        return self._wrap(self._target.__call__(name, *args, **kwargs))


def as_time_proxy(self, timestamp, assume_in_time=False):
    if not assume_in_time and isinstance(
            self, (HistoryMixin, OriginMixin)):
        self = self.version_at_time(timestamp)
    if self is not None:
        return HistoricalProxy(self, timestamp)
