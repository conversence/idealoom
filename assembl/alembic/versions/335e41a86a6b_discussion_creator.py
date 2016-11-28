"""discussion creator

Revision ID: 335e41a86a6b
Revises: 33b361960ee7
Create Date: 2016-11-14 12:32:52.653637

"""

# revision identifiers, used by Alembic.
revision = '335e41a86a6b'
down_revision = '33b361960ee7'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column('discussion', sa.Column(
            'creator_id', sa.Integer, sa.ForeignKey('user.id', ondelete="SET NULL")))

def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('discussion', 'creator_id')
