"""Web tokens for annotator interoperability.

Lifted with thanks from
https://github.com/okfn/annotator-store/blob/master/annotator/auth.py """
from builtins import str
import datetime

import isodate
import pytz
import jwt

DEFAULT_TTL = 86400


class TokenInvalid(Exception):
    pass


# Main auth routines

def encode_token(token, secret):
    token.update({'issuedAt': _now().isoformat()})
    return jwt.encode(token, secret)


def decode_token(token, secret='', ttl=DEFAULT_TTL, verify=True):
    try:
        token = jwt.decode(str(token), secret, verify=verify)
    except jwt.DecodeError as e:
        raise TokenInvalid("error decoding JSON Web Token", e)

    if verify:
        issue_time = token.get('issuedAt')
        if issue_time is None:
            raise TokenInvalid("'issuedAt' is missing from token")

        issue_time = isodate.parse_datetime(issue_time)
        expiry_time = issue_time + datetime.timedelta(seconds=ttl)

        if issue_time > _now():
            raise TokenInvalid("token is not yet valid")
        if expiry_time < _now():
            raise TokenInvalid("token has expired")

    return token


def _now():
    return datetime.datetime.now(pytz.UTC).replace(microsecond=0)
