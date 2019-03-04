"""new_permissions

Revision ID: dcc412989fc6
Revises: 10eaccaf8c33
Create Date: 2019-02-20 10:10:22.455481

"""

# revision identifiers, used by Alembic.
revision = 'dcc412989fc6'
down_revision = '10eaccaf8c33'

from itertools import chain

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config
from assembl.lib.sqla import mark_changed


renames = {
    'read': 'User.R.baseInfo',  # P_READ -> P_READ_USER_INFO
    'read_public_cif': 'Conversation.R',  # P_READ_PUBLIC_CIF -> P_READ
    'add_post': 'Post.C',  # P_ADD_POST
    'edit_post': 'Post.U',  # P_EDIT_POST
    'delete_post': 'Post.D',  # P_DELETE_POST
    'vote': 'Idea.C.Vote',  # P_VOTE
    'add_extract': 'Content.C.Extract',  # P_ADD_EXTRACT
    'edit_extract': 'Extract.U',  # P_EDIT_EXTRACT
    'add_idea': 'Idea.C',  # P_ADD_IDEA
    'edit_idea': 'Idea.U',  # P_EDIT_IDEA
    'edit_synthesis': 'Synthesis.U',  # P_EDIT_SYNTHESIS
    'send_synthesis': 'Synthesis.U.send',  # P_SEND_SYNTHESIS
    'self_register': 'Conversation.A.User',  # P_SELF_REGISTER
    'self_register_req': 'Conversation.A.User.request',  # P_SELF_REGISTER_REQUEST
    'admin_discussion': 'Conversation.U',  # P_ADMIN_DISC
    'sysadmin': '*',  # P_SYSADMIN
    'export_post': 'Content.U.export',  # P_EXPORT_EXTERNAL_SOURCE
    'moderate_post': 'Content.U.moderate',  # P_MODERATE
    'discussion_stats': 'Conversation.U.stats',  # P_DISC_STATS
    'override_autologin': 'Conversation.A.User.override_autologin',  # P_OVERRIDE_SOCIAL_AUTOLOGIN
}

owner_correspondances = {
    'delete_my_post': 'delete_post',  # P_DELETE_MY_POST
    'edit_my_extract': 'edit_extract'  # P_EDIT_MY_EXTRACT
}

extra_permissions = {
    'Content.C.Extract': ['Idea.A.Extract'],
    'Conversation.R': ['Idea.R']
}

def upgrade(pyramid_env):
    with context.begin_transaction():
        op.alter_column('permission', 'name', existing_type=sa.String(20), type_=sa.String())

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        role_ids = dict(list(db.execute('select name, id from role')))
        if 'r:owner' not in role_ids:
            db.execute("INSERT INTO role (name) VALUES ('r:owner')")
            role_ids = dict(list(db.execute('select name, id from role')))
        permission_ids = dict(list(db.execute('select name, id from permission')))
        for before, after in owner_correspondances.items():
            db.execute("UPDATE discussion_permission SET role_id=%d, permission_id=%d WHERE permission_id=%d" % (
                role_ids['r:owner'], permission_ids[after], permission_ids[before]))
            db.execute("DELETE FROM permission WHERE id=%d" % permission_ids[before])
        for source, target in renames.items():
            db.execute("UPDATE permission SET name='%s' WHERE id = %d" % (target, permission_ids[source]))
        new_names = set(chain(*extra_permissions.values())) - set(permission_ids.keys())
        for name in new_names:
            db.execute("INSERT INTO permission (name) VALUES ('%s')" % name)
        permission_ids = dict(list(db.execute('select name, id from permission')))
        for source, targets in extra_permissions.items():
            for target in targets:
                db.execute("""INSERT INTO discussion_permission (role_id, discussion_id, permission_id)
                    SELECT role_id, discussion_id, %d FROM discussion_permission
                    WHERE permission_id=%d""" % (permission_ids[target], permission_ids[source]))
        mark_changed()
        

def downgrade(pyramid_env):
    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        permission_ids = dict(list(db.execute('select name, id from permission')))
        new_names = set(chain(*extra_permissions.values()))
        for name in new_names:
            db.execute("DELETE FROM discussion_permission WHERE permission_id=%d" % (permission_ids[name]))
            db.execute("DELETE from permission WHERE id=%d" % (permission_ids[name]))
        for source, target in renames.items():
            db.execute("UPDATE permission SET name='%s' WHERE id = %d" % (source, permission_ids[target]))
        # the original role of r:owner discussion_permissions is lost. Only restore the permission itself
        for name in owner_correspondances.keys():
            db.execute("INSERT INTO permission (name) VALUES ('%s')" % name)
        mark_changed()

    with context.begin_transaction():
        op.alter_column('permission', 'name', existing_type=sa.String(), type_=sa.String(20))

