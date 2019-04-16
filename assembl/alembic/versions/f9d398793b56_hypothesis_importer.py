"""hypothesis importer

Revision ID: f9d398793b56
Revises: f77f2915bfb8
Create Date: 2019-04-14 15:51:33.618662

"""

# revision identifiers, used by Alembic.
revision = 'f9d398793b56'
down_revision = 'f77f2915bfb8'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table(
            'hypothesis_extract_source',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                "import_record_source.id"), primary_key=True),
            sa.Column('api_key', sa.String),
            sa.Column('user', sa.String),
            sa.Column('group', sa.String),
            sa.Column('tag', sa.Unicode),
            sa.Column('document_url', sa.Unicode))


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table('hypothesis_extract_source')
