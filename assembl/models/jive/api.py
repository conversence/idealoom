import requests
from .models import JiveAccessToken, JiveUserTokens

class __JiveOAuth:
    """The Jive Oauth Client"""
    _instance = None
    token_route = '/oauth2/token'
    authorize_route = '/oauth2/authorize'

    def __init__(self, instance_route, client_id, client_secret):
        if not isinstance(instance_route, basestring):
            raise TypeError("Cannot instantiate an OAuthCreator \
                            with input %s" % instance_route)
        self.root = instance_route

    def auth_code_grant(self, auth_code, user_name, password, client_id):
        payload = {
            'code': auth_code,
            'grant_type': 'authorization_code',
            'client_id': client_id
        }
        resp = requests.post(self.root + __JiveOAuth.token_route,
                             auth=(user_name, password),
                             data=payload
                             )
        # Parse the response. Update the db ?
        return resp

    def resource_owned_cred_grant(self, user_name, password,
                                  client_id, client_secret):
        payload = {
            'grant_type': 'password',
            'username': user_name,
            'password': password
        }
        resp = requests.post(self.root + __JiveOAuth.token_route,
                             auth=(client_id, client_secret),
                             data=payload)
        # parse the response, update db ?
        return resp

    def refresh_token(self, client_id, client_secret, refresh_access_token):
        payload = {
            'refresh_token': refresh_access_token,
            'grant_type': 'refresh_token'
        }
        resp = requests.post(self.root + __JiveOAuth.token_route,
                             auth=(client_id, client_secret),
                             data=payload)
        # parse and update db?
        return resp


def OAuthCreator(*args, **kwargs):
    if not __JiveOAuth._instance:
        __JiveOAuth._instance = __JiveOAuth(*args, **kwargs)
    return __JiveOAuth._instance


class JiveAPI(object):
    prefix = '/core/api/v3'  # Add capability to change this on init
    routes = {
        'hello': 'www.jive.com/'
    }

    def __init__(self, server_address, port=None, oauth=None):
        self.oauth = OAuthCreator(server_address)

    def _get_nonexpired_tokens(self):
        pass


    def _make_call(endpoint, args, **kwargs):
        pass
