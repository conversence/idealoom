"""Create the Virtuoso `Linked Data Views`_ from the RDF data embedded in the models. Obsolete.

.. _`Linked Data Views`: http://docs.openlinksw.com/virtuoso/rdfviewsrdbms.html
"""
from builtins import object
from os import listdir, urandom
from os.path import join
from inspect import isabstract, isclass
import re
from itertools import chain
from base64 import urlsafe_b64encode, urlsafe_b64decode
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.properties import RelationshipProperty
from rdflib import Graph, ConjunctiveGraph, URIRef
import simplejson as json

from . import (context_url, ontology_dir, local_context_loc)
from ..lib.config import get_config
from ..lib.utils import get_global_base_url
from ..lib.sqla import class_registry, Base
from .namespaces import (
    ASSEMBL, QUADNAMES, RDF, OWL, CATALYST, SIOC, FOAF, VirtRDF)
from sqla_rdfbridge.mapping import (
    QuadMapPattern, GraphQuadMapPattern, IriClass)
from sqla_rdfbridge.quadextractor import ClassPatternExtractor
# from virtuoso.vmapping import (
#     QuadStorage,  PatternGraphQuadMapPattern)
# from virtuoso.vstore import Virtuoso
# from virtuoso.alchemy import SparqlClause


log = logging.getLogger(__name__)


def get_nsm(session):
    from .namespaces import namespace_manager
    from virtuoso.vstore import VirtuosoNamespaceManager
    nsm = VirtuosoNamespaceManager(Graph(), session)
    for prefix, namespace in namespace_manager.namespaces():
        nsm.bind_virtuoso(session, prefix, namespace)
    return nsm


def get_virtuoso(session, storage=None):
    storage = storage or AppQuadStorageManager.discussion_storage_name()
    return Virtuoso(quad_storage=storage,
                 connection=session.connection())

USER_SECTION = 'user'
PRIVATE_USER_SECTION = 'private'
MAIN_SECTION = 'main'
EXTRACT_SECTION = 'extract'
DISCUSSION_DATA_SECTION = 'data'


formats = dict(
    ttl='turtle',
    owl='xml',
    xml='xml',
    trig='trig'
)


def load_ontologies(session, reload=None):
    store = Virtuoso(connection=session.bind.connect())
    known_graphs = [g.identifier for g in store.contexts()]
    log.debug('known ' + known_graphs)
    for fname in listdir(ontology_dir):
        ending = fname.rsplit('.')[-1]
        if ending not in formats:
            continue
        debug_str = fname + ' '
        temp_graph = Graph()
        temp_graph.parse(join(ontology_dir, fname), format=formats[ending])
        ontologies = list(temp_graph.subjects(RDF.type, OWL.Ontology))
        debug_str += ontologies + ' '
        if len(ontologies) != 1:
            log.debug(debug_str)
            continue
        ontology = ontologies[0]
        if ontology in known_graphs:
            log.debug(debug_str + 'already there')
            continue
        for (s, p, o) in temp_graph.triples((None, None, None)):
            store.add((s, p, o), context=ontology)
        log.debug(debug_str + "loaded")


class QuadMapPatternS(QuadMapPattern):
    def __init__(
            self, subject=None, predicate=None, obj=None, graph_name=None,
            name=None, conditions=None, nsm=None, sections=None,
            exclude_base_condition=False):
        super(QuadMapPatternS, self).__init__(
            subject, predicate, obj, graph_name, name, conditions, nsm)
        self.sections = sections
        self.exclude_base_condition = exclude_base_condition

    def clone_with_defaults(self, subject=None, obj=None, graph_name=None,
                            name=None, conditions=None, sections=None,
                            exclude_base_condition=False):
        # temporary. We should use the section objects themselves.
        if self.sections:
            graph_name = AppQuadStorageManager.sections[
                self.sections[0]].graph_iri
        qmp = super(QuadMapPatternS, self).clone_with_defaults(
            subject, obj, graph_name, name, conditions)
        qmp.sections = self.sections or sections
        qmp.exclude_base_condition = (
            self.exclude_base_condition or exclude_base_condition)
        return qmp


def assembl_iri_accessor(cls):
    return cls.iri_class()


