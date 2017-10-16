"""kill extract.body

Revision ID: 0a6cc006a44b
Revises: 7c400c47389c
Create Date: 2017-10-15 22:20:08.800849

"""

# revision identifiers, used by Alembic.
revision = '0a6cc006a44b'
down_revision = '7c400c47389c'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('extract', 'body')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column('extract', sa.Column('body', sa.UnicodeText))
