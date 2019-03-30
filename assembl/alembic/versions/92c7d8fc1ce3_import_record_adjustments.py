"""import_record adjustments

Revision ID: 92c7d8fc1ce3
Revises: b362d627b307
Create Date: 2019-03-30 11:08:52.736522

"""

# revision identifiers, used by Alembic.
revision = '92c7d8fc1ce3'
down_revision = 'b362d627b307'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_constraint('import_record_source_id_fkey', 'import_record')
        op.create_foreign_key(
            'import_record_source_id_fkey', 'import_record', 'content_source',
            ['source_id'], ['id'], ondelete="CASCADE", onupdate="CASCADE")
        op.execute("""ALTER TABLE import_record DROP CONSTRAINT IF EXISTS
            import_record_source_id_target_id_target_table_key""")
        op.execute("""ALTER TABLE import_record
            ADD CONSTRAINT import_record_target_id_target_table_key
            UNIQUE (target_id, target_table)""")
    try:
        with context.begin_transaction():
            op.execute("""ALTER TABLE import_record
                ADD CONSTRAINT import_record_source_id_external_id_key
                UNIQUE (source_id, external_id)""")
    except:
        pass  # this constraint may or may not be already present


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_constraint('import_record_source_id_fkey', 'import_record')
        op.create_foreign_key(
            'import_record_source_id_fkey', 'import_record', 'idea_source',
            ['source_id'], ['id'], ondelete="CASCADE", onupdate="CASCADE")
        op.execute("ALTER TABLE import_record DROP CONSTRAINT import_record_target_id_target_table_key")
        op.execute("""ALTER TABLE import_record
            ADD CONSTRAINT import_record_source_id_target_id_target_table_key
            UNIQUE (source_id, target_id, target_table)""")
