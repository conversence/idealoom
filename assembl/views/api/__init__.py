"""The classical API for IdeaLoom.

This is a RESTful API based on `cornice <https://cornice.readthedocs.io/en/latest/>`.
It should remain somewhat stable, and allows optimization of complex queries.
"""
import os

FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'static', 'js', 'tests', 'fixtures')
API_PREFIX = '/api/v1/'
API_DISCUSSION_PREFIX = API_PREFIX + 'discussion/{discussion_id:\d+}'
API_ETALAB_DISCUSSIONS_PREFIX = '/instances'


def instance_check_permission_id(request, permission, cls, id, **kwargs):
    assert id, "No id in instance request"
    instance = cls.get_instance(id)
    if not instance:
        request.errors.add('querystring', 'id', 'No such object exists')
        request.errors.status = 404
        return False
    if permission in request.base_permissions:
        return True
    if permission not in instance.local_permissions_req(request):
        request.errors.add("querystring", 'permissions', "Lacking permission "+permission)
        request.errors.status = 403
        return False
    return True


def instance_check_permission(request, permission, cls, **kwargs):
    return instance_check_permission_id(
        request, permission, cls, request.matchdict['id'])


def instance_check_op(request, op, cls, **kwargs):
    id = request.matchdict['id']
    assert id, "No id in instance request"
    instance = cls.get_instance(id)
    if not instance:
        request.errors.add('querystring', 'id', 'No such object exists')
        request.errors.status = 404
        return False
    if not instance.user_can_req(op, request):
        request.errors.add("querystring", 'permissions', "Not authorized "+op)
        request.errors.status = 403
        return False
    return True


def includeme(config):
    """ Initialize views and renderers at app start-up time. """

    config.add_route('csrf_token', 'api/v1/token')
    config.add_route('check_password_token',
                     'api/v1/check_password_token/{token}')
    config.add_route('mime_type', 'api/v1/mime_type')
    config.add_route('saml_metadata', 'api/v1/saml_metadata')
