from sqlalchemy.orm import relationship, backref
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Text,
    String,
    DateTime
)

from .. import Base
from ..generic import PostSource


# Currently Incomplete representation of a JiveSource
class JiveGroupSource(PostSource):
    __tablename__ = 'jive_group_source'
    __mapper_args__ = {
        'polymorphic_identity': 'jive_group_source',
    }

    id = Column(Integer, ForeignKey('post_source.id',
                onupdate='CASCADE', ondelete='CASCADE'),
                primary_key=True)
    # Internal JIVE instance ID
    group_id = Column(String(256), nullable=False)
    # PlaceID in the URL
    place_id = Column(String(256))
    json_data = Column(Text)
    settings = Column(Text)
    addon_uuid = Column(String(80))


class JiveAccessToken(Base):
    __tablename__ = 'jive_access_token'
    id = Column(Integer, primary_key=True)
    token_type = Column(String(60))
    access_token = Column(String(256), nullable=False)
    refresh_token = Column(String(256))
    expires = Column(DateTime)
    scope = Column(String(60))


class JiveUserTokens(Base):
    __tablename__ = 'jive_user_tokens'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('agent_profile.id',
                     onupdate='CASCADE', ondelete='CASCADE'))
    user = relationship('AgentProfile', backref=backref('jive_access_tokens'))
    token_id = Column(Integer, ForeignKey('jive_access_token.id',
                      onupdate='CASCADE', ondelete='CASCADE'))
    token = relationship(JiveAccessToken)
