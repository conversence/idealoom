"""This defines Context objects for traversal of the magic api.

Pyramid allows to use model objects as Context objects, but in our cases they're surrogates for model objects.
"""
from builtins import str
from builtins import next
from builtins import object
from traceback import print_exc
import logging

from future.utils import string_types, as_native_str
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.expression import and_
from sqlalchemy.inspection import inspect as sqlainspect
from sqlalchemy.exc import InvalidRequestError
from pyramid.security import Allow, Everyone, ALL_PERMISSIONS, DENY_ALL
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPNotFound
from abc import ABCMeta, abstractmethod
import reg

from assembl.auth import P_READ, R_SYSADMIN
from assembl.auth.util import discussion_from_request
from assembl.lib.sqla import uses_list, get_named_class, Base
from assembl.lib.logging import getLogger
from assembl.lib.decl_enums import DeclEnumType
from future.utils import with_metaclass


class BaseContext(object):
    """The base class for all traversal contexts.
    Delegate everything to parent by default."""

    def __init__(self, parent=None, acl=None):
        self.__parent__ = parent
        if parent:
            self.__acl__ = acl or parent.__acl__
            self.depth = getattr(parent, "depth", 0) + 1
        elif acl:
            self.acl = acl
            self.depth = 0

    def find_collection(self, collection_class_name):
        """Find a collection by name"""
        return self.__parent__.find_collection(collection_class_name)

    def get_discussion_id(self):
        """Get the current discussion_id somehow

        often from a :py:class:`DiscussionBoundBase` instance"""
        return self.__parent__.get_discussion_id()

    def get_request(self):
        """Get the request from the context, if known"""
        return self.__parent__.get_request()

    def get_all_instances(self):
        # Should be a yield from
        for i in self.__parent__.get_all_instances():
            yield i

    def get_user_id(self):
        return self.__parent__.get_user_id()

    def context_chain(self):
        yield self
        for ctx in self.__parent__.context_chain():
            yield ctx

    def get_instance_ctx_of_class(self, cls):
        """Look in the context chain for a model instance of a given class,
        and return that context"""
        return self.__parent__.get_instance_ctx_of_class(cls)

    def get_instance_of_class(self, cls):
        """Look in the context chain for a model instance of a given class"""
        return self.__parent__.get_instance_of_class(cls)

    def get_permissions(self):
        """Get the permissions from the request, maybe altering on the way.

        See e.g. in :py:class:`assembl.models.widgets.IdeaCreatingWidget.BaseIdeaHidingCollection`"""
        return self.__parent__.get_permissions()

    def __eq__(self, other):
        return (self.__class__ is other.__class__ and
                self.__parent__ == other.__parent__)

    def __hash__(self):
        h = hash(self.__class__)
        if self.__parent__:
            h = h % hash(self.__parent__)


class DictContext(BaseContext):
    """A Context defined using a simple dictionary"""
    def __init__(self, name, acl, subobjects=None):
        super(DictContext, self).__init__(None, acl)
        self.__name__ = name
        subobjects = subobjects or ()
        self.subobjects = {
            ctx.__name__: ctx for ctx in subobjects}
        for context in subobjects:
            context.__parent__ = self
        if acl:
            self.__acl__ = acl

    def __getitem__(self, key):
        return self.subobjects[key]


ACL_READABLE = [(Allow, R_SYSADMIN, ALL_PERMISSIONS),
                (Allow, Everyone, P_READ), DENY_ALL]
ACL_RESTRICTIVE = [(Allow, R_SYSADMIN, ALL_PERMISSIONS), DENY_ALL]


@reg.dispatch(
    reg.match_instance('inst_ctx', lambda inst_ctx, ctx: inst_ctx._instance),
    reg.match_key('ctx', lambda inst_ctx, ctx: ctx.collection.qual_name()))
def collection_creation_side_effects(inst_ctx, ctx):
    """Multiple dispatch adapter for collection-related side effects"""
    return ()


