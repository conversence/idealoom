from __future__ import print_function
import pytest


def build_user_language_preference(user, locale, source_of_evidence):
    from assembl.models.auth import UserLanguagePreference

    ulp = UserLanguagePreference(
        user=user,
        locale=locale,
        preferred_order=0,
        source_of_evidence=source_of_evidence)

    return ulp


def build_explicit_user_language_preference(user, locale):
    from assembl.models.auth import LanguagePreferenceOrder

    ulp = build_user_language_preference(user, locale, LanguagePreferenceOrder.Explicit.value)

    return ulp


def build_cookie_user_language_preference(user, locale):
    from assembl.models.auth import LanguagePreferenceOrder

    ulp = build_user_language_preference(user, locale, LanguagePreferenceOrder.Cookie.value)

    return ulp


@pytest.fixture(scope="function")
def participant1_user_language_preference_en_cookie(
        request, test_session, participant1_user):
    """Participant 1 User Language Preference fixture with English (en) cookie level"""

    ulp = build_explicit_user_language_preference(participant1_user, "en")

    def fin():
        print("finalizer participant1_user_language_preference_en_cookie")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def participant1_user_language_preference_fr_cookie(
        request, test_session, participant1_user):
    """Participant 1 User Language Preference fixture with French (fr) cookie level"""

    ulp = build_explicit_user_language_preference(participant1_user, "fr")

    def fin():
        print("finalizer participant1_user_language_preference_fr_cookie")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_en_cookie(request, test_session, admin_user):
    """User Language Preference fixture with English (en) cookie level"""
    ulp = build_explicit_user_language_preference(admin_user, "en")

    def fin():
        print("finalizer user_language_preference_en_cookie")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_fr_cookie(request, test_session, admin_user):
    """User Language Preference fixture with French (fr) cookie level"""
    ulp = build_cookie_user_language_preference(admin_user, "fr")

    def fin():
        print("finalizer user_language_preference_fr_cookie")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_it_cookie(request, test_session, admin_user):
    """User Language Preference fixture with Italian (it) cookie level"""

    ulp = build_cookie_user_language_preference(admin_user, "it")

    def fin():
        print("finalizer user_language_preference_it_cookie")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_en_explicit(request, test_session,
                                         admin_user):
    """User Language Preference fixture with English (en) explicit level"""
    ulp = build_explicit_user_language_preference(admin_user, "en")

    def fin():
        print("finalizer user_language_preference_en_explicit")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_fr_explicit(request, test_session,
                                         admin_user):
    """User Language Preference fixture with French (fr) explicit level"""
    ulp = build_explicit_user_language_preference(admin_user, "fr")

    def fin():
        print("finalizer user_language_preference_cookie")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_it_explicit(request, test_session,
                                         admin_user):
    """User Language Preference fixture with Italian (it) explicit level"""
    ulp = build_explicit_user_language_preference(admin_user, "it")

    def fin():
        print("finalizer user_language_preference_it_explicit")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_de_explicit(request, test_session,
                                         admin_user):
    """User Language Preference fixture with German (de) explicit level"""
    ulp = build_explicit_user_language_preference(admin_user, "de")

    def fin():
        print("finalizer user_language_preference_de_explicit")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_tr_explicit(request, test_session,
                                         admin_user):
    """User Language Preference fixture with Turkish (tr) explicit level"""
    ulp = build_explicit_user_language_preference(admin_user, "tr")

    def fin():
        print("finalizer user_language_preference_tr_explicit")
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_fr_mtfrom_en(request, test_session,
                                          admin_user):
    """User Language Preference fixture with French (fr) translated
    from English (en) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='en',
        translate='fr',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_en_mtfrom_fr(request, test_session,
                                          admin_user):
    """User Language Preference fixture with English (en) translated
    from French (fr) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='fr',
        translate='en',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_it_mtfrom_en(request, test_session,
                                          admin_user):
    """User Language Preference fixture with Italian (it) translated
    from English (en) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='en',
        translate='it',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_en_mtfrom_it(request, test_session,
                                          admin_user):
    """User Language Preference fixture with English (en) translated
    from Italian (it) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='it',
        translate='en',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_it_mtfrom_fr(request, test_session,
                                          admin_user):
    """User Language Preference fixture with Italian (it) translated
    from French (fr) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='fr',
        translate='it',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_fr_mtfrom_it(request, test_session,
                                          admin_user):
    """User Language Preference fixture with French (fr) translated
    from Italian (it) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='it',
        translate='fr',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_de_mtfrom_en(request, test_session,
                                          admin_user):
    """User Language Preference fixture with German (de) translated
    from English (en) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='en',
        translate='de',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp


@pytest.fixture(scope="function")
def user_language_preference_en_mtfrom_de(request, test_session,
                                          admin_user):
    """User Language Preference fixture with English (en) translated
    from German (de) explicit level"""

    from assembl.models.auth import (
        UserLanguagePreference,
        LanguagePreferenceOrder
    )

    ulp = UserLanguagePreference(
        user=admin_user,
        locale='de',
        translate='en',
        preferred_order=0,
        source_of_evidence=LanguagePreferenceOrder.Explicit.value)

    def fin():
        test_session.delete(ulp)
        test_session.flush()

    test_session.add(ulp)
    test_session.flush()
    request.addfinalizer(fin)
    return ulp
