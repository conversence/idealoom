"""All classes relative to permissions."""
from future import standard_library
standard_library.install_aliases()
from collections import defaultdict
import logging

from sqlalchemy import (
    Boolean,
    Column,
    String,
    ForeignKey,
    Integer,
    event,
    Index,
)
from pyramid.httpexceptions import HTTPBadRequest
from sqlalchemy.orm import (
    relationship, backref)
from rdflib import URIRef

from ..lib import config
from ..lib.sqla import CrudOperation
from . import Base, DiscussionBoundBase, PrivateObjectMixin
from ..auth import *
from ..semantic.namespaces import (
    SIOC, ASSEMBL, QUADNAMES)
from ..semantic.virtuoso_mapping import (
    QuadMapPatternS, USER_SECTION, AppQuadStorageManager)
from .auth import User, AgentProfile

log = logging.getLogger(__name__)


class Role(Base):
    """A role that a user may have in a discussion"""
    __tablename__ = 'role'

    id = Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)

    @classmethod
    def get_role(cls, name, session=None):
        session = session or cls.default_db()
        return session.query(cls).filter_by(name=name).first()

    @classmethod
    def populate_db(cls, db=None):
        db = db or cls.default_db()
        db.execute("lock table %s in exclusive mode" % cls.__table__.name)
        roles = {r[0] for r in db.query(cls.name).all()}
        for role in SYSTEM_ROLES - roles:
            db.add(cls(name=role))