class AppRoot(DictContext):
    """The root context. Anything not defined by a root comes here."""
    def __init__(self, request=None, user_id=None):
        self.request = request
        self.user_id = user_id
        self._permissions = None
        self._user_cache = None
        super(AppRoot, self).__init__('', ACL_READABLE, [
            Api2Context(self, ACL_RESTRICTIVE),
            DictContext('admin', ACL_RESTRICTIVE, [
                DictContext('permissions', None, [
                    DiscussionsContext()])]),
            DictContext('api', ACL_RESTRICTIVE, [
                DictContext('v1', None, [
                    DiscussionsContext(),
                    DictContext('token', ACL_READABLE)])])])

    def __getitem__(self, key):
        if key in self.subobjects:
            return self.subobjects[key]
        from assembl.models import Discussion
        discussion = Discussion.default_db.query(Discussion).filter_by(
            slug=key).first()
        if not discussion:
            raise KeyError()
        return discussion

    # Base of recursion for methods defined in BaseContext

    def get_request(self):
        """Get the request from the context, if known"""
        return self.request

    def context_chain(self):
        yield self

    def find_collection(self, collection_class_name):
        """Find a collection by name"""
        return None

    def get_discussion_id(self):
        return None

    def get_user_id(self):
        if self.user_id:
            return self.user_id
        request = self.get_request()
        if request:
            return request.authenticated_userid

    def get_instance_ctx_of_class(self, cls):
        return None # I'm the holder of the user, but not the user's context

    def get_instance_of_class(self, cls):
        from assembl.models import AgentProfile
        if issubclass(cls, AgentProfile):
            user_id = self.get_user_id()
            if user_id and user_id != Everyone:
                if self._user_cache is None:
                    self._user_cache = AgentProfile.get(user_id)
                return self._user_cache

    def get_all_instances(self):
        from assembl.models import User
        user = self.get_instance_of_class(User)
        if user is not None:
            yield user

    def get_permissions(self):
        if self.user_id:
            if self._permissions is None:
                from assembl.auth.util import get_permissions
                self._permissions = get_permissions(
                    self.user_id, self.get_discussion_id())
            return self._permissions
        elif self.request:
            # only use request if it knows the user
            return self.request.permissions
        return []


class DiscussionsContext(BaseContext):
    """A context where discussions, named by id, are sub-contexts"""

    __name__ = 'discussion'

    def __getitem__(self, key):
        from assembl.models import Discussion
        discussion = Discussion.get(int(key))
        if not discussion:
            raise KeyError()
        return discussion


class TraversalContext(BaseContext):
    """The base class for the magic API"""
    def __init__(self, parent, acl=None):
        self.__parent__ = parent
        self.__acl__ = acl or parent.__acl__
        self.depth = getattr(parent, "depth", 0) + 1

    def decorate_query(self, query, ctx, tombstones=False):
        """Given a SQLAlchemy query, add joins and filters that correspond
        to this step in the traversal path."""
        return self.__parent__.decorate_query(query, ctx, tombstones)

    def creation_side_effects_rec(self, inst_ctx, top_ctx):
        """Recursion"""
        for inst in self.__parent__.creation_side_effects_rec(inst_ctx, top_ctx):
            yield inst

    def creation_side_effects(self, inst_ctx=None):
        """Generator for objects that are created as side-effect of another
        object's creation. They can have their own side-effect.
        """
        for sub_inst_ctx in self.creation_side_effects_rec(inst_ctx, self):
            yield sub_inst_ctx
            for sub_sub in self.creation_side_effects(sub_inst_ctx):
                yield sub_sub

    def on_new_instance(self, instance):
        """If a model instance was created in this context, let the context learn about it.
        Exists mostly for :py:meth:`RelationCollectionDefinition.on_new_instance`"""
        self.__parent__.on_new_instance(instance)

    def get_target_class(self):
        """What is the model class we can expect to find at this context?"""
        return None


class Api2Context(TraversalContext):
    """The root class for the magic API (``/data``)

    Sub-contexts are :py:class:`ClassContext`"""
    _class_cache = {}

    __name__ = 'data'

    def __init__(self, parent, acl=None):
        super(Api2Context, self).__init__(parent, acl)

    def get_default_view(self):
        pass

    def __getitem__(self, key):
        cls = get_named_class(key)
        if not cls:
            raise KeyError()
        return ClassContext(self, cls)

    def all_class_names(self):
        return [k.external_typename()
                for k in Base._decl_class_registry.values()
                if getattr(k, 'external_typename', False)]

    # Base of recursion for methods defined in TraversalContext

    def decorate_query(self, query, ctx, tombstones=False):
        return query

    def on_new_instance(self, instance):
        pass

    def creation_side_effects_rec(self, inst_ctx, top_ctx):
        """Apply simple side-effects from the instance"""
        for inst in inst_ctx._instance.creation_side_effects(top_ctx):
            yield inst


def process_args(args, cls):
    mapper = sqlainspect(cls)
    for key, value in args.items():
        column = mapper.c.get(key)
        if column is not None:
            if isinstance(column.type, DeclEnumType):
                yield (key, column.type.enum.from_string(value))
            elif column.type.python_type == int:
                yield (key, int(value))
            elif column.type.python_type == float:
                yield (key, float(value))
            elif column.type.python_type == bool:
                yield (key, asbool(value))
            else:
                yield (key, value)
            continue
        reln = mapper.relationships.get(key)
        if (reln is not None and reln.direction.name == 'MANYTOONE' and
                isinstance(value, string_types)):
            assert(len(reln.local_columns) == 1)
            key = next(reln.local_columns.__iter__()).key
            yield (key, reln.mapper.class_.get_database_id(value))
            continue
        attribute = getattr(cls, key, None)
        if isinstance(attribute, property) and attribute.fset is not None:
            yield (key, value)
            continue


