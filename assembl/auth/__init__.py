"""Utility modules for permissions and authentication

This module defines basic roles and permissions."""

from builtins import object
from enum import Enum
from pyramid.security import (
    Everyone, Authenticated, ALL_PERMISSIONS)


R_PARTICIPANT = 'r:participant'
R_CATCHER = 'r:catcher'
R_MODERATOR = 'r:moderator'
R_ADMINISTRATOR = 'r:administrator'
R_SYSADMIN = 'r:sysadmin'
R_OWNER = 'r:owner'


SYSTEM_ROLES = set(
    (Everyone, Authenticated, R_PARTICIPANT, R_CATCHER,
     R_MODERATOR, R_ADMINISTRATOR, R_SYSADMIN, R_OWNER))

class Permissions(Enum):
    READ_USER_INFO = 'User.R.baseInfo'
    READ = 'Conversation.R'
    READ_IDEA = 'Idea.R'
    ADD_POST = 'Post.C'
    EDIT_POST = 'Post.U'
    DELETE_POST = 'Post.D'
    VOTE = 'Idea.C.Vote'
    ADD_EXTRACT = 'Content.C.Extract'
    EDIT_EXTRACT = 'Extract.U'
    ADD_IDEA_DRAFT = 'Idea.C.draft'
    ASSOCIATE_IDEA = 'Idea.A.Idea'
    ADD_IDEA = 'Idea.C'
    EDIT_IDEA = 'Idea.U'
    EDIT_SYNTHESIS = 'Synthesis.U'
    SEND_SYNTHESIS = 'Synthesis.U.send'
    SELF_REGISTER = 'Conversation.A.User'
    SELF_REGISTER_REQUEST = 'Conversation.A.User.request'
    ADMIN_DISC = 'Conversation.U'
    SYSADMIN = '*'
    EXPORT_EXTERNAL_SOURCE = 'Content.U.export'
    MODERATE = 'Content.U.moderate'
    DISC_STATS = 'Conversation.U.stats'
    OVERRIDE_SOCIAL_AUTOLOGIN = 'Conversation.A.User.override_autologin'
    ASSOCIATE_EXTRACT = 'Idea.A.Extract'

    @classmethod
    def by_value(cls, value):
        for v in cls.__members__.values():
            if v.value == value:
                return v

    def __json__(self):
        return self.value


MAYBE = "MAYBE"


class CrudPermissions(object):
    """A set of permissions required to Create, Read, Update or Delete
    an instance of a given class

    The :py:attr:`crud_permissions` class attribute of a model class
    should hold an instance of this class.
    Special permissions can be defined if you *own* this
    instance, according to :py:meth:`assembl.lib.sqla.BaseOps.is_owned`"""
    __slots__ = ('create', 'read', 'update', 'delete',
                 'read_owned', 'update_owned', 'delete_owned', 'variable')

    CREATE = 1
    READ = 2
    UPDATE = 3
    DELETE = 4

    def __init__(self, create=None, read=None, update=None, delete=None,
                 update_owned=None, delete_owned=None, read_owned=None,
                 variable=False):
        self.create = create or Permissions.SYSADMIN
        self.read = read or Permissions.READ
        self.update = update or create or Permissions.SYSADMIN
        self.delete = delete or Permissions.SYSADMIN
        self.read_owned = read_owned or self.read
        self.update_owned = update_owned or self.update
        self.delete_owned = delete_owned or self.delete
        self.variable = variable

    def can(self, operation, permissions):
        if Permissions.SYSADMIN in permissions:
            return True
        needed, needed_owned = self.crud_permissions(operation)
        if needed in permissions:
            return True
        elif needed_owned in permissions:
            return MAYBE
        if operation == self.CREATE:
            return False  # no maybe for create
        return self.variable

    def crud_permissions(self, operation):
        if operation == self.CREATE:
            return (self.create, self.create)
        elif operation == self.READ:
            return (self.read, self.read_owned)
        elif operation == self.UPDATE:
            return (self.update, self.update_owned)
        elif operation == self.DELETE:
            return (self.delete, self.delete_owned)
        else:
            raise ValueError()


def includeme(config):
    config.include('.util')
    config.include('.social_auth')
    config.include('.generic_auth_backend')
