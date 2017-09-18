#!/usr/bin/python
"""Inference library based on FuXi"""
from __future__ import print_function
from builtins import object
from os import path
import logging
from abc import abstractmethod

import requests
from rdflib import Graph, URIRef, ConjunctiveGraph, RDF, RDFS, OWL
from rdflib.graph import ReadOnlyGraphAggregate

from . import jsonld_context, DEFAULT_ROOT

log = logging.getLogger(__name__)

CATALYST_RULES = [
    "cache/rdf-schema.ttl",
    "cache/owl.ttl",
    "cache/dcterms.ttl",
    "cache/foaf.ttl",
    "cache/sioc.ttl",
    "cache/sioc_arg.ttl",
    "cache/swan-sioc.ttl",
    "cache/openannotation.ttl",
    "catalyst_core.ttl",
    "catalyst_aif.ttl",
    "catalyst_ibis.ttl",
    # "catalyst_ibis_extra.ttl",
    "catalyst_idea.ttl",
    "catalyst_idea_extra.ttl",
    "catalyst_vote.ttl",
    "assembl_core.ttl",
    "situation.ttl",
    "version.ttl",
]


class GraphOverlay(ReadOnlyGraphAggregate):
    def __init__(self, base_graph, overlay=None):
        self.base_graph = base_graph
        if not overlay:
            if isinstance(base_graph, ConjunctiveGraph):
                overlay = ConjunctiveGraph()
            else:
                overlay = Graph()
        self.overlay = overlay
        super(GraphOverlay, self).__init__([self.overlay, base_graph])

    def add(self, triple):
        self.overlay.add(triple)

    def destroy(self, configuration):
        self.overlay.destroy(configuration)

    def commit(self):
        self.overlay.commit()

    def rollback(self):
        self.overlay.rollback()

    def addN(self, quads):
        self.overlay.addN(quads)

    def remove(self, triple):
        self.overlay.remove(triple)

    def __iadd__(self, other):
        return self.overlay.__iadd__(other)

    def __isub__(self, other):
        return self.overlay.__isub__(other)

    def contexts(self, triple=None):
        assert isinstance(self.base_graph, ConjunctiveGraph)
        for context in self.base_graph.contexts(triple):
            yield GraphOverlay(
                context, self.overlay.get_context(context.identifier))


class InferenceStore(object):
    def __init__(self, ontology_root=DEFAULT_ROOT):
        self.ontology_root = ontology_root

    def get_graph(self):
        return Graph()

    def clear_graph(self):
        graph = self.ontology
        if isinstance(graph, ConjunctiveGraph):
            ctxs = list(self.ontology.contexts())
            for ctx in ctxs:
                self.ontology.remove_context()
        else:
            triples = list(graph.triples((None, None, None)))
            for triple in triples:
                graph.remove(triple)
        assert not len(graph)

    def load_ontology(self, reload=False):
        self.ontology = self.get_graph()
        if reload:
            self.clear_graph()
        if not len(self.ontology):
            self.add_ontologies()

    def as_file(self, uri):
        if uri[0] != '/' and ':' not in uri:
            uri = self.ontology_root + uri
        if uri.startswith('http'):
            r = requests.get(uri)
            assert r.ok
            return r.content
        elif uri.startswith('/' or uri.startswith('file:')):
            if uri.startswith('file:'):
                uri = uri[5:]
            while uri.startswith('//'):
                uri = uri[1:]
            assert path.exists(uri), uri + " does not exist"
            return open(uri)
        else:
            raise ValueError

    def add_ontologies(self, rules=CATALYST_RULES):
        for r in rules:
            self.add_ontology(self.as_file(r))
            log.debug(r)

    def add_ontology(self, source, format='turtle'):
        self.ontology.parse(source, format=format)


    def ontology_classes(self):
        return [c for c in self.ontology.subjects(
            RDF.type, RDFS.Class) if isinstance(c, URIRef)]

    def getSubClasses(self, cls):
        return self.ontology.transitive_subjects(RDFS.subClassOf, cls)

    def getSuperClasses(self, cls):
        return self.ontology.transitive_objects(cls, RDFS.subClassOf)

    def getSubProperties(self, cls):
        return self.ontology.transitive_subjects(RDFS.subPropertyOf, cls)

    def getSuperProperties(self, cls):
        return self.ontology.transitive_objects(cls, RDFS.subPropertyOf)

    @abstractmethod
    def get_inference(self, graph):
        return graph


