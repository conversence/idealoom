from builtins import object
from datetime import datetime
import logging

from sqlalchemy import (
    Column, ForeignKey, Integer, DateTime, Table,
    UniqueConstraint, Unicode, String, Boolean,
    CheckConstraint, event, Index, func)
from sqlalchemy.orm import relationship
from future.utils import string_types
import simplejson as json
from rdflib_jsonld.context import Context
from pyramid.threadlocal import get_current_registry
import requests

from . import DiscussionBoundBase, Base
from .generic import ContentSource
from ..lib.parsedatetime import parse_datetime
from ..lib.sqla import get_named_class, get_named_object
from ..lib.generic_pointer import (
    UniversalTableRefColType, generic_relationship)
from ..lib.utils import get_global_base_url
from ..semantic import jsonld_context
from ..tests.utils import PyramidWebTestRequest
from .idea_content_link import Extract
from .import_record_source import ImportRecord, ImportRecordSource
from ..tasks.source_reader import ClientError, ReaderError


log = logging.getLogger(__name__)


class HypothesisExtractSource(ImportRecordSource):
    __tablename__ = 'hypothesis_extract_source'
    id = Column(Integer, ForeignKey(ImportRecordSource.id), primary_key=True)
    api_key = Column(String)
    # search criteria
    user = Column(String)
    group = Column(String)
    tag = Column(Unicode)
    document_url = Column(Unicode)

    def __init__(self, *args, **kwargs):
        kwargs['source_uri'] = kwargs.pop('source_uri', 'https://hypothes.is/api/')
        super(HypothesisExtractSource, self).__init__(*args, **kwargs)

    __mapper_args__ = {
        'polymorphic_identity': 'hypothesis_source',
    }

    def class_from_data(self):
        return Extract

    def read(self, admin_user_id=None):
        if not self.api_key:
            raise ClientError("Missing the api key")
        admin_user_id = admin_user_id or self.discussion.creator_id
        headers={"Authorization": "Bearer "+self.api_key}
        uri = self.source_uri + "search"
        (latest,) = db.query(func.max(models.ImportRecord.last_import_time)).filter_by(source_id=self.id).first()
        params = {}
        if self.user:
            params['user'] = 'acct:' + self.user
        if self.group:
            params['group'] = self.group
        if self.tag:
            params['tag'] = self.tag
        if self.document_url:
            params['uri'] = self.document_url
        while True:
            if latest:
                params['search_after'] = latest.isoformat()
                params['order'] = asc
            result = requests.get(uri, params=params, headers=headers)
            if not result.ok:
                raise ReaderError()
            extracts = self.rows
            if not rows:
                break
            latest = parse_datetime(max([x['updated'] for x in rows]))
            self.read_data_gen(rows, admin_user_id, True)
        self.db.flush()

    def id_from_data(self, data):
        if isinstance(data, dict):
            data = data.get('id', None)
        if isinstance(data, string_types):
            return data
