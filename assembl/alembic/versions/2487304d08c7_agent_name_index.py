"""agent name index

Revision ID: 2487304d08c7
Revises: cdb5d8b8f003
Create Date: 2017-10-17 13:33:05.288164

"""

# revision identifiers, used by Alembic.
revision = '2487304d08c7'
down_revision = 'cdb5d8b8f003'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_index(
            "agent_profile_name_vidx",
            'agent_profile',
            [sa.text("to_tsvector('simple', 'name')")],
            postgresql_using='gin')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_index("agent_profile_name_vidx", "agent_profile")
