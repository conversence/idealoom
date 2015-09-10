# from sqlalchemy.orm import relationship, backref
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Text,
    String
)

# from .. import Base
from ..generic import PostSource


# # May want to add the access token information in here as well
# class JiveAddonSettings(Base):
#     __tablename__ = 'jive_addon_settings'
#     id = Column(Integer, primary_key=True)
#     source_id = Column(Integer, ForeignKey('jive_group_source.id',
#                        onupdate='CASCADE', ondelete='CASCADE'),
#                        nullable=False)

#     source = relationship('JiveGroupSource',
#                           backref=backref('setting', uselist=False))

#     # JSON object that is passed from JIVE upon add-on registration
#     # (via the register_url field of the add-on.
#     # See ./setup/__init__.py for more information
#     json_data = Column(Text, nullable=False)

#     def get_discussion_id(self):
#         return super(JiveAddonSettings, self).get_discussion_id()

#     # Copy/pasted from ContentSource. Is this even remotely correct?
#     @classmethod
#     def get_discussion_conditions(cls, discussion_id, alias_maker=None):
#         return (cls.discussion_id == discussion_id,)


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
