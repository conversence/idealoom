"""Enumerations that can be stored in the database.

Mostly from http://techspot.zzzeek.org/2011/01/14/the-enum-recipe/ """
from __future__ import print_function
from builtins import object
import re

from future.utils import string_types
from sqlalchemy.types import SchemaType, TypeDecorator, Enum
from sqlalchemy import __version__
from sqlalchemy.dialects.postgresql import ENUM
from future.utils import with_metaclass, as_native_str

from .logging import getLogger

if __version__ < '0.6.5':
    raise NotImplementedError("Version 0.6.5 or higher of SQLAlchemy is required.")


class EnumSymbol(object):
    """Define a fixed symbol tied to a parent class."""

    def __init__(self, cls_, name, value, description):
        self.cls_ = cls_
        self.name = name
        self.value = value
        self.description = description

    def __reduce__(self):
        """Allow unpickling to return the symbol 
        linked to the DeclEnum class."""
        return getattr, (self.cls_, self.name)

    def __iter__(self):
        return iter([self.value, self.description])

    @as_native_str()
    def __repr__(self):
        return "<%s>" % self.name


class EnumMeta(type):
    """Generate new DeclEnum classes."""

    def __init__(cls, classname, bases, dict_):
        cls._reg = reg = cls._reg.copy()
        for k, v in dict_.items():
            if isinstance(v, tuple):
                sym = reg[v[0]] = EnumSymbol(cls, k, *v)
                setattr(cls, k, sym)
        super(EnumMeta, cls).__init__(classname, bases, dict_)

    def __iter__(self):
        return iter(list(self._reg.values()))


class DeclEnum(with_metaclass(EnumMeta, object)):
    """Declarative enumeration."""
    _reg = {}

    @classmethod
    def from_string(cls, value):
        try:
            return cls._reg[value]
        except KeyError:
            raise ValueError(
                    "Invalid value for %r: %r" % 
                    (cls.__name__, value)
                )

    @classmethod
    def values(cls):
        return cls._reg.keys()

    @classmethod
    def db_type(cls):
        return DeclEnumType(cls)


class DeclEnumType(SchemaType, TypeDecorator):
    def __init__(self, enum, **kwargs):
        super(DeclEnumType, self).__init__(**kwargs)
        self.enum = enum
        self.impl = Enum(
                        *list(enum.values()), 
                        name="ck%s" % re.sub(
                                    '([A-Z])', 
                                    lambda m:"_" + m.group(1).lower(), 
                                    enum.__name__)
                    )

    def _set_table(self, column, table):
        self.impl.name = "ck_%s_%s_%s" % (
            '_'.join(table.schema.split('.')), table.name, self.impl.name[3:])
        self.impl._set_table(column, table)

    def copy(self, **kw):
        return DeclEnumType(self.enum, **kw)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, EnumSymbol):
            return value.value
        elif isinstance(value, string_types):
            # Should not happen, but mask the error for now.
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum.from_string(value.strip())


class UpdatablePgEnum(ENUM):
    """A Postgres-native enum type that will add values to the native enum
    when the Python Enum is updated."""

    def __init__(self, *enums, ordered=True, **kw):
        self.ordered = ordered
        super(UpdatablePgEnum, self).__init__(*enums, **kw)

    def update_type(self, bind):
        "Update the postgres enum to match the values of the ENUM"
        value_names = self.enums
        db_names = [n for (n,) in bind.execute('select * from unnest(enum_range(null::%s))' % self.name)]
        if not self.ordered:
            value_names = set(value_names)
            db_names = set(db_names)
        if value_names != db_names:
            # Check no element was removed. If needed, introduce tombstones to enums.
            removed = set(db_names) - set(value_names)
            if removed:
                getLogger().warn("Some enum values were removed from type %s: %s" % (
                    self.name, ', '.join(removed)))
                if self.ordered:
                    db_names = [n for n in db_names if n not in removed]
                else:
                    db_names = db_names - removed
            if self.ordered:
                # Check no reordering.
                value_names_present = [n for n in value_names if n in db_names]
                assert db_names == value_names_present, "Do not reorder elements in an enum"
                # add missing values
                bind = bind.execution_options(isolation_level="AUTOCOMMIT")
                for i, name in enumerate(value_names):
                    if i >= len(db_names) or name != db_names[i]:
                        if i == 0:
                            if len(db_names):
                                bind.execute(
                                    "ALTER TYPE %s ADD VALUE '%s' BEFORE '%s'" % (
                                        self.name, name, db_names[0]))
                            else:
                                bind.execute(
                                    "ALTER TYPE %s ADD VALUE '%s' " % (
                                        self.name, name))
                        else:
                            if len(db_names):
                                bind.execute(
                                    "ALTER TYPE %s ADD VALUE '%s' AFTER '%s'" % (
                                        self.name, name, db_names[i - 1]))
                            else:
                                bind.execute(
                                    "ALTER TYPE %s ADD VALUE '%s' " % (
                                        self.name, name))
                        db_names[i:i] = [name]
            else:
                bind = bind.execution_options(isolation_level="AUTOCOMMIT")
                for name in value_names - db_names:
                    bind.execute(
                        "ALTER TYPE %s ADD VALUE '%s' " % (self.name, name))

    def create(self, bind=None, checkfirst=True):
        schema = self.schema or self.metadata.schema
        if bind.dialect.has_type(
                bind, self.name, schema=schema):
            self.update_type(bind)
        else:
            super(UpdatablePgEnum, self).create(bind, False)

    def _on_metadata_create(self, target, bind, checkfirst=False, **kw):
        self.schema = target.schema
        super(UpdatablePgEnum, self)._on_metadata_create(
            target, bind, checkfirst=checkfirst, **kw)


if __name__ == '__main__':
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import Column, Integer, String, create_engine
    from sqlalchemy.orm import Session

    Base = declarative_base()

    class EmployeeType(DeclEnum):
        part_time = "P", "Part Time"
        full_time = "F", "Full Time"
        contractor = "C", "Contractor"

    class Employee(Base):
        __tablename__ = 'employee'

        id = Column(Integer, primary_key=True)
        name = Column(String(60), nullable=False)
        type = Column(EmployeeType.db_type())

        @as_native_str()
        def __repr__(self):
            return "Employee(%r, %r)" % (self.name, self.type)

    e = create_engine('sqlite://', echo=True)
    Base.metadata.create_all(e)

    sess = Session(e)

    sess.add_all([
        Employee(name='e1', type=EmployeeType.full_time),
        Employee(name='e2', type=EmployeeType.full_time),
        Employee(name='e3', type=EmployeeType.part_time),
        Employee(name='e4', type=EmployeeType.contractor),
        Employee(name='e5', type=EmployeeType.contractor),
    ])
    sess.commit()

    print(sess.query(Employee).filter_by(type=EmployeeType.contractor).all())
