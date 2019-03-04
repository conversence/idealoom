"""Utility modules for permissions and authentication

This module defines basic roles and permissions."""

from builtins import object
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

# Permissions
P_READ_USER_INFO = 'User.R.baseInfo'
P_READ = 'Conversation.R'
P_READ_IDEA = 'Idea.R'
P_ADD_POST = 'Post.C'
P_EDIT_POST = 'Post.U'
P_DELETE_POST = 'Post.D'
P_VOTE = 'Idea.C.Vote'
P_ADD_EXTRACT = 'Content.C.Extract'
P_EDIT_EXTRACT = 'Extract.U'
P_ADD_IDEA_DRAFT = 'Idea.C.draft'
P_ADD_IDEA = 'Idea.C'
P_EDIT_IDEA = 'Idea.U'
P_EDIT_SYNTHESIS = 'Synthesis.U'
P_SEND_SYNTHESIS = 'Synthesis.U.send'
P_SELF_REGISTER = 'Conversation.A.User'
P_SELF_REGISTER_REQUEST = 'Conversation.A.User.request'
P_ADMIN_DISC = 'Conversation.U'
P_SYSADMIN = '*'
P_EXPORT_EXTERNAL_SOURCE = 'Content.U.export'
P_MODERATE = 'Content.U.moderate'
P_DISC_STATS = 'Conversation.U.stats'
P_OVERRIDE_SOCIAL_AUTOLOGIN = 'Conversation.A.User.override_autologin'
P_ASSOCIATE_EXTRACT = 'Idea.A.Extract'

IF_OWNED = "IF_OWNED"

ASSEMBL_PERMISSIONS = set((
    P_READ, P_ADD_POST, P_EDIT_POST, P_DELETE_POST, P_VOTE, P_ADD_EXTRACT,
    P_EDIT_EXTRACT, P_ADD_IDEA, P_EDIT_IDEA, P_EDIT_SYNTHESIS,
    P_SEND_SYNTHESIS, P_SELF_REGISTER, P_SELF_REGISTER_REQUEST,
    P_ADMIN_DISC, P_SYSADMIN, P_READ_USER_INFO, P_OVERRIDE_SOCIAL_AUTOLOGIN,
    P_EXPORT_EXTERNAL_SOURCE, P_MODERATE, P_DISC_STATS, P_ASSOCIATE_EXTRACT,
    P_ADD_IDEA_DRAFT, P_READ_IDEA
))


class CrudPermissions(object):
    """A set of permissions required to Create, Read, Update or Delete
    an instance of a given class

    The :py:attr:`crud_permissions` class attribute of a model class
    should hold an instance of this class.
    Special permissions can be defined if you *own* this
    instance, according to :py:meth:`assembl.lib.sqla.BaseOps.is_owned`"""
    __slots__ = ('create', 'read', 'update', 'delete',
                 'read_owned', 'update_owned', 'delete_owned')

    CREATE = 1
    READ = 2
    UPDATE = 3
    DELETE = 4

    def __init__(self, create=None, read=None, update=None, delete=None,
                 update_owned=None, delete_owned=None, read_owned=None):
        self.create = create or P_SYSADMIN
        self.read = read or P_READ
        self.update = update or create or P_SYSADMIN
        self.delete = delete or P_SYSADMIN
        self.read_owned = read_owned or self.read
        self.update_owned = update_owned or self.update
        self.delete_owned = delete_owned or self.delete

    def can(self, operation, permissions):
        if P_SYSADMIN in permissions:
            return True
        needed, needed_owned = self.crud_permissions(operation)
        if needed in permissions:
            return True
        elif needed_owned in permissions:
            return IF_OWNED
        return False

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
