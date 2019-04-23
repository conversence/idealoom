"""These are subclasses of :py:class:`.generic.Content` for web annotation"""
import logging

from sqlalchemy import Column, Integer, ForeignKey, DateTime

from .generic import Content
from ..lib.sqla_types import CoerceUnicode
from .langstrings import LangString, LangStringEntry, LocaleLabel

log = logging.getLogger(__name__)


class Webpage(Content):
    """A web page as a content type

    This allows web annotation with annotator_.

    .. _annotator: http://annotatorjs.org/
    """
    __tablename__ = "webpage"
    id = Column(
        Integer, ForeignKey(
            'content.id',
            ondelete='CASCADE'
        ), primary_key=True)
    url = Column(CoerceUnicode, unique=True)
    last_modified_date = Column(DateTime, nullable=True)
    # Should we cache the page content?

    __mapper_args__ = {
        'polymorphic_identity': 'webpage',
    }

    def get_body(self):
        return self.body

    def get_title(self):
        return LangString.create(self.url, LocaleLabel.NON_LINGUISTIC)

    @classmethod
    def get_instance(cls, uri, discussion_id, session=None):
        session = session or cls.default_db
        page = session.query(cls).filter_by(url=uri, discussion_id=discussion_id).first()
        if not page:
            page = cls(url=uri, discussion_id=discussion_id)
            session.add(page)
            session.flush()
        return page

    @classmethod
    def get_database_id(cls, identifier):
        log.error("Deprecated")
        page = cls.get_by(url=identifier)
        if page:
            return page.id
