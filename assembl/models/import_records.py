import logging

from sqlalchemy import (
    Column, ForeignKey, Integer, DateTime,
    UniqueConstraint, Unicode, Index)
from sqlalchemy.orm import relationship

from . import DiscussionBoundBase
# from .generic import ContentSource
from ..lib.generic_pointer import (
    UniversalTableRefColType, generic_relationship)


log = logging.getLogger(__name__)


class ImportRecord(DiscussionBoundBase):
    __tablename__ = 'import_record'
    __table_args__ = (
        UniqueConstraint('source_id', 'external_id'),
        UniqueConstraint('source_id', 'target_id', 'target_table'),
        Index('idx_import_record_target', 'target_id', 'target_table'))

    id = Column(Integer, primary_key=True)
    external_id = Column(Unicode, nullable=False)
    source_id = Column(Integer, ForeignKey("idea_source.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    last_import_time = Column(DateTime, server_default="now()")
    target_id = Column(Integer, nullable=False)
    target_table = Column(UniversalTableRefColType(), nullable=False)
    # data = Column(Text)  # Do we need the last import data? probably

    target = generic_relationship(target_table, target_id)

    def get_discussion_id(self):
        return self.source.discussion_id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        from .idea_source import IdeaSource
        if alias_maker is None:
            import_record = cls
            source = IdeaSource
        else:
            import_record = alias_maker.alias_from_class(cls)
            source = alias_maker.alias_from_relns(import_record.source)
        return ((import_record.source_id == source.id),
                (source.discussion_id == discussion_id))

    @property
    def external_uri(self):
        return self.source.external_id_to_uri(self.external_id)

    @external_uri.setter
    def external_uri(self, val):
        self.external_id = self.source.uri_to_external_id(val)

    def update(self, data):
        pass

    @classmethod
    def records_query(cls, target, source_id=None):
        q = target.db.query(cls).filter_by(
            target_id=target.id, target_table=target.base_tablename())
        if source_id:
            q = q.filter_by(source_id=None)
        return q
