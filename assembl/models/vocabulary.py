from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declared_attr

from . import Base, DeclarativeAbstractMeta
from .langstrings import LangString
from ..lib.logging import getLogger
from ..lib.decl_enums import UpdatablePgEnum


class AbstractVocabulary(Base):
    __metaclass__ = DeclarativeAbstractMeta
    __abstract__ = True
    """A vocabulary backed by some identifier"""

    @declared_attr
    def name_id(cls):
        return Column("name_id", Integer, ForeignKey(LangString.id))

    @declared_attr
    def name(cls):
        return relationship(
            LangString,
            lazy="joined", single_parent=True,
            primaryjoin=cls.name_id == LangString.id,
            backref=backref("idvocabulary_from_name", lazy="dynamic"),
            cascade="all, delete-orphan")

    @classmethod
    def populate_db(cls, db=None):
        db = db or cls.default_db
        initial_names = getattr(cls, "_initial_names", None)
        if initial_names:
            values = db.query(cls).filter(cls.id.in_(cls.Enum.__members__.values())).all()
            values = {v.id: v for v in values}
            for id, names in initial_names.items():
                value = values.get(id, None)
                if value is None:
                    value = cls(id=id, name=LangString())
                    db.add(value)
                if value.name is None:
                    value.name = LangString()
                existing = {e.locale for e in value.name.entries}
                for locale, val in names.items():
                    if locale not in existing:
                        value.name.add_value(val, locale)


class AbstractIdentifierVocabulary(AbstractVocabulary):
    """A vocabulary backed by a string"""
    __abstract__ = True
    id = Column(String, primary_key=True)


class AbstractEnumVocabulary(AbstractVocabulary):
    """A vocabulary backed by a Python Enum.
    Define an 'Enum' member class (derived from enum.Enum)
    in concret subclasses.
    """
    __abstract__ = True

    @declared_attr
    def pg_enum_name(cls):
        return cls.__tablename__ + '_type'

    @declared_attr
    def pg_enum(cls):
        # TODO: reify
        return UpdatablePgEnum(
            cls.Enum, name=cls.pg_enum_name,
            metadata=cls.metadata, create_type=True)

    @declared_attr
    def id(cls):
        return Column(cls.pg_enum, primary_key=True)

    @declared_attr
    def name_id(cls):
        return Column("name_id", Integer, ForeignKey(LangString.id))

    @declared_attr
    def name(cls):
        return relationship(
            LangString,
            lazy="joined", single_parent=True,
            primaryjoin=cls.name_id == LangString.id,
            backref=backref("voc_%s_from_name" % (cls.__tablename__,),
                            lazy="dynamic"),
            cascade="all, delete-orphan")

    @classmethod
    def populate_db(cls, db=None):
        db = db or cls.default_db
        cls.pg_enum.create(db.bind)
        super(AbstractEnumVocabulary, cls).populate_db(db)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.id.name)