class ClassContext(TraversalContext):
    """A context that represents a given model class (e.g. ``/data/Idea``)

    Sub-contexts are :py:class:`InstanceContext`, given by numeric ID."""
    def __init__(self, parent, cls):
        # permission on class context are quite restrictive. review.
        super(ClassContext, self).__init__(parent)
        self._class = cls
        self.__name__ = cls.external_typename()
        self.class_alias = aliased(cls, name="alias_%s" % (cls.__name__))

    def __getitem__(self, key):
        from assembl.models import Preferences
        instance = self._class.get_instance(key)
        if not instance:
            raise KeyError()
        # TODO: use a protocol for this
        if isinstance(instance, Preferences):
            return PreferenceContext(self, instance)
        return InstanceContext(self, instance)

    def get_default_view(self):
        my_default = getattr(self._class, 'default_view', None)
        if my_default:
            return my_default
        return self.__parent__.get_default_view()

    def create_query(self, id_only=True, tombstones=False):
        from assembl.models import TombstonableMixin
        cls = self._class
        alias = self.class_alias
        if id_only:
            query = self._class.default_db.query(alias.id)
        else:
            query = self._class.default_db.query(alias)
        # TODO: Distinguish tombstone condition from other base_conditions
        if issubclass(cls, TombstonableMixin) and not tombstones:
            query = query.filter(and_(*cls.base_conditions(alias)))
        return query

    def get_class(self, typename=None):
        """Returns the collection class, or subclass designated by typename"""
        cls = self._class
        if typename is not None:
            other_cls = get_named_class(typename)
            if other_cls and issubclass(other_cls, cls):
                return other_cls
        return cls

    def get_target_class(self):
        return self._class

    def get_target_alias(self):
        return self.class_alias

    def create_object(self, typename=None, json=None):
        cls = self.get_class(typename)
        with self._class.default_db.no_autoflush:
            inst_ctx = cls.create_from_json(json, self)
            return [inst_ctx._instance]

    def __eq__(self, other):
        return (super(ClassContext, self).__eq__(other) and
                self._class == other._class)

    def __hash__(self):
        return super(ClassContext, self).hash() % hash(self._class)


class ClassContextPredicate(object):
    """A `view predicate factory`_ that checks that a given traversal context
    is a :py:class:`ClassContext` and represents the given class.

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        self.val = val

    def text(self):
        return 'class_context = %s' % (self.val,)

    phash = text

    def __call__(self, context, request):
        return isinstance(context, ClassContext) and context._class == self.val


class InstanceContext(TraversalContext):
    """A context that represents a given model instance (e.g. ``/data/Idea/12``)

    Sub-contexts are :py:class:`CollectionContext`, given by relationship name
    or taken from :py:meth:`assembl.lib.sqla.Base.extra_collections_dict`.
    """
    def __init__(self, parent, instance):
        # Do not call super, because it will set the acl.
        self._instance = instance
        self.__name__ = str(instance.id)
        self.__parent__ = parent
        # relations = instance.__class__.__mapper__.relationships

    _collections_by_class = {}

    @classmethod
    def _get_collections(cls, for_class):
        return for_class.get_collections()

    def get_collection_names(self):
        return list(self._instance.get_collections().keys())

    def get_default_view(self):
        my_default = getattr(self._instance, 'default_view', None)
        if my_default:
            return my_default
        return self.__parent__.get_default_view()

    @property
    def __acl__(self):
        if getattr(self._instance, '__acl__', None):
            return self._instance.__acl__
        if getattr(self._instance, 'discussion', None):
            return self._instance.discussion.__acl__
        discussion_id = self.get_discussion_id()
        if discussion_id:
            from assembl.models import Discussion
            return Discussion.get(discussion_id).__acl__
        return self.__parent__.__acl__

    def __getitem__(self, key):
        cls = self._instance.__class__
        collection = self._get_collections(cls).get(key, None)
        if not collection:
            raise KeyError()
        return collection.make_context(self)

    def find_collection(self, collection_class_name):
        return self.__parent__.find_collection(collection_class_name)

    def get_discussion_id(self):
        from assembl.models import DiscussionBoundBase
        if isinstance(self._instance, DiscussionBoundBase):
            try:
                discussion_id = self._instance.get_discussion_id()
                if discussion_id:
                    return discussion_id
            except Exception:
                pass
        return super(InstanceContext, self).get_discussion_id()

    def get_instance_of_class(self, cls):
        if isinstance(self._instance, cls):
            return self._instance
        return self.__parent__.get_instance_of_class(cls)

    def get_instance_ctx_of_class(self, cls):
        if isinstance(self._instance, cls):
            return self
        return self.__parent__.get_instance_ctx_of_class(cls)

    def get_all_instances(self):
        yield self._instance
        # Should be a yield from
        for i in self.__parent__.get_all_instances():
            yield i

    def get_target_class(self):
        return self._instance.__class__

    def get_target_alias(self):
        return self.__parent__.get_target_alias()

    @as_native_str()
    def __repr__(self):
        return "<InstanceContext (%s)>" % (self._instance,)

    def __eq__(self, other):
        return (super(InstanceContext, self).__eq__(other) and
                self._instance is other._instance)

    def __hash__(self):
        return super(ClassContext, self).hash() % id(self._instance)


class InstanceContextPredicate(object):
    """A `view predicate factory`_ that checks that a given traversal context
    is a :py:class:`InstanceContext`, and that the instance is of the given class.

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        self.val = val

    def text(self):
        return 'instance_context = %s' % (self.val,)

    phash = text

    def __call__(self, context, request):
        return isinstance(context, InstanceContext) and\
            isinstance(context._instance, self.val)


