from builtins import object
from datetime import datetime
import logging

from sqlalchemy import (
    Column, ForeignKey, Integer, DateTime, Table,
    UniqueConstraint, Unicode, String, Boolean,
    CheckConstraint, event, Index, func)
from sqlalchemy.orm import relationship, reconstructor
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
from .auth import IdentityProvider, AgentProfile
from .langstrings import LangString
from .social_auth import SocialAuthAccount
from .annotation import Webpage
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

    __mapper_args__ = {
        'polymorphic_identity': 'hypothesis_source',
    }

    def __init__(self, *args, **kwargs):
        kwargs['source_uri'] = kwargs.pop('source_uri', 'https://hypothes.is/api/')
        super(HypothesisExtractSource, self).__init__(*args, **kwargs)

    def class_from_data(self, data):
        return Extract

    def init_importer(self):
        super(HypothesisExtractSource, self).init_importer()
        self.hypothesis_provider = IdentityProvider.get_by_type("Hypothesis")

    def read(self, admin_user_id=None):
        self.init_importer()
        self.load_previous_records()
        if not self.api_key:
            raise ClientError("Missing the api key")
        admin_user_id = admin_user_id or self.discussion.creator_id
        headers={"Authorization": "Bearer "+self.api_key}
        uri = self.source_uri + "search"
        (latest,) = self.db.query(func.max(ImportRecord.last_import_time)
            ).filter_by(source_id=self.id).first()
        params = {'sort': 'updated', 'order': 'asc'}
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
                params['search_after'] = latest.isoformat()+"Z"
            result = requests.get(uri, params=params, headers=headers)
            if not result.ok:
                raise ReaderError()
            rows = result.json().get('rows', None)
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

    def process_data(self, data):
        uri = data['uri']
        page = self[uri]
        if page is None:
            page = Webpage.get_instance(uri, self.discussion_id)
            self[uri] = page
        name = data.get("user_info", {}).get("display_name", None)
        doc_title = data.get('document', {}).get('title', [None])[0]
        if not page.subject:
            if page.subject is not None:
                page.subject.delete()
            page.subject = LangString.create(doc_title)
        external_url = data.get('links', {}).get('incontext', None)
        account_id = data['user']
        account = self[account_id]
        if account is None:
            accounts = self.db.query(SocialAuthAccount
                ).filter_by(
                    uid=account_id,
                    provider_id=self.hypothesis_provider.id).first()
            if account is None:
                profile = AgentProfile(name=name)
                account = SocialAuthAccount(
                    uid=account_id, identity_provider=self.hypothesis_provider,
                    profile=profile, verified=True)
                self.db.add(account)
                self.db.flush()
            self[account_id] = account.profile
        targets = data.get('target', [])
        if not targets:
            log.error("Empty targets in hypothesis")
            return
        if len(targets) > 1:
            log.warning("Multiple targets in hypothesis")
        target = targets[0]
        tselectors = target.get('selector', [])
        quote = None
        selectors = []
        for selector in tselectors:
            stype = selector["type"]
            if stype == "TextQuoteSelector":
                quote = selector.get('exact', None)
                selectors.append({
                    "@type": "TextQuoteSelector",
                    "prefix": selector['prefix'],
                    "suffix": selector['suffix'],
                    "body": selector['exact'],
                })
            elif stype == "RangeSelector":
                selectors.append({
                    "@type": "RangeSelector",
                    "end": selector['endContainer'],
                    "endOffset": selector['endOffset'],
                    "start": selector['startContainer'],
                    "startOffset": selector['startOffset'],
                })
            elif stype == "TextPositionSelector":
                selectors.append({
                    "@type": "TextPositionSelector",
                    "end": selector['end'],
                    "start": selector['start'],
                })
            elif stype == "FragmentSelector":
                selectors.append({
                    "@type": "FragmentSelector",
                    "value": selector['value'],
                })

        return {
            "@type": "Excerpt",
            "idPost": uri,
            "idCreator": account_id,
            "external_url": external_url,
            "text": data.get('text', None),
            "ranges": selectors,
        }
