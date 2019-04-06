"""idea_source__update_back_imports

Revision ID: 8be3def744e9
Revises: 92c7d8fc1ce3
Create Date: 2019-04-05 13:45:06.315691

"""

# revision identifiers, used by Alembic.
revision = '8be3def744e9'
down_revision = '92c7d8fc1ce3'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'idea_source', sa.Column('update_back_imports', sa.Boolean))


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('idea_source', 'update_back_imports')
