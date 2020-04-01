from pyramid.view import view_config

from ..traversal import (InstanceContext, CollectionContext)
from . import instance_del, instance_put_json, collection_add_json, JSON_HEADER
from assembl.models import (Idea, IdeaContentLink)


@view_config(context=InstanceContext, request_method='DELETE', renderer='json',
             ctx_instance_class=IdeaContentLink)
def icl_instance_del(request):
    print("icl_instance_del")
    ctx = request.context
    instance = ctx._instance
    idea = instance.idea
    result = instance_del(request)
    # assume permissions taken care of there
    idea.send_to_changes()
    for ancestor in idea.get_all_ancestors():
        ancestor.send_to_changes()
    return result


@view_config(context=InstanceContext, request_method=('PATCH', 'PUT'),
             header=JSON_HEADER, ctx_instance_class=IdeaContentLink, renderer='json')
def icl_instance_put(request):
    print("icl_instance_put")
    ctx = request.context
    instance = ctx._instance
    old_idea = instance.idea
    result = instance_put_json(request)
    # assume permissions taken care of there
    new_idea = instance.idea
    if new_idea != old_idea:
        old_ancestors = set()
        new_ancestors = set()
        old_ancestors.add(old_idea)
        old_ancestors.update(old_idea.get_all_ancestors())
        new_ancestors.add(new_idea)
        new_ancestors.update(new_idea.get_all_ancestors())
        for ancestor in new_ancestors ^ old_ancestors:
            ancestor.send_to_changes()
    return result


@view_config(context=CollectionContext, request_method='POST',
             header=JSON_HEADER, ctx_collection_class=IdeaContentLink)
def icl_collection_add(request):
    print("icl_collection_add")
    result = collection_add_json(request)
    # assume permissions taken care of there
    # easier to get from request
    idea_id = request.json.get('idIdea', None)
    if idea_id:
        idea = Idea.get_instance(idea_id)
        if idea:
            idea.send_to_changes()
            for ancestor in idea.get_all_ancestors():
                ancestor.send_to_changes()
    return result