class InstanceContextPredicateWithExceptions(object):
    """A `view predicate factory`_ that checks that a given traversal context
    is a :py:class:`InstanceContext`, and that the instance is of the given
    class, but not of one of a given set of subclass exceptions.

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        cls, cls_exceptions = val
        self.val = cls
        self.cls_exceptions = cls_exceptions

    def text(self):
        return 'instance_context = %s except %s' % (
            self.val, repr(self.cls_exceptions))

    phash = text

    def __call__(self, context, request):
        return isinstance(context, InstanceContext) and\
            isinstance(context._instance, self.val) and\
            not isinstance(context._instance, self.cls_exceptions)


class CollectionContext(TraversalContext):
    """A context that represents a collection of model objects related to the model object of the parent :py:class:`InstanceContext`.

    The collection itself is embodied by a :py:class:`AbstractCollectionDefinition` object, often backed by a SQLA relationship.
    Sub-contexts are :py:class:`InstanceContext`, indexed by Id.
    """
    def __init__(self, parent, collection, instance):
        super(CollectionContext, self).__init__(parent)
        if isinstance(collection, InstrumentedAttribute):
            collection = collection.property
        # permission on class context are quite restrictive. review.
        self.collection = collection
        self.parent_instance = instance
        self.collection_class = self.collection.collection_class
        self.class_alias = aliased(self.collection_class)
        # TODO: This makes some tests fail, and I need to understand why.
        # name="alias_%s_%d" % (self.collection_class.__name__, self.depth))

    def get_default_view(self):
        my_default = self.collection.get_default_view()
        if my_default:
            return my_default
        return self.__parent__.get_default_view()

    def __getitem__(self, key):
        instance = self.collection.get_instance(key, self.parent_instance)
        if not instance:
            raise KeyError()
        return InstanceContext(self, instance)

    @property
    def __name__(self):
        return self.collection.name

    def get_collection_class(self, typename=None):
        """Returns the collection class, or subclass designated by typename"""
        cls = self.collection_class
        if typename is not None:
            other_cls = get_named_class(typename)
            if other_cls and issubclass(other_cls, cls):
                return other_cls
        return cls

    def get_target_class(self):
        return self.collection_class

    def get_target_alias(self):
        return self.class_alias

    def create_query(self, id_only=True, tombstones=False):
        alias = self.class_alias
        if id_only:
            query = self.parent_instance.db.query(alias.id)
            return self.decorate_query(query, self, tombstones).distinct()
        else:
            # There will be duplicates. But sqla takes care of them,
            # virtuoso won't allow distinct on full query,
            # and a distinct subquery takes forever.
            # Oh, and quietcast loses the distinct. Just great.
            query = self.parent_instance.db.query(alias)
            return self.decorate_query(query, self, tombstones)

    def decorate_query(self, query, ctx, tombstones=False):
        # This will decorate a query with a join on the relation.
        from assembl.models import TombstonableMixin
        query = self.collection.decorate_query(
            query, self.__parent__.get_target_alias(),
            self.get_target_alias(), self.parent_instance, ctx)
        cls = self.collection_class
        if issubclass(cls, TombstonableMixin) and not tombstones:
            query = query.filter(cls.tombstone_condition(self.class_alias))
        return super(CollectionContext, self).decorate_query(
            query, ctx, tombstones=False)

    def on_new_instance(self, instance):
        self.collection.on_new_instance(instance, self.parent_instance)
        super(CollectionContext, self).on_new_instance(instance)

    def get_permissions(self):
        permissions = super(
            CollectionContext, self).get_permissions()
        new_permissions = self.collection.extra_permissions(permissions)
        if new_permissions:
            permissions = new_permissions.extend(permissions)
        return permissions

    def create_object(self, typename=None, json=None):
        cls = self.get_collection_class(typename)
        with self.parent_instance.db.no_autoflush:
            try:
                inst_ctx = cls.create_from_json(json, self)
                if inst_ctx:
                    return [inst_ctx._instance]
            except Exception as e:
                # import pdb
                # pdb.post_mortem()
                print_exc()
                raise e

    def creation_side_effects_rec(self, inst_ctx, top_ctx):
        """Apply side-effects through multiple dispatch on the collection"""
        for ins in self.__parent__.creation_side_effects_rec(inst_ctx, top_ctx):
            yield ins
        assert isinstance(top_ctx, CollectionContext)
        assert isinstance(inst_ctx, InstanceContext)
        for ins in collection_creation_side_effects(inst_ctx, self):
            yield ins

    @as_native_str()
    def __repr__(self):
        return "<CollectionContext (%s)>" % (
            self.collection,)

    def find_collection(self, collection_class_name):
        if self.collection.qual_name() == collection_class_name:
            return self
        return self.__parent__.find_collection(collection_class_name)

    def __eq__(self, other):
        return (super(CollectionContext, self).__eq__(other) and
                self.collection is other.collection)

    def __hash__(self):
        return super(ClassContext, self).hash() % hash(
            self.collection.qual_name())


class NamedCollectionContextPredicate(object):
    """A `view predicate factory`_ that checks that a given traversal context
    is a :py:class:`CollectionContext`, whose collection's
    :py:meth:`AbstractCollectionDefinition.name` is as given.

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        self.val = val

    def text(self):
        return 'collection_context_name = %s' % (self.val,)

    phash = text

    def __call__(self, context, request):
        return (isinstance(context, CollectionContext) and
                self.val == context.collection.qual_name())


