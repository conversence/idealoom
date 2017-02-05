"""connected_user

Revision ID: 164b0fe5831b
Revises: 116f128b0000
Create Date: 2017-02-05 14:24:27.758440

"""

# revision identifiers, used by Alembic.
revision = '164b0fe5831b'
down_revision = '116f128b0000'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('last_connected', sa.DateTime()))
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('last_disconnected', sa.DateTime()))


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('agent_status_in_discussion', 'last_connected')
        op.drop_column('agent_status_in_discussion', 'last_disconnected')
