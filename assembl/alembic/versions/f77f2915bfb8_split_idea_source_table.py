"""split idea_source table

Revision ID: f77f2915bfb8
Revises: 8be3def744e9
Create Date: 2019-04-14 14:32:25.972806

"""

# revision identifiers, used by Alembic.
revision = 'f77f2915bfb8'
down_revision = '8be3def744e9'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.rename_table('idea_source', 'import_record_source')
        op.create_table(
            'idea_source',
            sa.Column('id', sa.Integer,
                sa.ForeignKey('import_record_source.id'), primary_key=True),
            sa.Column('target_state_id', sa.Integer, sa.ForeignKey(
                'publication_state.id', ondelete="SET NULL", onupdate="CASCADE")))
        op.execute('''INSERT INTO idea_source (id, target_state_id) 
            SELECT id, target_state_id FROM import_record_source''')
        op.drop_constraint('idealoom_idea_source_id_fkey', 'idealoom_idea_source')
        op.create_foreign_key(
            'idealoom_idea_source_id_fkey',
            'idealoom_idea_source', 'idea_source',
            ['id'], ['id'])
        op.drop_column('import_record_source', 'target_state_id')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'import_record_source', sa.Column('target_state_id', sa.Integer, sa.ForeignKey(
                'publication_state.id', ondelete="SET NULL", onupdate="CASCADE")))
        op.execute('''UPDATE import_record_source SET target_state_id = (
            SELECT idea_source.target_state_id FROM idea_source
            WHERE idea_source.id=import_record_source.id)''')
        op.drop_constraint('idealoom_idea_source_id_fkey', 'idealoom_idea_source')
        op.drop_table('idea_source')
        op.rename_table('import_record_source', 'idea_source')
        op.create_foreign_key(
            'idealoom_idea_source_id_fkey',
            'idealoom_idea_source', 'idea_source',
            ['id'], ['id'])
