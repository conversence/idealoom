"""Utilities for extracting posts and from a RSS or Atom feed."""
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import object
from io import StringIO
from importlib import import_module
from datetime import datetime
from calendar import timegm
import logging

from future.utils import string_types
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
 )
from pyisemail import is_email
import feedparser
import requests
from urllib.parse import urlparse, quote_plus

from ..lib.sqla_types import URLString
from .langstrings import LangString, LocaleLabel
from .generic import PostSource
from .post import ImportedPost
from .auth import AbstractAgentAccount, AgentProfile
from ..tasks.source_reader import PullSourceReader, ReaderError, ReaderStatus


log = logging.getLogger(__name__)


class FeedFetcher(object):
    """
    A thin wrapper around requests in order to be able to get a feed from a
    web resource address, returning either as a string object (which is the
    preferred method for feedparser) or as a StringIO object (which is what
    speedparser likes)
    """

    def return_string(self, uri):
        """Returns the string content with the xml inside"""
        resp = requests.get(uri)
        return resp.content

    def return_file(self, uri):
        """Returns a StringIO with the xml inside"""
        output = StringIO()
        resp = requests.get(uri)
        output.write(resp.content)
        return output


class ParserWrapper(object):
    """
    A moderate wrapper around which parsing module is used (feedparser vs
    speedparser).
    """

    def __init__(self, fetcher, parser, parser_can_read_file=False):
        self.fetcher = fetcher
        self.parser = parser
        self.parser_can_read_file = parser_can_read_file

    def parse(self, uri):
        if self.parser_can_read_file:
            return self.parser.parse(self.fetcher.return_file(uri))
        else:
            return self.parser.parse(self.fetcher.return_string(uri))


class ParsedData(object):
    """
    For every atom feed URL that is fetched, a ParsedData object is generated
    to handle the retrieving the feed, the entries, or other fields as needed.
    This object is the base "Data Getter" object for atom feeds.

    @TODO: Extend this class to suport RRS feeds as well.
    """

    def __init__(self, url, parser_wrapper=None):
        self.url = url
        self._parse_agent = parser_wrapper or \
            ParserWrapper(FeedFetcher(), feedparser)
        self._feed = None

    def _fetch_source(self):
        if not self._feed:
            self._feed = self._parse_agent.parse(self.url)

    def _update_feed(self,url):
        self._feed = self._parse_agent.parse(url)

    def refetch_source(self):
        self._feed = self._parse_agent.parse(self.url)

    def get_parsed_feed(self):
        """Returns the entire parsed feed as a dict"""
        self._fetch_source()
        return self._feed

    def get_feed(self):
        """Returns feed summary from entire parsed feed as list"""
        self._fetch_source()
        return self.get_parsed_feed()['feed']

    # Does not update the source
    def get_feed_forced(self,url):
        return self._parse_agent.parse(url)

    def get_feed_title(self):
        return self.get_feed()['title']

    def get_entries(self):
        self._fetch_source()
        return iter(self.get_parsed_feed()['entries'])


class PaginatedParsedData(ParsedData):
    """
    Extention of the "Data Getter" object, which supports basic pagination of
    data.

    @TODO: Extend this object to support variable key pagination, rather than
    simple integer incrementation.
    """
    def __init__(self, url, parser_wrapper=None,
                 page_key='page', start_page=1):
        self.page_number = start_page
        self.page_key = page_key
        self.url = url
        self._new_source_fetched = False
        self._parse_wrapper = parser_wrapper or \
            ParserWrapper(FeedFetcher(), feedparser)
        super(PaginatedParsedData, self).__init__(url, self._parse_wrapper)

    def _check_empty_entries(self, feed):
        """Checks if the currently fetched feed has any entries or not"""
        return feed['entries'] == []

    def _update_url(self):
        """The method updates the url to update the concept of 'next page'.
        It will call _append_pagination_to_url.

        @override this to implement specific logic"""
        next = self.page_number
        while True:
            next_url = self.url + "?" + self.page_key + "=" + str(next)
            next += 1
            yield next_url

    def get_next_feed(self):
        for url in self._update_url():
            feed = super(PaginatedParsedData, self).get_feed_forced(url)
            self._feed = feed
            if feed['entries'] == []:
                raise StopIteration
            yield feed

    def _get_entry_per_feed(self, feed):
        return iter(feed['entries'])

    def reset(self):
        self.page_number = 1

    def get_entries(self):
        for feed in self.get_next_feed():
            for entry in self._get_entry_per_feed(feed):
                yield entry