class AppClassPatternExtractor(ClassPatternExtractor):

    def iri_accessor(self, sqla_cls):
        return sqla_cls.iri_class()
        # TODO: Special case for special class accessors

    def get_subject_pattern(self, cls, alias_maker=None):
        iri_qmp = None
        try:
            iri_qmp = cls.iri_class()
        except AttributeError:
            pass
        if iri_qmp:
            return iri_qmp.apply(cls.id)
        return super(AppClassPatternExtractor, self
                     ).get_subject_pattern(cls, alias_maker)

    def class_pattern_name(self, cls, for_graph):
        clsname = cls.external_typename()
        if for_graph.discussion_id:
            return getattr(QUADNAMES, 'class_pattern_d%s_%s' % (
                for_graph.discussion_id, clsname))
        else:
            return getattr(QUADNAMES, 'class_pattern_'+clsname)

    def make_column_name(self, cls, column, for_graph):
        clsname = cls.external_typename()
        if for_graph.discussion_id:
            return getattr(QUADNAMES, 'col_pattern_d%s_%s_%s' % (
                for_graph.discussion_id, clsname, column.key))
        else:
            return getattr(QUADNAMES, 'col_pattern_%s_%s' % (
                clsname, column.key))

    def include_foreign_conditions(self, dest_class_path):
        from assembl.models import Discussion
        return dest_class_path.final_class != Discussion

    def delayed_class(self, sqla_cls, for_graph):
        from ..models import DiscussionBoundBase
        return (
            issubclass(sqla_cls, DiscussionBoundBase)
            and getattr(sqla_cls.get_discussion_conditions,
                        '__isabstractmethod__', None))

    def delayed_column(self, sqla_cls, column, for_graph):
        return self.delayed_class(sqla_cls.mro()[1], for_graph)

    def add_class(self, sqla_cls, for_graph):
        if self.delayed_class(sqla_cls, for_graph):
            return
        super(AppClassPatternExtractor, self).add_class(
            sqla_cls, for_graph)

    def extract_qmps(self, sqla_cls, subject_pattern, alias_maker, for_graph):
        rdf_class = sqla_cls.__dict__.get('rdf_class', None)
        rdf_sections = getattr(
            sqla_cls, 'rdf_sections', (DISCUSSION_DATA_SECTION,))
        if rdf_class is not None and for_graph.section in rdf_sections:
            yield QuadMapPatternS(
                subject_pattern, RDF.type, rdf_class, for_graph.name,
                self.class_pattern_name(sqla_cls, for_graph),
                self.get_base_conditions(alias_maker, sqla_cls, for_graph),
                None, rdf_sections)
        for qmp in super(AppClassPatternExtractor, self).extract_qmps(
                sqla_cls, subject_pattern, alias_maker, for_graph):
            if for_graph.section in qmp.sections:
                yield qmp
        if 'special_quad_patterns' in sqla_cls.__dict__:
            # Only direct definition
            # OK. I need to have one alias per column, with the possibility of
            # creating more aliases for paths (multiple joins.)
            # The paths can be expressed as sequences of properties, I guess.
            # Maybe propose aliases?
            for qmp in sqla_cls.special_quad_patterns(
                    alias_maker, for_graph.discussion_id):
                qmp = self.qmp_with_defaults(
                    qmp, subject_pattern, sqla_cls, alias_maker, for_graph)
                target_sections = qmp.sections or rdf_sections
                if (qmp.graph_name == for_graph.name
                        and for_graph.section in target_sections):
                    qmp.resolve(sqla_cls)
                    yield qmp

    def get_base_conditions(self, alias_maker, cls, for_graph):
        from ..models import DiscussionBoundBase
        conditions = super(
            AppClassPatternExtractor, self).get_base_conditions(
            alias_maker, cls, for_graph)
        base_conds = cls.base_conditions(alias_maker=alias_maker)
        if base_conds:
            conditions.extend(base_conds)
        if (for_graph.discussion_id and issubclass(cls, DiscussionBoundBase)
                and not isabstract(cls)):
            # TODO: update with conditionS.
            conditions.extend(cls.get_discussion_conditions(
                for_graph.discussion_id, alias_maker))
        return [c for c in conditions if c is not None]

    def qmp_with_defaults(
            self, qmp, subject_pattern, sqla_cls, alias_maker, for_graph,
            column=None):
        rdf_sections = getattr(
            sqla_cls, 'rdf_sections', (DISCUSSION_DATA_SECTION,))
        name = None
        if column is not None:
            name = self.make_column_name(sqla_cls, column, for_graph)
            if isinstance(column, RelationshipProperty):
                column = self.property_as_reference(column, alias_maker)
            elif column.foreign_keys:
                try:
                    column = self.column_as_reference(column)
                except AssertionError:
                    return None
        qmp = qmp.clone_with_defaults(
            subject_pattern, column, for_graph.name, name, None, rdf_sections)
        if not qmp.exclude_base_condition:
            conditions = self.get_base_conditions(
                alias_maker, sqla_cls, for_graph)
            if conditions:
                qmp.and_conditions(conditions)
        d_id = for_graph.discussion_id
        if (d_id and qmp.name is not None
                and "_d%d_" % (d_id,) not in qmp.name):
            # TODO: improve this
            qmp.name += "_d%d_" % (d_id,)
        if (for_graph.section != qmp.sections[0]
                and for_graph.section in qmp.sections):
            qmp.name += '_s%d' % (qmp.sections.index(for_graph.section),)
        return qmp


