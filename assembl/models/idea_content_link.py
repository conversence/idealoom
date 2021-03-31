"""Links between :py:class:`assembl.models.idea.Idea` and :py:class:`assembl.models.generic.Content`."""
from __future__ import print_function
import re
import quopri
import logging
import simplejson as json

from future.utils import as_native_str
from sqlalchemy.orm import (relationship, backref)
from sqlalchemy import (
    Column,
    Boolean,
    Integer,
    String,
    Float,
    Unicode,
    UnicodeText,
    ForeignKey,
    event,
)
from rdflib import URIRef
from sqla_rdfbridge.mapping import PatternIriClass

from . import DiscussionBoundBase, OriginMixin
from ..semantic import context_url
from ..semantic.virtuoso_mapping import QuadMapPatternS
from ..lib.sqla import CrudOperation
from ..lib.model_watcher import get_model_watcher
from ..lib.utils import get_global_base_url
from ..lib.clean_input import sanitize_html
from ..lib.sqla_types import URLString
from .discussion import Discussion
from .idea import Idea
from .generic import Content
from .post import Post
from .auth import AgentProfile
from ..auth import (
    CrudPermissions, P_READ, P_EDIT_IDEA, P_ASSOCIATE_EXTRACT,
    P_EDIT_EXTRACT, P_ADD_IDEA, P_ADD_EXTRACT)
from ..semantic.namespaces import (
    CATALYST, ASSEMBL, DCTERMS, OA, QUADNAMES, RDF, SIOC)


log = logging.getLogger(__name__)


class IdeaContentLink(DiscussionBoundBase, OriginMixin):
    """
    Abstract class representing a generic link between an idea and a Content
    (typically a Post)
    """
    __tablename__ = 'idea_content_link'
    # TODO: How to express the implied link as RDF? Remember not reified, unless extract.

    id = Column(Integer, primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    type = Column(String(60))

    # This is nullable, because in the case of extracts, the idea can be
    # attached later.
    idea_id = Column(Integer, ForeignKey(
            Idea.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    idea = relationship(
        Idea, active_history=True, backref=backref(
            "idea_content_links", passive_deletes=True))

    content_id = Column(Integer, ForeignKey(
        'content.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    content = relationship(Content, backref=backref(
        'idea_links_of_content', cascade="all, delete-orphan"))

    order = Column(Float, nullable=False, default=0.0)

    creator_id = Column(
        Integer,
        ForeignKey('agent_profile.id'),
        nullable=False,
        info={'rdf': QuadMapPatternS(None, SIOC.has_creator)}
    )

    creator = relationship(
        AgentProfile, foreign_keys=[creator_id], backref=backref(
            'idealinks_created', cascade="all")) # do not delete orphan

    extract_id = Column(Integer, ForeignKey(
        'extract.id', ondelete='CASCADE', onupdate='CASCADE'), index=True)

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:relatedToIdea',
        'polymorphic_on': type,
        'with_polymorphic': '*'
    }

    def get_discussion_id(self):
        content = self.content or Content.get(self.content_id)
        return content.get_discussion_id()

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return ((cls.content_id == Content.id),
                (Content.discussion_id == discussion_id))

    discussion = relationship(
        Discussion, viewonly=True, uselist=False, secondary=Content.__table__,
        backref="idea_content_links",
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    @classmethod
    def base_conditions(cls, alias=None, alias_maker=None):
        if alias_maker is None:
            idea_content_link = alias or cls
            idea = Idea
        else:
            idea_content_link = alias or alias_maker.alias_from_class(cls)
            idea = alias_maker.alias_from_relns(idea_content_link.idea)
        return ((idea_content_link.idea_id != None),
                (idea.tombstone_date == None))

    crud_permissions = CrudPermissions(
            P_ADD_IDEA, P_READ, P_EDIT_IDEA, P_EDIT_IDEA)


@event.listens_for(IdeaContentLink.idea, 'set', propagate=True, active_history=True)
def idea_content_link_idea_set_listener(target, value, oldvalue, initiator):
    """When an extract changes ideas, send the ideas on the socket."""
    # log.debug("idea_content_link_idea_set_listener for target: %s set to %s, was %s" % (target, value, oldvalue))
    if oldvalue is not None and oldvalue.id:
        with oldvalue.db.no_autoflush:
            oldvalue.send_to_changes()
            for ancestor in oldvalue.get_all_ancestors():
                ancestor.send_to_changes()
    if value is not None and value.id:
        with value.db.no_autoflush:
            value.send_to_changes()
            for ancestor in value.get_all_ancestors():
                ancestor.send_to_changes()


class IdeaContentPositiveLink(IdeaContentLink):
    """
    A normal link between an idea and a Content.
    Such links should be traversed.
    """

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        return [QuadMapPatternS(
            Content.iri_class().apply(cls.content_id),
            ASSEMBL.postLinkedToIdea,
            Idea.iri_class().apply(cls.idea_id),
            name=QUADNAMES.assembl_postLinkedToIdea,
            conditions=(cls.idea_id != None,))]

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:postLinkedToIdea_abstract',
    }


class IdeaContentWidgetLink(IdeaContentPositiveLink):
    """
    A link between an idea and a Content limited to a widget view.
    Such links should be traversed.
    """

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:postHiddenLinkedToIdea',
    }

Idea.widget_owned_contents = relationship(IdeaContentWidgetLink)
Content.widget_idea_links = relationship(
    IdeaContentWidgetLink, cascade="all, delete-orphan")


class IdeaRelatedPostLink(IdeaContentPositiveLink):
    """
    A post that is relevant, as a whole, to an idea, without having a specific
    extract harvested.
    """

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        return [QuadMapPatternS(
            Content.iri_class().apply(cls.content_id),
            ASSEMBL.postRelatedToIdea,
            Idea.iri_class().apply(cls.idea_id),
            name=QUADNAMES.assembl_postRelatedToIdea,
            conditions=(cls.idea_id != None,))]

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:postLinkedToIdea',
    }