class NamedCollectionInstancePredicate(object):
    """A `view predicate factory`_ that checks that a given traversal context
    is an :py:class:`InstanceContext` under a :py:class:`CollectionContext`
    whose collection's :py:meth:`AbstractCollectionDefinition.name` is as given.

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        self.val = val

    def text(self):
        return 'collection_instance_context_name = %s' % (self.val,)

    phash = text

    def __call__(self, context, request):
        parent = context.__parent__
        return (isinstance(context, InstanceContext) and
                isinstance(parent, CollectionContext) and
                self.val == parent.collection.qual_name())


class SecureConnectionPredicate(object):
    """A `view predicate factory`_ that checks that the connection is secure (https).

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        self.val = bool(val)

    def text(self):
        return 'secure_connection'

    phash = text

    def __call__(self, context, request):
        return self.val == (
            request.environ['wsgi.url_scheme'] == 'https')


class CollectionContextClassPredicate(object):
    """A `view predicate factory`_ that checks that a given traversal context
    is a :py:class:`CollectionContext`, where the class of the targets of the
    relationship is as given.

    .. _`view predicate factory`: http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hooks.html#view-and-route-predicates
    """
    def __init__(self, val, config):
        self.val = val

    def text(self):
        return 'collection_context_class = %s' % (self.val,)

    phash = text

    def __call__(self, context, request):
        return isinstance(context, CollectionContext) and\
            issubclass(context.collection_class, self.val)


class AbstractCollectionDefinition(with_metaclass(ABCMeta, object)):
    """Represents a collection of objects related to an instance."""

    def __init__(self, owner_class, name, collection_class):
        self.owner_class = owner_class
        self.collection_class = collection_class
        self.name = name

    def make_context(self, parent_ctx):
        return CollectionContext(parent_ctx, self, parent_ctx._instance)

    def get_instance(self, key, parent_instance):
        instance = self.collection_class.get_instance(key)
        # Validate that the instance belongs to the collection...
        if instance and not self.contains(parent_instance, instance):
            raise KeyError("This instance does not live in this collection.")
        return instance

    @abstractmethod
    def decorate_query(
            self, query, owner_alias, coll_alias, parent_instance, ctx):
        pass

    def on_new_instance(
            self, instance, parent_instance):
        pass

    @abstractmethod
    def contains(self, parent_instance, instance):
        pass

    def get_default_view(self):
        pass

    def qual_name(self):
        """The fully qualified name of the collection, including owning class name.

        Used in :py:class:`NamedCollectionContextPredicate` and :py:meth:`TraversalContext.find_collection`."""
        return ".".join((self.owner_class.__name__, self.name))

    def extra_permissions(self, permissions):
        """Return a list of extra permissions that could be added along the way.

        See e.g. in :py:class:`assembl.models.widgets.IdeaCreatingWidget.BaseIdeaHidingCollection`"""
        return None

    @as_native_str()
    def __repr__(self):
        return "<%s %s -(%s)-> %s>" % (
            self.__class__.__name__,
            self.owner_class.__name__,
            self.name,
            self.collection_class.__name__)


