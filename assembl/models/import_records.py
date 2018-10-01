import logging

from sqlalchemy import (
    Column, ForeignKey, Integer, DateTime, Table,
    UniqueConstraint, Unicode, String, Index)
from sqlalchemy.orm import relationship
from future.utils import string_types
import simplejson as json
from rdflib_jsonld.context import Context

from . import DiscussionBoundBase
from .uriref import URIRefDb
from .generic import ContentSource
from ..lib.sqla import get_named_class, get_named_object
from ..lib.generic_pointer import (
    UniversalTableRefColType, generic_relationship)
from ..lib.utils import get_global_base_url
from ..semantic import jsonld_context


log = logging.getLogger(__name__)


class IdeaSource(ContentSource):
    __tablename__ = 'idea_source'
    id = Column(Integer, ForeignKey(ContentSource.id), primary_key=True)
    uri_id = Column(Integer, ForeignKey(URIRefDb.id), nullable=False, unique=True)

    source_uri_id = relationship(URIRefDb)

    __mapper_args__ = {
        'polymorphic_identity': 'abstract_idea_source',
    }

    source_uri_ = relationship(URIRefDb)

    @property
    def source_uri(self):
        return self.source_uri_.val

    @source_uri.setter
    def source_uri(self, val):
        self.source_uri_ = URIRefDb.get_or_create(val, self.db)

    def external_id_to_uri(self, external_id):
        if '//' in external_id:
            return external_id
        return self.source_uri + external_id

    def uri_to_external_id(self, uri):
        base = self.source_uri
        if uri.startswith(base):
            uri = uri[len(base):]
        return uri

    def find_record(self, uri):
        external_id = self.uri_to_external_id(uri)
        return self.db.query(ImportRecord).filter_by(
            source_id=self.id,
            external_id=external_id).first()

    def generate_message_id(self, source_post_id):
        return source_post_id

    def get_existing(self, identifier):
        record = self.db.query(ImportRecord).filter_by(
            source=self, external_id=identifier).first()
        if record:
            return record.target

    def associate(self, target_id, instance, data=None):
        record = self.db.query(ImportRecord).filter_by(
            source=self, target=instance).first()
        if record:
            record.update(data)
        else:
            self.db.add(ImportRecord(
                source=self, target=instance, external_id=target_id))