class IdeaExtractLink(IdeaRelatedPostLink):
    """
    A post that is relevant, to an idea through a harvested extract
    """

    extract = relationship("Extract", backref=backref(
        "idea_content_links", passive_deletes=True))

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        return [QuadMapPatternS(
            Content.iri_class().apply(cls.content_id),
            ASSEMBL.postExtractRelatedToIdea,
            Idea.iri_class().apply(cls.idea_id),
            name=QUADNAMES.assembl_postRelatedToIdea,
            conditions=(cls.idea_id != None,))]

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:postExtractRelatedToIdea',
    }

    crud_permissions = CrudPermissions(
            P_ASSOCIATE_EXTRACT, P_READ, P_ASSOCIATE_EXTRACT, P_ASSOCIATE_EXTRACT)

class Extract(DiscussionBoundBase, OriginMixin):
    """
    An extracted part of a Content. A quotation to be referenced by an `Idea`.
    """
    __tablename__ = 'extract'
    __external_typename = "Excerpt"
    rdf_class = CATALYST.Excerpt
    # Extract ID represents both the oa:Annotation and the oa:SpecificResource
    # TODO: This iri is not yet dereferencable.
    specific_resource_iri = PatternIriClass(
        QUADNAMES.oa_specific_resource_iri,
        get_global_base_url() + '/data/SpecificResource/%d', None,
        ('id', Integer, False))

    id = Column(Integer, primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})

    graph_iri_class = PatternIriClass(
        QUADNAMES.ExcerptGraph_iri,
        get_global_base_url() + '/data/ExcerptGraph/%d',
        None,
        ('id', Integer, False))

    annotation_text = Column(UnicodeText)

    # info={'rdf': QuadMapPatternS(None, OA.hasBody)})
    # TODO: Maybe drop this column and use the content???
    discussion_id = Column(Integer, ForeignKey(
        'discussion.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True,
        info={'rdf': QuadMapPatternS(None, CATALYST.relevantToConversation)})
    discussion = relationship(
        Discussion, backref=backref('extracts', cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    content_id = Column(Integer, ForeignKey(
        'content.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    content = relationship(Content, backref=backref(
        'extracts_of_content', cascade="all, delete-orphan"))

    creator_id = Column(
        Integer,
        ForeignKey('agent_profile.id'),
        nullable=False,
        info={'rdf': QuadMapPatternS(None, SIOC.has_creator)}
    )
    creator = relationship(
        AgentProfile, foreign_keys=[creator_id], backref=backref(
            'extracts_created', cascade="all")) # do not delete orphan

    important = Column(Boolean, server_default='0')
    external_url = Column(URLString)

    attributed_to_id = Column(
        Integer, ForeignKey(AgentProfile.id,
                            ondelete='SET NULL', onupdate='CASCADE'))

    def local_uri_as_graph(self):
        return 'local:ExcerptGraph/%d' % (self.id,)

    def local_uri_as_resource(self):
        return 'local:SpecificResource/%d' % (self.id,)

    def extract_graph_name(self):
        from pyramid.threadlocal import get_current_registry
        reg = get_current_registry()
        host = reg.settings['public_hostname']
        return URIRef('http://%s/data/ExcerptGraph/%d' % (host, self.id))

    def fragements_as_web_annotatation(self):
        return sum((tfi.as_web_annotation()
                    for tfi in  self.selectors), [])

    def extract_graph_json(self):
        return [{
            "@graph": [
                {
                    "expressesIdea": Idea.uri_generic(icl.idea_id),
                    "@id": self.local_uri_as_resource()
                }
            ],
            "@id": self.local_uri_as_graph()
        } for icl in self.idea_content_links]

    def first_linked_idea(self):
        if self.idea_content_links:
            return self.idea_content_links[0].idea

    def extract_graph_json_wrap(self):
        return {
            "@context": [context_url, {'local': get_global_base_url()}],
            "@graph": self.extract_graph_json()
        }

    def extract_graph_json_wrap_flat(self):
        return json.dumps(self.extract_graph_json_wrap())

    def extract_graph_iri(self):
        return getattr(QUADNAMES, 'extract_%d_iri' % self.id)

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        return [
            QuadMapPatternS(
                None, OA.hasBody,
                cls.graph_iri_class.apply(cls.id),
                name=QUADNAMES.oa_hasBody,
                conditions=((cls.idea_id != None),
                            (Idea.tombstone_date == None))),
            QuadMapPatternS(
                #Content.iri_class().apply(cls.content_id),
                cls.specific_resource_iri.apply(cls.id),
                # It would be better to use CATALYST.expressesIdea,
                # but Virtuoso hates the redundancy.
                ASSEMBL.resourceExpressesIdea,
                Idea.iri_class().apply(cls.idea_id),
                name=QUADNAMES.assembl_postExtractRelatedToIdea,
                conditions=((cls.idea_id != None),
                            (Idea.tombstone_date == None)
                   # and it's a post extract... treat webpages separately.
                )),
            QuadMapPatternS(
                None, OA.hasTarget, cls.specific_resource_iri.apply(cls.id),
                name=QUADNAMES.oa_hasTarget),
            QuadMapPatternS(
                cls.specific_resource_iri.apply(cls.id),
                RDF.type, OA.SpecificResource,
                name=QUADNAMES.oa_SpecificResource_type),
            QuadMapPatternS(
                cls.specific_resource_iri.apply(cls.id),
                ASSEMBL.in_conversation,
                Discussion.iri_class().apply(cls.discussion_id),
                name=QUADNAMES.oa_SpecificResource_in_conversation),
            QuadMapPatternS(
                cls.specific_resource_iri.apply(cls.id), OA.hasSource,
                Content.iri_class().apply(cls.content_id),
                name=QUADNAMES.oa_hasSource),
            # TODO: Paths
            # QuadMapPatternS(
            #     AgentProfile.iri_class().apply((cls.content_id, Post.creator_id)),
            #     DCTERMS.contributor,
            #     Idea.iri_class().apply(cls.idea_id),
            #     name=QUADNAMES.assembl_idea_contributor,
            #     conditions=(cls.idea_id != None,)),
            ]

    attributed_to = relationship(
        AgentProfile, foreign_keys=[attributed_to_id],
        backref='extracts_attributed')

    extract_source = relationship(Content, backref="extracts")
    # extract_ideas = relationship(
    #     Idea, secondary="idea_content_link",
    #     backref="extracts")

    @property
    def target(self):
        retval = {
                '@type': self.content.external_typename()
                }
        if isinstance(self.content, Post):
            retval['@id'] = Post.uri_generic(self.content.id)
        elif self.content.type == 'webpage':
            retval['url'] = self.content.url
            subject = self.content.subject
            if subject:
                retval['title'] = subject.first_original().value
        return retval

    @as_native_str()
    def __repr__(self):
        r = super(Extract, self).__repr__()
        body = self.quote or ""
        return r[:-1] + body[:20] + ">"

    def populate_from_context(self, context):
        if not(self.creator or self.creator_id):
            self.creator_id = context.get_user_id()
        super(Extract, self).populate_from_context(context)

    def get_target(self):
        return self.content

    def get_post(self):
        if isinstance(self.content, Post):
            return self.content

    def infer_text_fragment(self):
        return self._infer_text_fragment_inner(
            self.content.get_title(), self.content.get_body(),
            self.get_post().id)

    @property
    def quote(self):
        return ' '.join((tf.body for tf in self.selectors if getattr(tf, 'body', None)))

    def _infer_text_fragment_inner(self, title, body, post_id):
        # dead code? If not needs to be refactored with langstrings
        # and moved within text_fragment, maybe?
        body = sanitize_html(body, [])
        quote = self.quote.replace("\r", "")
        try:
            # for historical reasons
            quote = quopri.decodestring(quote)
        except:
            pass
        quote = sanitize_html(quote, [])
        if quote != self.body:
            self.body = quote
        quote = quote.replace("\n", "")
        start = body.find(quote)
        lookin = 'message-body'
        if start < 0:
            xpath = "//div[@id='%s']/div[class='post_title']" % (post_id)
            start = title.find(quote)
            if start < 0:
                return None
            lookin = 'message-subject'
        xpath = "//div[@id='message-%s']//div[@class='%s']" % (
            Post.uri_generic(post_id), lookin)
        tfi = self.db.query(TextFragmentIdentifier).filter_by(
            extract=self).first()
        if not tfi:
            tfi = TextFragmentIdentifier(extract=self)
        tfi.xpath_start = tfi.xpath_end = xpath
        tfi.offset_start = start
        tfi.offset_end = start+len(quote)
        return tfi

    def send_to_changes(self, connection=None, operation=CrudOperation.UPDATE,
                        discussion_id=None, view_def="changes"):
        """invoke the modelWatcher on creation"""
        super(Extract, self).send_to_changes(
            connection, operation, discussion_id, view_def)
        watcher = get_model_watcher()
        if operation == CrudOperation.UPDATE:
            watcher.processExtractModified(self.id, 0)  # no versions yet.
        elif operation == CrudOperation.DELETE:
            watcher.processExtractDeleted(self.id)
        elif operation == CrudOperation.CREATE:
            watcher.processExtractCreated(self.id)

    def get_discussion_id(self):
        return self.discussion_id or self.discussion.id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    @classmethod
    def base_conditions(cls, alias=None, alias_maker=None):
        # Allow idea-less extracts
        return ()

    @classmethod
    def restrict_to_owners_condition(cls, query, user_id, alias=None, alias_maker=None):
        if not alias:
            alias = alias_maker.alias_from_class(cls) if alias_maker else cls
        return (query, alias.creator_id == user_id)

    crud_permissions = CrudPermissions(
            P_ADD_EXTRACT, P_READ, P_EDIT_EXTRACT, P_EDIT_EXTRACT)


class IdeaContentNegativeLink(IdeaContentLink):
    """
    A negative link between an idea and a Content.  Such links mean that
    a transitive context should be considered broken.  Used for thread breaking
    """

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:postDelinkedToIdea_abstract',
    }


class IdeaThreadContextBreakLink(IdeaContentNegativeLink):
    """
    Used for a Post the inherits an Idea from an ancester in the thread.
    It indicates that from this point on in the thread, this idea is no longer
    discussed.
    """

    __mapper_args__ = {
        'polymorphic_identity': 'assembl:postDelinkedToIdea',
    }


class AnnotationSelector(DiscussionBoundBase):
    __tablename__ = 'annotation_selector'
    id = Column(Integer, primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    extract_id = Column(Integer, ForeignKey(
        Extract.id, ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(60))
    refines_id = Column(Integer, ForeignKey(id, ondelete="CASCADE"))
    body = Column(UnicodeText)

    __mapper_args__ = {
        'polymorphic_identity': 'AbstractSelector',
        'polymorphic_on': type,
        'with_polymorphic': '*'
    }

    extract = relationship(Extract, backref=backref(
        'selectors', cascade="all, delete-orphan"))

    refined_by = relationship(
        "AnnotationSelector",
        backref=backref('refines', remote_side=[id]),
        cascade="all, delete-orphan")

    def get_discussion_id(self):
        extract = self.extract or Extract.get(self.extract_id)
        return extract.get_discussion_id()

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return ((cls.extract_id == Extract.id),
                (Extract.discussion_id == discussion_id))

    def find_best_sibling(self, parent, siblings):
        # self is a non-persistent object created from json,
        # and a corresponding persistent object may already exist in parent
        for sibling in siblings:
            if sibling.__class__ == self.__class__:
                return sibling

    discussion = relationship(
        Discussion, viewonly=True, uselist=False, secondary=Extract.__table__,
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    crud_permissions = CrudPermissions(
            P_ADD_EXTRACT, P_READ, P_EDIT_EXTRACT, P_EDIT_EXTRACT)


class TextQuoteSelector(AnnotationSelector):
    __tablename__ = 'text_quote_selector'
    id = Column(Integer,
                ForeignKey(
                    AnnotationSelector.id,
                    ondelete='CASCADE',
                    onupdate='CASCADE'),
                primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    prefix = Column(UnicodeText)
    suffix = Column(UnicodeText)

    __mapper_args__ = {
        'polymorphic_identity': 'TextQuoteSelector'
    }


class TextPositionSelector(AnnotationSelector):
    __tablename__ = 'text_position_selector'
    id = Column(Integer,
                ForeignKey(
                    AnnotationSelector.id,
                    ondelete='CASCADE',
                    onupdate='CASCADE'),
                primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    start = Column(Integer)
    end = Column(Integer)

    __mapper_args__ = {
        'polymorphic_identity': 'TextPositionSelector'
    }


class FragmentSelector(AnnotationSelector):
    __tablename__ = 'fragment_selector'
    id = Column(Integer,
                ForeignKey(
                    AnnotationSelector.id,
                    ondelete='CASCADE',
                    onupdate='CASCADE'),
                primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    value = Column(Unicode)

    __mapper_args__ = {
        'polymorphic_identity': 'FragmentSelector'
    }


class TextFragmentIdentifier(AnnotationSelector):
    __tablename__ = 'text_fragment_identifier'
    __external_typename = "RangeSelector"
    rdf_class = OA.RangeSelector

    id = Column(Integer,
                ForeignKey(
                    AnnotationSelector.id,
                    ondelete='CASCADE',
                    onupdate='CASCADE'),
                primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    xpath_start = Column(String)
    offset_start = Column(Integer)
    xpath_end = Column(String)
    offset_end = Column(Integer)

    __mapper_args__ = {
        'polymorphic_identity': 'AnnotatorRange'
    }

    @classmethod
    def generate_post_xpath(cls, post, original_xpath='', prefix=''):
        parts = original_xpath.split("/")
        suffix = ''
        for (n, p) in enumerate(parts):
            if ':SPost' in p:
                parts = parts[n+2:]
                if parts:
                    suffix = '/' + '/'.join(parts)
                break
        return "%s//div[@id='message-body-local:SPost/%d']%s" % (
            prefix, post.id, suffix)

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        return [
            QuadMapPatternS(
                Extract.specific_resource_iri.apply(cls.extract_id),
                OA.hasSelector,
                cls.iri_class().apply(cls.id),
                name=QUADNAMES.oa_hasSelector,
                conditions=(cls.extract_id != None,)),
            QuadMapPatternS(
                None, DCTERMS.conformsTo,
                URIRef("http://tools.ietf.org/rfc/rfc3023")),  # XPointer
            # TODO: add rdf:value for the XPointer. May have to construct within Virtuoso.
            # Optional: Add a OA.exact with the Extract.body. (WHY is the body in the extract?)
            ]

    xpath_re = re.compile(
        r'xpointer\(start-point\(string-range\(([^,]+),([^,]+),([^,]+)\)\)'
        r'/range-to\(string-range\(([^,]+),([^,]+),([^,]+)\)\)\)')

    @property
    def xpath_start_calc(self):
        if isinstance(self.extract.extract_source, Post):
            return self.generate_post_xpath(
                self.extract.extract_source, self.xpath_start)
        return self.xpath_start

    @property
    def xpath_end_calc(self):
        if isinstance(self.extract.extract_source, Post):
            return self.generate_post_xpath(
                self.extract.extract_source, self.xpath_start)
        return self.xpath_end

    def as_xpointer(self):
        return ("xpointer(start-point(string-range(%s,'',%d))/"
                "range-to(string-range(%s,'',%d)))" % (
                self.xpath_start_calc, self.offset_start,
                self.xpath_end_calc, self.offset_end))

    def __json__(self):
        return {"start": self.xpath_start, "startOffset": self.offset_start,
                "end": self.xpath_end, "endOffset": self.offset_end}

    def as_web_annotation(self):
        all = [
            {"type": "TextQuoteSelector", "exact": self.body},
            {
                "conformsTo": "http://tools.ietf.org/rfc/rfc3023",
                "type": "FragmentSelector",
                "value": self.as_xpointer(),
            },
        ]

        if self.xpath_start == self.xpath_end:
            all.append({
                "id": self.uri(),
                "type": "XPathSelector",
                "value": self.xpath_start,
                "refinedBy": {
                    "type": "TextPositionSelector",
                    "start": self.offset_start,
                    "end": self.offset_end
                }
            })
        else:
            all.append({
                "id": self.uri(),
                "type": "RangeSelector",
                "startSelector": {
                    "type": "XPathSelector",
                    "value": self.xpath_start,
                    "refinedBy": {
                        "type": "TextPositionSelector",
                        "start": self.offset_start
                    }
                },
                "endSelector": {
                    "type": "XPathSelector",
                    "value": self.xpath_end,
                    "refinedBy": {
                        "type": "TextPositionSelector",
                        "end": self.offset_end
                    }
                }
            })
        return all

    @classmethod
    def from_xpointer(cls, extract_id, xpointer):
        m = cls.xpath_re.match(xpointer)
        if m:
            try:
                (xpath_start, start_text, offset_start,
                    xpath_end, end_text, offset_end) = m.groups()
                offset_start = int(offset_start)
                offset_end = int(offset_end)
                xpath_start = xpath_start.strip()
                assert xpath_start[0] in "\"'"
                xpath_start = xpath_start.strip(xpath_start[0])
                xpath_end = xpath_end.strip()
                assert xpath_end[0] in "\"'"
                xpath_end = xpath_end.strip(xpath_end[0])
                return TextFragmentIdentifier(
                    extract_id=extract_id,
                    xpath_start=xpath_start, offset_start=offset_start,
                    xpath_end=xpath_end, offset_end=offset_end)
            except:
                pass
        return None


Idea.extracts = relationship(
    Extract, secondary=IdeaContentLink.__table__)
