"""new annotation selectors

Revision ID: 732b37ab3da2
Revises: f9d398793b56
Create Date: 2019-04-22 14:55:17.899524

"""

# revision identifiers, used by Alembic.
revision = '732b37ab3da2'
down_revision = 'f9d398793b56'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column('extract', sa.Column('external_url', sa.String))
        op.add_column(
            'annotation_selector',
            sa.Column('body', sa.UnicodeText))
        op.execute('''UPDATE annotation_selector AS asel SET body = (
            SELECT body FROM text_fragment_identifier AS tfi
            WHERE tfi.id = asel.id)''')
        op.drop_column('text_fragment_identifier', 'body')

        op.create_table(
            'text_quote_selector',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                "annotation_selector.id", ondelete='CASCADE', onupdate='CASCADE'),
                primary_key=True),
            sa.Column('prefix', sa.UnicodeText),
            sa.Column('suffix', sa.UnicodeText))

        op.create_table(
            'text_position_selector',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                "annotation_selector.id", ondelete='CASCADE', onupdate='CASCADE'),
                primary_key=True),
            sa.Column('start', sa.Integer),
            sa.Column('end', sa.Integer))

        op.create_table(
            'fragment_selector',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                "annotation_selector.id", ondelete='CASCADE', onupdate='CASCADE'),
                primary_key=True),
            sa.Column('value', sa.Unicode))


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('extract', 'external_url')
        op.drop_table('text_quote_selector')
        op.drop_table('text_position_selector')
        op.drop_table('fragment_selector')
        op.execute("DELETE FROM annotation_selector WHERE type != 'AnnotatorRange'")
        op.add_column(
            'text_fragment_identifier',
            sa.Column('body', sa.UnicodeText))
        op.execute('''UPDATE text_fragment_identifier AS tfi SET body = (
            SELECT body FROM annotation_selector AS asel
            WHERE asel.id = tfi.id)''')
        op.drop_column('annotation_selector', 'body')
