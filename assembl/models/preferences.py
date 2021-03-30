# -*- coding: utf-8 -*-
"""A set of preferences that apply to a Discussion.

May be defined at the user, Discussion or server level."""
from future import standard_library
from future.utils import text_type
standard_library.install_aliases()
from builtins import str
from itertools import chain
from collections import MutableMapping

from future.utils import string_types
import simplejson as json
from sqlalchemy import (
    Column,
    Integer,
    Text,
    Unicode,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from ..lib.sqla_types import CoerceUnicode
from pyramid.httpexceptions import HTTPUnauthorized

from . import AbstractBase, NamedClassMixin
from ..auth import *
from ..lib.abc import classproperty
from ..lib.locale import _, strip_country
from ..lib import config


def merge_json(base, patch):
    # simplistic recursive dictionary merge
    if not (isinstance(base, dict) and isinstance(patch, dict)):
        return patch
    base = dict(base)
    for k, v in patch.items():
        base[k] = merge_json(base[k], v) if k in base else v
    return base


class Preferences(MutableMapping, NamedClassMixin, AbstractBase):
    """
    Cascading preferences
    """
    __tablename__ = "preferences"
    BASE_PREFS_NAME = "default"
    id = Column(Integer, primary_key=True)
    name = Column(CoerceUnicode, nullable=False, unique=True)
    cascade_id = Column(Integer, ForeignKey(id), nullable=True)
    pref_json = Column("values", Text())  # JSON blob

    cascade_preferences = relationship("Preferences", remote_side=[id])

    @classmethod
    def get_naming_column_name(self):
        return "name"

    @classmethod
    def get_by_name(cls, name=None, session=None):
        name = name or cls.BASE_PREFS_NAME
        session = session or cls.default_db
        return session.query(cls).filter_by(name=name).first()

    @classmethod
    def get_default_preferences(cls, session=None):
        return cls.get_by_name('default', session) or cls(name='default')

    @classmethod
    def get_discussion_conditions(cls, discussion_id):
        # This is not a DiscussionBoundBase, but protocol is otherwise useful
        from .discussion import Discussion
        return ((cls.id == Discussion.preferences_id),
                (Discussion.id == discussion_id))

    @classmethod
    def init_from_settings(cls, settings):
        """Initialize some preference values"""
        from ..auth.social_auth import get_active_auth_strategies
        # TODO: Give linguistic names to social auth providers.
        active_strategies = {
            k: k for k in get_active_auth_strategies(settings)}
        active_strategies[''] = _("No special authentication")
        cls.preference_data['authorization_server_backend']['scalar_values'] = active_strategies

    @property
    def local_values_json(self):
        values = {}
        if self.pref_json:
            values = json.loads(self.pref_json)
            assert isinstance(values, dict)
        return values

    @local_values_json.setter
    def local_values_json(self, val):
        assert isinstance(val, dict)
        self.pref_json = json.dumps(val)

    @property
    def values_json(self):
        if self.cascade_preferences:
            values = self.cascade_preferences.values_json
        else:
            values = self.property_defaults
            if not values.get('preference_data', None):
                values['preference_data'] = self.get_preference_data_list()
        values.update(self.local_values_json)
        return values

    def safe_local_values_json(self, permissions):
        json = self.local_values_json
        spec = self.get_preference_data()
        json = {k: v for (k, v) in json.items()
                if k in spec}
        permissions = permissions[:] or []
        permissions.append("default_read")
        json = {k: v for (k, v) in json.items()
                if k in spec and
                spec[k].get("read_permission", "default_read") in permissions}
        return json

    def can_read(self, key, permissions):
        specs = self.get_preference_data()
        spec = specs.get(key, None)
        if not spec:
            return False
        needed = spec.get("read_permission", None)
        return not needed or (needed in permissions)

    def can_modify(self, key, permissions):
        specs = self.get_preference_data()
        spec = specs.get(key, None)
        if not spec:
            return False
        needed = spec.get("modification_permission", None)
        return not needed or (needed in permissions)

    def safe_get_value(self, key, permissions):
        specs = self.get_preference_data()
        spec = specs.get(key, None)
        if spec:
            needed = spec.get("read_permission", None)
            if not needed or (needed in permissions):
                return self[key]

    def safe_property_defaults(self, permissions):
        values = self.property_defaults
        if not values.get('preference_data', None):
            values['preference_data'] = self.get_preference_data_list()
        spec = self.get_preference_data()
        permissions = permissions[:]
        permissions.append("default_read")
        return {k: v for (k, v) in values.items()
                if k in spec and
                spec[k].get("read_permission", "default_read") in permissions}

    def safe_values_json(self, permissions):
        if self.cascade_preferences:
            values = self.cascade_preferences.safe_values_json(permissions)
        else:
            values = self.safe_property_defaults(permissions)
        values.update(self.safe_local_values_json(permissions))
        return values

    def _get_local(self, key):
        if key not in self.preference_data:
            raise KeyError("Unknown preference: " + key)
        values = self.local_values_json
        if key in values:
            value = values[key]
            return True, value
        return False, None

    def get_local(self, key):
        exists, value = self._get_local(key)
        if exists:
            return value

    def __getitem__(self, key):
        if key == 'name':
            return self.name
        if key == '@extends':
            return (self.uri_generic(self.cascade_id)
                    if self.cascade_id else None)
        exists, value = self._get_local(key)
        if exists:
            return value
        elif self.cascade_id:
            return self.cascade_preferences[key]
        if key == "preference_data":
            return self.get_preference_data_list()
        return self.get_preference_data()[key].get("default", None)

    def __len__(self):
        return len(self.preference_data_list) + 2

    def __iter__(self):
        return chain(self.preference_data_key_list, (
            'name', '@extends'))

    def __contains__(self, key):
        return key in self.preference_data_key_set

    def __delitem__(self, key):
        values = self.local_values_json
        if key in values:
            oldval = values[key]
            del values[key]
            self.local_values_json = values
            return oldval

    def __setitem__(self, key, value):
        if key == 'name':
            old_value = self.name
            self.name = text_type(value)
            return old_value
        elif key == '@extends':
            old_value = self.get('@extends')
            new_pref = self.get_instance(value)
            if new_pref is None:
                raise KeyError("Does not exist:" + value)
            self.cascade_preferences = new_pref
            return old_value
        if key not in self.preference_data_key_set:
            raise KeyError("Unknown preference: " + key)
        values = self.local_values_json
        old_value = values.get(key, None)
        value = self.validate(key, value)
        values[key] = value
        self.local_values_json = values
        return old_value

    def can_edit(self, key, permissions=(P_READ,), pref_data=None):
        if P_SYSADMIN in permissions:
            if key == 'name' and self.name == self.BASE_PREFS_NAME:
                # Protect the base name
                return False
            return True
        if key in ('name', '@extends', 'preference_data'):
            # TODO: Delegate permissions.
            return False
        if key not in self.preference_data_key_set:
            raise KeyError("Unknown preference: " + key)
        if pref_data is None:
            pref_data = self.get_preference_data()[key]
        req_permission = pref_data.get(
            'modification_permission', P_ADMIN_DISC)
        if req_permission not in permissions:
            return False
        return True

    def safe_del(self, key, permissions=(P_READ,)):
        if not self.can_edit(key, permissions):
            raise HTTPUnauthorized("Cannot delete "+key)
        del self[key]

    def safe_set(self, key, value, permissions=(P_READ,)):
        if not self.can_edit(key, permissions):
            raise HTTPUnauthorized("Cannot edit "+key)
        self[key] = value

    def validate(self, key, value, pref_data=None):
        if pref_data is None:
            pref_data = self.get_preference_data()[key]
        validator = pref_data.get('backend_validator_function', None)
        if validator:
            # This has many points of failure, but all failures are meaningful.
            module, function = validator.rsplit(".", 1)
            from importlib import import_module
            mod = import_module(module)
            try:
                value = getattr(mod, function)(value)
                if value is None:
                    raise ValueError("Empty value after validation")
            except Exception as e:
                raise ValueError(e.message)
        data_type = pref_data.get("value_type", "json")
        return self.validate_single_value(key, value, pref_data, data_type)

    def validate_single_value(self, key, value, pref_data, data_type):
        # TODO: Validation for the datatypes.
        # base_type: (bool|json|int|string|text|scalar|url|email|domain|locale|langstr|permission|role|pubflow|pubstate|password)
        # type: base_type|list_of_(type)|dict_of_(base_type)_to_(type)
        if data_type.startswith("list_of_"):
            assert isinstance(value, (list, tuple)), "Not a list"
            return [
                self.validate_single_value(key, val, pref_data, data_type[8:])
                for val in value]
        elif data_type.startswith("dict_of_"):
            assert isinstance(value, (dict)), "Not a dict"
            key_type, value_type = data_type[8:].split("_to_", 1)
            assert "_" not in key_type
            return {
                self.validate_single_value(key, k, pref_data, key_type):
                self.validate_single_value(key, v, pref_data, value_type)
                for (k, v) in value.items()}
        elif data_type == "langstr":
            # Syntactic sugar for dict_of_locale_to_string
            assert isinstance(value, (dict)), "Not a dict"
            return {
                self.validate_single_value(key, k, pref_data, "locale"):
                self.validate_single_value(key, v, pref_data, "string")
                for (k, v) in value.items()}
        elif data_type == "bool":
            assert isinstance(value, bool), "Not a boolean"
        elif data_type == "int":
            assert isinstance(value, int), "Not an integer"
        elif data_type == "json":
            pass  # no check
        else:
            assert isinstance(value, string_types), "Not a string"
            if data_type in ("string", "text", "password"):
                pass
            elif data_type == "scalar":
                assert value in pref_data.get("scalar_values", ()), (
                    "value not allowed: " + value)
            elif data_type == "url":
                from urllib.parse import urlparse
                assert urlparse(value).scheme in (
                    'http', 'https'), "Not a HTTP URL"
            elif data_type == "email":
                from pyisemail import is_email
                assert is_email(value), "Not an email"
            elif data_type == "locale":
                pass  # TODO
            elif data_type == "pubflow":
                from .publication_states import PublicationFlow
                assert PublicationFlow.getByName(value)
            elif data_type == "pubstate":
                discussion = self.discussion
                if discussion:
                    idea_pub_flow = discussion.idea_publication_flow
                else:
                    from .publication_states import PublicationFlow
                    idea_pub_flow = PublicationFlow.getByName(self['default_idea_pub_flow'])
                assert idea_pub_flow, "No flow available"
                assert idea_pub_flow.state_by_label(value), "No state %d in flow %d" % (
                    value, idea_pub_flow.label)
            elif data_type == "permission":
                assert value in ASSEMBL_PERMISSIONS
            elif data_type == "role":
                if value not in SYSTEM_ROLES:
                    from .auth import Role
                    assert self.db.query(Role).filter_by(
                        name=value).count() == 1, "Unknown role"
            elif data_type == "domain":
                from pyisemail.validators.dns_validator import DNSValidator
                v = DNSValidator()
                assert v.is_valid(value), "Not a valid domain"
                value = value.lower()
            else:
                raise RuntimeError("Invalid data_type: " + data_type)
        return value

    def generic_json(
            self, view_def_name='default', user_id=Everyone,
            permissions=(P_READ, ), base_uri='local:'):
        # TODO: permissions
        values = self.local_values_json
        values['name'] = self.name
        if self.cascade_preferences:
            values['@extends'] = self.cascade_preferences.name
        values['@id'] = self.uri()
        return values

    def _do_update_from_json(
            self, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        for key, value in json.items():
            if key == '@id':
                if value != self.uri():
                    raise RuntimeError("Wrong id")
            else:
                self[key] = value
        return self

    def __hash__(self):
        return AbstractBase.__hash__(self)

    @classproperty
    def property_defaults(cls):
        return {p['id']: p.get("default", None)
                for p in cls.preference_data_list}

    def get_preference_data(self):
        if self.cascade_id:
            base = self.cascade_preferences.get_preference_data()
        else:
            base = self.preference_data
        exists, patch = self._get_local("preference_data")
        if exists:
            base = merge_json(base, patch)
        return base

    def get_preference_data_list(self):
        data = self.get_preference_data()
        keys = self.preference_data_key_list
        return [data[key] for key in keys]

    crud_permissions = CrudPermissions(P_SYSADMIN)

    # This defines the allowed properties and their data format
    # Each preference metadata has the following format:
    # id (the key for the preference as a dictionary)
    # name (for interface)
    # description (for interface, hover help)
    # value_type: given by the following grammar:
    #       base_type = (bool|json|int|string|text|scalar|url|email|domain|locale|langstr|permission|role)
    #       type = base_type|list_of_(type)|dict_of_(base_type)_to_(type)
    #   more types may be added, but need to be added to both frontend and backend
    # show_in_preferences: Do we always hide this preference?
    # modification_permission: What permission do you need to change that preference?
    #   (default: P_DISCUSSION_ADMIN)
    # allow_user_override: Do we allow users to have their personal value for that permission?
    #   if so what permission is required? (default False)
    # scalar_values: "{value: "label"}" a dictionary of permitted options for a scalar value type
    # default: the default value
    # item_default: the default value for new items in a list_of_T... or dict_of_BT_to_T...

    preference_data_list = [
        # Languages used in the discussion.
        {
            "id": "preferred_locales",
            "value_type": "list_of_locale",
            "name": _("Languages used"),
            "description": _("All languages expected in the discussion"),
            "allow_user_override": None,
            "item_default": "en",
            "default": [strip_country(x) for x in config.get_config().get(
                'available_languages', 'fr en').split()]
        },
        # full class name of translation service to use, if any
        # e.g. assembl.nlp.translate.GoogleTranslationService
        {
            "id": "translation_service",
            "name": _("Translation service"),
            "value_type": "scalar",
            "scalar_values": {
                "": _("No translation"),
                "assembl.nlp.translation_service.DummyTranslationServiceTwoSteps":
                    _("Dummy translation service (two steps)"),
                "assembl.nlp.translation_service.DummyTranslationServiceOneStep":
                    _("Dummy translation service (one step)"),
                "assembl.nlp.translation_service.DummyTranslationServiceTwoStepsWithErrors":
                    _("Dummy translation service (two steps) with errors"),
                "assembl.nlp.translation_service.DummyTranslationServiceOneStepWithErrors":
                    _("Dummy translation service (one step) with errors"),
                "assembl.nlp.translation_service.GoogleTranslationService":
                    _("Google Translate"),
                "assembl.nlp.translation_service.DeeplTranslationService":
                    _("Deepl"),
            },
            "description": _(
                "Translation service"),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": ""
        },

        # full class name of translation service to use, if any
        # e.g. assembl.nlp.translate.GoogleTranslationService
        {
            "id": "translation_service_api_key",
            "name": _("Translation service API key"),
            "value_type": "password",
            "description": _(
                "API key for translation service"),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            "read_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": ""
        },

        # Simple view panel order, eg NIM or NMI
        {
            "id": "simple_view_panel_order",
            "name": _("Panel order in simple view"),
            "value_type": "scalar",
            "scalar_values": {
                "NIM": _("Navigation, Idea, Messages"),
                "NMI": _("Navigation, Messages, Idea")},
            "description": _("Order of panels"),
            "allow_user_override": P_READ,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": "NMI"
        },

        # Allow social sharing
        {
            "id": "social_sharing",
            "name": _("Social sharing"),
            "value_type": "bool",
            # "scalar_values": {value: "label"},
            "description": _("Show the share button on posts and ideas"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": True
        },

        # Require virus check
        {
            "id": "requires_virus_check",
            "name": _("Require anti-virus check"),
            "value_type": "bool",
            # "scalar_values": {value: "label"},
            "description": _("Run an anti-virus on file attachments"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": False  # for development
        },

        # Terms of service version
        {
            "id": "tos_version",
            "name": _("Terms of service version"),
            "value_type": "int",
            # "scalar_values": {value: "label"},
            "description": _("Version number of terms of service. Increment when terms change, participants will be alerted."),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": 1
        },

        # Terms of service version
        {
            "id": "terms_of_service",
            "name": _("Terms of service"),
            "value_type": "dict_of_locale_to_text",
            # "scalar_values": {value: "label"},
            "description": _("Terms of service. Multilingual HTML String."),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": None  # for development
        },

        {
            "id": "authorization_server_backend",
            "value_type": "scalar",
            "scalar_values": {
                "": _("No special authentication"),
            },
            "name": _(
                "Authentication service type"),
            "description": _(
                "A primary authentication server for this discussion, defined "
                "as a python-social-auth backend. Participants will be "
                "auto-logged in to that server, and discussion auto-"
                "subscription will require an account from this backend."),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": ""
        },

        # Are moderated posts simply hidden or made inaccessible by default?
        {
            "id": "default_allow_access_to_moderated_text",
            "name": _("Allow access to moderated text"),
            "value_type": "bool",
            # "scalar_values": {value: "label"},
            "description": _(
                "Are moderated posts simply hidden or made inaccessible "
                "by default?"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": True
        },

        # Does the Idea panel automatically open when an idea is clicked? (and close when a special section is clicked)
        {
            "id": "idea_panel_opens_automatically",
            "name": _("Idea panel opens automatically"),
            "value_type": "bool",
            # "scalar_values": {value: "label"},
            "description": _(
                "Does the Idea panel automatically open when an idea is clicked ? (and close when a special section is clicked)"),
            "allow_user_override": P_READ,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": True
        },

        # The specification of the default idea publication flow for a discussion
        {
            "id": "default_idea_pub_flow",
            "name": _("Default idea publication flow"),
            "value_type": "pubflow",
            "show_in_preferences": False,
            "description": _(
                "The idea publication flow to use for a new discussion"),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": "default"
        },

        # The specification of the default idea publication state for new ideas
        {
            "id": "default_idea_pub_state",
            "name": _("Publication state of a new idea"),
            "value_type": "pubstate",
            "scalar_values": [],
            "description": _(
                "The idea publication state to use for a new ideas, taken from the discussion's flow"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": "shared"
        },

        # The specification of the default permissions for a discussion
        {
            "id": "default_permissions",
            "name": _("Default private permissions"),
            "value_type": "dict_of_role_to_list_of_permission",
            "show_in_preferences": False,
            "description": _(
                "The base permissions for a new private discussion"),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "item_default": {
                R_PARTICIPANT: [P_READ],
            },
            "default": {
                R_ADMINISTRATOR: [
                    P_ADD_EXTRACT,
                    P_ADD_IDEA,
                    P_ADD_POST,
                    P_ADMIN_DISC,
                    P_DELETE_POST,
                    P_DISC_STATS,
                    P_EDIT_EXTRACT,
                    P_EDIT_IDEA,
                    P_ASSOCIATE_IDEA,
                    P_EDIT_POST,
                    P_EDIT_SYNTHESIS,
                    P_EXPORT_EXTERNAL_SOURCE,
                    P_MODERATE,
                    P_OVERRIDE_SOCIAL_AUTOLOGIN,
                    P_SEND_SYNTHESIS,
                    P_VOTE,
                ],
                R_CATCHER: [
                    P_ADD_EXTRACT,
                    P_ADD_IDEA,
                    P_ADD_POST,
                    P_EDIT_EXTRACT,
                    P_EDIT_IDEA,
                    P_ASSOCIATE_IDEA,
                    P_OVERRIDE_SOCIAL_AUTOLOGIN,
                    P_VOTE,
                ],
                R_MODERATOR: [
                    P_ADD_EXTRACT,
                    P_ADD_IDEA,
                    P_ADD_POST,
                    P_DELETE_POST,
                    P_DISC_STATS,
                    P_EDIT_EXTRACT,
                    P_EDIT_IDEA,
                    P_ASSOCIATE_IDEA,
                    P_EDIT_POST,
                    P_EDIT_SYNTHESIS,
                    P_EXPORT_EXTERNAL_SOURCE,
                    P_MODERATE,
                    P_OVERRIDE_SOCIAL_AUTOLOGIN,
                    P_SEND_SYNTHESIS,
                    P_VOTE,
                ],
                R_PARTICIPANT: [
                    P_ADD_POST,
                    P_READ_USER_INFO,
                    P_VOTE,
                    P_READ,
                    P_READ_IDEA,
                ],
                R_OWNER: [
                    P_DELETE_POST,
                    P_EDIT_EXTRACT,
                ],
            },
        },


        # The specification of the default permissions for a public discussion
        {
            "id": "default_permissions_public",
            "name": _("Default public permissions"),
            "value_type": "dict_of_role_to_list_of_permission",
            "show_in_preferences": False,
            "description": _(
                "Extra permissions for a new public discussion"),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "item_default": {
                R_PARTICIPANT: [P_READ],
            },
            "default": {
                Authenticated: [
                    P_SELF_REGISTER,
                ],
                Everyone: [
                    P_READ,
                    P_READ_IDEA,
                ],
            },
        },

        # Registration requires being a member of this email domain.
        {
            "id": "require_email_domain",
            "name": _("Require Email Domain"),
            "value_type": "list_of_domain",
            # "scalar_values": {value: "label"},
            "description": _(
                "List of domain names of user email address required for "
                "self-registration. Only accounts with at least an email from those "
                "domains can self-register to this discussion. Anyone can "
                "self-register if this is empty."),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": [],
            "item_default": ""
        },

        # Show the CI Dashboard in the panel group window
        {
            "id": "show_ci_dashboard",
            "name": _("Show CI Dashboard"),
            "value_type": "bool",
            # "scalar_values": {value: "label"},
            "description": _(
                "Show the CI Dashboard in the panel group window"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": False
        },

        # Idea and link types
        {
            "id": "idea_typology",
            "name": _("Idea Typology"),
            "value_type": "json",
            "description": _(
                "Idea types, must be present in ontology"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": {}
        },

        # Extra CSS
        {
            "id": "extra_css",
            "name": _("Extra CSS"),
            "value_type": "text",
            "description": _("CSS"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": ""
        },

        # Configuration of the visualizations shown in the CI Dashboard
        {
            "id": "ci_dashboard_url",
            "name": _("URL of CI Dashboard"),
            "value_type": "url",
            "description": _(
                "Configuration of the visualizations shown in the "
                "CI Dashboard"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default":
                "//cidashboard.net/ui/visualisations/index.php?"
                "width=1000&height=1000&vis=11,23,p22,13,p7,7,12,p2,p15,p9,"
                "p8,p1,p10,p14,5,6,16,p16,p17,18,p20,p4&lang=<%= lang %>"
                "&title=&url=<%= url %>&userurl=<%= user_url %>"
                "&langurl=&timeout=60"
        },

        # List of visualizations
        {
            "id": "visualizations",
            "name": _("Catalyst Visualizations"),
            "value_type": "json",
            # "scalar_values": {value: "label"},
            "description": _(
                "A JSON description of available Catalyst visualizations"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": {}
        },

        # Extra navigation sections (refers to visualizations)
        {
            "id": "navigation_sections",
            "name": _("Navigation sections"),
            "value_type": "json",
            # "scalar_values": {value: "label"},
            "description": _(
                "A JSON specification of Catalyst visualizations to show "
                "in the navigation section"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": {}
        },

        # Translations for the navigation sections
        {
            "id": "translations",
            "name": _("Catalyst translations"),
            "value_type": "json",
            # "scalar_values": {value: "label"},
            "description": _(
                "Translations applicable to Catalyst visualizations, "
                "in Jed (JSON) format"),
            "allow_user_override": None,
            # "view_permission": P_READ,  # by default
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": {}
        },

        # Default expanded/collapsed state of each idea in the table of ideas.
        # A user can override it by opening/closing an idea.
        # This is a hash where keys are ideas ids, and values are booleans.
        # We could use dict_of_string_to_bool, but that would clutter the interface.
        {
            "id": "default_table_of_ideas_collapsed_state",
            "name": _("Default Table of Ideas Collapsed state"),
            "value_type": "json",
            # "scalar_values": {value: "label"},
            "description": _(
                "Default expanded/collapsed state of each idea in the table "
                "of ideas. A user can override it by opening/closing an idea"),
            "allow_user_override": None,
            # "view_permission": P_READ,  # by default
            "modification_permission": P_ADD_IDEA,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": {},
            "show_in_preferences": False
        },

        # The specification of the preference data
        {
            "id": "preference_data",
            "name": _("Preference data"),
            "value_type": "json",
            "show_in_preferences": False,
            "description": _(
                "The preference configuration; override only with care"),
            "allow_user_override": None,
            "modification_permission": P_SYSADMIN,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": None  # this should be recursive...
        },

        # The specification of the cookies banner
        {
            "id": "cookies_banner",
            "name": _("Cookies banner"),
            "value_type": "bool",
            "show_in_preferences": True,
            "description": _(
                "Show the banner offering to disable Piwik cookies"),
            "allow_user_override": None,
            "modification_permission": P_ADMIN_DISC,
            # "frontend_validator_function": func_name...?,
            # "backend_validator_function": func_name...?,
            "default": True  # this should be recursive...
        }
    ]

    # Precompute, this is not mutable.
    preference_data_key_list = [p["id"] for p in preference_data_list]
    preference_data_key_set = set(preference_data_key_list)
    preference_data = {p["id"]: p for p in preference_data_list}


def includeme(config):
    """Initialize some preference values"""
    Preferences.init_from_settings(config.get_settings())
