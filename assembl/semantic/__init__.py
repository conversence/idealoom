"""package of semantic Web (RDF) modules.

Currently deprecated, as it is based on Virtuoso
and we gave up on that approach."""
from os import path

from rdflib import URIRef

REMOTE_ROOT = URIRef('http://purl.org/catalyst/')
context_url = REMOTE_ROOT + 'jsonld'
ontology_dir = path.abspath(path.join(path.dirname(__file__), 'ontology'))
local_context_loc = path.join(ontology_dir, 'context.jsonld')
DEFAULT_ROOT = ontology_dir + "/"

_jsonld_context = None

def jsonld_context(ontology_root=DEFAULT_ROOT):
    global _jsonld_context
    if _jsonld_context is None:
        from rdflib.plugins.shared.jsonld.context import Context
        _jsonld_context = Context(local_context_loc)
    return _jsonld_context