class FeedPost(ImportedPost):
    """
    A discussion post that is imported from an external feed source.
    """
    __mapper_args__ = {
        'polymorphic_identity': 'feed_imported_posts',
    }


class LoomioFeedPost(FeedPost):
    """
    A discussion post this is imported from a feed extracted from Loomio.
    """

    __mapper_args__ = {
        'polymorphic_identity': 'loomio_feed_post'
    }


class WebLinkAccount(AbstractAgentAccount):
    """
    An imported name that has not been validated nor authenticated
    within the platform. This is to keep track of an imported post's ownership.
    """
    __tablename__ = 'weblink_user'

    id = Column(Integer, ForeignKey(
                'abstract_agent_account.id',
                onupdate='CASCADE',
                ondelete='CASCADE'), primary_key=True)

    user_link = Column(URLString, unique=True)

    __mapper_args__ = {
        'polymorphic_identity': 'weblink_user'
    }

    def get_user_link(self):
        return self.user_link

    def unique_query(self):
        # Uniqueness does not care about subclasses,
        # so query on this class rather than self's class.
        return self.db.query(WebLinkAccount).filter_by(
            user_link=self.user_link), True


class LoomioAccount(WebLinkAccount):
    """
    An imported Loomio name and address. This is not an authenticated user.
    """
    __mapper_args__ = {
        'polymorphic_identity': 'loomio_user'
    }


class FeedPostSource(PostSource):
    """
    The source of an imported feed, be it Atom, RSS, or any other type of feed
    protocol.
    """
    __tablename__ = 'feed_posts_source'

    id = Column(Integer, ForeignKey(
                'post_source.id',
                ondelete='CASCADE',
                onupdate='CASCADE'), primary_key=True)

    url = Column(URLString, nullable=False)

    # For parameter free calling to parse posts from this source.
    parser_full_class_name = Column(String(512), nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'feed_posts_source'
    }

    post_type = FeedPost # for db querying
    user_type = WebLinkAccount

    def make_reader(self):
        return FeedSourceReader(self.id)

    @classmethod
    # eg. create_from(d, "www...xml", "A valid name", PaginatedFeedParser)
    def create_from(cls, discussion, url, source_name, parse_config_class):
        encoded_name = source_name
        encoded_url = url
        created_date = datetime.utcnow()
        parser_name = str(parse_config_class).split("'")[1]
        return cls(name=encoded_name, creation_date=created_date,
                   discussion=discussion, url=encoded_url,
                   parser_full_class_name=parser_name)

    def send_post(self, post):
        #TODO?
        log.warn("TODO?: FeedPostSource::send_post():  Actually send the post")

    def generate_message_id(self, source_post_id):
        # Feed post ids are supposed to be globally unique.
        # They may or may not be emails.
        if isinstance(source_post_id, string_types) and is_email(source_post_id):
            return source_post_id
        # Invalid source_post_id.
        return "%s_feed@%s" % (
            self.flatten_source_post_id(str(source_post_id), 5),
            urlparse(self.url).hostname)


class LoomioPostSource(FeedPostSource):
    """
    The source an imported feed, that came directly from Loomio.
    """
    __mapper_args__ = {
        'polymorphic_identity': 'feed_posts_source_loomio'
    }

    post_type = LoomioFeedPost
    user_type = LoomioAccount

    def make_reader(self):
        return LoomioSourceReader(self.id)

    def send_post(self, post):
        #TODO?
        log.warn("TODO?: LoomioPostSource::send_post():  Actually send the post")


