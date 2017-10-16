"""text fragment body

Revision ID: 7c400c47389c
Revises: fc307809685e
Create Date: 2017-10-15 13:39:23.423507

"""

# revision identifiers, used by Alembic.
revision = '7c400c47389c'
down_revision = 'fc307809685e'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.alter_column('extract', 'body', nullable=True, existing_nullable=False)
        op.add_column('text_fragment_identifier', sa.Column('body', sa.UnicodeText))
        op.execute('''UPDATE text_fragment_identifier SET body = (
            SELECT body FROM extract
            WHERE extract.id = text_fragment_identifier.extract_id
            AND length(body) > 0)''')
        op.execute('''UPDATE extract SET body = NULL WHERE id NOT IN (
            SELECT idea_content_link.id FROM idea_content_link JOIN content ON (content.id=idea_content_link.content_id)
            WHERE content.type = 'webpage')''')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.execute('''UPDATE extract SET body = (
            SELECT COALESCE(body, '') FROM text_fragment_identifier
            WHERE extract.id = text_fragment_identifier.extract_id
            LIMIT 1) WHERE id NOT IN (
            SELECT idea_content_link.id FROM idea_content_link JOIN content ON (content.id=idea_content_link.content_id)
            WHERE content.type = 'webpage')''')
        op.alter_column('extract', 'body', nullable=False, existing_nullable=True)
        op.drop_column('text_fragment_identifier', 'body')
