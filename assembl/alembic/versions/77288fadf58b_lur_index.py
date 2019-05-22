"""lur_index

Revision ID: 77288fadf58b
Revises: 243942b0a23d
Create Date: 2019-05-22 16:53:17.363166

"""

# revision identifiers, used by Alembic.
revision = '77288fadf58b'
down_revision = '243942b0a23d'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_index(
            'ix_local_user_role_user_discussion',
            'local_user_role', ['profile_id', 'discussion_id'], unique=False)
        op.create_index(
            'ix_idea_local_user_role_user_idea',
            'idea_user_role', ['profile_id', 'idea_id'], unique=False)


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_index(
            'ix_local_user_role_user_discussion', 'local_user_role')
        op.drop_index(
            'ix_idea_local_user_role_user_idea', 'idea_user_role')
