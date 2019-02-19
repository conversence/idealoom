# -*- coding: utf-8 -*-
"""Defining publication states for ideas and posts."""

from builtins import str
from builtins import object

from future.utils import as_native_str
from rdflib import URIRef
from sqlalchemy.orm import (
    relationship, backref)

from sqlalchemy import (
    Column,
    Boolean,
    Integer,
    String,
    Unicode,
    ForeignKey,
    UniqueConstraint,
)

from ..lib.sqla import CrudOperation, Base, DuplicateHandling
from . import DiscussionBoundBase, NamedClassMixin
from .langstrings import LangString
from .permissions import Permission, Role


class PublicationFlow(Base, NamedClassMixin):
    """A state automaton for publication states and transitions"""
    __tablename__ = "publication_flow"
    id = Column(Integer, primary_key=True)
    label = Column(String(), nullable=False, unique=True)
    name_id = Column(
        Integer(), ForeignKey(LangString.id, ondelete="SET NULL", onupdate="CASCADE"))
    name = relationship(
        LangString,
        lazy="joined",
        primaryjoin=name_id == LangString.id,
        backref=backref("pub_flow_from_name", lazy="dynamic"),
        cascade="all")
    default_duplicate_handling = DuplicateHandling.USE_ORIGINAL

    @classmethod
    def get_naming_column_name(cls):
        return "label"

    def state_by_label(self, label):
        for state in self.states:
            if state.label == label:
                return state

    def transition_by_label(self, label):
        for transition in self.transitions:
            if transition.label == label:
                return transition


    def unique_query(self):
        query, _ = super(PublicationFlow, self).unique_query()
        return query.filter_by(label=self.label), True

    def _do_update_from_json(
                self, json, parse_def, context,
                duplicate_handling=None, object_importer=None):
        target = super(PublicationFlow, self)._do_update_from_json(
            json, parse_def, context, object_importer=object_importer,
            duplicate_handling=duplicate_handling)
        state_ctx = target.get_collection_context('states', context)
        for stateJ in json['states']:
            PublicationState.create_from_json(
                stateJ, context=state_ctx, duplicate_handling=duplicate_handling)
        transition_ctx = target.get_collection_context('transitions', context)
        for transitionJ in json['transitions']:
            # easier if we create outside, so label setters can count on flow being there
            transition = target.transition_by_label(transitionJ['label']) or PublicationTransition(flow=target)
            ctx = transition.get_instance_context(transition_ctx)
            transition.update_from_json(transitionJ, context=ctx)
        return target


class PublicationState(Base, NamedClassMixin):
    """A publication state"""
    __tablename__ = "publication_state"
    __table_args__ = (
        UniqueConstraint('flow_id', 'label'),
    )

    id = Column(Integer, primary_key=True)
    flow_id = Column(Integer, ForeignKey(
            PublicationFlow.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    label = Column(String(), nullable=False)
    name_id = Column(
        Integer(), ForeignKey(
            LangString.id, ondelete="SET NULL", onupdate="CASCADE"))
    flow = relationship(PublicationFlow, backref="states")
    name = relationship(
        LangString,
        lazy="joined",
        primaryjoin=name_id == LangString.id,
        backref=backref("pub_state_from_name", lazy="dynamic"),
        cascade="all")
    default_duplicate_handling = DuplicateHandling.USE_ORIGINAL

    @classmethod
    def get_naming_column_name(cls):
        return "label"

    def unique_query(self):
        query, _ = super(PublicationState, self).unique_query()
        return query.filter_by(label=self.label, flow=self.flow), True


class PublicationTransition(Base, NamedClassMixin):
    """A publication transition"""
    __tablename__ = "publication_transition"
    __table_args__ = (
        UniqueConstraint('flow_id', 'label'),
    )

    id = Column(Integer, primary_key=True)
    flow_id = Column(Integer, ForeignKey(
            PublicationFlow.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    source_id = Column(Integer, ForeignKey(
            PublicationState.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    target_id = Column(Integer, ForeignKey(
            PublicationState.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    label = Column(String(), nullable=False)
    requires_permission_id = Column(Integer, ForeignKey(
            Permission.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False)
    name_id = Column(
        Integer(), ForeignKey(LangString.id))
    flow = relationship(PublicationFlow, backref="transitions")
    source = relationship(
        PublicationState,
        primaryjoin=source_id==PublicationState.id,
        backref="transitions_to")
    target = relationship(
        PublicationState,
        primaryjoin=target_id==PublicationState.id,
        backref="transitions_from")
    requires_permission = relationship(
        Permission,
        primaryjoin=requires_permission_id==Permission.id)
    name = relationship(
        LangString,
        lazy="joined",
        primaryjoin=name_id == LangString.id,
        backref=backref("pub_transition_from_name", lazy="dynamic"),
        cascade="all")
    default_duplicate_handling = DuplicateHandling.USE_ORIGINAL

    @classmethod
    def get_naming_column_name(cls):
        return "label"

    @property
    def source_label(self):
        return self.source.label
    
    @source_label.setter
    def source_label(self, label):
        self.source = next((state for state in self.flow.states if state.label == label))

    @property
    def target_label(self):
        return self.target.label

    @target_label.setter
    def target_label(self, label):
        self.target = next((state for state in self.flow.states if state.label == label))

    def unique_query(self):
        query, _ = super(PublicationTransition, self).unique_query()
        return query.filter_by(label=self.label, flow=self.flow), True


class StateDiscussionPermission(DiscussionBoundBase):
    """Which permissions are given to which roles for a given publication state."""
    __tablename__ = 'state_discussion_permission'
    id = Column(Integer, primary_key=True)
    discussion_id = Column(Integer, ForeignKey(
        'discussion.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    role_id = Column(Integer, ForeignKey(
        Role.id, ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey(
        Permission.id, ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    pub_state_id = Column(Integer, ForeignKey(
        PublicationState.id, ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False, index=True)
    discussion = relationship('Discussion')
    role = relationship(Role, lazy="joined")
    permission = relationship(Permission, lazy="joined")
    publication_state = relationship(PublicationState, lazy="joined")

    @property
    def role_name(self):
        return self.role.name

    @role_name.setter
    def role_name(self, label):
        self.role = Role.getByName(label)

    @property
    def permission_name(self):
        return self.permission.name

    @permission_name.setter
    def permission_name(self, label):
        self.permission = Permission.getByName(label)

    def get_discussion_id(self):
        return self.discussion_id or self.discussion.id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id, )
