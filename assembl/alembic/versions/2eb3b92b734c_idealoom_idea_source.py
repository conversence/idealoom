"""idealoom_idea_source

Revision ID: 2eb3b92b734c
Revises: dcc412989fc6
Create Date: 2019-02-28 09:29:34.687895

"""

# revision identifiers, used by Alembic.
revision = '2eb3b92b734c'
down_revision = 'dcc412989fc6'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column('idea_source', sa.Column('source_uri', sa.String, nullable=False))
        op.add_column('idea_source', sa.Column('data_filter', sa.String))
        op.add_column(
            'idea_source', sa.Column('target_state_id', sa.Integer, sa.ForeignKey(
                'publication_state.id', ondelete="SET NULL", onupdate="CASCADE")))
        op.execute("""UPDATE idea_source SET source_uri = (
            SELECT val FROM uriref WHERE uriref.id = idea_source.uri_id)""")
        op.drop_column('idea_source', 'uri_id')
        op.create_table(
            'idealoom_idea_source',
                sa.Column('id', sa.Integer, sa.ForeignKey('idea_source.id'), primary_key=True),
                sa.Column('username', sa.String()),
                sa.Column('password', sa.String())
            )


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table('idealoom_idea_source')
        op.drop_column('idea_source', 'data_filter')
        op.drop_column('idea_source', 'target_state_id')
        op.add_column(
            'idea_source', sa.Column('uri_id', sa.Integer, sa.ForeignKey(
                'uriref.id'), nullable=False, unique=True))
        op.execute("""INSERT INTO uriref (val)
            SELECT DISTINCT source_uri from idea_source
            EXCEPT SELECT val from uriref""")
        op.execute("""UPDATE idea_source SET uri_id = (
            SELECT id FROM uriref WHERE uriref.val = idea_source.source_uri)""")
        op.drop_column('idea_source', 'source_uri')
