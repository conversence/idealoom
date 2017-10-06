from enum import Enum as pyEnum
from collections import OrderedDict
from sqlalchemy import Column, Integer, ForeignKey, Enum as sqlEnum
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import attributes
from sqlalchemy_utils.generic import (
    TypeMapper, GenericRelationshipProperty as GenericRelationshipProperty_)
from future.utils import string_types


class BaseTableEnum(object):
    # pretends to be a pyEnum by implementing __members__
    __members__ = OrderedDict()

    @classmethod
    def init_members(cls, Base):
        """Must be called after object initialization"""
        base_cls_by_table = {
            c.__tablename__: c for c in Base._decl_class_registry.values()
            if getattr(c, '__dict__', {}).get('__tablename__', None) and
            c.__dict__['__tablename__'] == c.base_tablename()}
        tables = list(base_cls_by_table.keys())
        # make table order predictable
        tables.sort()
        for table in tables:
            cls.__members__[table] = base_cls_by_table[table]


class UniversalTableRefColType(ENUM):
    def __init__(self, *args, **kwargs):
        kwargs['name'] = 'base_tables_enum'
        super(UniversalTableRefColType, self).__init__(
            BaseTableEnum, *args, **kwargs)

    def create(self, bind=None, checkfirst=True):
        # Alembic uses checkfirst=False, just override
        super(UniversalTableRefColType, self).create(bind, True)

    def reset_enum(self):
        kw = {}
        values, objects = self._parse_into_values([self.enum_class], kw)
        self._setup_for_values(values, objects, kw)


universalTableRefColType = UniversalTableRefColType()


def init_data(base_class):
    BaseTableEnum.init_members(base_class)
    universalTableRefColType.reset_enum()


class MulticlassTableRefColType(ENUM):
    def __init__(self, target_classes, *args, **kwargs):
        class_enum = pyEnum(kwargs['name'], {
            c.base_tablename(): c.base_concrete_class()
            for c in target_classes})
        super(MulticlassTableRefColType, self).__init__(
            class_enum, *args, **kwargs)

    def create(self, bind=None, checkfirst=True):
        # Alembic uses checkfirst=False, just override
        super(UniversalTableRefColType, self).create(bind, True)


class MyTypeMapper(TypeMapper):

    def class_to_value(self, cls):
        return cls.base_tablename()

    def column_is_type(self, column, other_type):
        return column == other_type.base_concrete_class()

    def value_to_class(self, value, base_class):
        if isinstance(value, string_types):
            return BaseTableEnum.__members__.get(value, None)
        elif isinstance(value, type):
            return value
        else:
            raise RuntimeError("Wrong value")


class GenericRelationshipProperty(GenericRelationshipProperty_):
    _generic_pointers = []

    def __init__(self, *args, **kwargs):
        kwargs['type_mapper'] = MyTypeMapper()
        super(GenericRelationshipProperty, self).__init__(*args, **kwargs)

    def instrument_class(self, mapper):
        super(GenericRelationshipProperty, self).instrument_class(mapper)
        self._generic_pointers.append((self, mapper))

    @classmethod
    def declare_universal_delete_cascades(cls, db):
        global _universal_pointer_classes
        for target_cls in BaseTableEnum.__members__.values():
            target_table = target_cls.__tablename__
            for (pointer, mapper) in cls._generic_pointers:
                source_cls = mapper.class_
                source_table = source_cls.base_tablename()
                target_type = pointer._discriminator_col.type
                type_enum = target_type.enum_class
                for key in type_enum.keys():
                    fname = "on_delete_%s_universal_cascade_%s_%s" % (target_table, source_table, key)
                    text = """
        DROP TABLE IF EXISTS %(fname)s;
        CREATE FUNCTION %(fname)s() RETURNS trigger AS $%(fname)s$
        BEGIN
            DELETE FROM public.%(source_table)s
            WHERE %(key)s_table = base_tables_enum.%(target_table)s
            AND %(key)s_id = OLD.id
        END;
        $%(fname)s$ LANGUAGE plpgsql;
            DROP TRIGGER IF EXISTS %(fname)s ON %(target_table)s;
            CREATE TRIGGER %(fname)s AFTER DELETE ON %(target_table)s
            DEFERRABLE FOR EACH ROW
            EXECUTE PROCEDURE %(fname)s
            """ % {'key': key, 'source_table': source_table,
                   'target_table': target_table, 'fname': fname}
                db.execute(text)


def generic_relationship(*args, **kwargs):
    return GenericRelationshipProperty(*args, **kwargs)


# class GenericPointerMixin(object):
#     @classmethod
#     def list_keys(cls):
#         for col in cls.__mapper__._column_to_property:
#             if issubclass(col.type, GenericPointerTable):
#                 name = col.name
#                 assert name.endswith('_table')
#                 name = name[:-6]
#                 assert name + "_id" in cls.__mapper__._props
#                 yield name

#     @classmethod
#     def guess_key(cls):
#         return next(cls.list_keys())

#     def get_instance(self, key=None):
#         key = key or self.guess_key()
#         table_enum = getattr(self, key + '_table', None)
#         if not table_enum:
#             return
#         assert issubclass(table_enum, object)
#         table_id = getattr(self, key + '_id', None)
#         return table_enum.get()

#     @classmethod
#     def references_to_instance_query(cls, instance, key=None):
#         key = key or self.guess_key()
#         filter_args = {
#             key + "_id": instance.id,
#             key + "_table": BaseTableEnum.__members__[instance.base_tablename()]
#         }
#         return instance.db.query(cls).filter_by(**filter_args)