class ImportRecord(DiscussionBoundBase):
    __tablename__ = 'import_record'
    __table_args__ = (
        UniqueConstraint('source_id', 'external_id'),
        UniqueConstraint('source_id', 'target_id', 'target_table'),
        Index('idx_import_record_target', 'target_id', 'target_table'))

    id = Column(Integer, primary_key=True)
    external_id = Column(Unicode, nullable=False)
    source_id = Column(Integer, ForeignKey(IdeaSource.id, ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    last_import_time = Column(DateTime, server_default="now()")
    target_id = Column(Integer, nullable=False)
    target_table = Column(UniversalTableRefColType(), nullable=False)
    # data = Column(Text)  # Do we need the last import data? probably

    target = generic_relationship(target_table, target_id)
    source = relationship(IdeaSource, backref="import_records")

    def get_discussion_id(self):
        return self.source.discussion_id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        if alias_maker is None:
            import_record = cls
            source = IdeaSource
        else:
            import_record = alias_maker.alias_from_class(cls)
            source = alias_maker.alias_from_relns(import_record.source)
        return ((import_record.source_id == source.id),
                (source.discussion_id == discussion_id))

    @property
    def external_uri(self):
        return self.source.external_id_to_uri(self.external_id)

    @external_uri.setter
    def external_uri(self, val):
        self.external_id = self.source.uri_to_external_id(val)

    def update(self, data):
        pass


class CatalystIdeaSource(IdeaSource):

    __mapper_args__ = {
        'polymorphic_identity': 'catalyst',
    }

    subProperties = {
        "argumentAdressesCriterion": "source_id",
        "argument_arguing": "source_idea",
        "criterionOpposes": "source_idea",
        "criterionSupports": "source_idea",
        "response_issue": "target_idea",
        "questioned_by_issue": "target_idea",
        "response_position": "source_idea",
        "applicable_issue": "source_idea",

        "argument_opposing": "source_idea",
        "argument_supporting": "source_idea",
        "idea_argued": "target_idea",
        "position_supported": "target_idea",
        "position_argued": "target_idea",
        "position_opposed": "target_idea",
        "suggesting_issue": "source_idea",
        "issue_suggested": "source_idea",
    }

    deprecatedClassesAndProps = {
        "argument_supporting": "argument_arguing",
        "argument_opposing": "argument_arguing",
        "idea_argued": "target_idea",
        "position_supported": "target_idea",
        "position_argued": "target_idea",
        "position_opposed": "target_idea",
        "ArgumentSupportsPosition": "ArgumentSupportsIdea",
        "ArgumentOpposesPosition": "ArgumentOpposesIdea",
        "SuggestsIssue": "IssueAppliesTo",
        "suggesting_issue": "applicable_issue",
        "issue_suggested": "applicable_issue",
    }

    equivalents = {
        'CIdea': 'GenericIdeaNode',
        'Argument': 'GenericIdeaNode',
        'Criterion': 'GenericIdeaNode',
        'Decision': 'GenericIdeaNode',
        'Issue': 'GenericIdeaNode',
        'Position': 'GenericIdeaNode',
        'Question': 'GenericIdeaNode',
        'Reference': 'GenericIdeaNode',
        # 'GenericIdea': 'Idea', Should apply to nodes only
        'AbstractionStatement': 'DirectedIdeaRelation',
        'ArgumentApplication': 'DirectedIdeaRelation',
        'ArgumentOpposesIdea': 'DirectedIdeaRelation',
        'ArgumentSupportsIdea': 'DirectedIdeaRelation',
        'CausalInference': 'DirectedIdeaRelation',
        'CausalStatement': 'DirectedIdeaRelation',
        'ComparisonStatement': 'DirectedIdeaRelation',
        'ContextOfExpression': 'DirectedIdeaRelation',
        'CriterionApplication': 'DirectedIdeaRelation',
        'DistinctionStatement': 'DirectedIdeaRelation',
        'EquivalenceStatement': 'DirectedIdeaRelation',
        'IdeaRelation': 'DirectedIdeaRelation',
        'InclusionRelation': 'DirectedIdeaRelation',
        'IssueAppliesTo': 'DirectedIdeaRelation',
        'IssueQuestions': 'DirectedIdeaRelation',
        'MutualRelevanceStatement': 'DirectedIdeaRelation',
        'PositionRespondsToIssue': 'DirectedIdeaRelation',
        'WholePartRelation': 'DirectedIdeaRelation',
        'IdeaMap': 'ExplicitSubGraphView',
        # 'Map': 'ExplicitSubGraphView', actually IdeaGraphView
        'OrderingVote': 'vote:OrderingVote',
        'Vote': None,
        # 'LickertVote': 'LickertVote', actually LickertIdeaVote
        # 'Post': 'ImportedPost', =Post?
        # 'SPost': 'ImportedPost', actually Content
        'PostSource': 'ContentSource',  # or actually PostSource?
        'Person': 'AgentProfile',
        'Annotate': None,
        'Annotation': None,
        'ApprovalChange': None,
        'Community': None,
        'Conversation': None,
        'Create': None,
        'Delete': None,
        'ExcerptTarget': None,
        'Forum': None,
        'Graph': None,
        'Ideas': None,
        'Item': None,
        'Move': None,
        'ObjectSnapshot': None,
        'Organization': None,
        'ParticipantGroup': None,
        'Participants': None,
        'PerUserStateChange': None,
        'PerUserUpdate': None,
        'SItem': None,
        'SSite': None,
        'Site': None,
        'Space': None,
        'SpecificResource': None,
        'StateChange': None,
        'Statement': None,
        'TextPositionSelector': None,
        'TextQuoteSelector': None,
        'Thread': None,
        'Tombstone': None,
        'Update': None,
        'UserAccount': None,
        'Usergroup': None,
    }

    def class_from_json(self, json):
        typename = json.get('@type')
        # Look for aliased classes.
        # Maybe look in the context instead?
        typename = self.equivalents.get(typename, typename)
        if typename:
            cls = get_named_class(typename)
            # TODO: Adjust for subclasses according to json record
            # cls = cls.get_jsonld_subclass(json)
            return cls

    def get_existing(self, identifier):
        instance = self.instance_by_id.get(identifier, None)
        if instance is not None:
            return instance
        if identifier.startswith('local:'):
            identifier = self.remote_context.expand(identifier)
        if identifier.startswith(self.global_url):
            identifier = "local:" + identifier[len(self.global_url):]
        if identifier.startswith('local:'):  # Now guaranteed to be internal
            instance = get_named_object(identifier)
            if instance:
                return instance
        else:
            record = self.import_records_by_id.get(identifier, None)
            if record is not None:
                return record.target

    def get_record(self, identifier):
        record = self.json_by_id.get(identifier, None)
        if record:
            record['in_conversation'] = self.discussion.uri()
            from .idea import Idea, IdeaLink
            from .votes import AbstractIdeaVote, AbstractVoteSpecification
            from .widgets import MultiCriterionVotingWidget
            cls = self.class_from_json(record)
            if cls:
                if issubclass(cls, IdeaLink):
                    # compensate for old bug
                    if "questioned_by_issue" in record and 'response_issue' in record:
                        issue = record.pop('response_issue')
                        record['applicable_issue'] = issue
                    for prop in list(record.keys()):
                        alias = self.subProperties.get(prop, None)
                        if alias:
                            record[alias] = record[prop]
                if issubclass(cls, (Idea, IdeaLink)):
                    type = record["@type"]
                    record['rdf_type'] = \
                        self.deprecatedClassesAndProps.get(type, type)
                    record['@type'] = cls.external_typename()
                if issubclass(cls, (AbstractIdeaVote, AbstractVoteSpecification)):
                    if 'widget' not in record:
                        if 'dummy_vote_widget' not in self.instance_by_id:
                            self.instance_by_id['dummy_vote_widget'] = \
                                MultiCriterionVotingWidget(discussion=self.discussion)
                        record['widget'] = 'dummy_vote_widget'
            print("****** get_record: ", identifier, record)
            return record

    def associate(self, target_id, instance, data=None):
        if target_id in self.instance_by_id:
            if self.instance_by_id[target_id] != instance:
                print("**** conflicting association:", target_id, self.instance_by_id[target_id], instance)
        self.instance_by_id[target_id] = instance
        record = self.import_records_by_id.get(target_id, None)
        if record:
            record.update(data)
        else:
            record = ImportRecord(
                source=self, target=instance, external_id=target_id)
            # self.db.add(record)
            self.import_records_by_id[target_id] = record

    def read(self, jsonld, discussion, admin_user_id, base=None):
        from .idea import Idea, IdeaLink
        self.local_context = jsonld_context()
        self.instance_by_id = {}
        self.json_by_id = {}
        self.global_url = get_global_base_url() + "/data/"
        # preload
        self.import_records_by_id = {r.external_id: r for r in self.import_records}
        if isinstance(jsonld, string_types):
            jsonld = json.loads(jsonld)
        c = jsonld['@context']
        self.remote_context = Context(c)
        # Avoid loading the main context.
        # if c == context_url:
        #     c = local_context_loc
        # elif context_url in c:
        #     c.remove(context_url)
        #     c.append(local_context_loc)
        # c = Context(c, base=base)
        # site_iri = None

        def find_objects(j):
            if isinstance(jsonld, string_types):
                return
            if isinstance(j, list):
                for x in j:
                    find_objects(x)
            if isinstance(j, dict):
                jid = j.get('@id', None)
                if jid:
                    self.json_by_id[jid] = j
                for x in j.values():
                    find_objects(x)
        find_objects(jsonld)
        # for record in self.json_by_id.values():
        #     if record.get('@type', None) == 'Site':
        #         site_iri = record['@id']
        #         break
        # site_iri = site_iri or base
        # assert site_iri is not None
        ctx = discussion.get_instance_context(user_id=admin_user_id)
        for key in self.json_by_id:
            if key in self.instance_by_id:
                continue
            record = self.get_record(key)
            cls = self.class_from_json(record)
            if not cls:
                log.error("missing cls for : " + record['@type'])
                continue
            instance_ctx = cls.create_from_json(
                record, ctx, parse_def_name='cif_reverse',
                object_importer=self)
            if instance_ctx:
                self.db.add(instance_ctx._instance)
            self.db.flush()
        # add links from discussion root to roots of idea subtrees
        base_ids = self.db.query(Idea.id).outerjoin(IdeaLink, IdeaLink.target_id == Idea.id).filter(
            IdeaLink.id == None, Idea.discussion_id==self.discussion_id).all()
        root_id = self.discussion.root_idea.id
        base_ids.remove((root_id,))
        for (id,) in base_ids:
            self.db.add(IdeaLink(source_id=root_id, target_id=id))
        self.db.flush()
        # Maybe tombstone objects that had import records and were not reimported or referred to?
