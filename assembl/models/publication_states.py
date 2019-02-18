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
from .langstrings import LangString


class PublicationFlow(Base):
    """A state automaton for publication states and transitions"""
    __tablename__ = "publication_flow"
    id = Column(Integer, primary_key=True)
    label = Column(String(60), nullable=False, unique=True)
    name_id = Column(
        Integer(), ForeignKey(LangString.id, ondelete="SET NULL", onupdate="CASCADE"))
    name = relationship(
        LangString,
        lazy="joined",
        primaryjoin=name_id == LangString.id,
        backref=backref("pub_flow_from_name", lazy="dynamic"),
        cascade="all")
    default_duplicate_handling = DuplicateHandling.USE_ORIGINAL

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


class PublicationState(Base):
    """A publication state"""
    __tablename__ = "publication_state"
    __table_args__ = (
        UniqueConstraint('flow_id', 'label'),
    )

    id = Column(Integer, primary_key=True)
    flow_id = Column(Integer, ForeignKey(
            PublicationFlow.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    label = Column(String(60), nullable=False)
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

    def unique_query(self):
        query, _ = super(PublicationState, self).unique_query()
        return query.filter_by(label=self.label, flow=self.flow), True


class PublicationTransition(Base):
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
    label = Column(String(60), nullable=False)
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
    name = relationship(
        LangString,
        lazy="joined",
        primaryjoin=name_id == LangString.id,
        backref=backref("pub_transition_from_name", lazy="dynamic"),
        cascade="all")
    default_duplicate_handling = DuplicateHandling.USE_ORIGINAL

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

