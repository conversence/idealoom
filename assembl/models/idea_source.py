import logging
from datetime import datetime, timedelta
try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

from sqlalchemy import (
    Column, ForeignKey, Integer, String, Boolean)
from sqlalchemy.orm import relationship, reconstructor
from future.utils import string_types
import simplejson as json
from rdflib_jsonld.context import Context
import requests
from requests.cookies import RequestsCookieJar as CookieJar

from .auth import AgentProfile
from .import_record_source import ImportRecordSource
from .idea import Idea, IdeaLink
from ..tasks.source_reader import PullSourceReader, ClientError, IrrecoverableError
from .publication_states import PublicationState
from ..lib.sqla import get_named_class


log = logging.getLogger(__name__)


class IdeaSource(ImportRecordSource):
    __tablename__ = 'idea_source'
    id = Column(Integer, ForeignKey(ImportRecordSource.id), primary_key=True)
    target_state_id = Column(Integer, ForeignKey(
        PublicationState.id, ondelete="SET NULL", onupdate="CASCADE"))

    target_state = relationship(PublicationState)

    __mapper_args__ = {
        'polymorphic_identity': 'abstract_idea_source',
    }

    def process_new_object(self, ext_id, instance):
        if getattr(instance.__class__, 'pub_state', None):
            instance.pub_state = self.target_state
        super(IdeaSource, self).process_new_object(ext_id, instance)

    def add_missing_links(self):
        # add links from discussion root to roots of idea subtrees
        base_ids = self.db.query(Idea.id).outerjoin(IdeaLink, IdeaLink.target_id == Idea.id).filter(
            IdeaLink.id == None, Idea.discussion_id == self.discussion_id).all()
        root_id = self.discussion.root_idea.id
        base_ids.remove((root_id,))
        for (id,) in base_ids:
            self.db.add(IdeaLink(source_id=root_id, target_id=id))
        self.db.flush()
        # Maybe tombstone objects that had import records and were not reimported or referred to?

    def load_previous_records(self):
        super(IdeaSource, self).load_previous_records()
        self.local_urls = {Idea.uri_generic(id, self.global_url) for (id,)
            in self.db.query(Idea.id).filter_by(
                discussion_id=self.discussion_id).all()}
        self.local_urls.update({IdeaLink.uri_generic(id, self.global_url) for (id,)
            in self.db.query(IdeaLink.id).join(Idea, IdeaLink.source_id==Idea.id).filter_by(
                discussion_id=self.discussion_id).all()})

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


class IdeaLoomIdeaSource(IdeaSource):
    __tablename__ = 'idealoom_idea_source'
    id = Column(Integer, ForeignKey(IdeaSource.id), primary_key=True)
    # or use a token?
    username = Column(String())
    password = Column(String())
    # add credentials!
    use_local = False

    __mapper_args__ = {
        'polymorphic_identity': 'idealoom',
    }

    @reconstructor
    def init_on_load(self):
        super(IdeaLoomIdeaSource, self).init_on_load()
        # TODO: find a way to reuse Users when self.source_uri.startswith(self.global_url)
        self.cookies = CookieJar()

    def class_from_data(self, json):
        typename = json.get('@type', None)
        if typename:
            return get_named_class(typename)

    def base_source_uri(self):
        return urljoin(self.source_uri, '/data/')

    def process_data(self, data):
        dtype = data.get('@type', None)
        if dtype == 'RootIdea':
            self.base_set_item(self.normalize_id(data['@id']), self.discussion.root_idea)
            return None
        if dtype == 'GenericIdeaNode':
            data['pub_state_name'] = self.target_state.name
        elif dtype == 'DirectedIdeaRelation':
            source_id = self.normalize_id(data['source'])
            if source_id not in self.instance_by_id:
                self.base_set_item(source_id, self.discussion.root_idea)
                self[source_id] = self.discussion.root_idea
        return data

    def external_id_to_uri(self, external_id):
        if '//' in external_id:
            return external_id
        if external_id.startswith('local:'):
            return self.base_source_uri() + external_id[6:]
        return external_id  # as urn?

    def uri_to_external_id(self, uri):
        base = self.base_source_uri()
        if uri.startswith(base) and self.use_local:
            uri = 'local:' + uri[len(base):]
        return uri

    def get_imported_from_in_data(self, data):
        return data.get('imported_from_url', None)

    def normalize_id(self, id):
        id = self.id_from_data(id)
        if not id:
            return
        if id.startswith('local:') and not self.use_local:
            return self.external_id_to_uri(id)
        return super(IdeaLoomIdeaSource, self).normalize_id(id)

    def login(self, admin_user_id=None):
        login_url = urljoin(self.source_uri, '/login')
        r = requests.post(login_url, cookies=self.cookies, data={
            'identifier': self.username, 'password': self.password},
            allow_redirects=False)
        assert r.ok
        if 'login' in r.headers['Location']:
            return False
        self.cookies.update(r.cookies)
        self._last_login = datetime.now()
        return True

    def read(self, admin_user_id=None):
        admin_user_id = admin_user_id or self.discussion.creator_id
        super(IdeaLoomIdeaSource, self).read(admin_user_id)
        local_server = self.source_uri.startswith(urljoin(self.global_url, '/'))
        super(IdeaLoomIdeaSource, self).read(admin_user_id)
        last_login = getattr(self, '_last_login', None)
        if not last_login or datetime.now() - last_login > timedelta(days=1):
            assert self.login(admin_user_id)
        r = requests.get(self.source_uri, cookies=self.cookies)
        assert r.ok
        ideas = r.json()
        self.read_json(ideas, admin_user_id, True)
        discussion_id = self.source_uri.split('/')[-2]
        link_uri = urljoin(
            self.source_uri,
            '/data/Conversation/%s/idea_links' % (discussion_id,))
        r = requests.get(link_uri, cookies=self.cookies)
        assert r.ok
        links = r.json()
        link_subset = [
            l for l in links
            if self.normalize_id(l['target']) in self.instance_by_id]
        self.read_json(link_subset, admin_user_id)
        missing_oids = list(self.promises_by_target_id.keys())
        missing_classes = {oid.split('/')[-2] for oid in missing_oids}
        missing_classes.discard('Agent')
        assert not missing_classes, "Promises for unknown classes " + str(missing_classes)
        if local_server:
            for oid in missing_oids:
                loid = 'local:'+oid[len(self.global_url):]
                self.base_set_item(oid, AgentProfile.get_instance(loid))
        else:
            self.read_json([
                requests.get(oid, cookies=self.cookies).json()
                for oid in missing_oids], admin_user_id)

        self.db.flush()
        self.add_missing_links()

    def read_json(self, data, admin_user_id, apply_filter=False):
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

        self.read_data_gen(find_objects(data), admin_user_id, apply_filter)

    def make_reader(self):
        return SimpleIdealoomReader(self.id)


class SimpleIdealoomReader(PullSourceReader):

    def __init__(self, source_id):
        super(SimpleIdealoomReader, self).__init__(source_id)

    def login(self):
        try:
            login = self.source.login()
            if not login:
                raise IrrecoverableError("could not login")
        except AssertionError:
            raise ClientError("login connection error")

    def do_read(self):
        sess = self.source.db
        try:
            self.source.read()
            sess.commit()
        except Exception as e:
            self.new_error(e)


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
        if not id:
            return
        if id.startswith('local:'):
            return self.remote_context.expand(id)
        return super(CatalystIdeaSource, self).normalize_id(id)

    def process_data(self, record):
        record['in_conversation'] = self.discussion.uri()
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
        print("****** get_record: ", record.get('@id', None), record)
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