class SimpleInferenceStore(InferenceStore):
    """A simple inference engine that adds class closures"""
    def add_ontologies(self, rules=CATALYST_RULES):
        super(SimpleInferenceStore, self).add_ontologies(rules)
        self.base_ontology = self.ontology
        self.ontology = self.enrichOntology()
        ontology_root = self.ontology_root
        if ontology_root[:4] not in ('file', 'http'):
            ontology_root = 'file:' + ontology_root
        self.context = jsonld_context()

    def ontology_inheritance(self, base_classes=()):
        classes = self.ontology_classes()
        class_terms = {c: self.context.find_term(str(c)) for c in classes}
        class_terms = {c: t for (c, t) in class_terms.items() if t}
        inheritance = {}
        for cls, term in class_terms.items():
            super = self.getDirectSuperClasses(cls)
            super = [class_terms[k].name for k in super if k in class_terms]
            if super:
                inheritance[term.name] = super
        if base_classes:
            cache = {}
            def is_under_base(cls):
                if cls not in cache:
                    clsuri = URIRef(self.context.expand(cls))
                    for kls in self.getSuperClasses(clsuri):
                        klst = class_terms.get(kls, None)
                        if klst and klst.name in base_classes:
                            cache[cls] = True
                            break
                    else:
                        cache[cls] = False
                return cache[cls]
            inheritance = {cls: [k for k in supers if is_under_base(k)]
                           for (cls, supers) in inheritance.items()
                           if is_under_base(cls)}
            inheritance = {cls: supers for (cls, supers) in inheritance.items() if supers}
        return inheritance

    def combined_inheritance(self, base_inheritance):
        base_classes = set(base_inheritance.keys()).union(base_inheritance.values())
        inheritance = self.ontology_inheritance(base_classes)
        for base_cls, super_cls in base_inheritance.items():
            if base_cls in inheritance:
                ontology_supers = inheritance[base_cls]
                if super_cls not in ontology_supers:
                    import pdb; pdb.set_trace()
                    # super_cls is a subclass of (some) ontology supers?
                    def is_base_super(supc, subc):
                        while subc:
                            if supc == subc:
                                return True
                            subc = base_inheritance.get(subc, None)
                    inheritance[base_cls] = [supc for supc in ontology_supers if not is_base_super(supc, super_cls)]
                    # super_cls is a superclass of (any) ontology supers?
                    def is_onto_super(supc, subc):
                        if subc:
                            if supc == subc:
                                return True
                            return any((is_onto_super(supc, subsubc) for subsubc in inheritance.get(subc, ())))
                    if not any((is_onto_super(super_cls, subc) for subc in ontology_supers)):
                        inheritance[base_cls].append(super_cls)
            else:
                inheritance[base_cls] = [super_cls]
        return inheritance

    @staticmethod
    def addTransitiveClosure(graph, property):
        roots = set(graph.subjects(
            property, None))
        for r in roots:
            for o in list(graph.transitive_objects(r, property)):
                t = (r, property, o)
                if t not in graph:
                    graph.add(t)

    @staticmethod
    def addInstanceStatements(graph, root_class, sub_property):
        class_classes = set(graph.transitive_subjects(sub_property, root_class))
        class_classes.remove(root_class)
        classes = set()
        for class_class in class_classes:
            superclasses = set(graph.transitive_objects(class_class, sub_property))
            superclasses.remove(class_class)
            instances = graph.subjects(RDF.type, class_class)
            for instance in instances:
                for superclass in superclasses:
                    t = (instance, RDF.type, superclass)
                    if t not in graph:
                        graph.add(t)

    def enrichOntology(self):
        graph = self.rich_ontology = GraphOverlay(self.ontology)
        self.addTransitiveClosure(graph, RDFS.subPropertyOf)
        self.addTransitiveClosure(graph, RDFS.subClassOf)
        self.addInstanceStatements(graph, RDFS.Class, RDFS.subClassOf)
        self.addInstanceStatements(graph, RDF.Property, RDFS.subPropertyOf)
        return graph

    def add_inheritance(self, graph, root_class, sub_property):
        changes = False
        classes = self.ontology.subjects(RDF.type, root_class)
        for cls in classes:
            superclasses = set(self.ontology.transitive_objects(cls, sub_property))
            superclasses.remove(cls)
            for instance in graph.subjects(RDF.type, cls):
                for sup_cls in superclasses:
                    t = (instance, RDF.type, sup_cls)
                    if t not in graph:
                        changes = True
                        graph.add(t)
        return changes

    def add_inverses(self, graph):
        changes = False
        for (p1, _, p2) in self.ontology.triples(
                (None, OWL.inverseOf, None)):
            for (s, p, o) in graph.triples((None, p1, None)):
                t = (o, p2, s)
                if t not in graph:
                    graph.add(t)
                    changes = True
            for (s, p, o) in graph.triples((None, p2, None)):
                t = (o, p1, s)
                if t not in graph:
                    graph.add(t)
                    changes = True
        return changes

    def get_inference(self, graph):
        composite = GraphOverlay(graph)
        if isinstance(graph, ConjunctiveGraph):
            for g in composite.contexts():
                self.calc_inference(g)
        else:
            self.calc_inference(composite)
        return composite

    def calc_inference(self, graph):
        first = changes = True
        while first or changes:
            if first or changes:
                # {?P @has owl:inverseOf ?I. ?S ?P ?O} => {?O ?I ?S}.
                changes = self.add_inverses(graph)
            if first or changes:
                # {?P @has rdfs:subPropertyOf ?R. ?S ?P ?O} => {?S ?R ?O}.
                # {?P @has owl:subPropertyOf ?R. ?S ?P ?O} => {?S ?R ?O}.
                changes = self.add_inheritance(graph, RDF.Property, RDFS.subPropertyOf)
            first = False
            # loop because inheritance could add inverses.
        # {?P @has rdfs:domain ?C. ?S ?P ?O} => {?S a ?C}.
        for (p, _, c) in self.ontology.triples((None, RDFS.domain, None)):
            rs = {s for (s, _, o) in graph.triples((None, p, None))}
            for r in rs:
                t = (r, RDF.type, c)
                if t not in graph:
                    graph.add(t)
        # {?P @has rdfs:range ?C. ?S ?P ?O} => {?O a ?C}.
        for (p, _, c) in self.ontology.triples((None, RDFS.range, None)):
            rs = {o for (s, _, o) in graph.triples((None, p, None))}
            for r in rs:
                t = (r, RDF.type, c)
                if t not in graph:
                    graph.add(t)
        self.add_inheritance(graph, RDFS.Class, RDFS.subClassOf)

    def getDirectSubClasses(self, cls):
        return self.base_ontology.subjects(RDFS.subClassOf, cls)

    def getDirectSuperClasses(self, cls):
        return self.base_ontology.objects(cls, RDFS.subClassOf)

    def getDirectSubProperties(self, cls):
        return self.base_ontology.subjects(RDFS.subPropertyOf, cls)

    def getDirectSuperProperties(self, cls):
        return self.base_ontology.objects(cls, RDFS.subPropertyOf)

    def cls_to_ctx(self, cls):
        t = self.context.find_term(str(cls))
        if t:
            return t.name

    def getSubClassesCtx(self, cls):
        cls = URIRef(self.context.expand(cls))
        return list(filter(None, [
            self.cls_to_ctx(cls) for cls in self.getSubClasses(cls)]))

    def getSuperClassesCtx(self, cls):
        cls = URIRef(self.context.expand(cls))
        return list(filter(None, [
            self.cls_to_ctx(cls) for cls in self.getSuperClasses(cls)]))