class RelationCollectionDefinition(AbstractCollectionDefinition):
    """A collection of objects related to an instance through a relationship."""
    back_relation = None

    def __init__(self, owner_class, relationship, name=None):
        super(RelationCollectionDefinition, self).__init__(
            owner_class, name or relationship.key, relationship.mapper.class_)
        self.relationship = relationship
        back_properties = list(getattr(relationship, '_reverse_property', ()))
        if back_properties:
            # TODO: How to chose?
            self.back_relation = back_properties.pop()
            self.owner_class = self.back_relation.mapper.class_

    def decorate_query(
            self, query, owner_alias, coll_alias, parent_instance, ctx):
        # This will decorate a query with a join on the relation.
        inv = self.back_relation
        if inv:
            query = query.join(owner_alias,
                               getattr(coll_alias, inv.key))
        else:
            # hope for the best
            try:
                query = query.join(owner_alias)
            except InvalidRequestError:
                getLogger().error("Could not join %s to %s" % (owner_alias, query))
                # This is very likely to fail downstream
                return query
        found_key = False
        if inv and not uses_list(inv):
            # Try to constrain on coll_alias's key vs owner_alias.
            # Difficult cases happen when tombstone is part of the
            # reln's columns
            for column in inv.local_columns:
                for fk in column.foreign_keys:
                    if fk.column.table == parent_instance.__class__.__table__:
                        query = query.filter(
                            getattr(coll_alias, column.name) ==
                            parent_instance.id)
                        found_key = True
        if not found_key:
            query = query.filter(owner_alias.id == parent_instance.id)
        return query

    def on_new_instance(self, instance, parent_instance):
        if not isinstance(instance, self.collection_class):
            return
        # if the relation is through a helper class,
        #   create that and add to assocs (TODO)
        # otherwise set the appropriate relationship (below.)
        # Prefer non-list properties because we can check if they're set.
        if not uses_list(self.relationship):
            if getattr(parent_instance, self.relationship.key, None) is None:
                # print "Setting1 ", parent_instance, self.relationship.key, instance
                setattr(parent_instance, self.relationship.key, instance)
        elif self.back_relation and not uses_list(self.back_relation):
            inv = self.back_relation
            if getattr(instance, inv.key, None) is None:
                # print "Setting2 ", instance, inv.key, parent_instance
                setattr(instance, inv.key, parent_instance)
        elif self.back_relation:
            inv = self.back_relation
            # print "Adding1 ", instance, inv.key, parent_instance
            getattr(instance, inv.key).append(parent_instance)
        else:
            # print "Adding2 ", parent_instance, self.relationship.key, instance
            getattr(parent_instance, self.relationship.key).append(instance)

    def get_attribute(self, instance, property=None):
        # What we have is a property, not an instrumented attribute;
        # but they share the same key.
        property = property or self.relationship
        return getattr(instance, property.key)

    def contains(self, parent_instance, instance):
        if uses_list(self.relationship):
            if self.back_relation and not uses_list(self.back_relation):
                return self.get_attribute(
                    instance, self.back_relation) == parent_instance
            return instance in self.get_attribute(parent_instance)
        else:
            return instance == self.get_attribute(parent_instance)

    def get_instance(self, key, parent_instance):
        instance = None
        if key == '-':
            if not uses_list(self.relationship):
                instance = getattr(
                    parent_instance, self.relationship.key, None)
            else:
                # Allow if it happens to be a singleton.
                instances = getattr(parent_instance, self.relationship.key)
                if len(instances) == 1:
                    return instances[0]
                raise KeyError()
        else:
            instance = self.collection_class.get_instance(key)
        # Validate that the instance belongs to the collection...
        if instance and not self.contains(parent_instance, instance):
            raise KeyError("This instance does not live in this collection.")
        return instance

    @as_native_str()
    def __repr__(self):
        if self.back_relation:
            return "<%s %s <-(%s/%s)-> %s>" % (
                self.__class__.__name__,
                self.owner_class.__name__,
                self.back_relation.key if self.back_relation else '',
                self.name,
                self.collection_class.__name__)
        else:
            return super(RelationCollectionDefinition, self).__repr__()


