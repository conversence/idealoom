#!/usr/bin/python
"""Inference library based on FuXi"""
from __future__ import print_function
from builtins import object
from os import path
import logging
from abc import abstractmethod

import requests
from rdflib import Graph, URIRef, ConjunctiveGraph, RDF, RDFS, OWL


REMOTE_ROOT = URIRef('http://purl.org/catalyst/')
DEFAULT_ROOT = path.abspath(path.join(path.dirname(__file__), 'ontology')) + "/"
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
    # "catalyst_idea_extra.ttl",
    "catalyst_vote.ttl",
    "assembl_core.ttl",
    "version.ttl",
]


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

    @abstractmethod
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
        self.enrichOntology()

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
        graph = self.ontology
        self.addTransitiveClosure(graph, RDFS.subPropertyOf)
        self.addTransitiveClosure(graph, RDFS.subClassOf)
        self.addInstanceStatements(graph, RDFS.Class, RDFS.subClassOf)
        self.addInstanceStatements(graph, RDF.Property, RDFS.subPropertyOf)

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
        if isinstance(graph, ConjunctiveGraph):
            for g in graph.contexts():
                self.get_inference(g)
            return
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


if __name__ == '__main__':
    f = FuXiInferenceStore(LOCAL_ROOT)
    f.add_ontologies()
    eg = ConjunctiveGraph()
    eg.parse('/Users/maparent/OpenSource/assembl-feature/personal/d1.rdf')
    cl = f.get_inference(eg)
    print(list(cl.triples((None, RDF.type, None))))
