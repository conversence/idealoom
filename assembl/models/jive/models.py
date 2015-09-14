import simplejson as json
from sqlalchemy import orm
from sqlalchemy.orm import (
    relationship,
    backref
)
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Text,
    String,
    DateTime
)

from ..generic import PostSource
from .api import AssemblJiveOAuth
from .setup import jive_redirect_url


class JiveSource(PostSource):
    __tablename__ = 'jive_source'
    __mapper_args__ = {
        'polymorphic_identity': 'jive_source',
    }

    id = Column(Integer, ForeignKey('post_source.id',
                onupdate='CASCADE', ondelete='CASCADE'),
                primary_key=True)

    instance_url = Column(String(256), nullable=False)
    # Group specific things
    # Internal JIVE instance ID
    group_id = Column(String(256), nullable=False)
    # PlaceID in the URL
    place_id = Column(String(256))
    json_data = Column(Text)
    settings = Column(Text)

    # UUID of an addon created for the discussion
    addon_uuid = Column(String(80))

    # Current state of assumption is that only a community manager
    # will be creating the group, and therefore their access token
    # will be used to gather data from Jive. Hence why access_tokens
    # are under the source object for Jive.
    #
    # This assumption could be changed in the future
    user_id = Column(Integer, ForeignKey('agent_profile.id',
                     onupdate='CASCADE', ondelete='CASCADE'))

    user = relationship('AgentProfile', backref=backref('jive_access_tokens'))
    # token data
    token_type = Column(String(60))
    access_token = Column(String(256))
    refresh_token = Column(String(256))
    expires = Column(DateTime)
    scope = Column(String(60))
    csfr_state = Column(String(256))

    def __init__(self, *args, **kwargs):
        super(JiveSource, self).__init__(*args, **kwargs)
        self.oauth_client = AssemblJiveOAuth(self)

    @orm.reconstructor
    def init_on_load(self):
        self.oauth_client = AssemblJiveOAuth(self)

    @property
    def oauth_authentication_url(self):
        if not self.oauth_client:
            self.oauth_client = AssemblJiveOAuth(self)
        return self.oauth_client.get_authentication_url()

    def get_client_info(self):
        if not self.settings:
            return None, None
        data = json.loads(self.settings)
        return data['clientId'], data['clientSecret']

    @property
    def oauth_redirect_url(self):
        from assembl.lib.frontend_urls import FrontendUrls
        fu = FrontendUrls(self.discussion)
        return fu.get_discussion_source_url(self.id) + jive_redirect_url


# Currently Incomplete representation of a Group JiveSource
class JiveGroupSource(JiveSource):
    __mapper_args__ = {
        'polymorphic_identity': 'jive_group_source',
    }
