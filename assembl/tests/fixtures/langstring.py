# -*- coding: utf-8 -*-

import pytest


@pytest.fixture(scope="function")
def langstring_entry_values():
    """Dict fixture of content in multiple languages"""
    return {
        "subject": {
            "english":
                u"Here is an English subject that is very cool and hip.",
            "french":
                u"Voici un sujet anglais qui " +
                u"est très cool et branché.",
            "italian": u"Ecco un soggetto inglese che " +
                       u"è molto cool e alla moda.",
            "german": u"Hier ist ein englisches Thema, " +
                      u"das sehr cool und hip ist.",
            "turkish": u"Burada çok serin ve kalça bir İngiliz konudur.",
        },
        "body": {
            "english": u"Here is an English body that is " +
                       u"very cool and hip. And it is also longer.",
            "french": u"Voici un body anglais qui est très cool et branché. " +
                      u"Et il est également plus longue.",
            "italian": u"Qui è un organismo inglese che " +
                       u" è molto cool e alla moda. Ed è anche più.",
            "german": u"Hier ist ein englischer Körper, die sehr cool " +
                      u"und hip ist. Und es ist auch länger.",
            "turkish": u"Burada çok serin ve kalça bir İngiliz" +
                       u"organıdır. Ve aynı zamanda daha uzun."
        }
    }


@pytest.fixture(scope="function")
def en_langstring_entry(request, test_session,
                        langstring_body, langstring_entry_values):
    """LangStringEntry fixture with English locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='en',
        value=langstring_entry_values.get('body').get('english')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def fr_langstring_entry(request, test_session,
                        langstring_body, langstring_entry_values):
    """LangStringEntry fixture with French locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='fr',
        value=langstring_entry_values.get('body').get('french')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def it_langstring_entry(request, test_session,
                        langstring_body, langstring_entry_values):
    """LangStringEntry fixture with Italian locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='it',
        value=langstring_entry_values.get('body').get('italian')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def tr_langstring_entry(request, test_session,
                        langstring_body, langstring_entry_values):
    """LangStringEntry fixture with Turkish locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='tr',
        value=langstring_entry_values.get('body').get('turkish')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def und_langstring_entry(request, test_session,
                         langstring_body, langstring_entry_values):
    """LangStringEntry fixture with undefined locale"""

    from assembl.models.langstrings import LangStringEntry, LocaleLabel

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale=LocaleLabel.UNDEFINED,
        value=langstring_entry_values.get('body').get('english')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def non_linguistic_langstring_entry(request, test_session,
                                    langstring_body,
                                    langstring_entry_values):
    """LangStringEntry fixture with non_linguistic locale"""

    from assembl.models.langstrings import LangStringEntry, LocaleLabel

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale=LocaleLabel.NON_LINGUISTIC,
        value=langstring_entry_values.get('body').get('english')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def fr_from_en_langstring_entry(request, test_session,
                                langstring_body, en_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with EN locale + FR from EN locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='fr',
        mt_trans_of=en_langstring_entry,
        value=langstring_entry_values.get('body').get('french')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        print "Destroying fr_from_en_langstring_entry"
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def en_from_fr_langstring_entry(request, test_session,
                                langstring_body, fr_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with FR locale + EN from FR locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='en',
        mt_trans_of=fr_langstring_entry,
        value=langstring_entry_values.get('body').get('english')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def it_from_en_langstring_entry(request, test_session,
                                langstring_body, en_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with EN locale + IT from EN locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='it',
        mt_trans_of=en_langstring_entry,
        value=langstring_entry_values.get('body').get('italian')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def en_from_it_langstring_entry(request, test_session,
                                langstring_body, it_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with IT locale + EN from IT locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='en',
        mt_trans_of=it_langstring_entry,
        value=langstring_entry_values.get('body').get('english')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def it_from_fr_langstring_entry(request, test_session,
                                langstring_body, fr_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with FR locale + IT from FR locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='it',
        mt_trans_of=fr_langstring_entry,
        value=langstring_entry_values.get('body').get('italian')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def fr_from_it_langstring_entry(request, test_session,
                                langstring_body, it_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with IT locale + FR from IT locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='fr',
        mt_trans_of=it_langstring_entry,
        value=langstring_entry_values.get('body').get('french')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def en_from_tr_langstring_entry(request, test_session,
                                langstring_body, tr_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with TR locale + EN from TR locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='en',
        mt_trans_of=tr_langstring_entry,
        value=langstring_entry_values.get('body').get('english')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def de_from_tr_langstring_entry(request, test_session,
                                langstring_body, tr_langstring_entry,
                                langstring_entry_values):
    """LangStringEntry fixture with TR locale + DE from TR locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='de',
        mt_trans_of=tr_langstring_entry,
        value=langstring_entry_values.get('body').get('german')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def fr_from_und_langstring_entry(request, test_session,
                                 langstring_body, und_langstring_entry,
                                 langstring_entry_values):
    """LangStringEntry fixture with und locale + FR from und locale"""

    from assembl.models.langstrings import LangStringEntry

    entry = LangStringEntry(
        locale_confirmed=False,
        langstring=langstring_body,
        locale='fr',
        mt_trans_of=und_langstring_entry,
        value=langstring_entry_values.get('body').get('french')
    )

    test_session.expire(langstring_body, ["entries"])

    def fin():
        test_session.delete(entry)
        test_session.flush()

    test_session.add(entry)
    test_session.flush()
    request.addfinalizer(fin)
    return entry


@pytest.fixture(scope="function")
def langstring_body(request, test_session):
    """An Empty Langstring fixture"""

    from assembl.models.langstrings import LangString

    ls = LangString()
    test_session.add(ls)
    test_session.flush()

    def fin():
        test_session.delete(ls)
        test_session.flush()

    request.addfinalizer(fin)
    return ls


@pytest.fixture(scope="function")
def langstring_subject(request, test_session):
    """An Empty Langstring fixture"""

    from assembl.models.langstrings import LangString

    ls = LangString()
    test_session.add(ls)
    test_session.flush()

    def fin():
        test_session.delete(ls)
        test_session.flush()

    request.addfinalizer(fin)
    return ls
