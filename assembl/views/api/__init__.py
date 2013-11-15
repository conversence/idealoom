import os

from pyramid.security import Allow

from assembl.auth.models import DiscussionPermission


FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'static', 'js', 'tests', 'fixtures')
API_PREFIX = '/api/v1/'
API_DISCUSSION_PREFIX = API_PREFIX + 'discussion/{discussion_id}'


def acls(request):
    if request.matchdict and 'discussion_id' in request.matchdict:
        discussion_id = int(request.matchdict['discussion_id'])
        permissions = DiscussionPermission.db.query(
            DiscussionPermission).filter_by(
            discussion_id=discussion_id)
        acls = [(Allow, p.role.name, p.permission.name) for p in permissions]
        return acls
    return []

def includeme(config):
    """ Initialize views and renderers at app start-up time. """

    config.add_route('csrf_token', 'api/v1/token')