class FuXiInferenceStore(InferenceStore):
    def __init__(self, ontology_root=DEFAULT_ROOT, use_owl=False):
        from FuXi.Horn.HornRules import HornFromN3
        from FuXi.Rete.Util import generateTokenSet
        from FuXi.Rete.RuleStore import SetupRuleStore
        # from FuXi.Rete.Network import ReteNetwork
        # from FuXi.Horn import (
        #    DATALOG_SAFETY_NONE, DATALOG_SAFETY_STRICT, DATALOG_SAFETY_LOOSE)
        # from FuXi.Horn.HornRules import NetworkFromN3, HornFromDL
        super(FuXiInferenceStore, self).__init__(ontology_root)
        (self.rule_store, self.rule_graph, self.network) = SetupRuleStore(
            makeNetwork=True)
        self.use_owl = use_owl
        rulesets = ['cache/rdfs-rules.n3']
        if self.use_owl:
            # Does not work yet
            rulesets.append('cache/owl-rules.n3')
        for ruleset in rulesets:
            for rule in HornFromN3(self.as_file(ruleset)):
                self.network.buildNetworkFromClause(rule)

    def get_inference(self, graph):
        network = self.network
        network.reset()
        network.feedFactsToAdd(generateTokenSet(self.ontology))
        log.debug("ontology loaded")
        network.feedFactsToAdd(generateTokenSet(graph))
        return network.inferredFacts


_base_inference_store = None

def get_inference_store():
    global _base_inference_store
    if _base_inference_store is None:
        _base_inference_store = SimpleInferenceStore()
        _base_inference_store.load_ontology()
    return _base_inference_store


if __name__ == '__main__':
    f = FuXiInferenceStore(LOCAL_ROOT)
    f.add_ontologies()
    eg = ConjunctiveGraph()
    eg.parse('/Users/maparent/OpenSource/assembl-feature/personal/d1.rdf')
    cl = f.get_inference(eg)
    print(list(cl.triples((None, RDF.type, None))))