class UserRole(Base, PrivateObjectMixin):
    """roles that a user has globally (eg admin.)"""
    __tablename__ = 'user_role'
    rdf_sections = (USER_SECTION,)
    rdf_class = SIOC.Role

    id = Column(Integer, primary_key=True)
    profile_id = Column(
        Integer, ForeignKey('agent_profile.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True, info={'rdf': QuadMapPatternS(
            None, SIOC.function_of,
            AgentProfile.agent_as_account_iri.apply(None))})
    user = relationship(
        AgentProfile, backref=backref("roles", cascade="all, delete-orphan"))
    role_id = Column(
        Integer, ForeignKey('role.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    role = relationship(Role, lazy="joined")

    def get_user_uri(self):
        return AgentProfile.uri_generic(self.profile_id)

    def get_role_name(self):
        return self.role.name

    def set_role_by_name(self, name):
        self.role = Role.getRole(name)

    def container_url(self):
        return "/data/User/%d/roles" % (self.user_id)

    def is_owner(self, user_id):
        return self.profile_id == user_id

    @classmethod
    def restrict_to_owners(cls, query, user_id):
        "filter query according to object owners"
        return query.filter(cls.profile_id == user_id)

    def get_default_parent_context(self, request=None, user_id=None):
        return self.user.get_collection_context(
            'roles', self.user.get_class_context(), request, user_id)

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        role_alias = alias_maker.alias_from_relns(cls.role)
        return [
            QuadMapPatternS(cls.iri_class().apply(cls.id),
                SIOC.name, role_alias.name,
                name=QUADNAMES.class_UserRole_rolename,
                sections=(USER_SECTION,)),
            QuadMapPatternS(AgentProfile.agent_as_account_iri.apply(cls.user_id),
                SIOC.has_function, cls.iri_class().apply(cls.id),
                name=QUADNAMES.class_UserRole_global, sections=(USER_SECTION,)),
            # Note: The IRIs need to distinguish UserRole from LocalUserRole
            QuadMapPatternS(cls.iri_class().apply(cls.id),
                SIOC.has_scope, URIRef(AppQuadStorageManager.local_uri()),
                name=QUADNAMES.class_UserRole_globalscope, sections=(USER_SECTION,)),
            ]


@event.listens_for(UserRole, 'after_insert', propagate=True)
@event.listens_for(UserRole, 'after_delete', propagate=True)
def send_user_to_socket_for_user_role(mapper, connection, target):
    user = target.user
    if not target.user:
        user = User.get(target.user_id)
    user.send_to_changes(connection, CrudOperation.UPDATE, view_def="private")
    user.send_to_changes(connection, CrudOperation.UPDATE)



class LocalUserRole(DiscussionBoundBase, PrivateObjectMixin):
    """The role that a user has in the context of a discussion"""
    __tablename__ = 'local_user_role'
    rdf_sections = (USER_SECTION,)
    rdf_class = SIOC.Role

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('agent_profile.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True,
        info={'rdf': QuadMapPatternS(
            None, SIOC.function_of, AgentProfile.agent_as_account_iri.apply(None))})
    user = relationship(AgentProfile, backref=backref("local_roles", cascade="all, delete-orphan"))
    discussion_id = Column(Integer, ForeignKey(
        'discussion.id', ondelete='CASCADE'), nullable=False, index=True,
        info={'rdf': QuadMapPatternS(None, SIOC.has_scope)})
    discussion = relationship(
        'Discussion', backref=backref(
            "local_user_roles", cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})
    role_id = Column(Integer, ForeignKey(
        'role.id', ondelete='CASCADE', onupdate='CASCADE'),
        index=True, nullable=False)
    role = relationship(Role, lazy="joined")
    requested = Column(Boolean, server_default='0', default=False)
    # BUG in virtuoso: It will often refuse to create an index
    # whose name exists in another schema. So having this index in
    # schemas assembl and assembl_test always fails.
    # TODO: Bug virtuoso about this,
    # or introduce the schema name in the index name as workaround.
    # __table_args__ = (
    #     Index('user_discussion_idx', 'profile_id', 'discussion_id'),)

    def get_discussion_id(self):
        return self.discussion_id or self.discussion.id

    def container_url(self):
        return "/data/Discussion/%d/all_users/%d/local_roles" % (
            self.discussion_id, self.profile_id)

    def get_default_parent_context(self, request=None, user_id=None):
        return self.user.get_collection_context('roles', request=request, user_id=user_id)

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    @property
    def role_name(self):
        return self.role.name

    @role_name.setter
    def role_name(self, name):
        self.role = Role.getRole(name)

    def unique_query(self):
        query, _ = super(LocalUserRole, self).unique_query()
        profile_id = self.profile_id or self.user.id
        role_id = self.role_id or self.role.id
        return query.filter_by(
            profile_id=profile_id, role_id=role_id), True

    def get_user_uri(self):
        return AgentProfile.uri_generic(self.profile_id)

    def _do_update_from_json(
            self, json, parse_def, ctx,
            duplicate_handling=None, object_importer=None):
        user_id = ctx.get_user_id()
        json_user_id = json.get('user', None)
        if json_user_id is None:
            json_user_id = user_id
        else:
            json_user_id = AgentProfile.get_database_id(json_user_id)
            # Do not allow changing user
            if self.profile_id is not None and json_user_id != self.profile_id:
                raise HTTPBadRequest()
        self.profile_id = json_user_id
        role_name = json.get("role", None)
        if not (role_name or self.role_id):
            role_name = R_PARTICIPANT
        if role_name:
            role = self.db.query(Role).filter_by(name=role_name).first()
            if not role:
                raise HTTPBadRequest("Invalid role name:"+role_name)
            self.role = role
        json_discussion_id = json.get('discussion', None)
        if json_discussion_id:
            from .discussion import Discussion
            json_discussion_id = Discussion.get_database_id(json_discussion_id)
            # Do not allow change of discussion
            if self.discussion_id is not None \
                    and json_discussion_id != self.discussion_id:
                raise HTTPBadRequest()
            self.discussion_id = json_discussion_id
        else:
            if not self.discussion_id:
                raise HTTPBadRequest()
        return self

    def is_owner(self, user_id):
        return self.profile_id == user_id

    @classmethod
    def restrict_to_owners(cls, query, user_id):
        "filter query according to object owners"
        return query.filter(cls.profile_id == user_id)

    @classmethod
    def base_conditions(cls, alias=None, alias_maker=None):
        cls = alias or cls
        return (cls.requested == False,)

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        role_alias = alias_maker.alias_from_relns(cls.role)
        return [
            QuadMapPatternS(AgentProfile.agent_as_account_iri.apply(cls.profile_id),
                SIOC.has_function, cls.iri_class().apply(cls.id),
                name=QUADNAMES.class_LocalUserRole_global,
                conditions=(cls.requested == False,),
                sections=(USER_SECTION,)),
            QuadMapPatternS(cls.iri_class().apply(cls.id),
                SIOC.name, role_alias.name,
                conditions=(cls.requested == False,),
                sections=(USER_SECTION,),
                name=QUADNAMES.class_LocalUserRole_rolename)]

    crud_permissions = CrudPermissions(
        P_SELF_REGISTER, P_READ, P_ADMIN_DISC, P_ADMIN_DISC,
        P_SELF_REGISTER, P_SELF_REGISTER, P_READ)

    @classmethod
    def user_can_cls(cls, user_id, operation, permissions):
        # bypass... more checks are required upstream,
        # see assembl.views.api2.auth.add_local_role
        if operation == CrudPermissions.CREATE \
                and P_SELF_REGISTER_REQUEST in permissions:
            return True
        return super(LocalUserRole, cls).user_can_cls(
            user_id, operation, permissions)


@event.listens_for(LocalUserRole, 'after_delete', propagate=True)
@event.listens_for(LocalUserRole, 'after_insert', propagate=True)
def send_user_to_socket_for_local_user_role(
        mapper, connection, target):
    user = target.user
    if not target.user:
        user = User.get(target.profile_id)
    user.send_to_changes(connection, CrudOperation.UPDATE, target.discussion_id)
    user.send_to_changes(
        connection, CrudOperation.UPDATE, target.discussion_id, "private")


class Permission(Base):
    """A permission that a user may have"""
    __tablename__ = 'permission'
    id = Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)

    @classmethod
    def populate_db(cls, db=None):
        db = db or cls.default_db()
        db.execute("lock table %s in exclusive mode" % cls.__table__.name)
        perms = {p[0] for p in db.query(cls.name).all()}
        for perm in ASSEMBL_PERMISSIONS - perms:
            db.add(cls(name=perm))


class DiscussionPermission(DiscussionBoundBase):
    """Which permissions are given to which roles for a given discussion."""
    __tablename__ = 'discussion_permission'
    id = Column(Integer, primary_key=True)
    discussion_id = Column(Integer, ForeignKey(
        'discussion.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    discussion = relationship(
        'Discussion', backref=backref(
            "acls", cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})
    role_id = Column(Integer, ForeignKey(
        'role.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    role = relationship(Role, lazy="joined")
    permission_id = Column(Integer, ForeignKey(
        'permission.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    permission = relationship(Permission, lazy="joined")

    def role_name(self):
        return self.role.name

    def permission_name(self):
        return self.permission.name

    def get_discussion_id(self):
        return self.discussion_id or self.discussion.id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id, )


def create_default_permissions(discussion):
    session = discussion.db
    permissions = {p.name: p for p in session.query(Permission).all()}
    roles = {r.name: r for r in session.query(Role).all()}
    defaults = discussion.preferences['default_permissions']
    for role_name, permission_names in defaults.items():
        role = roles.get(role_name, None)
        assert role, "Unknown role: " + role_name
        for permission_name in permission_names:
            permission = permissions.get(permission_name, None)
            assert permission, "Unknown permission: " + permission_name
            session.add(DiscussionPermission(
                discussion=discussion, role=role, permission=permission))



class UserTemplate(DiscussionBoundBase, User):
    "A fake user with default permissions and Notification Subscriptions."
    __tablename__ = "user_template"

    __mapper_args__ = {
        'polymorphic_identity': 'user_template'
    }

    id = Column(
        Integer,
        ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True
    )

    discussion_id = Column(Integer, ForeignKey(
        "discussion.id", ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    discussion = relationship(
        "Discussion", backref=backref(
            "user_templates", cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    role_id = Column(Integer, ForeignKey(
        Role.id, ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    for_role = relationship(Role)

    # Create an index for (discussion, role)?

    def get_discussion_id(self):
        return self.discussion_id or self.discussion.id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    @classmethod
    def get_applicable_notification_subscriptions_classes(cls):
        """
        The classes of notifications subscriptions that make sense to put in
        a template user.

        Right now, that is all concrete classes that are global to the discussion.
        """
        from ..lib.utils import get_concrete_subclasses_recursive
        from ..models import NotificationSubscriptionGlobal
        return get_concrete_subclasses_recursive(NotificationSubscriptionGlobal)

    def get_notification_subscriptions(self):
        return self.get_notification_subscriptions_and_changed()[0]

    def get_notification_subscriptions_and_changed(self, on_thread=True):
        """the notification subscriptions for this template.
        Materializes applicable subscriptions.."""
        from .notification import (
            NotificationSubscription,
            NotificationSubscriptionStatus,
            NotificationCreationOrigin,
            NotificationSubscriptionGlobal)

        needed_classes = set(
            self.get_applicable_notification_subscriptions_classes())
        # We need to materialize missing NotificationSubscriptions,
        # But have duplication issues, probably due to calls on multiple
        # threads. So iterate until it works.
        query = self.db.query(NotificationSubscription).filter_by(
            discussion_id=self.discussion_id, user_id=self.id)
        changed = False
        discussion = self.discussion
        my_id = self.id
        role_name = self.for_role.name.split(':')[-1]
        # TODO: Fill from config.
        subscribed = defaultdict(bool)
        default_config = config.get_config().get(
            ".".join(("subscriptions", role_name, "default")),
            "FOLLOW_SYNTHESES")
        for role in default_config.split('\n'):
            subscribed[role.strip()] = True

        def calculate_missing():
            my_subscriptions = query.all() if self.id else []
            by_class = defaultdict(list)
            for sub in my_subscriptions:
                by_class[sub.__class__].append(sub)
            my_subscriptions_classes = set(by_class.keys())
            # We should have at most one subscription of a class, but we've had more.
            # Delete excess subscriptions
            for cl, subs in by_class.items():
                if not issubclass(cl, NotificationSubscriptionGlobal):
                    # Should not happen, all global on template
                    continue
                if len(subs) > 1:
                    log.error("There were many subscriptions of class %s" % (cl))
                    subs.sort(key=lambda sub: sub.id)
                    first_sub = subs[0]
                    for sub in subs[1:]:
                        first_sub.merge(sub)
                        sub.delete()
                by_class[cl] = subs[0]
            my_subscriptions = list(by_class.values())
            missing = needed_classes - my_subscriptions_classes
            if my_subscriptions_classes - needed_classes:
                log.error("Unknown subscription class: " + repr(
                    my_subscriptions_classes - needed_classes))
            discussion_kwarg = (dict(discussion_id=discussion.id)
                if discussion.id else dict(discussion=discussion))
            return [
                cls(
                    user_id=my_id,
                    creation_origin=NotificationCreationOrigin.DISCUSSION_DEFAULT,
                    status=(NotificationSubscriptionStatus.ACTIVE
                            if subscribed[cls.__mapper__.polymorphic_identity.name]
                            else NotificationSubscriptionStatus.INACTIVE_DFT),
                    **discussion_kwarg)
                for cls in missing
            ]
        if on_thread:
            changed |= self.locked_object_creation(
                calculate_missing, num_attempts=10)
        else:
            for ob in calculate_missing():
                self.db.add(ob)
                changed = True
        if changed:
            self.db.expire(self, ['notification_subscriptions'])
        return self.notification_subscriptions, changed


Index("user_template", "discussion_id", "role_id")