class AppGraphQuadMapPattern(GraphQuadMapPattern):
    def __init__(
            self, graph_iri, storage, section, discussion_id,
            name=None, option=None, nsm=None):
        super(AppGraphQuadMapPattern, self).__init__(
            graph_iri, storage, name, option, nsm)
        self.discussion_id = discussion_id
        self.section = section


class AESObfuscator(object):
    def __init__(self, key=None, blocklen=16):
        key = key or urandom(blocklen)
        self.key = self.pad(key, blocklen)
        self.blocklen = blocklen
        self.IV = ' ' * blocklen

    def encrypt(self, text):
        from Crypto.Cipher import AES
        encoder = AES.new(self.key, AES.MODE_CFB, self.IV)
        return urlsafe_b64encode(encoder.encrypt(text))

    def decrypt(self, code):
        from Crypto.Cipher import AES
        encoder = AES.new(self.key, AES.MODE_CFB, self.IV)
        code = code.encode('utf-8')
        code = urlsafe_b64decode(code)
        return encoder.decrypt(code)

    def pad(self, key, blocklen=16, padding=' '):
        return key + padding * (blocklen - (len(key) % blocklen))



class AppPatternGraphQuadMapPattern(GraphQuadMapPattern):
    def __init__(
            self, graph_iri_pattern, storage, alias_set, section,
            discussion_id, name=None, option=None, nsm=None):
        super(AppPatternGraphQuadMapPattern, self).__init__(
            graph_iri_pattern, storage, alias_set, name, option, nsm)
        self.discussion_id = discussion_id
        self.section = section


class StorageDefinition(object):
    __slots__ = ("sections", "name")
    def __init__(self, name):
        self.sections = []
        self.name = name

    def add_section(self, section):
        self.sections.append(section)

class DataSection(object):
    __slots__ = ("name", "graph_name", "graph_iri", "storage")
    def __init__(self, name, storage, graph_name, graph_iri, add=True):
        self.name = name
        self.storage = storage
        self.graph_name = graph_name
        self.graph_iri = graph_iri
        if add:
            storage.add_section(self)


