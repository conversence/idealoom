"""urireftable

Revision ID: a33ea73a4b2e
Revises: 5baafd563d59
Create Date: 2017-09-10 10:02:13.323941

"""

# revision identifiers, used by Alembic.
revision = 'a33ea73a4b2e'
down_revision = '5baafd563d59'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table(
            'uriref',
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("val", sa.Unicode, nullable=False, unique=True),
        )


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table('uriref')
