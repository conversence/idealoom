"""Some specialized SQLAlchemy column types"""
import uuid

from future.utils import as_native_str
from past.builtins import basestring
from past.builtins import str as oldstr
from sqlalchemy.types import (
    TypeDecorator, String, PickleType, Text)
from sqlalchemy.ext.hybrid import Comparator
from sqlalchemy.sql import func
from werkzeug.urls import iri_to_uri
from pyisemail import is_email
from sqlalchemy import Unicode as CoerceUnicode
from sqlalchemy.databases import postgresql
import simplejson as json
from rdflib import URIRef


class URLString(TypeDecorator):
    """Safely coerce URLs to Strings."""

    impl = String

    @property
    def python_type(self):
        return self.impl.python_type

    def process_bind_param(self, value, dialect):
        if not value:
            return value
        if isinstance(value, oldstr):
            value = value.decode('utf-8')
        # TODO: Ensure NFC order.
        value = iri_to_uri(value)
        return value

    def copy(self, **kw):
        return URLString(self.impl.length)


class URIRefString(TypeDecorator):
    """Safely coerce URIRefs to Strings."""

    impl = CoerceUnicode

    @property
    def python_type(self):
        return URIRef

    def process_bind_param(self, value, dialect):
        if value is not None:
            return URIRef(value)

    def process_result_value(self, value, dialect):
        if value is not None:
            return URIRef(value)

    def copy(self, **kw):
        return URIRefString(self.impl.length)


class EmailString(TypeDecorator):
    impl = String

    @property
    def python_type(self):
        return self.impl.python_type

    @staticmethod
    def normalize_email_case(email):
        # Assumes valid email. ensure domain is lower case
        (name, domain) = email.split('@')
        return name+'@'+domain.lower()

    @as_native_str(encoding='ascii')
    def normalize_to_type(self, value, dialect):
        return value

    def process_bind_param(self, value, dialect):
        if not value:
            return value
        value = self.normalize_to_type(value, dialect)
        if '%' in value:
            # LIKE search string
            return value
        if not is_email(value):
            raise ValueError(value+" is not a valid email")
        value = self.normalize_email_case(value)
        return value

    def copy(self, **kw):
        return self.__class__(self.impl.length)


class EmailUnicode(EmailString):
    impl = CoerceUnicode


class CaseInsensitiveWord(Comparator):
    "Hybrid value representing a lower case representation of a word."

    def __init__(self, word):
        if isinstance(word, basestring):
            self.word = word.lower()
        elif isinstance(word, CaseInsensitiveWord):
            self.word = word.word
        else:
            self.word = func.lower(word)

    def operate(self, op, other):
        if not isinstance(other, CaseInsensitiveWord):
            other = CaseInsensitiveWord(other)
        return op(self.word, other.word)

    def __clause_element__(self):
        return self.word

    def __str__(self):
        return self.word

    key = 'word'
    "Label to apply to Query tuple results"


# JSON type field
class JSONType(PickleType):
    impl = Text

    def __init__(self, *args, **kwargs):
        kwargs['pickler'] = json
        super(JSONType, self).__init__(*args, **kwargs)


class UUID(TypeDecorator):
    """
    Adapted from:
    http://stackoverflow.com/questions/183042/how-can-i-use-uuids-in-sqlalchemy
    """
    impl = postgresql.UUID

    def process_bind_param(self, value, dialect=None):
        if value and isinstance(value, uuid.UUID):
            return value.hex
        elif value:
            raise ValueError('value %s is not a valid uuid.UUID' % value)
        else:
            return None

    def process_result_value(self, value, dialect=None):
        if value:
            return uuid.UUID(value.decode('utf8'))
        else:
            return None

    def is_mutable(self):
        return False

    def copy(self, **kw):
        return UUID()