class FeedSourceReader(PullSourceReader):

    def __init__(self, source_id):
        super(FeedSourceReader,self).__init__(source_id)
        self._parse_agent = None

    def do_read(self):
        self._check_parser_loaded()
        if self.reimporting:
            self._re_import()
        else:
            self._add_entries()

    def _re_import(self, discussion=None):
        sess = self.source.db
        for entry in self._parse_agent.get_entries():
            try:
                post_id = self._get_entry_id(entry)
                user_link = self._get_author_link(entry)
                persisted_post = self._return_existing_post(post_id)
                account = self._create_account_from_entry(entry)
                other_account = account.find_duplicate(True, True)
                if other_account is not account and other_account is not None:
                    account = other_account
                    self._process_reimport_user(entry, account)
                else:
                    sess.add(account)

                if persisted_post is not None:
                    self._process_reimport_post(entry, persisted_post, discussion)
                    persisted_post.creator = account.profile
                    sess.commit()
                else:
                    persisted_post = self._convert_to_post(entry, account)
                    sess.add(persisted_post)
                sess.commit()
                self.handle_new_content(persisted_post)
            except Exception as e:
                sess.rollback()
                raise ReaderError(e)
            finally:
                self.source = FeedPostSource.get(self.source_id, sess)
            if self.status != ReaderStatus.READING:
                break

    def _process_reimport_post(self, entry, post, discussion=None):
        post.import_date = datetime.utcnow()
        post.source_post_id = self._get_entry_id(entry)
        post.source = self.source
        post.body_mime_type = self._get_body_mime_type(entry)
        post.creation_date = self._get_creation_date(entry)
        post.subject = self._get_subject(entry)
        post.body = self._get_body(entry)

    def _process_reimport_user(self, entry, user, user_desc=None):
        if not user.profile.name:
            user.profile.name = self._get_author(entry)
        if not user.profile.description:
            user.profile.description = \
                user_desc if not None else user.profile.description

    def _add_entries(self):
        for post, account in self._generate_post_stream():
            try:
                if not account.find_duplicate(True, True):
                    self.source.db.add(account)
                if not post.find_duplicate(True, True):
                    self.source.db.add(post)
                self.source.db.commit()
                self.handle_new_content(post)
            except Exception as e:
                self.source.db.rollback()
                raise ReaderError(e)
            finally:
                self.source = FeedPostSource.get(self.source_id, self.source.db)

    def _check_parser_loaded(self):
        if not self._parse_agent:
            module, parse_cls = \
                tmp =  self.source.parser_full_class_name.rsplit(".",1)
            mod = import_module(module)
            tmp = getattr(mod, parse_cls)
            self._parse_agent = tmp(self.source.url)

    def _create_account_from_entry(self, entry):
        author_name = self._get_author(entry)
        author_link = self._get_author_link(entry)
        agent_profile = AgentProfile(name=author_name)
        return self.source.user_type(user_link=author_link, profile=agent_profile)

    def _generate_post_stream(self):
        self._check_parser_loaded()
        for entry in self._parse_agent.get_entries():
            account = self._create_account_from_entry(entry)
            account = account.get_unique_from_db()
            yield self._convert_to_post(entry, account), account
            if self.status != ReaderStatus.READING:
                break

    def _return_existing_post(self, post_id):
        cls = self.source.post_type
        return self.source.db.query(cls).\
            filter_by(source_post_id=post_id, source_id=self.source_id).first()

    def _get_title_from_feed(self):
        self._check_parser_loaded()
        return self._parse_agent.get_feed_title()

    def _get_creation_date(self, entry):
        return datetime.fromtimestamp(timegm(entry['updated_parsed']))

    def _get_entry_id(self, entry):
        return entry['id']

    def _get_body_mime_type(self, entry):
        content = entry.get('content', None)
        if content:
            return content[0]['type']
        return 'text/html'  # assumed when rss

    def _get_subject(self, entry):
        return LangString.create(entry['title'])

    def _get_body(self, entry):
        body = entry.get('content', None)
        if body:
            body = body[0]
            language = body.get('language', None)
            if not language or language.lower() == 'none':
                language = LocaleLabel.UNDEFINED
            return LangString.create(body['value'], language)
        else:
            body = entry.get('description', None)
            if body:
                return LangString.create(body)
        raise RuntimeError("could not find description for entry ", entry)

    def _get_author(self, entry):
        return entry['author']

    def _get_author_link(self, entry):
        if 'author_detail' in entry and 'href' in entry['author_detail']:
            return entry['author_detail']['href']
        return "%s#%s" % (self.source.url, self._get_author(entry))

    def _convert_to_post(self, entry, account):
        source_post_id = self._get_entry_id(entry)
        source = self.source
        body_mime_type = self._get_body_mime_type(entry)
        subject = self._get_subject(entry)
        body = self._get_body(entry)
        imported_date = datetime.utcnow()

        user = account.profile
        # TODO AY: Can we get the locale?

        return source.post_type(
            creation_date=self._get_creation_date(entry),
            import_date=imported_date,
            source=source,
            source_post_id=source_post_id,
            discussion=source.discussion,
            body_mime_type=body_mime_type,
            creator=user,
            subject=subject,
            body=body)


class LoomioSourceReader(FeedSourceReader):

    def __init__(self, source_id):
        super(LoomioSourceReader, self).__init__(source_id)

    def _process_reimport_post(self, entry, post, discussion):
        super(LoomioSourceReader, self).\
            _process_reimport_post(entry, post, discussion)
        post.subject = self._get_title_from_feed()

    def _convert_to_post(self, entry, account):
        post = super(LoomioSourceReader, self)._convert_to_post(entry,account)
        post.subject = self._get_title_from_feed()
        return post
