from abc import abstractmethod
import logging
from collections import defaultdict
from itertools import groupby
try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

from sqlalchemy import (
    Column, ForeignKey, Integer, DateTime, Table,
    UniqueConstraint, Unicode, String, Index)
from sqlalchemy.orm import relationship, reconstructor
from future.utils import string_types
import simplejson as json
from rdflib_jsonld.context import Context
from jsonpath_ng.ext import parse
import requests
from requests.cookies import RequestsCookieJar as CookieJar

from . import DiscussionBoundBase
from .uriref import URIRefDb
from ..lib.sqla_types import URLString
from .generic import ContentSource
from .auth import AgentProfile
from .publication_states import PublicationState
from ..lib.sqla import get_named_class, get_named_object, PromiseObjectImporter
from ..lib.generic_pointer import (
    UniversalTableRefColType, generic_relationship)
from ..lib.utils import get_global_base_url
from ..semantic import jsonld_context


log = logging.getLogger(__name__)


class IdeaSource(ContentSource, PromiseObjectImporter):
    __tablename__ = 'idea_source'
    id = Column(Integer, ForeignKey(ContentSource.id), primary_key=True)
    source_uri = Column(URLString, nullable=False)
    data_filter = Column(String)  # jsonpath-based, assuming json data
    target_state_id = Column(Integer, ForeignKey(
        PublicationState.id, ondelete="SET NULL", onupdate="CASCADE"))

    target_state = relationship(PublicationState)

    __mapper_args__ = {
        'polymorphic_identity': 'abstract_idea_source',
    }

    def __init__(self, *args, **kwargs):
        super(IdeaSource, self).__init__(*args, **kwargs)
        self.init_on_load()

    @reconstructor
    def init_on_load(self):
        PromiseObjectImporter.__init__(self)
        self.parsed_data_filter = parse(self.data_filter) if self.data_filter else None
        self.global_url = get_global_base_url() + "/data/"
        

    def load_previous_records(self):
        records = list(self.import_records)
        records.sort(key=lambda r: r.target_table)
        for (table_id, recs) in groupby(records, lambda r: r.target_table):
            recs = list(recs)
            cls = ImportRecord.target.property.type_mapper.value_to_class(table_id, None)
            instances = self.db.query(cls).filter(cls.id.in_([r.target_id for r in recs]))
            instance_by_id = {i.id: i for i in instances}
            for r in recs:
                eid = self.normalize_id(r.external_id)
                self.instance_by_id[eid] = instance_by_id[r.target_id]

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

    def id_from_data(self, data):
        if isinstance(data, dict):
            data = data.get('@id', None)
        if isinstance(data, string_types):
            return data
        # TODO: array of ids...

    def normalize_id(self, id):
        id = self.id_from_data(id)
        if not id:
            return
        id = super(IdeaSource, self).normalize_id(id)
        if id.startswith('local:'):
            return self.source_uri + id[6:]
        return id

    def get_object(self, id, default=None):
        id = self.normalize_id(id)
        instance = super(IdeaSource, self).get_object(id, default)
        if instance:
            return instance
        record = self.db.query(ImportRecord).filter_by(
            source=self, external_id=id).first()
        if record:
            return record.target

    def __setitem__(self, id, instance):
        exists = id in self.instance_by_id
        super(IdeaSource, self).__setitem__(id, instance)
        if exists:
            return
        self.db.add(ImportRecord(
            source=self, target=instance, external_id=id))

    @property
    def target_state_label(self):
        if self.target_state:
            return self.target_state.label

    @target_state_label.setter
    def target_state_label(self, label):
        if not label:
            self.target_state = None
            return
        assert self.discussion.idea_publication_flow
        target_state = self.discussion.idea_publication_flow.state_by_label(label)
        assert target_state
        self.target_state = target_state

    @abstractmethod
    def class_from_data(self, data):
        return Idea

    def process_data(self, data):
        return data

    @abstractmethod
    def read(self, admin_user_id, base=None):
        self.load_previous_records()

    def read_data_gen(self, data_gen, admin_user_id):
        # preload
        waiting_for = defaultdict(list)
        #
        ctx = self.discussion.get_instance_context(user_id=admin_user_id)
        def resolve(id, instance):
            pass

        for data in data_gen:
            ext_id = self.id_from_data(data)
            if not ext_id:
                continue
            if ext_id in self:
                continue
            cls = self.class_from_data(data)
            if not cls:
                self[ext_id] = None
                continue
            if self.parsed_data_filter and not self.parsed_data_filter.find(data):
                self[ext_id] = None
                continue
            pdata = self.process_data(data)
            if not pdata:
                continue
            # Don't we need a CollectionCtx?
            instance_ctx = cls.create_from_json(
                pdata, ctx, object_importer=self, parse_def_name='import')
            if instance_ctx:
                instance = instance_ctx._instance
                self[ext_id] = instance
                if getattr(instance.__class__, 'pub_state', None):
                    instance.pub_state = self.target_state
                self.db.add(instance)
        if self.pending():
            self.resolve_pending()
        self.db.flush()
        # Maybe tombstone objects that had import records and were not reimported or referred to?

    def resolve_pending(self):
        """resolve any pending reference, may require queries. May fail."""
        pass

    def add_missing_links(self):
        from .idea import Idea, IdeaLink
        # add links from discussion root to roots of idea subtrees
        base_ids = self.db.query(Idea.id).outerjoin(IdeaLink, IdeaLink.target_id == Idea.id).filter(
            IdeaLink.id == None, Idea.discussion_id==self.discussion_id).all()
        root_id = self.discussion.root_idea.id
        base_ids.remove((root_id,))
        for (id,) in base_ids:
            self.db.add(IdeaLink(source_id=root_id, target_id=id))
        self.db.flush()
        # Maybe tombstone objects that had import records and were not reimported or referred to?



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

    @classmethod
    def records_query(cls, target, source_id=None):
        q = target.db.query(cls).filter_by(
            target_id=target.id, target_table=target.base_tablename())
        if source_id:
            q = q.filter_by(source_id=None)
        return q