class UserBoundNamespacedDictContext(TraversalContext):
    """Represents the set of user-bound namespace-K-V items"""
    def __init__(self, parent, collection):
        # Do not call super, because it will set the acl.
        self.collection = collection
        self.__parent__ = parent
        self._instance = parent._instance

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def as_collection(self):
        return self.collection.as_collection(self._instance)

    def __getitem__(self, namespace):
        user_ns_b_kvdict = self.collection.get_instance(
            namespace, self._instance)
        return UserNSBoundDictContext(user_ns_b_kvdict, self)

    def get_target_class(self):
        from assembl.models.user_key_values import UserNsDict
        return UserNsDict


class UserNSBoundDictContext(TraversalContext):
    """Represents the set of user-bound, namespace-bound K-V items"""
    def __init__(self, user_ns_b_kvdict, parent):
        # Do not call super, because it will set the acl.
        self.collection = user_ns_b_kvdict
        self.__parent__ = parent
        self.parent_instance = parent._instance

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def __getitem__(self, key):
        return UserNSKeyBoundDictItemContext(self.collection, self, key)

    def get_target_class(self):
        from assembl.models.user_key_values import NamespacedUserKVCollection
        return NamespacedUserKVCollection


class UserNSKeyBoundDictItemContext(TraversalContext):
    """Represents a value which is bound to a user, namespace and key"""
    def __init__(self, user_ns_b_kvdict, parent, key):
        # Do not call super, because it will set the acl.
        self.collection = user_ns_b_kvdict
        self.__parent__ = parent
        self.parent_instance = parent.parent_instance
        self.key = key

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def __getitem__(self, key):
        return None

    def get_target_class(self):
        return None


class UserNsDictCollection(AbstractCollectionDefinition):
    def __init__(self, cls):
        from assembl.models.user_key_values import NamespacedUserKVCollection
        super(UserNsDictCollection, self).__init__(
            cls, 'user_ns_kv', NamespacedUserKVCollection)

    def make_context(self, parent_context):
        return UserBoundNamespacedDictContext(parent_context, self)

    def decorate_query(
            self, query, owner_alias, last_alias, parent_instance, ctx):
        # No clue what to do here; UserKVCollection is not a sqla object
        return query.outerjoin(
            owner_alias, owner_alias.id != None)

    def contains(self, parent_instance, namespace):
        # all namespaces exist
        return True

    def as_collection(self, parent_instance):
        from pyramid.threadlocal import get_current_request
        from pyramid.httpexceptions import HTTPUnauthorized
        from assembl.models.user_key_values import UserNsDict
        request = get_current_request()
        if request is not None:
            user_id = request.unauthenticated_userid
            # Check again downstream for real userid
            if user_id is None:
                raise HTTPUnauthorized()
        else:
            raise RuntimeError()
        return UserNsDict(parent_instance, user_id)

    def get_instance(self, namespace, parent_instance):
        c = self.as_collection(parent_instance)
        return c[namespace]


class NamespacedDictContext(TraversalContext):
    """Represents the set of namespace-K-V items"""
    def __init__(self, parent, collection):
        # Do not call super, because it will set the acl.
        self.collection = collection
        self.__parent__ = parent
        self._instance = parent._instance

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def as_collection(self):
        return self.collection.as_collection(self._instance)

    def __getitem__(self, namespace):
        ns_kvdict = self.collection.get_instance(
            namespace, self._instance)
        return NSBoundDictContext(ns_kvdict, self)

    def get_target_class(self):
        from assembl.models.user_key_values import NsDict
        return NsDict


class NSBoundDictContext(TraversalContext):
    """Represents the set of namespace-bound K-V items"""
    def __init__(self, ns_kvdict, parent):
        # Do not call super, because it will set the acl.
        self.collection = ns_kvdict
        self.__parent__ = parent
        self.parent_instance = parent._instance

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def __getitem__(self, key):
        return NSKeyBoundDictItemContext(self.collection, self, key)

    def get_target_class(self):
        from assembl.models.user_key_values import NamespacedKVCollection
        return NamespacedKVCollection


class NSKeyBoundDictItemContext(TraversalContext):
    """Represents a value which is bound to a namespace and key"""
    def __init__(self, ns_kvdict, parent, key):
        # Do not call super, because it will set the acl.
        self.collection = ns_kvdict
        self.__parent__ = parent
        self.parent_instance = parent.parent_instance
        self.key = key

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def __getitem__(self, key):
        return None

    def get_target_class(self):
        return None