class AppQuadStorageManager(object):
    private_user_storage = StorageDefinition(QUADNAMES.PrivateUserStorage)
    discussion_storage = StorageDefinition(QUADNAMES.discussion_storage)
    main_storage = StorageDefinition(QUADNAMES.main_storage)
    discussion_data_section = DataSection(
        DISCUSSION_DATA_SECTION, discussion_storage, ASSEMBL.discussion_data,
        QUADNAMES.discussion_data_iri)
    user_section = DataSection(
        USER_SECTION, discussion_storage, ASSEMBL.user_graph,
        QUADNAMES.user_graph_iri)
    private_user_section = DataSection(
        PRIVATE_USER_SECTION, private_user_storage, ASSEMBL.private_user_graph,
        QUADNAMES.private_user_graph_iri)
    main_section = DataSection(
        MAIN_SECTION, main_storage, ASSEMBL.main_graph,
        QUADNAMES.main_graph_iri)
    storages = (discussion_storage, private_user_storage)  # main_storage
    sections = {section.name: section for section in chain(*(
        storage.sections for storage in storages))}
    global_graph = QUADNAMES.global_graph
    current_discussion_storage_version = 16

    def __init__(self, session=None, nsm=None):
        self.session = session or Base.default_db
        self.nsm = nsm or get_nsm(self.session)
        # Fails if not full schema
        assert Base.metadata.schema.split('.')[1]
        self.local_pattern = re.compile(
            r'\b%s([^"]+)' % ('\.'.join(self.local_uri().split('.'))))

    @staticmethod
    def local_uri():
        return get_global_base_url() + '/data/'

    def audit_metadata(self):
        # in response to error 22023, The quad storage is edited by other client
        self.session.execute("DB.DBA.RDF_AUDIT_METADATA(1, '*')")

    def prepare_storage(self, quad_storage_name, imported=None):
        cpe = AppClassPatternExtractor(Base.registry._class_registry.values())
        qs = QuadStorage(
            quad_storage_name, cpe, imported, False, nsm=self.nsm)
        return qs, cpe

    def populate_section(
            self, qs, cpe, section, discussion_id=None, exclusive=True):
        gqm = AppGraphQuadMapPattern(
            section.graph_name, qs, section.name, discussion_id, section.graph_iri,
            'exclusive' if exclusive else None)
        for cls in class_registry.values():
            # TODO: Take pattern's graph into account!
            if isclass(cls):
                cpe.add_class(cls, gqm)
        return gqm

    def create_storage(self, storage, discussion_id=None, exclusive=True,
                       imported=None, execute=True):
        qs, cpe = self.prepare_storage(storage.name, imported or [])
        for section in storage.sections:
            self.populate_section(qs, cpe, section, discussion_id, exclusive)
        if storage is self.discussion_storage:
            self.add_extracts_graphs(qs, cpe, None)
        defn = qs.full_declaration_clause()
        result = None
        if execute:
            result = list(self.session.execute(defn))
        return qs, cpe, defn, result

    def update_section(
            self, section, discussion_id, exclusive=True):
        qs, cpe = self.prepare_storage(section.storage.name)
        gqm = self.populate_section(
            qs, cpe, section, discussion_id, exclusive)
        defn = qs.alter_clause_add_graph(gqm)
        results = self.session.execute(defn)
        return qs, results

    def drop_storage(self, storage_name, force=True):
        qs = QuadStorage(storage_name, None, nsm=self.nsm)
        try:
            qs.drop(self.session, force)
        except Exception as e:
            log.error(e)

    def drop_graph(self, graph_iri, force=True):
        gr = GraphQuadMapPattern(graph_iri, None, nsm=self.nsm)
        gr.drop(self.session, force)

    @staticmethod
    def discussion_storage_name(discussion_id=None):
        if discussion_id:
            return getattr(QUADNAMES, 'discussion_%d_storage' % discussion_id)
        else:
            return AppQuadStorageManager.discussion_storage.name

    @staticmethod
    def discussion_graph_name(
            discussion_id=None, section=DISCUSSION_DATA_SECTION):
        if discussion_id:
            return getattr(ASSEMBL, 'discussion_%d_%s' % (
                discussion_id, section))
        else:
            return getattr(ASSEMBL, 'discussion_%s' % (section, ))

    @staticmethod
    def discussion_graph_iri(
            discussion_id=None, section=DISCUSSION_DATA_SECTION):
        if discussion_id:
            return getattr(QUADNAMES, 'discussion_%d_%s_iri' % (
                discussion_id, section))
        else:
            return getattr(QUADNAMES, 'discussion_%s_iri' % (section,))

    def add_extracts_graphs(self, qs, cpe, discussion_id=None):
        from ..models import Extract, Idea
        # Option 1: explicit graphs.
        # Fails because the extract.id in the condition is not part of
        # the compile, so we do not get explicit conditions.
        #
        # from ..models import TextFragmentIdentifier
        # for extract in self.session.query(Extract).filter(
        #         (Extract.discussion_id==discussion_id)
        #         & (Extract.idea != None)):
        #     gqm = GraphQuadMapPattern(
        #         extract.extract_graph_name(), qs,
        #         extract.extract_graph_iri())
        #     qmp = QuadMapPatternS(
        #         extract.extract_graph_name(), CATALYST.expressesIdea,
        #         IdeaContentLink.iri_class().apply(Extract.idea_id),
        #         graph_name=gqm.name,
        #         name=getattr(QUADNAMES, 'catalyst_expressesIdea_'+str(
        #                      extract.id)),
        #         condition=(Extract.idea_id != None
        #                   ) & (Extract.id == extract.id),
        #         sections=(EXTRACT_SECTION,))
        #     gqm.add_patterns((qmp,))
        #
        # Option 2: use the usual mechanism. But interaction with alias_set is
        # hopelessly complicated
        # self.populate_storage(qs, cpe, EXTRACT_SECTION,
        #     Extract.graph_iri_class.apply(Extract.id),
        #     QUADNAMES.ExtractGraph_iri, discussion_id)
        #
        # So option 3: A lot of encapsulation breaks...
        # Which still does not quite work in practice, but it does in theory.
        # Sigh.
        extract_graph_name = Extract.graph_iri_class.apply(Extract.id)
        extract_conditions=[(Extract.idea_id != None)]
        if discussion_id:
            extract_graph_iri = getattr(
                QUADNAMES, "catalyst_ExtractGraph_d%d_iri" % (discussion_id,))
            extract_expressesIdea_iri = getattr(
                QUADNAMES, "catalyst_expressesIdea_d%d_iri" % (discussion_id,))
            extract_conditions.append((Extract.discussion_id == discussion_id))
        else:
            extract_graph_iri = QUADNAMES.catalyst_ExtractGraph_iri
            extract_expressesIdea_iri = QUADNAMES.catalyst_expressesIdea_iri
        gqm = AppPatternGraphQuadMapPattern(
            extract_graph_name, qs, cpe, EXTRACT_SECTION, discussion_id,
            extract_graph_iri, 'exclusive')
        qmp = QuadMapPatternS(
            Extract.specific_resource_iri.apply(Extract.id),
            CATALYST.expressesIdea,
            Idea.iri_class().apply(Extract.idea_id),
            graph_name=extract_graph_name,
            name=extract_expressesIdea_iri,
            conditions=extract_conditions,
            sections=(EXTRACT_SECTION,))
        cpe.add_pattern(Extract, qmp, gqm)
        # defn2 = qs.alter_clause_add_graph(gqm)
        # result.extend(self.session.execute(str(defn2.compile(self.session.bind))))
        return qs

    def discussion_storage_version(self, discussion_id):
        return self.get_storage_version(self.discussion_storage_name(discussion_id))

    def get_storage_version(self, storage_name):
        exists = self.mapping_exists(storage_name, QuadStorage.mapping_type)
        if not exists:
            return -1
        n3 = self.n3
        version = self.session.execute(SparqlClause(
            "SELECT ?version WHERE { graph %s { %s %s ?version }}" % (
                n3(self.global_graph), n3(storage_name), n3(ASSEMBL.mapping_version))
            )).first()
        return int(version[0]) if version else 0

    def n3(self, rdf_term):
        return rdf_term.n3(self.nsm)

    def set_storage_version(self, storage_name, version):
        n3 = self.n3
        self.session.execute(SparqlClause(
            "WITH {0} DELETE {{ {1} {2} ?version }} WHERE {{ {1} {2} ?version }}".format(
                n3(self.global_graph), n3(storage_name), n3(ASSEMBL.mapping_version))))
        self.session.execute(SparqlClause(
            "INSERT DATA { graph %s { %s %s %d } }" % (
                n3(self.global_graph), n3(storage_name), n3(ASSEMBL.mapping_version), version)))
        self.session.commit()

    def drop_all_discussion_storages_but(self, discussion_id):
        # This to get around virtuoso issue 285
        # TODO: Make sure this is called by only one thread
        config = get_config()
        from assembl.models import Discussion
        discussion_full_name = '.'.join((
            config.get('db_schema'), config.get('db_user'),
            Discussion.__tablename__))
        storages = list(self.session.execute("""
            SPARQL SELECT DISTINCT ?s WHERE {graph virtrdf: {
                ?s a virtrdf:QuadStorage .
                ?s virtrdf:qsUserMaps ?um .
                ?um ?pn ?gm .
                ?gm a virtrdf:QuadMap .
                ?gm virtrdf:qmUserSubMaps ?usm .
                ?usm ?pm ?m .
                ?m a virtrdf:QuadMap ;
                   virtrdf:qmTableName "%s"  }}""" % (discussion_full_name, )))
        # storage names take the form quadnames:discussion_14_storage
        storage_nums = [re.search(r'discussion_([0-9]+_)?storage', s).group(1)
                        for (s,) in storages]
        storage_nums = [(int(x[:-1]) if x else None) for x in storage_nums]
        for storage_num in storage_nums:
            if storage_num == discussion_id:
                continue
            self.drop_discussion_storage(storage_num)

    def drop_iri_classes(self):
        for (quadname,) in list(self.session.execute("""
                SPARQL select * where {
                    graph virtrdf: {
                        ?s a virtrdf:QuadMapFormat }}""")):
            if quadname.startswith(QUADNAMES)\
                    and not quadname.endswith("-nullable"):
                self.session.execute("SPARQL drop iri class quadnames:%s" % (
                    quadname[len(QUADNAMES):],))

    def update_all_storages(self):
        self.audit_metadata()
        self.declare_functions()
        self.add_function_permissions()
        # drop old single-discussion storages
        self.drop_all_discussion_storages_but(None)
        delete_storages = False
        for storage in self.storages:
            version = self.get_storage_version(storage.name)
            if 0 <= version < self.current_discussion_storage_version:
                delete_storages = True
        if delete_storages:
            self.drop_all()
        for storage in self.storages:
            version = self.get_storage_version(storage.name)
            if version < self.current_discussion_storage_version\
                    or delete_storages:
                self.create_storage(storage)
                self.set_storage_version(
                    storage.name, self.current_discussion_storage_version)

    def drop_discussion_storage(self, discussion_id=None, force=True):
        self.drop_storage(
            self.discussion_storage_name(discussion_id), force)

    def create_extract_graph(self, extract):
        # TODO: Make sure this is called when an extract is added.
        discussion_id = extract.get_discussion_id()
        return self.update_section(DataSection(
            EXTRACT_SECTION, self.discussion_storage,
            extract.extract_graph_name(), extract.extract_graph_iri(), False),
            discussion_id)

    def drop_extract_graph(self, extract, force=True):
        self.drop_graph(self.extract_iri(extract.id), force)

    def mapping_exists(self, name, mapping_type):
        return bool(self.session.execute(
            """SPARQL ASK WHERE { GRAPH virtrdf: { %s a %s }}"""
            % (name.n3(self.nsm), mapping_type.n3(self.nsm))
            ).first())

    def add_function_permissions(self):
        for name in ("DB.DBA.RL_I2ID_NP",):
            self.make_function_public(name)

    def make_function_public(self, fname):
        self.session.execute('GRANT EXECUTE ON "%s" TO PUBLIC' % fname)

    def declare_functions(self):
        pass

    def drop_all(self, force=True):
        for storage in self.storages:
            self.drop_storage(storage.name, force)
        from ..models import Discussion
        for (id,) in self.session.query(Discussion.id).all():
            self.drop_storage(self.discussion_storage_name(id), force)
        self.drop_iri_classes()

    def as_graph(self, d_storage_name, graphs=()):
        v = get_virtuoso(self.session, d_storage_name)
        if not graphs:
            graphs = v.contexts()
        cg = ConjunctiveGraph()
        for ctx in graphs:
            for ((s, p, o), g) in v.triples((None,None,None), ctx):
                cg.add((s, p, o, ctx))
        return cg

    def add_subject_data(self, virtuoso, graph, subjects):
        for s in subjects:
            for p, o, g in virtuoso.query(
                'SELECT ?p ?o ?g WHERE { graph ?g { %s ?p ?o }}' % (s.n3(),)):
                    graph.add((s, p, o, g))


    def discussion_as_graph(self, discussion_id):
        from assembl.models import Discussion, AgentProfile
        local_uri = self.local_uri()
        discussion = Discussion.get(discussion_id)
        d_storage_name = self.discussion_storage_name()
        d_graph_iri = URIRef(self.discussion_graph_iri())
        v = get_virtuoso(self.session, d_storage_name)
        discussion_uri = URIRef(
            Discussion.uri_generic(discussion_id, local_uri))
        subjects = [s for (s,) in v.query(
            """SELECT DISTINCT ?s WHERE {
            ?s assembl:in_conversation %s }""" % (discussion_uri.n3()))]
        subjects.append(discussion_uri)
        participant_ids = list(discussion.get_participants(True))
        profiles = {URIRef(AgentProfile.uri_generic(id, local_uri))
                    for id in participant_ids}
        subjects.extend(profiles)
        # add pseudo-accounts
        subjects.extend((URIRef("%sAgentAccount/%d" % (local_uri, id))
                         for id in participant_ids))
        # log.debug( len(subjects))
        cg = ConjunctiveGraph(identifier=d_graph_iri)
        self.add_subject_data(v, cg, subjects)
        # add relationships of non-pseudo accounts
        for ((account, p, profile), g) in v.triples((None, SIOC.account_of, None)):
            if profile in profiles:
                cg.add((account, SIOC.account_of, profile, g))
                # Tempting: simplify with this.
                # cg.add((profile, FOAF.account, account, g))
        for (s, o, g) in v.query(
                '''SELECT ?s ?o ?g WHERE {
                GRAPH ?g {?s catalyst:expressesIdea ?o } .
                ?o assembl:in_conversation %s }''' % (discussion_uri.n3())):
            cg.add((s, CATALYST.expressesIdea, o, g))
        return cg

    def participants_private_as_graph(self, discussion_id):
        from assembl.models import Discussion, AgentProfile
        local_uri = self.local_uri()
        discussion = Discussion.get(discussion_id)
        d_storage_name = self.private_user_storage.name
        d_graph_iri = self.private_user_storage.sections[0].graph_iri
        cg = ConjunctiveGraph(identifier=d_graph_iri)
        v = get_virtuoso(self.session, d_storage_name)
        v_main = get_virtuoso(self.session, self.discussion_storage_name())
        participant_ids = discussion.get_participants(True)
        profiles={URIRef(AgentProfile.uri_generic(id, local_uri))
                  for id in participant_ids}
        self.add_subject_data(v, cg, profiles)
        accounts = [account for ((account, p, profile), g)
                    in v_main.triples((None, SIOC.account_of, None))
                    if profile in profiles]
        self.add_subject_data(v, cg, accounts)
        return cg

    def discussion_as_quads(self, discussion_id):
        cg = self.discussion_as_graph(discussion_id)
        return cg.serialize(format='nquads')

    @staticmethod
    def get_jsonld_context(expand=False):
        server_uri = AppQuadStorageManager.local_uri()
        if not expand:
            return [context_url, {'local': server_uri}]
        with open(local_context_loc) as f:
            context = json.load(f)
        context["@context"]['local'] = server_uri
        return context

    def graph_as_jsonld(self, cg):
        context = self.get_jsonld_context()
        jsonld = cg.serialize(format='json-ld', context=context, indent=None)
        # json-ld serializer does strict CURIES, ie only one segment after
        # the prefix. We use local:Classname/ID, so do this by hand.
        # Make sure not to change the one in the context.
        jsonld = self.local_pattern.sub(r'local:\1', jsonld)
        return jsonld

    def as_jsonld(self, discussion_id):
        cg = self.discussion_as_graph(discussion_id)
        return self.graph_as_jsonld(cg)

    @staticmethod
    def quads_to_jsonld(quads):
        from pyld import jsonld
        context = AppQuadStorageManager.get_jsonld_context(True)
        jsonf = jsonld.from_rdf(quads)
        jsonc = jsonld.compact(jsonf, context)
        jsonc['@context'] = AppQuadStorageManager.get_jsonld_context(False)
        return jsonc

    def as_jsonld_old(self, discussion_id):
        quads = self.discussion_as_quads_old(discussion_id)
        return self.quads_to_jsonld(quads)
