from abc import ABCMeta

from requests_oauthlib import OAuth2Session


class AbstractJiveOAuth(OAuth2Session):
    """Abstract OAuth Communicator with Jive"""

    token_route = '/oauth2/token'
    authorize_route = '/oauth2/authorize'

    def __init__(self, jive_server, client_id, client_secret, *args, **kwargs):
        if not isinstance(jive_server, basestring):
            raise TypeError("Cannot instantiate an OAuthCreator \
                            with input %s" % jive_server)
        if (jive_server[-1] == '/'):
            jive_server = jive_server[:-1]
        self.root = jive_server
        full_auth_path, state = self.set_authentication_url(*args, **kwargs)
        self.full_authentication_path = full_auth_path
        self.full_token_path = self.set_token_path(*args, **kwargs)
        self.refresh_token = kwargs.get('refresh_token', None)
        access_token = kwargs.get('access_token', None)
        if access_token:
            access_token = {
                'access_token': access_token,
                'token_type': 'Bearer'
            }

        redirect_uri = kwargs.get('redirect_url', None)

        super(AbstractJiveOAuth, self).__init__(
            client_id=client_id,
            auth_refresh_url=self.full_token_path,
            token=access_token,
            redirect_uri=redirect_uri)

    def get_authentication_url(self):
        return self.full_authentication_path

    def set_authentication_url(self, *args, **kwargs):
        full_path = self.root + self.authorize_route
        return self.authorization_url(full_path)

    def set_token_path(self, *args, **kwargs):
        return self.root + self.token_route

    def get_token(self, *args, **kwargs):
        auth = (self.client_id, self.client_secret)
        code = kwargs.get('code', None)
        if code:
            token = self.ro.fetch_token(self.full_token_path,
                                        auth=auth, code=code)
            # Do things with the token
            return token

    def renew_token(self, *args, **kwargs):
        auth = (self.client_id, self.client_secret)
        new_token = None
        if self.refresh_token:
            new_token = self.ro.refresh_token(self.full_token_path,
                                              refresh_token=self.refresh_token,
                                              auth=auth)
        else:
            refresh_token = kwargs.get('refresh_token')
            new_token = self.ro.refresh_token(self.full_token_path,
                                              refresh_token=refresh_token,
                                              auth=auth)

        # do things with the new_token
        return new_token

    def api_call(self, method, url, data=None, headers=None, *args, **kwargs):
        self.ro.request(method, url, data, headers, **kwargs)


class AssemblJiveOAuth(AbstractJiveOAuth):
    """ The concrete Jive implementation to be used by Assembl
    The OAuth communicator between Jive and Assembl.
    """

    def __init__(self, source):
        server_path = source.instance_url
        client_id, client_secret = source.get_client_info()
        super(AssemblJiveOAuth, self).__init__(server_path,
                                               client_id, client_secret)


class JiveAPI(object):
    prefix = '/core/api/v3'  # Add capability to change this on init
    routes = {
        'hello': 'www.jive.com/'
    }

    def __init__(self, server_address, port=None, oauth=None):
        # self.oauth = OAuthCreator(server_address)
        pass

    def _get_nonexpired_tokens(self):
        pass

    def _make_call(endpoint, args, **kwargs):
        pass