class IdeaLoomIdeaSource(IdeaSource):
    __tablename__ = 'idealoom_idea_source'
    id = Column(Integer, ForeignKey(IdeaSource.id), primary_key=True)
    # or use a token?
    username = Column(String())
    password = Column(String())
    # add credentials!

    __mapper_args__ = {
        'polymorphic_identity': 'idealoom',
    }

    @reconstructor
    def init_on_load(self):
        super(IdeaLoomIdeaSource, self).init_on_load()
        self.use_local = False
        # TODO: find a way to reuse Users when self.source_uri.startswith(self.global_url)
        self.cookies = CookieJar()

    def class_from_data(self, json):
        typename = json.get('@type', None)
        if typename:
            return get_named_class(typename)

    def base_source_uri(self):
        return urljoin(self.source_uri, '/data/')

    def process_data(self, data):
        if data['@type'] == 'RootIdea':
            self[data['@id']] = self.discussion.root_idea
            return None
        return data

    def normalize_id(self, id):
        id = self.id_from_data(id)
        if not id:
            return
        if id.startswith('local:') and not self.use_local:
            return self.base_source_uri() + id[6:]
        return super(IdeaLoomIdeaSource, self).normalize_id(id)

    def read(self, admin_user_id=None):
        super(IdeaLoomIdeaSource, self).read(admin_user_id)
        local_server = self.source_uri.startswith(urljoin(self.global_url, '/'))
        admin_user_id = admin_user_id or self.discussion.creator_id
        login_url = urljoin(self.source_uri, '/login')
        r = requests.post(login_url, cookies=self.cookies, data={
            'identifier':self.username, 'password':self.password},
            allow_redirects=False)
        assert r.ok
        assert 'login' not in r.headers['Location']
        self.cookies.update(r.cookies)
        r = requests.get(self.source_uri, cookies=self.cookies)
        assert r.ok
        ideas = r.json()
        self.read_json(ideas, admin_user_id)
        discussion_id = self.source_uri.split('/')[-2]
        link_uri = urljoin(self.source_uri,
            '/data/Conversation/%s/idea_links' % (discussion_id,))
        r = requests.get(link_uri, cookies=self.cookies)
        assert r.ok
        links = r.json()
        link_subset = [l for l in links
            if self.normalize_id(l['source']) in self.instance_by_id and
            self.normalize_id(l['target']) in self.instance_by_id]
        self.read_json(link_subset, admin_user_id)
        missing_oids = list(self.promises_by_target_id.keys())
        missing_classes = {oid.split('/')[-2] for oid in missing_oids}
        missing_classes.discard('Agent')
        assert not missing_classes, "Promises for unknown classes " + str(missing_classes)
        if local_server:
            for oid in missing_oids:
                loid = 'local:'+oid[len(self.global_url):]
                self[oid] = AgentProfile.get_instance(loid)
        else:
            self.read_json([
                requests.get(oid, cookies=self.cookies).json()
                for oid in missing_oids], admin_user_id)

        self.db.flush()
        self.add_missing_links()

    def read_json(self, data, admin_user_id):
        if isinstance(data, string_types):
            data = json.loads(data)

        def find_objects(j):
            if isinstance(j, list):
                for x in j:
                    for obj in find_objects(x):
                        yield obj
            elif isinstance(j, dict):
                jid = j.get('@id', None)
                if jid:
                    yield j
                for x in j.values():
                    for obj in find_objects(x):
                        yield obj

        self.read_data_gen(find_objects(data), admin_user_id)


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

    def class_from_data(self, json):
        typename = json.get('@type')
        # Look for aliased classes.
        # Maybe look in the context instead?
        typename = self.equivalents.get(typename, typename)
        if typename:
            cls = get_named_class(typename)
            # TODO: Adjust for subclasses according to json record
            # cls = cls.get_jsonld_subclass(json)
            return cls

    def normalize_id(self, id):
        id = self.id_from_data(data)
        if not id:
            return
        if id.startswith('local:'):
            return self.remote_context.expand(id)
        return super(CatalystIdeaSource, self).normalize_id(id)

    def process_data(self, record):
        record['in_conversation'] = self.discussion.uri()
        from .idea import Idea, IdeaLink
        from .votes import AbstractIdeaVote, AbstractVoteSpecification
        from .widgets import MultiCriterionVotingWidget
        cls = self.class_from_data(record)
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

    def read_data(self, jsonld, admin_user_id, base=None):
        self.load_previous_records()
        if isinstance(jsonld, string_types):
            jsonld = json.loads(jsonld)
        c = jsonld['@context']
        self.remote_context = Context(c)

        def find_objects(j):
            if isinstance(j, list):
                for x in j:
                    for obj in find_objects(x):
                        yield obj
            elif isinstance(j, dict):
                jid = j.get('@id', None)
                if jid:
                    yield j
                for x in j.values():
                    for obj in find_objects(x):
                        yield obj

        self.read_data_gen(find_objects(jsonld), admin_user_id)
        self.db.flush()
        self.add_missing_links()
