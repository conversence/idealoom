"""Extract attribution

Revision ID: cdb5d8b8f003
Revises: 0a6cc006a44b
Create Date: 2017-10-15 22:33:07.851973

"""

# revision identifiers, used by Alembic.
revision = 'cdb5d8b8f003'
down_revision = '0a6cc006a44b'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'extract', sa.Column(
                'attributed_to_id',
                sa.Integer, sa.ForeignKey(
                    'agent_profile.id',
                    ondelete='SET NULL', onupdate='CASCADE')))

def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('extract', 'attributed_to_id')
