from os.path import join, dirname
# from virtuoso.vmapping import IriClass, PatternIriClass


context_url = 'http://purl.org/catalyst/jsonld'
ontology_dir = join(dirname(__file__), 'ontology')
local_context_loc = join(ontology_dir, 'context.jsonld')


def upgrade_semantic_mapping():
    from assembl.lib.sqla import using_virtuoso
    if using_virtuoso():
        from .virtuoso_mapping import AssemblQuadStorageManager
        aqsm = AssemblQuadStorageManager()
        aqsm.update_all_storages()


def reset_semantic_mapping():
    from assembl.lib.sqla import using_virtuoso
    if using_virtuoso():
        from .virtuoso_mapping import AssemblQuadStorageManager
        aqsm = AssemblQuadStorageManager()
        aqsm.drop_all()
        aqsm.update_all_storages()


# placeholders

class IriClass(object):
    def __init__(self, *args, **kwargs):
        pass

    def apply(self, *args):
        pass


class PatternIriClass(IriClass):
    pass


class QuadMapPatternS(object):
    def __init__(
            self, subject=None, predicate=None, obj=None, graph_name=None,
            name=None, conditions=None, nsm=None, sections=None,
            exclude_base_condition=False):
        pass

USER_SECTION=None
PRIVATE_USER_SECTION=None

class AssemblQuadStorageManager(object):
    def local_uri(self):
        return None