class NsDictCollection(AbstractCollectionDefinition):
    def __init__(self, cls):
        from assembl.models.user_key_values import NamespacedKVCollection
        super(NsDictCollection, self).__init__(
            cls, 'ns_kv', NamespacedKVCollection)

    def make_context(self, parent_context):
        return NamespacedDictContext(parent_context, self)

    def decorate_query(
            self, query, owner_alias, last_alias, parent_instance, ctx):
        # No clue what to do here; KVCollection is not a sqla object
        return query.outerjoin(
            owner_alias, owner_alias.id != None)

    def contains(self, parent_instance, namespace):
        # all namespaces exist
        return True

    def as_collection(self, parent_instance):
        from assembl.models.user_key_values import NsDict
        return NsDict(parent_instance)

    def get_instance(self, namespace, parent_instance):
        c = self.as_collection(parent_instance)
        return c[namespace]


class PreferenceContext(TraversalContext):
    """Represents a set of preference values (eg for a discussion)

    Sub-contexts are :py:class:`PreferenceValueContext`"""
    def __init__(self, parent_context, preferences):
        # Do not call super, because it will set the acl.
        self.preferences = preferences
        self.__parent__ = parent_context

    @property
    def __acl__(self):
        return ACL_RESTRICTIVE

    def __getitem__(self, key):
        """returns the :py:class:`PreferenceValueContext` for that preference"""
        return PreferenceValueContext(self.preferences, self, key)

    def get_target_class(self):
        from assembl.models.preferences import Preferences
        return Preferences


class DiscussionPreferenceContext(PreferenceContext):
    """Represents a set of preference values for a discussion

    Backed by a :py:class:`DiscussionPreferenceCollection`, sub-contexts are
    :py:class:`PreferenceValueContext`"""
    def __init__(self, parent_context, collection):
        self.collection = collection
        self.parent_instance = parent_context._instance
        preferences = collection.as_collection(self.parent_instance)
        super(DiscussionPreferenceContext, self).__init__(
            parent_context, preferences)

    @property
    def __acl__(self):
        # collection acl?
        return self.__parent__.__acl__


class PreferenceValueContext(TraversalContext):
    """Represents a specific discussion preference"""
    def __init__(self, preferences, parent, key):
        # Do not call super, because it will set the acl.
        self.collection = preferences
        self.__parent__ = parent
        self.key = key

    @property
    def __acl__(self):
        return self.__parent__.__acl__

    def __getitem__(self, key):
        return None

    def get_target_class(self):
        return None


class DiscussionPreferenceCollection(AbstractCollectionDefinition):
    """Represents the collection of preferences for a given discussion's
    :py:class:`DiscussionPreferenceContext`."""
    def __init__(self, cls):
        from assembl.models.preferences import Preferences
        super(DiscussionPreferenceCollection, self).__init__(
            cls, 'settings', Preferences)

    def make_context(self, parent_context):
        return DiscussionPreferenceContext(parent_context, self)

    def decorate_query(
            self, query, owner_alias, last_alias, parent_instance, ctx):
        # No clue what to do here; UserKVCollection is not a sqla object
        return query.outerjoin(
            owner_alias, owner_alias.id != None)

    def contains(self, parent_instance, key):
        from assembl.models.preferences import Preferences
        return key in Preferences.property_defaults

    def as_collection(self, parent_instance):
        return parent_instance.preferences

    def get_instance(self, key, parent_instance):
        c = self.as_collection(parent_instance)
        return c[key]


def app_root_factory(request, user_id=None):
    return AppRoot(request, user_id)


def root_factory(request, user_id=None):
    """The factory function for the root context"""
    # OK, this is the old code... I need to do better, but fix first.
    from ..models import Discussion
    if request.matchdict and 'discussion_id' in request.matchdict:
        discussion_id = int(request.matchdict['discussion_id'])
        discussion = Discussion.default_db.query(Discussion).get(discussion_id)
        if not discussion:
            raise HTTPNotFound("No discussion ID %d" % (discussion_id,))
        return discussion
    elif request.matchdict and 'discussion_slug' in request.matchdict:
        discussion_slug = request.matchdict['discussion_slug']
        discussion = Discussion.default_db.query(Discussion).filter_by(
            slug=discussion_slug).first()
        if not discussion:
            raise HTTPNotFound("No discussion named %s" % (discussion_slug,))
        return discussion
    return app_root_factory(request, user_id)


def includeme(config):
    config.add_view_predicate('ctx_class', ClassContextPredicate)
    config.add_view_predicate('ctx_instance_class', InstanceContextPredicate)
    config.add_view_predicate('ctx_instance_class_with_exceptions',
                              InstanceContextPredicateWithExceptions)
    config.add_view_predicate('ctx_named_collection',
                              NamedCollectionContextPredicate)
    config.add_view_predicate('ctx_named_collection_instance',
                              NamedCollectionInstancePredicate)
    config.add_view_predicate('secure_connection', SecureConnectionPredicate)
    config.add_view_predicate('ctx_collection_class',
                              CollectionContextClassPredicate,
                              weighs_less_than='ctx_named_collection')
