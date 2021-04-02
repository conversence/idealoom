"""Subsets of :py:class:`assembl.models.idea.Idea` and :py:class:`assembl.models.idea.IdeaLink`."""
from collections import defaultdict
from datetime import datetime
from abc import abstractmethod
from itertools import chain

from future.utils import as_native_str
from sqlalchemy.orm import (
    relationship, backref)
from sqlalchemy import (
    Column,
    Integer,
    String,
    UnicodeText,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import join
import lxml.html as htmlt

from . import DiscussionBoundBase, OriginMixin
from .discussion import Discussion
from .langstrings import LangString
from ..semantic.virtuoso_mapping import QuadMapPatternS
from ..auth import (
    CrudPermissions, P_ADMIN_DISC, P_EDIT_SYNTHESIS)
from .idea import Idea, IdeaLink, RootIdea, IdeaVisitor, HtmlizationVisitor
from ..semantic.namespaces import (
    SIOC, CATALYST, IDEA, ASSEMBL, DCTERMS, QUADNAMES)
from assembl.views.traversal import AbstractCollectionDefinition
from ..views.traversal import collection_creation_side_effects, InstanceContext


class defaultdictlist(defaultdict):
    def __init__(self):
        super(defaultdictlist, self).__init__(list)


class IdeaGraphView(DiscussionBoundBase, OriginMixin):
    """
    A view on the graph of idea.
    """
    __tablename__ = "idea_graph_view"
    __external_typename = "Map"
    rdf_class = CATALYST.Map

    type = Column(String(60), nullable=False)
    id = Column(Integer, primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})

    creation_date = Column(DateTime, nullable=False, default=datetime.utcnow,
        info={'rdf': QuadMapPatternS(None, DCTERMS.created)})

    discussion_id = Column(
        Integer,
        ForeignKey('discussion.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True,
        info={'rdf': QuadMapPatternS(None, SIOC.has_container)}
    )
    discussion = relationship(
        Discussion, backref=backref("views", cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    __mapper_args__ = {
        'polymorphic_identity': 'idea_graph_view',
        'polymorphic_on': 'type',
        'with_polymorphic': '*'
    }

    def copy(self, db=None):
        retval = self.__class__()
        retval.discussion = self.discussion
        return retval

    def get_discussion_id(self):
        return self.discussion_id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id, )

    crud_permissions = CrudPermissions(P_ADMIN_DISC)

    @abstractmethod
    def get_idea_links(self):
        pass

    @abstractmethod
    def get_ideas(self):
        pass



class SubGraphIdeaAssociation(DiscussionBoundBase):
    """Association table saying that an Idea is part of a ExplicitSubGraphView"""
    __tablename__ = 'sub_graph_idea_association'
    __table_args__ = (
        UniqueConstraint("idea_id", "sub_graph_id"),
    )

    id = Column(Integer, primary_key=True)
    sub_graph_id = Column(Integer, ForeignKey(
        'explicit_sub_graph_view.id', ondelete="CASCADE", onupdate="CASCADE"),
        index=True, nullable=False)
    sub_graph = relationship(
        "ExplicitSubGraphView", backref=backref(
            "idea_assocs", cascade="all, delete-orphan"))
    idea_id = Column(Integer, ForeignKey(
        'idea.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    # reference to the "Idea" object for proxying
    idea = relationship("Idea", backref="in_subgraph_assoc")
    include_body = Column(Boolean, server_default='false')

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        idea_assoc = alias_maker.alias_from_class(cls)
        idea_alias = alias_maker.alias_from_relns(cls.idea)
        # Assume tombstone status of target is similar to source, for now.
        conditions = [(idea_assoc.idea_id == idea_alias.id),
                      (idea_alias.tombstone_date == None)]
        if discussion_id:
            conditions.append((idea_alias.discussion_id == discussion_id))
        return [
            QuadMapPatternS(
                Idea.iri_class().apply(idea_assoc.idea_id),
                IDEA.inMap,
                IdeaGraphView.iri_class().apply(idea_assoc.sub_graph_id),
                conditions=conditions,
                name=QUADNAMES.sub_graph_idea_assoc_reln)
        ]

    def get_discussion_id(self):
        sub_graph = self.sub_graph or IdeaGraphView.get(self.sub_graph_id)
        return sub_graph.get_discussion_id()

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return ((cls.sub_graph_id == ExplicitSubGraphView.id),
                (ExplicitSubGraphView.discussion_id == discussion_id))

    discussion = relationship(
        Discussion, viewonly=True, uselist=False, secondary=Idea.__table__,
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    def unique_query(self):
        # documented in lib/sqla
        idea_id = self.idea_id or self.idea.id
        subgraph_id = self.sub_graph_id or self.sub_graph.id
        return self.db.query(self.__class__).filter_by(
            idea_id=idea_id, sub_graph_id=subgraph_id), True

    # @classmethod
    # def special_quad_patterns(cls, alias_maker, discussion_id):
    #     return [QuadMapPatternS(
    #         Idea.iri_class().apply(cls.source_id),
    #         IDEA.includes,
    #         Idea.iri_class().apply(cls.target_id),
    #         name=QUADNAMES.idea_inclusion_reln)]

    crud_permissions = CrudPermissions(P_ADMIN_DISC)


class SubGraphIdeaLinkAssociation(DiscussionBoundBase):
    """Association table saying that an IdeaLink is part of a ExplicitSubGraphView"""
    __tablename__ = 'sub_graph_idea_link_association'
    id = Column(Integer, primary_key=True)
    __table_args__ = (
        UniqueConstraint("idea_link_id", "sub_graph_id"),
    )

    sub_graph_id = Column(Integer, ForeignKey(
        'explicit_sub_graph_view.id', ondelete="CASCADE", onupdate="CASCADE"),
        index=True, nullable=False)
    sub_graph = relationship(
        "ExplicitSubGraphView", backref=backref(
            "idealink_assocs", cascade="all, delete-orphan"))

    idea_link_id = Column(Integer, ForeignKey(
        'idea_idea_link.id', ondelete="CASCADE", onupdate="CASCADE"),
        index=True, nullable=False)

    # reference to the "IdeaLink" object for proxying
    idea_link = relationship("IdeaLink", backref="in_subgraph_assoc")

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        idea_link_assoc = alias_maker.alias_from_class(cls)
        idea_link_alias = alias_maker.alias_from_relns(cls.idea_link)
        # Assume tombstone status of target is similar to source, for now.
        conditions = [(idea_link_assoc.idea_link_id == idea_link_alias.id),
                      (idea_link_alias.tombstone_date == None)]
        if discussion_id:
            conditions.extend(cls.get_discussion_conditions(
                discussion_id, alias_maker))

        return [
            QuadMapPatternS(
                IdeaLink.iri_class().apply(idea_link_assoc.idea_link_id),
                IDEA.inMap,
                IdeaGraphView.iri_class().apply(idea_link_assoc.sub_graph_id),
                conditions=conditions,
                name=QUADNAMES.sub_graph_idea_link_assoc_reln)
        ]

    def get_discussion_id(self):
        sub_graph = self.sub_graph or IdeaGraphView.get(self.sub_graph_id)
        return sub_graph.get_discussion_id()

    def unique_query(self):
        # documented in lib/sqla
        idea_link_id = self.idea_link_id or self.idea_link.id
        subgraph_id = self.sub_graph_id or self.sub_graph.id
        return self.db.query(self.__class__).filter_by(
            idea_link_id=idea_link_id, sub_graph_id=subgraph_id), True

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        if not alias_maker:
            return ((cls.sub_graph_id == ExplicitSubGraphView.id),
                    (ExplicitSubGraphView.discussion_id == discussion_id))
        subgraph_alias = alias_maker.alias_from_relns(cls.sub_graph)
        return ((subgraph_alias.discussion_id == discussion_id))

    crud_permissions = CrudPermissions(P_ADMIN_DISC)


class ExplicitSubGraphView(IdeaGraphView):
    """
    A view where the Ideas and/or ideaLinks have been explicitly selected.

    Note that ideaLinks may point to ideas that are not in the graph.  They
    should be followed transitively (if their nature is compatible) to reach
    every idea in graph as if they were directly linked.
    """
    __tablename__ = "explicit_sub_graph_view"

    id = Column(Integer, ForeignKey(
        'idea_graph_view.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    # proxy the 'idea' attribute from the 'idea_assocs' relationship
    # for direct access
    ideas = association_proxy('idea_assocs', 'idea',
        creator=lambda idea: SubGraphIdeaAssociation(idea=idea))

    # proxy the 'idea_link' attribute from the 'idealink_assocs'
    # relationship for direct access
    idea_links = association_proxy('idealink_assocs', 'idea_link',
        creator=lambda idea_link: SubGraphIdeaLinkAssociation(idea_link=idea_link))

    __mapper_args__ = {
        'polymorphic_identity': 'explicit_sub_graph_view',
    }

    def copy(self, db=None):
        retval = IdeaGraphView.copy(self, db=db)
        # retval.ideas = self.ideas
        return retval

    def get_idea_links(self):
        # more efficient than the association_proxy
        return self.db.query(IdeaLink).join(
            SubGraphIdeaLinkAssociation
            ).filter_by(sub_graph_id=self.id).all()

    def get_idealink_assocs(self):
        return self.idealink_assocs

    def get_ideas(self):
        # more efficient than the association_proxy
        return self.db.query(Idea).join(
            SubGraphIdeaAssociation
            ).filter_by(sub_graph_id=self.id).all()

    def visit_ideas_depth_first(self, idea_visitor):
        # prefetch
        idea_assocs_by_idea_id = {
            link.idea_id: link for link in self.idea_assocs}
        children_links = defaultdict(list)
        with self.db.no_autoflush:
            idealink_assocs = self.get_idealink_assocs()
            for link_assoc in idealink_assocs:
                children_links[link_assoc.idea_link.source_id].append(link_assoc)
            for assocs in children_links.values():
                assocs.sort(key=lambda l: l.idea_link.order)
            root = self.discussion.root_idea
            root_assoc = idea_assocs_by_idea_id.get(root.base_id, None)
            root_id = root_assoc.idea_id if root_assoc else root.id
            result = self._visit_ideas_depth_first(
                root_id, idea_assocs_by_idea_id, children_links, idea_visitor,
                set(), 0, None, None)
            # special case for autocreated links
            for link_assoc in idealink_assocs:
                self.db.expunge(link_assoc)
        return result

    def _visit_ideas_depth_first(
            self, idea_id, idea_assocs_by_idea_id, children_links, idea_visitor,
            visited, level, prev_result, parent_link_assoc):
        result = None
        if idea_id in visited:
            # not necessary in a tree, but let's start to think graph.
            return False
        assoc = idea_assocs_by_idea_id.get(idea_id, None)
        if assoc:
            result = idea_visitor.visit_idea(
                idea_id, level, prev_result, (assoc, parent_link_assoc))
        visited.add(idea_id)
        child_results = []
        if result is not IdeaVisitor.CUT_VISIT:
            for link_assoc in children_links[idea_id]:
                child_id = link_assoc.idea_link.target_id
                r = self._visit_ideas_depth_first(
                    child_id, idea_assocs_by_idea_id, children_links,
                    idea_visitor, visited, level+1, result, link_assoc)
                if r:
                    child_results.append((child_id, r))
        return idea_visitor.end_visit(idea_id, level, result, child_results, (assoc, parent_link_assoc))

    @classmethod
    def extra_collections(cls):
        class GViewIdeaCollectionDefinition(AbstractCollectionDefinition):
            def __init__(self, cls):
                super(GViewIdeaCollectionDefinition, self).__init__(
                    cls, 'ideas', Idea)

            def decorate_query(self, query, owner_alias, last_alias,
                               parent_instance, ctx):
                return query.join(SubGraphIdeaAssociation, owner_alias)

            def contains(self, parent_instance, instance):
                return instance.db.query(
                    SubGraphIdeaAssociation).filter_by(
                        idea=instance,
                        sub_graph=parent_instance
                    ).count() > 0

        @collection_creation_side_effects.register(
            inst_ctx=Idea, ctx='ExplicitSubGraphView.ideas')
        def add_graph_idea_assoc(inst_ctx, ctx):
            yield InstanceContext(
                inst_ctx['in_subgraph_assoc'],
                SubGraphIdeaAssociation(
                    idea=inst_ctx._instance, sub_graph=ctx.parent_instance))

        @collection_creation_side_effects.register(
            inst_ctx=IdeaLink, ctx='ExplicitSubGraphView.ideas')
        def add_graph_idea_link_assoc(inst_ctx, ctx):
            yield InstanceContext(
                inst_ctx['in_subgraph_assoc'],
                SubGraphIdeaLinkAssociation(
                    idea_link=inst_ctx._instance,
                    sub_graph=ctx.parent_instance))

        class GViewIdeaLinkCollectionDefinition(AbstractCollectionDefinition):
            def __init__(self, cls):
                super(GViewIdeaLinkCollectionDefinition, self
                      ).__init__(cls, 'idea_links', IdeaLink)

            def decorate_query(self, query, owner_alias, last_alias,
                               parent_instance, ctx):
                return query.join(SubGraphIdeaLinkAssociation, owner_alias)

            def contains(self, parent_instance, instance):
                    return instance.db.query(
                        SubGraphIdeaLinkAssociation).filter_by(
                            idea_link=instance,
                            sub_graph=parent_instance
                        ).count() > 0

        @collection_creation_side_effects.register(
            inst_ctx=IdeaLink, ctx='ExplicitSubGraphView.idea_links')
        def add_graph_idea_link_assoc2(inst_ctx, ctx):
            yield InstanceContext(
                inst_ctx['in_subgraph_assoc'],
                SubGraphIdeaLinkAssociation(
                    idea_link=inst_ctx._instance, sub_graph=ctx.parent_instance))


        return (GViewIdeaCollectionDefinition(cls),
                GViewIdeaLinkCollectionDefinition(cls))

    crud_permissions = CrudPermissions(P_ADMIN_DISC)


SubGraphIdeaLinkAssociation.discussion = relationship(
        Discussion, viewonly=True, uselist=False,
        secondary=join(
            ExplicitSubGraphView.__table__,
            IdeaGraphView.__table__,
            ExplicitSubGraphView.id == IdeaGraphView.id),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})


class TableOfContents(IdeaGraphView):
    """
    Represents a Table of Ideas.

    A ToI in IdeaLoom is used to organize the core ideas of a discussion in a
    threaded hierarchy.
    """
    __tablename__ = "table_of_contents"

    id = Column(Integer, ForeignKey(
        'idea_graph_view.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'table_of_contents',
    }

    discussion = relationship(
        Discussion, backref=backref("table_of_contents", uselist=False))

    def get_discussion_id(self):
        return self.discussion.id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    def get_idea_links(self):
        return self.discussion.get_idea_links()

    def get_ideas(self):
        return self.discussion.ideas

    @as_native_str()
    def __repr__(self):
        r = super(TableOfContents, self).__repr__()
        return r[:-1] + self.discussion.slug + ">"


class Synthesis(ExplicitSubGraphView):
    """
    A synthesis of the discussion.  A selection of ideas, associated with
    comments, sent periodically to the discussion.

    A synthesis only has link's to ideas before publication (as it is edited)
    Once published, if freezes the links by copying tombstoned versions of
    each link in the discussion.
    """
    __tablename__ = "synthesis"

    id = Column(Integer, ForeignKey(
        'explicit_sub_graph_view.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    subject_id = Column(
        Integer(), ForeignKey(LangString.id))
    introduction_id = Column(
        Integer(), ForeignKey(LangString.id))
    conclusion_id = Column(
        Integer(), ForeignKey(LangString.id))
    subject = relationship(
        LangString,
        lazy="subquery", single_parent=True,
        primaryjoin=subject_id == LangString.id,
        backref=backref("synthesis_from_subject", lazy="dynamic"),
        cascade="all, delete-orphan")
    introduction = relationship(
        LangString,
        lazy="subquery", single_parent=True,
        primaryjoin=introduction_id == LangString.id,
        backref=backref("synthesis_from_introduction", lazy="dynamic"),
        cascade="all, delete-orphan")
    conclusion = relationship(
        LangString,
        lazy="subquery", single_parent=True,
        primaryjoin=conclusion_id == LangString.id,
        backref=backref("synthesis_from_conclusion", lazy="dynamic"),
        cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': 'synthesis',
    }

    def copy(self):
        retval = ExplicitSubGraphView.copy(self)
        retval.subject = self.subject.clone()
        retval.introduction = self.introduction.clone()
        retval.conclusion = self.conclusion.clone()
        return retval

    def publish(self):
        """ Publication is the end of a synthesis's lifecycle.
        It creates and returns a frozen copy of its state 
        using tombstones for ideas and links."""
        now = datetime.utcnow()
        frozen_synthesis = self.copy()
        self.db.add(frozen_synthesis)
        self.db.flush()

        # Copy tombstoned versions of all idea links and relevant ideas in the current synthesis
        links = Idea.get_all_idea_links(self.discussion_id)
        ideas = [idea for idea in self.ideas if not idea.is_tombstone]
        synthesis_idea_ids = {idea.id for idea in ideas}
        # Do not copy the root
        root = self.discussion.root_idea
        idea_copies = {root.id: root}
        # Also copies ideas between two synthesis ideas
        relevant_idea_ids = synthesis_idea_ids.copy()
        def add_ancestors_between(idea, path=None):
            if isinstance(idea, RootIdea):
                return
            path = path[:] if path else []
            if idea.id in synthesis_idea_ids:
                relevant_idea_ids.update({i.id for i in path})
            else:
                path.append(idea)
            for parent in idea.parents:
                add_ancestors_between(parent, path)
        for idea in ideas:
            for parent in idea.parents:
                add_ancestors_between(parent)
        for link in links:
            new_link = link.copy(tombstone=now)
            frozen_synthesis.idea_links.append(new_link)
            if link.source_id in relevant_idea_ids:
                if link.source_id not in idea_copies:
                    new_idea = link.source_ts.copy(tombstone=now)
                    idea_copies[link.source_id] = new_idea
                    if link.source_id in synthesis_idea_ids:
                        frozen_synthesis.ideas.append(new_idea)
                new_link.source_ts = idea_copies[link.source_id]
            if link.target_id in relevant_idea_ids:
                if link.target_id not in idea_copies:
                    new_idea = link.target_ts.copy(tombstone=now)
                    idea_copies[link.target_id] = new_idea
                    if link.target_id in synthesis_idea_ids:
                        frozen_synthesis.ideas.append(new_idea)
                new_link.target_ts = idea_copies[link.target_id]
        return frozen_synthesis

    def as_html(self, jinja_env, lang_prefs):
        v = SynthesisHtmlizationVisitor(self, jinja_env, lang_prefs)
        self.visit_ideas_depth_first(v)
        return v.as_html()

    def get_idea_links(self):
        if self.is_next_synthesis:
            return Idea.get_all_idea_links(self.discussion_id)
        else:
            return super(Synthesis, self).get_idea_links()

    def get_idealink_assocs(self):
        if self.is_next_synthesis:
            return [
                SubGraphIdeaLinkAssociation(
                    idea_link=link)
                for link in Idea.get_all_idea_links(self.discussion_id)]
        else:
            return super(Synthesis, self).get_idealink_assocs()

    @property
    def is_next_synthesis(self):
        return self.discussion.get_next_synthesis() == self

    def get_discussion_id(self):
        return self.discussion_id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    @as_native_str()
    def __repr__(self):
        r = super(Synthesis, self).__repr__()
        subject = self.subject.first_original().value if self.subject else ""
        return r[:-1] + subject + ">"

    crud_permissions = CrudPermissions(P_EDIT_SYNTHESIS)

LangString.setup_ownership_load_event(
    Synthesis, ['subject', 'introduction', 'conclusion'])

class SynthesisHtmlizationVisitor(HtmlizationVisitor):
    def __init__(self, graph_view, jinja_env, lang_prefs):
        super(SynthesisHtmlizationVisitor, self).__init__(
            jinja_env, lang_prefs, 'idea_in_synthesis.jinja2', 'synthesis.jinja2')
        self.graph_view = graph_view

    def as_html(self):
        synthesis = self.graph_view
        subject = synthesis.subject.best_lang(self.lang_prefs).value
        introduction = synthesis.introduction.best_lang(self.lang_prefs).value
        conclusion = synthesis.conclusion.best_lang(self.lang_prefs).value
        return self.page_template.render(
            synthesis=synthesis, content=self.result,
            introduction=introduction,
            subject=subject, conclusion=conclusion)
