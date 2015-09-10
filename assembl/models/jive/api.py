import requests


class OAuthCreator:
    token_route = '/oauth2/token'
    authorize_route = '/oauth2/authorize'

    def __init__(self, instance_route):
        if not isinstance(instance_route, basestring):
            raise TypeError("Cannot instantiate an OAuthCreator with input %s"
                            % instance_route)
        self.root = instance_route



class JiveAPI(object):
    prefix = '/core/api/v3'  # Add capability to change this on init
    routes = {
        'hello': 'www.jive.com/'
    }

    def __init__(self, server_address, port=None, oauth=None):
        pass

    def _make_call(endpoint, args, **kwargs):
        pass
