"""description in synthesis

Revision ID: cfdb3b895127
Revises: d1d922f0cf3a
Create Date: 2018-04-21 20:28:51.348799

"""

# revision identifiers, used by Alembic.
revision = 'cfdb3b895127'
down_revision = 'd1d922f0cf3a'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'sub_graph_idea_association',
            sa.Column('include_body', sa.Boolean, server_default='false'))


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column(
            'sub_graph_idea_association', 'include_body')
